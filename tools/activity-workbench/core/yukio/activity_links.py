"""Explicit client-reported relationships; no names, prompts or inferred graph.

Codex session_meta.id identifies this thread; session_id can identify its root.
Keep forks distinct from spawned agents. A link does not establish task success.
"""


def identifier(value):
    return value if isinstance(value, str) and value.strip() and len(value) <= 256 and all(ord(c) >= 32 and ord(c) != 127 for c in value) else None


def codex_identity(payload):
    issues, links = [], []
    thread = identifier(payload.get('id') if 'id' in payload else payload.get('session_id'))
    out = dict(relationships=links, identity_issues=issues)
    if thread is None:
        issues.append('invalid_thread_identity')
        return out
    if payload.get('thread_id') is not None and identifier(payload['thread_id']) != thread:
        issues.append('conflicting_thread_identity')
        return out
    out['thread_id'] = thread
    root = identifier(payload.get('session_id'))
    if payload.get('session_id') is not None and root is None: issues.append('invalid_root_identity')
    if root: out['reported_root_session_id'] = root

    def link(kind, target, basis):
        if target == thread:
            issues.append('self_' + kind)
        else:
            links.append(dict(kind=kind, from_session_id=thread, to_session_id=target,
                              basis=basis, evidence_class='observed', status='reported_by_client'))
    if root and root != thread: link('belongs_to_root', root, 'session_meta.session_id')
    top = identifier(payload.get('parent_thread_id'))
    parent_invalid = payload.get('parent_thread_id') is not None and top is None
    source = payload.get('source')
    subagent = source.get('subagent') if isinstance(source, dict) else None
    spawn_present = isinstance(subagent, dict) and 'thread_spawn' in subagent
    spawn = subagent.get('thread_spawn') if spawn_present else None
    nested = identifier(spawn.get('parent_thread_id')) if isinstance(spawn, dict) else None
    if spawn_present and nested is None: parent_invalid = True
    if parent_invalid: issues.append('invalid_parent_identity')
    elif top and nested and top != nested: issues.append('conflicting_parent_identity')
    elif nested:
        basis = 'session_meta.source.subagent.thread_spawn.parent_thread_id'
        if top: basis += '+session_meta.parent_thread_id'
        link('spawned_from', nested, basis)
    elif top: link('parent_thread', top, 'session_meta.parent_thread_id')
    fork = identifier(payload.get('forked_from_id'))
    if payload.get('forked_from_id') is not None and fork is None: issues.append('invalid_fork_identity')
    if fork: link('forked_from', fork, 'session_meta.forked_from_id')
    return out


def links_page(rows, after, limit):
    """Bounded evidence page, not a reconciled graph or proof targets were read."""
    links, issues = [], []
    for row in rows:
        # Never combine identical client IDs across different source clients.
        for index, relation in enumerate(row.get('relationships', [])):
            links.append(dict(relation, evidence_id=row['event_id'] + ':link:' + str(index),
                              record_evidence_id=row['event_id'], source=row['source'],
                              source_id=row['source_id'], generation=row['generation'], sequence=row['sequence']))
        if row.get('identity_issues'):
            issues.append(dict(record_evidence_id=row['event_id'], source=row['source'],
                               sequence=row['sequence'], codes=row['identity_issues']))
    return dict(links=links, issues=issues, scanned_records=len(rows),
                next_after=rows[-1]['sequence'] if rows else after, page_full=len(rows) == limit)


def ordinal(value):
    if type(value) in (int, float) and 0 <= value <= 9007199254740991 and int(value) == value:
        return int(value)
    return None


class CodexHistoryScope:
    """An explicit own-history boundary cannot be replaced by inherited headers."""
    def __init__(self, state=None):
        if state is None: state = dict(boundary_unresolved=False)
        if not isinstance(state, dict): raise ValueError('Invalid Codex history scope')
        self.owner_thread = state.get('owner_thread')
        self.start_ordinal = state.get('start_ordinal')
        self.boundary_unresolved = state['boundary_unresolved']
        if (self.owner_thread is not None and identifier(self.owner_thread) is None
                or self.start_ordinal is not None and ordinal(self.start_ordinal) is None
                or type(self.boundary_unresolved) is not bool
                or self.owner_thread is None and (self.start_ordinal is not None or self.boundary_unresolved)):
            raise ValueError('Invalid Codex history scope')

    def checkpoint(self):
        return dict(owner_thread=self.owner_thread, start_ordinal=self.start_ordinal,
                    boundary_unresolved=self.boundary_unresolved)

    def gate(self, obj):
        p = obj.get('payload') if isinstance(obj.get('payload'), dict) else obj
        kind = p.get('type', obj.get('type'))
        if kind == 'session_meta' and (self.owner_thread is None or self.start_ordinal is None and not self.boundary_unresolved):
            self.owner_thread = codex_identity(p).get('thread_id')
            if self.owner_thread is not None and p.get('subagent_history_start_ordinal') is not None:
                self.start_ordinal = ordinal(p['subagent_history_start_ordinal'])
                self.boundary_unresolved = self.start_ordinal is None
            return None
        if self.owner_thread is None: return None
        position = ordinal(obj.get('ordinal'))
        issue, inherited = None, False
        if self.boundary_unresolved: issue = 'unresolved_history_boundary'
        elif self.start_ordinal is not None:
            if position is None: issue = 'missing_or_invalid_history_ordinal'
            elif position < self.start_ordinal: inherited = True
        if not inherited and issue is None and kind == 'session_meta' and codex_identity(p).get('thread_id') != self.owner_thread:
            issue = 'conflicting_thread_identity'
            self.boundary_unresolved = True
        if not inherited and issue is None: return None
        row = dict(kind='inherited_context_record' if inherited else 'identity_scope_unresolved',
                   source_kind=identifier(kind) or '', session_id=self.owner_thread,
                   evidence_class='observed', timestamp_available=False, projection_eligible=False,
                   history_scope='inherited' if inherited else 'unresolved', identity_issues=[issue] if issue else [])
        if position is not None: row['reported_ordinal'] = position
        if self.start_ordinal is not None: row['own_history_start_ordinal'] = self.start_ordinal
        return row
