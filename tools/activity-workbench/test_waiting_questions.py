"""Explicit question tools stay pending until their own receipt or turn boundary."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from launcher import core_path
sys.path.insert(0, str(core_path()))
from yukio.activity_history import ActivityHistory
from glance_view import GlanceView
from history_view import HistoryView


class WaitingQuestionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sources = self.root / 'claude'
        self.sources.mkdir()
        self.db = self.root / 'history.sqlite'
        self.now = time.time()
        self.recorder = self.root / 'claude-workbench-status.json'
        self.recorder.write_text(json.dumps(dict(state='waiting', updated_at=datetime.now(timezone.utc).isoformat())))
        self.rows = {}
        self.glance = GlanceView(HistoryView({'claude': self.db}),
                                 {'claude': self.sources}, clock=lambda: self.now)
        for session in ('A', 'B'):
            self.rows[session] = []
            self.append(session, 'user', 'Please ask me before proceeding.')
            self.ask(session)

    def append(self, session, role, content, stop=None, **extra):
        row = dict(type=role, sessionId=session, uuid=f'{session}-{len(self.rows[session])}',
                   timestamp=datetime.fromtimestamp(self.now - 600 + len(self.rows[session]), timezone.utc).isoformat(),
                   message=dict(role=role, content=content), **extra)
        if stop: row['message']['stop_reason'] = stop
        self.rows[session].append(row)
        path = self.sources / (session + '.jsonl')
        path.write_text(''.join(json.dumps(item) + '\n' for item in self.rows[session]))
        store = ActivityHistory(self.db)
        try: store.ingest(path, source_format='claude')
        finally: store.close()

    def ask(self, session, call='same-call'):
        self.append(session, 'assistant', [dict(type='tool_use', id=call, name='AskUserQuestion',
                    input=dict(questions=[dict(question='Choose for ' + session, header=session,
                        options=[dict(label='ONE', description='First'), dict(label='TWO', description='Second')])]))], stop='tool_use')

    def state(self, session):
        card = next(c for c in self.glance.cards()['cards'] if c['session_id'] == session)
        detail = self.glance.detail('claude', card['key'])
        return card['activity_state'], detail['activity_state']

    def test_two_old_questions_are_waiting_without_rewriting_history(self):
        before = self.db.read_bytes()
        self.assertEqual(self.state('A'), ('waiting', 'waiting'))
        self.assertEqual(self.state('B'), ('waiting', 'waiting'))
        self.assertEqual(self.db.read_bytes(), before)

    def test_answer_to_same_call_id_in_A_does_not_clear_B(self):
        self.append('A', 'user', [dict(type='tool_result', tool_use_id='same-call', is_error=False, content='ONE')])
        self.append('A', 'assistant', [dict(type='text', text='Received ONE.')], stop='end_turn')
        self.assertEqual(self.state('A'), ('inactive', 'inactive'))
        self.assertEqual(self.state('B'), ('waiting', 'waiting'))

    def test_receipt_with_unknown_outcome_still_ends_the_question_wait(self):
        self.append('A', 'user', [dict(type='tool_result', tool_use_id='same-call', content='Answer received')])
        self.assertNotIn('waiting', self.state('A'))

    def test_new_user_turn_and_cancel_do_not_reuse_old_question(self):
        self.append('A', 'user', 'Ignore the old choice; here is a new request.')
        self.append('B', 'user', '[Request interrupted by user]')
        self.assertNotIn('waiting', self.state('A'))
        self.assertEqual(self.state('B'), ('inactive', 'inactive'))

    def test_ambiguous_reused_question_id_is_not_reported_as_waiting(self):
        self.ask('A')
        self.assertNotIn('waiting', self.state('A'))
        self.assertEqual(self.state('B'), ('waiting', 'waiting'))

    def test_context_boundary_clears_prior_wait(self):
        self.append('A', 'system', '', subtype='compact_boundary')
        self.assertNotIn('waiting', self.state('A'))
        self.assertEqual(self.state('B'), ('waiting', 'waiting'))

    def test_stopped_recorder_does_not_claim_a_live_question(self):
        self.recorder.write_text(json.dumps(dict(state='stopped', updated_at=datetime.now(timezone.utc).isoformat())))
        self.assertEqual(self.state('A'), ('unknown', 'unknown'))


if __name__ == '__main__': unittest.main()
