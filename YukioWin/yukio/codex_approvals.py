"""Map live Codex approval requests to the shared question-card mechanism."""
import json
from .events import PetQuestion, QuestionOption, PetEvent, PetState, Kind
from .l10n import tr

PREFIX = 'yukio-approval:'
METHODS = {
    'item/commandExecution/requestApproval': 'thread-follower-command-approval-decision',
    'item/fileChange/requestApproval': 'thread-follower-file-approval-decision',
    'item/permissions/requestApproval': 'thread-follower-permissions-request-approval-response',
}

def pending(snapshot, session):
    from .codex_answer import turns_in, AnswerError
    if snapshot.get('id') != session:
        raise AnswerError('protocol')
    turns = turns_in(snapshot)
    turn = turns[-1] if turns else {}
    turn_id = turn.get('turnId', turn.get('id'))
    if turn.get('status') != 'inProgress' or not isinstance(turn_id, str):
        return []
    result = []
    for request in snapshot.get('requests', []):
        method, params = request.get('method'), request.get('params', {})
        if (method not in METHODS or type(request.get('id')) not in (str, int)
                or request.get('completed') is True or params.get('threadId') != session
                or params.get('turnId') != turn_id):
            continue
        lines = [params.get('reason') or tr('Approve this action?', '是否批准此操作？')]
        if isinstance(params.get('command'), str): lines.append(params['command'])
        if isinstance(params.get('cwd'), str): lines.append(tr('Folder: ', '目录：') + params['cwd'])
        if isinstance(params.get('grantRoot'), str): lines.append(tr('Path: ', '路径：') + params['grantRoot'])
        if method == 'item/fileChange/requestApproval':
            for item in turn.get('items', []):
                if item.get('id') == params.get('itemId'):
                    lines.extend(c['path'] for c in item.get('changes', []) if isinstance(c.get('path'), str))
        if isinstance(params.get('permissions'), dict):
            lines.append(json.dumps(params['permissions'], sort_keys=True, ensure_ascii=False))
        available = params.get('availableDecisions')
        options = []
        if available is None or 'accept' in available:
            options.append(QuestionOption(tr('Approve once', '批准本次')))
        if available is None or 'decline' in available:
            options.append(QuestionOption(tr('Decline', '拒绝')))
        question = PetQuestion(text='\n'.join(lines), header=tr('Needs your approval', '等你批准'), options=options,
                               approval=json.dumps(request, sort_keys=True, ensure_ascii=False))
        call_id = PREFIX + json.dumps([turn_id, request['id']], separators=(',', ':'))
        result.append((call_id, question, request))
    return result


def submission(snapshot, session, call_id, question, answer):
    from .codex_answer import AnswerError
    matches = [r for r in pending(snapshot, session) if r[0] == call_id and r[1] == question]
    if len(matches) != 1 or answer not in [o.label for o in question.options]:
        raise AnswerError('expired')
    request = matches[0][2]
    approve = answer == tr('Approve once', '批准本次')
    result = dict(conversationId=session, requestId=request['id'])
    if request['method'] == 'item/permissions/requestApproval':
        permissions = request['params'].get('permissions')
        if not isinstance(permissions, dict):
            raise AnswerError('protocol')
        result['response'] = dict(permissions=permissions if approve else {}, scope='turn')
    else:
        result['decision'] = 'accept' if approve else 'decline'
    return METHODS[request['method']], result


def fetch_snapshot(session):
    from .codex_answer import Connection, AnswerError
    connection = Connection()
    owner = None
    try:
        owner = connection.request('thread-owner-discovery', dict(hostId='local', conversationId=session)).get('handledByClientId')
        if not owner:
            raise AnswerError('unavailable')
        connection.follow(session, owner, True)
        return connection.snapshot(session, owner)
    finally:
        try:
            if owner: connection.follow(session, owner, False)
        finally:
            connection.close()


class ApprovalMonitor:
    def __init__(self):
        self.shown = {}
        self.cursor = 0
        self.future = None
        self.next_poll = 0

    def poll(self, sessions, now, executor):
        events = []
        self.shown = {s: ids for s, ids in self.shown.items() if s in sessions}
        if self.future and self.future.done():
            try:
                rows = pending(self.future.result(), self.session) if self.session in sessions else []
                old = self.shown.get(self.session, set())
                current = {r[0] for r in rows}
                events += [PetEvent(self.started_at, 'codex', self.session, Kind.activity_end, event_id=i) for i in sorted(old-current)]
                # Repeated starts refresh liveness; the router deduplicates open IDs.
                events += [PetEvent(self.started_at, 'codex', self.session, Kind.activity_start, event_id=i,
                                    activity=PetState.question_for_user, detail=q.short_label, question=q) for i, q, _ in rows]
                self.shown[self.session] = current
            except Exception:
                pass  # A failed read is not evidence that the request was resolved.
            self.future = None
        if not self.future and sessions and now >= self.next_poll:
            self.session = sessions[self.cursor % len(sessions)]
            self.cursor += 1
            self.next_poll = now + 750
            self.started_at = now
            self.future = executor.submit(fetch_snapshot, self.session)
        return events
