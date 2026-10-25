"""A bounded, evidence-linked task recap. No inferred completion or reply adoption.

The input is one exact chat snapshot. Public progress is self-report; supplied
project context is a plan, never observed work. Handoffs stay per communication
and recipient, so a later reply cannot silently become another assignment's result.
"""
from source_context import clean


def point(text,basis,refs=()):
    return dict(text=clean(text,440),basis=basis,evidence=list(refs))


def recap(data,handoffs):
    brief=data.get('project_context') or {}
    goal=point(brief['goal'],'user_request',[dict(title='本机项目说明',text=brief['source_note'])]) if brief else point(
        data['project_goals'][0]['text'] if data['project_goals'] else data['goal'],
        'user_request' if data['project_goals'] or data['evidence'].get('goal') else 'unknown',
        data['project_goals'][:1])
    before=[]
    if brief.get('before'):before.append(point(brief['before'],'assistant',[dict(title='提供的开发背景，非客户端观察事实',text=brief['source_note'])]))
    for item in reversed(data['previous_progress']):
        before.append(point(item['text'],'assistant',[item]))
    for item in reversed(data.get('earlier_activity',[])):
        before.append(point(item['text'],'assistant',[dict(item,title='本轮较早的公开说明')]))
    now=point(data['content'],data['content_basis'],data['part_evidence'].get('content',[]))
    outcomes=[point(r['text'],r['basis'],[dict(title='操作和对应结果',event_id=r['event_id'],sequence=r['sequence'],text=r['text'])])
              for r in data['results'] if not r['text'].startswith('一次工具操作；')][-3:]
    exchanges=[]
    for card in handoffs['items'][:6]:
        # Never join independent cards by recipient name or presumed task.
        receivers=[]
        for target in card['targets']:
            replies=[r['text'] for r in card['returns'] if r.get('target_id')==target['id']]
            receivers.append(dict(who=target['label'],state=target['state'],
                reply=clean('；'.join(replies),360) if replies else '这次交接没有可确认的回复正文。',
                reply_basis='assistant' if replies else 'unknown',input_note=target['input_note']))
        exchanges.append(dict(title=card['title'],request=card['sent'],status=card['status'],
            receivers=receivers,conflict=card.get('conflict',False),
            adoption='尚未确认主助手如何采用回复；收到回复不等于完成整项任务。',
            evidence=card['evidence']))
    limits=['这是一份依据可读记录整理的小结，不是对整项任务的完成验收。',
            '前面进展来自助手公开汇报或提供的项目背景，不代表每项成果都已经核验。']
    if data['partial'] or data['source_unavailable'] or handoffs['limited']:
        limits.append('记录存在缺失或查看范围限制；未看到的步骤、回复和结果没有补猜。')
    if handoffs['items'] and not exchanges:limits.append('没有可汇总的交接内容。')
    return dict(snapshot=data['snapshot'],goal=goal,before=before[-3:],now=now,outcomes=outcomes,
        next=point(brief['next'],'plan',[dict(title='后续计划，尚未完成',text=brief['source_note'])]) if brief.get('next') else point('尚未取得明确的后续安排，请以原聊天为准。','unknown'),
        handoffs=exchanges,handoff_empty='这段可读记录中没有可确认的助手交接；不代表整个任务从未委派。',
        limited=bool(data['partial'] or data['source_unavailable'] or handoffs['limited']),
        whole_task_status='unknown',limits=limits)
