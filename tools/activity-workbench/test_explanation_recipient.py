"""Regression cases for the Oct 31 findings. Synthetic inputs; no real accounts."""
import json
import unittest
from unittest.mock import patch

import agent_explanation as agent
from explanation import ExplanationError, ExplanationService
from test_explanation import answer, item, config
import test_glance


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
            self.assertEqual(self.service.generate(preview['token'],True)['model'],agent.LABELS['claude'])
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


