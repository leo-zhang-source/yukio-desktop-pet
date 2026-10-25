"""A small current-work view, backed by scoped evidence and transient excerpts."""
import json
import hashlib
import re
import sqlite3
import time
from history_view import CLIENTS, CLIENT, FROM, SOURCE, GENERATION, SESSION, HistoryView, key_parts
from source_context import SourceContext, clean
from collector_status import read_status
from context_view import ContextView
from handoff_view import HandoffView
from task_summary import recap
from plain_language import plain_words
from explanation import add_object_names
from chat_catalog import activity_state, readable_title, catalog_card

IGNORED={'reasoning_record_observed','inherited_context_record','context_record_observed','identity_conflict','foreign_session_record','identity_scope_unresolved'}
NOISE={'token_count','token_usage_record','thread_settings_applied'}


def meaningful_request(text):
    """Short corrections matter. Only exact acknowledgements lack a new goal."""
    normalized=re.sub(r'[\s。.!！?？,，]+','',text).lower()
    return bool(normalized) and normalized not in {'继续','继续吧','好的','好','谢谢','ok','okay','continue','下一步'}


def progress_headline(text):
    # A full stop inside an example quotation must not discard its framing.
    sentences=[];start=0;quotes=[];pairs={'“':'”','‘':'’','「':'」','『':'』'}
    for i,char in enumerate(text):
        if char in pairs:quotes.append(pairs[char])
        elif quotes and char==quotes[-1]:quotes.pop()
        if char in '。！？' and not quotes:sentences.append(text[start:i+1]);start=i+1
    if text[start:].strip():sentences.append(text[start:])
    useful=[s.strip() for s in sentences if s.strip() and not re.fullmatch(r'(?:收到|明白|好的|好|不会停|没问题|可以|我继续|我会继续|继续推进)[。！？.!]*',s.strip())]
    # A completed milestone followed by "I am checking ..." must not keep
    # yesterday's achievement in the current-work slot. Quoted examples retain
    # their framing and are never promoted to the live action.
    if useful and re.search(r'已经|已(?:完成|装|通过|保存|保留|更新|交付)|完成了',useful[0]):
        current=next((s for s in useful[1:] if re.match(r'^(?:我(?:现在)?正在|(?:现在|目前)?正在)',s) and not re.search(r'例如|比如|示例|模拟',s)),None)
        if current:return clean(current,120)
    return clean(useful[0],120) if useful else ''


def waiting_request(operations,start,closed):
    for op in reversed(operations):
        if op['request']['sequence']<=max(start,closed) or op['status'] in ('succeeded','failed','cancelled','conflict','unresolved'):continue
        latest=max([op['request']]+op['receipts'],key=lambda r:r['sequence'])
        if latest.get('reported_await_user_response') is True:return latest
    return None


def public_reason(speech):
    """An explicit public rationale, never hidden reasoning or an old update."""
    if not speech:return None
    if re.search(r'例如|比如|示例|能这样表达|模拟材料',speech['text']):return None
    sentences=re.split(r'(?<=[。！？.!?])\s*',speech['text'])
    for sentence in sentences:
        if re.search(r'(?:不|不会|并非).{0,4}因为',sentence):continue
        if re.search(r'为了|以便|目的是|旨在|这样可以|这样能|为避免|原因(?:是|在于)|因为.+[，,]|.+所以.+|[，,](?:让|使|便于|方便|避免|防止)',sentence):
            return dict(speech,text=clean(sentence,160))
    return None


