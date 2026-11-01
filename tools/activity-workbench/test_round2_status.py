import json
import tempfile
import time
import unittest
from pathlib import Path
from datetime import datetime, timezone
from launcher import core_path
import sys
sys.path.insert(0, str(core_path()))
from yukio.activity_history import ActivityHistory
from history_view import HistoryView
from glance_view import GlanceView

class ClaudeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.sources=self.root/'projects';self.sources.mkdir()
        self.path=self.sources/'A.jsonl';self.db=self.root/'history.sqlite'
        self.now=time.time();self.rows=[]
        self.history=HistoryView({'claude':self.db})
        self.glance=GlanceView(self.history,{'claude':self.sources},clock=lambda:self.now)
        (self.root/'claude-workbench-status.json').write_text(json.dumps(dict(state='active',updated_at=datetime.now(timezone.utc).isoformat())))
    def tearDown(self):self.tmp.cleanup()
    def append(self,kind,content=None,**extra):
        self.now+=.01
        row=dict(type=kind,sessionId='A',timestamp=datetime.fromtimestamp(self.now,timezone.utc).isoformat(),uuid=str(len(self.rows)))
        if kind in ('user','assistant'):row['message']=dict(role=kind,content=content,**extra)
        else:row.update(extra)
        self.rows.append(row)
        self.path.write_text(''.join(json.dumps(x)+'\n' for x in self.rows))
        store=ActivityHistory(self.db)
        try:store.ingest(self.path,source_format='claude')
        finally:store.close()
        self.key=self.history.groups('claude')['groups'][0]['key']
    def card(self):return self.glance.cards()['cards'][0]
    def detail(self):return self.glance.detail('claude',self.key)
    def test_begin_stop_and_resume_agree_in_rail_and_detail(self):
        self.append('user','Please inspect this test project')
        self.assertEqual(self.card()['activity_state'],'working')
        self.assertEqual(self.detail()['turn_marker'],'turn_started')
        self.append('assistant',[dict(type='text',text='This step is finished; the rest remains.')],stop_reason='end_turn')
        self.assertEqual(self.card()['activity_state'],'inactive')
        self.assertEqual(self.detail()['status'],'这一轮已结束')
        self.append('user','Continue')
        self.assertEqual(self.card()['activity_state'],'working')
    def test_tool_result_is_not_a_new_user_request(self):
        self.append('user','Run the check')
        self.append('assistant',[dict(type='tool_use',id='c',name='Read',input={})],stop_reason='tool_use')
        self.append('user',[dict(type='tool_result',tool_use_id='c',is_error=False,content='test')])
        self.assertEqual(self.card()['activity_state'],'working')
        self.append('system',subtype='stop_hook_summary')
        self.assertEqual(self.card()['activity_state'],'inactive')
        self.append('user',[dict(type='tool_result',tool_use_id='c',is_error=False,content='late duplicate')])
        self.assertNotEqual(self.card()['activity_state'],'working')
    def test_interruption_and_stale_records_do_not_claim_work(self):
        self.append('user','Test request')
        self.append('user','[Request interrupted by user]')
        self.assertEqual(self.card()['activity_state'],'inactive')
        self.append('user','Resume the test')
        self.now+=700
        self.assertEqual(self.card()['activity_state'],'unknown')
    def test_delayed_old_start_does_not_reopen_newer_end(self):
        self.append('user','Old request')
        old=self.rows[0]
        self.append('assistant',[dict(type='text',text='Reply ended')],stop_reason='end_turn')
        self.rows.append(dict(old,uuid='late-copy'))
        self.path.write_text(''.join(json.dumps(x)+'\n' for x in self.rows))
        store=ActivityHistory(self.db)
        try:store.ingest(self.path,source_format='claude')
        finally:store.close()
        self.assertEqual(self.card()['activity_state'],'inactive')
        self.assertEqual(self.detail()['status'],'这一轮已结束')

    def test_meta_and_tool_result_rows_do_not_create_user_turns(self):
        from yukio.claude_history import ClaudeHistoryParser
        p=ClaudeHistoryParser('A')
        for extra,content in [({'isMeta':True},'Internal'),({},'<local-command-stdout>done</local-command-stdout>'),({},[dict(type='tool_result',tool_use_id='x')])]:
            raw=json.dumps(dict(type='user',sessionId='A',message=dict(role='user',content=content),**extra)).encode()
            self.assertNotIn('turn_marker',p.observe(raw,'test'))
        row=p.observe(json.dumps(dict(type='user',sessionId='A',message=dict(role='user',content='PRIVATE TEST BODY'))).encode(),'test')
        self.assertEqual(row['turn_marker'],'turn_started')
        self.assertNotIn('PRIVATE TEST BODY',json.dumps(row))
    def test_other_session_does_not_end_selected_chat(self):
        self.append('user','Test request')
        path=self.sources/'B.jsonl'
        path.write_text(json.dumps(dict(type='assistant',sessionId='B',timestamp=datetime.fromtimestamp(self.now,timezone.utc).isoformat(),message=dict(role='assistant',stop_reason='end_turn',content=[dict(type='text',text='Other reply')])))+'\n')
        store=ActivityHistory(self.db)
        try:store.ingest(path,source_format='claude')
        finally:store.close()
        cards=self.glance.cards()['cards']
        self.assertEqual(next(c for c in cards if c['session_id']=='A')['activity_state'],'working')
        self.assertEqual(next(c for c in cards if c['session_id']=='B')['activity_state'],'inactive')
if __name__=='__main__':unittest.main()
