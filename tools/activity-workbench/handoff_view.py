"""Evidence-backed, bounded collaboration cards. Never infer causal use of a reply.

One card is one communication, not an inferred task lifecycle. Different turns,
files, revisions and gaps cannot share request/receipt pairing. Child navigation
requires one current exact identity with a matching explicit parent relationship.
"""
import json
from context_view import ContextView, BOUNDARIES, evidence_id
from history_view import FROM,CLIENT,CURRENT,GENERATION,SESSION,SOURCE,key_parts,key_for,safe_handoff

ACTIONS={'spawn_agent':'交给协助助手','send_input':'补充工作要求','send_message':'发送消息',
         'followup_task':'安排后续工作','wait':'查看助手回复','wait_agent':'查看助手回复',
         'resume_agent':'恢复助手','close_agent':'关闭助手','interrupt_agent':'打断助手'}


class HandoffView:
    def __init__(self,history,reader):self.history=history;self.reader=reader

    def detail(self,client,key,snapshot=0):
        parts=key_parts(key);ctx=ContextView(self.history).snapshot(client,key,snapshot)
        out=dict(items=[],limited=ctx['window_limited'],archived=ctx['archived'],snapshot=ctx['snapshot'],
                 note='只显示明确留下的交接。发出要求、收到回复和采用回复分别看待；任务是否完成仍需回原聊天确认。')
        if client!='codex':
            # Other clients expose tool receipts but no verified recipient contract.
            for op in ctx['operations']:
                if op['request'].get('tool_name') in ('Task','Agent'):
                    out['items'].append(dict(title='交给协助助手',sent='已看到委派请求，暂未取得可确认的交接内容。',
                        status='已收到这次操作的回执' if op['receipts'] else '尚未看到对应回执',
                        targets=[],returns=[],input_note='客户端没有提供已验证的接收者联系，暂不能连接到具体助手。',
                        use_note='尚未观察到回复如何被采用。',evidence=[dict(label='委派请求',id=evidence_id(op['request']))]))
            out['note']='这个客户端可查看委派操作与回执；目前不能可靠确认具体接收者。'+out['note']
            out['limited']=out['limited'] or len(out['items'])>12;out['items']=out['items'][-12:][::-1];return out
        scope,args=self.history.scope(parts)
        with self.history.connect(client) as db:
            state=json.loads(db.execute('SELECT state FROM sources WHERE source_id=?',(parts[0],)).fetchone()[0])
            # Include source-level boundaries so an unknown session cannot bridge a gap.
            rows=db.execute('SELECT e.sequence,e.record'+FROM+f' WHERE {SOURCE}=? AND {GENERATION}=? AND {CLIENT}=? AND e.sequence BETWEEN ? AND ? ORDER BY sequence LIMIT 1001',
                            [parts[0],parts[1],client,ctx['window_start'],ctx['window_end']]).fetchall()
            parsed=[];size=0
            for seq,raw in rows:
                size+=len(raw.encode())
                if len(parsed)>=1000 or size>8<<20:out['limited']=True;break
                parsed.append((seq,json.loads(raw)))
        selected=[(s,r) for s,r in parsed if r.get('session_id','')==parts[2] and r.get('agent_id','')==parts[3] and bool(r.get('is_sidechain',False))==bool(parts[4])]
        native={};epoch=0;epochs={}
        for seq,row in parsed:
            if row.get('kind') in BOUNDARIES:epoch+=1
            epochs[seq]=epoch
            if (seq,row) not in selected:continue
            h=row.get('handoff',{})
            if h.get('form')!='native' or h.get('sender')!=parts[2]:continue
            identity=(epoch,row.get('turn_id') or row.get('context_turn_id') or 'unscoped:'+str(seq),h.get('call'))
            if not identity[2]:continue
            entries=native.setdefault(identity,[]);entries.append((seq,row,safe_handoff(h)))
        cards=[];native_calls=set()
        for (epoch,turn,call),entries in native.items():
            native_calls.add((epoch,turn,call));last=entries[-1];h=last[2]
            actions={e[2]['action'] for e in entries}
            finals=[e[2] for e in entries if e[2].get('status')!='in_progress']
            # Identical repeated snapshots are harmless; incompatible terminal data isn't.
            conflict=turn.startswith('unscoped:') or len(actions)!=1 or len({json.dumps(e,sort_keys=True) for e in finals})>1 or any(e[2].get('invalid_targets') for e in entries)
            if h.get('status')=='in_progress' and finals:conflict=True
            hs=[e[2].get('prompt_sha256') for e in entries if e[2].get('prompt_sha256')]
            if len(set(hs))>1:conflict=True
            ts=h.get('targets',[])
            if any(not set(e[2].get('targets',[])).issubset(set(ts)) for e in entries):conflict=True
            card=self.card(h,last[0],last[1]['event_id'],conflict=conflict)
            card['_rows']=entries;card['_prompt']=hs[-1] if hs else None;cards.append(card)
        raw_by_seq=dict(selected)
        for op in ctx['operations']:
            request=op['request'];h=request.get('handoff',{})
            if h.get('form')!='request' or h.get('action') not in ACTIONS:continue
            identity=(epochs.get(request['sequence']),request.get('turn_id') or request.get('context_turn_id'),request.get('call_id'))
            if identity in native_calls:continue
            receipts=[r.get('handoff',{}) for r in op['receipts']]
            created={r['created_agent'] for r in receipts if r.get('created_agent')}
            conflict=op['status'] in ('conflict','unresolved') or h.get('invalid_targets') or len(created)>1
            if created and op['status'] in ('failed','cancelled'):conflict=True
            normalized=dict(h,sender=parts[2],status='in_progress' if not op['receipts'] else 'unknown',states={})
            if op['status'] in ('failed','cancelled'):normalized['status']='failed' if op['status']=='failed' else 'interrupted'
            if created and h['action']=='spawn_agent':normalized.update(targets=sorted(created),status='completed')
            ss=[r['states'] for r in receipts if r.get('states')]
            if len({json.dumps(s,sort_keys=True) for s in ss})>1:conflict=True
            if ss:normalized['states']=ss[-1]
            if any(r.get('interrupted') for r in receipts):normalized['status']='interrupted'
            card=self.card(normalized,request['sequence'],evidence_id(request),conflict=conflict)
            rs=[request]+op['receipts'];card['_rows']=[(r['sequence'],raw_by_seq[r['sequence']],r.get('handoff',{})) for r in rs if r['sequence'] in raw_by_seq]
            card['evidence'] += [dict(label='对应回执',id=evidence_id(r)) for r in op['receipts'][:4]]
            card['_prompt']=h.get('prompt_sha256');cards.append(card)
        cards.sort(key=lambda c:c['sequence'],reverse=True);out['limited']=out['limited'] or len(cards)>12
        aliases={target:'协助助手 '+str(i+1) for i,target in enumerate(sorted({t['id'] for c in cards[:12] for t in c['targets']}))}
        receiver_budget=8
        for card in cards[:12]:
            if len(card['targets'])>4:card['targets']=card['targets'][:4];out['limited']=True
            for target in card['targets']:target['label']=aliases[target['id']]
            material=self.reader.read(client,parts,state,[(seq,row) for seq,row,_ in card['_rows']])
            snippets=material.get('handoffs',[])
            sent=next((v['sent'] for v in snippets if v.get('sent')),None)
            card['sent']=sent or ('这次是在查看已有回复，没有新增工作要求。' if card['action'] in ('wait','wait_agent') else '已看到发出要求的标记，但没有可显示的内容。' if card.get('_prompt') else '这条交接没有可显示的要求内容。')
            if not card['conflict']:
                for target in card['targets']:
                    if receiver_budget>0:
                        receiver_budget-=1;self.receiver(client,parts,ctx['snapshot'],target,card.get('_prompt'),ctx['archived'])
                    else:target['input_note']='本次展开已达到查看上限。';out['limited']=True
                for target in card['targets']:
                    for v in snippets:
                        text=v.get('returns',{}).get(target['id'])
                        if text and target.get('has_message'):card['returns'].append(dict(who=target['label'],target_id=target['id'],text=text,basis='助手自述'))
            card.pop('_rows');card.pop('_prompt');out['items'].append(card)
        return out

    def card(self,h,seq,eid,conflict=False):
        ts=h.get('targets',[]);ss=h.get('states',{})
        unexpected=set(ss)-set(ts)
        conflict=bool(conflict or unexpected or h.get('sender') in ts)
        status='交接对应关系尚不可靠，暂不合并' if conflict else {'completed':'客户端已确认这次操作','failed':'这次交接报告失败','interrupted':'这次交接被打断','in_progress':'尚未看到这次操作的结束记录'}.get(h.get('status'),'结果尚不明确')
        return dict(title=ACTIONS[h['action']],action=h['action'],sequence=seq,conflict=conflict,status=status,
                    targets=[dict(id=t,label='协助助手 '+str(i+1),state=ss.get(t,{}).get('state','unknown'),has_message=ss.get(t,{}).get('has_message',False)) for i,t in enumerate(ts[:32])],
                    returns=[],input_note='接收者实际拿到的完整背景尚不可确认。',use_note='尚未观察到回复如何被采用；收到回复不代表已经采用。',
                    evidence=[dict(label='交接记录',id=eid)])

    def receiver(self,client,parts,snapshot,target,prompt_hash,archived):
        target['input_note']='暂未取得可确认的接收记录。'
        if archived:return
        with self.history.connect(client) as db:
            candidates=db.execute(f'SELECT DISTINCT {SOURCE},{GENERATION},{SESSION},coalesce(json_extract(e.record,\'$.agent_id\'),\'\'),coalesce(json_extract(e.record,\'$.is_sidechain\'),0)'+FROM+f' WHERE {CLIENT}=? AND {GENERATION}={CURRENT} AND {SESSION}=? AND e.sequence<=? LIMIT 3',(client,target['id'],snapshot)).fetchall()
            if len(candidates)!=1:
                target['input_note']='接收者有多个来源，暂不自动选择。' if candidates else target['input_note'];return
            child=list(candidates[0]);scope,args=self.history.scope(child)
            rows=db.execute('SELECT e.sequence,e.record'+FROM+f' WHERE {scope} AND {CLIENT}=? AND e.sequence<=? ORDER BY sequence LIMIT 160',args+[client,snapshot]).fetchall()
            records=[(s,json.loads(r)) for s,r in rows]
            parents={rel.get('to_session_id') for _,r in records for rel in r.get('relationships',[]) if rel.get('kind')=='spawned_from' and rel.get('status')=='reported_by_client'}
            if parents!={parts[2]}:
                target['input_note']='尚未取得一致的主助手联系，暂不连接聊天。';return
            state=json.loads(db.execute('SELECT state FROM sources WHERE source_id=?',(child[0],)).fetchone()[0])
        target['key']=key_for(child)
        material=self.reader.read(client,child,state,records[:1]);target['label']=material.get('title') or target['label']
        # A boundary invalidates further matching in this bounded initial window.
        for seq,row in records:
            if row.get('kind') in BOUNDARIES:break
            h=row.get('handoff',{})
            if prompt_hash and h.get('form')=='recipient_input' and h.get('prompt_sha256')==prompt_hash:
                target['input_note']='接收方记录中有与这次要求完全相同的一条文字；其他背景仍不完整。'
                target['input_evidence']=row['event_id'];return