def local_story(user,activity,reason,step,fragment):
    """Small, bounded interpretations of explicit actions, usable without a model.

    A purpose is always a labelled inference unless publicly stated. Recipes
    explain an action's role, never infer file contents, success or hidden intent.
    Raw facts remain separate for model previews; inferred prose is not evidence.
    """
    refs=[dict(title='你的要求',**user)] if user else []
    if step:refs.append(dict(title='这一步及结果',text=step['action']+'；'+step['result'],event_id=step['event_id'],sequence=step['sequence']))
    if activity:refs.append(dict(title='助手公开说明' if activity['kind'] in ('assistant','operation_note') else '操作请求',**activity))
    action=(step or {}).get('action','') if step and (not activity or step['sequence']>=activity['sequence']) else ''
    recipes=[
        (r'^请求查看 ', '先核对现有内容，找出该从哪里处理；查看请求本身没有改动文件。', '先弄清现状，再决定怎么处理你的要求，避免只凭文件名和印象修改。'),
        (r'^请求修改 ', '这一步在把调整写进文件；是否解决问题，还要看之后的检查。', '把你的要求落实到实际文件，再通过检查确认效果。'),
        (r'^请求运行测试', '这一步检查改动能否正常工作；一次检查的结果，不等于整个任务已经验收。', '先找出改动带来的问题，减少把有问题的版本交给你使用的可能。'),
        (r'^请求构建程序', '这一步检查能否生成可运行的程序；生成成功还需要实际打开检查。', '确认改过的代码能变成你可以使用的程序。'),
        (r'^(?:搜索：|请求查找)', '这一步在寻找相关线索；找到材料后，还要核对内容是否适用于当前问题。', '先补齐处理你这项要求需要的信息，避免在依据不足时直接下结论。'),
        (r'^交给协助助手：', '这一步把一部分工作交给协助助手；发出请求不等于已经收到结果。', '把可分开的工作交给协助助手，之后再核对它的回复。'),
        (r'^助手标注：.*(?:检查|核对|确认|测试|验证)', '助手把这一步标为检查；需要结合返回结果，才能知道检查发现了什么。', '先核对实际效果，判断是否还要继续修改，再交给你使用。'),
    ]
    recipe=next((r for r in recipes if re.search(r[0],action)),None)
    if not recipe and activity and activity['kind']=='assistant':
        first=progress_headline(activity['text'])
        # Only an explicit announcement, not arbitrary words in a quoted file
        # or a diagnosis, can support this limited interpretation of a plan.
        if re.match(r'^(?:我(?:会|先|将|正在|准备)|接下来|现在开始|正在|先)',first):
            if re.search(r'检查|核对|验证|测试',first):recipe=recipes[2]
            elif re.search(r'查看|阅读|读一下',first):recipe=recipes[0]
            elif re.search(r'修改|修复|简化|调整|收起',first):recipe=recipes[1]
            if recipe:
                recipe=(recipe[0],'按助手的公开说明，'+recipe[1],recipe[2])
    if fragment and (not activity or fragment['sequence']>=activity['sequence']):
        explanation='读到的内容：'+fragment['display']+'（只看到这一小段）';eb='observed'
        er=[dict(title='明确对应的读取返回',**fragment)]
    elif recipe:
        explanation=recipe[1];eb='inference';er=refs
    else:
        # Public follow-up sentences can supply a useful explanation even when
        # a client exposes no readable operation. They stay attributed quotes.
        extra=[]
        if activity and activity['kind']=='assistant':
            sentences=re.split(r'(?<=[。！？])\s*',activity['text'])
            extra=[s for s in sentences[1:] if s.strip() and (not reason or s not in reason['text'])]
        explanation='助手补充：'+clean(''.join(extra),130) if extra else ('已读到助手的公开说明，但还不能可靠说明这一步与要求的具体关系。' if activity else '还没读到这一步的具体内容，暂时无法说明它与要求的关系。')
        eb='assistant' if extra else 'unknown';er=refs[-1:] if extra else []
    if reason:
        why=reason['text'];rb='assistant';rr=[dict(title='助手公开说明的理由',**reason)]
    elif recipe and user:
        why='可能是'+recipe[2];rb='inference';rr=refs
    else:
        why='还缺少当前步骤或目的说明，暂时不能判断为什么这样做。';rb='unknown';rr=[]
    return dict(explanation=explanation,explanation_basis=eb,reason=why,reason_basis=rb,
                part_evidence=dict(explanation=er,reason=rr))


