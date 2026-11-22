"""Claude interaction contract, exercised through the saved history and both views."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from claude_runtime import ClaudeRuntimeIndex
from claude_desktop import apply_interaction, ClaudeInteractionIndex
from launcher import core_path
sys.path.insert(0, str(core_path()))
from yukio.activity_history import ActivityHistory
from yukio.parsers_claude import ClaudeTranscriptParser
from yukio.claude_history import ClaudeHistoryParser
from yukio.events import Kind
from history_view import HistoryView
from glance_view import GlanceView
from test_claude_completion import record, answer


def ask(second=2, identity='q'):
    return record('assistant', second, uuid='request-'+identity, message=dict(role='assistant', id='response-'+identity,
        content=[dict(type='tool_use',name='AskUserQuestion',id=identity,input=dict(questions=[dict(question='Choose a color',options=[dict(label='Red'),dict(label='Blue')])]))]))


class ClaudeInteractionTests(unittest.TestCase):
    def test_denied_permission_has_cancelled_outcome_with_original_error_flag(self):
        for text in ('Permission denied by hook','The user declined this operation in Yukio.'):
            p=ClaudeTranscriptParser();p.events(ask())
            receipt=record('user',3,message=dict(content=[dict(type='tool_result',tool_use_id='q',is_error=True,content=text)]))
            self.assertEqual([e.kind for e in p.events(receipt)],[Kind.activity_end])
            history=ClaudeHistoryParser('chat-a');history.observe(json.dumps(ask()).encode(),'request')
            rows=history.observe(json.dumps(receipt).encode(),'receipt')['blocks']
            result=next(r for r in rows if r.get('kind')=='tool_result')
            self.assertEqual(result['outcome'],'cancelled')
            self.assertTrue(result['reported_is_error'])
    def test_plan_review_waits_and_desktop_plan_updates_the_progress(self):
        p=ClaudeTranscriptParser()
        events=p.events(record('assistant',1,message=dict(content=[dict(type='tool_use',id='plan',name='mcp__ccd_turn__update_plan',
            input=dict(items=[dict(content='Done',status='completed'),dict(content='Next',status='in_progress')]))])))
        self.assertEqual(events[-1].kind,Kind.todo_list)
        self.assertEqual(len(events[-1].todos),2)
        p.events(record('assistant',2,message=dict(content=[dict(type='tool_use',id='approval',name='ExitPlanMode',input={})])))
        self.assertEqual(p.snapshot('chat-a')['phase'],'waiting')
        self.assertEqual(p.snapshot('chat-a')['interaction_kind'],'permission')

    def test_runtime_registry_validates_identity_and_keeps_exit_distinct_from_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sid=str(uuid.uuid4());clock=[10];alive=[True]
            path=root/'123.json'
            def write(status='waiting',start='correct'):
                path.write_text(json.dumps(dict(pid=123,sessionId=sid,pidDomain='darwin',procStart=start,status=status,updatedAt=1000)))
            write()
            index=ClaudeRuntimeIndex(root,clock=lambda:clock[0],process=lambda pid,start:alive[0] and pid==123 and start=='correct')
            self.assertEqual(index.get(sid)['status'],'waiting')
            write('busy');clock[0]+=3
            self.assertEqual(index.get(sid)['status'],'working')
            write('idle');clock[0]+=3
            self.assertEqual(index.get(sid)['status'],'idle')
            alive[0]=False;clock[0]+=3
            self.assertEqual(index.get(sid)['status'],'offline')
            clock[0]+=3
            self.assertEqual(index.get(sid)['status'],'offline')
            # A cold reader cannot treat a reused PID as a running client.
            self.assertIsNone(ClaudeRuntimeIndex(root,clock=lambda:clock[0],process=lambda *_:False).get(sid))

    def test_permission_channel_is_live_and_never_copies_private_question_text(self):
        with tempfile.TemporaryDirectory() as temp:
            import os
            root=Path(temp);rid=str(uuid.uuid4());path=root/rid;path.mkdir()
            request=dict(id=rid,session='chat-a',callID='call',pid=os.getpid(),createdAt=3000,expiresAt=20000,
                         questions=[dict(text='PRIVATE TEXT',approval=True)])
            (path/'request.json').write_text(json.dumps(request))
            channel=ClaudeInteractionIndex(root,clock=lambda:10)
            p=ClaudeTranscriptParser();p.events(record('user',1,message=dict(content='Do work')))
            state=dict(checkpoint=json.dumps(dict(lifecycle=p.history_checkpoint())))
            detail={};apply_interaction(detail,state,'chat-a',channel)
            self.assertEqual(detail['status'],'等待你批准')
            self.assertNotIn('PRIVATE TEXT',json.dumps(detail))
            (path/'done').touch()
            channel.checked=None
            self.assertIsNone(channel.get('chat-a'))

    def test_question_is_not_completed_by_an_unrelated_response(self):
        p=ClaudeTranscriptParser();p.events(ask())
        a=answer(3);a['entrypoint']='sdk-cli';p.events(a)
        self.assertEqual(p.events(dict(type='last-prompt',sessionId='chat-a',leafUuid='answer-a')),[])

    def test_earlier_parallel_receipt_closes_only_its_matching_question(self):
        p=ClaudeTranscriptParser();p.events(ask());p.events(record('api-request',5,querySource='sdk'))
        receipt=record('user',4,uuid='receipt',message=dict(content=[dict(type='tool_result',tool_use_id='q',content='Answered')]))
        self.assertEqual([e.kind for e in p.events(receipt)],[Kind.activity_end])
        self.assertEqual(p.events(ask()),[])

    def test_waiting_survives_restart_and_noise_then_exact_receipt_retires_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'chat.jsonl';db=root/'history.sqlite'
            question=ask()
            question['message']['content'][0]['input']['questions'].append(dict(question='Choose a shape',options=[dict(label='Circle'),dict(label='Square')]))
            rows=[record('user',1,promptId='human',message=dict(content='Ask before continuing')),
                  record('assistant',1,message=dict(content=[dict(type='text',text='Earlier progress before asking')])) ,question]
            source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            def ingest():
                store=ActivityHistory(db)
                try:
                    while store.ingest(source,source_format='claude')['batch_full']:pass
                finally:store.close()
            ingest()
            (root/'claude-workbench-status.json').write_text(json.dumps(dict(state='waiting',updated_at=datetime.now(timezone.utc).isoformat())))
            history=HistoryView({'claude':db});view=GlanceView(history,{'claude':root},clock=lambda:4000)
            key=history.groups('claude')['groups'][0]['key']
            def waiting():
                self.assertEqual(view.cards()['cards'][0]['activity_state'],'waiting')
                self.assertEqual(view.detail('claude',key)['activity_state'],'waiting')
                self.assertIn('回答',view.detail('claude',key)['needs_you'])
                self.assertIn('Choose a color',view.detail('claude',key)['content'])
            waiting()
            with source.open('a') as f:
                for n in range(3,510):f.write(json.dumps(record('progress',n,data=dict(type='hook_progress')))+'\n')
            ingest();waiting()
            from work_understanding import WorkUnderstanding
            _,payload,_=WorkUnderstanding(view).prepared('claude',key)
            self.assertTrue(any('等待你回答' in fact['excerpt'] for fact in payload['facts']))
            channel=root/'answers';request_id=str(uuid.uuid4());request=channel/request_id;request.mkdir(parents=True)
            (request/'request.json').write_text(json.dumps(dict(id=request_id,session='chat-a',callID='q',pid=os.getpid(),
                createdAt=999000,expiresAt=1010000,questions=[dict(text='Choose a color'),dict(text='Choose a shape')])) )
            (request/'receipt-0.json').write_text(json.dumps('Red'))
            view.reader.claude_interactions=ClaudeInteractionIndex(channel,clock=lambda:1000)
            next_question=view.detail('claude',key)
            self.assertIn('Choose a shape',next_question['content'])
            self.assertNotIn('Choose a color',next_question['content'])
            (request/'done').touch();view.reader.claude_interactions.checked=None
            with source.open('a') as f:f.write(json.dumps(record('user',510,uuid='receipt',message=dict(content=[dict(type='tool_result',tool_use_id='q',content='Red')])) )+'\n')
            ingest()
            self.assertNotEqual(view.cards()['cards'][0]['activity_state'],'waiting')
            self.assertNotEqual(view.detail('claude',key)['activity_state'],'waiting')

    def test_backfill_does_not_publish_a_historical_question_as_current(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'chat.jsonl';db=root/'history.sqlite'
            receipt=record('user',3,message=dict(content=[dict(type='tool_result',tool_use_id='q',content='Red')]))
            rows=[record('user',1,message=dict(content='Ask first')),ask(),receipt,answer(4)]
            source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (root/'claude-workbench-status.json').write_text(json.dumps(dict(state='active',updated_at=datetime.now(timezone.utc).isoformat())))
            store=ActivityHistory(db)
            try:
                store.ingest(source,source_format='claude',max_records=2)
                history=HistoryView({'claude':db});view=GlanceView(history,{'claude':root},clock=lambda:4000)
                key=history.groups('claude')['groups'][0]['key']
                detail=view.detail('claude',key)
                self.assertEqual(detail['activity_state'],'unknown')
                self.assertNotIn('Choose a color',detail['content'])
                self.assertNotEqual(view.cards()['cards'][0]['activity_state'],'waiting')
                store.ingest(source,source_format='claude')
                self.assertNotEqual(view.detail('claude',key)['activity_state'],'waiting')
            finally:store.close()


if __name__=='__main__':unittest.main()
