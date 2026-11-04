import json
import os
import queue
from pathlib import Path
import sqlite3
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

from launcher import databases_for,inspect,check_existing,ROOT
from runtime_identity import identity
from server import create_server
from test_workbench import fixture

class LauncherTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def launch_until_ready(self,port,data):
        process=subprocess.Popen([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--fallback-port','--port',str(port),'--data-dir',str(data)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        lines=queue.Queue()
        def read():
            for line in process.stdout:lines.put(line)
            lines.put(None)
        threading.Thread(target=read,daemon=True).start()
        self.addCleanup(self.stop_probe,process)
        deadline=time.monotonic()+8
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:self.fail('Launcher readiness timed out')
            line=lines.get(timeout=remaining)
            if line is None:self.fail('Launcher exited before readiness')
            if line.startswith('YUKIO_WORKBENCH_READY '):
                from urllib.parse import urlsplit
                return process,urlsplit(json.loads(line.split(' ',1)[1])['url']).port
    @staticmethod
    def stop_probe(process):
        if process.poll() is None:process.terminate()
        process.wait(timeout=5)
        process.stdout.close()

    def test_fallback_binds_available_port_without_stopping_unrelated_listener(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0));occupied.listen();port=occupied.getsockname()[1]
            data=self.root/'new-profile'
            process,new_port=self.launch_until_ready(port,data)
            self.assertNotEqual(new_port,port)
            self.assertEqual(check_existing(new_port,databases_for(data)),'same')
            self.assertEqual(occupied.getsockname()[1],port)
            self.assertFalse(data.exists(),'Read-only startup must not create history')
            self.assertIsNone(process.poll())

    def test_zero_port_reports_the_actual_reserved_port(self):
        data=self.root/'automatic-port'
        process,port=self.launch_until_ready(0,data)
        self.assertGreater(port,0)
        self.assertEqual(check_existing(port,databases_for(data)),'same')
        self.assertIsNone(process.poll())

    def test_fallback_does_not_reuse_or_stop_a_different_workbench(self):
        old_databases=databases_for(self.root/'old-profile');server=create_server(0,old_databases)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            process,new_port=self.launch_until_ready(server.server_port,self.root/'new-profile')
            self.assertNotEqual(new_port,server.server_port)
            self.assertEqual(check_existing(server.server_port,old_databases),'same')
            self.assertEqual(check_existing(new_port,databases_for(self.root/'new-profile')),'same')
        finally:server.shutdown();server.server_close();thread.join()

    def test_same_service_reuse_reports_its_actual_url_before_exiting(self):
        dbs=databases_for(self.root);server=create_server(0,dbs)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            process,port=self.launch_until_ready(server.server_port,self.root)
            self.assertEqual(port,server.server_port);self.assertEqual(process.wait(timeout=3),0)
            self.assertEqual(check_existing(port,dbs),'same')
        finally:server.shutdown();server.server_close();thread.join()
    def wait_stopped(self,data):
        # Child EOF must release the history, even after Windows TerminateProcess.
        for _ in range(100):
            paths=[data/(c+'-workbench-status.json') for c in ('codex','claude','deepcode')]
            try:
                if all(p.exists() and json.loads(p.read_text())['state']=='stopped' for p in paths):
                    from yukio.activity_collector_cli import CollectorLease
                    for db in databases_for(data).values():CollectorLease(db).close()
                    return
            except (OSError,ValueError):pass
            time.sleep(.05)
        self.fail('Owned recorders did not stop and release histories')
    def test_readiness_does_not_create_missing_history(self):
        directory=self.root/'absent';out=inspect(directory)
        self.assertFalse(directory.exists());self.assertTrue(out['python_supported'])
        self.assertTrue(all(not c['available'] for c in out['clients']))
    def test_reuse_requires_same_build_and_database_scope(self):
        dbs=databases_for(self.root);server=create_server(0,dbs)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with patch('urllib.request.HTTPSHandler',side_effect=AssertionError('Loopback health must not initialize TLS')):
                self.assertEqual(check_existing(server.server_port,dbs),'same')
            self.assertEqual(check_existing(server.server_port,databases_for(self.root/'other')),'different')
            self.assertEqual(check_existing(server.server_port,dbs,{'model':'changed'}),'different')
        finally:server.shutdown();server.server_close();t.join()
    def test_wrong_port_owner_is_not_terminated_or_written_over(self):
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen();port=sock.getsockname()[1]
        try:
            result=subprocess.run([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--collect','--port',str(port),'--data-dir',str(self.root/'new')],capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0);self.assertFalse((self.root/'new').exists());self.assertEqual(sock.getsockname()[1],port)
        finally:sock.close()
    def test_start_readonly_stop_and_restart_preserve_history(self):
        dbs=databases_for(self.root)
        for path in dbs.values():fixture(path)
        before={k:v.read_bytes() for k,v in dbs.items()}
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        for _ in range(2):
            p=subprocess.Popen([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--port',str(port),'--data-dir',str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               env=dict(os.environ,PYTHONUTF8='0',PYTHONIOENCODING='cp1252'))
            try:
                for attempt in range(50):
                    if check_existing(port,dbs)=='same':break
                    if p.poll() is not None:self.fail('Launcher exited early')
                    time.sleep(.02)
                else:self.fail('Launcher not ready')
            finally:p.terminate();p.communicate(timeout=5)
        self.assertEqual(before,{k:v.read_bytes() for k,v in dbs.items()})
    def test_invalid_private_config_does_not_start_or_modify_history(self):
        self.root.joinpath('local-explanation-options.json').write_text(json.dumps(dict(lan=True)))
        self.root.joinpath('lan-model.json').write_text(json.dumps(dict(api_key='PRIVATE')))
        self.root.joinpath('explanation-provider.json').write_text(json.dumps(dict(provider='lan',automatic_on_open=False)))
        result=subprocess.run([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--collect','--data-dir',str(self.root)],capture_output=True,timeout=4)
        self.assertNotEqual(result.returncode,0);self.assertNotIn(b'PRIVATE',result.stderr)
        self.assertIn(b'"code": "invalid_configuration"',result.stderr)
        self.assertEqual({p.name for p in self.root.iterdir()},{'lan-model.json','explanation-provider.json','local-explanation-options.json'})

    def test_existing_page_without_collectors_starts_missing_recorders(self):
        data=self.root/'reuse-data';sources=self.root/'reuse-sources';data.mkdir()
        for client in ('codex','claude','deepcode'):(sources/client).mkdir(parents=True)
        (sources/'codex/new.jsonl').write_text(json.dumps(dict(type='session_meta',payload=dict(id='new-chat')))+'\n')
        dbs=databases_for(data);server=create_server(0,dbs)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        process=subprocess.Popen([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--collect','--port',str(server.server_port),'--data-dir',str(data),'--source-root',str(sources)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for _ in range(80):
                report=inspect(data)
                if report['clients'][0].get('saved_records',0)>0:break
                time.sleep(.05)
            else:self.fail('Existing page was reused without starting missing collectors')
            self.assertIsNone(process.poll())
        finally:
            process.terminate();process.communicate(timeout=8)
            self.wait_stopped(data)
            self.assertEqual(check_existing(server.server_port,dbs),'same')
            for client in ('codex','claude','deepcode'):
                state_path=data/(client+'-workbench-status.json')
                if state_path.exists():self.assertEqual(json.loads(state_path.read_text())['state'],'stopped')
            server.shutdown();server.server_close();thread.join()

    def test_full_collection_history_context_restart_and_shared_ownership(self):
        sources=self.root/'sources';data=self.root/'data'
        examples={
            'codex':[dict(type='session_meta',payload=dict(id='demo')),dict(type='event_msg',payload=dict(type='task_started',turn_id='t')),dict(type='response_item',payload=dict(type='function_call',call_id='c',name='Read')),dict(type='response_item',payload=dict(type='function_call_output',call_id='c',output='{"exit_code":0}'))],
            'claude':[dict(type='assistant',sessionId='demo',uuid='r',message=dict(content=[dict(type='tool_use',id='c',name='Read')])),dict(type='user',sessionId='demo',message=dict(content=[dict(type='tool_result',tool_use_id='c',is_error=False)]))],
            'deepcode':[dict(role='assistant',sessionId='demo',id='r',messageParams=dict(tool_calls=[dict(id='c',type='function',function=dict(name='Read',arguments='{}'))])),dict(role='tool',sessionId='demo',messageParams=dict(tool_call_id='c'),content='{"ok":true}')],
        }
        for client,rows in examples.items():
            (sources/client).mkdir(parents=True)
            (sources/client/'demo.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        def free_port():
            with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
        def start(port):
            return subprocess.Popen([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--collect','--port',str(port),'--data-dir',str(data),'--source-root',str(sources)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def get(port,route):
            req=urllib.request.Request('http://127.0.0.1:%d/api/'%port+route,headers={'X-Yukio-Workbench':'1'})
            with urllib.request.urlopen(req,timeout=1) as r:return json.load(r)
        def wait_ready(port):
            for _ in range(80):
                try:
                    clients=get(port,'clients')['clients']
                    if all(c['available'] and c['saved_records']>=2 for c in clients):return clients
                except Exception:pass
                time.sleep(.05)
            self.fail('Collectors did not save synthetic activity')
        def stop(p):
            if p.poll() is None:p.terminate()
            p.communicate(timeout=8)
        port=free_port();first=start(port);second=None
        try:
            clients=wait_ready(port);counts={c['id']:c['saved_records'] for c in clients}
            from urllib.parse import urlencode
            for client in examples:
                group=get(port,'groups?client='+client)['groups'][0]
                context=get(port,'context?'+urlencode(dict(client=client,key=group['key'])))
                self.assertEqual(context['status_counts'],{'succeeded':1})
            other_port=free_port();second=start(other_port);wait_ready(other_port);stop(second);second=None
            # The second launch did not own the first launch's recorder leases.
            self.assertIsNone(first.poll())
            for client in examples:
                state=json.loads((data/(client+'-workbench-status.json')).read_text())['state']
                self.assertNotIn(state,('stopped','failed'))
        finally:
            if second:stop(second)
            stop(first);self.wait_stopped(data)
        restarted=start(port)
        try:
            clients=wait_ready(port)
            self.assertEqual(counts,{c['id']:c['saved_records'] for c in clients})
        finally:stop(restarted);self.wait_stopped(data)
        for client in examples:
            self.assertEqual(json.loads((data/(client+'-workbench-status.json')).read_text())['state'],'stopped')

    def test_forced_launcher_exit_releases_only_owned_recorders(self):
        sources=self.root/'kill-sources';data=self.root/'kill-data'
        for client in ('codex','claude','deepcode'):(sources/client).mkdir(parents=True)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        p=subprocess.Popen([sys.executable,str(ROOT/'launcher.py'),'--no-browser','--collect','--port',str(port),'--data-dir',str(data),'--source-root',str(sources)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           env=dict(os.environ,YUKIO_DIAGNOSTICS='1'))
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if p.poll() is not None:
                    _,error=p.communicate(timeout=1)
                    self.fail('Launcher exited before recorder readiness: '+error.decode('utf-8',errors='replace'))
                if all((data/(c+'-workbench-status.json')).exists() for c in ('codex','claude','deepcode')):break
                time.sleep(.05)
            else:
                p.kill();out,error=p.communicate(timeout=5)
                self.fail('Recorders did not start; launcher output: '+(out+error).decode('utf-8',errors='replace'))
        finally:
            p.kill();p.communicate(timeout=5)
        self.wait_stopped(data)

if __name__=='__main__':unittest.main()
