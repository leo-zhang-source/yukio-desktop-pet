import http.client
import json
import sqlite3
import threading
import unittest
from contextlib import closing
from unittest.mock import patch
from urllib.parse import urlencode

import test_glance
from explanation import ExplanationService, ExplanationError, encode, validate_output, output_system
from glance_automation import GlanceAutomation
from localization import language_context, localize
from reading_view import ReadingView
from server import create_server
from test_explanation import config
from work_understanding import WorkUnderstanding, MAX_PROJECT_CHATS


class WorkUnderstandingTests(unittest.TestCase):
    def setUp(self):
        self.fx = test_glance.GlanceTests(); self.fx.setUp()
        self.view = WorkUnderstanding(self.fx.glance)
        self.now = [0.]; self.sent = []
        def sender(cfg, payload):
            self.sent.append(payload)
            return [dict(part=p['part'], text='助手汇报检查了工作台的阅读顺序，实际效果仍需用户验证。',
                         basis='inference', evidence_ids=p['required']) for p in payload['scope']['reading_parts']]
        self.service = ExplanationService(config(), sender=sender, clock=lambda:self.now[0])
        self.auto = GlanceAutomation(self.fx.glance, self.service, clock=lambda:self.now[0], page_allowed=lambda:True)
        _, payload, refs = self.fx.glance.prepared('codex', self.fx.key)
        token = self.service.preview_prepared(dict(client='codex', key=self.fx.key), payload, refs)['token']
        self.grant = self.auto.authorize(token, True, page_owned=True)['grant']
        self.reading = ReadingView(self.fx.glance, self.service, self.auto)

    def tearDown(self): self.fx.tearDown()

    def prepare(self, scope='chat'): return self.view.prepared('codex', self.fx.key, scope)

    def test_local_work_story_uses_readable_requests_and_keeps_technical_proof_separate(self):
        self.fx.rows[2]['payload']['content'][0]['text']='<system-reminder>Internal workspace note.</system-reminder>\n请修复首页 `/tmp/private/main.py` 的聊天选择。'
        self.fx.rows += [dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='<task-notification><summary>Internal event</summary></task-notification>')]))]
        self.fx.write();self.fx.ingest()
        self.fx.key=self.fx.history.groups('codex')['groups'][0]['key']
        data,payload,refs=self.prepare()
        story=data['local']['goal']['text']
        self.assertIn('聊天选择',story)
        for marker in ('system-reminder','task-notification','Internal','/tmp','main.py','`'):
            self.assertNotIn(marker,story)
        self.assertIn('main.py',encode(refs));self.assertNotIn('Internal',encode(payload))

    def add_project(self, count=2):
        """Real transcript parsing and project lookup, with constructed inputs."""
        state = self.fx.root/'state_5.sqlite'
        with closing(sqlite3.connect(state)) as db, db:
            db.execute('CREATE TABLE threads(id TEXT,cwd TEXT,rollout_path TEXT,title TEXT)')
            db.executescript('CREATE TABLE projects(id TEXT,name TEXT); CREATE TABLE project_roots(project_id TEXT,path TEXT);')
            db.execute('INSERT INTO projects VALUES(?,?)',('project-one','页面项目'))
            db.execute('INSERT INTO project_roots VALUES(?,?)',('project-one','/demo/one/app'))
            db.execute('INSERT INTO threads VALUES(?,?,?,?)', ('chat-one','/demo/one/app',str(self.fx.path),'简化雪绪首页'))
            for i in range(count-1):
                session = 'other-'+str(i); path = self.fx.sources/(session+'.jsonl')
                rows = [dict(type='session_meta',payload=dict(id=session,cwd='/demo/one/app')),
                        dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='检查同项目的第'+str(i)+'个阅读流程。')])),
                        dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我先检查阅读流程，再请用户复述目标。')])),
                        dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='助手汇报布局已经调整，真实理解效果仍未验证。')]))]
                path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
                from yukio.activity_history import ActivityHistory
                store = ActivityHistory(self.fx.db)
                try: store.ingest(path)
                finally: store.close()
                db.execute('INSERT INTO threads VALUES(?,?,?,?)', (session,'/demo/one/app',str(path),'检查阅读流程'+str(i)))
        return state

    def test_chat_preserves_original_goal_latest_correction_and_earlier_approach(self):
        self.fx.rows += [dict(type='response_item',payload=dict(type='message',role='assistant',phase='analysis',content=[dict(type='output_text',text='HIDDEN_PRIVATE_REASONING')])),
                        dict(type='event_msg',payload=dict(type='task_complete',turn_id='turn')),
                        dict(type='event_msg',payload=dict(type='task_started',turn_id='next')),
                        dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='保留详细依据，但合并最近活动。')])),
                        dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我会把最近活动收在一起，再说明目标和方法。')]))]
        self.fx.write(); self.fx.ingest()
        data, payload, _ = self.prepare()
        raw = encode(payload)
        for text in ('让我一眼看懂','保留详细依据','先查看入口','把最近活动收在一起'):
            self.assertIn(text, raw)
        self.assertNotIn('HIDDEN_PRIVATE_REASONING', raw)
        self.assertEqual(set(data['local']), {'goal','strategy','effectiveness'})
        self.assertEqual(data['effectiveness_status'], '尚待验证')
        self.assertFalse(self.sent)

    def test_results_keep_operation_scope_and_cannot_establish_effectiveness(self):
        self.fx.rows.append(dict(type='response_item',payload=dict(type='function_call_output',call_id='c',output='Process exited with code 1\ncheck failed')))
        self.fx.write(); self.fx.ingest()
        data, payload, _ = self.prepare()
        self.assertIn('失败', encode(payload))
        self.assertIn('不能证明方法达到了目标', data['local']['effectiveness']['text'])
        self.assertEqual(payload['scope']['whole_task_status'], 'unknown')
        parts=payload['scope']['reading_parts']
        values=[dict(part=p['part'],text='助手汇报检查了首页，仍需按目标验证效果。',basis='inference',evidence_ids=p['required']) for p in parts]
        self.assertEqual(len(validate_output(encode(dict(explanations=values)),payload)),3)
        values[-1]['text']='这种方法已证明完全有效，目标已经实现。'
        with self.assertRaises(ExplanationError): validate_output(encode(dict(explanations=values)),payload)
        values[-1]['text']='方法有效率为99%，仍需进一步验证。'
        with self.assertRaises(ExplanationError): validate_output(encode(dict(explanations=values)),payload)

    def test_project_uses_real_membership_and_never_joins_same_named_folders(self):
        state = self.add_project(3)
        with closing(sqlite3.connect(state)) as db, db:
            db.execute("UPDATE threads SET cwd='/demo/unrelated/app' WHERE id='other-1'")
        data, payload, refs = self.prepare('project')
        self.assertEqual(data['included_chats'],2)
        self.assertNotIn('第1个阅读流程',encode(payload))
        self.assertIn('第0个阅读流程',encode(payload))
        self.assertEqual(len({r['chat'] for r in refs if r['chat']}),2)
        self.assertEqual(len(payload['scope']['reading_parts'][0]['required']),2)
        self.assertEqual(len(payload['scope']['reading_parts'][2]['required']),3)
        self.assertNotIn('/demo/',encode(payload))

    def test_project_limit_and_changing_membership_remain_explicit(self):
        self.add_project(9)
        data, payload, _ = self.prepare('project')
        self.assertEqual(data['included_chats'],MAX_PROJECT_CHATS)
        self.assertEqual(data['known_chats'],9)
        self.assertTrue(data['limited'])
        self.assertTrue(all(len(p['required'])<=8 for p in payload['scope']['reading_parts']))
        self.assertLess(len(encode(payload)),30000)
        original = self.fx.glance.detail
        def moved(client,key):
            result=original(client,key)
            if key!=self.fx.key:result['project']=dict(id='moved',name='Same name')
            return result
        with patch.object(self.fx.glance,'detail',side_effect=moved):
            changed=self.prepare('project')[0]
        self.assertEqual(changed['included_chats'],1)
        self.assertEqual(changed['unavailable'],MAX_PROJECT_CHATS-1)

    def test_unavailable_source_and_unknown_project_never_broaden_scope(self):
        with self.assertRaises(ValueError): self.prepare('project')
        with self.assertRaises(ValueError): self.prepare('all')
        self.fx.path.unlink()
        data,payload,_=self.prepare()
        self.assertFalse(data['local']['goal']['evidence_ids'])
        self.assertEqual(data['local']['goal']['basis'],'unknown')
        self.assertTrue(data['chats'][0]['source_unavailable'])
        self.assertNotIn('简化首页，让我',encode(payload))

    def test_frozen_project_is_explicit_reading_and_uses_shared_budget(self):
        self.add_project()
        prepared=self.reading.work(self.grant,'project')
        self.assertFalse(self.sent)
        self.assertEqual(self.service.entries[prepared['token']]['payload']['scope']['work_scope'],'project')
        result=self.reading.explain(self.grant,prepared['token'])
        self.assertEqual(result['result']['mode'],'model');self.assertEqual(len(self.sent),1)
        self.reading.explain(self.grant,prepared['token']);self.assertEqual(len(self.sent),1)
        self.assertEqual(len(self.service.calls),1)
        self.auto.revoke(self.grant)
        with self.assertRaises(ExplanationError):self.reading.explain(self.grant,prepared['token'])

    def test_revoked_page_during_project_preparation_cannot_send(self):
        self.add_project()
        original=self.fx.glance.cards
        def close():
            self.auto.revoke(self.grant)
            return original()
        with patch.object(self.fx.glance,'cards',side_effect=close):
            with self.assertRaises(ExplanationError):self.reading.work(self.grant,'project')
        self.assertFalse(self.sent)

    def test_changed_goals_invalidate_reading_but_bookkeeping_does_not(self):
        before=self.prepare()[0]['revision']
        self.fx.rows.append(dict(type='event_msg',payload=dict(type='token_count',info={})))
        self.fx.write();self.fx.ingest()
        self.assertEqual(before,self.prepare()[0]['revision'])
        self.fx.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='改为优先展示整个项目的目标。')])))
        self.fx.write();self.fx.ingest()
        self.assertNotEqual(before,self.prepare()[0]['revision'])

    def test_english_local_summary_and_model_contract(self):
        with language_context('en'):
            data,payload,_=self.prepare()
            localized=localize(data)
            for value in localized['local'].values():self.assertNotRegex(value['text'],r'[\u3400-\u9fff]')
            self.assertIn('same-project',output_system(payload).lower())
            self.assertIn('Never invent a score',output_system(payload))

    def test_http_local_read_does_not_require_or_call_model(self):
        server=create_server(0,{'codex':self.fx.db},synthetic=True,explanation_service=self.service,source_roots={'codex':self.fx.sources})
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            headers={'X-Yukio-Workbench':'1'}
            with closing(http.client.HTTPConnection('127.0.0.1',server.server_port)) as connection:
                connection.request('GET','/api/work-understanding?'+urlencode(dict(client='codex',key=self.fx.key,scope='chat')),headers=headers)
                response=connection.getresponse();data=json.loads(response.read())
                self.assertEqual(response.status,200);self.assertEqual(data['scope'],'chat')
                connection.request('GET','/api/reading-history?'+urlencode(dict(client='codex',key=self.fx.key)),headers=headers)
                response=connection.getresponse();history=json.loads(response.read())
                self.assertEqual(response.status,200);self.assertIsNone(history['token'])
                self.assertTrue(history['cards'][0]['local'])
                connection.request('GET','/api/reading-history?'+urlencode(dict(client='codex',key=self.fx.key)))
                response=connection.getresponse();response.read();self.assertEqual(response.status,403)
                connection.request('POST','/api/reading-work',body=json.dumps(dict(grant='unapproved',scope='project')),headers=dict(headers,**{'Content-Type':'application/json'}))
                response=connection.getresponse();response.read();self.assertEqual(response.status,409)
            self.assertFalse(self.sent)
        finally:server.shutdown();server.server_close();thread.join(3)

    def test_each_work_detail_freezes_only_its_focus_and_enforces_evidence(self):
        self.add_project(3)
        for focus in ('goal','strategy','effectiveness'):
            with self.subTest(focus=focus):
                data=self.reading.work(self.grant,'project',focus)
                payload=self.service.entries[data['token']]['payload']
                self.assertEqual(payload['scope']['work_part'],focus)
                self.assertEqual(len(payload['scope']['reading_parts']),3)
                self.assertTrue(all(p['part'].startswith(focus+'_') for p in data['parts']))
                allowed=set(data['parts'][0]['allowed'])
                self.assertEqual({f['evidence_id'] for f in payload['facts']},allowed)
                self.assertEqual({r['evidence_id'] for r in self.service.entries[data['token']]['references']},allowed)
                self.assertIn(data['parts'][0]['part'],output_system(payload))
                values=[dict(part=p['part'],text='这些公开汇报仍需对应目标核验，实际效果未知。',basis='unknown',evidence_ids=p['required']) for p in data['parts']]
                self.assertEqual(len(validate_output(encode(dict(explanations=values)),payload)),3)
                values[0]['evidence_ids']=[]
                with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=values)),payload)
        self.assertFalse(self.sent)
        with self.assertRaises(ValueError):self.reading.work(self.grant,'chat','other')
        with self.assertRaises(ValueError):self.reading.work(self.grant,'chat',[])

    def test_detail_effectiveness_rejects_false_success_and_revocation_blocks_send(self):
        data=self.reading.work(self.grant,'chat','effectiveness')
        payload=self.service.entries[data['token']]['payload']
        values=[dict(part=p['part'],text='方法有效率99%，仍需检查。',basis='inference',evidence_ids=p['required']) for p in data['parts']]
        with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=values)),payload)
        self.auto.revoke(self.grant)
        with self.assertRaises(ExplanationError):self.reading.explain(self.grant,data['token'])
        self.assertFalse(self.sent)

    def test_local_details_keep_older_project_sources_and_english_reading_aids(self):
        self.add_project(3)
        data=self.prepare('project')[0]
        for focus,rows in data['details'].items():
            self.assertEqual(len(rows),3)
            refs=[r for r in data['references'] if r['evidence_id'] in rows[0]['evidence_ids']]
            self.assertEqual(len({r['chat'] for r in refs if r['chat']}),3)
        with language_context('en'):
            data=localize(self.prepare('project')[0])
            for rows in data['details'].values():
                for row in rows:
                    self.assertNotRegex(row['title']+row['text'],r'[\u3400-\u9fff]')


if __name__=='__main__':unittest.main()
