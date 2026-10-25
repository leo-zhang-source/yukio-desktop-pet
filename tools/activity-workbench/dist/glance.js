'use strict';
const $=id=>document.getElementById(id), make=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const names={codex:'Codex',claude:'Claude',deepcode:'Deep Code'}, basis={observed:'记录所见',assistant:'助手自述',user_request:'你的要求',inference:'推测',unknown:'尚不清楚'};
let selected=null, current=null, epoch=0, busy=false, cardsAt=0, model=null, grant=null, autoBusy=false, modelAnswer=null, previewOpen=false, refreshAgain=false, synthetic=false, modelPending=false, attemptMessage="";
function continuation(selection,cards){
 // A resumed chat can move to a new file. Match explicit client/session/agent
 // identity, never a title. This only changes the current page selection.
 const identity=value=>{try{const key=value.key.replace(/-/g,'+').replace(/_/g,'/'),p=JSON.parse(atob(key+'='.repeat((4-key.length%4)%4)));return Array.isArray(p)&&p.length===5&&typeof p[2]==='string'&&p[2]&&!p[2].startsWith('source-')?JSON.stringify([value.client,p[2],p[3],p[4]]):null;}catch{return null;}};
 const prior=identity(selection);if(!prior)return null;
 const matches=cards.filter(c=>identity(c)===prior);
 return matches.length===1?{client:matches[0].client,key:matches[0].key}:null;
}
async function api(route,data){
 let response;
 try{response=await fetch('/api/'+route,{method:data?'POST':'GET',headers:{'X-Yukio-Workbench':'1',...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{}),cache:'no-store',signal:AbortSignal.timeout(65000)});}
 catch(error){throw Error(error.name==='TimeoutError'?'这次等待时间较长，请稍后重试。已有记录仍可查看。':'工作台连接已断开。请重新打开桌面上的“雪绪活动工作台”；这里保留的是断开前的内容。');}
 let value;try{value=await response.json();}catch{throw Error('暂时没读到可显示的消息，请刷新页面或重新打开工作台。');}
 if(!response.ok)throw Object.assign(Error(value.error||'暂时没读到新消息，原来的记录仍然保留。'),{reason:value.reason});return value;
}
function note(text){$('alert').textContent=text;$('alert').hidden=!text;}
function emptyHelp(clients){$('emptyClients').replaceChildren();for(const c of clients){const state=c.recorder?.state;const text=state==='source_unavailable'?'暂时没读到客户端留下的聊天':state==='waiting'||state==='starting'?'正在等新聊天':state==='active'?'已发现活动，正在整理':state==='partial_history'||state==='degraded'?'有些记录暂时读不到':'还没有可显示的新记录';$('emptyClients').append(make('p',names[c.id]+'：'+text+'。'));}}
function age(stamp){if(!stamp)return '时间未提供';const seconds=Math.max(0,Math.round((Date.now()-stamp)/1000));return seconds<60?'刚刚':seconds<3600?Math.floor(seconds/60)+' 分钟前':seconds<86400?Math.floor(seconds/3600)+' 小时前':Math.floor(seconds/86400)+' 天前';}
function proof(refs){$('evidence').replaceChildren();for(const ref of refs){const p=make('p');p.append(make('span',ref.title+' · '),make('span',ref.quote||ref.text||''));$('evidence').append(p);}}
function proofModel(target,answer,withText=false){target.replaceChildren();for(const item of answer.result.explanations){target.append(make('p',({content:'内容',explanation:'解释',reason:'原因'})[item.part]+(withText?'：'+item.text:'的依据')));for(const id of item.evidence_ids){const ref=answer.refs.find(r=>r.evidence_id===id);if(ref)target.append(make('blockquote',ref.title+'：'+ref.quote));}if(!item.evidence_ids.length)target.append(make('p','没有足够依据，保留未知。'));}}
function partProof(part,kind,refs){
 const button=$(part+'Basis'),box=$(part+'Proof');button.textContent=(basis[kind]||'尚不清楚')+' · 依据';box.replaceChildren();
 for(const ref of refs)box.append(make('blockquote',(ref.title?ref.title+'：':'')+(ref.quote||ref.text||'')));
 if(!refs.length)box.append(make('p','这部分暂时没有足够依据，先保留未知。'));
}
function showStory(data){for(const part of ['content','explanation','reason']){
 $(part).textContent=data[part];const ref=data.evidence[part==='explanation'?'fragment':part];
 partProof(part,data[part+'_basis'],data.part_evidence?.[part]||(ref?[{quote:ref.text}]:[]));
}}
function showAnswer(result,refs,snapshot,revision){
 if(result.mode!=='model'){modelAnswer=null;attemptMessage=result.message||'千问暂时没能解释，保留本机已知情况。';render(current);return;}
 attemptMessage='';modelAnswer={result,refs,snapshot,revision};render(current);
}
function render(data){current=data;if($('handoffBox').open)loadHandoffs();if($('taskSummaryBox').open)loadTaskSummary();$('work').hidden=false;$('empty').hidden=true;$('title').textContent=data.title;$('status').textContent=data.status;$('status').className='status '+data.tone;$('goal').textContent=data.goal;$('goalShort').textContent=data.project_context?.goal||data.goal_short||data.goal;$('goalLabel').textContent=data.project_context?'整个任务':'这次的要求';$('projectFocus').hidden=!data.project_context;$('projectFocus').textContent=data.project_context?.now||'';$('projectBox').hidden=!data.project_context;$('projectText').textContent=data.project_context?['前面：'+data.project_context.before,'现在：'+data.project_context.now,'接下来：'+data.project_context.next,'来源：'+data.project_context.source_note].join('\n\n'):'';$('attention').hidden=data.tone!=='attention';$('attention').textContent=data.needs_you;
 $('latestStep').hidden=!data.last_step;if(data.last_step){$('stepAction').textContent=data.last_step.action;$('stepResult').textContent=data.last_step.result;}
 $('historyLink').href='/history?'+new URLSearchParams({client:data.client,key:data.key});
 $('scope').textContent=(data.source_unavailable?'这段原文暂时读不到，等待来源恢复。':data.partial?'这次只看到一部分，缺失内容没有补猜。':'依据最近可读取的一段聊天。')+' '+age(data.last_activity_ms)+'有活动。';
 $('recent').replaceChildren();for(const item of data.recent)$('recent').append(make('p',(item.kind==='assistant'?'助手说：':'观察到：')+item.text));
 const applicable=modelAnswer&&modelAnswer.revision===data.revision;
 $('previousModel').hidden=!modelAnswer||applicable;
 if(applicable){for(const item of modelAnswer.result.explanations){$(item.part).textContent=item.text;partProof(item.part,item.basis,item.evidence_ids.map(id=>modelAnswer.refs.find(r=>r.evidence_id===id)).filter(Boolean));}proofModel($('evidence'),modelAnswer);if(!modelPending)$('modelNote').textContent=(grant?'千问正在持续解释这段聊天':'当前显示千问说明')+' · 下方三段已更新，可展开依据';}
 else {showStory(data);proof(Object.entries(data.evidence).map(([key,item])=>({title:({goal:'你的要求',content:'具体活动',explanation:'助手说明',reason:'原因出处',fragment:'所见短片段'})[key],quote:item.text})));
  if(!modelPending)$('modelNote').textContent=attemptMessage|| (modelAnswer?'工作已有变化，当前显示本机说明；上一次千问说明已收在下方。':grant?'当前显示本机新记录，千问会稍后更新这段聊天的说明。':model?.configured?'当前显示本机说明。想看结合上下文的千问说明，请点上方按钮。':'当前显示本机说明；尚未配置千问，仍可查看下面三段与依据。');
  if(modelAnswer)proofModel($('previousText'),modelAnswer,true);
 }
 $('explain').textContent=grant?'更新千问说明':'让千问解释这段聊天';$('explain').disabled=!model?.configured||previewOpen||modelPending||autoBusy;if(!synthetic&&['stopped','failed','stale','unavailable'].includes(data.recorder?.state)){
 $('status').textContent='显示上次内容';$('status').className='status quiet';note('新记录暂时没跟上，这里保留的是之前的工作。请重新打开桌面上的“雪绪活动工作台”。');}
 if(!synthetic&&data.recorder?.state==='paused_capacity'){$('status').textContent='保存暂时停下了';$('status').className='status quiet';note('旧记录仍可查看。请先检查电脑上的可用空间，再重新打开工作台。');}
 if(data.source_unavailable){$('status').textContent='这段原文暂时读不到';$('status').className='status quiet';}}
