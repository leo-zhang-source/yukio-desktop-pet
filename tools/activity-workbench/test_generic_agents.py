"""Different users/installations, without shared accounts or model requests."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import agent_explanation as agent
from explanation import ExplanationError, ExplanationService
from test_explanation import item, answer

CODEX_HELP = ('--ignore-user-config --ephemeral --skip-git-repo-check --sandbox '
              '--color --output-schema --output-last-message')
CLAUDE_HELP = ('--print --safe-mode --output-format --no-session-persistence '
               '--tools --disable-slash-commands --strict-mcp-config --mcp-config '
               '--system-prompt --json-schema\nCommands:\n  auth Manage authentication')


class GenericSelectionTests(unittest.TestCase):
    def test_local_startup_needs_no_external_hostname_lookup(self):
        from server import create_server
        with tempfile.TemporaryDirectory() as folder, \
             patch('socket.getfqdn',side_effect=AssertionError('No reverse DNS for loopback')):
            server=create_server(0,{'codex':Path(folder)/'absent.sqlite'})
            try:
                self.assertEqual(server.server_name,'localhost')
                self.assertGreater(server.server_port,0)
            finally:
                server.server_close()

    def test_automatic_selection_skips_signed_out_or_incompatible_installations(self):
        cfg = agent.configuration(None)
        for state in ['agent_login_required', 'agent_incompatible', 'agent_start_failed', 'agent_probe_timeout']:
            for preferred in ('codex', 'claude'):
                other = 'claude' if preferred == 'codex' else 'codex'
                with self.subTest(state=state, preferred=preferred), \
                     patch.object(agent, 'find_agent', side_effect=lambda p: [p]), \
                     patch.object(agent, 'probe_agent', side_effect=lambda p,c: dict(state='ready') if p == other else dict(state='unavailable', reason=state)):
                    self.assertEqual(agent.select_agent(cfg, preferred)['agent'], other)

    def test_explicit_choice_never_switches_to_another_account(self):
        with patch.object(agent, 'find_agent', side_effect=lambda p: [p]), \
             patch.object(agent, 'probe_agent', return_value=dict(state='unavailable', reason='agent_login_required')) as probe:
            with self.assertRaisesRegex(ExplanationError, 'agent_login_required'):
                agent.select_agent(agent.configuration(None, 'claude'), 'codex')
            self.assertEqual([c.args[0] for c in probe.call_args_list], ['claude'])

    def test_preflight_does_not_spend_generation_budget_or_cache_a_login_failure(self):
        sent = []
        service = ExplanationService(agent.configuration(None, 'claude'), sender=lambda c,p: sent.append(c) or answer(p))
        preview = service.preview(dict(client='claude'), item(), [])
        with patch.object(agent, 'find_agent', return_value=['test-client']), \
             patch.object(agent, 'probe_agent', return_value=dict(state='unavailable', reason='agent_login_required')):
            self.assertEqual(service.generate(preview['token'], True)['reason'], 'agent_login_required')
        self.assertFalse(sent)
        self.assertFalse(service.calls)
        with patch.object(agent, 'find_agent', return_value=['test-client']), \
             patch.object(agent, 'probe_agent', return_value=dict(state='ready')):
            self.assertEqual(service.generate(preview['token'], True)['mode'], 'model')
        self.assertEqual(len(sent), 1)
        self.assertEqual(len(service.calls), 1)

    def test_close_or_stop_during_preflight_prevents_any_excerpt_send(self):
        import test_reading
        fx = test_reading.ReadingTests(); fx.setUp()
        try:
            fx.service.config = agent.configuration(None, 'claude')
            def probe(*_):
                fx.auto.revoke(fx.grant)
                return dict(state='ready')
            with patch.object(agent, 'find_agent', return_value=['test-client']), \
                 patch.object(agent, 'probe_agent', side_effect=probe):
                result = fx.auto.refresh(fx.grant, True)
            self.assertEqual(result['result']['reason'], 'consent_required')
            self.assertFalse(fx.sent)
            self.assertFalse(fx.service.calls)
        finally:
            fx.tearDown()

    def test_source_settings_and_discovery_are_separate_for_each_user(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, provider in [('Alice', 'codex'), ('Bob 中文', 'claude')]:
                user = root / name
                exe = user / '.local/bin' / provider
                exe.parent.mkdir(parents=True)
                exe.write_text('fixture'); exe.chmod(0o700)
                data = user / 'data'
                self.assertEqual(agent.configuration(data)['agent'], 'auto')
                agent.save_preferences(data, provider, True)
                with patch('shutil.which', return_value=None):
                    command = agent.find_agent(provider, environ={'PATH':''}, home=user)
                self.assertEqual(command, [str(exe)])
                self.assertEqual(agent.configuration(data)['agent'], provider)
                self.assertNotIn(str(root), json.dumps(agent.preferences(data)))
            self.assertEqual(agent.configuration(root/'Alice/data')['agent'], 'codex')
            self.assertEqual(agent.configuration(root/'Bob 中文/data')['agent'], 'claude')

    def test_windows_npm_works_with_node_outside_stale_start_menu_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shim = root/'User 中文/AppData/Roaming/npm/claude.cmd'
            script = shim.parent/'node_modules/@anthropic-ai/claude-code/cli.js'
            script.parent.mkdir(parents=True); script.write_text('fixture')
            shim.write_text('do not run a shell')
            program_files = root/'Program Files'
            node = program_files/'nodejs/node.exe'
            node.parent.mkdir(parents=True); node.write_text('fixture')
            with patch('shutil.which', return_value=None):
                command = agent.find_agent('claude', environ={'PATH':'','YUKIO_CLAUDE_PATH':str(shim),
                    'ProgramFiles':str(program_files)}, home=root/'User 中文', windows=True)
            self.assertEqual(command, [str(node),str(script)])


class ProbeTests(unittest.TestCase):
    def test_help_and_login_inspection_receive_no_excerpts(self):
        for provider, help_text, auth in [('codex', CODEX_HELP, b'Logged in using ChatGPT'),
                                           ('claude', CLAUDE_HELP, b'{"loggedIn":true,"email":"PRIVATE"}')]:
            calls = []
            def run(command, prompt, cwd, timeout):
                calls.append((command,prompt))
                return (0,help_text.encode(),b'') if '--help' in command else (0,auth,b'')
            with patch.object(agent, 'run_bounded', side_effect=run):
                result = agent.probe_agent(provider, ['test-client'])
            self.assertEqual(result, dict(state='ready'))
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(not prompt for _,prompt in calls))
            self.assertNotIn('PRIVATE', str(result))
            self.assertEqual(calls[0][0], ['test-client']+(['exec','--help'] if provider=='codex' else ['--help']))
            self.assertEqual(calls[1][0], ['test-client']+(['login','status'] if provider=='codex' else ['auth','status','--json']))

    def test_old_or_unknown_cli_is_rejected_before_login_or_generation(self):
        with patch.object(agent, 'run_bounded', return_value=(0,b'--print --tools',b'')) as run:
            result = agent.probe_agent('claude', ['old-client'])
        self.assertEqual(result['reason'], 'agent_incompatible')
        self.assertEqual(run.call_count, 1)

    def test_unknown_auth_command_is_never_guessed_as_a_chat_prompt(self):
        help_text = CLAUDE_HELP.split('Commands:')[0]
        with patch.object(agent, 'run_bounded', return_value=(0,help_text.encode(),b'')) as run:
            self.assertEqual(agent.probe_agent('claude', ['client']), dict(state='unknown'))
        self.assertEqual(run.call_count, 1)

    def test_signed_out_user_and_third_party_provider_remain_distinct(self):
        for auth, expected in [({'loggedIn':False},'unavailable'),
                               ({'loggedIn':False,'authMethod':'third_party'},'unknown')]:
            with patch.object(agent, 'run_bounded', side_effect=[(0,CLAUDE_HELP.encode(),b''),(0,json.dumps(auth).encode(),b'')]):
                result = agent.probe_agent('claude',['client'])
            self.assertEqual(result['state'],expected)

    def test_probe_failures_do_not_trigger_a_generation_or_another_subcommand(self):
        with patch.object(agent, 'run_bounded', side_effect=ExplanationError('agent_timeout')) as run:
            self.assertEqual(agent.probe_agent('codex',['client'])['reason'],'agent_probe_timeout')
        self.assertEqual(run.call_count,1)

    def test_probes_work_through_real_unicode_path_subprocesses(self):
        with tempfile.TemporaryDirectory(prefix='通用 检查 & ') as folder:
            script = Path(folder)/'client.py'
            script.write_text('''import sys,json
assert sys.stdin.read()==''
if '--help' in sys.argv:
 print('''+repr(CODEX_HELP+'\n'+CLAUDE_HELP)+''')
elif sys.argv[1:]==['login','status']: print('Logged in')
elif sys.argv[1:]==['auth','status','--json']: print(json.dumps({'loggedIn':True}))
else: raise SystemExit('Unexpected command: no generation is allowed')
''', encoding='utf-8')
            for provider in ('codex','claude'):
                self.assertEqual(agent.probe_agent(provider,[sys.executable,str(script)]),dict(state='ready'))


if __name__=='__main__':
    unittest.main()
