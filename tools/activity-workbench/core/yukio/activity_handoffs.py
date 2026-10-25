"""Allowlisted collaboration evidence. No prompt, result body or reasoning retained.

Native Codex items/events and explicit function arguments are separate contracts.
A receipt shape alone never establishes a delegation or a recipient.
"""
import hashlib
import json
from .activity_links import identifier

ACTIONS = {'spawn_agent','send_input','send_message','followup_task','wait','wait_agent',
           'resume_agent','close_agent','interrupt_agent'}
STATES = {'pending_init','running','interrupted','completed','errored','shutdown','not_found'}
STATUSES = {'in_progress','completed','failed','interrupted'}


def dictionary(value):
    if isinstance(value,dict):return value
    if isinstance(value,str):
        try:obj=json.loads(value)
        except (ValueError,RecursionError):return {}
        return obj if isinstance(obj,dict) else {}
    return {}


def prompt(value):
    if not isinstance(value,str) or not value.strip():return {}
    try:digest=hashlib.sha256(value.encode()).hexdigest()
    except UnicodeError:return {}
    return dict(prompt_present=True,prompt_sha256=digest)


def state(value):
    if isinstance(value,str) and value in STATES:return dict(state=value,has_message=False)
    if isinstance(value,dict) and len(value)==1:
        name=next(iter(value))
        if name in ('completed','errored'):
            return dict(state=name,has_message=name=='completed' and isinstance(value[name],str) and bool(value[name].strip()))
    return dict(state='unknown',has_message=False)


def states(value):
    if not isinstance(value,dict) or len(value)>32:return {}
    if any(identifier(k) is None for k in value):return {}
    return {k:state(v) for k,v in value.items()}


def targets(value):
    if not isinstance(value,list) or len(value)>32 or any(identifier(x) is None for x in value):return None
    if len(value)!=len(set(value)):return None
    return value


def capture(payload,kind):
    item=payload.get('item')
    if kind in ('item_started','item_updated','item_completed') and isinstance(item,dict) and item.get('type')=='CollabAgentToolCall':
        action=item.get('tool');sender=identifier(item.get('sender_thread_id'));call=identifier(item.get('id'))
        if not isinstance(action,str) or action not in ACTIONS or not sender or not call:return None
        ts=targets(item.get('receiver_thread_ids',[]))
        return dict(form='native',action=action,sender=sender,call=call,targets=ts or [],
                    invalid_targets=ts is None,status=item.get('status') if isinstance(item.get('status'),str) and item['status'] in STATUSES else 'unknown',
                    states=states(item.get('agents_states')),**prompt(item.get('prompt')))
    # Legacy Codex EventMsg variants use the same protocol IDs, not UI item IDs.
    legacy={'collab_agent_spawn':('spawn_agent','new_thread_id'),
            'collab_agent_interaction':('send_input','receiver_thread_id'),
            'collab_waiting':('wait',None),'collab_close':('close_agent','receiver_thread_id'),
            'collab_resume':('resume_agent','receiver_thread_id')}
    for prefix,(action,target) in legacy.items():
        if kind not in (prefix+'_begin',prefix+'_end'):continue
        call=identifier(payload.get('call_id'));sender=identifier(payload.get('sender_thread_id'))
        if not call or not sender:return None
        end=kind.endswith('_end');ts=targets(payload.get('receiver_thread_ids',[])) if target is None else ([payload[target]] if identifier(payload.get(target)) else [])
        if target is None and end and 'receiver_thread_ids' not in payload:ts=targets(sorted(payload.get('statuses',{}))) if isinstance(payload.get('statuses'),dict) else None
        ss=states(payload.get('statuses')) if target is None else ({ts[0]:state(payload.get('status'))} if ts else {})
        # A non-failed receiver status is not a returned task result.
        failed=any(v['state'] in ('errored','not_found') for v in ss.values()) or action=='spawn_agent' and end and not ts
        return dict(form='native',action=action,sender=sender,call=call,targets=ts or [],invalid_targets=ts is None,
                    status=('failed' if failed else 'completed') if end else 'in_progress',states=ss,**prompt(payload.get('prompt')))
    if kind=='function_call':
        name=payload.get('name','');namespace=payload.get('namespace','')
        if not isinstance(name,str) or namespace not in ('','functions','collaboration'):return None
        if name.startswith(('functions.','collaboration.')):name=name.split('.',1)[1]
        if name not in ACTIONS:return None
        args=dictionary(payload.get('arguments'));ts=[]
        if name in ('wait','wait_agent'):ts=targets(args.get('ids',[]))
        elif name!='spawn_agent':
            target=args.get('id',args.get('target'))
            ts=[target] if identifier(target) else None
        return dict(form='request',action=name,call=identifier(payload.get('call_id')) or '',targets=ts or [],invalid_targets=ts is None,
                    **prompt(args.get('message',args.get('prompt'))))
    if kind=='function_call_output':
        obj=dictionary(payload.get('output'));out=dict(form='receipt',states=states(obj.get('status')))
        agent=identifier(obj.get('agent_id'))
        if agent:out['created_agent']=agent
        if type(obj.get('interrupted')) is bool:out['interrupted']=obj['interrupted']
        return out if out['states'] or agent or 'interrupted' in out else None
    if kind=='message' and payload.get('role')=='user':
        content=payload.get('content')
        # Exact single text input only; no matching of truncated/filtered text.
        if isinstance(content,list) and len(content)==1 and isinstance(content[0],dict) and content[0].get('type') in ('input_text','text'):
            p=prompt(content[0].get('text'))
            if p:return dict(form='recipient_input',**p)
    return None
