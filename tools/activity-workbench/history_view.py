"""Read-only, bounded presentation of saved evidence. Never open transcripts.

A view is one database/client, source file, generation, session, agent and sidechain.
No task completion is inferred, and no calls are joined by the presentation layer.
"""
import base64
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import time

APPLICATION_ID = 1498762063
CLIENTS = {'codex': 'Codex', 'claude': 'Claude', 'deepcode': 'Deep Code'}
SOURCE = "json_extract(e.record, '$.source_id')"
GENERATION = "json_extract(e.record, '$.generation')"
AGENT = "coalesce(json_extract(e.record, '$.agent_id'), '')"
SIDECHAIN = "coalesce(json_extract(e.record, '$.is_sidechain'), 0)"
CLIENT = "json_extract(e.record, '$.source')"
SESSION = "coalesce(e.session_id, '')"
CURRENT = "json_extract(s.state, '$.generation')"
FROM = f' FROM events e JOIN sources s ON s.source_id={SOURCE}'
SAFE_FIELDS = {
    'event_id', 'evidence_id', 'sequence', 'source', 'source_id', 'generation',
    'source_line', 'source_offset', 'next_offset', 'source_record_sha256',
    'source_fragment_sha256', 'kind', 'source_kind', 'evidence_class', 'session_id',
    'agent_id', 'is_sidechain', 'thread_id', 'turn_id', 'context_turn_id', 'call_id', 'item_id',
    'tool_name', 'association', 'turn_association', 'outcome', 'call_outcome',
    'projection_eligible', 'conflicting_results', 'exit_code', 'reported_status',
    'reported_is_error', 'reported_ok', 'reported_interrupted',
    'reported_await_user_response', 'background_task_reported',
    'result_flags_conflict', 'request_evidence_id', 'after_gap_evidence_id',
    'gap_evidence_id', 'gap_part', 'gap_start_offset', 'skipped_bytes',
    'total_record_bytes', 'record_complete', 'reason', 'history_scope',
    'block_index', 'timestamp_ms', 'timestamp_available', 'reported_stop_reason',
}
RELATION_FIELDS = {'kind', 'from_session_id', 'to_session_id', 'basis', 'status', 'evidence_class'}


def safe_fields(value, allowed=SAFE_FIELDS):
    if not isinstance(value, dict):
        return {}
    out = {key: item for key, item in value.items() if key in allowed and (
        isinstance(item, str) and len(item) <= 2048 or type(item) is bool or
        type(item) is int and abs(item) <= 2**63 or
        type(item) is float and math.isfinite(item) and abs(item) <= 2**63)}
    if allowed is SAFE_FIELDS and isinstance(value.get('handoff'),dict):
        out['handoff'] = safe_handoff(value['handoff'])
    return out


def safe_handoff(value):
    out=safe_fields(value,{'form','action','call','sender','status','prompt_present','prompt_sha256','invalid_targets','created_agent','interrupted'})
    out['targets']=[v for v in value.get('targets',[])[:32] if isinstance(v,str) and len(v)<=256] if isinstance(value.get('targets'),list) else []
    states=value.get('states',{})
    out['states']={k:safe_fields(v,{'state','has_message'}) for k,v in list(states.items())[:32] if isinstance(k,str) and len(k)<=256 and isinstance(v,dict)} if isinstance(states,dict) else {}
    return out


def key_for(parts):
    return base64.urlsafe_b64encode(json.dumps(parts, ensure_ascii=True, separators=(',', ':')).encode()).decode().rstrip('=')


def key_parts(key):
    try:
        if not isinstance(key, str) or len(key) > 8000:
            raise ValueError()
        parts = json.loads(base64.b64decode(key + '=' * (-len(key) % 4), altchars=b'-_', validate=True))
        if (not isinstance(parts, list) or len(parts) != 5 or
                any(not isinstance(parts[i], str) or len(parts[i]) > 1024 for i in (0, 2, 3)) or
                type(parts[1]) is not int or not 1 <= parts[1] < 2**31 or
                type(parts[4]) is not int or parts[4] not in (0,1) or key_for(parts) != key):
            raise ValueError()
        return parts
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('Invalid view') from None


