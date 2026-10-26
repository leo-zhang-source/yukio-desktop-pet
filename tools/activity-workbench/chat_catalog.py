"""Local navigation metadata. Never merge conversations or send paths to a model."""
import hashlib
import json
import posixpath
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from source_context import clean
from localization import current_language, english_text


def catalog_card(history, reader, client, group, clock):
    """Build navigation from scoped metadata; don't reconstruct every task."""
    from history_view import key_parts, CLIENT, FROM
    from collector_status import read_status
    parts=key_parts(group['key']);scope,args=history.scope(parts)
    with history.connect(client) as db:
        saved=db.execute('SELECT state FROM sources WHERE source_id=?',(parts[0],)).fetchone()
        if not saved:raise ValueError('Unknown source')
        state=json.loads(saved[0])
        if state.get('generation')!=parts[1]:raise ValueError('Old source')
        rows=[(seq,json.loads(raw)) for seq,raw in db.execute('SELECT e.sequence,e.record'+FROM+f' WHERE {scope} AND {CLIENT}=? ORDER BY e.sequence DESC LIMIT 80',args+[client])]
        marker=db.execute('SELECT e.sequence,e.record'+FROM+f" WHERE {scope} AND {CLIENT}=? AND json_extract(e.record,'$.kind') IN ('turn_started','turn_ended','turn_cancelled') ORDER BY e.sequence DESC LIMIT 1",args+[client]).fetchone()
        speech=db.execute('SELECT e.sequence,e.record'+FROM+f" WHERE {scope} AND {CLIENT}=? AND json_extract(e.record,'$.source_kind') IN ('message','user_message','user') ORDER BY e.sequence LIMIT 5",args+[client]).fetchall()
    title,path=reader.title_and_path(client,parts[2],parts[0])
    has_client_title=bool(title)
    available=False
    if path and reader.permitted(path,client,parts[0]):
        try:
            info=path.stat();available=state.get('file_identity')=='%s:%s'%(info.st_dev,info.st_ino)
        except OSError:pass
    material=reader.read(client,parts,state,[(seq,json.loads(raw)) for seq,raw in speech]) if available and (not title or client!='codex') else {}
    if not title:
        opening=next((item['text'] for item in material.get('items',[]) if item['kind']=='user'),'')
        title=re.split(r'[。！？\n]',opening, maxsplit=1)[0][:52]
    meaningful=[(seq,row) for seq,row in rows if row.get('kind') not in ('reasoning_record_observed','inherited_context_record','context_record_observed','identity_conflict','foreign_session_record','identity_scope_unresolved') and row.get('source_kind') not in ('token_count','token_usage_record','thread_settings_applied')]
    stamp=next((row['timestamp_ms'] for _,row in meaningful if type(row.get('timestamp_ms')) in (float,int)),None)
    age=max(0,clock()-(stamp or 0)/1000) if stamp is not None else None
    marker_kind=json.loads(marker[1]).get('kind') if marker else None
    later=any(seq>(marker[0] if marker else 0) and row.get('kind') in ('tool_requested','tool_result','message_observed','text_record_observed') for seq,row in meaningful)
    status='刚有新活动' if age is not None and age<90 else '暂时没有新消息'
    if marker_kind=='turn_ended' and not later:status='这一轮已结束'
    elif marker_kind=='turn_cancelled' and not later:status='这一轮已取消'
    latest=meaningful[0][1] if meaningful else {}
    tone='attention' if latest.get('reported_await_user_response') is True and marker_kind not in ('turn_ended','turn_cancelled') else 'quiet'
    card=dict(client=client,key=group['key'],session_id=parts[2],title=readable_title(title),
              title_source='客户端聊天名称' if has_client_title else ('开场要求' if title else '名称待确认'),status=status,tone=tone,last_activity_ms=stamp,
              source_unavailable=not available,turn_marker=marker_kind,age_seconds=age,
              recorder=read_status(history.databases[client],client))
    card['activity_state']=activity_state(card)
    card['project']=codex_project(reader,parts) if client=='codex' and available else material.get('project')
    return card


