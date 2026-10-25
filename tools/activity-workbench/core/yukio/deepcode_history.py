"""Deep Code JSONL metadata, independently of pet completion heuristics.

The mutable sessions index and prose are not evidence of successful execution.
Only explicit receipt flags and same-file/session call identities are used.
"""
from collections import OrderedDict
import hashlib
import json

from .events import parse_timestamp

CAPACITY = 4096


def identifier(value):
    return value if isinstance(value, str) and value.strip() and len(value) <= 256 else None


def tool_identity(name):
    # Explicit aliases in the verified upstream executor, not general case folding.
    return {"Bash": "bash", "Read": "read", "Write": "write", "Edit": "edit"}.get(name, name)


def object_value(value):
    return value if isinstance(value, dict) else {}


class DeepCodeHistoryParser:
    def __init__(self, fallback_session):
        self.fallback_session = fallback_session
        self.calls = OrderedDict()
        self.tracking_limited = False

    def history_checkpoint(self):
        return dict(deepcode_history_version=1, fallback_session=self.fallback_session,
                    tracking_limited=self.tracking_limited, calls=list(self.calls.values()))

    @classmethod
    def from_history_checkpoint(cls, state):
        if type(state.get('deepcode_history_version')) is not int or state['deepcode_history_version'] != 1 or not identifier(state.get('fallback_session')):
            raise ValueError('Unsupported Deep Code history checkpoint')
        if type(state.get('tracking_limited')) is not bool or not isinstance(state.get('calls'), list) or len(state['calls']) > CAPACITY:
            raise ValueError('Invalid Deep Code history checkpoint')
        parser = cls(state['fallback_session']); parser.tracking_limited = state['tracking_limited']
        for call in state['calls']:
            key = call['key']
            if not isinstance(key, list) or len(key) != 2 or any(not identifier(v) for v in key) or tuple(key) in parser.calls:
                raise ValueError('Invalid Deep Code history scope')
            if not identifier(call.get('request_evidence_id')) or type(call.get('ambiguous')) is not bool:
                raise ValueError('Invalid Deep Code history call')
            for field in ('request_uuid', 'tool_name', 'request_fingerprint'):
                if call.get(field) is not None and not identifier(call[field]):
                    raise ValueError('Invalid Deep Code history identity')
            outcomes = call['outcomes']
            if not isinstance(outcomes, list) or any(v not in ('succeeded', 'failed', 'cancelled') for v in outcomes) or len(outcomes) != len(set(outcomes)):
                raise ValueError('Invalid Deep Code history outcomes')
            entry = {k: call[k] for k in ('key', 'request_evidence_id', 'ambiguous', 'outcomes')}
            for field in ('request_uuid', 'tool_name', 'request_fingerprint'):
                if call.get(field) is not None: entry[field] = call[field]
            parser.calls[tuple(key)] = entry
        return parser

    def observe(self, raw, evidence_id):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict): raise ValueError()
        except (ValueError, UnicodeError, RecursionError):
            self.calls.clear()
            return dict(kind='invalid_record', evidence_class='observed', timestamp_available=False, session_id=self.fallback_session)
        role = identifier(obj.get('role')) or ''
        session = identifier(obj.get('sessionId'))
        row = dict(kind='message_observed' if role in ('user', 'assistant', 'tool', 'system') else 'unrecognized_record',
                   source_kind=role, session_id=session or self.fallback_session, evidence_class='observed', timestamp_available=False)
        uuid = identifier(obj.get('id'))
        if uuid: row['reported_message_id'] = uuid
        for field in ('visible', 'compacted'):
            if type(obj.get(field)) is bool: row['reported_' + field] = obj[field]
        for field, target in (('createTime', 'timestamp_ms'), ('updateTime', 'reported_update_timestamp_ms')):
            ts = parse_timestamp(obj.get(field)) if isinstance(obj.get(field), str) else None
            if ts is not None:
                row[target] = ts
                if field == 'createTime': row['timestamp_available'] = True
        meta = object_value(obj.get('meta')); params = object_value(obj.get('messageParams'))
        if obj.get('compacted') is True or meta.get('isSummary') is True:
            self.calls.clear(); row['kind'] = 'context_record_observed'; return row
        # No verified agent identity field exists in the supported message format.
        scope_known = bool(session) and not any(k in obj for k in ('agentId', 'agent_id'))
        if (role != 'assistant' and 'tool_calls' in params) or (role != 'tool' and 'tool_call_id' in params):
            self.calls.clear(); row['kind'] = 'identity_conflict'; return row
        blocks = []
        def block(index, kind, source_kind):
            return dict(block_index=index, evidence_id=evidence_id + ':block:' + str(index), evidence_class='observed', kind=kind, source_kind=source_kind)
        if role == 'assistant':
            calls = params.get('tool_calls')
            if calls is not None and not isinstance(calls, list):
                self.calls.clear(); row['kind'] = 'invalid_tool_calls'; return row
            if len(calls or []) > CAPACITY:
                self.calls.clear(); self.tracking_limited = True; row['kind'] = 'record_limit_exceeded'; return row
            digest = hashlib.sha256(raw).digest()
            for index, call in enumerate(calls or []):
                b = block(index, 'tool_requested', 'function')
                if not isinstance(call, dict) or call.get('type') != 'function' or not isinstance(call.get('function'), dict):
                    b.update(kind='unrecognized_block', source_kind='unknown'); blocks.append(b)
                    self.calls.clear(); self.tracking_limited = True; continue
                cid = identifier(call.get('id')); name = identifier(call['function'].get('name'))
                if cid: b['call_id'] = cid
                if name: b['tool_name'] = name
                b['association'] = 'missing_identity'
                if self.tracking_limited: b['association'] = 'tracking_limit_exceeded'
                elif scope_known and cid and name:
                    key = (session, cid); old = self.calls.get(key)
                    fingerprint = hashlib.sha256(digest + (':' + str(index)).encode()).hexdigest()
                    if old is not None:
                        duplicate = uuid is not None and uuid == old.get('request_uuid') and name == old.get('tool_name') and fingerprint == old.get('request_fingerprint')
                        if not duplicate: old['ambiguous'] = True
                        b['association'] = 'ambiguous_reused_call' if old['ambiguous'] else 'duplicate_request'
                    elif len(self.calls) >= CAPACITY:
                        self.calls.clear(); self.tracking_limited = True; b['association'] = 'tracking_limit_exceeded'
                    else:
                        entry = dict(key=list(key), request_evidence_id=b['evidence_id'], tool_name=name,
                                     request_fingerprint=fingerprint, ambiguous=False, outcomes=[])
                        if uuid: entry['request_uuid'] = uuid
                        self.calls[key] = entry; b['association'] = 'request_observed'
                elif scope_known and cid:
                    # A malformed request reusing an earlier ID cannot borrow its identity.
                    if (session, cid) in self.calls: self.calls[(session, cid)]['ambiguous'] = True
                blocks.append(b)
            for field, kind in (('content', 'text_record_observed'), ('reasoning_content', 'reasoning_record_observed')):
                text = obj.get(field) if field == 'content' else params.get(field)
                if isinstance(text, str) and text.strip():
                    b = block(len(blocks), kind, field)
                    if field == 'content': b['evidence_class'] = 'self_report'
                    blocks.append(b)
        elif role == 'tool':
            b = block(0, 'tool_result', 'tool'); cid = identifier(params.get('tool_call_id'))
            if cid: b['call_id'] = cid
            try:
                result = object_value(json.loads(obj['content'])) if isinstance(obj.get('content'), str) else {}
            except (ValueError, UnicodeError, RecursionError): result = {}
            metadata = object_value(result.get('metadata'))
            ok, interrupted, waiting = result.get('ok'), metadata.get('interrupted'), result.get('awaitUserResponse')
            for field, value in (('reported_ok', ok), ('reported_interrupted', interrupted), ('reported_await_user_response', waiting)):
                if type(value) is bool: b[field] = value
            background = 'backgroundTaskId' in metadata or metadata.get('runInBackground') is True
            if background: b['background_task_reported'] = True
            conflict = interrupted is True and ok is True
            flags_invalid = any(k in container and type(container[k]) is not bool for container, k in ((metadata, 'interrupted'), (result, 'awaitUserResponse'))) or ('metadata' in result and not isinstance(result['metadata'], dict))
            outcome = 'unknown'
            if interrupted is True and not conflict and not flags_invalid: outcome = 'cancelled'
            elif not conflict and not flags_invalid and waiting is not True and not background and type(ok) is bool: outcome = 'succeeded' if ok else 'failed'
            b.update(outcome=outcome, call_outcome='unknown', projection_eligible=False, conflicting_results=False, result_flags_conflict=conflict,
                     outcome_basis='explicit_tool_receipt', association='missing_identity' if not scope_known or not cid else 'unobserved_request')
            if self.tracking_limited: b['association'] = 'tracking_limit_exceeded'
            entry = self.calls.get((session, cid)) if scope_known and cid and not self.tracking_limited else None
            names = [identifier(result.get('name')), identifier(object_value(meta.get('function')).get('name'))]
            if entry is not None:
                name_conflict = any(n is not None and tool_identity(n) != tool_identity(entry.get('tool_name')) for n in names)
                if name_conflict: entry['ambiguous'] = True
                b['association'] = 'identity_conflict' if name_conflict else ('ambiguous_reused_call' if entry['ambiguous'] else 'matching_tool_call_id')
                if not entry['ambiguous']:
                    if conflict: entry['outcomes'] = sorted(set(entry['outcomes']) | {'cancelled', 'succeeded'})
                    if outcome != 'unknown': entry['outcomes'] = sorted(set(entry['outcomes']) | {outcome})
                    b.update(request_evidence_id=entry['request_evidence_id'], projection_eligible=True,
                             conflicting_results=len(entry['outcomes']) > 1,
                             call_outcome=entry['outcomes'][0] if len(entry['outcomes']) == 1 and not conflict else 'unknown', tool_name=entry['tool_name'])
            blocks.append(b)
        row.update(blocks=blocks, correlation_limited=self.tracking_limited)
        return row
