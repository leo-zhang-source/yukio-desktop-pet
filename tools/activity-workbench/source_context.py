"""Bounded, transient excerpts from exact locally saved source evidence.

No arbitrary-path HTTP API; no transcript copies, reasoning, or raw tool output.
A changed/missing source cannot supply content for an old saved event.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import stat
from contextlib import closing
import threading
import time

MAX_LINE = 256 * 1024
MAX_READ = 2 * 1024 * 1024


def default_roots():
    home = Path.home()
    return {key:Path(os.environ.get(env, str(home/name)))/child for key,env,name,child in (
        ('codex','CODEX_HOME','.codex','sessions'),('claude','CLAUDE_CONFIG_DIR','.claude','projects'),
        ('deepcode','DEEPCODE_CONFIG_DIR','.deepcode','projects'))}


def clean(text, limit=360):
    if not isinstance(text,str):return ''
    text=text[:16000]
    text=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)','[已隐藏密钥]',text,flags=re.S)
    text=re.sub(r'(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{16,}|Bearer\s+\S+)','[已隐藏凭据]',text)
    text=re.sub(r'(?i)((?:api[_ -]?key|password|passwd|secret|access[_ -]?token)\s*["\x27]?\s*[:=]\s*)[^\s,;]+',r'\1[已隐藏]',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[邮箱]',text)
    text=re.sub(r'https?://[^\s<>]+','[链接]',text)
    text=re.sub(r'(?:/Users/|/home/)[^\s/]+/','~/',text)
    text=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[网络地址]',text)
    text=re.sub(r'```.*?(?:```|$)','[代码略]',text,flags=re.S)
    text=re.sub(r'[\x00-\x08\x0b-\x1f\x7f]','',text)
    text=re.sub(r'[\n\r\t ]+',' ',text).strip(' #*`')
    return text[:limit] + ('…' if len(text)>limit else '')


def user_text(text):
    if not isinstance(text,str):return ''
    if text.lstrip().startswith('<send_user_message_question_reply>'):
        # These are visible human answers, not ambient app instructions. Keep
        # the answer only; opaque question IDs and the app wrapper stay out.
        match=re.fullmatch(r'\s*<send_user_message_question_reply>\s*(.*?)\s*</send_user_message_question_reply>\s*',text,flags=re.S)
        if not match:return ''
        try:answers=json.loads(match[1])
        except (ValueError,RecursionError):return ''
        if not isinstance(answers,list):return ''
        consent_choices={'同意，开启本页当前聊天的自动说明','同意，只解释预览中的这一步','暂不发送，只用本机说明'}
        return clean('；'.join(a['answer'] for a in answers[:3] if isinstance(a,dict) and isinstance(a.get('answer'),str) and a['answer'] not in consent_choices),480)
    if '## My request:' in text:text=text.rsplit('## My request:',1)[1]
    elif text.lstrip().startswith(('# AGENTS.md instructions','<environment_context>','<send_user_message_question_reply>','<external_codex_apps_open_page>')):return ''
    text=re.sub(r'<(?:in-app-browser-context|environment_context|app-context|INSTRUCTIONS)\b[^>]*>.*?</(?:in-app-browser-context|environment_context|app-context|INSTRUCTIONS)>','',text,flags=re.S)
    # App mentions are visible labels; their installation URLs are not the
    # user's goal and must not consume the short request shown on the homepage.
    text=re.sub(r'\[(@[^\]\n]+)\]\(plugin://[^\s)]+\)',r'\1',text)
    if len(text)>480:
        goal=re.search(r'(?im)^#{0,3}\s*(?:[一二三四五六七八九十\d]+[、.：:]\s*)?(?:总体开发目标|项目目标|最终目标|goal|objective)[^\n]*\n',text)
        if goal:
            section=re.split(r'\n#{1,3}\s',text[goal.end():],maxsplit=1)[0]
            return clean(text[:180]+'；主要目标：'+section[:550],800)
    return clean(text,480)


def text_blocks(content):
    if isinstance(content,str):return content
    if not isinstance(content,list):return ''
    return '\n'.join(b.get('text','') for b in content[:100] if isinstance(b,dict) and b.get('type') in ('text','input_text','output_text') and isinstance(b.get('text'),str))


def filename(value):
    if not isinstance(value,str):return ''
    return clean(value.replace('\\','/').rstrip('/').rsplit('/',1)[-1],80)


def operation(name,arguments):
    """Explain only explicit arguments. Never execute commands or expose raw code."""
    if not isinstance(name,str):return None
    if isinstance(arguments,str):
        try:args=json.loads(arguments)
        except ValueError:args={}
    else:args=arguments
    if not isinstance(args,dict):args={}
    short=name.rsplit('.',1)[-1].lower()
    if short=='exec' and isinstance(arguments,str):
        patch=script_patch(arguments)
        if patch:return '脚本提出修改 '+ '、'.join(patch['targets'])+'（还需核对实际结果）'
    if short=='exec' and isinstance(arguments,str) and 'tools.exec_command(' in arguments:
        targets=script_targets(arguments)
        if targets:return '请求执行一组步骤，涉及 '+ '、'.join(targets)+'（尚未单独确认其中的步骤）'
    if name in ('mcp__cua_repl.js','mcp__node_repl.js') and isinstance(args.get('title'),str) and clean(args['title']):
        return '助手标注：'+clean(args['title'],96)
    target=next((filename(args.get(k)) for k in ('file_path','path','target_file','file') if filename(args.get(k))), '')
    if short in ('read','read_file','view_image') and target:return '请求查看 '+target
    if short in ('write','write_file','edit','edit_file') and target:return '请求修改 '+target
    if short=='apply_patch' and isinstance(arguments,str):
        names=[filename(s) for s in re.findall(r'^\*\*\* (?:Update|Add|Delete) File: (.+)$',arguments,re.M)][:3]
        if names:return '请求修改 '+ '、'.join(names)
    if short in ('spawn_agent','delegate','task'):
        task=clean(args.get('description') or args.get('message') or args.get('prompt'),100)
        if task:return '交给协助助手：'+task
    if short in ('run','search','web_search'):
        queries=args.get('search_query',[])
        if isinstance(queries,list) and queries and isinstance(queries[0],dict):
            query=clean(queries[0].get('q'),100)
            if query:return '搜索：'+query
    command=args.get('cmd') or args.get('command')
    if not isinstance(command,str) and short in ('exec','js'):
        code=args.get('code') if isinstance(args.get('code'),str) else arguments if isinstance(arguments,str) else ''
        # Only explicit JSON string command values, not arbitrary source strings.
        m=re.search(r'\bcmd\s*:\s*("(?:\\.|[^"\\])*")',code)
        if m:
            try:command=json.loads(m[1])
            except ValueError:pass
    if isinstance(command,str):
        # A script body is not evidence that its branches or embedded commands ran.
        if '\n' in command or re.search(r'[<>;|&`]|\$\(',command):return None
        try:tokens=shlex.split(command[:3000])
        except ValueError:return None
        if not tokens:return None
        executable=tokens[0].rsplit('/',1)[-1]
        if executable in ('pytest','pytest3') or executable.startswith('python') and tokens[1:3]==['-m','unittest'] or executable in ('swift','npm','pnpm','cargo') and tokens[1:2]==['test']:
            return '请求运行测试，检查改动是否正常'
        if executable in ('swift','npm','pnpm','cargo') and (tokens[1:2]==['build'] or tokens[1:3]==['run','build']):return '请求构建程序，检查能否正常生成'
        if executable in ('cat','sed','rg','head','tail'):
            names=[]
            for token in tokens:
                if re.fullmatch(r'[\w./ -]+\.(?:py|swift|js|ts|tsx|json|md|html|css)',token):
                    name=filename(token)
                    if name not in names:names.append(name)
            if names:return '请求查看 '+ '、'.join(names[:3])+(' 等文件' if len(names)>3 else '')
            return '请求查找项目中的相关内容'
    return None


def script_targets(code):
    """Objects named in explicit command strings, not claims of executed actions."""
    targets=[]
    for literal in re.findall(r'\bcmd\s*:\s*("(?:\\.|[^"\\])*")',code[:24000])[:8]:
        try:command=json.loads(literal)
        except ValueError:continue
        for match in re.findall(r'(?:[\w./-]+/)?[\w.-]+\.(?:py|swift|js|ts|tsx|json|md|html|css)\b',command):
            name=filename(match)
            if name and name not in targets:targets.append(name)
            if len(targets)==3:return targets
    return targets


def script_patch(code):
    match=re.search(r'\btools\.apply_patch\(\s*("(?:\\.|[^"\\])*")',code[:24000])
    if not match:return None
    try:patch=json.loads(match[1])
    except (ValueError,RecursionError):return None
    targets=[filename(s) for s in re.findall(r'^\*\*\* (?:Update|Add|Delete) File: (.+)$',patch,re.M)][:3]
    if not targets:return None
    changes=[line for line in patch.splitlines() if line.startswith(('+','-')) and not line.startswith(('+++','---'))]
    return dict(targets=targets,excerpt=clean('\n'.join(changes),600))


def returned_text(value):
    """Public text only. Ignore images, wrapper timing and nested metadata."""
    if not isinstance(value,list):return text_blocks(value)
    pieces=[]
    for block in value[:30]:
        if not isinstance(block,dict) or block.get('type') not in ('text','input_text','output_text'):continue
        text=block.get('text')
        if not isinstance(text,str):continue
        if re.fullmatch(r'Script (?:completed|running).*?Output:\s*',text,flags=re.S):continue
        try:obj=json.loads(text)
        except (ValueError,RecursionError):obj=None
        if isinstance(obj,dict) and isinstance(obj.get('output'),str):
            text=obj['output']
            if type(obj.get('exit_code')) is int:text='其中一项返回退出码 '+str(obj['exit_code'])+'；'+text
        if text.strip():pieces.append(text)
        if sum(len(p) for p in pieces)>1600:break
    return '\n'.join(pieces)


def extract(client, obj):
    """Return public user/assistant speech and explicit operation objects only."""
    out=[]
    if client=='codex':
        p=obj.get('payload') if isinstance(obj.get('payload'),dict) else obj
        kind=p.get('type',obj.get('type'));role=p.get('role');phase=p.get('phase') or p.get('channel')
        if kind=='message' and phase in (None,'','commentary','final','final_answer'):
            text=text_blocks(p.get('content'))
            if role=='user':text=user_text(text)
            elif role=='assistant':text=clean(text,400)
            else:text=''
            if text:out.append((role,text))
        elif kind in ('user_message','agent_message') and phase in (None,'','commentary','final','final_answer'):
            role='user' if kind=='user_message' else 'assistant'
            text=user_text(p.get('message')) if role=='user' else clean(p.get('message'),400)
            if text:out.append((role,text))
        elif kind in ('function_call','custom_tool_call'):
            name=p.get('name');namespace=p.get('namespace')
            if isinstance(name,str) and isinstance(namespace,str) and namespace and '.' not in name:name=namespace+'.'+name
            text=operation(name,p.get('arguments',p.get('input')))
            if text:out.append(('operation_note' if text.startswith('助手标注：') else 'operation',text))
    elif client=='claude':
        role=obj.get('type');msg=obj.get('message',{})
        if obj.get('isMeta') or obj.get('isCompactSummary') or not isinstance(msg,dict):return []
        if role not in ('user','assistant') or msg.get('role',role)!=role:return []
        content=msg.get('content');text=text_blocks(content)
        text=user_text(text) if role=='user' else clean(text,400)
        if text:out.append((role,text))
        for block in content[:100] if isinstance(content,list) else []:
            if isinstance(block,dict) and block.get('type')=='tool_use':
                text=operation(block.get('name'),block.get('input'))
                if text:out.append(('operation',text))
    elif client=='deepcode':
        role=obj.get('role');meta=obj.get('meta',{});params=obj.get('messageParams',{})
        if obj.get('compacted') or isinstance(meta,dict) and meta.get('isSummary'):return []
        if role in ('user','assistant'):
            text=text_blocks(obj.get('content'))
            text=user_text(text) if role=='user' else clean(text,400)
            if text:out.append((role,text))
        if role=='assistant' and isinstance(params,dict):
            for call in (params['tool_calls'][:50] if isinstance(params.get('tool_calls'),list) else []):
                if isinstance(call,dict) and isinstance(call.get('function'),dict):
                    f=call['function'];text=operation(f.get('name'),f.get('arguments'))
                    if text:out.append(('operation',text))
    return out


def tool_material(client,obj):
    """Only explicit read requests and their returned text; linking happens elsewhere."""
    requests=[];receipts=[]
    def request(call,name,args):
        if not isinstance(call,str) or not isinstance(name,str):return
        if name.rsplit('.',1)[-1].lower() not in ('read','read_file'):return
        if isinstance(args,str):
            try:args=json.loads(args)
            except ValueError:return
        if not isinstance(args,dict):return
        target=next((filename(args.get(k)) for k in ('file_path','path','target_file','file') if filename(args.get(k))), '')
        if target:requests.append(dict(call_id=call,target=target))
    def receipt(call,value):
        if not isinstance(call,str):return
        if isinstance(value,str):
            try:parsed=json.loads(value)
            except ValueError:parsed=None
            if isinstance(parsed,dict):value=parsed
        if isinstance(value,dict):value=value.get('content',value.get('output',''))
        text=clean(returned_text(value),600)
        if text:receipts.append(dict(call_id=call,text=text))
    if client=='codex':
        p=obj.get('payload',{});kind=p.get('type') if isinstance(p,dict) else None
        if kind=='function_call':request(p.get('call_id'),p.get('name'),p.get('arguments'))
        if kind=='function_call' and isinstance(p.get('name'),str) and p['name'].rsplit('.',1)[-1]=='exec_command' and isinstance(p.get('call_id'),str):
            args=p.get('arguments',{})
            if isinstance(args,str):
                try:args=json.loads(args)
                except (ValueError,RecursionError):args={}
            if isinstance(args,dict) and isinstance(args.get('cmd'),str):requests.append(dict(call_id=p['call_id'],target=operation(p['name'],args) or '这次命令',material_kind='tool_output'))
        if kind=='function_call_output':receipt(p.get('call_id'),p.get('output'))
        if kind=='custom_tool_call' and p.get('name') in ('exec','functions.exec') and isinstance(p.get('input'),str) and isinstance(p.get('call_id'),str):
            patch=script_patch(p['input'])
            if patch:requests.append(dict(call_id=p['call_id'],target='、'.join(patch['targets']),material_kind='proposal',excerpt=patch['excerpt']))
            elif 'tools.exec_command(' in p['input']:
                targets=script_targets(p['input'])
                requests.append(dict(call_id=p['call_id'],target='、'.join(targets) if targets else '这组步骤',material_kind='tool_output'))
        if kind=='custom_tool_call_output':receipt(p.get('call_id'),p.get('output'))
    elif client=='claude':
        msg=obj.get('message',{});blocks=msg.get('content',[]) if isinstance(msg,dict) else []
        for block in blocks[:100] if isinstance(blocks,list) else []:
            if not isinstance(block,dict):continue
            if block.get('type')=='tool_use':request(block.get('id'),block.get('name'),block.get('input'))
            if block.get('type')=='tool_result':receipt(block.get('tool_use_id'),block.get('content'))
    elif client=='deepcode':
        params=obj.get('messageParams',{})
        if isinstance(params,dict):
            if obj.get('role')=='assistant':
                for call in (params['tool_calls'][:50] if isinstance(params.get('tool_calls'),list) else []):
                    if isinstance(call,dict) and isinstance(call.get('function'),dict):
                        f=call['function'];request(call.get('id'),f.get('name'),f.get('arguments'))
            elif obj.get('role')=='tool':receipt(params.get('tool_call_id'),obj.get('content'))
    return requests,receipts


def handoff_material(obj):
    """Public delegation input and completed replies only, never agent reasoning."""
    p=obj.get('payload',obj);out=dict(sent='',returns={})
    if not isinstance(p,dict):return out
    kind=p.get('type',obj.get('type'))
    if kind=='function_call':
        args=p.get('arguments',{})
        if isinstance(args,str):
            try:args=json.loads(args)
            except (ValueError,RecursionError):args={}
        if isinstance(args,dict):out['sent']=clean(args.get('message',args.get('prompt')),240)
    elif kind=='function_call_output':
        value=p.get('output',{})
        if isinstance(value,str):
            try:value=json.loads(value)
            except (ValueError,RecursionError):value={}
        if isinstance(value,dict):
            ss=value.get('status',{})
            if isinstance(ss,dict):out['returns']={k:clean(v['completed'],360) for k,v in list(ss.items())[:32] if isinstance(k,str) and isinstance(v,dict) and isinstance(v.get('completed'),str)}
    else:
        item=p.get('item',{})
        if isinstance(item,dict) and item.get('type')=='CollabAgentToolCall':
            out['sent']=clean(item.get('prompt'),240);ss=item.get('agents_states',{})
        elif kind in ('collab_agent_spawn_end','collab_agent_interaction_end','collab_waiting_end','collab_agent_spawn_begin','collab_agent_interaction_begin'):
            out['sent']=clean(p.get('prompt'),240)
            ss=p.get('statuses',{}) if kind=='collab_waiting_end' else {p.get('new_thread_id',p.get('receiver_thread_id','')):p.get('status')}
        else:ss={}
        if isinstance(ss,dict):out['returns']={k:clean(v['completed'],360) for k,v in list(ss.items())[:32] if isinstance(k,str) and isinstance(v,dict) and isinstance(v.get('completed'),str)}
    return out


class SourceContext:
    def __init__(self,roots=None):
        self.roots={k:Path(v).resolve() for k,v in (default_roots() if roots is None else roots).items()}
        self.paths={};self.scan_at={};self.lock=threading.Lock()

    def permitted(self,path,client,source):
        root=self.roots.get(client)
        if root is None:return False
        try:
            p=Path(path)
            return not p.is_symlink() and p.resolve().is_relative_to(root) and hashlib.sha256(str(p.resolve()).encode()).hexdigest()==source
        except (OSError,ValueError):return False

    def title_and_path(self,client,session,source):
        title='';path=None;root=self.roots.get(client)
        if root is None:return title,path
        if client=='codex':
            # The local index is already used by Yukio's existing Codex source.
            index=root.parent/'session_index.jsonl'
            try:
                with index.open('rb') as f:
                    raw=f.read(2*1024*1024+1)
                if len(raw)<=2*1024*1024:
                    for line in raw.splitlines():
                        try:row=json.loads(line)
                        except ValueError:continue
                        if isinstance(row,dict) and row.get('id')==session and isinstance(row.get('thread_name'),str):title=clean(row['thread_name'],100)
            except OSError:pass
            state=root.parent/'state_5.sqlite'
            try:
                with closing(sqlite3.connect(state.as_uri()+'?mode=ro',uri=True,timeout=.2)) as db:
                    db.execute('PRAGMA query_only=ON')
                    db.set_progress_handler(lambda:1 if time.monotonic()>deadline else 0,1000)
                    deadline=time.monotonic()+.2
                    row=db.execute('SELECT title,rollout_path FROM threads WHERE id=? LIMIT 1',(session,)).fetchone()
                    if row:
                        if not title:title=clean(user_text(row[0]).split('。')[0],100)
                        if self.permitted(row[1],client,source):path=Path(row[1])
            except (sqlite3.Error,OSError,ValueError):pass
        if path is None:
            with self.lock:
                if time.monotonic()-self.scan_at.get(client,-100)<30:path=self.paths.get((client,source))
                else:
                    count=0;deadline=time.monotonic()+.7
                    for directory,dirs,files in os.walk(root,followlinks=False):
                        dirs[:]=sorted(d for d in dirs if d not in ('backup','backups','images','node_modules','.git') and not Path(directory,d).is_symlink())
                        for name in files:
                            count+=1
                            if count>6000 or time.monotonic()>deadline:break
                            if not name.endswith('.jsonl'):continue
                            p=Path(directory,name)
                            if p.is_symlink():continue
                            digest=hashlib.sha256(str(p.resolve()).encode()).hexdigest();self.paths[(client,digest)]=p
                        if count>6000 or time.monotonic()>deadline:break
                    self.scan_at[client]=time.monotonic();path=self.paths.get((client,source))
        return title,path

    def read(self,client,parts,state,rows):
        title,path=self.title_and_path(client,parts[2],parts[0]);out=[];missing=0;used=0;requests=[];receipts=[];handoffs=[]
        if not path or not self.permitted(path,client,parts[0]):return dict(title=title,items=[],unavailable=True,missing=0)
        if state.get('generation')!=parts[1]:return dict(title=title,items=[],unavailable=True,missing=0)
        descriptor=None
        try:
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            with os.fdopen(descriptor,'rb') as stream:
                descriptor=None;info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or state.get('file_identity')!='%s:%s'%(info.st_dev,info.st_ino):
                    return dict(title=title,items=[],unavailable=True,missing=0)
                for seq,row in rows:
                    start,end=row.get('source_offset'),row.get('next_offset');expected=row.get('source_record_sha256')
                    if type(start) is not int or type(end) is not int or not expected or not 0<=start<end<=info.st_size:continue
                    length=end-start
                    if length>MAX_LINE or used+length>MAX_READ:missing+=1;continue
                    stream.seek(start);raw=stream.read(length);used+=length
                    if not raw.endswith(b'\n') or hashlib.sha256(raw[:-1]).hexdigest()!=expected:missing+=1;continue
                    try:obj=json.loads(raw)
                    except (ValueError,RecursionError):missing+=1;continue
                    if not isinstance(obj,dict):continue
                    if client=='codex' and row.get('handoff',{}).get('form') in ('request','receipt','native'):
                        handoffs.append(dict(handoff_material(obj),sequence=seq,event_id=row['event_id']))
                    reqs,results=tool_material(client,obj)
                    for entries,target in ((reqs,requests),(results,receipts)):
                        target.extend(dict(item,sequence=seq,event_id=row['event_id']) for item in entries)
                    for kind,text in extract(client,obj):
                        phase=(obj.get('payload',{}).get('phase') or obj.get('payload',{}).get('channel')) if client=='codex' and isinstance(obj.get('payload'),dict) else None
                        # Observed in the Windows desktop client's public final
                        # response. Keep the allowlist narrow; unknown phases and
                        # analysis remain unreadable rather than guessed public.
                        if phase=='final_answer':phase='final'
                        out.append(dict(kind=kind,text=text,phase=phase if phase in ('commentary','final') else None,sequence=seq,event_id=row['event_id'],timestamp_ms=row.get('timestamp_ms'),turn_id=row.get('context_turn_id') or row.get('turn_id')))
        except OSError:return dict(title=title,items=[],unavailable=True,missing=missing)
        finally:
            if descriptor is not None:os.close(descriptor)
        return dict(title=title,items=out,requests=requests,receipts=receipts,handoffs=handoffs,unavailable=False,missing=missing)
