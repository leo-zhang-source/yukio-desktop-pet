import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import agent_explanation as agent
from explanation import ExplanationError, ExplanationService, encode, prepare
from launcher import check_existing
from page_explanation_policy import enabled
from server import create_server
from test_explanation import item, answer


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='雪绪 Agent & ')
        self.root = Path(self.temp.name)
        self.payload, _ = prepare(item(), [])
        self.probe = patch.object(agent, 'probe_agent', return_value=dict(state='ready'))
        self.probe.start()
    def tearDown(self):
        self.probe.stop()
        self.temp.cleanup()

    def test_default_uses_own_agent_and_does_not_inherit_lan_consent(self):
        cfg = agent.configuration(self.root)
        self.assertEqual(cfg['agent'], 'auto')
        self.assertFalse(enabled(self.root, cfg))
        (self.root / 'page-explanation-policy.json').write_text(encode(dict(version=1,
            automatic_on_open=True, scope='selected_chat_short_excerpts', destination=cfg['base_url'])))
        self.assertFalse(enabled(self.root, cfg))
        agent.save_preferences(self.root, 'auto', True)
        self.assertTrue(enabled(self.root, cfg))
        self.assertFalse(enabled(self.root, agent.configuration(self.root, 'claude')))
        if os.name != 'nt':
            self.assertEqual((self.root / agent.SETTINGS).stat().st_mode & 0o777, 0o600)

    def test_invalid_preferences_fail_without_exposing_values(self):
        path = self.root / agent.SETTINGS
        for value in [dict(provider='other', automatic_on_open=True),
                      dict(provider='auto', automatic_on_open='yes'), [],
                      dict(provider='auto', automatic_on_open=True, api_key='secret')]:
            path.write_text(encode(value))
            with self.assertRaises(ValueError):
                agent.preferences(self.root)

    def test_auto_follows_chat_and_uses_only_an_installed_client(self):
        cfg = agent.configuration(self.root)
        with patch.object(agent, 'find_agent', side_effect=lambda p: [p]):
            self.assertEqual(agent.select_agent(cfg, 'claude')['agent'], 'claude')
            self.assertEqual(agent.select_agent(cfg, 'codex')['agent'], 'codex')
            self.assertEqual(agent.select_agent(cfg, 'deepcode')['agent'], 'codex')
        with patch.object(agent, 'find_agent', side_effect=lambda p: ['cli'] if p == 'claude' else None):
            self.assertEqual(agent.select_agent(cfg, 'codex')['agent'], 'claude')
            with self.assertRaisesRegex(ExplanationError, 'agent_not_found'):
                agent.select_agent(agent.configuration(self.root, 'codex'))

    def test_old_lan_file_is_not_a_dependency_of_default_agent(self):
        (self.root / 'lan-model.json').write_text('broken old configuration')
        self.assertEqual(agent.configuration(self.root)['provider'], 'agent')
        with self.assertRaises(ValueError):
            agent.configuration(self.root, 'lan')

    @unittest.skipIf(sys.version_info < (3, 11), 'Custom providers use bundled Python 3.12 TOML parser')
    def test_custom_codex_model_and_auth_survive_without_secrets_in_arguments(self):
        (self.root / 'config.toml').write_text('''model="my-model"
model_provider="my-service"
cli_auth_credentials_store="keyring"
[model_providers.my-service]
name="My service"
base_url="https://example.test/v1"
wire_api="responses"
experimental_bearer_token="SECRET_BEARER"
http_headers={X-Key="SECRET_HEADER"}
''')
        with patch.dict(os.environ, {'CODEX_HOME': str(self.root)}):
            args, env = agent.codex_overrides()
        self.assertIn('model="my-model"', args)
        self.assertIn('cli_auth_credentials_store="keyring"', args)
        self.assertNotIn('SECRET', str(args))
        self.assertEqual(env['YUKIO_AGENT_BEARER'], 'SECRET_BEARER')
        self.assertEqual(env['YUKIO_AGENT_HEADER_0'], 'SECRET_HEADER')

    def test_finder_path_and_explicit_path_with_spaces(self):
        path = self.root / '.local/bin/claude'
        path.parent.mkdir(parents=True)
        path.write_text('test')
        path.chmod(0o700)
        with patch('shutil.which', return_value=None):
            self.assertEqual(agent.find_agent('claude', environ={'PATH': ''}, home=self.root), [str(path)])
            self.assertEqual(agent.find_agent('claude', environ={'YUKIO_CLAUDE_PATH': str(path)}, home=self.root), [str(path)])
            self.assertIsNone(agent.find_agent('claude', environ={'YUKIO_CLAUDE_PATH': str(path)+'missing'}, home=self.root))

    def test_short_explanations_cap_expensive_reasoning_without_changing_user_configuration(self):
        path = self.root / 'config.toml'
        for effort in ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'):
            with self.subTest(effort=effort):
                raw = 'model="chosen-model"\nmodel_reasoning_effort=' + json.dumps(effort) + '\n'
                path.write_text(raw)
                with patch.dict(os.environ, {'CODEX_HOME': str(self.root)}):
                    args, _ = agent.codex_overrides()
                expected = effort if effort in ('none', 'minimal', 'low', 'medium') else 'medium'
                self.assertIn('model_reasoning_effort=' + json.dumps(expected), args)
                self.assertIn('model="chosen-model"', args)
                self.assertEqual(path.read_text(), raw)

    def test_disabled_codex_selection_survives_server_restart_without_falling_back(self):
        databases = dict(codex=self.root / 'history.sqlite')
        servers = []
        threads = []
        def start():
            server = create_server(0, databases)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start(); servers.append(server); threads.append(thread)
            return server
        def request(server, settings=None):
            c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            c.request('POST' if settings else 'GET', '/api/explanation-settings' if settings else '/api/clients',
                      encode(settings).encode() if settings else None,
                      {'Content-Type': 'application/json', 'X-Yukio-Workbench': '1'})
            r = c.getresponse(); raw = r.read(); c.close(); return r.status, json.loads(raw)
        try:
            server = start()
            with patch('server.select_agent', side_effect=ExplanationError('agent_login_required')) as probe:
                status, data = request(server, dict(provider='codex', automatic_on_open=False))
                probe.assert_not_called()
                self.assertEqual(status, 200)
                self.assertEqual(data['provider'], 'codex')
                self.assertFalse(data['automatic_on_open'])
                self.assertEqual(request(server, dict(provider='codex', automatic_on_open=True))[0], 409)
            restarted = start()
            data = request(restarted)[1]['explanation']
            self.assertEqual(data['provider'], 'codex')
            self.assertFalse(data['automatic_on_open'])
            with patch('server.select_agent', return_value={}):
                self.assertEqual(request(restarted, dict(provider='codex', automatic_on_open=True))[0], 200)
            data = request(start())[1]['explanation']
            self.assertEqual(data['provider'], 'codex')
            self.assertTrue(data['automatic_on_open'])
        finally:
            for server, thread in zip(servers, threads):
                server.shutdown(); server.server_close(); thread.join()

    def test_windows_npm_shim_uses_node_without_cmd_shell(self):
        path = self.root / 'npm/codex.cmd'
        path.parent.mkdir()
        path.write_text('MUST NOT EXECUTE')
        node = path.parent / 'node.exe'
        node.write_text('test')
        script = path.parent / 'node_modules/@openai/codex/bin/codex.js'
        script.parent.mkdir(parents=True)
        script.write_text('test')
        self.assertEqual(agent.find_agent('codex', environ={'YUKIO_CODEX_PATH': str(path)},
            home=self.root, windows=True), [str(node), str(script)])
        script.unlink()
        self.assertIsNone(agent.find_agent('codex', environ={'YUKIO_CODEX_PATH': str(path)},
            home=self.root, windows=True))

    def test_both_cli_protocols_via_actual_subprocesses_and_unicode_stdin(self):
        script = self.root / 'fake agent.py'
        script.write_text('''import sys,json,pathlib
args=sys.argv[1:];prompt=sys.stdin.read()
assert 'PRIVATE' not in prompt
if args[0]=='exec':
 assert '--ephemeral' in args and '--ignore-user-config' in args
 assert '--resume' not in args and '--continue' not in args
 path=pathlib.Path(args[args.index('--output-schema')+1]);schema=json.loads(path.read_text())
 payload=json.loads(prompt[prompt.index('{"facts"'):])
 result={'explanations':[{'evidence_id':f['evidence_id'],'text':'这是模拟解释。'} for f in payload['facts']]}
 pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
else:
 assert args[args.index('--tools')+1]=='' and '--safe-mode' in args
 assert '--no-session-persistence' in args and '--strict-mcp-config' in args
 payload=json.loads(prompt)
 result={'explanations':[{'evidence_id':f['evidence_id'],'text':'这是模拟解释。'} for f in payload['facts']]}
 print(json.dumps({'type':'result','subtype':'success','is_error':False,'structured_output':result}))
''', encoding='utf-8')
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider):
                cfg = dict(agent.configuration(self.root, provider), command=[sys.executable, str(script)])
                result = agent.call_agent(cfg, self.payload)
                self.assertEqual(result[0]['text'], '这是模拟解释。')

    def test_errors_are_classified_without_returning_provider_text(self):
        for text, expected in [('Not logged in SECRET', 'agent_login_required'),
                               ('rate limit 429 SECRET', 'agent_rate_limited'),
                               ('unexpected argument --ephemeral', 'agent_incompatible'),
                               ('unknown failure SECRET', 'agent_failed')]:
            self.assertEqual(agent.failure(b'', text.encode()), expected)
        self.assertEqual(agent.failure(b'', b'ERROR: {"error":{"code":"model_not_found"}}'), 'agent_model_unavailable')
        self.assertEqual(agent.failure(b'', b'2026-10-27T04:32:29.429\nERROR: generic failure'), 'agent_failed')
        self.assertEqual(agent.failure(b'User excerpt: not logged in and quota issues', b'ERROR: model_not_found'), 'agent_model_unavailable')

    def test_nonzero_invalid_json_error_result_and_missing_codex_result_reject(self):
        cfg = dict(agent.configuration(self.root, 'claude'), command=['test'])
        for output in [b'not json', b'[]', b'{"subtype":"error","is_error":true}',
                       b'{"subtype":"success","structured_output":{"explanations":[]}}']:
            with patch.object(agent, 'run_bounded', return_value=(0, output, b'')):
                with self.assertRaises(ExplanationError):
                    agent.call_agent(cfg, self.payload)
        with patch.object(agent, 'run_bounded', return_value=(1, b'', b'Not logged in SECRET')):
            with self.assertRaisesRegex(ExplanationError, 'agent_login_required'):
                agent.call_agent(cfg, self.payload)
        cfg = dict(agent.configuration(self.root, 'codex'), command=['test'])
        with patch.object(agent, 'run_bounded', return_value=(0, b'partial output', b'')):
            with self.assertRaisesRegex(ExplanationError, 'incomplete_response'):
                agent.call_agent(cfg, self.payload)

    def test_bounded_runner_stops_timeout_and_large_stdout_or_stderr(self):
        with self.assertRaisesRegex(ExplanationError, 'agent_timeout'):
            agent.run_bounded([sys.executable, '-c', 'import time;time.sleep(30)'], '', self.root, .1)
        for pipe in ('stdout', 'stderr'):
            with self.subTest(pipe=pipe), self.assertRaisesRegex(ExplanationError, 'response_too_large'):
                agent.run_bounded([sys.executable, '-c', 'import sys;sys.'+pipe+'.write("x"*400000)'], '', self.root, 3)

    def test_runner_keeps_prompts_out_of_arguments_and_cleans_frozen_environment(self):
        code = 'import os,sys,json;print(json.dumps([sys.stdin.read(),os.getenv("PYTHONHOME"),os.getenv("CLAUDECODE")]))'
        with patch.dict(os.environ, {'PYTHONHOME': 'bad', 'CLAUDECODE': 'parent'}):
            status, out, _ = agent.run_bounded([sys.executable, '-c', code], '你好 & $(never)', self.root, 3)
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out), ['你好 & $(never)', None, None])

    def test_failure_does_not_silently_switch_agents_and_retired_previews_cannot_send(self):
        cfg = agent.configuration(self.root)
        sent = []
        def sender(config, payload):
            sent.append(config['agent'])
            raise ExplanationError('agent_login_required')
        service = ExplanationService(cfg, sender=sender)
        with patch.object(agent, 'find_agent', side_effect=lambda p: [p]):
            preview = service.preview(dict(client='claude'), item(), [])
            result = service.generate(preview['token'], True)
        self.assertEqual(sent, ['claude'])
        self.assertEqual(result['reason'], 'agent_login_required')
        service.retired = True
        with self.assertRaisesRegex(ExplanationError, 'preview_expired'):
            service.generate(preview['token'], True)

    def test_agent_transport_handles_home_details_and_history_with_existing_validators(self):
        import test_glance
        from test_reading import ReadingTests, with_titles
        fx = ReadingTests(); fx.setUp()
        try:
            fx.add_turns(3)
            for provider in ('claude', 'codex'):
                fx.service.config = agent.configuration(self.root, provider)
                fx.service.calls.clear()
                fx.service.entries.clear()
                def transport(command, prompt, cwd, timeout, extra_env):
                    payload = json.loads(prompt[prompt.index('{"facts"'):]) if command[1] == 'exec' else json.loads(prompt)
                    if payload['scope'].get('reading'):
                        items = with_titles(payload, [dict(part=p['part'], text='助手汇报检查工作台，效果仍需确认。',
                            basis='inference', evidence_ids=p['required'] or p['allowed'][:1]) for p in payload['scope']['reading_parts']])
                    else:
                        items = test_glance.result(payload)
                    content = dict(explanations=items)
                    if command[1] == 'exec':
                        Path(command[command.index('--output-last-message')+1]).write_text(encode(content), encoding='utf-8')
                        return 0, b'', b''
                    return 0, encode(dict(subtype='success', structured_output=content)).encode(), b''
                fx.service.sender = agent.call_agent
                with patch.object(agent, 'find_agent', return_value=['fake']), patch.object(agent, 'run_bounded', side_effect=transport):
                    # A provider change needs a fresh grant, just as the HTTP settings route does.
                    _, payload, refs = fx.fx.glance.prepared('codex', fx.fx.key)
                    preview = fx.service.preview_prepared(dict(client='codex', key=fx.fx.key), payload, refs)
                    fx.grant = fx.auto.authorize(preview['token'], True, page_owned=True)['grant']
                    self.assertEqual(fx.auto.refresh(fx.grant, True)['result']['model'], agent.LABELS[provider])
                    fx.now[0] += 11
                    current = fx.reading.current(fx.grant)
                    self.assertEqual(fx.reading.explain(fx.grant, current['token'])['result']['mode'], 'model')
                    fx.now[0] += 11
                    history = fx.reading.history_page(fx.grant)
                    self.assertEqual(fx.reading.explain(fx.grant, history['token'])['result']['mode'], 'model')
                    fx.now[0] += 11
        finally:
            fx.tearDown()


