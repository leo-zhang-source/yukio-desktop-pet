import json
import http.client
import threading
import unittest
from contextlib import contextmanager
from urllib.parse import urlencode

import test_glance
from explanation import ExplanationError, ExplanationService, encode, validate_output, output_system
from glance_automation import GlanceAutomation
from history_review import HistoryReview
from reading_view import ReadingView
from test_explanation import config
from server import create_server


def speech(text,role='assistant',phase='commentary'):
    return dict(type='response_item',payload=dict(type='message',role=role,phase=phase,
                content=[dict(type='input_text' if role=='user' else 'output_text',text=text)]))


class HistoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.fx=test_glance.GlanceTests();self.fx.setUp();self.view=HistoryReview(self.fx.glance)

    def tearDown(self):self.fx.tearDown()

    def prepare(self,section='overview',**kwargs):return self.view.prepared('codex',self.fx.key,section,**kwargs)

    def append(self,*rows):self.fx.rows.extend(rows);self.fx.write();self.fx.ingest()

    def test_overview_spans_early_middle_and_recent_public_work_without_hidden_reasoning(self):
        self.append(*[speech('第'+str(i)+'阶段：检查阅读顺序，并保留用户确认的依据。') for i in range(80)],
                    speech('HIDDEN_REASONING_NOT_PUBLIC',phase='analysis'),speech('接下来请检查折叠交互。',role='user'))
        data,payload,refs=self.prepare()
        raw=encode(payload)
        for marker in ['让我一眼看懂','第0阶段','第40阶段','第79阶段','检查折叠交互']:self.assertIn(marker,raw)
        self.assertNotIn('HIDDEN_REASONING_NOT_PUBLIC',raw)
        self.assertEqual([p['part'] for p in data['parts']],['goal','before','now','next'])
        self.assertFalse(data['coverage']['sampled']);self.assertNotIn('local',data)
        self.assertIn('Never paste code',output_system(payload))

    def test_long_history_labels_sampling_and_preserves_endpoints(self):
        self.append(*[speech('进展片段 '+str(i)) for i in range(190)])
        data,payload,_=self.prepare()
        self.assertTrue(data['coverage']['sampled']);self.assertEqual(data['coverage']['selected'],160)
        self.assertIn('不代表完整步骤',data['note'])
        self.assertIn('让我一眼看懂',encode(payload));self.assertIn('进展片段 189',encode(payload))

    def test_whole_chat_read_uses_bounded_database_work(self):
        self.append(*[speech('较长历史的公开进展 '+str(i)) for i in range(200)])
        connect=self.fx.history.connect;queries=[]
        @contextmanager
        def traced(client):
            with connect(client) as db:
                db.set_trace_callback(queries.append)
                yield db
        self.fx.history.connect=traced
        items,coverage,_=self.view.public_history('codex',self.fx.key)
        self.assertEqual(coverage['selected'],160);self.assertTrue(items)
        # The read budget must be independent of the number of excerpts, rather
        # than restarting a database scan for each selected historical message.
        self.assertLessEqual(len([q for q in queries if q.startswith('SELECT')]),4)

    def test_steps_keep_matching_tool_receipt_and_public_report_separate(self):
        self.append(dict(type='response_item',payload=dict(type='function_call_output',call_id='other',output='FOREIGN_RESULT')),
                    dict(type='response_item',payload=dict(type='function_call_output',call_id='c',output='Process exited with code 1\nMATCHED_RESULT')),
                    speech('助手汇报：下一步需要核对文件。'))
        data,payload,refs=self.prepare('steps')
        self.assertNotIn('FOREIGN_RESULT',encode(payload));self.assertIn('MATCHED_RESULT',encode(payload))
        op=next(i for i in data['items'] if i['kind']=='operation')
        self.assertEqual(op['tool'],'Read');self.assertEqual(op['status'],'结果仍不明确')
        self.assertTrue(any(i['kind']=='report' for i in data['items']))

    def test_frozen_pagination_does_not_mix_newer_records_or_drop_previous_steps(self):
        self.append(*[speech('历史步骤 '+str(i)) for i in range(15)])
        first,_,_=self.prepare('steps');self.assertTrue(first['has_more'])
        self.append(speech('NEW_AFTER_SNAPSHOT'))
        older,payload,_=self.prepare('steps',snapshot=first['snapshot'],before=first['next_before'])
        self.assertNotIn('NEW_AFTER_SNAPSHOT',encode(payload))
        self.assertLess(max(i['sequence'] for i in older['items']),min(i['sequence'] for i in first['items']))
        self.assertEqual(first['snapshot'],older['snapshot'])

    def test_missing_source_yields_no_fake_recaps(self):
        self.fx.path.unlink()
        data,payload,_=self.prepare()
        self.assertTrue(data['coverage']['missing']);self.assertNotIn('local',data)
        self.assertIn('暂时读不到',data['note'])

    def test_prose_validation_rejects_code_and_long_verbatim_source(self):
        _,payload,_=self.prepare()
        def answer(text):return encode(dict(explanations=[dict(part=p['part'],text=text,basis='unknown',evidence_ids=p['required']) for p in payload['scope']['reading_parts']]))
        self.assertEqual(len(validate_output(answer('助手汇报正在梳理工作台的阅读顺序，完整效果仍需验证。'),payload)),4)
        for text in ['运行 python check.py 就能检查。','```const result = 1```']:
            with self.assertRaises(ExplanationError):validate_output(answer(text),payload)
        payload['facts'][0]['excerpt']='这是一段从记录复制的说明文字。'*5
        with self.assertRaises(ExplanationError):validate_output(answer(payload['facts'][0]['excerpt']),payload)

    def test_page_grant_scope_fresh_generation_and_revocation(self):
        sent=[];now=[0.]
        def sender(cfg,payload):
            sent.append(payload)
            return [dict(part=p['part'],text='助手汇报已调整阅读顺序，实际效果仍需用户验证。',basis='inference',evidence_ids=p['required']) for p in payload['scope']['reading_parts']]
        service=ExplanationService(config(),sender=sender,clock=lambda:now[0])
        auto=GlanceAutomation(self.fx.glance,service,clock=lambda:now[0],page_allowed=lambda:True)
        _,payload,refs=self.fx.glance.prepared('codex',self.fx.key)
        preview=service.preview_prepared(dict(client='codex',key=self.fx.key),payload,refs)
        grant=auto.authorize(preview['token'],True,page_owned=True)['grant'];reading=ReadingView(self.fx.glance,service,auto)
        first=reading.review(grant);second=reading.review(grant)
        self.assertNotEqual(first['token'],second['token'])
        self.assertFalse(sent);reading.explain(grant,first['token']);self.assertEqual(len(sent),1)
        focused=reading.review(grant,part='before');self.assertEqual([p['part'] for p in focused['parts']],['before'])
        with self.assertRaises(ValueError):reading.review(grant,part='foreign')
        auto.revoke(grant)
        with self.assertRaises(ExplanationError):reading.explain(grant,focused['token'])
        self.assertEqual(len(sent),1)

    def test_http_review_is_local_read_only_and_model_prepare_requires_a_grant(self):
        server=create_server(0,{'codex':self.fx.db},synthetic=True,source_roots={'codex':self.fx.sources},model_config=config())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            client=http.client.HTTPConnection('127.0.0.1',server.server_port)
            query=urlencode(dict(client='codex',key=self.fx.key,section='overview'))
            client.request('GET','/api/history-review?'+query,headers={'X-Yukio-Workbench':'1'})
            response=client.getresponse();data=json.loads(response.read())
            self.assertEqual(response.status,200);self.assertEqual(len(data['parts']),4);self.assertNotIn('token',data)
            client.request('GET','/api/history-review?'+query,headers={'X-Yukio-Workbench':'1','Origin':'https://other.example'})
            response=client.getresponse();response.read();self.assertEqual(response.status,403)
            client.request('POST','/api/reading-review',body=json.dumps(dict(grant='unknown',section='overview')),headers={'X-Yukio-Workbench':'1','Content-Type':'application/json'})
            response=client.getresponse();response.read();self.assertEqual(response.status,409)
            client.close()
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
