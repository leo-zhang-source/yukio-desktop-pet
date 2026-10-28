#!/usr/bin/env python3
"""Check a frozen runtime on its native OS using isolated, offline CLI fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

from test_workbench import fixture
from history_view import key_for


def check(runtime, output):
    node = shutil.which('node')
    if not node:
        raise ValueError('Node is required for the offline test clients')
    output.mkdir(parents=True, exist_ok=False)
    results = []
    with tempfile.TemporaryDirectory(prefix='Yukio 通用 Agent & ') as folder:
        root = Path(folder)
        clients = root/'Clients 中文'
        clients.mkdir()
        paths = {}
        javascript = '''const fs=require('node:fs');const args=process.argv.slice(2);
const trace=kind=>fs.appendFileSync(process.env.YUKIO_TEST_TRACE,kind+'\\n');
if(args.includes('--help')){
 trace('help');console.log('--ignore-user-config --ephemeral --skip-git-repo-check --sandbox --color --output-schema --output-last-message --print --safe-mode --output-format --no-session-persistence --tools --disable-slash-commands --strict-mcp-config --mcp-config --system-prompt --json-schema\\nCommands:\\n  auth Manage authentication');
}else if(args[0]==='login'&&args[1]==='status'){trace('auth');console.log('Logged in using a TEST account');}
else if(args[0]==='auth'&&args[1]==='status'){trace('auth');console.log(JSON.stringify({loggedIn:true}));}
else{
 trace('generate');
 let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',part=>input+=part);
 process.stdin.on('end',()=>{
  const payload=JSON.parse(args[0]==='exec'?input.slice(input.indexOf('{"facts"')):input);
  const answer={explanations:payload.facts.map(f=>({evidence_id:f.evidence_id,text:'这是一条测试客户端返回的说明。'}))};
  if(args[0]==='exec')fs.writeFileSync(args[args.indexOf('--output-last-message')+1],JSON.stringify(answer),'utf8');
  else console.log(JSON.stringify({subtype:'success',is_error:false,structured_output:answer}));
 });
}
'''
        for provider, package in [('codex','@openai/codex/bin/codex.js'),
                                  ('claude','@anthropic-ai/claude-code/cli.js')]:
            if os.name == 'nt':
                path = clients/(provider+'.cmd')
                path.write_text('Do not execute this shim through a shell.\n', encoding='utf-8')
                script = clients/'node_modules'/package
                script.parent.mkdir(parents=True, exist_ok=True)
                script.write_text(javascript, encoding='utf-8')
            else:
                path = clients/provider
                path.write_text('#!'+node+'\n'+javascript, encoding='utf-8')
                path.chmod(0o700)
            paths[provider] = path
        for provider in ('codex','claude'):
            data = root/provider
            data.mkdir()
            fixture(data/'codex-activity-history-v1.sqlite')
            (data/'explanation-provider.json').write_text(json.dumps(dict(provider=provider,automatic_on_open=False)), encoding='utf-8')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
            env = dict(os.environ, PATH=str(root/'no-python-or-node-on-path'),
                       NVM_SYMLINK=str(Path(node).parent), YUKIO_CODEX_PATH=str(paths['codex']),
                       YUKIO_CLAUDE_PATH=str(paths['claude']),YUKIO_TEST_TRACE=str(data/'invocations.txt'))
            env['YUKIO_DIAGNOSTICS']='1'
            # Test fixtures have no account, private model configuration or API.
            env['CODEX_HOME'] = str(root/'empty-codex-home')
            log_path = output/(provider+'-runtime.log')
            with log_path.open('wb') as log:
                process = subprocess.Popen([str(runtime),'--no-browser','--data-dir',str(data),'--port',str(port)],
                    env=env,stdout=log,stderr=log)
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                def api(route, payload=None):
                    headers = {'X-Yukio-Workbench':'1'}
                    if payload is not None:headers['Content-Type']='application/json'
                    request = urllib.request.Request('http://127.0.0.1:%d/api/'%port+route,
                        data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
                    with opener.open(request,timeout=20) as response:return json.load(response)
                try:
                    for _ in range(120):
                        if process.poll() is not None:
                            log.flush()
                            raise AssertionError('Frozen runtime exited; offline fixture log:\n'+log_path.read_text(encoding='utf-8',errors='replace')[-8000:])
                        try:info=api('clients');break
                        except OSError:time.sleep(.1)
                    else:raise AssertionError('Frozen runtime did not start')
                    assert info['explanation']['provider']==provider
                    assert not info['explanation']['automatic_on_open']
                    preview=api('explanation-preview',dict(client='codex',key=key_for(['file-a',2,'demo-chat-a','',0]),sequence=2))
                    result=api('explanation-generate',dict(token=preview['token'],consent=True))
                    assert result['mode']=='model',result
                    assert result['model']==('Codex' if provider=='codex' else 'Claude Code')
                    assert result['explanations'][0]['text']=='这是一条测试客户端返回的说明。'
                    assert (data/'invocations.txt').read_text().splitlines()==['help','auth','generate']
                    results.append(dict(provider=provider,help_login_and_generation_protocol=True,
                        unicode_space_paths=True,python_and_node_removed_from_path=True,real_account_used=False))
                finally:
                    process.terminate();process.wait(timeout=10)
    report=dict(platform=platform.platform(),native_platform=__import__('sys').platform,
        runtime_sha256=hashlib.sha256(runtime.read_bytes()).hexdigest(),offline_clients=True,
        real_generation_verified=False,checks=results)
    (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(check(args.runtime.resolve(),args.out.resolve()),ensure_ascii=False))