let summaryEpoch=0,summaryBusy=false,handoffBusy=false;
function updateExpanded(box,data,draw){
 // Polling must not collapse the evidence someone is reading. Ignore a pure
 // snapshot advance and leave an unchanged subtree (including focus) intact.
 const {snapshot,...visible}=data,key=JSON.stringify(visible);
 if(box.dataset.contentKey===key)return;
 const opened=new Set([...box.querySelectorAll('details[open]')].map(n=>n.dataset.detailKey).filter(Boolean));
 const focused=box.contains(document.activeElement)?document.activeElement.closest('details')?.dataset.detailKey:null;
 box.replaceChildren();draw();box.dataset.contentKey=key;
 for(const item of box.querySelectorAll('details')){if(opened.has(item.dataset.detailKey))item.open=true;if(focused&&item.dataset.detailKey===focused)item.querySelector('summary')?.focus();}
}
function summaryPoint(box,title,item){
 const section=make('section');section.className='summary-section';section.append(make('h3',title),make('p',item.text));
 const refs=make('details');refs.dataset.detailKey=JSON.stringify([title,item.text]);refs.append(make('summary',(item.basis==='plan'?'后续计划':basis[item.basis]||'尚不清楚')+' · 查看依据'));
 for(const ref of item.evidence||[])refs.append(make('blockquote',ref.text||ref.quote||'记录位置已保留，可在交接详情核对。'));
 if(!(item.evidence||[]).length)refs.append(make('p','没有足够的可读依据。'));section.append(refs);box.append(section);
}
async function loadTaskSummary(){
 if(summaryBusy||!selected)return;summaryBusy=true;
 const own=++summaryEpoch,selection={...selected};
 try{const data=await api('task-summary?'+new URLSearchParams(selection));if(own!==summaryEpoch||JSON.stringify(selection)!==JSON.stringify(selected))return;
 const box=$('taskSummary');updateExpanded(box,data,()=>{summaryPoint(box,'原本要做什么',data.goal);
 if(!data.before.length)box.append(make('p','前面的进展暂时没有可读依据。'));
 for(const [i,item] of data.before.entries())summaryPoint(box,i===0?'前面做到哪':'此前的公开汇报',item);
 summaryPoint(box,'眼前在做什么',data.now);
 for(const item of data.outcomes)summaryPoint(box,'最近操作的已知结果',item);
 summaryPoint(box,'接下来',data.next);box.append(make('h3','助手交接小结'));
 if(!data.handoffs.length)box.append(make('p',data.handoff_empty));
 for(const item of data.handoffs){const card=make('section');card.className='handoff-card';card.append(make('h4',item.title),make('p','交代的事：'+item.request),make('p',item.status));
 if(!item.receivers.length)card.append(make('p','具体接收者尚不能确认。'));
 for(const receiver of item.receivers)card.append(make('p',receiver.who+'：'+receiver.reply),make('p',receiver.input_note));
 card.append(make('p',item.adoption));const refs=make('details');refs.dataset.detailKey=JSON.stringify(item.evidence);refs.append(make('summary','查看交接依据'));for(const ref of item.evidence)refs.append(make('p',ref.label+' · '+ref.id));card.append(refs);box.append(card);}
 for(const text of data.limits){const p=make('p',text);p.className='scope';box.append(p);}
 });
 }catch(error){if(own===summaryEpoch){delete $('taskSummary').dataset.contentKey;$('taskSummary').replaceChildren(make('p','小结暂时读不到，当前工作和原记录仍可查看。'));}}
 finally{summaryBusy=false;}
}
$('taskSummaryBox').addEventListener('toggle',()=>{if($('taskSummaryBox').open)loadTaskSummary();else summaryEpoch++;});
let handoffEpoch=0;
async function loadHandoffs(){
 if(handoffBusy||!selected)return;handoffBusy=true;
 const own=++handoffEpoch, selection={...selected};
 try{const data=await api('handoffs?'+new URLSearchParams(selection));if(own!==handoffEpoch||JSON.stringify(selection)!==JSON.stringify(selected))return;
 const box=$('handoffs');updateExpanded(box,data,()=>{
 if(!data.items.length)box.append(make('p','这段记录里还没有可确认的助手交接。'));
 const states={pending_init:'等待准备',running:'当时正在工作',completed:'当时这一轮已结束',interrupted:'当时被打断',errored:'当时遇到错误',shutdown:'当时已关闭',not_found:'当时未找到',unknown:'状态不明确'};
 for(const item of data.items){const card=make('section');card.className='handoff-card';card.append(make('h3',item.title),make('p',item.sent),make('p',item.status));
 for(const target of item.targets){const p=make('p');if(target.key){const a=make('a',target.label+' ↗');a.href='/?'+new URLSearchParams({client:selection.client,key:target.key});p.append(a);}else p.append(make('span',target.label));p.append(make('span',' · '+(states[target.state]||states.unknown)));card.append(p,make('p',target.input_note||item.input_note));}
 if(!item.targets.length)card.append(make('p',item.input_note));
 for(const reply of item.returns)card.append(make('blockquote',reply.who+'回复：'+reply.text));
 if(!item.returns.length)card.append(make('p','这次交接没有可显示的回复正文。'));
 card.append(make('p',item.use_note));const details=make('details'),summary=make('summary','查看这次交接的依据');details.dataset.detailKey=JSON.stringify(item.evidence);details.append(summary);for(const ref of item.evidence)details.append(make('p',ref.label+' · '+ref.id));card.append(details);box.append(card);}
 box.append(make('p',data.note+(data.limited?' 这里只显示最近一部分交接。':'')));
 });
 }catch(error){if(own===handoffEpoch){delete $('handoffs').dataset.contentKey;$('handoffs').replaceChildren(make('p','暂时没读到交接信息，已有工作说明仍可查看。'));}}
 finally{handoffBusy=false;}
}
$('handoffBox').addEventListener('toggle',()=>{if($('handoffBox').open)loadHandoffs();});
async function stopAuto(){const old=grant;grant=null;$('stopAuto').hidden=true;if(old){try{await api('glance-stop',{grant:old});}catch{}}}
async function choose(value){epoch++;selected=JSON.parse(value);window.history?.replaceState(null,'','/?'+new URLSearchParams(selected));modelAnswer=null;attemptMessage='';previewOpen=false;$('preview').hidden=true;$('work').hidden=true;$('detailsBox').open=false;$('taskSummaryBox').open=false;$('taskSummary').replaceChildren();delete $('taskSummary').dataset.contentKey;delete $('handoffs').dataset.contentKey;summaryEpoch++;handoffEpoch++;for(const part of ['content','explanation','reason']){$(part+'Proof').hidden=true;$(part+'Basis').setAttribute('aria-expanded','false');}await stopAuto();await refresh(true);}
async function refresh(force=false){if(busy){refreshAgain=refreshAgain||force;return;}if(document.hidden&&!force)return;busy=true;const own=epoch;try{
 if(force||Date.now()-cardsAt>30000){const data=await api('current');if(own!==epoch)return;cardsAt=Date.now();const prior=selected?JSON.stringify(selected):'';$('chat').replaceChildren();
 for(const [helper,label] of [[false,'你的聊天'],[true,'协助助手的工作']]){const group=make('optgroup');group.label=label;for(const c of data.cards.filter(c=>Boolean(c.is_helper)===helper)){const option=make('option',names[c.client]+' · '+c.title+' · '+age(c.last_activity_ms));option.value=JSON.stringify({client:c.client,key:c.key});group.append(option);}if(group.children.length)$('chat').append(group);}
 note('');$('connection').textContent=synthetic?'模拟活动 · 用于检查':data.cards.length?'已连接本机记录':'已连接 · 等待聊天';if(!data.cards.length){$('work').hidden=true;$('empty').hidden=false;$('chat').append(make('option','尚未发现可显示的聊天'));try{const info=await api('clients');if(own===epoch)emptyHelp(info.clients);}catch{}return;}
 if(prior&&[...$('chat').options].some(o=>o.value===prior))$('chat').value=prior;
 else if(selected){const next=continuation(selected,data.cards);if(next){await choose(JSON.stringify(next));return;}const option=make('option',names[selected.client]+' · '+(current?.title||'当前聊天'));option.value=prior;$('chat').prepend(option);$('chat').value=prior;}
 else selected=JSON.parse($('chat').value);}
 if(!selected)return;const data=await api('glance?'+new URLSearchParams(selected));if(own!==epoch)return;note('');render(data);$('connection').textContent=synthetic?'模拟活动 · 用于检查':'已连接本机记录';$('refreshNote').textContent=synthetic?'模拟活动 · 用于检查':'自动跟进新消息';
 }catch(error){if(own===epoch){note(error.message);$('connection').textContent='暂未连上';if(current){$('status').textContent='显示断开前内容';$('status').className='status quiet';}}}finally{busy=false;if(refreshAgain){refreshAgain=false;refresh(true);}}}
