import json
from pathlib import Path
import tempfile
import unittest
from explanation import ExplanationService,ExplanationError
from glance_automation import GlanceAutomation
from page_explanation_policy import enabled
from test_explanation import config
import test_glance


class PagePolicyTests(unittest.TestCase):
    def test_opt_in_is_local_and_bound_to_the_recipient_and_excerpt_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'page-explanation-policy.json';cfg=config()
            self.assertFalse(enabled(folder,cfg))
            value=dict(version=1,automatic_on_open=True,scope='selected_chat_short_excerpts',destination=cfg['base_url'])
            path.write_text(json.dumps(value));self.assertTrue(enabled(folder,cfg))
            for change in [dict(destination='http://127.0.0.2:1234/v1'),dict(automatic_on_open=False),dict(scope='all_files'),dict(version=99)]:
                path.write_text(json.dumps(dict(value,**change)));self.assertFalse(enabled(folder,cfg))
            for text in ('broken','x'*2049):path.write_text(text);self.assertFalse(enabled(folder,cfg))


class PageAutomationTests(unittest.TestCase):
    def setUp(self):
        self.fx=test_glance.GlanceTests();self.fx.setUp();self.now=[0.];self.allowed=[True];self.sent=[]
        cfg=dict(config(),max_calls_per_hour=20)
        self.service=ExplanationService(cfg,clock=lambda:self.now[0],sender=lambda c,p:self.sent.append(p) or test_glance.result(p))
        self.auto=GlanceAutomation(self.fx.glance,self.service,clock=lambda:self.now[0],page_allowed=lambda:self.allowed[0])
    def tearDown(self):self.fx.tearDown()
    def start(self):
        _,payload,refs=self.fx.glance.prepared('codex',self.fx.key)
        preview=self.service.preview_prepared(dict(client='codex',key=self.fx.key),payload,refs)
        return self.auto.authorize(preview['token'],True,page_owned=True)['grant']

    def test_page_mode_requires_the_local_policy_and_has_no_send_on_authorization(self):
        self.allowed[0]=False
        with self.assertRaises(ExplanationError):self.start()
        self.assertFalse(self.sent)

    def test_open_first_explanation_close_stops_further_calls(self):
        token=self.start();self.assertFalse(self.sent)
        self.assertEqual(self.auto.refresh(token,True)['result']['mode'],'model');self.assertEqual(len(self.sent),1)
        self.auto.revoke(token)
        with self.assertRaises(ExplanationError):self.auto.refresh(token,True)
        self.assertEqual(len(self.sent),1)

    def test_missing_close_notice_expires_without_a_model_call(self):
        token=self.start();self.now[0]=121
        with self.assertRaises(ExplanationError):self.auto.refresh(token,True)
        self.assertFalse(self.sent)

    def test_heartbeat_keeps_an_open_page_alive_beyond_two_hours(self):
        token=self.start()
        for stamp in range(100,7501,100):self.now[0]=stamp;self.assertTrue(self.auto.heartbeat(token)['alive'])
        self.assertEqual(self.auto.refresh(token,True)['result']['mode'],'model')
        self.assertEqual(len(self.sent),1)

    def test_unchanged_work_does_not_resend_and_changed_work_keeps_interval(self):
        token=self.start();self.auto.refresh(token,True)
        for stamp in (100,200):self.now[0]=stamp;self.auto.heartbeat(token)
        self.assertEqual(self.auto.refresh(token)['mode'],'unchanged');self.assertEqual(len(self.sent),1)
        self.fx.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我正在检查解释是否容易阅读。')])));self.fx.write();self.fx.ingest()
        self.now[0]=250;self.auto.heartbeat(token);self.assertEqual(self.auto.refresh(token)['mode'],'waiting')
        self.now[0]=350;self.auto.heartbeat(token);self.now[0]=381
        self.assertEqual(self.auto.refresh(token)['mode'],'updated');self.assertEqual(len(self.sent),2)

    def test_revoking_policy_stops_a_live_page(self):
        token=self.start();self.allowed[0]=False
        with self.assertRaises(ExplanationError):self.auto.heartbeat(token)
        with self.assertRaises(ExplanationError):self.auto.refresh(token,True)
        self.assertFalse(self.sent)

    def test_close_during_preparation_prevents_the_next_send(self):
        token=self.start();original=self.fx.glance.prepared
        def prepare(*args,**kwargs):
            data=original(*args,**kwargs);self.auto.revoke(token);return data
        self.fx.glance.prepared=prepare
        with self.assertRaises(ExplanationError):self.auto.refresh(token,True)
        self.assertFalse(self.sent)
