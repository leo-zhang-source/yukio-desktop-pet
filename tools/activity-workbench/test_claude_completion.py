"""Synthetic Claude lifecycle records; no private transcript contents."""
from datetime import datetime, timezone
import sys
import unittest

from launcher import core_path
sys.path.insert(0, str(core_path()))
from yukio.events import Kind
from yukio.parsers_claude import ClaudeTranscriptParser


def record(kind, second, session='chat-a', **fields):
    return dict(type=kind, sessionId=session,
                timestamp=datetime.fromtimestamp(second, timezone.utc).isoformat(), **fields)


def answer(second=1, stop='end_turn', identity='answer-a', session='chat-a', blocks=None):
    return record('assistant', second, session, uuid=identity,
                  message=dict(role='assistant', stop_reason=stop,
                               content=blocks or [dict(type='text', text='Public reply')]))


def summary(second=2, parent='answer-a', session='chat-a', **changes):
    value = record('system', second, session, subtype='stop_hook_summary', parentUuid=parent,
                   preventedContinuation=False, hasOutput=False, hookErrors=[],
                   hookAdditionalContext=[], stopReason='')
    value.update(changes)
    return value


class ClaudeCompletionTests(unittest.TestCase):
    def kinds(self, parser, row):
        return [event.kind for event in parser.events(row)]

    def test_interactive_cli_duration_confirms_only_matching_answer(self):
        parser = ClaudeTranscriptParser()
        row = answer(); row['entrypoint'] = 'cli'
        parser.events(row)
        self.assertEqual(self.kinds(parser, record('system', 2, subtype='turn_duration',
                         parentUuid='foreign', entrypoint='cli', durationMs=1200)), [])
        self.assertEqual(self.kinds(parser, record('system', 3, subtype='turn_duration',
                         parentUuid='answer-a', entrypoint='cli', durationMs=1200)),
                         [Kind.final_answer, Kind.task_end])

    def test_sdk_cli_persisted_leaf_confirms_without_hook_summary(self):
        for entrypoint, expected in [('sdk-cli', [Kind.final_answer, Kind.task_end]),
                                     ('claude-desktop', []), ('unknown', [])]:
            parser = ClaudeTranscriptParser(); row = answer(); row['entrypoint'] = entrypoint
            parser.events(row)
            leaf = dict(type='last-prompt', sessionId='chat-a', leafUuid='answer-a')
            self.assertEqual(self.kinds(parser, leaf), expected)
            self.assertEqual(self.kinds(parser, leaf), [])

    def test_background_receipts_and_system_notifications_keep_one_human_turn(self):
        parser = ClaudeTranscriptParser()
        parser.events(record('user', 0, promptId='human', message=dict(content='Check totals')))
        parser.events(record('user', 1, promptId='human', toolUseResult=dict(backgroundTaskId='job-a'),
                             message=dict(content=[dict(type='tool_result',tool_use_id='call-a',content='Started')])) )
        row = answer(2); row['entrypoint'] = 'sdk-cli'; parser.events(row)
        self.assertEqual(self.kinds(parser, dict(type='last-prompt',sessionId='chat-a',leafUuid='answer-a')), [])
        notice = record('user', 3, promptId='notification-prompt', promptSource='system',
                        origin=dict(kind='task-notification'), message=dict(content=
                        '<task-notification><task-id>job-a</task-id><status>completed</status></task-notification>'))
        self.assertEqual(self.kinds(parser, notice), [Kind.thinking])
        row = answer(4, identity='final'); row['entrypoint'] = 'sdk-cli'; parser.events(row)
        self.assertEqual(self.kinds(parser, dict(type='last-prompt',sessionId='chat-a',leafUuid='final')),
                         [Kind.final_answer, Kind.task_end])

    def test_background_jobs_survive_metadata_checkpoint_without_body(self):
        parser = ClaudeTranscriptParser()
        parser.events(record('user', 0, promptId='human', message=dict(content='PRIVATE REQUEST')))
        parser.events(record('user', 1, toolUseResult=dict(backgroundTaskId='job-a'),
                             message=dict(content=[dict(type='tool_result',tool_use_id='call-a',content='PRIVATE OUTPUT')])) )
        import json
        checkpoint = parser.history_checkpoint()
        self.assertNotIn('PRIVATE', json.dumps(checkpoint))
        restored = ClaudeTranscriptParser.from_history_checkpoint(checkpoint)
        row = answer(2); row['entrypoint'] = 'sdk-cli'; restored.events(row)
        self.assertEqual(self.kinds(restored, dict(type='last-prompt',sessionId='chat-a',leafUuid='answer-a')), [])

    def test_stop_sequence_is_continuing_work(self):
        parser = ClaudeTranscriptParser()
        self.assertEqual(self.kinds(parser, answer(stop='stop_sequence')), [Kind.thinking])
        self.assertEqual(self.kinds(parser, summary()), [])
        self.assertEqual(self.kinds(parser, record('api-request', 8, querySource='sdk')), [Kind.thinking])

    def test_exact_successful_summary_confirms_once(self):
        parser = ClaudeTranscriptParser()
        self.assertEqual(self.kinds(parser, answer()), [Kind.thinking])
        for row in [summary(parent='foreign-answer'), summary(session='chat-b')]:
            self.assertEqual(self.kinds(parser, row), [])
        self.assertEqual(self.kinds(parser, summary()), [Kind.final_answer, Kind.task_end])
        for row in [summary(), answer(), summary(second=3)]:
            self.assertEqual(self.kinds(parser, row), [])

    def test_stop_hook_feedback_and_unknown_fields_do_not_complete(self):
        for change in [dict(preventedContinuation=True), dict(hasOutput=True), dict(hookErrors=['retry']),
                       dict(hookAdditionalContext=['continue']), dict(stopReason='retry'),
                       dict(preventedContinuation=None), dict(hookErrors=None)]:
            with self.subTest(change=change):
                parser = ClaudeTranscriptParser()
                parser.events(answer())
                self.assertEqual(self.kinds(parser, summary(**change)), [Kind.thinking])

    def test_new_work_invalidates_the_old_response(self):
        for continuation in [record('api-request', 2, querySource='sdk'), record('system', 2, subtype='api_error'),
                             record('user', 2, message=dict(content='Next request')),
                             answer(2, stop='tool_use', identity='working', blocks=[dict(type='thinking')])]:
            with self.subTest(type=continuation['type']):
                parser = ClaudeTranscriptParser()
                parser.events(answer())
                parser.events(continuation)
                self.assertEqual(self.kinds(parser, summary(3)), [])

    def test_tool_and_text_block_order_never_completes(self):
        blocks = [dict(type='text', text='Working'), dict(type='tool_use', name='Read', id='r')]
        for content in [blocks, blocks[::-1]]:
            parser = ClaudeTranscriptParser()
            kinds = self.kinds(parser, answer(blocks=content))
            self.assertIn(Kind.activity_start, kinds)
            self.assertNotIn(Kind.final_answer, kinds)
            self.assertEqual(self.kinds(parser, summary()), [])

    def test_child_context_and_identity_conflicts_cannot_finish_main_turn(self):
        for extra in [dict(isSidechain=True), dict(agentId='child'), dict(isMeta=True), dict(isCompactSummary=True)]:
            parser = ClaudeTranscriptParser()
            row = answer(); row.update(extra)
            self.assertEqual(self.kinds(parser, row), [])
            self.assertEqual(self.kinds(parser, summary()), [])
        parser = ClaudeTranscriptParser()
        row = answer(); row['message']['role'] = 'user'
        self.assertEqual(self.kinds(parser, row), [])

    def test_two_chats_and_two_turns_are_independent(self):
        parser = ClaudeTranscriptParser()
        parser.events(answer(session='chat-a'))
        parser.events(answer(identity='answer-b', session='chat-b'))
        self.assertEqual(self.kinds(parser, summary(parent='answer-b', session='chat-b')),
                         [Kind.final_answer, Kind.task_end])
        self.assertEqual(self.kinds(parser, summary()), [Kind.final_answer, Kind.task_end])
        parser.events(record('user', 3, message=dict(content='Next request')))
        parser.events(answer(4, identity='answer-c'))
        self.assertEqual(self.kinds(parser, summary(5, parent='answer-c')), [Kind.final_answer, Kind.task_end])

    def test_missing_summary_is_not_guessed_from_time_or_model_stop(self):
        parser = ClaudeTranscriptParser()
        self.assertEqual(self.kinds(parser, answer()), [Kind.thinking])
        self.assertEqual(self.kinds(parser, record('attachment', 100000)), [])

    def test_split_tool_blocks_and_helper_requests_preserve_scope(self):
        parser = ClaudeTranscriptParser()
        tool = answer(blocks=[dict(type='tool_use', name='Read', id='r')])
        text = answer(2)
        for row in [tool, text]:
            row['message']['id'] = 'same-api-response'
            parser.events(row)
        self.assertEqual(self.kinds(parser, summary(3)), [])
        parser = ClaudeTranscriptParser()
        parser.events(answer())
        self.assertEqual(self.kinds(parser, record('api-request', 2, querySource='title')), [])
        self.assertEqual(self.kinds(parser, summary(3)), [Kind.final_answer, Kind.task_end])