async function explain(){if(!selected)return;const own=epoch,selection={...selected};$('explain').disabled=true;try{const preview=await api('glance-preview',selection);if(own!==epoch)return;const box=$('preview');box.replaceChildren(make('h2','让千问结合这段聊天解释'),make('p','发送到你的内网模型：'+preview.model+' · '+preview.destination),make('p','说明生成后会直接显示在本页的“内容、解释、原因”三处。只解释你当前选中的这段聊天。'),make('p',preview.excluded));for(const f of preview.payload.facts){box.append(make('strong',f.record_marker),make('blockquote',f.excerpt));}
 box.append(make('p','开启自动说明后，只跟进这段聊天，后续发送同类短摘录；至少间隔 3 分钟，最长 2 小时。切换聊天、关闭页面或点停止，就会结束。'));
 const buttons=make('div');buttons.className='confirm-buttons';const send=make('button','同意，只解释这一次'),automatic=make('button','同意，持续解释这段聊天'),cancel=make('button','先不用');send.className='primary';buttons.append(send,automatic,cancel);box.append(buttons);box.hidden=false;previewOpen=true;
 cancel.onclick=()=>{box.hidden=true;previewOpen=false;$('explain').disabled=!model?.configured;};
 const generate=async(auto)=>{send.disabled=true;automatic.disabled=true;cancel.disabled=true;try{if(auto){await stopAuto();const approved=await api('glance-authorize',{token:preview.token,consent:true});if(own!==epoch){await api('glance-stop',{grant:approved.grant});return;}grant=approved.grant;$('stopAuto').hidden=false;}
 attemptMessage='';modelPending=true;$('modelNote').textContent='千问正在组织说明…';const result=await api('explanation-generate',{token:preview.token,consent:true});if(own!==epoch)return;const latest=await api('glance?'+new URLSearchParams(selection));if(own!==epoch)return;render(latest);box.hidden=true;previewOpen=false;modelPending=false;showAnswer(result,preview.references,preview.snapshot,preview.revision);
 }catch(error){if(own===epoch){note(error.message);$('modelNote').textContent='说明未完成，原文仍然可看。';}}finally{modelPending=false;send.disabled=false;automatic.disabled=false;cancel.disabled=false;$('explain').disabled=!model?.configured||previewOpen;}};
 send.onclick=()=>generate(false);automatic.onclick=()=>generate(true);
 }catch(error){if(own===epoch)note(error.message);}finally{$('explain').disabled=!model?.configured||previewOpen||modelPending;}}