class ProviderHTTPTests(unittest.TestCase):
    def test_settings_origin_budget_retirement_restart_and_health(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            databases = dict(codex=directory / 'history.sqlite')
            server = create_server(0, databases)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def post(data, headers=None):
                c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                c.request('POST', '/api/explanation-settings', encode(data).encode(),
                    dict({'Content-Type':'application/json','X-Yukio-Workbench':'1'}, **(headers or {})))
                r = c.getresponse(); raw = r.read(); result = r.status, json.loads(raw) if r.status != 403 else {}; c.close(); return result
            try:
                self.assertEqual(check_existing(server.server_port, databases), 'same')
                settings = dict(provider='claude', automatic_on_open=True)
                self.assertEqual(post(settings, {'Origin':'https://other.test'})[0], 403)
                self.assertFalse((directory / agent.SETTINGS).exists())
                for reason in ('agent_not_found', 'agent_login_required'):
                    with patch('server.select_agent', side_effect=ExplanationError(reason)):
                        status, data = post(settings)
                    self.assertEqual(status, 409)
                    self.assertFalse((directory / agent.SETTINGS).exists())
                with patch('server.select_agent', return_value={}):
                    status, data = post(settings)
                self.assertEqual(status, 200)
                self.assertEqual(data['provider'], 'claude')
                self.assertTrue(data['automatic_on_open'])
                self.assertEqual(agent.configuration(directory)['agent'], 'claude')
                self.assertEqual(check_existing(server.server_port, databases), 'same')
                self.assertFalse(post(dict(provider='claude', automatic_on_open=False))[1]['automatic_on_open'])
                for invalid in [dict(provider='bad', automatic_on_open=True), dict(provider='auto', automatic_on_open='yes')]:
                    self.assertEqual(post(invalid)[0], 400)
            finally:
                server.shutdown(); server.server_close(); thread.join()


class ProbeStageTests(unittest.TestCase):
    def test_help_and_login_timeouts_remain_distinct_without_a_generation(self):
        flags=b'--print --safe-mode --output-format --no-session-persistence --tools --disable-slash-commands --strict-mcp-config --mcp-config --system-prompt --json-schema\n  auth  Login commands'
        for outcomes,reason,count in [([ExplanationError('agent_timeout')],'agent_compatibility_timeout',1),
                                      ([(0,flags,b''),ExplanationError('agent_timeout')],'agent_login_check_timeout',2),
                                      ([(0,flags,b''),(0,b'{"loggedIn":false}',b'')],'agent_login_required',2)]:
            with patch.object(agent,'run_bounded',side_effect=outcomes) as run:
                result=agent.probe_agent('claude',['claude'])
                self.assertEqual(result['reason'],reason)
                self.assertEqual(run.call_count,count)
                self.assertTrue(all(call.args[1]=='' for call in run.call_args_list))


if __name__ == '__main__':
    unittest.main()
