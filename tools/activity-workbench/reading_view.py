"""On-demand, bounded reading of the selected chat, never a transcript export.

History pages use explicit session/agent/branch identity across source files.
Each excerpt is still read and verified in its own source/generation; operations
are never paired across those boundaries. Cursors freeze a database snapshot.
"""
from collections import defaultdict
import json
import re
from history_view import CLIENT, SOURCE, GENERATION, SESSION, AGENT, SIDECHAIN, CURRENT, FROM, key_parts
from glance_view import IGNORED,meaningful_request
from explanation import ExplanationError,add_object_names
from plain_language import plain_words
from localization import current_language
from work_understanding import WorkUnderstanding


class ReadingView:
    def __init__(self,glance,explainer,automation):
        self.glance=glance;self.history=glance.history;self.explainer=explainer;self.automation=automation

    def freeze(self,grant,payload,refs):
        selection=self.automation.selection(grant)
        return self.explainer.preview_prepared(dict(selection,reading_grant=grant),payload,refs)['token']

    @staticmethod
    def payload(facts,parts,*,kind='detail',historical=False,state='unknown',naming=None):
        scope=dict(reading=kind,language=current_language(),reading_parts=parts,historical=historical,
                               history_order='newest_first' if historical else None,
                               current_turn_state=state,bounded_context=True,whole_task_status='unknown')
        if naming:scope['naming_context_evidence_id']=naming
        return dict(scope=scope,facts=facts)

    def current(self,grant):
        selection=self.automation.selection(grant)
        data,prepared,refs=self.glance.prepared(**selection)
        scope=prepared['scope'];ids=[f['evidence_id'] for f in prepared['facts']]
        action=scope.get('current_work_evidence_id') or scope.get('current_operation_evidence_id')
        bridge=scope.get('context_bridge_evidence_ids',[])
        goal=scope.get('project_goal_evidence_id')
        outcome=scope.get('current_operation_evidence_id')
        parts=[dict(part='action',title='具体做了什么',allowed=ids,required=[action] if action else []),
               dict(part='connection',title='和前面有什么联系',allowed=ids,required=([action] if action else [])+bridge),
               dict(part='purpose',title='对整个任务有什么用',allowed=ids,required=[goal] if goal else []),
               dict(part='limits',title='结果怎样，还有什么不清楚',allowed=ids,required=[outcome] if outcome else ['E5'])]
        payload=self.payload(prepared['facts'],parts,state=scope.get('current_turn_state','unknown'),naming=scope.get('naming_context_evidence_id'))
        return dict(token=self.freeze(grant,payload,refs),parts=parts,revision=data['revision'],
                    note='这是点击时的工作片段；首页仍会继续更新。')

    def work(self,grant,scope='chat',part=None):
        # This endpoint is requested by the scope-specific explanation button.
        # Merely opening a project locally does not extend automatic disclosure.
        selection=self.automation.selection(grant)
        data,payload,refs=WorkUnderstanding(self.glance).prepared(**selection,scope=scope)
        if part is not None:
            data,payload=WorkUnderstanding.focused(data,payload,part)
            ids={f['evidence_id'] for f in payload['facts']}
            refs=[r for r in refs if r['evidence_id'] in ids]
        return dict(data,token=self.freeze(grant,payload,refs))

    def review(self,grant,section='overview',snapshot=0,before=0,part=None):
        from history_review import HistoryReview
        selection=self.automation.selection(grant)
        data,payload,refs=HistoryReview(self.glance).prepared(**selection,section=section,snapshot=snapshot,before=before,part=part)
        return dict(data,token=self.freeze(grant,payload,refs) if data['parts'] else None)

    def history_page(self,grant,snapshot=0,before=0):
        return self._history_page(self.automation.selection(grant),snapshot,before,grant)

    def history_local(self,client,key,snapshot=0,before=0):
        return self._history_page(dict(client=client,key=key),snapshot,before)

    def _history_page(self,selection,snapshot=0,before=0,grant=None):
        if any(type(n) is not int or not 0<=n<2**63 for n in (snapshot,before)):raise ValueError('Invalid cursor')
        client=selection['client'];parts=key_parts(selection['key'])
        # Missing session identity cannot be used to merge separate files.
        if not parts[2] or parts[2].startswith('source-'):
            scope,args=self.history.scope(parts)
        else:
            scope=f'{SESSION}=? AND {AGENT}=? AND {SIDECHAIN}=? AND {GENERATION}={CURRENT}'
            args=[parts[2],parts[3],parts[4]]
        speech="json_extract(e.record,'$.source_kind') IN ('message','user_message','agent_message','user','assistant')"
        with self.history.connect(client) as db:
            high=db.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]
            snapshot=min(snapshot,high) if snapshot else high
            rows=db.execute('SELECT e.sequence,e.record,s.state'+FROM+f' WHERE {scope} AND {CLIENT}=? AND e.sequence<=? AND e.sequence<? AND {speech} ORDER BY e.sequence DESC LIMIT 101',args+[client,snapshot,before or snapshot+1]).fetchall()
        sources=defaultdict(list);states={};missing=False
        for seq,raw,state_raw in rows[:100]:
            row=json.loads(raw)
            if row.get('kind') in IGNORED:continue
            source_parts=(row['source_id'],row['generation'],parts[2],parts[3],parts[4])
            sources[source_parts].append((seq,row));states[source_parts]=json.loads(state_raw)
        items=[]
        # Keep all reads bounded even if a malformed history lists many sources.
        for source_parts,entries in list(sources.items())[:8]:
            result=self.glance.reader.read(client,list(source_parts),states[source_parts],entries)
            missing=missing or result['unavailable'] or bool(result['missing'])
            items.extend(i for i in result['items'] if i['kind'] in ('user','assistant'))
        missing=missing or len(sources)>8
        items.sort(key=lambda i:i['sequence'])
        groups=[];group=None;last=None;last_seq=-10
        for item in items:
            # Some clients save the same public message in two adjacent forms.
            signature=(item['kind'],item['text'])
            if signature==last and item['sequence']-last_seq<=2:continue
            last=signature;last_seq=item['sequence']
            if item['kind']=='user':
                group=dict(start=item['sequence'],request=item,assistants=[]);groups.append(group)
            else:
                if group is None:
                    # A very long turn may exceed the speech window. Do not
                    # drop all its replies or silently attach them to a later ask.
                    group=dict(start=item['sequence'],request=None,assistants=[]);groups.append(group);missing=True
                group['assistants'].append(item)
        picked=list(reversed(groups[-3:]));cards=[];facts=[];refs=[];summaries=[]
        brief=self.glance.project_context.get(**selection) if self.glance.project_context else None
        naming=add_object_names(facts,refs,brief)
        shared_facts=list(facts);shared_refs=list(refs)
        for index,group in enumerate(picked):
            sid='section'+str(index+1);own_facts=[];own_refs=[]
            def add(item,label,kind):
                alias='E'+str(len(facts)+len(own_facts)+1)
                own_facts.append(dict(evidence_id=alias,record_marker=label,excerpt=item['text'][:480],evidence_class=kind))
                own_refs.append(dict(evidence_id=alias,title=label,quote=item['text'][:480],sequence=item['sequence'],record_id=item['event_id']))
                return alias
            request_item=group['request'] or dict(text='这一段的要求没有读到，以下仅是公开汇报片段。',sequence=group['start'],event_id='未取得要求')
            request=add(request_item,'这一段的用户要求' if group['request'] else '这部分记录的限制','user_request' if group['request'] else 'unknown')
            prior_group=next((g for g in reversed(groups[:groups.index(group)]) if g['request'] and meaningful_request(g['request']['text'])),None)
            prior=(prior_group['assistants'][-1] if prior_group['assistants'] else prior_group['request']) if prior_group else None
            prior_report=bool(prior_group and prior_group['assistants'])
            background=add(prior,'前一段助手公开答复，仅供衔接、不是本段执行结果' if prior_report else '前一段较明确的要求，只作背景、不能当作已完成','assistant' if prior_report else 'user_request') if prior else None
            assistants=group['assistants'];chosen=[]
            if assistants:chosen.append(assistants[0])
            for item in assistants[-1:] if background else assistants[-2:]:
                if item not in chosen:chosen.append(item)
            reports=[add(i,'这一段的助手公开汇报（未独立验证）','assistant') for i in chosen]
            ids=[f['evidence_id'] for f in shared_facts+own_facts]
            antecedent=[background] if background and re.search(r'(?:这|那)(?:两个|几个|些|个)按钮',request_item['text']) else []
            required=[request]+antecedent+reports[-1:]
            detail_parts=[dict(part='request',title='这段要解决什么',allowed=ids,required=[request]+antecedent),
                          dict(part='work',title='助手具体做了什么',allowed=ids,required=reports[-1:] or [request]),
                          dict(part='outcome',title='结果与后续',allowed=ids,required=reports[-1:] or [request])]
            detail=self.freeze(grant,self.payload(shared_facts+own_facts,detail_parts,historical=True,naming=naming),shared_refs+own_refs) if grant else None
            title=plain_words(group['request']['text'])[:48] if group['request'] else '较早的工作片段（要求未读到）'
            local=[dict(part='request',text=plain_words(request_item['text']),basis='user_request' if group['request'] else 'unknown',evidence_ids=[request]+antecedent),
                   dict(part='work',text='以下是助手当时的公开说明，只能证明它这样汇报，不能据此认定已执行。',basis='unknown',evidence_ids=reports),
                   dict(part='outcome',text='仅凭这些公开汇报还不能确认独立验收情况。请对照当时要求与实际结果，不能把历史汇报当成当前版本已验证。',basis='unknown',evidence_ids=reports[-1:])]
            if current_language()=='en':
                local[0]['text']='The request at the time is preserved in the original supporting notes.' if group['request'] else 'The request for this fragment was not available.'
                local[1]['text']='These are public assistant statements from that time. They establish what was reported, not what was actually executed.'
                local[2]['text']='These excerpts do not provide independent acceptance evidence. Compare the request with actual results; an old report does not validate the current version.'
            local_summary=('助手当时汇报：'+plain_words(assistants[-1]['text'])[:180] if reports else '这一段暂时只有要求，未读到助手汇报。')
            if current_language()=='en':
                local_summary='Public assistant statements are available in this segment; their results are not independently verified.' if reports else 'Only the request was available; no assistant report was found.'
            cards.append(dict(id=sid,start=group['start'],title=title or '这一段工作',stamp=request_item.get('timestamp_ms'),detail_token=detail,parts=detail_parts,
                              local=local,local_summary=local_summary,references=shared_refs+own_refs,
                              position=(['最近一段','更早一段','再早一段'][index] if not before else '较早记录 '+str(index+1)),missing_reply=not reports,
                              note='有公开汇报；结果仍以实际验收为准。' if reports else '这一段暂时只有要求，未读到助手汇报。'))
            summaries.append(dict(part=sid,title='这段的简短回顾',allowed=ids,required=required))
            facts.extend(own_facts);refs.extend(own_refs)
        next_before=picked[-1]['start'] if picked else (rows[min(len(rows),100)-1][0] if rows else before)
        with self.history.connect(client) as db:
            more=bool(next_before and db.execute('SELECT 1'+FROM+f' WHERE {scope} AND {CLIENT}=? AND e.sequence<=? AND e.sequence<? AND {speech} LIMIT 1',args+[client,snapshot,next_before]).fetchone())
        token=self.freeze(grant,self.payload(facts,summaries,kind='summary',historical=True,naming=naming),refs) if cards and grant else None
        return dict(cards=cards,token=token,snapshot=snapshot,next_before=next_before,has_more=more,
                    note='按每次要求分段，先看最近三段，再往前翻。这里只采用每段少量公开摘录，不是完整历史。'+('部分原文暂时读不到，没有补猜。' if missing else ''))

    def explain(self,grant,token):
        selection=self.automation.selection(grant)
        with self.explainer.lock:
            entry=self.explainer.entries.get(token)
            if not entry or entry['selection']!=dict(selection,reading_grant=grant):raise ExplanationError('preview_expired')
            if not entry['payload'].get('scope',{}).get('reading'):raise ExplanationError('consent_required')
            refs=entry['references']
            # A deliberate retry should not replay a cached transport failure.
            # Successful explanations remain cached; the shared budget still applies.
            if entry['state']=='done' and entry['result'].get('mode')=='fallback':
                entry['state']='ready';entry.pop('result',None)
        # Close/switch during preparation cannot cause a later model request.
        self.automation.selection(grant)
        return dict(result=self.explainer.generate(token,True,can_send=lambda:self.automation.selection(grant)),references=refs)
