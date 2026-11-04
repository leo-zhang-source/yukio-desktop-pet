"""Desktop Codex discovery never launches clients or changes global settings."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agent_explanation as agent
from explanation import ExplanationError, ExplanationService
from agent_setup import AgentSetup
from test_explanation import item, answer


class CodexDesktopDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Yukio desktop 中文 & ')
        self.root=Path(self.temp.name)
        self.apps=[self.root/'User 中文/Applications',self.root/'Applications']
        self.cli=self.root/'bin/codex';self.cli.parent.mkdir();self.cli.write_text('fixture');self.cli.chmod(0o700)

    def tearDown(self):self.temp.cleanup()

    def bundle(self,root=None,name='ChatGPT.app'):
        package=(root or self.apps[0])/name/'Contents/Resources/codex-cli'
        command=package/'bin/codex';command.parent.mkdir(parents=True,exist_ok=True)
        command.write_text('fixture');command.chmod(0o700)
        (package/'codex-package.json').write_text(json.dumps(dict(layoutVersion=1,variant='codex',
            target='aarch64-apple-darwin',entrypoint='bin/codex')))
        return command

    def find(self,environ=None,**kwargs):
        with patch('shutil.which',return_value=str(self.cli)),patch.object(agent,'run_bounded',side_effect=AssertionError('Discovery must not launch clients')):
            return agent.find_agent('codex',environ=environ or {'PATH':''},home=self.root/'User 中文',
                application_roots=self.apps,**kwargs)

    def test_current_user_and_system_layouts_precede_path_without_launching(self):
        system=self.bundle(self.apps[1]);self.assertEqual(self.find(),[str(system)])
        own=self.bundle();self.assertEqual(self.find(),[str(own)])
        self.assertEqual(self.find(prefer_desktop=False),[str(self.cli)])

    def test_current_layout_under_codex_name_is_supported(self):
        command=self.bundle(name='Codex.app');self.assertEqual(self.find(),[str(command)])

    def test_explicit_override_is_never_replaced_even_when_missing(self):
        self.bundle()
        self.assertEqual(self.find({'YUKIO_CODEX_PATH':str(self.cli)}),[str(self.cli)])
        self.assertIsNone(self.find({'YUKIO_CODEX_PATH':str(self.root/'missing')}))

    def test_invalid_or_oversize_manifests_fall_back_to_path(self):
        command=self.bundle();manifest=command.parent.parent/'codex-package.json'
        for raw in ['[]','broken',' '*8193,json.dumps(dict(layoutVersion=True,variant='codex',target='aarch64-apple-darwin',entrypoint='bin/codex')),
                    json.dumps(dict(layoutVersion=1,variant='codex',target='aarch64-apple-darwin',entrypoint='../../other')),
                    json.dumps(dict(layoutVersion=2,variant='codex',target='aarch64-apple-darwin',entrypoint='bin/codex'))]:
            with self.subTest(raw=raw[:80]):
                manifest.write_text(raw);self.assertEqual(self.find(),[str(self.cli)])

    def test_missing_nonexecutable_or_escaping_entrypoints_fall_back(self):
        command=self.bundle();command.chmod(0o600);self.assertEqual(self.find(),[str(self.cli)])
        command.unlink();self.assertEqual(self.find(),[str(self.cli)])
        command.symlink_to(self.cli);self.assertEqual(self.find(),[str(self.cli)])
        command.unlink();command.symlink_to(command.name);self.assertEqual(self.find(),[str(self.cli)])

    def test_legacy_or_absent_desktop_keeps_cli_priority_and_windows_is_unchanged(self):
        legacy=self.apps[0]/'Codex.app/Contents/Resources/codex';legacy.parent.mkdir(parents=True);legacy.write_text('fixture');legacy.chmod(0o700)
        self.assertEqual(self.find(),[str(self.cli)])
        self.bundle();self.assertEqual(self.find(windows=True),[str(self.cli)])

    def test_unstartable_or_incompatible_new_bundle_uses_cli_before_preview_only(self):
        desktop=str(self.bundle())
        for reason in ['agent_start_failed','agent_incompatible','agent_compatibility_timeout']:
            with self.subTest(reason=reason),patch.dict(os.environ,{'YUKIO_CODEX_PATH':''}), \
                 patch.object(agent,'find_agent',side_effect=lambda p,**kw:[str(self.cli)] if kw.get('prefer_desktop') is False else [desktop]), \
                 patch.object(agent,'probe_agent',side_effect=lambda p,c:dict(state='ready') if c==[str(self.cli)] else dict(state='unavailable',reason=reason)):
                selected=agent.select_agent(agent.configuration(None,'codex'))
                self.assertEqual(selected['command'],[str(self.cli)])
                self.assertEqual(AgentSetup().check('codex'),dict(provider='codex',state='ready'))

    def test_logged_out_desktop_and_explicit_override_do_not_silently_switch(self):
        desktop=str(self.bundle())
        for override,reason in [('', 'agent_login_required'),(desktop,'agent_incompatible')]:
            with patch.dict(os.environ,{'YUKIO_CODEX_PATH':override}),patch.object(agent,'find_agent',return_value=[desktop]) as find, \
                 patch.object(agent,'probe_agent',return_value=dict(state='unavailable',reason=reason)):
                with self.assertRaises(ExplanationError):agent.select_agent(agent.configuration(None,'codex'))
                self.assertEqual(find.call_count,1)

    def test_bundle_loss_after_preview_does_not_send_using_cli(self):
        desktop=str(self.bundle());sent=[]
        service=ExplanationService(agent.configuration(None,'codex'),sender=lambda c,p:sent.append(c) or answer(p))
        with patch.object(agent,'find_agent',return_value=[desktop]),patch.object(agent,'probe_agent',return_value=dict(state='ready')):
            preview=service.preview(dict(client='codex'),item(),[])
        with patch.object(agent,'find_agent',return_value=[str(self.cli)]),patch.object(agent,'probe_agent',return_value=dict(state='ready')):
            result=service.generate(preview['token'],True)
        self.assertEqual(result['reason'],'recipient_changed');self.assertFalse(sent)


if __name__=='__main__':unittest.main()
