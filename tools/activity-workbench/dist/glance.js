'use strict';
var tr=globalThis.YukioI18n?.t||(value=>value);
var uiLanguage=globalThis.YukioI18n?.language||'zh';
const $=id=>document.getElementById(id), make=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const names={codex:'Codex',claude:'Claude',deepcode:'Deep Code'}, basis={observed:tr('记录所见'),assistant:tr('助手自述'),user_request:tr('你的要求'),inference:tr('推测'),unknown:tr('尚不清楚')};
let selected=null, current=null, epoch=0, busy=false, cardsAt=0, model=null, grant=null, modelAnswer=null, refreshAgain=false, synthetic=false, modelPending=false, attemptMessage='', pageClosed=false, autoRun=null, nextRetry=0;
let chatCatalog=[],chatFilter='recent',chatSearch='',chatLimited=false;
const openProjects=new Set(),activityLabels={working:tr('正在工作'),waiting:tr('等你处理'),inactive:tr('本轮已结束'),unknown:tr('状态待确认')};
const chatValue=c=>JSON.stringify({client:c.client,key:c.key});
function filteredChats(cards,filter,query){
 const search=query.trim().toLocaleLowerCase();
 return cards.filter(c=>(filter==='recent'||filter==='working'&&['working','waiting'].includes(c.activity_state)||filter==='inactive'&&c.activity_state==='inactive')&&
 (!search||[c.title,c.project?.name,names[c.client]].filter(Boolean).join(' ').toLocaleLowerCase().includes(search)));
}
function projectGroups(cards){
 const groups=new Map();for(const card of cards){if(!card.project?.id)continue;const id=card.project.id;
 if(!groups.has(id))groups.set(id,{...card.project,cards:[]});groups.get(id).cards.push(card);}
 return [...groups.values()];
}
function toggleChatBrowser(open){
 document.body?.classList.toggle('chat-nav-open',open);$('chatBrowse').setAttribute('aria-expanded',String(open));
 if(open)$('chatSearch').focus();
}
function chatRow(card){
 const button=make('button');button.className='chat-row';button.type='button';button.dataset.chatValue=chatValue(card);
 const chosen=selected&&button.dataset.chatValue===chatValue(selected);button.className+=chosen?' selected':'';
 button.setAttribute('aria-current',chosen?'true':'false');button.title=card.title;
 const text=make('span');text.className='chat-row-text';const title=make('span',card.title);title.className='chat-row-title';
 const meta=make('span',names[card.client]+(card.is_helper?tr(' · 协助助手'):'')+' · '+(activityLabels[card.activity_state]||tr('状态待确认'))+' · '+age(card.last_activity_ms));meta.className='chat-row-meta';text.append(title,meta);
 const state=card.activity_state||'unknown',dot=make('span');dot.className='chat-state '+state;dot.setAttribute('aria-label',activityLabels[state]);dot.title=activityLabels[state];
 button.append(dot,text);button.onclick=()=>{toggleChatBrowser(false);void choose(chatValue(card));};return button;
}
function renderChatNavigation(){
 const shown=filteredChats(chatCatalog,chatFilter,chatSearch),signature=JSON.stringify([shown.map(c=>[c.key,c.title,c.project,c.activity_state,age(c.last_activity_ms)]),selected,chatFilter,chatSearch]);
 const list=$('chatLists');if(list.dataset.signature===signature)return;list.dataset.signature=signature;
 const focused=list.contains(document.activeElement)?document.activeElement?.dataset.chatValue:null;let restore;
 const add=(container,card)=>{const row=chatRow(card);container.append(row);if(row.dataset.chatValue===focused)restore=row;};
 for(const [filter,id] of [['recent','filterRecent'],['working','filterWorking'],['inactive','filterInactive']]){
  const button=$(id);button.setAttribute('aria-pressed',String(chatFilter===filter));button.className='chat-filter'+(chatFilter===filter?' active':'');
  $(id+'Count').textContent=String(filteredChats(chatCatalog,filter,'').length);
 }
 list.replaceChildren();const projects=projectGroups(shown);
 if(projects.length){list.append(make('h2',tr('项目')));for(const group of projects){
  const folder=make('details');folder.className='chat-project';folder.open=openProjects.has(group.id)||Boolean(chatSearch);
  const heading=make('summary');heading.append(make('span','▱'),make('span',group.name),make('small',String(group.cards.length)));folder.append(heading);
  folder.addEventListener('toggle',()=>{if(folder.open)openProjects.add(group.id);else openProjects.delete(group.id);});
  const rows=make('div');rows.className='project-chats';for(const card of group.cards)add(rows,card);folder.append(rows);list.append(folder);
 }}
 list.append(make('h2',chatSearch?tr('搜索结果'):chatFilter==='working'?tr('正在工作'):chatFilter==='inactive'?tr('未在工作'):tr('最近聊天')));
 for(const card of shown.filter(c=>!c.is_helper))add(list,card);
 const helpers=shown.filter(c=>c.is_helper);if(helpers.length){const section=make('details');section.className='chat-project';section.append(make('summary',tr('协助助手的工作 · ')+helpers.length));for(const card of helpers)add(section,card);list.append(section);}
 if(!shown.length){const message=make('p',chatSearch?tr('没有找到相符的聊天。'):chatFilter==='working'?tr('暂时没有确认正在工作的聊天。'):chatFilter==='inactive'?tr('暂时没有确认已结束的聊天。'):tr('还没有读到聊天记录。'));message.className='chat-list-empty';list.append(message);}
 $('chatListNote').textContent=chatLimited?tr('先显示最近读到的聊天；更早的内容可在记录详情查看。'):tr('按本机读到的记录整理。缺少依据时保留“状态待确认”。');
 restore?.focus();
}
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
 try{response=await fetch('/api/'+route,{method:data?'POST':'GET',headers:{'X-Yukio-Workbench':'1','X-Yukio-Language':uiLanguage,...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{}),cache:'no-store',signal:AbortSignal.timeout(65000)});}
 catch(error){throw Error(error.name==='TimeoutError'?tr('这次等待时间较长，请稍后重试。已有记录仍可查看。'):tr('工作台连接已断开。请重新打开桌面上的“雪绪活动工作台”；这里保留的是断开前的内容。'));}
 let value;try{value=await response.json();}catch{throw Error(tr('暂时没读到可显示的消息，请刷新页面或重新打开工作台。'));}
 if(!response.ok)throw Object.assign(Error(value.error||tr('暂时没读到新消息，原来的记录仍然保留。')),{reason:value.reason});return value;
}
function note(text){$('alert').textContent=text;$('alert').hidden=!text;}
function emptyHelp(clients){$('emptyClients').replaceChildren();for(const c of clients){const state=c.recorder?.state;const text=state==='source_unavailable'?tr('暂时没读到客户端留下的聊天'):state==='waiting'||state==='starting'?tr('正在等新聊天'):state==='active'?tr('已发现活动，正在整理'):state==='partial_history'||state==='degraded'?tr('有些记录暂时读不到'):tr('还没有可显示的新记录');$('emptyClients').append(make('p',names[c.id]+'：'+text+'。'));}}
function age(stamp){if(synthetic)return tr('模拟时间');if(uiLanguage==='en'&&stamp){const seconds=Math.max(0,Math.round((Date.now()-stamp)/1000));const r=new Intl.RelativeTimeFormat('en',{numeric:'auto'});return seconds<60?'just now':seconds<3600?r.format(-Math.floor(seconds/60),'minute'):seconds<86400?r.format(-Math.floor(seconds/3600),'hour'):r.format(-Math.floor(seconds/86400),'day');}if(!stamp)return tr('时间未提供');const seconds=Math.max(0,Math.round((Date.now()-stamp)/1000));return seconds<60?tr('刚刚'):seconds<3600?Math.floor(seconds/60)+tr(' 分钟前'):seconds<86400?Math.floor(seconds/3600)+tr(' 小时前'):Math.floor(seconds/86400)+tr(' 天前');}
function proof(refs){$('evidence').replaceChildren();for(const ref of refs){const p=make('p');p.append(make('span',ref.title+' · '),make('span',ref.quote||ref.text||''));$('evidence').append(p);}}
function proofModel(target,answer,withText=false){target.replaceChildren();for(const item of answer.result.explanations){target.append(make('p',({content:tr('内容'),explanation:tr('解释'),reason:tr('原因')})[item.part]+(withText?'：'+item.text:tr('的依据'))));for(const id of item.evidence_ids){const ref=answer.refs.find(r=>r.evidence_id===id);if(ref)target.append(make('blockquote',ref.title+'：'+ref.quote));}if(!item.evidence_ids.length)target.append(make('p',tr('没有足够依据，保留未知。')));}}
function partProof(part,kind,refs){
 const button=$(part+'Basis'),box=$(part+'Proof');button.textContent=(basis[kind]||tr('尚不清楚'))+tr(' · 依据');box.replaceChildren();
 for(const ref of refs)box.append(make('blockquote',(ref.title?ref.title+'：':'')+(ref.quote||ref.text||'')));
 if(!refs.length)box.append(make('p',tr('这部分暂时没有足够依据，先保留未知。')));
}
function showStory(data){for(const part of ['content','explanation','reason']){
 $(part).textContent=uiLanguage==='en'&&/[\u4e00-\u9fff]/.test(data[part])?({content:'The assistant has shared an update in this chat. An English explanation is being prepared.',explanation:'Supporting records are available. The connection with earlier work has not yet been explained in English.',reason:'The purpose of this step needs to be explained using the request and previous progress; a tool reply alone cannot establish it.'})[part]:data[part];const ref=data.evidence[part==='explanation'?'fragment':part];
 partProof(part,data[part+'_basis'],data.part_evidence?.[part]||(ref?[{quote:ref.text}]:[]));
}}
function showAnswer(result,refs,snapshot,revision){
 if(result.mode!=='model'){attemptMessage=result.message||tr('千问暂时没能解释，先保留已有说明。');render(current);return;}
 attemptMessage='';modelAnswer={result,refs,snapshot,revision};render(current);
}
function render(data){current=data;$('chatName').textContent=data.title;$('chatLocation').textContent=names[data.client]+tr(' · 当前查看');
 // Navigation reads the latest lifecycle marker independently. The bounded
 // explanation excerpt may omit that marker in a long turn; it must not
 // replace the catalogue's state with a less complete observation.
 renderChatNavigation();if($('handoffBox').open)loadHandoffs();if($('taskSummaryBox').open)loadTaskSummary();$('work').hidden=false;$('empty').hidden=true;$('title').textContent=data.title;$('status').textContent=data.status;$('status').className='status '+data.tone;$('goal').textContent=data.goal;$('goalShort').textContent=data.project_context?.goal||data.goal_short||data.goal;$('goalLabel').textContent=data.project_context?tr('整个任务'):tr('这次的要求');$('projectFocus').hidden=!data.project_context;$('projectFocus').textContent=data.project_context?.now||'';$('projectBox').hidden=!data.project_context;$('projectText').textContent=data.project_context?[tr('前面：')+data.project_context.before,tr('现在：')+data.project_context.now,tr('接下来：')+data.project_context.next,tr('来源：')+data.project_context.source_note].join('\n\n'):'';$('attention').hidden=data.tone!=='attention';$('attention').textContent=data.needs_you;
 $('latestStep').hidden=!data.last_step;if(data.last_step){$('stepAction').textContent=data.last_step.action;$('stepResult').textContent=data.last_step.result;}
 $('historyLink').href='/history?'+new URLSearchParams({client:data.client,key:data.key,lang:uiLanguage});
 $('scope').textContent=(data.source_unavailable?tr('这段原文暂时读不到，等待来源恢复。'):data.partial?tr('这次只看到一部分，缺失内容没有补猜。'):tr('依据最近可读取的一段聊天。'))+' '+(uiLanguage==='en'?'Last activity: '+age(data.last_activity_ms)+'.':age(data.last_activity_ms)+tr('有活动。'));
 $('recent').replaceChildren();for(const item of data.recent)$('recent').append(make('p',(item.kind==='assistant'?tr('助手说：'):tr('观察到：'))+item.text));
 const applicable=modelAnswer&&modelAnswer.revision===data.revision;
 $('previousModel').hidden=true;
 // A single requested explanation is a snapshot, not a live claim. Keep it
 // readable when more work arrives, explicitly label its age, and reset it on
 // chat/source changes. A polling/tool event must not erase it immediately.
 if(modelAnswer){for(const item of modelAnswer.result.explanations){$(item.part).textContent=item.text;partProof(item.part,item.basis,item.evidence_ids.map(id=>modelAnswer.refs.find(r=>r.evidence_id===id)).filter(Boolean));}proofModel($('evidence'),modelAnswer);$('modelNote').textContent=attemptMessage||(applicable?tr('千问说明 · 自动跟进这段聊天'):modelPending?tr('千问正在更新 · 先保留上一条说明'):tr('千问说明（稍早）· 新活动会自动更新'));}
 else {showStory(data);proof(Object.entries(data.evidence).map(([key,item])=>({title:({goal:tr('你的要求'),content:tr('具体活动'),explanation:tr('助手说明'),reason:tr('原因出处'),fragment:tr('所见短片段')})[key],quote:item.text})));
  $('modelNote').textContent=attemptMessage||(modelPending?tr('千问正在解释 · 下方暂为本机记录'):model?.automatic_on_open?tr('千问会自动解释 · 下方暂为本机记录'):model?.configured?tr('自动解释尚未开启，当前显示本机说明。'):tr('尚未配置千问，当前显示本机说明。'));
  if(modelAnswer)proofModel($('previousText'),modelAnswer,true);
 }
 if(!synthetic&&['stopped','failed','stale','unavailable'].includes(data.recorder?.state)){
 $('status').textContent=tr('显示上次内容');$('status').className='status quiet';note(tr('新记录暂时没跟上，这里保留的是之前的工作。请重新打开桌面上的“雪绪活动工作台”。'));}
 if(!synthetic&&data.recorder?.state==='paused_capacity'){$('status').textContent=tr('保存暂时停下了');$('status').className='status quiet';note(tr('旧记录仍可查看。请先检查电脑上的可用空间，再重新打开工作台。'));}
 if(data.source_unavailable){$('status').textContent=tr('这段原文暂时读不到');$('status').className='status quiet';}}
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
 const refs=make('details');refs.dataset.detailKey=JSON.stringify([title,item.text]);refs.append(make('summary',(item.basis==='plan'?tr('后续计划'):basis[item.basis]||tr('尚不清楚'))+tr(' · 查看依据')));
 for(const ref of item.evidence||[])refs.append(make('blockquote',ref.text||ref.quote||tr('记录位置已保留，可在交接详情核对。')));
 if(!(item.evidence||[]).length)refs.append(make('p',tr('没有足够的可读依据。')));section.append(refs);box.append(section);
}
async function loadTaskSummary(){
 if(summaryBusy||!selected)return;summaryBusy=true;
 const own=++summaryEpoch,selection={...selected};
 try{const data=await api('task-summary?'+new URLSearchParams(selection));if(own!==summaryEpoch||JSON.stringify(selection)!==JSON.stringify(selected))return;
 const box=$('taskSummary');updateExpanded(box,data,()=>{summaryPoint(box,tr('原本要做什么'),data.goal);
 if(!data.before.length)box.append(make('p',tr('前面的进展暂时没有可读依据。')));
 for(const [i,item] of data.before.entries())summaryPoint(box,i===0?tr('前面做到哪'):tr('此前的公开汇报'),item);
 summaryPoint(box,tr('眼前在做什么'),data.now);
 for(const item of data.outcomes)summaryPoint(box,tr('最近操作的已知结果'),item);
 summaryPoint(box,tr('接下来'),data.next);box.append(make('h3',tr('助手交接小结')));
 if(!data.handoffs.length)box.append(make('p',data.handoff_empty));
 for(const item of data.handoffs){const card=make('section');card.className='handoff-card';card.append(make('h4',item.title),make('p',tr('交代的事：')+item.request),make('p',item.status));
 if(!item.receivers.length)card.append(make('p',tr('具体接收者尚不能确认。')));
 for(const receiver of item.receivers)card.append(make('p',receiver.who+'：'+receiver.reply),make('p',receiver.input_note));
 card.append(make('p',item.adoption));const refs=make('details');refs.dataset.detailKey=JSON.stringify(item.evidence);refs.append(make('summary',tr('查看交接依据')));for(const ref of item.evidence)refs.append(make('p',ref.label));card.append(refs);box.append(card);}
 for(const text of data.limits){const p=make('p',text);p.className='scope';box.append(p);}
 });
 }catch(error){if(own===summaryEpoch){delete $('taskSummary').dataset.contentKey;$('taskSummary').replaceChildren(make('p',tr('小结暂时读不到，当前工作和原记录仍可查看。')));}}
 finally{summaryBusy=false;}
}
$('taskSummaryBox').addEventListener('toggle',()=>{if($('taskSummaryBox').open)loadTaskSummary();else summaryEpoch++;});
let handoffEpoch=0;
async function loadHandoffs(){
 if(handoffBusy||!selected)return;handoffBusy=true;
 const own=++handoffEpoch, selection={...selected};
 try{const data=await api('handoffs?'+new URLSearchParams(selection));if(own!==handoffEpoch||JSON.stringify(selection)!==JSON.stringify(selected))return;
 const box=$('handoffs');updateExpanded(box,data,()=>{
 if(!data.items.length)box.append(make('p',tr('这段记录里还没有可确认的助手交接。')));
 const states={pending_init:tr('等待准备'),running:tr('当时正在工作'),completed:tr('当时这一轮已结束'),interrupted:tr('当时被打断'),errored:tr('当时遇到错误'),shutdown:tr('当时已关闭'),not_found:tr('当时未找到'),unknown:tr('状态不明确')};
 for(const item of data.items){const card=make('section');card.className='handoff-card';card.append(make('h3',item.title),make('p',item.sent),make('p',item.status));
 for(const target of item.targets){const p=make('p');if(target.key){const a=make('a',target.label+' ↗');a.href='/?'+new URLSearchParams({client:selection.client,key:target.key,lang:uiLanguage});p.append(a);}else p.append(make('span',target.label));p.append(make('span',' · '+(states[target.state]||states.unknown)));card.append(p,make('p',target.input_note||item.input_note));}
 if(!item.targets.length)card.append(make('p',item.input_note));
 for(const reply of item.returns)card.append(make('blockquote',reply.who+tr('回复：')+reply.text));
 if(!item.returns.length)card.append(make('p',tr('这次交接没有可显示的回复正文。')));
 card.append(make('p',item.use_note));const details=make('details'),summary=make('summary',tr('查看这次交接的依据'));details.dataset.detailKey=JSON.stringify(item.evidence);details.append(summary);for(const ref of item.evidence)details.append(make('p',ref.label));card.append(details);box.append(card);}
 box.append(make('p',data.note+(data.limited?tr(' 这里只显示最近一部分交接。'):'')));
 });
 }catch(error){if(own===handoffEpoch){delete $('handoffs').dataset.contentKey;$('handoffs').replaceChildren(make('p',tr('暂时没读到交接信息，已有工作说明仍可查看。')));}}
 finally{handoffBusy=false;}
}
$('handoffBox').addEventListener('toggle',()=>{if($('handoffBox').open)loadHandoffs();});
async function stopAuto(){const old=grant;grant=null;if(old){try{await api('glance-stop',{grant:old});}catch{}}}
async function choose(value,keepAnswer=false){resetReading();epoch++;selected=JSON.parse(value);window.history?.replaceState(null,'','/?'+new URLSearchParams({...selected,lang:uiLanguage}));if(!keepAnswer)modelAnswer=null;current=null;attemptMessage='';modelPending=false;autoRun=null;nextRetry=0;if(!keepAnswer)$('work').hidden=true;$('detailsBox').open=false;$('taskSummaryBox').open=false;$('taskSummary').replaceChildren();delete $('taskSummary').dataset.contentKey;delete $('handoffs').dataset.contentKey;summaryEpoch++;handoffEpoch++;renderChatNavigation();for(const part of ['content','explanation','reason']){$(part+'Proof').hidden=true;$(part+'Basis').setAttribute('aria-expanded','false');}await stopAuto();await refresh(true);}
async function refresh(force=false){if(busy){refreshAgain=refreshAgain||force;return;}if(document.hidden&&!force)return;busy=true;const own=epoch;try{
 if(force||Date.now()-cardsAt>30000){const data=await api('current');if(own!==epoch)return;cardsAt=Date.now();chatCatalog=data.cards;chatLimited=Boolean(data.limited);const prior=selected?JSON.stringify(selected):'';$('chat').replaceChildren();
 for(const [helper,label] of [[false,tr('你的聊天')],[true,tr('协助助手的工作')]]){const group=make('optgroup');group.label=label;for(const c of data.cards.filter(c=>Boolean(c.is_helper)===helper)){const option=make('option',names[c.client]+' · '+c.title+' · '+age(c.last_activity_ms));option.value=JSON.stringify({client:c.client,key:c.key});group.append(option);}if(group.children.length)$('chat').append(group);}
 renderChatNavigation();note('');$('connection').textContent=synthetic?tr('模拟活动 · 用于检查'):data.cards.length?tr('已连接本机记录'):tr('已连接 · 等待聊天');if(!data.cards.length){epoch++;current=null;selected=null;modelAnswer=null;autoRun=null;modelPending=false;void stopAuto();$('work').hidden=true;$('empty').hidden=false;$('chat').append(make('option',tr('尚未发现可显示的聊天')));try{const info=await api('clients');if(own===epoch)emptyHelp(info.clients);}catch{}return;}
 if(prior&&[...$('chat').options].some(o=>o.value===prior))$('chat').value=prior;
 else if(selected){const next=continuation(selected,data.cards);if(next){await choose(JSON.stringify(next),true);return;}const option=make('option',names[selected.client]+' · '+(current?.title||tr('当前聊天')));option.value=prior;$('chat').prepend(option);$('chat').value=prior;}
 else selected=JSON.parse($('chat').value);}
 if(!selected)return;const data=await api('glance?'+new URLSearchParams(selected));if(own!==epoch)return;note('');render(data);$('connection').textContent=synthetic?tr('模拟活动 · 用于检查'):tr('已连接本机记录');$('refreshNote').textContent=synthetic?tr('模拟活动 · 用于检查'):tr('自动跟进新消息');void automatic();
 }catch(error){if(own===epoch){note(error.message);$('connection').textContent=tr('暂未连上');if(current){$('status').textContent=tr('显示断开前内容');$('status').className='status quiet';}}}finally{busy=false;if(refreshAgain){refreshAgain=false;refresh(true);}}}
