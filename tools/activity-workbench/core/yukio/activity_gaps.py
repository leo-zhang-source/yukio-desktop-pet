"""Persist framing gaps without retaining oversized source bodies."""
from .activity_links import identifier


class HistoryCoverage:
    def __init__(self, state=None, offset=0):
        state = state if state is not None else dict(version=1, gap_count=0, codex_needs_identity=False)
        self.version = state['version']
        self.gap_count = state['gap_count']
        self.open_record_offset = state.get('open_record_offset')
        self.last_gap_evidence_id = state.get('last_gap_evidence_id')
        self.codex_needs_identity = state['codex_needs_identity']
        self.quarantined_calls = state.get('quarantined_calls', [])
        self.quarantine_full = state.get('quarantine_full', False)
        if (type(self.version) is not int or self.version != 1
                or type(self.gap_count) is not int or not 0 <= self.gap_count <= 2**63-1
                or type(self.codex_needs_identity) is not bool
                or self.open_record_offset is not None and (type(self.open_record_offset) is not int or not 0 <= self.open_record_offset < offset)
                or self.last_gap_evidence_id is not None and identifier(self.last_gap_evidence_id) is None
                or (self.open_record_offset is not None or self.codex_needs_identity) and self.last_gap_evidence_id is None
                or type(self.quarantine_full) is not bool or not isinstance(self.quarantined_calls, list)
                or len(self.quarantined_calls) > 4096 or any(identifier(x) is None for x in self.quarantined_calls)
                or len(set(self.quarantined_calls)) != len(self.quarantined_calls)):
            raise ValueError('Invalid activity coverage checkpoint')

    def checkpoint(self): return vars(self).copy()

    def reset_source(self):
        self.open_record_offset = self.last_gap_evidence_id = None
        self.codex_needs_identity = False
        self.quarantined_calls = []; self.quarantine_full = False

    def quarantine(self, checkpoint, codex):
        state = checkpoint.get('results', {}) if codex else checkpoint
        ids = list(self.quarantined_calls) + (state.get('retired', []) if codex else [])
        for call in state.get('calls', []):
            ids.append(call.get('id') if codex else call['key'][-1])
        if any(identifier(x) is None for x in ids) or state.get('tracking_limited') is True:
            self.quarantine_full = True
        ids = sorted({x for x in ids if identifier(x) is not None})
        if len(ids) > 4096: self.quarantine_full = True
        self.quarantined_calls = ids[:4096]

    def guard_results(self, row):
        results = [row['result']] if isinstance(row.get('result'), dict) else []
        results += [b for b in row.get('blocks', []) if b.get('kind') == 'tool_result']
        for result in results:
            if self.quarantine_full or any(result.get(k) in self.quarantined_calls for k in ('call_id', 'item_id')):
                result.update(call_outcome='unknown', projection_eligible=False, association='ambiguous_across_gap')
                result.pop('request_evidence_id', None)
                result['gap_evidence_id'] = self.last_gap_evidence_id

    def gap(self, offset, end, complete, evidence_id, codex):
        first = self.open_record_offset is None
        if first:
            if self.gap_count == 2**63-1: raise ValueError('Activity gap counter is full')
            self.gap_count += 1
            self.open_record_offset = offset
            self.last_gap_evidence_id = evidence_id
            self.codex_needs_identity = codex
        row = dict(kind='observation_gap', reason='record_too_large', evidence_class='observed',
                   timestamp_available=False, projection_eligible=False, record_complete=complete,
                   gap_evidence_id=self.last_gap_evidence_id, gap_start_offset=self.open_record_offset,
                   gap_part='start' if first else 'continuation', skipped_bytes=end-offset)
        if complete:
            row['total_record_bytes'] = end - self.open_record_offset
            self.open_record_offset = None
        return row, first

    def gate_codex(self, payload, kind, scope):
        if not self.codex_needs_identity: return None
        # A lost header can contain an inherited-history boundary. Do not infer
        # the owner from subsequent copied context if no earlier owner was read.
        identity = identifier(payload.get('id') if 'id' in payload else payload.get('session_id')) if kind == 'session_meta' else identifier(payload.get('thread_id'))
        if scope is not None and scope.owner_thread is not None and identity == scope.owner_thread:
            self.codex_needs_identity = False
            return None
        return dict(kind='unattributed_record', source_kind=identifier(kind) or '',
                    reason='identity_missing_after_gap', evidence_class='observed',
                    timestamp_available=False, projection_eligible=False)