KINDS = {
    'tool_requested': ('已发起一个操作', '请求已被记录；这不代表操作已经执行成功。'),
    'turn_started': ('开始了一轮工作', '客户端记录了开始标记。'),
    'turn_context': ('记录了本轮工作信息', '用于区分不同轮次，不代表任务完成。'),
    'turn_ended': ('这一轮已结束', '客户端报告本轮结束；仍不能据此确认整项任务完成或已获用户验收。'),
    'turn_cancelled': ('这一轮已取消', '客户端记录了取消标记。'),
    'session_observed': ('发现了聊天身份', '这里只展示客户端明确报告的身份和关系。'),
    'inherited_context_record': ('附带的旧聊天记录', '保留作参考，不算这位助手新做的工作。'),
    'context_record_observed': ('上下文参考记录', '这是供助手参考的信息，不算新的执行结果。'),
    'context_boundary': ('聊天上下文发生整理', '此前的操作不能仅靠相同编号继续配对。'),
    'observation_gap': ('这里有一段没有读到', '这条内容超过读取上限。已留下缺口，后面的正常记录可以继续保存。'),
    'source_reset': ('记录文件发生变化', '已开始一个新的观察版本，旧版本仍保留。'),
    'invalid_record': ('这条记录无法辨认', '不能据此推断其中发生了什么。'),
    'identity_scope_unresolved': ('无法确定这条记录属于谁', '先保留证据，不把它算到某位助手名下。'),
    'identity_conflict': ('身份信息有冲突', '这条记录不能作为可靠的任务归属依据。'),
    'foreign_session_record': ('记录提到了另一个聊天', '只保留报告的身份，不与当前聊天合并。'),
    'reasoning_record_observed': ('出现了一条思考记录', '这里只保存类型标记，没有保存或读取完整内部思考。'),
    'text_record_observed': ('出现了一条文字消息', '没有保存正文，不能根据这个标记确认助手说了什么。'),
    'message_observed': ('出现了一条消息', '这里只保存活动标记，没有聊天正文。'),
    'web_search_observed': ('出现了一次搜索记录', '记录中出现搜索活动；这不代表搜索结果已被核实。'),
    'source_error': ('客户端报告了错误', '有错误标记；没有正文时不能判断具体原因。'),
}
TOOLS = {'Read': '请求读取文件', 'read': '请求读取文件', 'Write': '请求写入文件',
         'write': '请求写入文件', 'Edit': '请求修改文件', 'edit': '请求修改文件',
         'Bash': '请求运行命令', 'bash': '请求运行命令', 'exec_command': '请求运行命令',
         'functions.exec_command': '请求运行命令', 'spawn_agent': '请求委派助手',
         'collaboration.spawn_agent': '请求委派助手', 'web.run': '请求查找网页'}
OUTCOMES = {'succeeded': '成功', 'failed': '失败', 'cancelled': '取消', 'unknown': '不明确'}


def describe(value):
    kind = value.get('kind')
    title, note = KINDS.get(kind, ('保存了一条活动记录', '目前没有足够信息把它解释成更具体的工作。'))
    tone = 'neutral'
    if kind == 'tool_requested':
        title = TOOLS.get(value.get('tool_name'), title)
    if kind == 'tool_result':
        # A receipt stays a receipt. Never turn it into task or user acceptance.
        outcome = value.get('outcome', 'unknown')
        title = '工具回执报告' + OUTCOMES.get(outcome, '不明确')
        note = '这是这次回执的结果，不表示整个任务已完成。'
        tone = 'warning' if outcome in ('failed', 'cancelled', 'unknown') else 'neutral'
        if value.get('conflicting_results') or value.get('result_flags_conflict'):
            title, note, tone = '结果标记有冲突', '保留不同的结果标记，暂不判定这项操作成功或失败。', 'warning'
        elif value.get('projection_eligible') is not True:
            note += ' 对应关系尚不可靠，不能把这个结果算到某次请求上。'
            tone = 'warning'
        elif value.get('call_outcome') == 'unknown':
            note += ' 这项操作的明确结论仍未知。'
    if kind in ('observation_gap', 'invalid_record', 'identity_scope_unresolved', 'identity_conflict', 'foreign_session_record'):
        tone = 'warning'
    return dict(title=title, note=note, tone=tone,
                evidence_label='助手自述标记' if value.get('evidence_class') == 'self_report' else '已观察到的记录')