function revokeOnClose(token){if(token)fetch('/api/glance-stop',{method:'POST',headers:{'Content-Type':'application/json','X-Yukio-Workbench':'1','X-Yukio-Language':uiLanguage},body:JSON.stringify({grant:token}),keepalive:true}).catch(()=>{});}
function closePage(){resetReading();pageClosed=true;epoch++;const old=grant;grant=null;autoRun=null;modelPending=false;revokeOnClose(old);}
async function automatic(){
 if(pageClosed||!model?.automatic_on_open||!selected||!current||current.key!==selected.key||autoRun)return;
 if(!grant&&Date.now()<nextRetry)return;
 const run={},own=epoch,selection={...selected};autoRun=run;
 const active=()=>!pageClosed&&own===epoch&&autoRun===run;
 try{
  let first=false;
  if(!grant){
   modelPending=true;render(current);
   const preview=await api('glance-preview',selection);if(!active())return;
   const approved=await api('glance-authorize',{token:preview.token,consent:true,page_owned:true});
   if(!active()){revokeOnClose(approved.grant);return;}grant=approved.grant;first=true;
  }else{
   const token=grant;await api('glance-heartbeat',{grant:token});if(!active()||grant!==token)return;
  }
  if(readingBusy||Date.now()<nextRetry)return;
  const token=grant,data=await api('glance-refresh',{grant:token,...(first?{force:true}:{})});
  if(!active()||grant!==token)return;
  if(data.mode==='updated'){
   const latest=await api('glance?'+new URLSearchParams(selection));if(!active()||grant!==token)return;
   modelPending=false;render(latest);showAnswer(data.result,data.references,data.snapshot,data.revision);
  }
 }catch(error){
  if(active()){
   if(['preview_expired','consent_required'].includes(error.reason)){grant=null;nextRetry=Date.now()+15000;attemptMessage=tr('正在接续这段聊天的自动说明…');}
   else{nextRetry=Date.now()+(error.reason==='rate_limited'?180000:30000);attemptMessage=tr('说明暂时未更新，会自动重试。已有内容仍保留。');}
  }
 }finally{if(autoRun===run){autoRun=null;modelPending=false;if(!pageClosed&&current)render(current);}}
}
$('chat').onchange=()=>choose($('chat').value);$('reload').onclick=()=>refresh(true);
for(const [filter,id] of [['recent','filterRecent'],['working','filterWorking'],['inactive','filterInactive']])$(id).onclick=()=>{chatFilter=filter;renderChatNavigation();};
$('chatSearch').oninput=()=>{chatSearch=$('chatSearch').value;renderChatNavigation();};
$('chatBrowse').onclick=()=>toggleChatBrowser(true);$('chatNavClose').onclick=()=>toggleChatBrowser(false);$('chatBackdrop').onclick=()=>toggleChatBrowser(false);
window.addEventListener('keydown',event=>{if(event.key==='Escape')toggleChatBrowser(false);});

