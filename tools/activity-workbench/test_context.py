"""Use saved evidence to check pairing, scope, bounded context and navigation."""
import http.client
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from context_view import ContextView, project
from explanation import ExplanationService, encode
from history_view import HistoryView,key_for
from server import create_server
from test_workbench import fixture
from test_explanation import config,answer


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'history.sqlite';fixture(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:db.execute('DELETE FROM events')
        self.history=HistoryView(dict.fromkeys(('codex','claude','deepcode'),self.path));self.view=ContextView(self.history)
        self.key=key_for(['file-a',2,'chat','',0])
    def tearDown(self):self.temp.cleanup()
    def add(self,kind='tool_requested',**extra):
        with closing(sqlite3.connect(self.path)) as db, db:
            seq=db.execute('SELECT coalesce(max(sequence),0)+1 FROM events').fetchone()[0]
            row=dict(event_id='event-'+str(seq),source='codex',source_id='file-a',generation=2,session_id='chat',kind=kind,context_turn_id='turn',call_id='call',tool_name='Read')
            row.update(extra)
            db.execute('INSERT INTO events(sequence,event_id,session_id,record) VALUES (?,?,?,?)',(seq,row['event_id'],row.get('session_id'),json.dumps(row)))
        return row
    def receipt(self,outcome='succeeded',**extra):
        result=dict(call_id='call',turn_id='turn',outcome=outcome,call_outcome=outcome,projection_eligible=True)
        result.update(extra);return self.add('tool_result',result=result)
    def context(self,**extra):return self.view.context('codex',self.key,**extra)

    def test_explicit_codex_request_result_pair_keeps_receipts(self):
        req=self.add();self.receipt();data=self.context();op=data['operations'][0]
        self.assertEqual(op['status'],'succeeded');self.assertEqual(op['request']['event_id'],req['event_id'])
        self.assertEqual(op['receipt_count'],1);self.assertIn('不代表任务完成',op['note'])

    def test_result_without_request_and_request_without_result_are_not_success(self):
        self.receipt();self.add();data=self.context()
        self.assertEqual(data['unlinked_receipt_count'],1);self.assertEqual(data['operations'][0]['status'],'no_receipt')

    def test_later_conflict_overrides_previous_success_but_keeps_both(self):
        self.add();self.receipt();self.receipt('failed',conflicting_results=True)
        op=self.context()['operations'][0];self.assertEqual(op['status'],'conflict');self.assertEqual(op['receipt_count'],2)

    def test_unknown_and_cancelled_are_distinct(self):
        self.add();self.receipt('unknown');self.assertEqual(self.context()['operations'][0]['status'],'unknown')
        self.add(call_id='two');self.receipt('cancelled',call_id='two')
        self.assertEqual(self.context()['operations'][0]['status'],'cancelled')

    def test_duplicate_requests_do_not_duplicate_success_credit(self):
        self.add();self.receipt();self.add();self.receipt()
        d=self.context();self.assertEqual(d['status_counts'],{'unresolved':2});self.assertEqual(d['unlinked_receipt_count'],1)

    def test_turn_source_session_agent_and_sidechain_do_not_cross(self):
        self.add()
        for extra in [dict(context_turn_id='other'),dict(source_id='file-b',generation=1),dict(session_id='other'),dict(agent_id='helper'),dict(is_sidechain=True),dict(source='claude')]:
            self.add(**extra)
        self.receipt();data=self.context();self.assertEqual(len(data['operations']),2)
        self.assertEqual(data['status_counts'],{'succeeded':1,'no_receipt':1})

    def test_unattributed_gap_and_invalid_records_prevent_cross_gap_pairing(self):
        self.add();self.add('observation_gap',session_id=None);self.receipt()
        data=self.context();self.assertEqual(data['operations'][0]['status'],'no_receipt')
        self.assertEqual(data['unlinked_receipt_count'],1);self.assertEqual(data['source_warning_count'],1)

    def test_explicit_projection_false_stays_unlinked_even_with_same_call(self):
        self.add();self.receipt(projection_eligible=False)
        self.assertEqual(self.context()['unlinked_receipt_count'],1)

    def test_context_reset_allows_new_explicit_request_without_reusing_old_one(self):
        self.add('message_observed',source='deepcode',blocks=[dict(kind='tool_requested',evidence_id='old',call_id='a')])
        self.add('context_record_observed',source='deepcode')
        self.add('message_observed',source='deepcode',blocks=[dict(kind='tool_requested',evidence_id='new',call_id='a')])
        self.add('message_observed',source='deepcode',blocks=[dict(kind='tool_result',evidence_id='res',request_evidence_id='new',call_id='a',outcome='succeeded',projection_eligible=True)])
        data=self.view.context('deepcode',self.key)
        self.assertEqual(data['status_counts'],{'no_receipt':1,'succeeded':1})
        self.assertEqual(data['operations'][0]['request']['evidence_id'],'new')

    def test_claude_direct_block_reference_and_cross_scope_guards(self):
        req=self.add('message_observed',source='claude',blocks=[dict(kind='tool_requested',evidence_id='r:block:0',call_id='claude-call',tool_name='Read')])
        self.add('message_observed',source='claude',blocks=[dict(kind='tool_result',evidence_id='r:block:1',call_id='claude-call',request_evidence_id='r:block:0',outcome='failed',projection_eligible=True)])
        d=self.view.context('claude',self.key);self.assertEqual(d['operations'][0]['status'],'failed')
        self.add('message_observed',source='claude',agent_id='other',blocks=[dict(kind='tool_result',evidence_id='r:block:2',call_id='claude-call',request_evidence_id='r:block:0',outcome='succeeded',projection_eligible=True)])
        self.assertEqual(self.view.context('claude',self.key)['operations'][0]['receipt_count'],1)

    def test_block_call_id_mismatch_cannot_borrow_direct_reference(self):
        self.add('message_observed',source='deepcode',blocks=[dict(kind='tool_requested',evidence_id='req',call_id='a')])
        self.add('message_observed',source='deepcode',blocks=[dict(kind='tool_result',evidence_id='res',request_evidence_id='req',call_id='b',outcome='succeeded',projection_eligible=True)])
        d=self.view.context('deepcode',self.key);self.assertEqual(d['unlinked_receipt_count'],1)

    def test_snapshot_does_not_mix_later_receipts_or_filter_pages(self):
        for i in range(36):self.add(call_id='call-'+str(i))
        first=self.context();self.assertTrue(first['has_more']);self.receipt(call_id='call-0')
        frozen=self.context(snapshot=first['snapshot'],offset=first['next_offset']);self.assertEqual(len(frozen['operations']),6)
        self.assertEqual(frozen['status_counts'],{'no_receipt':36})
        current=self.context(filter='succeeded');self.assertEqual(len(current['operations']),1)
        self.assertEqual(current['operations'][0]['status'],'succeeded')

    def test_missing_turn_never_guesses_codex_pair(self):
        self.add(context_turn_id=None);self.receipt(turn_id=None)
        self.assertEqual(self.context()['operations'][0]['status'],'unresolved')

    def test_read_window_reports_limits_and_old_request_is_not_invented(self):
        self.add()
        for i in range(1002):self.add('text_record_observed')
        self.receipt();d=self.context();self.assertTrue(d['window_limited']);self.assertEqual(d['unlinked_receipt_count'],1)
        self.assertEqual(d['operations'],[]);self.assertEqual(d['counts']['records'],1000)

    def test_block_and_receipt_caps_are_visible(self):
        self.add()
        for i in range(12):self.receipt()
        op=self.context()['operations'][0];self.assertEqual(op['receipt_count'],12);self.assertEqual(len(op['receipts']),10)
        self.add('message_observed',blocks=[dict(kind='text_record_observed') for _ in range(5001)])
        self.assertTrue(self.context()['window_limited'])

    def test_warning_range_and_prior_gap_are_not_hidden(self):
        self.add();self.add('observation_gap',session_id=None)
        out=self.context();self.assertEqual(out['window_end'],2)
        self.add(after_gap_evidence_id='prior-gap',call_id='next')
        out,facts=self.view.explanation_context('codex',self.key)
        self.assertTrue(out['earlier_gap_reported']);self.assertIn('前方缺口',facts[2]['note'])

    def test_context_explanation_is_minimized_and_freezes_counts(self):
        self.add(tool_name='PRIVATE-TOOL',body='PRIVATE-BODY');self.receipt()
        out,facts=self.view.explanation_context('codex',self.key)
        sent=[];service=ExplanationService(config(),sender=lambda c,p:sent.append(p) or answer(p))
        p=service.preview_context(dict(client='codex',key=self.key),out,facts)
        self.assertEqual(sent,[]);self.assertNotIn('PRIVATE',encode(p['payload']));self.assertNotIn('event-',encode(p['payload']))
        self.assertIn('成功回执 1 项',p['payload']['facts'][1]['boundary'])
        self.receipt('failed');service.generate(p['token'],True)
        self.assertIn('成功回执 1 项',sent[0]['facts'][1]['boundary']);self.assertEqual(sent[0]['scope']['whole_task_status'],'unknown')

    def test_relations_navigate_only_explicit_current_same_client_targets(self):
        self.add('session_observed',session_id='child',relationships=[dict(kind='spawned_from',from_session_id='child',to_session_id='chat',basis='explicit',status='reported_by_client')])
        self.add('session_observed');self.add('session_observed',source_id='file-b',generation=1)
        self.add('session_observed',source='claude')
        d=self.view.relations('codex',self.key);self.assertEqual(len(d['items']),1)
        self.assertEqual(len(d['items'][0]['targets']),1);self.assertEqual(d['items'][0]['targets'][0]['session_id'],'child')
        child=key_for(['file-a',2,'child','',0]);d=self.view.relations('codex',child)
        self.assertEqual(len(d['items'][0]['targets']),2)
        self.assertTrue(all(t['generation'] in (1,2) for t in d['items'][0]['targets']))

    def test_missing_target_and_cycles_stay_statements_not_recursive_trees(self):
        self.add('session_observed',relationships=[dict(kind='spawned_from',from_session_id='chat',to_session_id='absent',status='reported_by_client')])
        self.assertEqual(self.view.relations('codex',self.key)['items'][0]['targets'],[])
        self.add('session_observed',session_id='absent',relationships=[dict(kind='spawned_from',from_session_id='absent',to_session_id='chat',status='reported_by_client')])
        self.assertEqual(len(self.view.relations('codex',self.key)['items']),2)

    def test_archive_counts_not_merged_with_current(self):
        self.add(generation=1);self.add();self.receipt();old=key_for(['file-a',1,'chat','',0])
        d=self.view.context('codex',old);self.assertTrue(d['archived']);self.assertEqual(d['status_counts'],{'no_receipt':1})

    def test_http_context_preview_and_guard(self):
        self.add();self.receipt();sent=[];service=ExplanationService(config(),sender=lambda c,p:sent.append(p) or answer(p))
        server=create_server(0,{'codex':self.path},explanation_service=service);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,data=None,headers=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            h={'X-Yukio-Workbench':'1','Content-Type':'application/json'};h.update(headers or {})
            c.request(method,path,None if data is None else encode(data).encode(),h);r=c.getresponse();body=r.read();status=r.status;c.close();return status,body
        selection=dict(client='codex',key=self.key,snapshot=0)
        try:
            for route in ('context','relations'):
                self.assertEqual(request('GET','/api/'+route+'?'+urlencode(selection))[0],200)
                self.assertEqual(request('GET','/api/'+route+'?'+urlencode(selection),headers={'Origin':'https://evil.test'})[0],403)
            status,body=request('POST','/api/context-preview',selection);self.assertEqual(status,200);self.assertEqual(sent,[])
            p=json.loads(body);self.assertFalse(p['payload']['scope']['single_saved_record'])
            self.assertEqual(request('POST','/api/context-preview',dict(selection,payload='tamper'))[0],400)
            self.assertEqual(request('POST','/api/explanation-generate',dict(token=p['token'],consent=True))[0],200);self.assertEqual(len(sent),1)
        finally:server.shutdown();server.server_close();thread.join()

    def test_three_actual_history_writers_feed_pairing(self):
        from launcher import core_path
        sys.path.insert(0,str(core_path()))
        from yukio.activity_history import ActivityHistory
        examples={
        'codex':[{'type':'session_meta','payload':{'id':'integration'}},{'type':'event_msg','payload':{'type':'task_started','turn_id':'t'}},{'type':'response_item','payload':{'type':'function_call','call_id':'c','name':'Read'}},{'type':'response_item','payload':{'type':'function_call_output','call_id':'c','output':'{"exit_code":0}'}}],
        'claude':[{'type':'assistant','sessionId':'integration','uuid':'r','message':{'content':[{'type':'tool_use','id':'c','name':'Read','input':{'secret':'PRIVATE'}}]}},{'type':'user','sessionId':'integration','message':{'content':[{'type':'tool_result','tool_use_id':'c','is_error':False,'content':'PRIVATE'}]}}],
        'deepcode':[{'type':'assistant','session_id':'integration','uuid':'r','message':{'role':'assistant','tool_calls':[{'id':'c','function':{'name':'Read','arguments':'PRIVATE'}}]}},{'type':'tool','session_id':'integration','message':{'role':'tool','tool_call_id':'c','content':'PRIVATE','is_error':False}}]}
        # Deep Code uses the concrete role/params shape, unlike Claude's message/content.
        examples['deepcode']=[dict(role='assistant',sessionId='integration',id='request',messageParams=dict(tool_calls=[dict(id='c',type='function',function=dict(name='Read',arguments='PRIVATE'))])),dict(role='tool',sessionId='integration',messageParams=dict(tool_call_id='c'),content=json.dumps(dict(ok=True)))]
        for client,lines in examples.items():
            with self.subTest(client=client):
                source=Path(self.temp.name)/(client+'.jsonl');source.write_text(''.join(json.dumps(x)+'\n' for x in lines));db=Path(self.temp.name)/(client+'.sqlite')
                writer=ActivityHistory(db);writer.ingest(source,source_format=client);writer.close()
                history=HistoryView({client:db});group=history.groups(client)['groups'][0];out=ContextView(history).context(client,group['key'])
                self.assertEqual(len(out['operations']),1)
                self.assertEqual(out['operations'][0]['receipt_count'],1)
                self.assertNotIn('PRIVATE',json.dumps(out))


if __name__=='__main__':unittest.main()