def readable_title(value):
    text = clean(value, 100)
    if not text or '暂未取得聊天名称' in text:
        return english_text('未命名聊天') if current_language()=='en' else '未命名聊天'
    if re.search(r'<(?:bash|tool|command)[\s>-]|(?:^|\s)(?:pkill\s|rm\s+-|python3?\s+-|curl\s)|^[/\\]|^@?[\x22\x27]?~[/\\]|^[A-Za-z]:[/\\]|^\[代码略\]', text, re.I):
        return english_text('本机操作记录') if current_language()=='en' else '本机操作记录'
    return text


def activity_state(detail):
    # A recent message or a successful tool result is not proof of an open turn.
    if detail.get('source_unavailable') or detail.get('recorder', {}).get('state') in ('stopped', 'failed', 'stale', 'unavailable', 'source_unavailable', 'paused_capacity'):
        return 'unknown'
    if detail.get('tone') == 'attention':
        return 'waiting'
    if detail.get('status') in ('这一轮已结束', '这一轮已取消'):
        return 'inactive'
    age = detail.get('age_seconds')
    if detail.get('turn_marker') == 'turn_started' and isinstance(age, (float, int)) and age < 120:
        return 'working'
    return 'unknown'


def normalize_workspace(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or re.search(r'[\x00-\x1f]', value):
        return ''
    value = value.replace('\\', '/')
    if not value.startswith('/') and not re.match(r'^[A-Za-z]:/', value):
        return ''
    return posixpath.normpath(value)


def project_label(workspace, *, client, explicit=None, roots=()):
    workspace = normalize_workspace(workspace)
    if not workspace:
        return None
    match = explicit
    if not match:
        candidates = []
        for key, name, root in roots:
            root = normalize_workspace(root)
            if root and (workspace == root or workspace.startswith(root.rstrip('/') + '/')):
                candidates.append((len(root), key, name))
        if candidates:
            length = max(c[0] for c in candidates)
            matches = {(key, name) for size, key, name in candidates if size == length}
            if len(matches) == 1:
                match = next(iter(matches))
    name = readable_title(match[1]) if match else readable_title(posixpath.basename(workspace))
    if not name or name == '未命名聊天':
        return None
    identity = client + ':' + ('project:' + str(match[0]) if match else 'workspace:' + workspace)
    return dict(id=hashlib.sha256(identity.encode()).hexdigest()[:24], name=name,
                source='client_project' if match else 'workspace')


def codex_project(reader, parts):
    root = reader.roots.get('codex')
    if root is None:
        return None
    path = root.parent / 'state_5.sqlite'
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.2)) as db:
            db.execute('PRAGMA query_only=ON')
            deadline = time.monotonic() + .2
            db.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
            columns = {row[1] for row in db.execute('PRAGMA table_info(threads)')}
            if not {'cwd', 'rollout_path'} <= columns:
                return None
            row = db.execute('SELECT cwd,rollout_path,' + ('project_id' if 'project_id' in columns else 'NULL') + ' FROM threads WHERE id=? LIMIT 1', (parts[2],)).fetchone()
            if not row or not reader.permitted(row[1], 'codex', parts[0]):
                return None
            roots = []; explicit = None
            try:
                roots = db.execute('SELECT p.id,p.name,r.path FROM projects p JOIN project_roots r ON r.project_id=p.id LIMIT 1000').fetchall()
                if row[2]:
                    explicit = db.execute('SELECT id,name FROM projects WHERE id=? LIMIT 1', (row[2],)).fetchone()
            except sqlite3.Error:
                pass  # Older client databases can still supply a workspace name.
            return project_label(row[0], client='codex', explicit=explicit, roots=roots)
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return None
