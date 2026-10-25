"""Bounded, read-only request/receipt projections from saved evidence.

Exact source/generation/session/agent scopes are inherited from HistoryView.
No temporal proximity, text matching, task completion or recursive agent tree.
"""
from collections import Counter, defaultdict
import json
import time

from history_view import (CLIENT, SOURCE, GENERATION, SESSION, AGENT, SIDECHAIN,
                          CURRENT, FROM, key_parts, key_for, present, safe_fields, describe)

BOUNDARIES = ('observation_gap','invalid_record','context_boundary','source_reset',
              'identity_scope_unresolved','identity_conflict','foreign_session_record',
              'context_record_observed','invalid_tool_calls','record_limit_exceeded')
STATUS = {
    'succeeded': ('收到成功回执', '仅说明这次操作的回执，不代表任务完成。'),
    'failed': ('收到失败回执', '有明确失败标记；没有正文，不能判断具体原因。'),
    'cancelled': ('收到取消回执', '有明确取消标记。'),
    'unknown': ('结果仍不明确', '结果信息不足，暂不判定成功或失败。'),
    'conflict': ('回执互相冲突', '保留冲突，不挑选一条当作最终结论。'),
    'unresolved': ('对应关系有疑问', '操作编号有重复或身份问题，不能可靠合并结果。'),
    'no_receipt': ('尚未见到可配对的回执', '不表示仍在运行，也不证明执行失败；结果可能尚未出现或未被观察到。'),
}


def atoms(row, sequence):
    parent = safe_fields(dict(row,sequence=sequence))
    if isinstance(row.get('blocks'),list):
        for b in row['blocks']:
            if not isinstance(b,dict):continue
            data=safe_fields(b)
            # Inherit location only, never overwrite block identity with parent kind.
            for key in ('source','source_id','generation','session_id','agent_id','is_sidechain','sequence','after_gap_evidence_id'):
                if key in parent:data[key]=parent[key]
            yield data
    else:
        if isinstance(row.get('result'),dict):
            parent.update(safe_fields(row['result']))
            parent['kind']='tool_result'
            # Location and identity belong to the selected saved source.
            for key in ('source','source_id','generation','session_id','agent_id','is_sidechain','sequence','event_id'):
                if key in row:parent[key]=row[key]
            parent['sequence']=sequence
        yield parent


def evidence_id(value):return value.get('evidence_id') or value.get('event_id') or ''


def project(records, client):
    operations=[];orphans=[];by_id={};by_call=defaultdict(list);epoch=0
    counts=Counter();latest=None;warnings=[];atom_count=0;limited=False;processed_end=0
    for sequence,row,selected in records:
        processed_end=sequence
        if row.get('kind') in BOUNDARIES:
            epoch+=1;warnings.append(present(row,sequence))
        if not selected:continue
        counts['records']+=1
        if row.get('kind') in ('turn_started','turn_ended','turn_cancelled','source_error'):
            latest=present(row,sequence)
        for a in atoms(row,sequence):
            atom_count+=1
            if atom_count>5000:limited=True;break
            kind=a.get('kind');counts[kind or 'unknown']+=1
            if a.get('evidence_class')=='self_report':counts['self_reports']+=1
            if kind not in ('tool_requested','tool_result'):continue
            eid=evidence_id(a);call=a.get('call_id');turn=a.get('turn_id') or a.get('context_turn_id')
            call_key=(epoch,turn if client=='codex' else None,call)
            if kind=='tool_requested':
                op=dict(request=a,receipts=[],uncertain=False)
                operations.append(op)
                if not eid or eid in by_id:op['uncertain']=True
                if eid in by_id:by_id[eid]['uncertain']=True
                by_id[eid]=op
                if not call or client=='codex' and not turn:op['uncertain']=True
                if a.get('association') in ('ambiguous_reused_call','missing_identity','tracking_limit_exceeded'):
                    op['uncertain']=True
                if call:
                    if by_call[call_key]:
                        # Retain duplicate requests as evidence, without double success credit.
                        op['uncertain']=True
                        for previous in by_call[call_key]:previous['uncertain']=True
                    by_call[call_key].append(op)
                op['_epoch']=epoch
            else:
                op=None
                if a.get('projection_eligible') is True:
                    ref=a.get('request_evidence_id')
                    if ref and call:
                        candidate=by_id.get(ref)
                        if candidate and candidate['_epoch']==epoch and candidate['request'].get('call_id')==call:
                            op=candidate
                    elif client=='codex' and call and turn:
                        candidates=by_call[call_key]
                        if len(candidates)==1:op=candidates[0]
                if op is not None and not op['uncertain']:
                    op['receipts'].append(a)
                else:
                    orphans.append(a)
                    # A later explicitly ambiguous reuse invalidates earlier neat-looking pairs.
                    if a.get('association')=='ambiguous_reused_call' and call:
                        for candidate in by_call[call_key]:candidate['uncertain']=True
        if limited:break
    for op in operations:
        results=op['receipts'];outcomes={r.get('outcome','unknown') for r in results}
        known=outcomes & {'succeeded','failed','cancelled'}
        if op['uncertain']:status='unresolved'
        elif len(known)>1 or any(r.get('conflicting_results') or r.get('result_flags_conflict') for r in results):status='conflict'
        elif not results:status='no_receipt'
        elif 'unknown' in outcomes or not known:status='unknown'
        else:status=next(iter(known))
        op.update(status=status,title=describe(op['request'])['title'],status_label=STATUS[status][0],note=STATUS[status][1],receipt_count=len(results))
        del op['_epoch'];del op['uncertain']
    return dict(operations=operations,unlinked_receipts=orphans,counts=dict(counts),latest_marker=latest,
                warnings=warnings,atom_limit_reached=limited,processed_end=processed_end)