def present(row, sequence):
    row = dict(row, sequence=sequence)
    evidence = safe_fields(row)
    parts = row.get('blocks')
    # Block paging is separate: never silently discard blocks in a large message.
    count = len(parts) if isinstance(parts, list) else 0
    item = dict(evidence=evidence, block_count=count, **describe(evidence))
    item['preview'] = [dict(evidence=safe_fields(b), **describe(safe_fields(b))) for b in parts[:3]] if count else []
    if isinstance(row.get('result'), dict):
        result = safe_fields(row['result'])
        item.update(describe(dict(result, kind='tool_result')))
        item['result'] = result
    item['relationships'] = [safe_fields(r, RELATION_FIELDS) for r in row.get('relationships', [])[:32] if isinstance(r, dict)]
    item['identity_issues'] = [v for v in row.get('identity_issues', [])[:32] if isinstance(v, str) and len(v) <= 256]
    return item


class HistoryView:
    def __init__(self, databases, *, query_seconds=2):
        if not databases or any(k not in CLIENTS for k in databases):
            raise ValueError('Choose supported local databases')
        self.databases = {k: Path(p).absolute() for k, p in databases.items()}
        self.query_seconds = query_seconds

    @contextmanager
    def connect(self, client):
        if client not in self.databases:
            raise ValueError('Unknown client')
        path = self.databases[client]
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=0.25)
        try:
            deadline = time.monotonic() + self.query_seconds
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            db.execute('PRAGMA query_only=ON')
            db.execute('PRAGMA trusted_schema=OFF')
            if db.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or db.execute('PRAGMA user_version').fetchone()[0] not in (1, 2):
                raise ValueError('Unsupported history database')
            db.execute('BEGIN')
            yield db
        finally:
            db.close()

    def clients(self):
        out = []
        for client in self.databases:
            try:
                with self.connect(client) as db:
                    count, latest = db.execute(f'SELECT count(*), coalesce(max(sequence),0) FROM events e WHERE {CLIENT}=?', (client,)).fetchone()
                out.append(dict(id=client, name=CLIENTS[client], available=True, saved_records=count, revision=latest))
            except (sqlite3.Error, OSError, ValueError):
                out.append(dict(id=client, name=CLIENTS[client], available=False))
        return dict(clients=out, mode='local', explanation='规则说明，尚未使用千问', ordering='保存顺序；不是跨助手的实际执行先后')

    def groups(self, client, *, archive=False, offset=0, limit=30, snapshot=0):
        if type(archive) is not bool or not 0 <= offset <= 100000 or not 1 <= limit <= 50 or snapshot < 0:
            raise ValueError('Invalid page')
        with self.connect(client) as db:
            high = db.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]
            snapshot = min(snapshot, high) if snapshot else high
            where = f' WHERE e.sequence<=? AND {CLIENT}=? AND {GENERATION}' + ('!=' if archive else '=') + CURRENT
            query = f'SELECT {SOURCE}, {GENERATION}, {SESSION}, {AGENT}, {SIDECHAIN}, count(*), max(e.sequence)' + FROM + where
            query += f' GROUP BY {SOURCE}, {GENERATION}, {SESSION}, {AGENT}, {SIDECHAIN} ORDER BY max(e.sequence) DESC LIMIT ? OFFSET ?'
            rows = db.execute(query, (snapshot, client, limit + 1, offset)).fetchall()
            groups = [dict(key=key_for(list(r[:5])), source_id=r[0], generation=r[1], session_id=r[2], agent_id=r[3], is_sidechain=bool(r[4]), records=r[5], last_sequence=r[6], archived=archive) for r in rows[:limit]]
            return dict(groups=groups, snapshot=snapshot, has_more=len(rows)>limit, next_offset=offset+len(groups))

    @staticmethod
    def scope(parts):
        return f'{SOURCE}=? AND {GENERATION}=? AND {SESSION}=? AND {AGENT}=? AND {SIDECHAIN}=?', parts

    def timeline(self, client, key, *, before=0, snapshot=0, limit=40):
        if before < 0 or snapshot < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid page')
        parts = key_parts(key)
        with self.connect(client) as db:
            high = db.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]
            snapshot = min(snapshot, high) if snapshot else high
            scope, args = self.scope(parts)
            state = db.execute('SELECT state FROM sources WHERE source_id=?', (parts[0],)).fetchone()
            if state is None: raise ValueError('Unknown source')
            current = json.loads(state[0])
            query = 'SELECT e.sequence, e.record' + FROM + f' WHERE {scope} AND {CLIENT}=? AND e.sequence<=? AND e.sequence<? ORDER BY e.sequence DESC LIMIT ?'
            rows = db.execute(query, args + [client, snapshot, before or snapshot+1, limit+1]).fetchall()
            items = [present(json.loads(record), seq) for seq, record in rows[:limit]]
            # File-level notices remain visible even when the gap has no session identity.
            notices = db.execute(f"SELECT e.sequence, e.record FROM events e WHERE {SOURCE}=? AND {GENERATION}=? AND {CLIENT}=? AND e.sequence<=? AND json_extract(e.record, '$.kind') IN ('observation_gap','invalid_record','source_reset','identity_scope_unresolved','identity_conflict','foreign_session_record') ORDER BY sequence DESC LIMIT 21", (parts[0], parts[1], client, snapshot)).fetchall()
            return dict(items=items, snapshot=snapshot, has_more=len(rows)>limit,
                        next_before=rows[min(len(rows),limit)-1][0] if rows else before,
                        archived=parts[1]!=current['generation'], generation=parts[1],
                        source_notices=[present(json.loads(r), seq) for seq,r in notices[:20]],
                        more_source_notices=len(notices)>20)

    def blocks(self, client, key, sequence, *, offset=0, limit=40):
        if not 1 <= sequence < 2**63 or not 0 <= offset <= 4096 or not 1 <= limit <= 100:
            raise ValueError('Invalid block page')
        parts = key_parts(key)
        with self.connect(client) as db:
            scope, args = self.scope(parts)
            found = db.execute('SELECT e.record'+FROM+f' WHERE {scope} AND {CLIENT}=? AND e.sequence=?', args+[client,sequence]).fetchone()
            if not found: raise ValueError('Unknown record in this view')
            row = json.loads(found[0]); blocks = row.get('blocks', [])
            if not isinstance(blocks, list): raise ValueError('Invalid blocks')
            items = []
            for block in blocks[offset:offset+limit]:
                evidence = safe_fields(block)
                items.append(dict(evidence=evidence, **describe(evidence)))
            return dict(items=items, total=len(blocks), next_offset=offset+len(items), has_more=offset+len(items)<len(blocks))

    def explanation_record(self, client, key, sequence):
        """Fetch one immutable record and earlier source warnings in one read snapshot."""
        if type(sequence) is not int or not 1 <= sequence < 2**63:
            raise ValueError('Invalid record')
        parts = key_parts(key)
        with self.connect(client) as db:
            scope, args = self.scope(parts)
            found = db.execute('SELECT e.record'+FROM+f' WHERE {scope} AND {CLIENT}=? AND e.sequence=?', args+[client,sequence]).fetchone()
            if not found:
                raise ValueError('Unknown record in this view')
            row = json.loads(found[0])
            warnings = db.execute(f"SELECT e.sequence,e.record FROM events e WHERE {SOURCE}=? AND {GENERATION}=? AND {CLIENT}=? AND e.sequence<=? AND json_extract(e.record,'$.kind') IN ('observation_gap','invalid_record','identity_scope_unresolved','identity_conflict') ORDER BY sequence DESC LIMIT 1", (parts[0],parts[1],client,sequence)).fetchall()
            return present(row,sequence), [present(json.loads(record),seq) for seq,record in warnings]
