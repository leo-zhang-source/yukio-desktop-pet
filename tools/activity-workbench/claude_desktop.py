"""Read-only Claude Desktop chat identity, separate from transcript evidence.

A desktop chat can own several CLI transcripts after rewinds. Only the client's
explicit current/prior IDs connect them; titles, directories and timing never do.
Unrecognized, conflicting or unavailable metadata cannot authorize a merge.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import uuid


ENDED_ON_QUESTION=dict(status='等待你回答',tone='attention',needs_you='Claude 在这一轮结束时提了一个问题，要等你回答才能继续。请回原聊天回答。')


def ended_on_blocking_question(marker_row, marker_kind, later):
    """The latest turn closed on the client's own blocking question and nothing followed."""
    return marker_kind=='turn_ended' and not later and marker_row.get('reported_blocked_on_user') is True


def lifecycle_snapshot(state, session):
    """Use the Claude adapter's durable state, not another client's wait flag."""
    from yukio.parsers_claude import ClaudeTranscriptParser
    try:
        saved=json.loads(state['checkpoint'])
        return ClaudeTranscriptParser.from_history_checkpoint(saved['lifecycle']).snapshot(session)
    except (KeyError, TypeError, ValueError, RecursionError):return None


def apply_interaction(detail, state, session, interactions=None, runtime=None):
    snapshot=lifecycle_snapshot(state,session)
    if snapshot is None:return
    presence=runtime.get(session) if runtime is not None else None
    if presence:
        snapshot=dict(snapshot,client_status=presence['status'])
        if presence['status']=='offline' and snapshot['phase'] not in ('completed','cancelled','failed'):
            snapshot['phase']='offline'
        elif presence['status']=='waiting' and presence['updated_at'] >= (snapshot['timestamp'] or 0):
            snapshot['phase']='waiting'
    live=interactions.get(session) if interactions is not None else None
    # A stale hook from a previous turn cannot replace this turn or a terminal
    # receipt. Receipt time is only used to scope a live channel, never to end work.
    if live and snapshot['phase']!='offline' and live['created_at'] >= (snapshot['started_at'] or 0) and (
            snapshot['phase'] not in ('completed','cancelled','failed') or live['created_at'] > (snapshot['timestamp'] or 0)):
        snapshot=dict(snapshot,phase='waiting',interaction_kind=live['kind'],channel='live',
                      question_call_id=live.get('call_id'),question_index=live.get('index'))
    detail['claude_lifecycle']=snapshot
    if detail.get('source_unavailable'):return
    if snapshot['phase']=='waiting':
        permission=snapshot.get('interaction_kind')=='permission'
        detail.update(status='等待你批准' if permission else '等待你回答',tone='attention',
                      needs_you='Claude 正在等你批准这次操作。' if permission else 'Claude 正在等你回答问题。')
    elif snapshot['phase']=='completed' and detail.get('ended_on_question') is True:
        # The turn is over, but it closed on the client's blocking question.
        detail.update(ENDED_ON_QUESTION)
    elif snapshot['phase'] in ('completed','cancelled'):
        detail.update(status='这一轮已结束' if snapshot['phase']=='completed' else '这一轮已取消',tone='quiet')
    elif snapshot['phase']=='failed':
        detail.update(status='这一轮因错误停止',tone='quiet',needs_you='Claude 报告了错误，请回原聊天查看。')
    elif snapshot['phase']=='offline':
        detail.update(status='Claude 客户端已退出',tone='quiet',needs_you='请回原聊天继续；退出不代表任务完成。')


class ClaudeInteractionIndex:
    """Read an already-configured local answer channel. Never install a hook.

    Only lease/identity facts leave this reader; questions and answers are not
    copied into history or sent to an explanation provider.
    """
    def __init__(self, root=None, *, clock=time.time):
        self.root=Path(root) if root is not None else None
        self.clock=clock;self.checked=None;self.cache={};self.lock=threading.Lock()

    def get(self, session):
        with self.lock:
            now=self.clock()
            if self.checked is not None and now-self.checked<.25:return self.cache.get(session)
            result={}
            if self.root is not None and self.root.is_dir() and not self.root.is_symlink():
                try:
                    paths=sorted(self.root.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True)[:512]
                    for path in paths:
                        try:
                            uuid.UUID(path.name)
                            if path.is_symlink() or not path.is_dir():continue
                            request=path/'request.json';info=request.lstat()
                            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>1<<20:continue
                            with request.open('rb') as stream:raw=stream.read((1<<20)+1)
                            if len(raw)>1<<20:continue
                            row=json.loads(raw)
                            if row.get('id')!=path.name or row.get('provider','claude')!='claude':continue
                            if type(row.get('pid')) is not int or row['pid']<=0:continue
                            if type(row.get('expiresAt')) not in (int,float) or not math.isfinite(row['expiresAt']) or row['expiresAt']<=now*1000:continue
                            if type(row.get('createdAt')) not in (int,float) or not 0<=row['createdAt']<=now*1000+1000:continue
                            if (path/'done').exists():continue
                            os.kill(row['pid'],0)
                            questions=row.get('questions')
                            if not isinstance(questions,list) or not 1<=len(questions)<=64:continue
                            pending=[(n,q) for n,q in enumerate(questions) if not (path/('receipt-%d.json'%n)).exists()]
                            sid=row.get('session')
                            if pending and isinstance(pending[0][1],dict) and isinstance(sid,str) and 0<len(sid)<=256 and sid not in result:
                                call=row.get('callID')
                                result[sid]=dict(created_at=row['createdAt'],kind='permission' if pending[0][1].get('approval') is True else 'question',
                                                 call_id=call if isinstance(call,str) and len(call)<=256 else None,index=pending[0][0])
                        except (OSError,ValueError,TypeError,RecursionError):continue
                except OSError:pass
            self.cache=result;self.checked=now
            return result.get(session)

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 512
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')


