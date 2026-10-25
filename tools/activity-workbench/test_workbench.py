"""Synthetic isolation, evidence presentation and HTTP boundary checks."""
import hashlib
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import sys
from urllib.parse import urlencode

from history_view import APPLICATION_ID, HistoryView, describe, key_for, key_parts, present
from server import create_server


def fixture(path):
    db = sqlite3.connect(path)
    db.executescript(f'PRAGMA application_id={APPLICATION_ID}; PRAGMA user_version=2; CREATE TABLE sources(source_id TEXT PRIMARY KEY,state TEXT NOT NULL); CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE,session_id TEXT,record TEXT NOT NULL); CREATE INDEX events_session ON events(session_id,sequence);')
    for source, gen in [('file-a',2),('file-b',1),('claude-file',1),('deep-file',1)]:
        db.execute('INSERT INTO sources VALUES (?,?)', (source,json.dumps(dict(generation=gen))))
    def add(source='file-a', generation=2, session='demo-chat-a', client='codex', **extra):
        seq=db.execute('SELECT coalesce(max(sequence),0)+1 FROM events').fetchone()[0]
        row=dict(event_id=f'{source}:{generation}:{seq}',source_id=source,generation=generation,session_id=session,source=client,
                 kind='tool_requested',evidence_class='observed',source_line=seq,timestamp_available=False,tool_name='Read',**extra)
        db.execute('INSERT INTO events(event_id,session_id,record) VALUES (?,?,?)',(row['event_id'],session,json.dumps(row)))
    add(generation=1)
    for _ in range(85): add()
    add(session='demo-chat-b')
    add(source='file-b',generation=1)
    add(agent_id='demo-helper')
    add(agent_id='demo-helper',is_sidechain=True)
    # Same client-provided chat ID must not merge different clients.
    add(source='claude-file',generation=1,client='claude')
    add(source='deep-file',generation=1,client='deepcode')
    row=dict(event_id='gap',source_id='file-a',generation=2,source='codex',kind='observation_gap',evidence_class='observed',timestamp_available=False,gap_part='start',record_complete=True,skipped_bytes=9000000)
    db.execute('INSERT INTO events(event_id,session_id,record) VALUES (?,?,?)',('gap',None,json.dumps(row)))
    blocks=[dict(kind='text_record_observed',evidence_class='self_report',evidence_id=f'blocks:block:{n}',block_index=n,body='PRIVATE BODY') for n in range(101)]
    blocks[0].update(kind='tool_result',outcome='failed',call_outcome='failed',projection_eligible=True,tool_name='Bash',request_evidence_id='request-demo')
    row=dict(event_id='blocks',source_id='claude-file',generation=1,source='claude',session_id='demo-chat-a',kind='message_observed',blocks=blocks)
    db.execute('INSERT INTO events(event_id,session_id,record) VALUES (?,?,?)',('blocks','demo-chat-a',json.dumps(row)))
    row=dict(event_id='result-demo',source_id='file-a',generation=2,source='codex',session_id='demo-chat-a',kind='tool_result',timestamp_available=False,result=dict(outcome='succeeded',call_outcome='unknown',projection_eligible=False,association='ambiguous_across_gap',call_id='demo-call'),after_gap_evidence_id='gap')
    db.execute('INSERT INTO events(event_id,session_id,record) VALUES (?,?,?)',('result-demo','demo-chat-a',json.dumps(row)))
    db.commit();db.close()


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'history.sqlite';fixture(self.path)
        self.view=HistoryView(dict.fromkeys(('codex','claude','deepcode'),self.path))
    def tearDown(self): self.temp.cleanup()
    def key(self, session='demo-chat-a', source='file-a', generation=2, agent='', sidechain=0):
        return key_for([source,generation,session,agent,sidechain])

    def test_scope_separates_clients_files_sessions_agents_and_sidechains(self):
        data=self.view.groups('codex')['groups']
        self.assertEqual(len(data),6)
        self.assertEqual(len({g['key'] for g in data}),6)
        for group in data:
            rows=self.view.timeline('codex',group['key'])['items']
            for item in rows:
                self.assertEqual(item['evidence']['source'],'codex')
                self.assertEqual(item['evidence'].get('session_id',''),group['session_id'])
                self.assertEqual(item['evidence'].get('agent_id',''),group['agent_id'])
        self.assertEqual(len(self.view.groups('claude')['groups']),1)
        self.assertEqual(self.view.timeline('claude',self.key())['items'],[])

    def test_current_and_archive_are_separate(self):
        self.assertTrue(all(g['generation']==2 for g in self.view.groups('codex')['groups'] if g['source_id']=='file-a'))
        old=self.view.groups('codex',archive=True)['groups'];self.assertEqual(len(old),1)
        self.assertTrue(self.view.timeline('codex',old[0]['key'])['archived'])

    def test_timeline_snapshot_paging_without_duplicates_or_new_rows(self):
        first=self.view.timeline('codex',self.key(),limit=10);snapshot=first['snapshot']
        db=sqlite3.connect(self.path)
        row=dict(event_id='late',source='codex',source_id='file-a',generation=2,session_id='demo-chat-a',kind='turn_ended')
        db.execute('INSERT INTO events(event_id,session_id,record) VALUES (?,?,?)',('late','demo-chat-a',json.dumps(row)));db.commit();db.close()
        seen=[i['evidence']['sequence'] for i in first['items']];page=first
        while page['has_more']:
            page=self.view.timeline('codex',self.key(),before=page['next_before'],snapshot=snapshot,limit=10)
            seen += [i['evidence']['sequence'] for i in page['items']]
        self.assertEqual(len(seen),86);self.assertEqual(len(seen),len(set(seen)));self.assertEqual(seen,sorted(seen,reverse=True))
        self.assertGreater(self.view.timeline('codex',self.key())['snapshot'],snapshot)

    def test_groups_page_is_stable_and_complete(self):
        page=self.view.groups('codex',limit=2);keys=[]
        while True:
            keys += [g['key'] for g in page['groups']]
            if not page['has_more']:break
            page=self.view.groups('codex',limit=2,offset=page['next_offset'],snapshot=page['snapshot'])
        self.assertEqual(len(keys),6);self.assertEqual(len(set(keys)),6)

    def test_unattributed_gap_visible_in_known_session(self):
        page=self.view.timeline('codex',self.key())
        self.assertIn('observation_gap',[n['evidence']['kind'] for n in page['source_notices']])
        self.assertNotIn('observation_gap',[n['evidence']['kind'] for n in page['items']])

    def test_blocks_paging_and_session_access_boundary(self):
        group=self.view.groups('claude')['groups'][0];item=self.view.timeline('claude',group['key'])['items'][0]
        self.assertEqual(item['block_count'],101);self.assertEqual(len(item['preview']),3)
        seq=item['evidence']['sequence'];all_items=[];offset=0
        while True:
            page=self.view.blocks('claude',group['key'],seq,offset=offset)
            all_items+=page['items'];offset=page['next_offset']
            if not page['has_more']:break
        self.assertEqual(len(all_items),101);self.assertEqual(len({i['evidence']['block_index'] for i in all_items}),101)
        self.assertNotIn('PRIVATE BODY',json.dumps(all_items))
        with self.assertRaises(ValueError):self.view.blocks('codex',self.key(),seq)

    def test_readonly_all_routes_preserve_database(self):
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.view.clients();self.view.groups('codex');self.view.timeline('codex',self.key())
        with self.view.connect('codex') as db:
            with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM events')
        self.assertEqual(before,hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_missing_or_future_database_is_explicit_and_not_created(self):
        absent=Path(self.temp.name)/'absent.sqlite';v=HistoryView({'codex':absent})
        self.assertFalse(v.clients()['clients'][0]['available']);self.assertFalse(absent.exists())
        db=sqlite3.connect(self.path);db.execute('PRAGMA user_version=99');db.close()
        self.assertFalse(self.view.clients()['clients'][0]['available'])

    def test_query_budget_terminates_expensive_queries(self):
        v=HistoryView({'codex':self.path},query_seconds=-1)
        with self.assertRaises(sqlite3.OperationalError):v.groups('codex')

    def test_bad_keys_and_page_limits(self):
        for key in ['abc',key_for(['file-a',2,'session','']),key_for(['file-a',True,'','',0]),'x'*8001]:
            with self.assertRaises(ValueError):key_parts(key)
        for fn in [lambda:self.view.groups('codex',limit=51),lambda:self.view.timeline('codex',self.key(),before=-1),lambda:self.view.blocks('codex',self.key(),1,limit=1000)]:
            with self.assertRaises(ValueError):fn()

    def test_only_allowlisted_evidence_is_returned(self):
        row=dict(kind='tool_result',body='SECRET',prompt='SECRET',output='SECRET',api_key='SECRET',result=dict(outcome='failed',output='SECRET'),blocks=[dict(kind='text_record_observed',body='SECRET')],relationships=[dict(kind='spawned_from',private_path='SECRET')])
        self.assertNotIn('SECRET',json.dumps(present(row,1)))

    def test_actual_history_writers_feed_all_three_client_views(self):
        from launcher import core_path
        sys.path.insert(0,str(core_path()))
        from yukio.activity_history import ActivityHistory
        cases = {
            'codex': [dict(type='session_meta',payload=dict(id='demo-real-parser')),dict(type='response_item',payload=dict(type='function_call',call_id='call',name='Read')),dict(type='response_item',payload=dict(type='function_call_output',call_id='call',output=dict(exit_code=0)))],
            'claude': [dict(type='assistant',sessionId='demo-real-parser',uuid='request',message=dict(role='assistant',content=[dict(type='tool_use',id='call',name='Read')])),dict(type='user',sessionId='demo-real-parser',message=dict(role='user',content=[dict(type='tool_result',tool_use_id='call',is_error=True,content='PRIVATE RESULT')]))],
            'deepcode': [dict(role='assistant',sessionId='demo-real-parser',id='request',messageParams=dict(tool_calls=[dict(id='call',type='function',function=dict(name='Read',arguments='PRIVATE ARGS'))])),dict(role='tool',sessionId='demo-real-parser',messageParams=dict(tool_call_id='call'),content=json.dumps(dict(ok=True)))],
        }
        for client, lines in cases.items():
            with self.subTest(client=client):
                source=Path(self.temp.name)/(client+'.jsonl');source.write_text(''.join(json.dumps(r)+'\n' for r in lines))
                dbpath=Path(self.temp.name)/(client+'.sqlite');history=ActivityHistory(dbpath)
                history.ingest(source,source_format=client);history.close()
                reader=HistoryView({client:dbpath});group=reader.groups(client)['groups'][0]
                data=reader.timeline(client,group['key']);self.assertEqual(len(data['items']),len(lines))
                serialized=json.dumps(data);self.assertNotIn('PRIVATE',serialized)
                self.assertIn('工具回执报告',json.dumps(data,ensure_ascii=False))

    def test_receipts_unknown_conflicts_and_end_are_not_task_completion(self):
        for outcome in ('succeeded','failed','cancelled','unknown'):
            value=describe(dict(kind='tool_result',outcome=outcome,projection_eligible=False))
            self.assertIn('对应关系尚不可靠',value['note'])
            self.assertIn('不表示整个任务已完成',value['note'])
        self.assertEqual(describe(dict(kind='tool_result',outcome='succeeded',conflicting_results=True))['title'],'结果标记有冲突')
        self.assertIn('不能据此确认',describe(dict(kind='turn_ended'))['note'])
        self.assertEqual(describe(dict(kind='text_record_observed',evidence_class='self_report'))['evidence_label'],'助手自述标记')

    def test_http_guards_and_private_data_not_static(self):
        server=create_server(0,{'codex':self.path},synthetic=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        port=server.server_port
        def get(path,headers=None,method='GET'):
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3);conn.request(method,path,headers=headers or {});r=conn.getresponse();result=(r.status,dict(r.getheaders()),r.read());conn.close();return result
        try:
            for path in ('/','/app.js','/style.css'):
                status,headers,_=get(path);self.assertEqual(status,200);self.assertEqual(headers['Cache-Control'],'no-store')
                self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            self.assertEqual(get('/api/clients')[0],403)
            good={'X-Yukio-Workbench':'1'}
            # A link may open the public page shell; cross-site data reads stay blocked.
            self.assertEqual(get('/', {'Sec-Fetch-Site':'cross-site'})[0],200)
            result=get('/api/clients',good);self.assertEqual(result[0],200);self.assertEqual(json.loads(result[2])['mode'],'synthetic')
            for headers in [dict(good,Host='example.com'),dict(good,Origin='https://evil.test'),dict(good,**{'Sec-Fetch-Site':'cross-site'})]:
                self.assertEqual(get('/api/clients',headers)[0],403)
            for path in ['/history.sqlite','/../history_view.py','/api/nope']:
                self.assertEqual(get(path,good)[0],404)
            for query in ['client=codex&client=claude','client=codex&offset=-1','client=codex&path=private','client=codex&archive=wat']:
                self.assertEqual(get('/api/groups?'+query,good)[0],400)
            self.assertEqual(get('/api/clients',good,method='POST')[0],404)
            status,_,body=get('/api/timeline?'+urlencode(dict(client='codex',key=self.key())),good)
            self.assertEqual(status,200);self.assertNotIn(str(self.path).encode(),body)
            self.assertEqual(json.loads(body)['items'][0]['title'],'工具回执报告成功')
        finally:server.shutdown();server.server_close();thread.join()


if __name__ == '__main__': unittest.main()