class GlanceView:
    def __init__(self,history,roots=None,clock=time.time):
        self.history=history;self.reader=SourceContext(roots);self.clock=clock;self.project_context=None

    def detail(self,client,key):
        parts=key_parts(key)
        with self.history.connect(client) as db:
            scope,args=self.history.scope(parts)
            saved=db.execute('SELECT state FROM sources WHERE source_id=?',(parts[0],)).fetchone()
            if not saved:raise ValueError('Unknown source')
            state=json.loads(saved[0])
            if state.get('generation')!=parts[1]:raise ValueError('Choose current records')
            rows=db.execute('SELECT e.sequence,e.record'+FROM+f' WHERE {scope} AND {CLIENT}=? ORDER BY e.sequence DESC LIMIT 360',args+[client]).fetchall()
            if not rows:raise ValueError('No records in this view')
            high=rows[0][0];selected=[];warnings=False;latest_stamp=None
            for seq,raw in rows:
                row=json.loads(raw)
                if row.get('after_gap_evidence_id') or row.get('kind') in ('observation_gap','invalid_record'):warnings=True
                if row.get('kind') not in IGNORED and row.get('source_kind') not in NOISE:
                    selected.append((seq,row))
                    if latest_stamp is None and type(row.get('timestamp_ms')) in (int,float):latest_stamp=row['timestamp_ms']
            # User requests can be far behind many tool bookkeeping rows. Fetch a
            # separate bounded speech window so operational noise cannot erase context.
            speech_rows=db.execute('SELECT e.sequence,e.record'+FROM+f" WHERE {scope} AND {CLIENT}=? AND e.sequence<=? AND json_extract(e.record,'$.source_kind') IN ('message','user_message','agent_message','user','assistant') ORDER BY e.sequence DESC LIMIT 90",args+[client,high]).fetchall()
            anchor_rows=db.execute('SELECT e.sequence,e.record'+FROM+f" WHERE {scope} AND {CLIENT}=? AND e.sequence<=? AND json_extract(e.record,'$.source_kind') IN ('message','user_message','agent_message','user','assistant') ORDER BY e.sequence ASC LIMIT 30",args+[client,high]).fetchall()
        content_rows={seq:row for seq,row in selected[:40]}
        for seq,raw in speech_rows+anchor_rows:
            row=json.loads(raw)
            if row.get('kind') not in IGNORED:content_rows[seq]=row
        source=self.reader.read(client,parts,state,sorted(content_rows.items(),reverse=True));items=source['items']
        users=[x for x in items if x['kind']=='user'];assistants=[x for x in items if x['kind']=='assistant']
        user=next((x for x in users if meaningful_request(x['text'])),users[0] if users else None)
        origins=[x for x in reversed(users) if meaningful_request(x['text'])][:2]
        background=[]
        for item in users:
            if meaningful_request(item['text']) and item['text'] not in background:background.append(item['text'])
            if len(background)==3:break
        goal='；后来补充：'.join(reversed(background)) if background else (user or {}).get('text','尚未读到这段聊天中的具体要求。')
        newest_user=users[0]['sequence'] if users else 0
        latest_start=next((seq for seq,r in selected if r.get('kind')=='turn_started'),0)
        current_start=max(newest_user,latest_start)
        previous=[x for x in assistants if x['sequence']<current_start]
        checkpoints=[x for x in previous if x.get('phase')=='final'][:2] or previous[:2]
        assistants=[x for x in assistants if x['sequence']>current_start]
        speech=assistants[0] if assistants else None
        earlier_activity=[];earlier_texts={speech['text']} if speech else set()
        for item in assistants[1:]:
            if item['text'] in earlier_texts or not progress_headline(item['text']):continue
            earlier_texts.add(item['text']);earlier_activity.append(item)
            if len(earlier_activity)==2:break
        operations=[x for x in items if x['kind'] in ('operation','operation_note') and x['sequence']>current_start]
        # The public progress note anchors a short step; its individual operations
        # remain available as evidence instead of continually replacing the headline.
        activity=speech or (operations[0] if operations else None)
        reason=public_reason(speech)
        context=ContextView(self.history).snapshot(client,key,high)
        steps=[op for op in context['operations'] if op['request']['sequence']>current_start][-3:]
        needed={a['sequence'] for op in steps for a in [op['request']]+op['receipts'][-2:]}
        with self.history.connect(client) as db:
            linked_rows=db.execute('SELECT e.sequence,e.record'+FROM+f" WHERE {scope} AND {CLIENT}=? AND e.sequence<=? AND e.sequence IN ({','.join('?' for _ in needed)})",args+[client,high,*sorted(needed)]).fetchall() if needed else []
        material=self.reader.read(client,parts,state,[(seq,json.loads(raw)) for seq,raw in linked_rows])
        results=[];fragment=None;proposals=[]
        last_step=None
        for op in steps:
            # An older read must not explain a newer, unrelated operation.
            fragment=None
            request=op['request'];call=request.get('call_id')
            descriptions=[x for x in material['items'] if x['sequence']==request['sequence'] and x['kind'] in ('operation','operation_note')]
            # A record with multiple operations is not an unambiguous object label.
            target=descriptions[0]['text'] if len(descriptions)==1 else '一次工具操作'
            results.append(dict(text=target+'；'+op['status_label']+'。'+op['note'],status=op['status'],basis='assistant' if len(descriptions)==1 and descriptions[0]['kind']=='operation_note' else 'observed',event_id=request.get('evidence_id') or request.get('event_id'),sequence=request['sequence']))
            result_label={'succeeded':'这次操作报告成功','failed':'这次操作报告失败','cancelled':'这次操作已取消',
                'unknown':'已收到结果，是否成功还不清楚','no_receipt':'还没看到对应结果',
                'unresolved':'暂时不能确定结果属于谁','conflict':'结果有冲突，暂不下结论'}[op['status']]
            last_step=dict(action=clean(target,72),result=result_label,event_id=results[-1]['event_id'],sequence=request['sequence']) if len(descriptions)==1 else None
            reqs=[r for r in material.get('requests',[]) if r['sequence']==request['sequence'] and r['call_id']==call]
            if len(reqs)!=1:continue
            if reqs[0].get('material_kind')=='proposal':
                proposals.append(dict(reqs[0],text=reqs[0]['target']+' 拟修改片段（脚本请求，尚未确认写入）：'+reqs[0]['excerpt']))
                continue
            output=reqs[0].get('material_kind')=='tool_output'
            if op['status'] not in (('succeeded','unknown','failed','cancelled') if output else ('succeeded','unknown')):continue
            for receipt in op['receipts'][-2:]:
                snippets=[r for r in material.get('receipts',[]) if r['sequence']==receipt['sequence'] and r['call_id']==call]
                if len(snippets)==1:
                    fragment=dict(snippets[0],material_kind='tool_output' if output else 'file_read',display=clean(snippets[0]['text'],100),text=reqs[0]['target']+(' 的工具返回短片段：' if output else ' 的读取返回短片段：')+snippets[0]['text']+('（工具实际返回的这小段文字；未单独确认脚本内各步骤，不代表完整文件或任务结果；' if output else '（仅这段返回，不代表完整文件；')+op['status_label']+'）')
        title=readable_title(source['title'] or clean((user or {}).get('text',''),62))
        status='最近的工作';tone='quiet';needs='暂未看到明确需要你处理的请求。'
        markers=[(seq,r) for seq,r in selected if r.get('kind') in ('turn_started','turn_ended','turn_cancelled')]
        latest_marker=markers[0][1]['kind'] if markers else None
        age=max(0,self.clock()-(latest_stamp or 0)/1000) if latest_stamp is not None else None
        last_marker_sequence=markers[0][0] if markers else 0
        later_work=any(seq>last_marker_sequence and r.get('kind') in ('tool_requested','tool_result','message_observed','text_record_observed') for seq,r in selected)
        if latest_marker=='turn_ended' and not later_work:status='这一轮已结束'
        elif latest_marker=='turn_cancelled' and not later_work:status='这一轮已取消'
        elif age is not None and age<90:status='刚有新活动';tone='fresh'
        else:status='暂时没有新消息'
        # Do not keep an old waiting signal after a result, reply or closed turn.
        closed=max((seq for seq,r in selected if r.get('kind') in ('turn_ended','turn_cancelled','context_boundary')),default=0)
        attention=waiting_request(context['operations'],current_start,closed)
        if attention:
            status='有一项请求等你处理';tone='attention';needs='这次操作提到需要你回答。请回原聊天确认并处理。'
        meaningful=[];seen=set()
        for item in items:
            identity=(item['kind'],item['text'])
            if item['kind']=='user' or identity in seen:continue
            seen.add(identity);meaningful.append(item)
            if len(meaningful)==3:break
        detail=dict(client=client,key=key,session_id=parts[2],title=title,title_source='客户端聊天名称' if source['title'] else '根据你的要求显示',
            status=status,tone=tone,last_activity_ms=latest_stamp,age_seconds=round(age) if age is not None else None,project=source.get('project'),
            goal=goal,project_goals=origins,previous_progress=checkpoints,earlier_activity=earlier_activity,
            goal_short=clean((user or {}).get('text','尚未读到具体要求。'),96),
            last_step=last_step,
            content=progress_headline((activity or {}).get('text','')) or '暂时没有可读的具体活动，请稍后查看。',
            content_basis='assistant' if activity and activity['kind'] in ('assistant','operation_note') else 'observed',
            needs_you=needs,recent=meaningful,source_unavailable=source['unavailable'],source_missing=source['missing'],
            partial=warnings or source['missing']>0 or material['missing']>0 or len(rows)>=360 or context['window_limited'],
            snapshot=high,scope='最近保存的一段；不是全部任务。',recorder=read_status(self.history.databases[client],client),
            results=results,fragment=fragment,proposals=proposals,turn_marker=latest_marker,
            evidence={k:v for k,v in [('goal',user),('content',activity),('explanation',speech),('reason',reason),('fragment',fragment)] if v})
        detail.update(local_story(user,activity,reason,last_step,fragment))
        content_refs=[dict(title='具体活动',**activity)] if activity else []
        if last_step and (not activity or last_step['sequence']>=activity['sequence']):
            outcome=results[-1]['status']
            name=next((label for pattern,label in [(r'运行测试','检查'),(r'请求查看','查看'),(r'请求修改','修改'),(r'构建程序','生成程序'),(r'交给协助','交接')] if re.search(pattern,last_step['action'])),'操作')
            suffix={'failed':'报告失败。','cancelled':'已取消。','no_receipt':'还没看到结果。','conflict':'结果有冲突。','unresolved':'对应关系不清楚。','unknown':'已收到结果，是否成功还不清楚。','succeeded':'报告成功；整项任务仍需验收。'}[outcome]
            detail['content']=clean(detail['content'],100)+'这次'+name+suffix
            detail['content_basis']='inference' if activity and activity['kind'] in ('assistant','operation_note') else 'observed'
            content_refs.append(dict(title='最近一步及结果',text=last_step['action']+'；'+last_step['result'],event_id=last_step['event_id'],sequence=last_step['sequence']))
        detail['project_context']=self.project_context.get(client,key) if self.project_context else None
        if detail['project_context']:
            brief=detail['project_context']
            before=clean(re.split(r'[。；]',brief['before'])[0],100)
            action_story=local_story(user,activity,reason,last_step,None)
            role=action_story['explanation'] if action_story['explanation_basis']=='inference' else ''
            detail.update(explanation=clean('前面进展：'+before+'。'+(role or '眼前的公开工作线索是“'+detail['content']+'”；其具体作用还需结合后续结果确认。'),160),explanation_basis='inference')
            detail['part_evidence']['explanation']=[dict(title='前面进展（开发记录）',text=brief['before'])]+detail['part_evidence']['explanation']
            if not reason and brief['benefit']:
                detail.update(reason=brief['benefit'],reason_basis='inference')
                detail['part_evidence']['reason']=[dict(title='整体目标',text=brief['goal']),dict(title='项目说明中的用途',text=brief['benefit'])]
        detail['part_evidence']['content']=content_refs
        meaning={k:detail[k] for k in ('title','goal','content','explanation','reason','needs_you','partial','source_unavailable','results','fragment','turn_marker')}
        # Model freshness follows readable meaning, not receipt IDs, repeated
        # opaque calls or polling. Real changed actions/results still invalidate.
        meaning['results']=[{k:r[k] for k in ('text','basis','status')} for r in results if not r['text'].startswith('一次工具操作；')]
        meaning['fragment']={k:fragment[k] for k in ('text','material_kind')} if fragment else None
        meaning['proposals']=[p['text'] for p in proposals]
        meaning['project_goals']=[p['text'] for p in origins];meaning['previous_progress']=[p['text'] for p in checkpoints]
        meaning['earlier_activity']=[p['text'] for p in earlier_activity]
        meaning['current_turn_state']={'这一轮已结束':'ended','这一轮已取消':'cancelled'}.get(detail['status'],'unknown')
        meaning['project_context']=detail['project_context']
        meaning['handoffs']=[(seq,r.get('handoff')) for seq,r in selected if r.get('handoff')]
        meaning['turn']=[newest_user,latest_start];meaning['speech']=(speech or {}).get('text')
        detail['revision']=hashlib.sha256(json.dumps(meaning,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        # Story prose uses object roles; exact excerpts remain in folded proof.
        for part in ('content','explanation','reason'):
            detail[part]=plain_words(detail[part])
        detail['activity_state']=activity_state(detail)
        return detail

    def summary(self,client,key):
        data=self.detail(client,key)
        handoffs=HandoffView(self.history,self.reader).detail(client,key,data['snapshot'])
        return recap(data,handoffs)

    def cards(self):
        cards=[];unavailable=[];limited=False
        for client in self.history.databases:
            try:
                groups=self.history.groups(client,limit=50)['groups']
                with self.history.connect(client) as db:
                    headers=db.execute('SELECT e.record'+FROM+f" WHERE {CLIENT}=? AND {GENERATION}=json_extract(s.state,'$.generation') AND json_extract(e.record,'$.kind')='session_observed' ORDER BY sequence DESC LIMIT 200",[client]).fetchall()
                    helpers={(r.get('source_id'),r.get('generation'),r.get('session_id')) for raw, in headers for r in [json.loads(raw)] if any(link.get('kind')=='spawned_from' and link.get('status')=='reported_by_client' for link in r.get('relationships',[]))}
            except (ValueError,OSError,sqlite3.Error):
                unavailable.append(client);continue
            groups.sort(key=lambda g:((g['source_id'],g['generation'],g['session_id']) in helpers,-g['last_sequence']))
            seen=set()
            for group in groups:
                if not group['session_id'] or group['session_id'].startswith('source-') or group['is_sidechain'] or group['agent_id']:continue
                if group['session_id'] in seen:continue
                seen.add(group['session_id'])
                try:card=catalog_card(self.history,self.reader,client,group,self.clock)
                except (ValueError,OSError,sqlite3.Error):continue
                card['is_helper']=(group['source_id'],group['generation'],group['session_id']) in helpers
                cards.append(card)
                if len(seen)>=20:
                    limited=True;break
        cards.sort(key=lambda c:(c['is_helper'],-(c['last_activity_ms'] or 0)))
        return dict(cards=cards[:60],unavailable=unavailable,limited=limited or len(cards)>60)

    def prepared(self,client,key):
        data=self.detail(client,key);facts=[];references=[];prior_progress=[]
        entries=[('聊天和你的要求',data['title']+'；你的要求：'+data['goal'],'user_request','goal'),
                 ('当前工作线索',data['content'],data['content_basis'],'content'),
                 ('助手公开说明',data['evidence'].get('explanation',{}).get('text','助手尚未留下可显示的文字说明。'),'assistant' if 'explanation' in data['evidence'] else 'unknown','explanation'),
                 ('助手明确说明的原因',data['evidence'].get('reason',{}).get('text','助手未公开说明这一步的原因。'),'assistant' if 'reason' in data['evidence'] else 'unknown','reason')]
        for title,text,basis,field in entries:
            alias='E'+str(len(facts)+1)
            facts.append(dict(evidence_id=alias,record_marker=title,excerpt=text,evidence_class=basis))
            ref=data['evidence'].get(field,{})
            references.append(dict(evidence_id=alias,title=title,quote=text,record_id=ref.get('event_id','未取得原文'),sequence=ref.get('sequence')))
        marker={'turn_started':'曾观察到这一轮开始','turn_ended':'这一轮已结束，不代表任务验收','turn_cancelled':'这一轮已取消'}.get(data['turn_marker'],'暂无明确轮次标记')
        facts.append(dict(evidence_id='E5',record_marker='当前观察范围',excerpt=marker+'；不据此判断当前仍在运行。'+data['needs_you']+('存在缺失或范围限制。' if data['partial'] or data['source_unavailable'] else ''),evidence_class='observed'))
        references.append(dict(evidence_id='E5',title='本机状态说明',quote=facts[-1]['excerpt']))
        current_operation={}
        if data['evidence'].get('content'):
            current_operation['current_work_evidence_id']='E2'
        for index,item in enumerate(data['results']):
            if item['text'].startswith('一次工具操作；'):continue
            alias='E'+str(len(facts)+1)
            facts.append(dict(evidence_id=alias,record_marker='最近一步及对应结果' if index==len(data['results'])-1 else '之前的操作与结果',excerpt=item['text'],evidence_class=item.get('basis','observed')))
            references.append(dict(evidence_id=alias,title='操作与结果',quote=item['text'],record_id=item['event_id'],sequence=item['sequence']))
            if data['last_step'] and item['sequence']==data['last_step']['sequence'] and item['sequence']>=data['evidence'].get('content',{}).get('sequence',0):
                current_operation.update(current_operation_evidence_id=alias,current_operation_status=item['status'])
        for item in data['proposals'][-2:]:
            alias='E'+str(len(facts)+1)
            facts.append(dict(evidence_id=alias,record_marker='拟修改内容，尚未确认写入',excerpt=item['text'],evidence_class='observed'))
            references.append(dict(evidence_id=alias,title='脚本中提出的修改',quote=item['text'],record_id=item['event_id'],sequence=item['sequence']))
        brief=data['project_context'];bridge=[];project_goal_id=None
        if brief:
            for field,title,basis in [('goal','已明确的整体项目目标','user_request'),('before','前几步的开发记录，尚非客户端观察事实','assistant'),('now','阶段安排（计划，不能代替当前动作）','user_request'),('benefit','用户期望得到的实际用途','user_request'),('next','后续计划，尚未完成','user_request')]:
                if not brief[field]:continue
                alias='E'+str(len(facts)+1);quote=brief[field]+'；来源说明：'+brief['source_note']
                if field=='goal':project_goal_id=alias
                if field=='before':prior_progress.append(alias)
                if field in ('before','now'):bridge.append(alias)
                facts.append(dict(evidence_id=alias,record_marker=title,excerpt=quote,evidence_class=basis))
                references.append(dict(evidence_id=alias,title=title,quote=quote,record_id='本机项目说明，非原始活动记录'))
        for title,items,basis in [('这段可读记录中较早的要求，不一定是项目最初目标',data['project_goals'],'user_request'),('前面已有的进展，助手自述',data['previous_progress'],'assistant'),('本轮前面的公开说明，助手自述',data['earlier_activity'],'assistant')]:
            for item in items:
                alias='E'+str(len(facts)+1)
                if basis=='assistant':prior_progress.append(alias)
                facts.append(dict(evidence_id=alias,record_marker=title,excerpt=item['text'],evidence_class=basis))
                references.append(dict(evidence_id=alias,title=title,quote=item['text'],record_id=item['event_id'],sequence=item['sequence']))
        alias='E'+str(len(facts)+1);snippet=data['fragment']
        facts.append(dict(evidence_id=alias,record_marker='实际收到的工具返回短片段' if snippet and snippet.get('material_kind')=='tool_output' else '实际取得的内容片段',excerpt=snippet['text'] if snippet else '未取得可确认的文件内容片段；不得根据文件名编造内容。',evidence_class='observed' if snippet else 'unknown'))
        references.append(dict(evidence_id=alias,title='内容片段',quote=facts[-1]['excerpt'],record_id=snippet['event_id'] if snippet else '',sequence=snippet['sequence'] if snippet else None))
        handoffs=HandoffView(self.history,self.reader).detail(client,key,data['snapshot'])
        for card in handoffs['items'][:3]:
            alias='E'+str(len(facts)+1)
            text=card['title']+'：'+card['sent']+'；'+card['status']+'。'+card['use_note']
            if card['returns']:text+=' 回复（助手自述）：'+'；'.join(r['who']+'：'+clean(r['text'],160) for r in card['returns'][:4])
            facts.append(dict(evidence_id=alias,record_marker='可观察的助手交接（回复属于助手自述）',excerpt=text,evidence_class='assistant' if card['returns'] else 'observed'))
            references.append(dict(evidence_id=alias,title='助手交接',quote=text,record_id=card['evidence'][0]['id'],sequence=card.get('sequence')))
        naming=add_object_names(facts,references,brief)
        payload=dict(scope=dict(glance=True,compose_current_result=True,whole_task_status='unknown',body_text_included=True,untrusted_excerpts=True,
                               bounded_context=True,partial=data['partial'] or data['source_unavailable'] or handoffs['limited'],
                               current_turn_state={'这一轮已结束':'ended','这一轮已取消':'cancelled'}.get(data['status'],'unknown'),
                               previous_progress_evidence_ids=prior_progress,**current_operation),facts=facts)
        if naming:payload['scope']['naming_context_evidence_id']=naming
        if brief:payload['scope'].update(context_bridge_evidence_ids=bridge,project_goal_evidence_id=project_goal_id)
        action=current_operation.get('current_work_evidence_id') or current_operation.get('current_operation_evidence_id')
        payload['scope']['writing_anchors']={
            'content':[action] if action else [],
            'explanation':([action] if action else [])+bridge,
            'reason':[project_goal_id] if project_goal_id else []}
        return data,payload,references
