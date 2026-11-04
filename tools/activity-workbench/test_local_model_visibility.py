"""Private Qwen visibility cannot be inherited by ordinary installations."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import agent_explanation as agent
from server import create_server


class LocalModelVisibilityTests(unittest.TestCase):
    def test_public_installation_hides_lan_even_with_an_old_model_file(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(agent,'find_agent',return_value=None):
            root=Path(folder)
            for existing in (False,True):
                if existing:(root/'lan-model.json').write_text('old private model')
                self.assertEqual([x['id'] for x in agent.provider_options(root)],['auto','codex','claude'])
                with self.assertRaises(ValueError):agent.configuration(root,'lan')
                with self.assertRaises(ValueError):agent.save_preferences(root,'lan',True)

    def test_local_opt_in_only_affects_its_own_installation(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(agent,'find_agent',return_value=['client']):
            owner=Path(folder)/'owner';other=Path(folder)/'other';owner.mkdir();other.mkdir()
            (owner/agent.LOCAL_OPTIONS).write_text(json.dumps({'lan':True}))
            (owner/'lan-model.json').write_text('existing private config')
            self.assertEqual(agent.provider_options(owner)[-1],dict(id='lan',label=agent.LABELS['lan'],available=True))
            self.assertNotIn('lan',[x['id'] for x in agent.provider_options(other)])
            (owner/agent.LOCAL_OPTIONS).unlink()
            self.assertNotIn('lan',[x['id'] for x in agent.provider_options(owner)])

    def test_invalid_opt_in_cannot_enable_the_private_option(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for raw in ['broken','[]','{"lan":1}','{"lan":"true"}','{"lan":false}',
                        '{"lan":true,"other":true}',' '*513]:
                (root/agent.LOCAL_OPTIONS).write_text(raw)
                self.assertFalse(agent.local_lan_enabled(root),raw)

    def test_old_lan_auto_explanation_is_disabled_without_modifying_its_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);saved=json.dumps(dict(provider='lan',automatic_on_open=True))
            (root/agent.SETTINGS).write_text(saved);(root/'lan-model.json').write_text('PRIVATE')
            self.assertEqual(agent.preferences(root),dict(provider='auto',automatic_on_open=False))
            self.assertEqual(agent.configuration(root)['agent'],'auto')
            self.assertEqual((root/agent.SETTINGS).read_text(),saved)

    def test_public_api_neither_advertises_nor_enables_lan(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(agent,'find_agent',return_value=None):
            root=Path(folder);server=create_server(0,{'codex':root/'absent.sqlite'})
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(method,route,body=None):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                c.request(method,'/api/'+route,None if body is None else json.dumps(body),
                          {'X-Yukio-Workbench':'1','Content-Type':'application/json'})
                response=c.getresponse();value=json.loads(response.read());status=response.status;c.close()
                return status,value
            try:
                status,result=request('GET','clients')
                self.assertEqual(status,200)
                self.assertEqual([x['id'] for x in result['explanation']['providers']],['auto','codex','claude'])
                self.assertFalse(result['explanation']['automatic_on_open'])
                self.assertEqual(request('POST','explanation-settings',dict(provider='lan',automatic_on_open=True))[0],400)
                self.assertFalse((root/agent.SETTINGS).exists())
            finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
