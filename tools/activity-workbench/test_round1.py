"""Regression cases for the Oct 31 findings. Synthetic inputs; no real accounts."""
import json
import unittest
from unittest.mock import patch

import agent_explanation as agent
from explanation import ExplanationError, ExplanationService
from test_explanation import answer, item, config
import test_glance
from context_view import ContextView
from work_understanding import WorkUnderstanding
from localization import language_context, localize


class RecipientTests(unittest.TestCase):
    def setUp(self):
        self.sent=[]
        self.service=ExplanationService(agent.configuration(None), sender=lambda c,p:self.sent.append(c) or answer(p))

    def test_preview_resolves_auto_before_consent_and_generate_never_switches(self):
        with patch.object(agent,'find_agent',side_effect=lambda p:[p]), patch.object(agent,'probe_agent',return_value={'state':'ready'}):
            preview=self.service.preview({'client':'claude'},item(),[])
            self.assertEqual(preview['recipient']['provider'],'claude')
            self.assertEqual(self.sent,[])
            # Even if Claude subsequently disappears and Codex is available, do not send to Codex.
            with patch.object(agent,'find_agent',side_effect=lambda p:['codex'] if p=='codex' else None):
                result=self.service.generate(preview['token'],True)
            self.assertEqual(result['reason'],'agent_not_found')
            self.assertEqual(self.sent,[])
            self.assertEqual(self.service.generate(preview['token'],True)['model'],'Claude Code')
        self.assertEqual([c['agent'] for c in self.sent],['claude'])

    def test_configuration_change_or_retirement_rejects_old_preview(self):
        for retired in (False,True):
            service=ExplanationService(config(),sender=lambda c,p:self.fail('must not send'))
            preview=service.preview('selected',item(),[])
            if retired:service.retired=True
            else:service.config['base_url']='http://127.0.0.1:9999/v1'
            with self.assertRaises(ExplanationError):service.generate(preview['token'],True)

    def test_unavailable_or_not_logged_in_cannot_create_sendable_preview(self):
        for reason in ('agent_login_required','agent_probe_timeout'):
            with patch.object(agent,'find_agent',return_value=['test']), patch.object(agent,'probe_agent',return_value=dict(state='unavailable',reason=reason)):
                with self.assertRaisesRegex(ExplanationError,reason):self.service.preview({'client':'codex'},item(),[])
        self.assertFalse(self.sent)
        self.assertFalse(self.service.entries)

    def test_lan_preview_identifies_address_and_model(self):
        service=ExplanationService(config(),sender=lambda c,p:self.fail('preview must not send'))
        preview=service.preview('selected',item(),[])
        self.assertEqual(preview['recipient'],dict(provider='lan',model='test-model',destination=config()['base_url']))

    def test_auto_grant_keeps_recipient_for_new_activity_and_reading(self):
        from glance_automation import GlanceAutomation
        from reading_view import ReadingView
        fx=test_glance.GlanceTests();fx.setUp()
        try:
            service=ExplanationService(agent.configuration(None),sender=lambda c,p:answer(p))
            auto=GlanceAutomation(fx.glance,service,page_allowed=lambda:True)
            with patch.object(agent,'find_agent',side_effect=lambda p:[p]), patch.object(agent,'probe_agent',return_value={'state':'ready'}):
                _,payload,refs=fx.glance.prepared('codex',fx.key)
                preview=service.preview_prepared(dict(client='codex',key=fx.key),payload,refs)
                grant=auto.authorize(preview['token'],True,page_owned=True)['grant']
            with patch.object(agent,'find_agent',side_effect=lambda p:['claude'] if p=='claude' else None):
                result=auto.refresh(grant,True)
                self.assertEqual(result['result']['reason'],'agent_not_found')
                token=ReadingView(fx.glance,service,auto).current(grant)['token']
                self.assertEqual(service.entries[token]['recipient']['provider'],'codex')
                self.assertEqual(service.generate(token,True)['reason'],'agent_not_found')
        finally:fx.tearDown()


class UnlinkedCommandTests(unittest.TestCase):
    def setUp(self):
        self.fx=test_glance.GlanceTests();self.fx.setUp()
        # The new CLI exposes an outer exec call and an independently identified command.
        self.fx.rows[-1]=dict(type='response_item',payload=dict(type='custom_tool_call',name='exec',call_id='outer',input='await tools.exec_command({cmd:"echo example"})'))
        self.fx.write();self.fx.ingest()
        self.fx.key=self.fx.history.groups('codex')['groups'][0]['key']
    def tearDown(self):self.fx.tearDown()
    def receipt(self,status='completed',exit_code=0,identity='nested'):
        self.fx.rows.extend([
            dict(type='event_msg',payload=dict(type='item_completed',thread_id='chat-one',turn_id='turn',item=dict(type='CommandExecution',id=identity,status=status,exit_code=exit_code,command=['echo','example']))),
            dict(type='response_item',payload=dict(type='custom_tool_call_output',call_id='outer',output='Script completed'))])
        self.fx.write();self.fx.ingest()

    def test_success_is_visible_without_promoting_outer_exec(self):
        self.receipt()
        data=self.fx.detail()
        self.assertEqual(data['results'][-1]['status'],'unknown')
        self.assertEqual(data['unlinked_results'][0]['status'],'succeeded')
        self.assertIn('不能据此判定外层步骤',data['unlinked_results'][0]['text'])
        _,payload,_=self.fx.glance.prepared('codex',self.fx.key)
        self.assertTrue(any(f['record_marker']=='未关联回执的独立结果' for f in payload['facts']))
        _,payload,_=WorkUnderstanding(self.fx.glance).prepared('codex',self.fx.key)
        self.assertIn('收到成功回执',json.dumps(payload,ensure_ascii=False))
        _,facts=ContextView(self.fx.history).explanation_context('codex',self.fx.key)
        self.assertTrue(any(f['title']=='未关联回执的独立结果' for f in facts))
        with language_context('en'):
            self.assertIn('Not yet linked',localize(data)['unlinked_results'][0]['text'])
        self.fx.ingest()
        self.assertEqual(self.fx.detail()['unlinked_results'],data['unlinked_results'])

    def test_failure_and_cancellation_stay_independent_when_commands_interleave(self):
        self.receipt('failed',2,'nested-a')
        self.receipt('cancelled',130,'nested-b')
        data=self.fx.detail()
        self.assertEqual([r['status'] for r in data['unlinked_results']],['failed','cancelled'])
        self.assertTrue(all(r['status']=='unknown' for r in data['results']))

    def test_foreign_chat_receipt_is_never_used(self):
        self.fx.rows.append(dict(type='event_msg',payload=dict(type='item_completed',thread_id='other-chat',turn_id='turn',item=dict(type='CommandExecution',id='foreign',exit_code=0))))
        self.fx.write();self.fx.ingest()
        self.assertFalse(self.fx.detail()['unlinked_results'])


if __name__=='__main__':unittest.main()
