#!/usr/bin/env python3
"""Local launcher: existing collector ownership is respected; no automatic model call."""
import argparse
import errno
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from runtime_identity import identity
from server import create_server
from explanation import load_config
from agent_explanation import configuration

ROOT=Path(__file__).resolve().parent
CLIENTS=('codex','claude','deepcode')

def ready(port):
    url='http://127.0.0.1:%d/'%port
    print('YUKIO_WORKBENCH_READY '+json.dumps({'url':url}),flush=True)
    return url

def startup_error(code):
    # Stable, non-sensitive codes for the native host. Never serialize config,
    # conversation contents or exception messages into the diagnostic protocol.
    print('YUKIO_WORKBENCH_ERROR '+json.dumps({'code':code}),file=sys.stderr,flush=True)

def default_directory():
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/YukioPlayer/activity-observation'
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Yukio/activity-observation'
    return Path.home()/'.local/share/yukio/activity-observation'

def core_path():
    packaged=ROOT/'core'
    return packaged if packaged.is_dir() else ROOT.parents[1]/'YukioWin'

def databases_for(directory):return {client:directory/(client+'-activity-history-v1.sqlite') for client in CLIENTS}

def check_existing(port,databases,model_config=None):
    req=urllib.request.Request('http://127.0.0.1:%d/api/health'%port,headers={'X-Yukio-Workbench':'1'})
    try:
        # Health checks target a fixed loopback HTTP URL. Avoid initializing
        # platform TLS/certificate stores on every startup or readiness poll.
        opener=urllib.request.OpenerDirector()
        for handler in (urllib.request.HTTPHandler(),urllib.request.HTTPDefaultErrorHandler(),urllib.request.HTTPErrorProcessor()):
            opener.add_handler(handler)
        with opener.open(req,timeout=1) as r:raw=r.read(8193)
        if len(raw)>8192:return 'different'
        data=json.loads(raw)
        return 'same' if data==identity(databases,model_config) else 'different'
    except Exception as error:
        if os.environ.get('YUKIO_DIAGNOSTICS')=='1':
            print('Existing service check: '+type(error).__name__+' '+str(getattr(error,'name',getattr(error,'errno',''))),file=sys.stderr)
        return 'unavailable'

def inspect(directory):
    from history_view import HistoryView
    databases=databases_for(directory)
    data=HistoryView(databases).clients()
    data.pop('explanation',None)
    data['python_supported']=sys.version_info>=(3,9)
    data['collector_code_available']=(core_path()/'yukio/activity_collector_cli.py').is_file()
    data['model_config_present']=(directory/'lan-model.json').is_file()
    return data