async function automatic(force=false){if(!grant||autoBusy||(!force&&document.hidden)||previewOpen)return;autoBusy=true;const own=epoch,token=grant;$('explain').disabled=true;if(force)$('modelNote').textContent='正在结合项目背景整理说明…';try{const data=await api('glance-refresh',{grant:token,...(force?{force:true}:{})});if(own===epoch&&grant===token&&data.mode==='updated'){const latest=await api('glance?'+new URLSearchParams(selected));if(own!==epoch||grant!==token)return;render(latest);showAnswer(data.result,data.references,data.snapshot,data.revision);}}catch(error){if(own===epoch){if(['preview_expired','consent_required'].includes(error.reason)){await stopAuto();$('explain').textContent='让千问解释这段聊天';note('本次自动说明已到期或停止，请重新设置。');}else note('说明暂时没有更新，原有设置仍然保留：'+error.message);}}finally{autoBusy=false;if(own===epoch)$('explain').disabled=!model?.configured||previewOpen||modelPending;}}
$('chat').onchange=()=>choose($('chat').value);$('reload').onclick=()=>refresh(true);$('explain').onclick=()=>grant?automatic(true):explain();$('stopAuto').onclick=async()=>{await stopAuto();$('explain').textContent='让千问解释这段聊天';$('modelNote').textContent='自动说明已停止';};
for(const part of ['content','explanation','reason'])$(part+'Basis').onclick=()=>{const box=$(part+'Proof');box.hidden=!box.hidden;$(part+'Basis').setAttribute('aria-expanded',String(!box.hidden));};
window.addEventListener('pagehide',()=>{if(grant)fetch('/api/glance-stop',{method:'POST',headers:{'Content-Type':'application/json','X-Yukio-Workbench':'1'},body:JSON.stringify({grant}),keepalive:true}).catch(()=>{});});
(async()=>{try{const initial=new URLSearchParams(location.search);if(names[initial.get('client')]&&/^[A-Za-z0-9_-]{1,4096}$/.test(initial.get('key')||''))selected={client:initial.get('client'),key:initial.get('key')};const data=await api('clients');model=data.explanation;synthetic=data.mode==='synthetic';if(synthetic)$('connection').textContent='模拟活动 · 用于检查';$('modelDetails').textContent=model?.configured?'已配置 '+model.model+'；每小时最多 '+model.max_calls_per_hour+' 次。':'未配置模型，仍可查看本机原文说明。';await refresh(true);if(data.mode==='synthetic'){$('refreshNote').textContent='模拟活动 · 用于检查';document.title='雪绪 · 模拟当前工作';}}catch(error){note(error.message);}})();
setInterval(()=>refresh(),6000);setInterval(automatic,15000);
