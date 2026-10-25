"""Synthetic evidence checks: two recipients, missing input, failure and ambiguity."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import closing
import sqlite3
from launcher import core_path
sys.path.insert(0,str(core_path()))
from yukio.activity_history import ActivityHistory
from yukio.activity_handoffs import capture
from history_view import HistoryView
from source_context import SourceContext
from handoff_view import HandoffView


def header(id,parent=None):
    p=dict(id=id)
    if parent:p['source']=dict(subagent=dict(thread_spawn=dict(parent_thread_id=parent)))
    return dict(type='session_meta',payload=p)


def item(id='spawn',tool='spawn_agent',targets=None,states=None,status='completed',**extra):
    return dict(type='event_msg',payload=dict(type='item_completed',thread_id='main',turn_id='t',item=dict(type='CollabAgentToolCall',id=id,tool=tool,sender_thread_id='main',receiver_thread_ids=['child'] if targets is None else targets,agents_states=states or {},status=status,**extra)))


def text(value):return dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text=value)]))
def start(turn='t'):return dict(type='event_msg',payload=dict(type='task_started',turn_id=turn))
def req(name='spawn_agent',call='a',args=None):return dict(type='response_item',payload=dict(type='function_call',name=name,namespace='collaboration',call_id=call,arguments=json.dumps(args or {'message':'PRIVATE_SENTINEL 检查按钮'})))
def receipt(value,call='a'):return dict(type='response_item',payload=dict(type='function_call_output',call_id=call,output=json.dumps(value)))


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=self.root/'history.sqlite';self.sources=self.root/'sessions';self.sources.mkdir()
        self.history=HistoryView({'codex':self.db});self.reader=SourceContext({'codex':self.sources});self.view=HandoffView(self.history,self.reader)
    def tearDown(self):self.temp.cleanup()
    def save(self,rows,name='main'):
        p=self.sources/(name+'.jsonl');p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        h=ActivityHistory(self.db)
        try:
            while h.ingest(p)['batch_full']:pass
        finally:h.close()
        self.reader.scan_at.clear();return p
    def detail(self,snapshot=0):
        key=next(g['key'] for g in self.history.groups('codex')['groups'] if g['session_id']=='main')
        return self.view.detail('codex',key,snapshot)
    def test_two_workers_keep_messages_and_returns_separate(self):
        self.save([header('main'),start(),item(prompt='检查按钮'),item('spawn2',targets=['child2'],prompt='检查颜色'),
                   item('wait','wait',targets=['child','child2'],states={'child':{'completed':'按钮检查通过'},'child2':{'completed':'需要修正颜色'}})])
        self.save([header('child','main'),start(),text('检查按钮')],'child');self.save([header('child2','main'),start(),text('检查颜色')],'child2')
        data=self.detail();self.assertEqual(len(data['items']),3)
        wait=data['items'][0];self.assertEqual([r['text'] for r in wait['returns']],['按钮检查通过','需要修正颜色'])
        self.assertTrue(all('已经采用' in c['use_note'] for c in data['items']))
        spawn=data['items'][2];self.assertIn('完全相同',spawn['targets'][0]['input_note']);self.assertEqual(spawn['returns'],[])
        self.assertNotIn('全部完成',json.dumps(data,ensure_ascii=False))
    def test_no_recipient_context_no_return_and_no_claim_of_use(self):
        self.save([header('main'),start(),item(prompt='检查按钮')]);card=self.detail()['items'][0]
        self.assertNotIn('key',card['targets'][0]);self.assertEqual(card['returns'],[]);self.assertIn('暂未',card['targets'][0]['input_note'])
    def test_exact_function_request_receipt_and_wait(self):
        self.save([header('main'),start(),req(),receipt({'agent_id':'child'}),req('wait','w',{'ids':['child']}),receipt({'status':{'child':{'completed':'PRIVATE_SENTINEL 回复'}}},'w')])
        data=self.detail();self.assertEqual(data['items'][1]['targets'][0]['id'],'child');self.assertIn('PRIVATE_SENTINEL 回复',data['items'][0]['returns'][0]['text'])
        with closing(sqlite3.connect(self.db)) as db:
            for table,col in [('events','record'),('sources','state')]:self.assertFalse(any('PRIVATE_SENTINEL' in r[0] for r in db.execute('SELECT '+col+' FROM '+table)))
    def test_duplicate_requests_conflicting_returns_and_late_cross_turn_are_not_joined(self):
        for middle in [[req()], [start('other')], [dict(type='compacted',payload={})], ['invalid']]:
            self.save([header('main'),start(),req(),*middle,receipt({'agent_id':'child'})])
            self.assertTrue(all(not x['targets'] for x in self.detail()['items']))
    def test_result_from_another_source_cannot_supply_recipient(self):
        self.save([header('main'),start(),req()]);self.save([header('main'),start(),receipt({'agent_id':'child'})],'other')
        # Select original request source explicitly.
        sid=hashlib.sha256(str((self.sources/'main.jsonl').resolve()).encode()).hexdigest()
        key=next(g['key'] for g in self.history.groups('codex')['groups'] if g['source_id']==sid)
        self.assertFalse(self.view.detail('codex',key)['items'][0]['targets'])
    def test_conflicting_native_terminals_and_foreign_sender(self):
        self.save([header('main'),start(),item(),item(status='failed')]);self.assertTrue(self.detail()['items'][0]['conflict'])
        foreign=item();foreign['payload']['item']['sender_thread_id']='other';self.save([header('main'),start(),foreign]);self.assertFalse(self.detail()['items'])
    def test_wrong_parent_and_multiple_sources_do_not_auto_link(self):
        self.save([header('main'),start(),item(prompt='检查按钮')]);self.save([header('child','other'),text('检查按钮')],'child')
        self.assertNotIn('key',self.detail()['items'][0]['targets'][0])
        self.save([header('child','main'),text('检查按钮')],'child');self.save([header('child','main'),text('检查按钮')],'duplicate')
        self.assertNotIn('key',self.detail()['items'][0]['targets'][0])
    def test_changed_source_and_restarted_history_do_not_fabricate_content(self):
        p=self.save([header('main'),start(),item(prompt='检查按钮')]);key=self.history.groups('codex')['groups'][0]['key']
        h=ActivityHistory(self.db)
        try:self.assertEqual(h.ingest(p)['events_saved'],0)
        finally:h.close()
        p.write_text(p.read_text().replace('检查按钮','检查颜色'));data=self.view.detail('codex',key)
        self.assertNotIn('检查颜色',data['items'][0]['sent']);self.assertNotIn('检查按钮',data['items'][0]['sent'])
    def test_historical_snapshot_excludes_later_returns(self):
        self.save([header('main'),start(),item(),item('wait','wait',states={'child':{'completed':'回复'}})])
        self.assertEqual(len(self.detail(snapshot=3)['items']),1)
    def test_legacy_events_and_malformed_inputs_are_safe(self):
        for tool in [[],{},5,None]:
            p={'item':{'type':'CollabAgentToolCall','tool':tool}};self.assertIsNone(capture(p,'item_completed'))
        row=capture(dict(sender_thread_id='main',call_id='w',statuses={'child':{'completed':'secret'}}),'collab_waiting_end')
        self.assertEqual(row['targets'],['child']);self.assertTrue(row['states']['child']['has_message']);self.assertNotIn('secret',json.dumps(row))
    def test_failed_creation_with_agent_identity_is_not_success(self):
        self.save([header('main'),start(),req(),receipt({'agent_id':'child','success':False})])
        card=self.detail()['items'][0];self.assertTrue(card['conflict']);self.assertNotIn('已确认',card['status'])
    def test_self_target_is_unreliable(self):
        self.save([header('main'),start(),item(targets=['main'])]);self.assertTrue(self.detail()['items'][0]['conflict'])
    def test_missing_turn_is_visible_but_never_merged(self):
        row=item();row['payload'].pop('turn_id');self.save([header('main'),row])
        self.assertTrue(self.detail()['items'][0]['conflict'])
    def test_closed_message_is_not_inferred_to_be_a_return(self):
        self.save([header('main'),start(),item('close','close_agent',states={'child':'shutdown'})])
        card=self.detail()['items'][0];self.assertFalse(card['returns']);self.assertFalse(card['targets'][0]['has_message'])
    def test_gap_prevents_pairing_and_limits_are_visible(self):
        self.save([header('main'),start(),req(),'broken',receipt({'agent_id':'child'})]);self.assertFalse(self.detail()['items'][0]['targets'])
        self.save([header('main'),start(),item(targets=['child'+str(i) for i in range(32)])]);d=self.detail();self.assertTrue(d['limited']);self.assertEqual(len(d['items'][0]['targets']),4)

    def test_old_history_upgrade_appends_without_rewriting(self):
        p=self.save([header('main'),start(),item()])
        with closing(sqlite3.connect(self.db)) as db,db:
            before=db.execute('SELECT sequence,record FROM events').fetchall();sid,raw=db.execute('SELECT source_id,state FROM sources').fetchone();state=json.loads(raw);state.pop('codex_handoff_version');db.execute('UPDATE sources SET state=? WHERE source_id=?',(json.dumps(state),sid))
        h=ActivityHistory(self.db)
        try:self.assertEqual(h.ingest(p)['generation'],2)
        finally:h.close()
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(before,db.execute('SELECT sequence,record FROM events WHERE sequence<=3').fetchall())
        self.assertEqual(len(self.detail()['items']),1)

if __name__=='__main__':unittest.main()
