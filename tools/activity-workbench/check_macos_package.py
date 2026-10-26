#!/usr/bin/env python3
"""Native Mac acceptance of the released archive, with simulated activity only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlencode
import zipfile


def check(archive, output):
    assert __import__('sys').platform == 'darwin'
    output.mkdir(parents=True,exist_ok=False)
    # Spaces and non-ASCII paths are part of the actual package acceptance.
    unpack=output/'Mac 安装包';unpack.mkdir()
    subprocess.run(['/usr/bin/ditto','-x','-k',str(archive),str(unpack)],check=True)
    app=unpack/'雪绪活动工作台.app'
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
    package=app/'Contents/Resources/workbench'
    runtime=app/'Contents/Resources/runtime/YukioRuntime/YukioRuntime'
    manifest=json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest,name
    assert not any(p.name in ('lan-model.json','page-explanation-policy.json','work-context.json') or p.suffix in ('.sqlite','.jsonl','.log') for p in package.rglob('*'))
    sources=output/'模拟聊天';data=output/'记录'
    for client in ('codex','claude','deepcode'):(sources/client).mkdir(parents=True)
    rows=[dict(type='session_meta',payload=dict(id='mac-synthetic-chat')),
          dict(type='event_msg',payload=dict(type='task_started',turn_id='t')),
          dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='模拟验收：请简化首页，让我工作时一眼看懂。')])),
          dict(type='response_item',payload=dict(type='function_call',call_id='read',name='Read',arguments=json.dumps(dict(file_path='/demo/index.html')))),
          dict(type='response_item',payload=dict(type='function_call_output',call_id='read',output=json.dumps(dict(exit_code=0,content='这是模拟材料。首页有聊天选择、当前工作、操作计数和详细记录。')))),
          dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我正在简化首页。为了让你工作时一眼看懂，先把详细记录收起来。')]))]
    rows += [dict(type='event_msg',payload=dict(type='item_completed',thread_id='mac-synthetic-chat',turn_id='t',item=dict(type='CollabAgentToolCall',id='delegate',tool='spawn_agent',sender_thread_id='mac-synthetic-chat',receiver_thread_ids=['synthetic-helper'],status='completed',prompt='模拟验收：检查按钮文字',agents_states={'synthetic-helper':'running'}))),
             dict(type='event_msg',payload=dict(type='item_completed',thread_id='mac-synthetic-chat',turn_id='t',item=dict(type='CollabAgentToolCall',id='wait',tool='wait',sender_thread_id='mac-synthetic-chat',receiver_thread_ids=['synthetic-helper'],status='completed',agents_states={'synthetic-helper':{'completed':'模拟回复：按钮文字清楚。'}})))]
    child=[dict(type='session_meta',payload=dict(id='synthetic-helper',source=dict(subagent=dict(thread_spawn=dict(parent_thread_id='mac-synthetic-chat'))))),
           dict(type='event_msg',payload=dict(type='task_started',turn_id='helper-turn')),
           dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='模拟验收：检查按钮文字')]))]
    (sources/'codex/helper.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in child),encoding='utf-8')
    source=sources/'codex/demo.jsonl' 
    source.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env=dict(os.environ);env['PATH']='/nonexistent'
    env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
    command=[str(runtime),'--collect','--no-browser','--port',str(port),'--data-dir',str(data),'--source-root',str(sources)]
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(route):
        req=urllib.request.Request('http://127.0.0.1:%d/api/'%port+route,headers={'X-Yukio-Workbench':'1'})
        with opener.open(req,timeout=2) as response:return json.load(response)
    def stopped():
        for _ in range(100):
            try:
                if all(json.loads((data/(c+'-workbench-status.json')).read_text())['state']=='stopped' for c in ('codex','claude','deepcode')):return
            except (ValueError,OSError):pass
            time.sleep(.05)
        raise AssertionError('Packaged recorders did not stop')
    saved=[]
    for attempt in range(2):
        with (output/('launch-%s.log'%attempt)).open('wb') as log:
            process=subprocess.Popen(command,env=env,stdout=log,stderr=log)
            try:
                for _ in range(150):
                    if process.poll() is not None:raise AssertionError('Packaged launcher exited early; see launch log')
                    try:
                        cards=get('current')['cards']
                        if cards:break
                    except (OSError,ValueError):pass
                    time.sleep(.1)
                else:raise AssertionError('No synthetic chat observed')
                card=next(c for c in cards if c['session_id']=='mac-synthetic-chat');detail=get('glance?'+urlencode(dict(client='codex',key=card['key'])))
                assert '简化首页' in detail['content'] and '一眼看懂' in detail['reason']
                assert detail['explanation_basis']=='inference' and '调整' in detail['explanation']
                assert detail['part_evidence']['reason']
                assert '模拟验收' in detail['goal_short']
                assert detail['last_step']['action']=='请求查看 相关页面'
                assert '.html' not in detail['last_step']['action']
                assert detail['last_step']['result']=='这次操作报告成功'
                assert cards[0]['session_id']=='mac-synthetic-chat' and not cards[0]['is_helper']
                context=get('context?'+urlencode(dict(client='codex',key=card['key'])))
                assert context['status_counts']=={'succeeded':1}
                handoffs=get('handoffs?'+urlencode(dict(client='codex',key=card['key'])))
                assert len(handoffs['items'])==2 and handoffs['items'][0]['returns'][0]['text']=='模拟回复：按钮文字清楚。'
                assert '完全相同' in handoffs['items'][1]['targets'][0]['input_note']
                summary=get('task-summary?'+urlencode(dict(client='codex',key=card['key'])))
                assert summary['whole_task_status']=='unknown' and '简化首页' in summary['goal']['text']
                assert len(summary['handoffs'])==2 and summary['handoffs'][0]['receivers'][0]['reply']=='模拟回复：按钮文字清楚。'
                assert '尚未确认' in summary['handoffs'][0]['adoption']
                reuse=subprocess.run(command,env=env,capture_output=True,text=True,timeout=8)
                assert reuse.returncode==0, 'Opening the same packaged workbench failed'
                saved.append(next(c['saved_records'] for c in get('clients')['clients'] if c['id']=='codex'))
                with opener.open('http://127.0.0.1:%d/'%port,timeout=2) as response:
                    page=response.read().decode('utf-8');assert '千问说明会自动显示在下方' in page and 'id="explain"' not in page and 'id="stopAuto"' not in page
            finally:
                process.kill();process.wait(timeout=5);stopped()
    assert saved[0]==saved[1]==len(rows)+len(child)
    result=dict(platform=platform.platform(),native_macos=True,package_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),manifest_files=len(manifest['files']),all_hashes_match=True,no_private_data_in_package=True,python_removed_from_path=True,unicode_space_path_passed=True,collector_history_context_page_passed=True,handoff_request_input_return_passed=True,task_and_handoff_summary_passed=True,forced_exit_stops_owned_collectors=True,restart_record_count=saved,synthetic_only=True,real_model_called=False,signature_valid=True,standalone_runtime=True,reopening_existing_service_passed=True)
    (output/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',required=True,type=Path);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    print(json.dumps(check(args.archive.resolve(),args.out.resolve())))