def default_directory(transcripts):
    # Custom source roots (including test/import profiles) must never borrow
    # another profile's desktop metadata. Current platform scope is macOS.
    if sys.platform == 'darwin' and transcripts is not None:
        if Path(transcripts).resolve() == (Path.home()/'.claude/projects').resolve():
            return Path.home()/'Library/Application Support/Claude/claude-code-sessions'
    return None


class ClaudeDesktopIndex:
    def __init__(self, root, *, clock=time.monotonic):
        self.root=Path(root) if root is not None else None
        self.clock=clock;self.lock=threading.Lock();self.checked=None;self.cache={};self.mapping={}

    def _paths(self):
        if self.root is None or self.root.is_symlink() or not self.root.is_dir():return []
        paths=[];visited=0
        def children(directory):
            nonlocal visited
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        visited+=1
                        if visited>4096:return
                        if not entry.is_symlink():yield Path(entry.path)
            except OSError:return
        # Only account/org/local_UUID.json, never arbitrary recursive files.
        for account in children(self.root):
            if not account.is_dir():continue
            for org in children(account):
                if not org.is_dir():continue
                for path in children(org):
                    if path.name.startswith('local_') and path.suffix=='.json':
                        paths.append(path)
                        if len(paths)>=MAX_FILES:return paths
        return paths

    def _metadata(self, path, info):
        descriptor=None
        try:
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_FILE or not path.resolve().is_relative_to(self.root.resolve()):return None
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            with os.fdopen(descriptor,'rb') as stream:
                descriptor=None;before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_FILE:return None
                raw=stream.read(MAX_FILE+1);after=os.fstat(stream.fileno())
            signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if len(raw)>MAX_FILE or signature(info)!=signature(before) or signature(before)!=signature(after):return None
            row=json.loads(raw)
            if not isinstance(row,dict):return None
            local=row.get('sessionId');current=row.get('cliSessionId');prior=row.get('priorCliSessionIds',[])
            if not isinstance(local,str) or local!=path.stem or not UUID.fullmatch(local.removeprefix('local_')):return None
            if not isinstance(current,str) or not UUID.fullmatch(current):return None
            if not isinstance(prior,list) or len(prior)>256 or any(not isinstance(p,str) or not UUID.fullmatch(p) for p in prior):return None
            archived=row.get('isArchived',False)
            if type(archived) is not bool:return None
            title=row.get('title','')
            if not isinstance(title,str) or len(title)>2048:title=''
            identity=hashlib.sha256((str(path.parent.relative_to(self.root))+'/'+local).encode()).hexdigest()
            # Discard prompts, tool settings, credentials and all other fields.
            return dict(id=identity,current=current,members=list(dict.fromkeys([current]+prior)),title=title,archived=archived)
        except (OSError,ValueError,RecursionError):return None
        finally:
            if descriptor is not None:os.close(descriptor)

    def snapshot(self):
        with self.lock:
            now=self.clock()
            if self.checked is not None and now-self.checked<2:return self.mapping
            updated={};budget=MAX_TOTAL
            try:paths=self._paths()
            except OSError:paths=[]
            for path in paths:
                try:
                    info=path.stat();signature=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
                    cached=self.cache.get(path)
                    if cached and cached[0]==signature:entry=cached[1]
                    else:
                        if info.st_size>budget:continue
                        budget-=info.st_size;entry=self._metadata(path,info)
                    updated[path]=(signature,entry)
                except OSError:continue
            claims={};entries=[entry for _,entry in updated.values() if entry]
            for entry in entries:
                for cli in entry['members']:claims.setdefault(cli,set()).add(entry['id'])
            mapping={}
            for entry in entries:
                if len(claims[entry['current']])!=1:continue
                members=[cli for cli in entry['members'] if len(claims[cli])==1]
                entry=dict(entry,members=members)
                for cli in members:mapping[cli]=entry
            self.cache=updated;self.mapping=mapping;self.checked=now
            return mapping
