import copy
import unittest
from concurrent.futures import Future
from unittest.mock import patch
from yukio.codex_approvals import pending, METHODS, ApprovalMonitor
from yukio.codex_answer import submission, AnswerError
from yukio.question import QuestionCardLayout
from yukio.events import Kind, PetState
from yukio.router import ActivityRouter


def snapshot(method='item/commandExecution/requestApproval'):
    return dict(id='session', turns=[dict(turnId='turn', status='inProgress', items=[])],
                requests=[dict(id=42, method=method, params=dict(threadId='session', turnId='turn', itemId='tool',
                    reason='Write the report?', command='echo report', cwd='/tmp', permissions={'network': {'enabled': True}}))])


class ApprovalTests(unittest.TestCase):
    def test_approve_and_decline_use_request_channel_for_all_types(self):
        for method in METHODS:
            snap = snapshot(method)
            call, q, _ = pending(snap, 'session')[0]
            for i, decision in enumerate(['accept', 'decline']):
                target, params = submission(snap, 'session', call, q, q.options[i].label)
                self.assertEqual(target, METHODS[method])
                self.assertEqual(params['requestId'], 42)
                self.assertNotIn('input', params)
                if 'permissions' in method:
                    self.assertEqual(params['response']['scope'], 'turn')
                    self.assertEqual(bool(params['response']['permissions']), i == 0)
                else: self.assertEqual(params['decision'], decision)

    def test_stale_changed_duplicate_wrong_thread_turn_id_and_free_text_rejected(self):
        snap = snapshot(); call, q, _ = pending(snap, 'session')[0]
        variants = []
        gone = copy.deepcopy(snap); gone['requests'] = []; variants.append(gone)
        changed = copy.deepcopy(snap); changed['requests'][0]['params']['command'] = 'other'; variants.append(changed)
        duplicate = copy.deepcopy(snap); duplicate['requests'] *= 2; variants.append(duplicate)
        ended = copy.deepcopy(snap); ended['turns'][0]['status'] = 'completed'; variants.append(ended)
        next_turn = copy.deepcopy(snap); next_turn['turns'][0]['turnId'] = 'new'; variants.append(next_turn)
        string_id = copy.deepcopy(snap); string_id['requests'][0]['id'] = '42'; variants.append(string_id)
        for stale in variants:
            with self.assertRaises(AnswerError): submission(stale, 'session', call, q, q.options[0].label)
        with self.assertRaises(AnswerError): submission(snap, 'other', call, q, q.options[0].label)
        with self.assertRaises(AnswerError): submission(snap, 'session', call, q, 'yes')

    def test_supported_decisions_and_canonical_history(self):
        snap = snapshot(); turn = snap['turns'][0]
        snap['turnHistory'] = dict(kind='canonical', history=dict(entitiesByKey={'live': turn}, islands=[dict(entries=[dict(value='live')])]))
        snap['turns'] = []
        snap['requests'][0]['params']['availableDecisions'] = ['decline', 'acceptForSession']
        call, q, _ = pending(snap, 'session')[0]
        self.assertEqual(len(q.options), 1)
        self.assertEqual(submission(snap, 'session', call, q, q.options[0].label)[1]['decision'], 'decline')

    def test_card_has_no_input_and_clicking_close_does_not_decide(self):
        _, q, _ = pending(snapshot(), 'session')[0]
        card = QuestionCardLayout(q)
        self.assertIsNone(card.input_rect)
        self.assertIsNone(card._send_rect)
        self.assertEqual(card.hit(card._close_rect[0]+1, card._close_rect[1]+1).kind, 'close')

    def test_monitor_routes_deduplicates_preserves_on_disconnect_and_clears_on_resolution(self):
        monitor = ApprovalMonitor()
        class Executor:
            def submit(self, *args): return Future()
        executor = Executor()
        router = ActivityRouter(now=0)
        monitor.poll(['session'], 0, executor)
        monitor.future.set_result(snapshot())
        events = monitor.poll(['session'], 100, executor)
        self.assertEqual([e.kind for e in events], [Kind.activity_start])
        for e in events: router.ingest(e, 100)
        router.tick(100)
        router.tick(1000)
        self.assertEqual(router.displayed, PetState.question_for_user)
        monitor.poll(['session'], 1000, executor)
        monitor.future.set_exception(OSError('offline'))
        self.assertEqual(monitor.poll(['session'], 1100, executor), [])
        self.assertTrue(monitor.shown['session'])
        monitor.poll(['session'], 2000, executor)
        done = snapshot(); done['requests'] = []
        monitor.future.set_result(done)
        events = monitor.poll(['session'], 2100, executor)
        self.assertEqual([e.kind for e in events], [Kind.activity_end])
        for e in events: router.ingest(e, 2100)
        router.tick(3000)
        self.assertIsNone(router.asking_question)
