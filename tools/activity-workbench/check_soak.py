#!/usr/bin/env python3
"""Elapsed-time package soak with disposable, explicitly synthetic chats.

Never opens a user's profile, calls a model, or accelerates the clock. The
report records the measured duration; a short run is not daily acceptance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.parse import urlencode
import urllib.request


def row(kind, **payload):
    return dict(type=kind, timestamp=datetime.now(timezone.utc).isoformat(), payload=payload)


def memory(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in
                ('peak_rss','rss','peak_pool','pool','peak_nonpool','nonpool','pagefile','peak_pagefile')]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x410,False,pid)
        if not handle:raise OSError('Cannot inspect test process')
        try:
            counters=Counters();counters.cb=ctypes.sizeof(counters);handles=wintypes.DWORD()
            psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
            kernel.GetProcessHandleCount.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
            if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.cb):raise OSError('Memory query failed')
            if not kernel.GetProcessHandleCount(handle,ctypes.byref(handles)):raise OSError('Handle query failed')
            return dict(rss_bytes=counters.rss,handles=handles.value)
        finally:kernel.CloseHandle(handle)
    rss=int(subprocess.check_output(['ps','-p',str(pid),'-o','rss='],text=True).strip())*1024
    return dict(rss_bytes=rss)


def run(args):
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sources=out/'模拟聊天';data=out/'记录'
    for client in ('codex','claude','deepcode'):(sources/client).mkdir(parents=True)
    files=[];expected={};completed={};written=0
    for n in range(2):
        path=sources/'codex'/('chat%d.jsonl'%n);session='synthetic-soak-%d'%n
        path.write_text(json.dumps(row('session_meta',id=session))+'\n',encoding='utf-8')
        files.append((path,session));expected[session]=1;completed[session]=0
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=[str(args.exe.resolve())] if args.exe else [sys.executable,'-B',str(args.runtime.resolve()/'launcher.py')]
    command+=['--collect','--no-browser','--port',str(port),'--data-dir',str(data),'--source-root',str(sources)]
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));latencies=[];requests=0;samples=[];failures=[]
    def get(route):
        nonlocal requests
        start=time.monotonic()
        request=urllib.request.Request('http://127.0.0.1:%d/api/'%port+route,headers={'X-Yukio-Workbench':'1'})
        with opener.open(request,timeout=8) as response:value=json.load(response)
        latencies.append(time.monotonic()-start);requests+=1
        return value
    def counts():
        with sqlite3.connect('file:'+str(data/'codex-activity-history-v1.sqlite')+'?mode=ro',uri=True) as db:
            return dict(db.execute('SELECT session_id,count(*) FROM events GROUP BY session_id'))
    def wait_counts():
        for _ in range(100):
            try:
                actual=counts()
                if all(actual.get(k)==v for k,v in expected.items()):return actual
            except sqlite3.Error:pass
            time.sleep(.1)
        raise AssertionError('Saved history did not catch up with complete source lines')
    def stop(process):
        process.terminate();process.wait(timeout=10)
        for _ in range(100):
            try:
                if all(json.loads((data/(c+'-workbench-status.json')).read_text(encoding='utf-8'))['state']=='stopped' for c in ('codex','claude','deepcode')):return
            except (OSError,ValueError):pass
            time.sleep(.1)
        raise AssertionError('Owned collectors remained after launcher exit')
    started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();process=None;halfline=None;checks=0
    with (out/'launch.log').open('wb') as log:
        try:
            process=subprocess.Popen(command,stdout=log,stderr=log)
            for _ in range(100):
                try:
                    if get('current')['cards']:break
                except (OSError,ValueError):pass
                time.sleep(.1)
            else:raise AssertionError('No synthetic chat discovered')
            health=get('health');deadline=time.monotonic()+args.seconds
            with ThreadPoolExecutor(max_workers=3) as pool:
                while time.monotonic()<deadline:
                    if process.poll() is not None:raise AssertionError('Test launcher exited')
                    if halfline:
                        path,tail,session=halfline
                        with path.open('ab') as stream:stream.write(tail)
                        expected[session]+=1;halfline=None
                    for n,(path,session) in enumerate(files):
                        turn='t%d'%checks
                        # Reuse call IDs across chats and turns deliberately.
                        code=1 if (checks+n)%3==0 else 0
                        batch=[row('event_msg',type='task_started',turn_id=turn),
                            row('response_item',type='message',role='user',content=[dict(type='input_text',text='模拟持续检查：检查第%d项保存操作。'%checks)]),
                            row('response_item',type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我正在检查第%d项保存操作。为了避免存不下输入内容，先核对本次检查结果。'%checks)]),
                            row('response_item',type='function_call',call_id='same-call',name='exec_command',arguments=json.dumps(dict(cmd='python3 -m unittest test_save'))),
                            row('response_item',type='function_call_output',call_id='same-call',turn_id=turn,output=json.dumps(dict(exit_code=code))),
                            row('event_msg',type='task_complete',turn_id=turn)]
                        with path.open('ab') as stream:
                            for entry in batch:
                                encoded=(json.dumps(entry,ensure_ascii=False)+'\n').encode()
                                if n==0 and checks%10==0 and entry is batch[-1]:
                                    split=len(encoded)//2;stream.write(encoded[:split]);halfline=(path,encoded[split:],session)
                                else:stream.write(encoded);expected[session]+=1
                        written+=len(batch);completed[session]=checks+1
                    wait_counts()
                    cards=get('current')['cards']
                    for n,(_,session) in enumerate(files):
                        card=next(c for c in cards if c['session_id']==session)
                        params=urlencode(dict(client='codex',key=card['key']))
                        routes=['glance?'+params,'task-summary?'+params,'context?'+params]
                        glance,summary,context=list(pool.map(get,routes))
                        assert str(checks) in glance['content'] and summary['whole_task_status']=='unknown'
                        latest=context['operations'][0]
                        assert latest['status']==('failed' if (checks+n)%3==0 else 'succeeded'), 'Cross-chat/turn result mismatch'
                    samples.append(dict(elapsed=round(time.monotonic()-clock,2),**memory(process.pid)))
                    checks+=1
                    if checks%12==0:
                        (out/'progress.json').write_text(json.dumps(dict(seconds=round(time.monotonic()-clock),cycles=checks,requests=requests,last_memory=samples[-1]))+'\n')
                    time.sleep(min(args.interval,max(0,deadline-time.monotonic())))
            if halfline:
                path,tail,session=halfline
                with path.open('ab') as stream:stream.write(tail)
                expected[session]+=1
            before=wait_counts();stop(process);process=None
            process=subprocess.Popen(command,stdout=log,stderr=log)
            for _ in range(100):
                try:
                    if get('health')==health:break
                except (OSError,ValueError):pass
                time.sleep(.1)
            else:raise AssertionError('Restart failed')
            after=wait_counts();assert before==after
            stop(process);process=None
        except Exception as error:
            failures.append(dict(type=type(error).__name__,message=str(error)))
        finally:
            if process is not None and process.poll() is None:stop(process)
    elapsed=time.monotonic()-clock;steady=samples[5:] or samples
    result=dict(started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),platform=platform.platform(),
        elapsed_seconds=round(elapsed,2),requested_seconds=args.seconds,cycles=checks,http_requests=requests,
        synthetic_only=True,model_calls=0,build=locals().get('health'),failures=failures,
        completed_turns=completed,expected_saved_counts=expected,restart_counts_equal=locals().get('before')==locals().get('after') and 'after' in locals(),
        rss_min_bytes=min((s['rss_bytes'] for s in steady),default=0),rss_max_bytes=max((s['rss_bytes'] for s in steady),default=0),
        max_response_seconds=round(max(latencies,default=0),3),samples=samples,
        limitation='Measured bounded run with simulated activity; not multi-day or real-user acceptance.')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
    return 1 if failures else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);runtime=parser.add_mutually_exclusive_group(required=True)
    runtime.add_argument('--runtime',type=Path);runtime.add_argument('--exe',type=Path)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=int,default=1200);parser.add_argument('--interval',type=float,default=3)
    options=parser.parse_args()
    if not 1<=options.seconds<=86400 or not .1<=options.interval<=60:parser.error('Invalid duration/interval')
    raise SystemExit(run(options))
