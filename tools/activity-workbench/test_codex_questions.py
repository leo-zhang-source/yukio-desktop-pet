"""Question lifetime is independent of a Codex assistant turn and ingest batch."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import os
import sys
import tempfile
import unittest
from launcher import core_path
sys.path.insert(0,str(core_path()))
from yukio.activity_history import ActivityHistory, metadata_record
from yukio.parsers_codex import CodexRolloutParser
from history_view import HistoryView
from glance_view import GlanceView


def row(kind,**payload):
    return dict(timestamp='2026-11-15T10:00:00Z',type='response_item',payload=dict(type=kind,**payload))


def ask(call='q'):
    return row('function_call',name='functions.request_user_input_async',call_id=call,arguments=json.dumps(dict(questions=[
        dict(title='PRIVATE_COLOR Choose a color',options=['Red','Blue']),dict(title='PRIVATE_SHAPE Choose a shape',options=['Circle','Square'])])))


def reply(index,call='q'):
    text='<send_user_message_question_reply>'+json.dumps([dict(questionItemId=json.dumps(['request_user_input_async',call,index]),answer='PRIVATE_ANSWER')])+'</send_user_message_question_reply>'
    return row('message',role='user',content=[dict(type='input_text',text=text)])


class CodexQuestionsTests(unittest.TestCase):
    def test_real_collector_drains_existing_batches_before_idle_wait(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sources=root/'sources';sources.mkdir();db=root/'history.sqlite'
            source=sources/'chat.jsonl'
            items=[dict(type='session_meta',payload=dict(id='chat')),ask()]+[row('token_count') for _ in range(1500)]+[reply(0),reply(1)]
            source.write_text(''.join(json.dumps(item)+'\n' for item in items))
            env=dict(os.environ,PYTHONPATH=str(core_path()))
            result=subprocess.run([sys.executable,'-c',
                'from yukio.activity_collector_cli import run_activity_collector; import sys; sys.exit(run_activity_collector(sys.argv[1:]))',
                '--activity-collect',str(db),'--sessions-dir',str(sources),'--seconds','3'],
                env=env,text=True,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['pending_files'],0)
            with sqlite3.connect(db) as connection:
                state=json.loads(connection.execute('SELECT state FROM sources').fetchone()[0])
            self.assertFalse(state['read_pending'])
            self.assertEqual(json.loads(state['checkpoint'])['async_questions'],[])

    def test_metadata_preserves_identity_without_question_or_answer_text(self):
        parser=CodexRolloutParser('chat')
        for item in (ask(),row('function_call_output',call_id='q',output='{"accepted":true}'),row('task_complete'),reply(1)):
            metadata=metadata_record(item)
            self.assertNotIn('PRIVATE_',json.dumps(metadata))
            parser.events(metadata)
        saved=parser.history_checkpoint()
        self.assertNotIn('PRIVATE_',json.dumps(saved))
        restored=CodexRolloutParser.from_history_checkpoint(saved)
        self.assertEqual(restored._async_questions['q']['indices'],{0})
        with self.assertRaises(ValueError):
            CodexRolloutParser.from_history_checkpoint(dict(saved,async_questions=[dict(id='q',indices=[True],ts=0)]))

    def test_saved_pending_questions_survive_batch_restart_turn_end_and_noise(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'chat.jsonl';db=root/'history.sqlite'
            source.write_text('')
            def append(*items):
                with source.open('a') as f:
                    for item in items:f.write(json.dumps(item)+'\n')
                store=ActivityHistory(db)
                try:
                    while store.ingest(source)['batch_full']:pass
                finally:store.close()
            append(dict(type='session_meta',payload=dict(id='chat')),row('task_started',turn_id='first'),
                   row('message',role='user',content=[dict(type='input_text',text='Ask two questions')]),ask())
            (root/'codex-workbench-status.json').write_text(json.dumps(dict(state='waiting',updated_at=datetime.now(timezone.utc).isoformat())))
            history=HistoryView({'codex':db});view=GlanceView(history,{'codex':root})
            key=history.groups('codex')['groups'][0]['key']
            def pending(*words):
                detail=view.detail('codex',key)
                self.assertEqual(detail['activity_state'],'waiting')
                self.assertEqual(view.cards()['cards'][0]['activity_state'],'waiting')
                for word in words:self.assertIn(word,detail['content'])
                return detail
            pending('Choose a color','Choose a shape')
            append(row('function_call_output',call_id='q',output='{"accepted":true}'),row('task_complete',turn_id='first'),
                   row('task_started',turn_id='second'),row('message',role='user',content=[dict(type='input_text',text='Also check progress')]),
                   *[row('token_count') for _ in range(507)])
            pending('Choose a color','Choose a shape')
            append(row('compacted'),reply(1),ask())
            detail=pending('Choose a color');self.assertNotIn('Choose a shape',detail['content'])
            append(reply(0))
            self.assertNotEqual(view.detail('codex',key)['activity_state'],'waiting')
            with sqlite3.connect(db) as connection:
                saved=''.join(r[0] for r in connection.execute('SELECT state FROM sources'))
                saved+=''.join(r[0] for r in connection.execute('SELECT record FROM events'))
            self.assertNotIn('PRIVATE_',saved)

    def test_backfill_does_not_flash_a_question_before_reading_its_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'chat.jsonl';db=root/'history.sqlite'
            items=[dict(type='session_meta',payload=dict(id='chat')),row('message',role='user',content='Ask first'),ask(),reply(0),reply(1)]
            source.write_text(''.join(json.dumps(x)+'\n' for x in items))
            (root/'codex-workbench-status.json').write_text(json.dumps(dict(state='active',updated_at=datetime.now(timezone.utc).isoformat())))
            store=ActivityHistory(db)
            try:
                store.ingest(source,max_records=3)
                history=HistoryView({'codex':db});view=GlanceView(history,{'codex':root});key=history.groups('codex')['groups'][0]['key']
                detail=view.detail('codex',key)
                self.assertEqual(detail['activity_state'],'unknown')
                self.assertNotIn('PRIVATE_COLOR',detail['content'])
                self.assertNotEqual(view.cards()['cards'][0]['activity_state'],'waiting')
                store.ingest(source)
                self.assertNotEqual(view.detail('codex',key)['activity_state'],'waiting')
            finally:store.close()

    def test_upgrade_replays_original_source_and_preserves_previous_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'chat.jsonl';db=root/'history.sqlite'
            source.write_text('\n'.join(json.dumps(x) for x in [dict(type='session_meta',payload=dict(id='chat')),ask()])+'\n')
            store=ActivityHistory(db)
            try:
                store.ingest(source)
                state=json.loads(store.db.execute('SELECT state FROM sources').fetchone()[0]);state.pop('codex_question_version')
                store.db.execute('UPDATE sources SET state=?',(json.dumps(state),));store.db.commit()
                result=store.ingest(source)
                self.assertEqual(result['generation'],2)
                self.assertGreater(store.db.execute('SELECT COUNT(*) FROM events WHERE json_extract(record,"$.generation")=1').fetchone()[0],0)
                current=json.loads(store.db.execute('SELECT state FROM sources').fetchone()[0])
                self.assertEqual(json.loads(current['checkpoint'])['async_questions'][0]['indices'],[0,1])
            finally:store.close()


if __name__=='__main__':unittest.main()
