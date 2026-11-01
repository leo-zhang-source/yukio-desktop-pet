"""Metadata-only Claude transcript evidence, separate from pet display decisions.

No body, input, output, command or thinking text enters rows or checkpoints.
Correlation stays within one file and explicit session/agent identity.
"""
from collections import OrderedDict
import json
import hashlib

from .events import parse_timestamp

CAPACITY = 4096


def identifier(value):
    return value if isinstance(value, str) and value.strip() and len(value) <= 256 else None


class ClaudeHistoryParser:
    def __init__(self, fallback_session):
        self.fallback_session = fallback_session
        self.calls = OrderedDict()
        self.tracking_limited = False

    def history_checkpoint(self):
        return dict(claude_history_version=1, fallback_session=self.fallback_session,
                    tracking_limited=self.tracking_limited, calls=list(self.calls.values()))

    @classmethod
    def from_history_checkpoint(cls, state):
        if state.get('claude_history_version') != 1 or not identifier(state.get('fallback_session')):
            raise ValueError('Unsupported Claude history checkpoint')
        parser = cls(state['fallback_session'])
        if type(state.get('tracking_limited')) is not bool:
            raise ValueError('Invalid Claude history limit state')
        parser.tracking_limited = state['tracking_limited']
        calls = state['calls']
        if not isinstance(calls, list) or len(calls) > CAPACITY:
            raise ValueError('Invalid Claude history checkpoint')
        for call in calls:
            key = call['key']
            if not isinstance(key, list) or len(key) != 4 or any(not isinstance(v, str) or len(v) > 256 for v in key):
                raise ValueError('Invalid Claude history scope')
            if tuple(key) in parser.calls or not identifier(call.get('request_evidence_id')) or type(call.get('ambiguous')) is not bool:
                raise ValueError('Invalid Claude history call')
            for field in ('request_uuid', 'tool_name', 'request_fingerprint'):
                if call.get(field) is not None and not identifier(call[field]):
                    raise ValueError('Invalid Claude history identity')
            outcomes = call['outcomes']
            if not isinstance(outcomes, list) or len(outcomes) != len(set(outcomes)) or any(v not in ('succeeded', 'failed') for v in outcomes):
                raise ValueError('Invalid Claude history outcomes')
            parser.calls[tuple(key)] = {k: call[k] for k in ('key', 'request_evidence_id', 'ambiguous', 'outcomes')}
            for field in ('request_uuid', 'tool_name', 'request_fingerprint'):
                if call.get(field) is not None:
                    parser.calls[tuple(key)][field] = call[field]
        return parser

    def observe(self, raw, evidence_id):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError):
            self.calls.clear()
            return dict(kind='invalid_record', evidence_class='observed', timestamp_available=False,
                        session_id=self.fallback_session)
        kind = identifier(obj.get('type')) or ''
        session = identifier(obj.get('sessionId'))
        agent = identifier(obj.get('agentId'))
        sidechain = obj.get('isSidechain')
        row = dict(kind='message_observed' if kind in ('assistant', 'user') else 'unrecognized_record',
                   source_kind=kind, session_id=session or self.fallback_session,
                   evidence_class='observed', timestamp_available=False)
        for field, name in (('uuid', 'reported_uuid'), ('parentUuid', 'reported_parent_uuid'), ('agentId', 'agent_id')):
            value = identifier(obj.get(field))
            if value is not None:
                row[name] = value
        if type(sidechain) is bool:
            row['is_sidechain'] = sidechain
        timestamp = parse_timestamp(obj.get('timestamp')) if isinstance(obj.get('timestamp'), str) else None
        if timestamp is not None:
            row.update(timestamp_ms=timestamp, timestamp_available=True)
        if kind == 'system' and obj.get('subtype') == 'compact_boundary':
            self.calls.clear()
            row['kind'] = 'context_boundary'
            self.tracking_limited = False
        if kind == 'system' and obj.get('subtype') == 'stop_hook_summary':
            row['turn_marker'] = 'turn_ended'
        if kind not in ('assistant', 'user'):
            return row
        message = obj.get('message') if isinstance(obj.get('message'), dict) else {}
        stop = identifier(message.get('stop_reason'))
        if stop:
            row['reported_stop_reason'] = stop  # end_turn is not task completion.
        if message.get('role') is not None and message.get('role') != kind:
            self.calls.clear()
            row['kind'] = 'identity_conflict'
            return row
        if obj.get('isMeta') is True or obj.get('isCompactSummary') is True:
            row['kind'] = 'context_record_observed'
            return row
        content = message.get('content')
        if isinstance(content, list) and len(content) > CAPACITY:
            self.calls.clear()
            row['kind'] = 'record_limit_exceeded'
            return row
        # Preserve message/block kinds used by result correlation. Lifecycle is
        # separate metadata: reply ended never means the whole task succeeded.
        if kind == 'assistant' and message.get('model') == '<synthetic>':
            row['turn_marker'] = 'turn_cancelled'
        elif kind == 'assistant' and stop in ('end_turn', 'stop_sequence'):
            if not isinstance(content, list) or not any(isinstance(b, dict) and b.get('type') == 'tool_use' for b in content):
                row['turn_marker'] = 'turn_ended'
        elif kind == 'user':
            blocks = content if isinstance(content, list) else []
            has_results = any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in blocks)
            text = content if isinstance(content, str) else '\n'.join(b.get('text', '') for b in blocks if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('text'), str))
            stripped = text.strip()
            if not has_results:
                if stripped.startswith('[Request interrupted by user'):
                    row['turn_marker'] = 'turn_cancelled'
                elif not stripped.startswith(('<local-command-', '<command-name>', '<command-message>')) and (stripped or blocks):
                    row['turn_marker'] = 'turn_started'
        if not isinstance(content, list):
            return row
        blocks = []
        record_digest = hashlib.sha256(raw).digest()
        # Unknown sidechain identity must never borrow the main agent's calls.
        scope_known = bool(session) and (sidechain is None or type(sidechain) is bool) and (sidechain is not True or agent is not None) and ('agentId' not in obj or agent is not None)
        for index, block in enumerate(content):
            b = dict(block_index=index, evidence_id=evidence_id + ':block:' + str(index),
                     evidence_class='observed', kind='unrecognized_block')
            if not isinstance(block, dict):
                b['kind'] = 'invalid_block'; blocks.append(b); continue
            typ = identifier(block.get('type')) or ''
            b['source_kind'] = typ
            if typ == 'text':
                b['kind'] = 'text_record_observed'
                if kind == 'assistant':
                    b['evidence_class'] = 'self_report'
            elif typ in ('thinking', 'redacted_thinking'):
                b['kind'] = 'reasoning_record_observed'
            elif typ == 'tool_use' and kind == 'assistant':
                b['kind'] = 'tool_requested'
                call = identifier(block.get('id')); name = identifier(block.get('name'))
                if call: b['call_id'] = call
                if name: b['tool_name'] = name
                if self.tracking_limited:
                    b['association'] = 'tracking_limit_exceeded'
                elif scope_known and call:
                    key = (session, agent or '', 'true' if sidechain is True else 'false', call)
                    old = self.calls.get(key); uuid = identifier(obj.get('uuid'))
                    fingerprint = hashlib.sha256(record_digest + (':' + str(index)).encode()).hexdigest()
                    if old is not None:
                        duplicate = uuid is not None and uuid == old.get('request_uuid') and name == old.get('tool_name') and fingerprint == old.get('request_fingerprint')
                        if not duplicate: old['ambiguous'] = True
                        b['association'] = 'ambiguous_reused_call' if old['ambiguous'] else 'duplicate_request'
                    else:
                        entry = dict(key=list(key), request_evidence_id=b['evidence_id'], ambiguous=False, outcomes=[])
                        if uuid: entry['request_uuid'] = uuid
                        if name: entry['tool_name'] = name
                        entry['request_fingerprint'] = fingerprint
                        if len(self.calls) >= CAPACITY:
                            self.calls.clear(); self.tracking_limited = True
                            b['association'] = 'tracking_limit_exceeded'
                        else:
                            self.calls[key] = entry
                            b['association'] = 'request_observed'
                else:
                    b['association'] = 'missing_identity'
            elif typ == 'tool_result' and kind == 'user':
                b['kind'] = 'tool_result'
                call = identifier(block.get('tool_use_id'))
                if call: b['call_id'] = call
                error = block.get('is_error')
                outcome = ('failed' if error else 'succeeded') if type(error) is bool else 'unknown'
                b.update(outcome=outcome, call_outcome='unknown', projection_eligible=False, conflicting_results=False)
                if type(error) is bool: b['reported_is_error'] = error
                key = (session, agent or '', 'true' if sidechain is True else 'false', call)
                entry = self.calls.get(key) if scope_known and call and not self.tracking_limited else None
                b['association'] = 'missing_identity' if not scope_known or not call else 'unobserved_request'
                if self.tracking_limited: b['association'] = 'tracking_limit_exceeded'
                if entry is not None:
                    b['association'] = 'ambiguous_reused_call' if entry['ambiguous'] else 'matching_tool_use_id'
                    if not entry['ambiguous']:
                        if outcome != 'unknown': entry['outcomes'] = sorted(set(entry['outcomes']) | {outcome})
                        b.update(request_evidence_id=entry['request_evidence_id'], projection_eligible=True,
                                 conflicting_results=len(entry['outcomes']) > 1,
                                 call_outcome=entry['outcomes'][0] if len(entry['outcomes']) == 1 else 'unknown')
                        if entry.get('tool_name'): b['tool_name'] = entry['tool_name']
            blocks.append(b)
        row['correlation_limited'] = self.tracking_limited
        row['blocks'] = blocks
        return row