def main(argv=None):
    # Frozen Windows builds may use the system's legacy code page even when
    # PYTHONUTF8 is set. Status text must not prevent a healthy service starting.
    for stream in (sys.stdout,sys.stderr):
        if callable(getattr(stream,'reconfigure',None)):
            stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=default_directory())
    parser.add_argument('--port',type=int,default=8767,help='Loopback port; 0 lets the OS reserve an available port')
    parser.add_argument('--fallback-port',action='store_true',help='Use an available loopback port if the preferred port is occupied')
    parser.add_argument('--collect',action='store_true',help='Collect supported recent local activity; no model transmission')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--check',action='store_true',help='Read-only readiness report')
    parser.add_argument('--source-root',type=Path,help='Optional source parent containing codex, claude and deepcode directories')
    parser.add_argument('--collector',choices=CLIENTS,help=argparse.SUPPRESS)
    parser.add_argument('--parent-stdin',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if not 0<=args.port<=65535:parser.error('Port must be 0..65535')
    directory=args.data_dir.absolute();databases=databases_for(directory)
    if args.check:print(json.dumps(inspect(directory),ensure_ascii=False));return 0
    if args.collector:
        sys.path.insert(0,str(core_path()))
        from yukio.activity_collector_cli import run_activity_collector
        collector_args=['--activity-collect',str(databases[args.collector]),'--source-format',args.collector,'--status-file',str(directory/(args.collector+'-workbench-status.json'))]
        if args.source_root:collector_args+=['--sessions-dir',str(args.source_root.absolute()/args.collector)]
        if args.parent_stdin:collector_args+=['--parent-stdin']
        return run_activity_collector(collector_args)
    try:config=configuration(directory)
    except (OSError,ValueError):
        startup_error('invalid_configuration')
        print('模型配置需要检查；未启动新服务。',file=sys.stderr);return 1
    existing=check_existing(args.port,databases,config) if args.port else 'unavailable'
    if existing=='same' and not args.collect:
        url=ready(args.port)
        print('本机工作台已在运行，继续使用现有服务。',flush=True)
        if not args.no_browser:webbrowser.open(url)
        return 0
    if existing=='different' and not args.fallback_port:
        startup_error('port_in_use')
        print('这个端口已有不同版本或不同记录目录的服务。请关闭该服务或换一个端口；没有替换现有进程。',file=sys.stderr);return 1
    children=[];server=None;old_handlers={}
    try:
        # A fast exit during startup must still release our newly started children.
        def stop(*_):raise KeyboardInterrupt
        for sig in (signal.SIGINT,signal.SIGTERM):old_handlers[sig]=signal.signal(sig,stop)
        if args.parent_stdin:
            # The native App owns this pipe. Abrupt App exit closes it; stop only
            # this launcher and the collector processes in our children list.
            def watch_parent():
                try:
                    while os.read(sys.stdin.fileno(),1):pass
                except (OSError,ValueError):pass
                os.kill(os.getpid(),signal.SIGTERM)
            threading.Thread(target=watch_parent,daemon=True).start()
        # Reserve the port before creating databases or starting child collectors.
        roots={c:args.source_root.absolute()/c for c in CLIENTS} if args.source_root else None
        if existing!='same':
            try:
                server=create_server(0 if existing=='different' else args.port,databases,model_config=config,source_roots=roots)
            except OSError as error:
                if not args.fallback_port or error.errno!=errno.EADDRINUSE:raise
                # The OS reserves the new port atomically; never stop or reuse an
                # unrelated service, including a stale build from another App.
                server=create_server(0,databases,model_config=config,source_roots=roots)
        if args.collect:
            sys.path.insert(0,str(core_path()))
            from yukio.activity_collector_cli import CollectorLease
            directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            for client,database in databases.items():
                try:lease=CollectorLease(database)
                except ValueError:
                    print(client+'：沿用已有记录器。',flush=True);continue
                lease.close()
                command=([sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-B',str(ROOT/'launcher.py')])
                command+=['--data-dir',str(directory),'--collector',client,'--parent-stdin']
                if args.source_root:command+=['--source-root',str(args.source_root.absolute())]
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                                         stderr=None if os.environ.get('YUKIO_DIAGNOSTICS')=='1' else subprocess.DEVNULL,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                children.append(process)
            time.sleep(.25)
            if any(p.poll() is not None for p in children):
                print('部分新记录器未启动；请检查记录器状态。已有历史仍可查看。',flush=True)
        url=ready(server.server_port if server else args.port)
        print('Yukio 活动工作台 '+url+'\n关闭此启动窗口或按 Ctrl-C 停止本次启动的服务；不会停止已有记录器。',flush=True)
        if not args.no_browser:webbrowser.open(url)
        if server:server.serve_forever()
        elif children:
            # A live read-only page does not imply that its collectors are alive.
            print('本机页面已在运行；本窗口接续缺少的记录器。',flush=True)
            while True:time.sleep(.5)
        else:print('本机工作台和记录器已在运行，继续使用现有服务。',flush=True)
    except KeyboardInterrupt:pass
    except (OSError,ValueError,ImportError) as error:
        startup_error('port_in_use' if isinstance(error,OSError) and error.errno==errno.EADDRINUSE else
                      'data_unavailable' if isinstance(error,(OSError,ValueError)) else 'runtime_unavailable')
        print('无法启动；请检查端口、Python 环境或本机记录目录。已有数据未被替换。',file=sys.stderr);return 1
    finally:
        if server:server.server_close()
        for process in children:
            if process.stdin:process.stdin.close()
        for process in children:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=5)
                print('本次记录器未及时响应，已停止；下次启动会检查保存位置。',file=sys.stderr)
        for sig,handler in old_handlers.items():signal.signal(sig,handler)
    return 0

if __name__=='__main__':sys.exit(main())