class ContextView:
    def __init__(self,history):self.history=history

    def snapshot(self,client,key,snapshot=0):
        if type(snapshot) is not int or not 0<=snapshot<2**63:raise ValueError('Invalid snapshot')
        parts=key_parts(key);scope,args=self.history.scope(parts)
        with self.history.connect(client) as db:
            high=db.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]
            snapshot=min(snapshot,high) if snapshot else high
            state=db.execute('SELECT state FROM sources WHERE source_id=?',(parts[0],)).fetchone()
            if not state:raise ValueError('Unknown source')
            where=f"{SOURCE}=? AND {GENERATION}=? AND {CLIENT}=? AND e.sequence<=? AND (({SESSION}=? AND {AGENT}=? AND {SIDECHAIN}=?) OR json_extract(e.record,'$.kind') IN ({','.join('?' for _ in BOUNDARIES)}))"
            query=f'SELECT e.sequence,e.record FROM events e WHERE {where} ORDER BY sequence DESC LIMIT 1001'
            cursor=db.execute(query,[parts[0],parts[1],client,snapshot,parts[2],parts[3],parts[4],*BOUNDARIES])
            records=[];size=0;limited=False;deadline=time.monotonic()+self.history.query_seconds
            for sequence,raw in cursor:
                size+=len(raw.encode('utf-8'))
                if len(records)>=1000 or size>8*1024*1024 or time.monotonic()>deadline:limited=True;break
                row=json.loads(raw)
                selected=(row.get('session_id') or '',row.get('agent_id') or '',int(bool(row.get('is_sidechain',False))))==tuple(parts[2:])
                records.append((sequence,row,selected))
            if not any(r[2] for r in records):raise ValueError('No records in this view')
        records.reverse();out=project(records,client)
        # A gap outside this bounded window still matters when later records carry it.
        out['earlier_gap_reported']=any(r[1].get('after_gap_evidence_id') for r in records if r[2])
        out.update(snapshot=snapshot,window_start=records[0][0],window_end=out.pop('processed_end'),
                   window_limited=limited or out['atom_limit_reached'],archived=parts[1]!=json.loads(state[0])['generation'],
                   scope_note='只计算本次读取范围内的记录；不是完整任务进度，也不证明助手仍在运行。')
        out['status_counts']=dict(Counter(o['status'] for o in out['operations']))
        return out

    def context(self,client,key,*,snapshot=0,offset=0,filter='all'):
        if type(offset) is not int or not 0<=offset<=5000 or filter not in ('all','attention','no_receipt','succeeded'):
            raise ValueError('Invalid context page')
        out=self.snapshot(client,key,snapshot)
        operations=sorted(out.pop('operations'),key=lambda x:x['request']['sequence'],reverse=True)
        if filter=='attention':operations=[o for o in operations if o['status'] in ('failed','cancelled','unknown','conflict','unresolved')]
        elif filter!='all':operations=[o for o in operations if o['status']==filter]
        page=operations[offset:offset+30]
        for op in page:
            op['receipts']=op['receipts'][:10]
        out.update(operations=page,filtered_operations=len(operations),has_more=offset+len(page)<len(operations),next_offset=offset+len(page),filter=filter)
        out['unlinked_receipt_count']=len(out['unlinked_receipts']);out['unlinked_receipts']=out['unlinked_receipts'][-10:]
        out['source_warning_count']=len(out['warnings']);out['warnings']=out['warnings'][-10:]
        return out

    def relations(self,client,key,*,snapshot=0):
        parts=key_parts(key)
        if not parts[2]:return dict(items=[],has_more=False)
        if type(snapshot) is not int or not 0<=snapshot<2**63:raise ValueError('Invalid snapshot')
        with self.history.connect(client) as db:
            high=db.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]
            snapshot=min(snapshot,high) if snapshot else high
            query=f"SELECT e.sequence,e.record,j.value"+FROM+" JOIN json_each(e.record,'$.relationships') j "+f"WHERE {CLIENT}=? AND {GENERATION}={CURRENT} AND e.sequence<=? AND (json_extract(j.value,'$.from_session_id')=? OR json_extract(j.value,'$.to_session_id')=?) ORDER BY e.sequence DESC LIMIT 21"
            rows=db.execute(query,(client,snapshot,parts[2],parts[2])).fetchall()
            items=[]
            for seq,raw,link in rows[:20]:
                row=json.loads(raw);relation=json.loads(link)
                if relation.get('status')!='reported_by_client':continue
                target=relation.get('to_session_id') if relation.get('from_session_id')==parts[2] else relation.get('from_session_id')
                candidates=db.execute(f'SELECT {SOURCE},{GENERATION},{SESSION},{AGENT},{SIDECHAIN},count(*),max(e.sequence)'+FROM+f' WHERE {CLIENT}=? AND {GENERATION}={CURRENT} AND {SESSION}=? AND e.sequence<=? GROUP BY {SOURCE},{GENERATION},{SESSION},{AGENT},{SIDECHAIN} ORDER BY max(e.sequence) DESC LIMIT 11',(client,target,snapshot)).fetchall()
                choices=[dict(key=key_for(list(r[:5])),source_id=r[0],generation=r[1],session_id=r[2],agent_id=r[3],is_sidechain=bool(r[4]),records=r[5],last_sequence=r[6],archived=False) for r in candidates[:10]]
                items.append(dict(relation=safe_fields(relation,{'kind','from_session_id','to_session_id','basis','status'}),evidence=safe_fields(dict(row,sequence=seq)),targets=choices,more_targets=len(candidates)>10))
            return dict(items=items,has_more=len(rows)>20,snapshot=snapshot,note='只列当前观察版本中客户端明确报告的关系。相同聊天的不同来源分别列出；关系不证明交接完成。')

    def explanation_context(self,client,key,snapshot=0):
        out=self.snapshot(client,key,snapshot);counts=out['status_counts']
        ops=out['operations'];receipts=out['unlinked_receipts'];warnings=out['warnings']
        facts=[dict(title='本次查看范围',note='本次查看范围内保存了 %d 条记录、%d 次操作请求。%s 不代表任务完成度。'%(out['counts'].get('records',0),len(ops),'范围受到读取上限限制。' if out['window_limited'] else '这仍只是已观察到的记录。'),ids=[]),
               dict(title='操作回执情况',note='本次范围：成功回执 %d 项，失败 %d 项，取消 %d 项，结果不明确 %d 项，冲突 %d 项，对应有疑问 %d 项，尚未见可配对回执 %d 项。回执不等于任务完成；没有回执也不证明仍在运行。'%tuple(counts.get(s,0) for s in STATUS),ids=[evidence_id(o['request']) for o in ops]),
               dict(title='无法配对和缺失的信息',note='本次范围内有 %d 条回执未能可靠配对、%d 条来源提醒。%s没有保存正文，不能判断具体任务内容、错误原因或用户是否认可。'%(len(receipts),len(warnings),'记录还报告了前方缺口，不能当作完整经过。' if out['earlier_gap_reported'] else ''),ids=[evidence_id(r) for r in receipts]+[w['evidence'].get('event_id','') for w in warnings])]
        # STATUS insertion order deliberately matches the tuple above; assert in tests.
        latest=out['latest_marker']
        if latest:facts.append(dict(title='最后观察到的阶段标记',note=latest['title']+'。'+latest['note']+' 不代表当前仍在运行。',ids=[latest['evidence']['event_id']]))
        return out,facts
