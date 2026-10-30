"""Real loopback processes with synthetic histories; no personal client directories."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import urlsplit

from launcher import ROOT, check_existing, databases_for, inspect
from test_workbench import fixture


class StartupLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=self.root/'data'
        self.sources=self.root/'sources'
        for client in ('codex','claude','deepcode'):(self.sources/client).mkdir(parents=True)

    def command(self,collect=False):
        cmd=[sys.executable,'-B',str(ROOT/'launcher.py'),'--no-browser','--port','0',
             '--data-dir',str(self.data),'--source-root',str(self.sources),'--parent-stdin']
        return cmd+(['--collect'] if collect else [])

    @staticmethod
    def stop(p):
        if p.stdin and not p.stdin.closed:p.stdin.close()
        try:p.wait(timeout=8)
        except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=8)
        if p.stdout:p.stdout.close()

    def launch(self,collect=False):
        p=subprocess.Popen(self.command(collect),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        self.addCleanup(self.stop,p)
        lines=queue.Queue()
        def read():
            for line in p.stdout:lines.put(line)
            lines.put(None)
        threading.Thread(target=read,daemon=True).start()
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            line=lines.get(timeout=max(.01,deadline-time.monotonic()))
            if line is None:self.fail('Launcher exited before ready')
            if line.startswith('YUKIO_WORKBENCH_READY '):
                port=urlsplit(json.loads(line.split(' ',1)[1])['url']).port
                return p,port
        self.fail('No readiness within deadline')

    def wait_state(self,state):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            try:
                rows=[json.loads((self.data/(c+'-workbench-status.json')).read_text()) for c in ('codex','claude','deepcode')]
                if state=='healthy' and all(r['state'] not in ('failed','stopped') for r in rows):return
                if all(r['state']==state for r in rows):return
            except (OSError,ValueError):pass
            time.sleep(.05)
        self.fail('Collector state did not become '+state)

    def test_ten_reconnections_leave_no_owned_service_and_keep_history(self):
        self.data.mkdir()
        for path in databases_for(self.data).values():fixture(path)
        before={k:p.read_bytes() for k,p in databases_for(self.data).items()}
        for _ in range(10):
            p,port=self.launch()
            self.assertEqual(check_existing(port,databases_for(self.data)),'same')
            self.assertTrue(any(c.get('saved_records',0)>0 for c in inspect(self.data)['clients']))
            p.stdin.close();self.assertEqual(p.wait(timeout=8),0)
            self.assertEqual(check_existing(port,databases_for(self.data)),'unavailable')
        self.assertEqual(before,{k:p.read_bytes() for k,p in databases_for(self.data).items()})

    def test_parent_pipe_eof_stops_own_recorders_but_keeps_external_recorders(self):
        external,external_port=self.launch(collect=True)
        self.wait_state('healthy')
        owned,owned_port=self.launch(collect=True)
        self.assertNotEqual(owned_port,external_port)
        owned.stdin.close();self.assertEqual(owned.wait(timeout=8),0)
        self.assertIsNone(external.poll())
        self.assertEqual(check_existing(external_port,databases_for(self.data)),'same')
        self.wait_state('healthy')
        external.stdin.close();self.assertEqual(external.wait(timeout=8),0)
        self.wait_state('stopped')
        from yukio.activity_collector_cli import CollectorLease
        for path in databases_for(self.data).values():CollectorLease(path).close()

    @unittest.skipUnless(sys.platform=='darwin','Mac owner-death check; Windows deferred')
    def test_forced_host_exit_closes_launcher_and_all_owned_recorders(self):
        # This disposable host owns the same anonymous stdin pipe as the native
        # Process host. SIGKILL skips cleanup; only kernel EOF remains available.
        code='''import json,subprocess,sys,time
p=subprocess.Popen(json.loads(sys.argv[1]),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
for line in p.stdout:
 if line.startswith('YUKIO_WORKBENCH_READY '):
  print(json.dumps(dict(pid=p.pid,ready=json.loads(line.split(' ',1)[1]))),flush=True)
  break
time.sleep(60)
'''
        host=subprocess.Popen([sys.executable,'-c',code,json.dumps(self.command(True))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def cleanup():
            if host.poll() is None:host.kill()
            host.communicate(timeout=5)
        self.addCleanup(cleanup)
        import select
        self.assertTrue(select.select([host.stdout],[],[],12)[0],'Host did not report readiness')
        report=json.loads(host.stdout.readline())
        self.wait_state('healthy')
        host.kill();host.wait(timeout=5)
        self.wait_state('stopped')
        port=urlsplit(report['ready']['url']).port
        self.assertEqual(check_existing(port,databases_for(self.data)),'unavailable')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:os.kill(report['pid'],0)
            except ProcessLookupError:break
            time.sleep(.05)
        else:self.fail('Owned launcher survived host death')
        from yukio.activity_collector_cli import CollectorLease
        for path in databases_for(self.data).values():CollectorLease(path).close()


if __name__=='__main__':unittest.main()