let readingEpoch=0,readingBusy=false,deepLoaded=false,pastPage=null;
function resetReading(){readingEpoch++;readingBusy=false;deepLoaded=false;pastPage=null;for(const id of ['deepPanel','pastPanel'])$(id).hidden=true;for(const id of ['deepRead','pastRead'])$(id).setAttribute('aria-expanded','false');$('deepText').replaceChildren();$('pastText').replaceChildren();}
function readingReady(){if(!grant)throw Error(tr('首页说明还在准备，请稍后再点。'));if(readingBusy||autoRun)throw Error(tr('有一段说明正在生成，请稍后再点。'));}
function readingActive(own,panel){return own===readingEpoch&&!pageClosed&&!$(panel).hidden;}
async function readingModel(token,own,panel,status){
 for(let attempt=0;attempt<2;attempt++){
  if(!readingActive(own,panel))return null;
  try{return await api('reading-explain',{grant,token});}
  catch(error){if(attempt===0&&['rate_limited','busy'].includes(error.reason)){
   status.textContent=tr('千问刚处理过一段说明，稍等片刻就继续…');
   await new Promise(resolve=>setTimeout(resolve,11000));
  }else throw error;}
 }
}
function readingParts(box,parts,data){
 box.replaceChildren();for(const part of parts){const item=data.result.explanations.find(i=>i.part===part.part);if(!item)continue;
 const section=make('section');section.append(make('h3',part.title),make('p',item.text));
 const refs=make('details');refs.append(make('summary',tr('千问说明 · 查看依据')));
 for(const id of item.evidence_ids){const ref=data.references.find(r=>r.evidence_id===id);if(ref)refs.append(make('blockquote',ref.title+'：'+ref.quote));}
 section.append(refs);box.append(section);}
}
async function loadDeep(){
 const own=readingEpoch;let started=false;$('deepRetry').hidden=true;
 try{readingReady();readingBusy=true;started=true;$('deepNote').textContent=tr('千问正在把这一步展开讲清楚…');
 const frozen=await api('reading-current',{grant});if(!readingActive(own,'deepPanel'))return;
 const answer=await readingModel(frozen.token,own,'deepPanel',$('deepNote'));if(!answer||!readingActive(own,'deepPanel'))return;
 if(answer.result.mode!=='model')throw Error(answer.result.message||tr('这次详细说明没能生成，请稍后重试。'));
 readingParts($('deepText'),frozen.parts,answer);deepLoaded=true;$('deepNote').textContent=tr('千问深入说明 · ')+frozen.note;$('deepRetry').textContent=tr('按最新工作再解释');
 }catch(error){if(readingActive(own,'deepPanel')){$('deepNote').textContent=error.message;$('deepRetry').hidden=false;}}
 finally{if(started&&own===readingEpoch){readingBusy=false;$('deepRetry').hidden=false;}}
}
async function loadPast(snapshot=0,before=0){
 const own=readingEpoch;let started=false;$('pastRetry').hidden=true;$('pastOlder').hidden=true;
 try{readingReady();readingBusy=true;started=true;$('pastNote').textContent=tr('正在分段回顾这段聊天…');
 const page=await api('reading-history',{grant,snapshot,before});if(!readingActive(own,'pastPanel'))return;
 pastPage=page;page.before=before;$('pastText').replaceChildren();$('pastNewer').hidden=!before;
 for(const card of page.cards){
  const section=make('section');section.className='past-card';const heading=make('h3',card.title.length>26?card.title.slice(0,26)+'…':card.title);card.heading=heading;section.append(heading);
  const time=make('p',(card.position?card.position+' · ':'')+age(card.stamp)+tr('的要求'));time.className='reading-caption';section.append(time);
  const short=make('p',tr('千问正在总结这一段…'));section.append(short);card.short=short;card.container=section;
  const button=make('button',tr('深入看这一段')),detail=make('div');detail.className='past-detail';detail.hidden=true;
  button.setAttribute('aria-expanded','false');button.onclick=()=>loadPastDetail(card,button,detail);
  section.append(button,detail);$('pastText').append(section);
  if(card.missing_reply){const limit=make('p',card.note);limit.className='reading-caption';section.append(limit);}
 }
 if(!page.token){$('pastNote').textContent=tr('这部分还没有可读取的公开内容。')+page.note;return;}
 $('pastNote').textContent=tr('千问正在为这三段写简短总结…');
 const answer=await readingModel(page.token,own,'pastPanel',$('pastNote'));if(!answer||!readingActive(own,'pastPanel'))return;
 if(answer.result.mode!=='model')throw Error(answer.result.message||tr('千问暂时没能总结，点击下方重新读取。'));
 for(const card of page.cards){const item=answer.result.explanations.find(i=>i.part===card.id);card.short.textContent=item?.text||tr('这段暂时没有说明。');
  // A dedicated subject title preserves names after commas and complete pairs.
  // Legacy cached replies fall back to a sentence, never its first short clause.
  if(item)card.heading.textContent=item.title||item.text.split(/[。；]/)[0];
  const evidence=make('details');evidence.append(make('summary',tr('千问总结 · 查看依据')));for(const id of item?.evidence_ids||[]){const ref=answer.references.find(r=>r.evidence_id===id);if(ref)evidence.append(make('blockquote',ref.title+'：'+ref.quote));}card.container.append(evidence);
 }
 $('pastNote').textContent=page.note;
 }catch(error){if(readingActive(own,'pastPanel')){for(const card of pastPage?.cards||[])if(card.short.textContent===tr('千问正在总结这一段…'))card.short.textContent=tr('暂时没有千问总结；下面仍可单独展开这一段。');$('pastNote').textContent=error.message;$('pastRetry').hidden=false;}}
 finally{if(started&&own===readingEpoch){readingBusy=false;$('pastOlder').hidden=!pastPage?.has_more;$('pastRetry').hidden=false;$('pastRetry').textContent=tr('重新读取这一页');}}
}
async function loadPastDetail(card,button,box){
 if(!box.hidden){box.hidden=true;button.setAttribute('aria-expanded','false');return;}
 box.hidden=false;button.setAttribute('aria-expanded','true');if(card.loaded)return;
 const own=readingEpoch;let started=false;const status=make('p',tr('千问正在展开这一段…'));box.replaceChildren(status);
 try{readingReady();readingBusy=true;started=true;
 const answer=await readingModel(card.detail_token,own,'pastPanel',status);if(!answer||!readingActive(own,'pastPanel')||box.hidden)return;
 if(answer.result.mode!=='model')throw Error(answer.result.message||tr('这次没有生成详细说明。'));
 readingParts(box,card.parts,answer);card.loaded=true;
 }catch(error){if(readingActive(own,'pastPanel')){status.textContent=error.message;box.append(make('p',tr('收起后再展开可以重试；放久了请重新读取这一页。')));}}
 finally{if(started&&own===readingEpoch)readingBusy=false;}
}
$('deepRead').onclick=()=>{const panel=$('deepPanel');panel.hidden=!panel.hidden;$('deepRead').setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden&&!deepLoaded)void loadDeep();};
$('pastRead').onclick=()=>{const panel=$('pastPanel');panel.hidden=!panel.hidden;$('pastRead').setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden&&!pastPage)void loadPast();};
$('deepRetry').onclick=()=>loadDeep();$('pastRetry').onclick=()=>loadPast(pastPage?.snapshot||0,pastPage?.before||0);$('pastNewer').onclick=()=>loadPast();$('pastOlder').onclick=()=>{if(pastPage)void loadPast(pastPage.snapshot,pastPage.next_before);};
for(const part of ['content','explanation','reason'])$(part+'Basis').onclick=()=>{const box=$(part+'Proof');box.hidden=!box.hidden;$(part+'Basis').setAttribute('aria-expanded',String(!box.hidden));};
window.addEventListener('pagehide',closePage);
window.addEventListener('pageshow',()=>{pageClosed=false;nextRetry=0;void automatic();});
(async()=>{try{const initial=new URLSearchParams(location.search);if(names[initial.get('client')]&&/^[A-Za-z0-9_-]{1,4096}$/.test(initial.get('key')||''))selected={client:initial.get('client'),key:initial.get('key')};const data=await api('clients');model=data.explanation;synthetic=data.mode==='synthetic';if(synthetic)$('connection').textContent=tr('模拟活动 · 用于检查');$('modelDetails').textContent=model?.configured?tr('使用你设置的千问，每小时最多 ')+model.max_calls_per_hour+tr(' 次。'):tr('未配置模型，仍可查看本机说明。');await refresh(true);if(data.mode==='synthetic'){$('refreshNote').textContent=tr('模拟活动 · 用于检查');document.title=tr('雪绪 · 模拟当前工作');}}catch(error){note(error.message);}})();
setInterval(()=>refresh(),6000);setInterval(automatic,15000);