if __name__ == '__main__':
    unittest.main()


class ClaudeHistoryCompletionTests(unittest.TestCase):
    def test_malformed_body_does_not_stop_metadata_ingestion_or_reuse_an_old_answer(self):
        import json
        from yukio.claude_history import ClaudeHistoryParser
        parser=ClaudeHistoryParser('chat-a')
        parser.observe(json.dumps(answer()).encode(),'answer')
        row=record('user',2,message=dict(content=[dict(type='text',text=123)]))
        observed=parser.observe(json.dumps(row).encode(),'bad')
        self.assertTrue(observed['lifecycle_unavailable'])
        self.assertEqual(observed['kind'],'message_observed')
        self.assertNotIn('turn_marker',parser.observe(json.dumps(summary(3)).encode(),'late'))

    def test_batch_restart_and_schema_upgrade_keep_history_and_expose_completion(self):
        import json, tempfile
        from pathlib import Path
        from yukio.activity_history import ActivityHistory
        from history_view import HistoryView
        from glance_view import GlanceView
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'chat.jsonl';db=root/'history.sqlite'
            reply=answer();reply['entrypoint']='sdk-cli'
            rows=[record('user',0,promptId='human',message=dict(content='Review the current sound.')),reply,
                  dict(type='last-prompt',sessionId='chat-a',leafUuid='answer-a')]
            source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            for _ in rows:
                store=ActivityHistory(db)
                try:store.ingest(source,source_format='claude',max_records=1)
                finally:store.close()
            (root/'claude-workbench-status.json').write_text(json.dumps(dict(state='waiting',updated_at=datetime.now(timezone.utc).isoformat())))
            history=HistoryView({'claude':db});view=GlanceView(history,{'claude':root})
            key=history.groups('claude')['groups'][0]['key']
            self.assertEqual(view.detail('claude',key)['activity_state'],'inactive')
            self.assertEqual(view.cards()['cards'][0]['activity_state'],'inactive')
            store=ActivityHistory(db)
            try:
                before=store.db.execute('SELECT sequence,record FROM events ORDER BY sequence').fetchall()
                sid,raw=store.db.execute('SELECT source_id,state FROM sources').fetchone()
                state=json.loads(raw);state.pop('claude_lifecycle_version')
                store.db.execute('UPDATE sources SET state=? WHERE source_id=?',(json.dumps(state),sid));store.db.commit()
                store.ingest(source,source_format='claude')
                after=store.db.execute('SELECT sequence,record FROM events ORDER BY sequence').fetchall()
                self.assertEqual(after[:len(before)],before)
                self.assertTrue(any(json.loads(row[1]).get('reason')=='claude_lifecycle_model_upgraded' for row in after))
            finally:store.close()
            self.assertEqual(view.cards()['cards'][0]['activity_state'],'inactive')
