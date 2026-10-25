import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from explanation import (ExplanationError, ExplanationService, call_model, encode,
                         load_config, prepare, validate_output)
from history_view import HistoryView, key_for, present
from server import create_server
from test_workbench import fixture


def config(url='http://127.0.0.1:1234/v1'):
    return dict(base_url=url,model='test-model',timeout_seconds=1,max_tokens=300,max_calls_per_hour=2,cooldown_seconds=1)


def item():
    return present(dict(kind='tool_result',event_id='PRIVATE-ID',source_id='PRIVATE-FILE',session_id='PRIVATE-CHAT',
                        tool_name='PRIVATE-TOOL',timestamp_ms=12345,source_record_sha256='PRIVATE-HASH',
                        result=dict(outcome='failed',call_outcome='failed',projection_eligible=True)),1)


def answer(payload):
    return [dict(evidence_id=f['evidence_id'],text='模拟说明：'+f['record_marker']) for f in payload['facts']]


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'history.sqlite';fixture(self.path)
        self.view=HistoryView({'codex':self.path,'claude':self.path})
        self.now=100.;self.sent=[]
        self.service=ExplanationService(config(),sender=lambda c,p:self.sent.append(p) or answer(p),clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def preview(self,selection='one'):
        return self.service.preview(selection,item(),[])

    def test_config_accepts_explicit_lan_without_keys(self):
        path=self.root/'config.json';path.write_text(encode(dict(config(),large_model='reserved-never-used')))
        loaded=load_config(path);self.assertNotIn('large_model',loaded)
        for url in ['http://example.test/v1','http://8.8.8.8/v1','http://169.254.169.254/v1','http://u:p@127.0.0.1/v1','http://127.0.0.1/v1?key=x']:
            path.write_text(encode(dict(config(),base_url=url)))
            with self.assertRaises(ValueError):load_config(path)
        path.write_text(encode(dict(config(),api_key='SECRET')))
        with self.assertRaises(ValueError):load_config(path)

    def test_payload_contains_no_private_identifiers_or_tool_names(self):
        payload,refs=prepare(item(),[])
        self.assertNotIn('PRIVATE',encode(payload));self.assertNotIn('timestamp',encode(payload))
        self.assertEqual(refs[0]['record_id'],'PRIVATE-ID')
        self.assertEqual(payload['scope']['whole_task_status'],'unknown')

    def test_block_limit_and_self_report_are_explicit(self):
        blocks=[dict(kind='text_record_observed',evidence_class='self_report',evidence_id='PRIVATE-'+str(i),body='SECRET') for i in range(20)]
        payload,_=prepare(present(dict(kind='message_observed',event_id='PRIVATE',blocks=blocks),2),[])
        self.assertEqual(payload['scope']['blocks_in_record'],20)
        self.assertEqual(payload['scope']['blocks_included'],3)
        self.assertEqual(payload['facts'][1]['evidence_class'],'self_report')
        self.assertNotIn('SECRET',encode(payload));self.assertNotIn('PRIVATE',encode(payload))

    def test_preview_is_frozen_and_does_not_call_model(self):
        preview=self.preview();self.assertEqual(self.sent,[])
        result=self.service.generate(preview['token'],True)
        self.assertEqual(result['mode'],'model');self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0],preview['payload'])

    def test_gap_and_identity_limits_survive_minimization(self):
        observed=item();observed['evidence']['after_gap_evidence_id']='PRIVATE-GAP';observed['identity_issues']=['PRIVATE-ISSUE']
        payload,_=prepare(observed,[])
        self.assertIn('不能当作完整历史',payload['facts'][0]['boundary'])
        self.assertIn('归属不能完全确认',payload['facts'][0]['boundary'])
        self.assertNotIn('PRIVATE',encode(payload))

    def test_no_send_without_confirmation_or_with_unknown_token(self):
        p=self.preview()
        for token,consent in [(p['token'],False),(p['token'],'true'),('invalid',True)]:
            with self.assertRaises(ExplanationError):self.service.generate(token,consent)
        self.assertEqual(self.sent,[])

    def test_duplicate_click_and_preview_reuse_do_not_repeat_calls(self):
        p=self.preview();self.service.generate(p['token'],True)
        second=self.preview();self.assertEqual(p['token'],second['token']);self.assertTrue(second['cached'])
        self.assertTrue(self.service.generate(second['token'],True)['cached']);self.assertEqual(len(self.sent),1)

    def test_different_records_do_not_share_explanation_cache(self):
        p=self.preview('first');q=self.preview('second');self.assertNotEqual(p['token'],q['token'])
        self.service.generate(p['token'],True);self.now+=2;self.service.generate(q['token'],True)
        self.assertEqual(len(self.sent),2)

    def test_rate_and_expiration_and_memory_limit(self):
        p=self.preview();self.service.generate(p['token'],True)
        q=self.preview('two')
        with self.assertRaisesRegex(ExplanationError,'rate_limited'):self.service.generate(q['token'],True)
        self.now+=2;self.service.generate(q['token'],True);self.now+=2
        with self.assertRaisesRegex(ExplanationError,'rate_limited'):self.service.generate(self.preview('three')['token'],True)
        self.now+=301
        with self.assertRaisesRegex(ExplanationError,'preview_expired'):self.service.generate(q['token'],True)
        for i in range(100):self.preview(str(i))
        self.assertEqual(len(self.service.entries),64)

    def test_concurrent_calls_are_not_duplicated(self):
        entered=threading.Event();release=threading.Event()
        def sender(c,p):entered.set();release.wait(2);return answer(p)
        service=ExplanationService(config(),sender=sender)
        preview=service.preview('one',item(),[])
        t=threading.Thread(target=lambda:service.generate(preview['token'],True));t.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(ExplanationError,'busy'):service.generate(preview['token'],True)
        release.set();t.join();self.assertTrue(service.generate(preview['token'],True)['cached'])

    def test_bad_references_schema_and_text_are_rejected(self):
        payload,_=prepare(item(),[])
        for data in [dict(explanations=[dict(evidence_id='E99',text='bad')]),dict(explanations=[]),
                     dict(explanations=[dict(evidence_id='E1',text='x'*241)]),dict(explanations=answer(payload),extra='no'),
                     dict(explanations=answer(payload)*2)]:
            with self.assertRaises(ExplanationError):validate_output(encode(data),payload)

    def test_transport_failure_falls_back_and_is_cached(self):
        def failure(c,p):raise ExplanationError('service_unavailable')
        self.service.sender=failure;p=self.preview();result=self.service.generate(p['token'],True)
        self.assertEqual(result['mode'],'fallback');self.assertIn('工具回执报告失败',result['explanations'][0]['text'])
        self.assertTrue(self.service.generate(p['token'],True)['cached'])

    def test_preview_selects_exact_record_not_another_chat_or_future_gap(self):
        key=key_for(['file-a',2,'demo-chat-a','',0])
        before,warnings=self.view.explanation_record('codex',key,2);self.assertEqual(warnings,[])
        last=self.view.timeline('codex',key)['items'][0]['evidence']['sequence']
        _,warnings=self.view.explanation_record('codex',key,last);self.assertEqual(warnings[0]['evidence']['kind'],'observation_gap')
        with self.assertRaises(ValueError):self.view.explanation_record('codex',key_for(['file-a',2,'other','',0]),last)

    def test_http_preview_confirmation_origin_and_payload_tamper_guards(self):
        server=create_server(0,{'codex':self.path},explanation_service=self.service)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        def post(path,data,headers=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            h={'Content-Type':'application/json','X-Yukio-Workbench':'1'};h.update(headers or {})
            c.request('POST',path,encode(data).encode(),h);r=c.getresponse();body=r.read();status=r.status;c.close();return status,body
        try:
            selection=dict(client='codex',key=key_for(['file-a',2,'demo-chat-a','',0]),sequence=2)
            status,body=post('/api/explanation-preview',selection);self.assertEqual(status,200);p=json.loads(body);self.assertEqual(self.sent,[])
            self.assertEqual(post('/api/explanation-generate',dict(token=p['token'],consent=False))[0],409)
            for headers in [{'Origin':'https://evil.test'},{'Sec-Fetch-Site':'cross-site'},{'Host':'evil.test'},{'X-Yukio-Workbench':'0'}]:
                self.assertEqual(post('/api/explanation-generate',dict(token=p['token'],consent=True),headers)[0],403)
            self.assertEqual(post('/api/explanation-generate',dict(token=p['token'],consent=True,payload='tampered'))[0],400)
            self.assertEqual(post('/api/explanation-generate',dict(token=p['token'],consent=True))[0],200)
            self.assertEqual(len(self.sent),1)
        finally:server.shutdown();server.server_close();t.join()

    def test_real_http_transport_validation_without_external_services(self):
        scenario={'mode':'ok','requests':[]}
        payload,_=prepare(item(),[])
        class Mock(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                scenario['requests'].append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                mode=scenario['mode']
                if mode=='timeout':time.sleep(1.2);return
                if mode=='redirect':
                    self.send_response(307);self.send_header('Location','http://127.0.0.1:1/should-not-follow');self.end_headers();return
                if mode=='404':self.send_response(404);self.end_headers();self.wfile.write(b'SECRET ERROR');return
                if mode=='large':raw=b'x'*65537
                elif mode=='bad-json':raw=b'bad'
                else:
                    raw=encode(dict(model='other' if mode=='model' else 'test-model',choices=[dict(finish_reason='length' if mode=='length' else 'stop',message=dict(content=encode(dict(explanations=answer(payload))),reasoning='DO NOT DISPLAY'))])).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Mock);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        cfg=config('http://127.0.0.1:%d/v1'%server.server_port)
        try:
            self.assertEqual(call_model(cfg,payload),answer(payload))
            request=scenario['requests'][0];self.assertEqual(json.loads(request['messages'][1]['content']),payload)
            self.assertNotIn('PRIVATE',encode(request));self.assertNotIn('tools',request);self.assertEqual(request['reasoning_effort'],'none')
            for mode,code in [('redirect','redirect_blocked'),('404','model_unavailable'),('large','response_too_large'),('bad-json','invalid_response'),('model','unexpected_model'),('length','incomplete_response'),('timeout','service_unavailable')]:
                scenario['mode']=mode
                with self.assertRaisesRegex(ExplanationError,code):call_model(cfg,payload)
        finally:server.shutdown();server.server_close();t.join()


if __name__=='__main__':unittest.main()
