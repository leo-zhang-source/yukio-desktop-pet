"""Read-only Claude Desktop chat identity, separate from transcript evidence.

A desktop chat can own several CLI transcripts after rewinds. Only the client's
explicit current/prior IDs connect them; titles, directories and timing never do.
Unrecognized, conflicting or unavailable metadata cannot authorize a merge.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time

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
