"""A Claude Desktop turn that closes on the client's blocking question waits for the user.

Synthetic records only. The question wording is never interpreted or saved.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from launcher import core_path
sys.path.insert(0, str(core_path()))
from yukio.activity_history import ActivityHistory
from yukio.claude_history import ClaudeHistoryParser, blocked_on_user
from history_view import HistoryView
from glance_view import GlanceView
from localization import english_text
from claude_desktop import ENDED_ON_QUESTION
from test_claude_completion import record, answer, summary

SECRET = 'Install the private build now?'


def box(second, identity, **fields):
    return record('assistant', second, uuid='request-' + identity, message=dict(role='assistant', id='response-' + identity,
        content=[dict(type='tool_use', name='mcp__ccd_turn__wrap_up', id=identity, input=dict(recap='Done.', **fields))]))


def receipt(second, identity):
    return record('user', second, message=dict(content=[dict(type='tool_result', tool_use_id=identity, content='Shown.')]))


def turn(start, prompt, boxes, reply='answer-a'):
    rows = [record('user', start, promptId=prompt, message=dict(content='Please continue.'))]
    for n, fields in enumerate(boxes):
        rows += [box(start + 1 + 2 * n, '%s-box-%d' % (prompt, n), **fields), receipt(start + 2 + 2 * n, '%s-box-%d' % (prompt, n))]
    end = start + 1 + 2 * len(boxes)
    return rows + [answer(end, identity=reply), summary(end + 1, parent=reply)]


def markers(rows):
    parser = ClaudeHistoryParser('chat-a')
    seen = [parser.observe(json.dumps(row).encode(), 'e%d' % n) for n, row in enumerate(rows)]
    return [row for row in seen if row.get('turn_marker') == 'turn_ended'], parser


class BlockedHandoffRecordTests(unittest.TestCase):
    def test_only_the_client_flag_with_a_question_counts(self):
        self.assertTrue(blocked_on_user(dict(input=dict(ask=SECRET, blocked=True))))
        for data in (dict(ask=SECRET), dict(ask=SECRET, blocked=False), dict(ask=SECRET, blocked='true'), dict(ask=SECRET, blocked=1),
                     dict(blocked=True), dict(ask='  ', blocked=True), dict(ask=7, blocked=True), None, 'blocked'):
            self.assertFalse(blocked_on_user(dict(input=data)), data)

    def test_blocking_question_marks_the_turn_end_without_saving_its_text(self):
        ended, parser = markers(turn(0, 'p1', [dict(ask=SECRET, blocked=True, actions=[dict(label='Yes')])]))
        self.assertEqual([row.get('reported_blocked_on_user') for row in ended], [True])
        self.assertNotIn(SECRET, json.dumps(ended) + json.dumps(parser.history_checkpoint()))
        self.assertFalse(parser.blocked_handoff)

    def test_suggestions_and_plain_recaps_end_normally(self):
        for fields in (dict(ask=SECRET, actions=[dict(label='Merge')]), dict(ask=SECRET, blocked=False), dict(), dict(blocked=True)):
            ended, _ = markers(turn(0, 'p1', [fields]))
            self.assertEqual(len(ended), 1)
            self.assertNotIn('reported_blocked_on_user', ended[0], fields)
        ended, _ = markers(turn(0, 'p1', []))
        self.assertNotIn('reported_blocked_on_user', ended[0])

    def test_the_last_box_of_the_turn_decides_and_the_next_turn_starts_clean(self):
        ended, _ = markers(turn(0, 'p1', [dict(ask=SECRET, blocked=True), dict(ask='Merge it?')]))
        self.assertNotIn('reported_blocked_on_user', ended[0])
        ended, _ = markers(turn(0, 'p1', [dict(ask='Merge it?'), dict(ask=SECRET, blocked=True)]))
        self.assertTrue(ended[0]['reported_blocked_on_user'])
        rows = turn(0, 'p1', [dict(ask=SECRET, blocked=True)], reply='a1') + turn(20, 'p2', [], reply='a2')
        ended, _ = markers(rows)
        self.assertEqual([row.get('reported_blocked_on_user') for row in ended], [True, None])
        # A box whose turn never reaches a confirmed end is dropped by the next request.
        rows = turn(0, 'p1', [dict(ask=SECRET, blocked=True)], reply='a1')[:-2] + turn(20, 'p2', [], reply='a2')
        ended, _ = markers(rows)
        self.assertEqual([row.get('reported_blocked_on_user') for row in ended], [None])

    def test_helper_agents_cannot_mark_the_main_chat(self):
        rows = turn(0, 'p1', [])
        helper = box(1, 'helper-box', ask=SECRET, blocked=True)
        for extra in (dict(isSidechain=True, agentId='helper'), dict(agentId='helper')):
            ended, _ = markers(rows[:1] + [dict(helper, **extra)] + rows[1:])
            self.assertNotIn('reported_blocked_on_user', ended[0], extra)

    def test_marker_survives_a_checkpoint_and_old_checkpoints_still_load(self):
        rows = turn(0, 'p1', [dict(ask=SECRET, blocked=True)])
        parser = ClaudeHistoryParser('chat-a')
        for n, row in enumerate(rows[:-2]): parser.observe(json.dumps(row).encode(), 'e%d' % n)
        saved = json.loads(json.dumps(parser.history_checkpoint()))
        self.assertIs(saved['blocked_handoff'], True)
        resumed = ClaudeHistoryParser.from_history_checkpoint(saved)
        seen = [resumed.observe(json.dumps(row).encode(), 'late%d' % n) for n, row in enumerate(rows[-2:])]
        self.assertTrue(seen[-1]['reported_blocked_on_user'])
        old = dict(saved); old.pop('blocked_handoff')
        self.assertFalse(ClaudeHistoryParser.from_history_checkpoint(old).blocked_handoff)
        with self.assertRaises(ValueError): ClaudeHistoryParser.from_history_checkpoint(dict(saved, blocked_handoff='yes'))

    def test_unreadable_records_drop_the_pending_marker(self):
        rows = turn(0, 'p1', [dict(ask=SECRET, blocked=True)])
        parser = ClaudeHistoryParser('chat-a')
        for n, row in enumerate(rows[:-2]): parser.observe(json.dumps(row).encode(), 'e%d' % n)
        parser.observe(b'{not json', 'bad')
        self.assertFalse(parser.blocked_handoff)


class BlockedHandoffViewTests(unittest.TestCase):
    def views(self, temp, rows):
        root = Path(temp); source = root / 'chat.jsonl'; db = root / 'history.sqlite'
        source.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        store = ActivityHistory(db)
        try: store.ingest(source, source_format='claude')
        finally: store.close()
        (root / 'claude-workbench-status.json').write_text(json.dumps(dict(state='waiting', updated_at=datetime.now(timezone.utc).isoformat())))
        history = HistoryView({'claude': db}); view = GlanceView(history, {'claude': root})
        key = history.groups('claude')['groups'][0]['key']
        return view.detail('claude', key), view.cards()['cards'][0], db

    def test_both_views_wait_for_the_answer_and_the_question_stays_out_of_the_database(self):
        with tempfile.TemporaryDirectory() as temp:
            detail, card, db = self.views(temp, turn(0, 'p1', [dict(ask=SECRET, blocked=True)]))
            for shown in (detail, card):
                self.assertEqual(shown['status'], '等待你回答')
                self.assertEqual(shown['tone'], 'attention')
                self.assertEqual(shown['activity_state'], 'waiting')
                self.assertEqual(shown['turn_marker'], 'turn_ended')
            self.assertEqual(detail['needs_you'], ENDED_ON_QUESTION['needs_you'])
            self.assertNotIn(SECRET.encode(), db.read_bytes())

    def test_suggestion_boxes_stay_finished(self):
        with tempfile.TemporaryDirectory() as temp:
            detail, card, _ = self.views(temp, turn(0, 'p1', [dict(ask=SECRET, actions=[dict(label='Merge')])]))
            for shown in (detail, card):
                self.assertEqual(shown['status'], '这一轮已结束')
                self.assertEqual(shown['activity_state'], 'inactive')
                self.assertFalse(shown['ended_on_question'])

    def test_answering_starts_a_new_turn_and_clears_the_wait(self):
        with tempfile.TemporaryDirectory() as temp:
            rows = turn(0, 'p1', [dict(ask=SECRET, blocked=True)], reply='a1')
            rows.append(record('user', 20, promptId='p2', message=dict(content='Yes, go ahead.')))
            detail, card, _ = self.views(temp, rows)
            for shown in (detail, card):
                self.assertNotEqual(shown['status'], '等待你回答')
                self.assertNotEqual(shown['activity_state'], 'waiting')
            rows += [answer(21, identity='a2'), summary(22, parent='a2')]
        with tempfile.TemporaryDirectory() as temp:
            detail, card, _ = self.views(temp, rows)
            for shown in (detail, card): self.assertEqual(shown['status'], '这一轮已结束')

    def test_wait_text_is_available_in_english(self):
        for text in (ENDED_ON_QUESTION['status'], ENDED_ON_QUESTION['needs_you']):
            self.assertNotEqual(english_text(text), text)
            self.assertFalse(any('一' <= c <= '鿿' for c in english_text(text)))


if __name__ == '__main__':
    unittest.main()
