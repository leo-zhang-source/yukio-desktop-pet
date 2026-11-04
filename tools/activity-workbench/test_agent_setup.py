"""Onboarding never sends excerpts, shares account output, or changes grants."""
import http.client
import json
from pathlib import Path
import shlex
import tempfile
import threading
import unittest
from unittest.mock import patch

from agent_setup import AgentSetup
import agent_explanation as agent
from explanation import ExplanationService
from localization import language_context, localize
from server import create_server
from test_generic_agents import CLAUDE_HELP


class AgentSetupTests(unittest.TestCase):
    def test_inventory_does_not_launch_clients(self):
        with patch('agent_explanation.find_agent', side_effect=lambda p: ['local'] if p=='codex' else None), \
             patch('agent_explanation.probe_agent') as probe:
            self.assertEqual(AgentSetup().inventory()['agents'], [
                dict(provider='codex',state='not_checked'),dict(provider='claude',state='not_found')])
            probe.assert_not_called()

    def test_login_command_preserves_unicode_and_shell_metacharacters_in_both_languages(self):
        command=["/Users/安装 解释 ' $(touch BAD)/codex"]
        with patch('agent_explanation.find_agent',return_value=command), \
             patch('agent_explanation.probe_agent',return_value=dict(state='unavailable',reason='agent_login_required')):
            value=AgentSetup().check('codex')
        for lang in ('zh','en'):
            with language_context(lang):
                self.assertEqual(shlex.split(localize(value)['login_command']),command+['login'])

    def test_each_check_is_fresh_and_only_definite_logged_out_gets_a_command(self):
        for reason,state in [('agent_login_required','login_required'),('agent_incompatible','incompatible'),
                             ('agent_compatibility_timeout','compatibility_timeout'),
                             ('agent_login_check_timeout','login_check_timeout'),('PRIVATE RAW FAILURE','check_failed')]:
            with self.subTest(reason=reason),patch('agent_explanation.find_agent',return_value=['claude']), \
                 patch('agent_explanation.probe_agent',side_effect=[dict(state='unavailable',reason=reason),dict(state='ready')]):
                setup=AgentSetup();first=setup.check('claude');second=setup.check('claude')
                self.assertEqual(first['state'],state)
                self.assertEqual('login_command' in first,state=='login_required')
                self.assertEqual(second,dict(provider='claude',state='ready'))
                self.assertNotIn('PRIVATE',str(first))
        with patch('agent_explanation.find_agent',return_value=['claude']),patch('agent_explanation.probe_agent',return_value=dict(state='unknown')):
            self.assertEqual(AgentSetup().check('claude'),dict(provider='claude',state='unverified'))

    def test_duplicate_check_does_not_block_other_provider(self):
        entered=threading.Event();release=threading.Event();answers=[]
        def probe(provider,command):
            if provider=='codex':entered.set();release.wait(2)
            return dict(state='ready')
        with patch('agent_explanation.find_agent',return_value=['client']),patch('agent_explanation.probe_agent',side_effect=probe):
            setup=AgentSetup();thread=threading.Thread(target=lambda:answers.append(setup.check('codex')))
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(setup.check('codex')['state'],'checking')
                self.assertEqual(setup.check('claude')['state'],'ready')
            finally:release.set();thread.join(2)
            self.assertEqual(answers,[dict(provider='codex',state='ready')])

    def test_malformed_claude_status_never_claims_signed_in(self):
        for raw in [b'not json',b'{}',b'[]',b'{"loggedIn":"yes","email":"PRIVATE"}']:
            with patch.object(agent,'run_bounded',side_effect=[(0,CLAUDE_HELP.encode(),b''),(0,raw,b'')]) as run:
                self.assertEqual(agent.probe_agent('claude',['client']),dict(state='unknown'))
                self.assertTrue(all(c.args[1]=='' for c in run.call_args_list))

    def test_http_checks_require_local_json_and_never_enable_or_generate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);service=ExplanationService(agent.configuration(root))
            server=create_server(0,{'codex':root/'absent.sqlite'},explanation_service=service)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(method,path,body=None,headers=None):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                h={'Content-Type':'application/json','X-Yukio-Workbench':'1'};h.update(headers or {})
                c.request(method,path,None if body is None else json.dumps(body),h)
                r=c.getresponse();raw=r.read();status=r.status;c.close();return status,raw
            try:
                with patch('agent_explanation.find_agent',return_value=['claude']), \
                     patch('agent_explanation.probe_agent',return_value=dict(state='ready')) as probe, \
                     patch.object(service,'generate',side_effect=AssertionError('No generation')):
                    self.assertEqual(request('GET','/api/agent-status')[0],200);probe.assert_not_called()
                    self.assertEqual(json.loads(request('POST','/api/agent-check',{'provider':'claude'})[1]),dict(provider='claude',state='ready'))
                    self.assertEqual(request('POST','/api/agent-check',{'provider':'claude'},{'Origin':'https://other.test'})[0],403)
                    for body in [{'provider':'auto'},{'provider':[]},{'provider':'claude','prompt':'PRIVATE'}]:
                        self.assertEqual(request('POST','/api/agent-check',body)[0],400)
                    self.assertEqual(request('GET','/api/agent-status?provider=codex')[0],400)
                    self.assertEqual(probe.call_count,1)
                    self.assertFalse(service.calls)
                    self.assertFalse((root/agent.SETTINGS).exists())
            finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
