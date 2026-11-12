'use strict';
var tr=globalThis.YukioI18n?.t||(value=>value);
var uiLanguage=globalThis.YukioI18n?.language||'zh';
const $=id=>document.getElementById(id), make=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const names={codex:'Codex',claude:'Claude',deepcode:'Deep Code'}, basis={observed:tr('记录所见'),assistant:tr('助手自述'),user_request:tr('你的要求'),inference:tr('推测'),unknown:tr('尚不清楚')};
let selected=null, current=null, epoch=0, busy=false, cardsAt=0, model=null, grant=null, modelAnswer=null, refreshAgain=false, synthetic=false, modelPending=false, attemptMessage='', pageClosed=false, autoRun=null, nextRetry=0;
let chatCatalog=[],chatSearch='',chatLimited=false,providerSaving=false;
const chatExpansion=new Map();let chatRenderedSearch='';
const activityLabels={working:tr('正在工作'),waiting:tr('等你处理'),inactive:tr('本轮已结束'),unknown:tr('状态待确认')};
const chatValue=c=>JSON.stringify({client:c.client,key:c.key});
function filteredChats(cards,query){
 const search=query.trim().toLocaleLowerCase();
 return cards.filter(c=>!c.source_unavailable&&c.has_content!==false&&(!search||[c.title,names[c.client]].filter(Boolean).join(' ').toLocaleLowerCase().includes(search)));
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
 const meta=make('span',names[card.client]+(card.is_helper?tr(' · 协助助手'):'')+' · '+age(card.last_activity_ms));meta.className='chat-row-meta';text.append(title,meta);
 const state=card.activity_state||'unknown',dot=make('span');dot.className='chat-state '+state;dot.setAttribute('aria-hidden','true');dot.title=activityLabels[state];
 const badge=make('span');badge.className='chat-status '+state;badge.title=activityLabels[state]||activityLabels.unknown;const label=make('span',badge.title);label.className='chat-status-label';badge.append(dot,label);
 button.append(text,badge);button.onclick=()=>{toggleChatBrowser(false);void choose(chatValue(card));};return button;
}
function renderChatNavigation(){
 const shown=filteredChats(chatCatalog,chatSearch),signature=JSON.stringify([shown.map(c=>[c.client,c.key,c.title,c.is_helper,c.activity_state,age(c.last_activity_ms)]),selected,chatSearch]);
 const list=$('chatLists');if(list.dataset.signature===signature)return;list.dataset.signature=signature;
 const active=list.contains(document.activeElement)?document.activeElement:null,focused=active?.dataset.chatValue,focusedClient=active?.dataset.clientToggle,scroll=list.scrollTop;let restore;
 // Remember manual folds only outside search. Searching briefly opens matches,
 // then restores the user's folds; a new page always starts collapsed.
 if(!chatRenderedSearch)for(const section of list.querySelectorAll('details'))chatExpansion.set(section.dataset.client,section.open);
 chatRenderedSearch=chatSearch.trim();
 list.replaceChildren();
 for(const client of ['claude','codex','deepcode']){
  const chats=shown.filter(c=>c.client===client);if(!chats.length)continue;
  const section=make('details');section.className='chat-client';section.dataset.client=client;section.open=Boolean(chatRenderedSearch)||chatExpansion.get(client)===true;
  const summary=make('summary');summary.dataset.clientToggle=client;summary.append(make('span',names[client]),make('small',String(chats.length)));
  const rows=make('div');rows.className='client-chats';section.append(summary,rows);list.append(section);
  if(client===focusedClient)restore=summary;
  for(const card of chats){const row=chatRow(card);rows.append(row);if(row.dataset.chatValue===focused)restore=section.open?row:summary;}
 }
 if(!shown.length){const message=make('p',chatSearch?tr('没有找到相符的聊天。'):tr('还没有读到聊天记录。'));message.className='chat-list-empty';list.append(message);}
 $('chatListNote').textContent=chatLimited?tr('先显示最近读到的聊天；更早的内容可在记录详情查看。'):tr('按本机读到的记录整理。缺少依据时保留“状态待确认”。');
 restore?.focus();
 list.scrollTop=scroll;
}
function chatIdentity(value){try{const key=value.key.replace(/-/g,'+').replace(/_/g,'/'),p=JSON.parse(atob(key+'='.repeat((4-key.length%4)%4)));return Array.isArray(p)&&p.length===5&&typeof p[2]==='string'&&p[2]&&!p[2].startsWith('source-')?JSON.stringify([value.client,p[2],p[3],p[4]]):null;}catch{return null;}}
function continuation(selection,cards){
 // Same transcript identity, or Claude Desktop's explicit current/prior IDs.
 // Never infer a relationship from matching titles, paths or recent activity.
 const prior=chatIdentity(selection);if(!prior)return null;const scope=JSON.parse(prior);
 const matches=cards.filter(c=>{
  if(chatIdentity(c)===prior)return true;
  if(scope[0]!=='claude'||scope[2]!==''||scope[3]!==0||c.client!=='claude'||!c.conversation_id||!Array.isArray(c.continuation_sessions))return false;
  const target=chatIdentity(c);if(!target)return false;const parts=JSON.parse(target);
  return parts[2]===''&&parts[3]===0&&c.continuation_sessions.includes(scope[1]);
 });
 return matches.length===1?{client:matches[0].client,key:matches[0].key}:null;
}
async function continueSelection(next){
 // A rewind changes the evidence branch: revoke its grant and clear its old
 // explanation. Moving the same transcript to another file can retain it.
 await choose(JSON.stringify(next),chatIdentity(selected)!==null&&chatIdentity(selected)===chatIdentity(next));
}
async function api(route,data){
 let response;
 try{response=await fetch('/api/'+route,{method:data?'POST':'GET',headers:{'X-Yukio-Workbench':'1','X-Yukio-Language':uiLanguage,...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{}),cache:'no-store',signal:AbortSignal.timeout(120000)});}
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
function localStoryText(data,part){return uiLanguage==='en'&&/[\u4e00-\u9fff]/.test(data[part])?({content:'An English explanation of the latest activity is not available yet. Supporting notes show what was actually read.',explanation:'The source notes are in another language. Their connection with earlier work has not yet been explained in English.',reason:'The purpose has not yet been explained in English using this chat’s request and earlier progress.'})[part]:data[part];}
function showStory(data){for(const part of ['content','explanation','reason']){
 const untranslated=uiLanguage==='en'&&/[\u4e00-\u9fff]/.test(data[part]);
 $(part).textContent=localStoryText(data,part);const ref=data.evidence[part==='explanation'?'fragment':part];
 partProof(part,untranslated?'unknown':data[part+'_basis'],data.part_evidence?.[part]||(ref?[{quote:ref.text}]:[]));
 if(part==='content'&&[tr('这一轮已结束'),tr('这一轮已取消')].includes(data.status)&&!untranslated)$(part).textContent=tr('这一轮的最后记录：')+$(part).textContent;
}}
function showAnswer(result,refs,snapshot,revision){
 if(result.mode!=='model'){attemptMessage=result.message||tr('模型暂时没能解释，先保留已有说明。');render(current);return;}
 attemptMessage='';modelAnswer={result,refs,snapshot,revision};render(current);
}
function render(data){current=data;$('chatName').textContent=data.title;$('chatLocation').textContent=names[data.client]+tr(' · 当前查看');
 // Navigation reads the latest lifecycle marker independently. The bounded
 // explanation excerpt may omit that marker in a long turn; it must not
 // replace the catalogue's state with a less complete observation.
 renderChatNavigation();if($('handoffBox').open)loadHandoffs();$('work').hidden=false;$('empty').hidden=true;$('title').textContent=data.title;$('status').textContent=data.status;$('status').className='status '+data.tone;$('goal').textContent=data.goal;const brief=data.project_context;
 const originalBrief=uiLanguage==='en'&&brief&&/[\u3400-\u9fff]/.test(brief.goal+brief.now);
 $('goalShort').textContent=originalBrief?(data.goal_short||data.goal):(brief?.goal||data.goal_short||data.goal);
 $('goalLabel').textContent=originalBrief?tr('这次的要求（原文）'):brief?tr('整个任务'):tr('这次的要求');
 $('projectFocus').hidden=!brief||originalBrief;$('projectFocus').textContent=originalBrief?'':brief?.now||'';
 $('projectBox').hidden=!brief;
 $('projectText').textContent=brief?[tr('前面：')+brief.before,tr('现在：')+brief.now,tr('接下来：')+brief.next,tr('来源：')+brief.source_note].join('\n\n'):'';
 $('attention').hidden=data.tone!=='attention';$('attention').textContent=data.needs_you;
 $('latestStep').hidden=!data.last_step;if(data.last_step){$('stepAction').textContent=data.last_step.action;$('stepResult').textContent=data.last_step.result;}
 $('historyLink').href='/history?'+new URLSearchParams({client:data.client,key:data.key,lang:uiLanguage});
 $('historyRecords').href=$('historyLink').href;
 $('historyScope').textContent=tr('这次聊天的历史：')+data.title+tr(' · 切换左侧聊天可查看其他聊天的记录。');
 $('scope').textContent=(data.source_unavailable?tr('这段原文暂时读不到，等待来源恢复。'):data.partial?tr('这次只看到一部分，缺失内容没有补猜。'):tr('依据最近可读取的一段聊天。'))+' '+(uiLanguage==='en'?'Last activity: '+age(data.last_activity_ms)+'.':age(data.last_activity_ms)+tr('有活动。'));
 $('recent').replaceChildren();for(const item of data.recent)$('recent').append(make('p',(item.kind==='assistant'?tr('助手说：'):tr('观察到：'))+item.text));
 const applicable=modelAnswer&&modelAnswer.revision===data.revision;

 // A single requested explanation is a snapshot, not a live claim. Keep it
 // readable when more work arrives, explicitly label its age, and reset it on
 // chat/source changes. A polling/tool event must not erase it immediately.
 if(modelAnswer){for(const item of modelAnswer.result.explanations){$(item.part).textContent=item.text;partProof(item.part,item.basis,item.evidence_ids.map(id=>modelAnswer.refs.find(r=>r.evidence_id===id)).filter(Boolean));}proofModel($('evidence'),modelAnswer);$('modelNote').textContent=attemptMessage||(applicable?(modelAnswer.result.model?modelAnswer.result.model+' · ':'')+tr('模型说明 · 自动跟进这段聊天'):modelPending?tr('模型正在更新 · 先保留上一条说明'):(modelAnswer.result.model?modelAnswer.result.model+' · ':'')+tr('模型说明（稍早）· 新活动会自动更新'));}
 else {showStory(data);proof(Object.entries(data.evidence).map(([key,item])=>({title:({goal:tr('你的要求'),content:tr('具体活动'),explanation:tr('助手说明'),reason:tr('原因出处'),fragment:tr('所见短片段')})[key],quote:item.text})));
  $('modelNote').textContent=attemptMessage||(modelPending?tr('模型正在解释 · 下方暂为本机记录'):model?.automatic_on_open?tr('模型会自动解释 · 下方暂为本机记录'):model?.configured?tr('自动解释尚未开启，当前显示本机说明。'):tr('尚未配置模型，当前显示本机说明。'));

 }
 if(!synthetic&&['stopped','failed','stale','unavailable'].includes(data.recorder?.state)){
 $('status').textContent=tr('显示上次内容');$('status').className='status quiet';note(tr('新记录暂时没跟上，这里保留的是之前的工作。请重新打开桌面上的“雪绪活动工作台”。'));}
 if(!synthetic&&data.recorder?.state==='paused_capacity'){$('status').textContent=tr('保存暂时停下了');$('status').className='status quiet';note(tr('旧记录仍可查看。请先检查电脑上的可用空间，再重新打开工作台。'));}
 if(data.source_unavailable){$('status').textContent=tr('这段原文暂时读不到');$('status').className='status quiet';}}
let handoffBusy=false;
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
function renderProviderSettings(){
 const select=$('explanationProvider');select.replaceChildren();
 for(const provider of model?.providers||[]){const option=make('option',provider.label+(provider.available?'':tr('（未找到）')));option.value=provider.id;option.disabled=!provider.available;select.append(option);}
 select.value=model?.provider||'auto';
 $('providerEnable').textContent=model?.automatic_on_open?tr('应用并继续解释'):tr('开启解释');
 $('providerDisable').hidden=!model?.automatic_on_open;
 $('providerNote').textContent=(model?.automatic_on_open?tr('已开启：'):tr('开启后：'))+tr('只解释所选聊天的短摘录，使用对应 Agent 的账号额度。自动模式优先使用该聊天的 Agent，未安装、未登录或版本不支持时选择另一个可用的 Agent；调用失败时保留本机说明。');
}
async function setExplanationProvider(enabled,provider=enabled?$('explanationProvider').value:model.provider){
 if(providerSaving||!model)return;
 if((enabled||provider!==model.provider)&&(autoRun||readingBusy||workInFlight)){$('explanationProvider').value=model.provider;$('providerNote').textContent=tr('选择尚未保存：正在生成一段说明，请等它结束后再切换。');return;}
 const enable=$('providerEnable'),disable=$('providerDisable'),select=$('explanationProvider');providerSaving=true;enable.disabled=true;disable.disabled=true;select.disabled=true;
 $('providerNote').textContent=tr('正在保存解释来源…');if(enabled)enable.textContent=tr('正在检查助手…');
 let saved=false;
 try{
  const updated=await api('explanation-settings',{provider,automatic_on_open:enabled});
  epoch++;resetReading();model=updated;grant=null;autoRun=null;modelAnswer=null;modelPending=false;attemptMessage='';nextRetry=0;
  renderProviderSettings();$('providerNote').textContent=tr('解释来源已保存。')+' '+$('providerNote').textContent;if(current)render(current);saved=true;
 }catch(error){select.value=model.provider;$('providerNote').textContent=tr('更改未保存，仍保留原解释来源。')+' '+error.message;}
 finally{providerSaving=false;enable.disabled=false;disable.disabled=false;select.disabled=false;enable.textContent=model?.automatic_on_open?tr('应用并继续解释'):tr('开启解释');}
 if(saved)void automatic();
}
$('explanationProvider').onchange=()=>setExplanationProvider(Boolean(model?.automatic_on_open),$('explanationProvider').value);
$('providerEnable').onclick=()=>setExplanationProvider(true);
$('providerDisable').onclick=()=>setExplanationProvider(false);
async function stopAuto(){const old=grant;grant=null;if(old){try{await api('glance-stop',{grant:old});}catch{}}}
async function choose(value,keepAnswer=false){resetReading();epoch++;selected=JSON.parse(value);window.history?.replaceState(null,'','/?'+new URLSearchParams({...selected,lang:uiLanguage}));if(!keepAnswer)modelAnswer=null;current=null;attemptMessage='';modelPending=false;autoRun=null;nextRetry=0;if(!keepAnswer)$('work').hidden=true;$('detailsBox').open=false;$('taskSummaryBox').open=false;$('taskSummary').replaceChildren();delete $('taskSummary').dataset.contentKey;delete $('handoffs').dataset.contentKey;handoffEpoch++;renderChatNavigation();for(const part of ['content','explanation','reason']){$(part+'Proof').hidden=true;$(part+'Basis').setAttribute('aria-expanded','false');}await stopAuto();await refresh(true);}
async function refresh(force=false){if(busy){refreshAgain=refreshAgain||force;return;}if(document.hidden&&!force)return;busy=true;const own=epoch;try{
 if(force||Date.now()-cardsAt>30000){const data=await api('current');if(own!==epoch)return;cardsAt=Date.now();chatCatalog=data.cards;chatLimited=Boolean(data.limited);const prior=selected?JSON.stringify(selected):'';$('chat').replaceChildren();
 for(const [helper,label] of [[false,tr('你的聊天')],[true,tr('协助助手的工作')]]){const group=make('optgroup');group.label=label;for(const c of data.cards.filter(c=>Boolean(c.is_helper)===helper)){const option=make('option',names[c.client]+' · '+c.title+' · '+age(c.last_activity_ms));option.value=JSON.stringify({client:c.client,key:c.key});group.append(option);}if(group.children.length)$('chat').append(group);}
 renderChatNavigation();note('');$('connection').textContent=synthetic?tr('模拟活动 · 用于检查'):data.cards.length?tr('已连接本机记录'):tr('已连接 · 等待聊天');if(!data.cards.length){const emptyEpoch=++epoch;current=null;selected=null;modelAnswer=null;autoRun=null;modelPending=false;void stopAuto();$('work').hidden=true;$('empty').hidden=false;$('chat').append(make('option',tr('尚未发现可显示的聊天')));try{const info=await api('clients');if(emptyEpoch===epoch)emptyHelp(info.clients);}catch{}return;}
 if(prior&&[...$('chat').options].some(o=>o.value===prior))$('chat').value=prior;
 else if(selected){const next=continuation(selected,data.cards);if(next){await continueSelection(next);return;}const option=make('option',names[selected.client]+' · '+(current?.title||tr('当前聊天')));option.value=prior;$('chat').prepend(option);$('chat').value=prior;}
 else selected=JSON.parse($('chat').value);}
 if(!selected)return;const data=await api('glance?'+new URLSearchParams(selected));if(own!==epoch)return;note('');render(data);void loadUnderstanding(force);$('connection').textContent=synthetic?tr('模拟活动 · 用于检查'):tr('已连接本机记录');$('refreshNote').textContent=synthetic?tr('模拟活动 · 用于检查'):tr('自动跟进新消息');void automatic();
 }catch(error){if(own===epoch){note(error.message);$('connection').textContent=tr('暂未连上');if(current){$('status').textContent=tr('显示断开前内容');$('status').className='status quiet';}}}finally{busy=false;if(refreshAgain){refreshAgain=false;refresh(true);}}}
function revokeOnClose(token){if(token)fetch('/api/glance-stop',{method:'POST',headers:{'Content-Type':'application/json','X-Yukio-Workbench':'1','X-Yukio-Language':uiLanguage},body:JSON.stringify({grant:token}),keepalive:true}).catch(()=>{});}
function closePage(){resetReading();pageClosed=true;epoch++;const old=grant;grant=null;autoRun=null;modelPending=false;revokeOnClose(old);}
async function automatic(){
 if(pageClosed||providerSaving||!model?.automatic_on_open||!selected||!current||current.key!==selected.key||autoRun)return;
 if(!grant&&Date.now()<nextRetry)return;
 const run={},own=epoch,selection={...selected};autoRun=run;
 const active=()=>!pageClosed&&own===epoch&&autoRun===run;
 try{
  let first=false;
  if(!grant){
   modelPending=true;render(current);
   const preview=await api('glance-preview',selection);if(!active())return;
   if(model.destination&&preview.destination!==model.destination){model.automatic_on_open=false;attemptMessage=tr('解释来源已更改，请刷新页面后继续。');return;}
   const approved=await api('glance-authorize',{token:preview.token,consent:true,page_owned:true});
   if(!active()){revokeOnClose(approved.grant);return;}grant=approved.grant;first=true;
  }else{
   const token=grant;await api('glance-heartbeat',{grant:token});if(!active()||grant!==token)return;
  }
  if(readingBusy||workInFlight||Date.now()<nextRetry)return;
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
 }finally{if(autoRun===run){autoRun=null;modelPending=false;if(!pageClosed&&current)render(current);}understandingControls();}
}
$('chat').onchange=()=>choose($('chat').value);$('reload').onclick=()=>refresh(true);
$('chatSearch').oninput=()=>{chatSearch=$('chatSearch').value;renderChatNavigation();};
$('chatBrowse').onclick=()=>toggleChatBrowser(true);$('chatNavClose').onclick=()=>toggleChatBrowser(false);$('chatBackdrop').onclick=()=>toggleChatBrowser(false);
window.addEventListener('keydown',event=>{if(event.key==='Escape')toggleChatBrowser(false);});

let readingEpoch=0,readingBusy=false,deepLoaded=false,pastPage=null;
function resetReading(){resetHistoryReview();resetUnderstanding();readingEpoch++;readingBusy=false;deepLoaded=false;pastPage=null;for(const id of ['deepPanel','pastPanel'])$(id).hidden=true;for(const id of ['deepRead','pastRead'])$(id).setAttribute('aria-expanded','false');$('deepText').replaceChildren();$('pastText').replaceChildren();}
function readingReady(){if(!grant)throw Error(tr('首页说明还在准备，请稍后再点。'));if(readingBusy||autoRun||workInFlight)throw Error(tr('有一段说明正在生成，请稍后再点。'));}
function readingActive(own,panel){return own===readingEpoch&&!pageClosed&&!$(panel).hidden&&(panel!=='pastPanel'||$('taskSummaryBox').open);}
async function readingModel(token,own,panel,status,visible=()=>true){
 for(let attempt=0;attempt<2;attempt++){
  if(!readingActive(own,panel)||!visible())return null;
  try{return await api('reading-explain',{grant,token});}
  catch(error){if(attempt===0&&['rate_limited','busy'].includes(error.reason)){
   status.textContent=tr('模型刚处理过一段说明，稍等片刻就继续…');
   await new Promise(resolve=>setTimeout(resolve,11000));
  }else throw error;}
 }
}
function readingParts(box,parts,data,local=false){
 box.replaceChildren();for(const part of parts){const item=data.result.explanations.find(i=>i.part===part.part);if(!item)continue;
 const section=make('section');section.append(make('h3',part.title),make('p',item.text));
 const refs=make('details');refs.append(make('summary',local?tr('本机记录 · 查看依据'):tr('模型说明 · 查看依据')));
 refs.open=local&&(part===parts[0]||part.part==='work');
 for(const id of item.evidence_ids){const ref=data.references.find(r=>r.evidence_id===id);if(ref)refs.append(make('blockquote',(ref.chat?'「'+ref.chat+'」 · ':'')+ref.title+'：'+ref.quote));}
 if(!item.evidence_ids.length)refs.append(make('p',tr('没有足够的可读依据。')));
 section.append(refs);box.append(section);}
}
async function loadDeep(){
 const own=readingEpoch;let started=false;$('deepRetry').hidden=true;
 if(!deepLoaded&&current){
  const titles={content:tr('具体做了什么'),explanation:tr('和前面有什么联系'),reason:tr('对整个任务有什么用')};
  const parts=Object.keys(titles).map(part=>({part,title:titles[part]}));
  readingParts($('deepText'),parts,{result:{explanations:parts.map(p=>({part:p.part,text:localStoryText(current,p.part),evidence_ids:[p.part]}))},references:parts.filter(p=>current.evidence?.[p.part]).map(p=>({evidence_id:p.part,title:titles[p.part],quote:current.evidence[p.part].text}))},true);
 }
 if(!grant||!model?.automatic_on_open){deepLoaded=true;$('deepNote').textContent=tr('本机记录详情 · 基于展开时的记录；开启上方解释后可进一步讲解。');return;}
 try{readingReady();readingBusy=true;started=true;$('deepNote').textContent=tr('模型正在把这一步展开讲清楚…');
 const frozen=await api('reading-current',{grant});if(!readingActive(own,'deepPanel'))return;
 const answer=await readingModel(frozen.token,own,'deepPanel',$('deepNote'));if(!answer||!readingActive(own,'deepPanel'))return;
 if(answer.result.mode!=='model')throw Error(answer.result.message||tr('这次详细说明没能生成，请稍后重试。'));
 readingParts($('deepText'),frozen.parts,answer);deepLoaded=true;$('deepNote').textContent=tr('模型深入说明 · ')+frozen.note;$('deepRetry').textContent=tr('按最新工作再解释');
 }catch(error){if(readingActive(own,'deepPanel')){$('deepNote').textContent=error.message;$('deepRetry').hidden=false;}}
 finally{if(started&&own===readingEpoch){readingBusy=false;$('deepRetry').hidden=false;}}
}
async function loadPast(snapshot=0,before=0){
 const own=readingEpoch;let started=false;$('pastRetry').hidden=true;$('pastOlder').hidden=true;
 const localOnly=!grant||!model?.automatic_on_open;
 try{if(localOnly){if(readingBusy)throw Error(tr('有一段说明正在生成，请稍后再点。'));}else readingReady();readingBusy=true;started=true;$('pastNote').textContent=tr('正在分段回顾这段聊天…');
 const page=localOnly?await api('reading-history?'+new URLSearchParams({...selected,snapshot,before})):await api('reading-history',{grant,snapshot,before});if(!readingActive(own,'pastPanel'))return;
 pastPage=page;page.before=before;$('pastText').replaceChildren();$('pastNewer').hidden=!before;
 for(const card of page.cards){
  const section=make('section');section.className='past-card';const heading=make('h3',card.title);card.heading=heading;section.append(heading);
  const time=make('p',(card.position?card.position+' · ':'')+age(card.stamp)+tr('的要求'));time.className='reading-caption';section.append(time);
  const short=make('p',card.local_summary||card.local?.find(p=>p.part==='request')?.text||tr('模型正在总结这一段…'));section.append(short);card.short=short;card.container=section;
  const button=make('button',tr('深入看这一段')),detail=make('div');detail.className='past-detail';detail.hidden=true;
  button.setAttribute('aria-expanded','false');button.onclick=()=>loadPastDetail(card,button,detail);
  section.append(button,detail);$('pastText').append(section);
  if(card.missing_reply){const limit=make('p',card.note);limit.className='reading-caption';section.append(limit);}
 }
 if(!page.token){$('pastNote').textContent=(page.cards.length?tr('本机记录详情 · 开启上方解释后，可请模型进一步讲解。'):tr('这部分还没有可读取的公开内容。'))+' '+page.note;return;}
 $('pastNote').textContent=tr('模型正在为这三段写简短总结…');
 const answer=await readingModel(page.token,own,'pastPanel',$('pastNote'));if(!answer||!readingActive(own,'pastPanel'))return;
 if(answer.result.mode!=='model')throw Error(answer.result.message||tr('模型暂时没能总结，点击下方重新读取。'));
 for(const card of page.cards){const item=answer.result.explanations.find(i=>i.part===card.id);card.short.textContent=item?.text||tr('这段暂时没有说明。');
  // A dedicated subject title preserves names after commas and complete pairs.
  // Legacy cached replies fall back to a sentence, never its first short clause.
  if(item)card.heading.textContent=item.title||item.text.split(/[。；]/)[0];
  const evidence=make('details');evidence.append(make('summary',tr('模型总结 · 查看依据')));for(const id of item?.evidence_ids||[]){const ref=answer.references.find(r=>r.evidence_id===id);if(ref)evidence.append(make('blockquote',ref.title+'：'+ref.quote));}card.container.append(evidence);
 }
 $('pastNote').textContent=page.note;
 }catch(error){if(readingActive(own,'pastPanel')){for(const card of pastPage?.cards||[])if(card.short.textContent===tr('模型正在总结这一段…'))card.short.textContent=tr('暂时没有模型总结；下面仍可单独展开这一段。');$('pastNote').textContent=error.message;$('pastRetry').hidden=false;}}
 finally{if(started&&own===readingEpoch){readingBusy=false;$('pastOlder').hidden=!pastPage?.has_more;$('pastRetry').hidden=false;$('pastRetry').textContent=tr('重新读取这一页');}}
}
async function loadPastDetail(card,button,box){
 if(!box.hidden){box.hidden=true;button.setAttribute('aria-expanded','false');return;}
 box.hidden=false;button.setAttribute('aria-expanded','true');if(card.loaded)return;
 const own=readingEpoch;let started=false;const status=make('p',tr('模型正在展开这一段…'));
 readingParts(box,card.parts,{result:{explanations:card.local||[]},references:card.references||[]},true);box.append(status);
 if(!grant||!model?.automatic_on_open||!card.detail_token){status.textContent=tr('本机记录详情 · 开启上方解释后，可请模型进一步讲解。');return;}
 try{readingReady();readingBusy=true;started=true;
 const answer=await readingModel(card.detail_token,own,'pastPanel',status,()=>!box.hidden);if(!answer||!readingActive(own,'pastPanel')||box.hidden)return;
 if(answer.result.mode!=='model')throw Error(answer.result.message||tr('这次没有生成详细说明。'));
 readingParts(box,card.parts,answer);card.loaded=true;
 }catch(error){if(readingActive(own,'pastPanel')){status.textContent=error.message;box.append(make('p',tr('收起后再展开可以重试；放久了请重新读取这一页。')));}}
 finally{if(started&&own===readingEpoch)readingBusy=false;}
}
$('deepRead').onclick=()=>{const panel=$('deepPanel');panel.hidden=!panel.hidden;$('deepRead').setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden&&!deepLoaded)void loadDeep();};
$('pastRead').onclick=()=>{const panel=$('pastPanel');panel.hidden=!panel.hidden;$('pastRead').setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden&&!pastPage)void loadPast();};
$('deepRetry').onclick=()=>loadDeep();$('pastRetry').onclick=()=>loadPast(pastPage?.snapshot||0,pastPage?.before||0);$('pastNewer').onclick=()=>loadPast();$('pastOlder').onclick=()=>{if(pastPage)void loadPast(pastPage.snapshot,pastPage.next_before);};

let workScope='chat',workData=null,workAnswer=null,workEpoch=0,workLoad=null,workAt=0,workInFlight=false,workRequestEpoch=-1,workMessage='',workDetails={};
function resetUnderstanding(scope='chat'){
 workEpoch++;workScope=scope;workData=null;workAnswer=null;workLoad=null;workAt=0;workMessage='';workDetails={};
 $('understandingParts').replaceChildren();delete $('understandingParts').dataset.contentKey;
 $('understandingChats').replaceChildren();$('understandingCoverage').textContent='';
 $('understandingTitle').textContent='';$('understandingNote').textContent=tr('正在整理工作目标与方法…');
 $('understandingSources').open=false;understandingControls();
}
function understandingControls(){
 $('scopeChat').setAttribute('aria-pressed',String(workScope==='chat'));
 $('scopeProject').setAttribute('aria-pressed',String(workScope==='project'));
 $('scopeProject').disabled=!current?.project;
 const button=$('understandingExplain');
 button.disabled=!workData||!grant||!model?.automatic_on_open||workInFlight||readingBusy||Boolean(autoRun)||pageClosed;
 button.textContent=workInFlight?tr('正在解读…'):workScope==='project'?tr('解读整个项目'):tr('解读这次聊天');
 $('understandingSendNote').textContent=!model?.automatic_on_open?tr('当前为本机记录摘要。开启上方解释后，可生成目标、方法和有效性的连贯解读。'):
  workScope==='project'?tr('点击后，将下方列出的同项目聊天短摘录交给所选解释服务；只生成这一次，使用你的账号额度。'):
  tr('点击后，根据这次聊天的较早要求、最新补充、公开做法和已知结果生成解读。');
}
function renderUnderstanding(){
 understandingControls();if(!workData)return;
 $('understandingTitle').textContent=(workScope==='project'?tr('项目：'):tr('聊天：'))+workData.title;
 const stale=workAnswer&&workAnswer.revision!==workData.revision;
 $('understandingNote').textContent=workMessage||(workInFlight?(workRequestEpoch===workEpoch?tr('正在联系所选解释服务，已有内容仍可查看。'):tr('上一段说明仍在生成，这里先显示本机摘要。')):workAnswer?
  (stale?tr('较早的解读 · 记录已有变化，点击下方按钮重新解读。'):tr('基于当前可读摘录的模型解读 · 结论仍需核对依据。')):
  tr('本机记录摘要 · 先列出已知要求、公开做法和结果，缺少的部分保留未知。'));
 if(workScope==='project'){
  const source=workAnswer?.source||workData;
  $('understandingNote').textContent+=' '+(uiLanguage==='en'?`Project scope: ${source.included_chats} of ${source.known_chats} currently listed chats; only opening and recent excerpts, not the full project history.`:`项目范围：当前列出的 ${source.known_chats} 段聊天中采用 ${source.included_chats} 段，仅含开场与近期摘录，并非完整项目历史。`);
 }
 const references=workAnswer?.references||workData.references;
 const values=workAnswer?Object.fromEntries(workAnswer.result.explanations.map(x=>[x.part,x])):workData.local;
 const labels={goal:tr('要达成什么目标'),strategy:tr('用什么方法与策略'),effectiveness:tr('方法是否有效')};
 updateExpanded($('understandingParts'),{values,references,details:workData.details,revision:workData.revision,expanded:workDetails,language:uiLanguage,modelReady:!!grant&&!!model?.automatic_on_open,busy:readingBusy||workInFlight||Boolean(autoRun)},()=>{
  for(const [index,part] of ['goal','strategy','effectiveness'].entries()){
   const item=values[part];if(!item)continue;
   const section=make('section');section.className='understanding-part';const heading=make('h3');
   const number=make('span',String(index+1).padStart(2,'0'));number.className='section-number';number.setAttribute('aria-hidden','true');heading.append(number,make('span',labels[part]));
   section.append(heading,make('p',item.text));
   const details=make('details');details.dataset.detailKey='work-'+part;
   details.append(make('summary',(workAnswer?tr('模型解读'):basis[item.basis]||tr('尚不清楚'))+tr(' · 查看依据')));
   for(const id of item.evidence_ids||[]){const ref=references.find(r=>r.evidence_id===id);if(ref)details.append(make('blockquote',(ref.chat?'「'+ref.chat+'」 · ':'')+ref.title+'：'+ref.quote));}
   if(!item.evidence_ids?.length)details.append(make('p',tr('没有足够的可读依据。')));
   section.append(details);appendWorkDetail(section,part,labels[part]);$('understandingParts').append(section);
  }
 });
 const source=workAnswer?.source||workData;
 $('understandingChats').replaceChildren();const list=make('ul');
 for(const chat of source.chats){const row=make('li'),link=make('a',chat.title);link.href='/?'+new URLSearchParams({client:chat.client,key:chat.key,lang:uiLanguage});row.append(link,make('span',' · '+age(chat.last_activity_ms)));if(chat.source_unavailable)row.append(make('span',tr(' · 原文暂时读不到')));list.append(row);}
 $('understandingChats').append(list);
 $('understandingCoverage').textContent=(uiLanguage==='en'?`Includes ${source.included_chats} of ${source.known_chats} chats currently listed (up to ${source.max_chats} per reading). `:`采用当前列出的 ${source.known_chats} 段聊天中的 ${source.included_chats} 段，每次最多 ${source.max_chats} 段。`)+source.note+
  (source.scope==='project'?tr(' 项目目录未被读取；尚未覆盖整个项目的所有聊天。')+tr(' 按当前客户端确认的项目归属汇总，跨客户端项目不会自动合并。'):'')+
  (source.catalog_limited||source.unavailable?tr(' 有些聊天暂时不可读取或未进入最近列表。'):'');
}
function appendWorkDetail(section,part,title){
 const entry=workDetails[part],source=entry?.source||workData,rows=source.details?.[part]||[{part,title,...source.local[part]}];
 const detail=make('details');detail.className='work-detail';detail.id='workDetail-'+part;detail.dataset.detailKey='work-detail-'+part;
 const summary=make('summary',tr('详细解释')+' · '+title);detail.append(summary);
 const body=make('div');body.className='work-detail-body';
 const note=make('p',entry?.message||(entry?.answer?tr('模型详细解释 · 基于点击时的记录。'):model?.automatic_on_open?tr('本机记录详情 · 下方可按当前范围请模型深入解释。'):tr('本机记录详情 · 开启上方解释后，可请模型进一步讲解。')));note.className='reading-caption';note.setAttribute('role','status');
 if(source.revision!==workData.revision)note.textContent+=' '+tr('记录已有变化，下方保留的是点击时的内容。');
 const text=make('div');text.className='detail-prose';
 readingParts(text,entry?.answer?source.parts:rows,entry?.answer||{result:{explanations:rows},references:source.references},!entry?.answer);
 const button=make('button',entry?.pending?tr('正在展开说明…'):tr('请模型进一步解释'));
 button.disabled=!grant||!model?.automatic_on_open||readingBusy||workInFlight||Boolean(autoRun)||pageClosed;
 button.onclick=()=>explainWorkDetail(part);body.append(note,text,button);detail.append(body);section.append(detail);
}
async function explainWorkDetail(part){
 if(!workData||!grant||!model?.automatic_on_open||readingBusy||workInFlight||autoRun||pageClosed)return;
 const own=workEpoch,readOwn=readingEpoch,selection={...selected},scope=workScope,token=grant,projectId=current?.project?.id;
 const prior=workDetails[part];
 const entry={source:prior?.answer?prior.source:workData,answer:prior?.answer,pending:true,message:tr('正在展开说明…')};workDetails[part]=entry;readingBusy=true;renderUnderstanding();
 const active=()=>own===workEpoch&&readOwn===readingEpoch&&!pageClosed&&grant===token&&workDetails[part]===entry&&$('workDetail-'+part).open&&JSON.stringify(selection)===JSON.stringify(selected)&&scope===workScope&&(scope!=='project'||current?.project?.id===projectId);
 try{
  const frozen=await api('reading-work',{grant:token,scope,part});if(!active())return;
  if(!entry.answer)entry.source=frozen;let answer;
  for(let attempt=0;attempt<2;attempt++){
   if(!active())return;
   try{answer=await api('reading-explain',{grant:token,token:frozen.token});break;}
   catch(error){if(attempt===0&&['rate_limited','busy'].includes(error.reason)){entry.message=tr('模型刚处理过一段说明，稍等片刻就继续…');renderUnderstanding();await new Promise(resolve=>setTimeout(resolve,11000));}else throw error;}
  }
  if(!active())return;
  if(answer.result.mode!=='model')throw Error(answer.result.message||tr('这次详细说明没能生成，请稍后重试。'));
  entry.source=frozen;entry.answer=answer;entry.message='';
 }catch(error){if(active())entry.message=error.message;}
 finally{entry.pending=false;if(entry.message===tr('正在展开说明…'))entry.message='';if(readOwn===readingEpoch)readingBusy=false;if(workData)renderUnderstanding();else understandingControls();}
}
async function loadUnderstanding(force=false){
 if(pageClosed||!selected||!current)return;
 if(workScope==='project'&&(!current.project||workData?.project?.id&&workData.project.id!==current.project.id))resetUnderstanding(current.project?'project':'chat');
 if(workLoad||workInFlight&&workRequestEpoch===workEpoch||(!force&&workData&&Date.now()-workAt<30000))return;
 const own=workEpoch,selection={...selected},scope=workScope,run={};workLoad=run;
 const active=()=>own===workEpoch&&!pageClosed&&JSON.stringify(selection)===JSON.stringify(selected)&&scope===workScope;
 try{const data=await api('work-understanding?'+new URLSearchParams({...selection,scope}));if(!active())return;workData=data;workAt=Date.now();workMessage='';renderUnderstanding();}
 catch(error){if(active()){workMessage=tr('工作解读暂时读不到，当前活动仍可查看。');$('understandingNote').textContent=workMessage;}}
 finally{if(workLoad===run)workLoad=null;understandingControls();}
}
async function chooseWorkScope(scope){
 if(scope===workScope||scope==='project'&&!current?.project)return;
 resetUnderstanding(scope);await loadUnderstanding(true);
}
async function explainUnderstanding(){
 if(!workData||!grant||!model?.automatic_on_open||workInFlight)return;
 if(readingBusy||autoRun){workMessage=tr('有一段说明正在生成，请稍后再点。');renderUnderstanding();return;}
 // Invalidate a local poll started before this frozen reading. A stale request
 // must never replace another scope's text, sources, or pending generation.
 const own=++workEpoch,selection={...selected},scope=workScope,token=grant,projectId=current?.project?.id;workLoad=null;workInFlight=true;workRequestEpoch=own;workMessage='';renderUnderstanding();
 const active=()=>own===workEpoch&&!pageClosed&&grant===token&&JSON.stringify(selection)===JSON.stringify(selected)&&scope===workScope&&(scope!=='project'||current?.project?.id===projectId);
 try{
  const frozen=await api('reading-work',{grant:token,scope});if(!active())return;
  workData=frozen;workAt=Date.now();renderUnderstanding();let answer;
  for(let attempt=0;attempt<2;attempt++){
   if(!active())return;
   try{answer=await api('reading-explain',{grant:token,token:frozen.token});break;}
   catch(error){if(attempt===0&&['rate_limited','busy'].includes(error.reason)){workMessage=tr('模型刚处理过一段说明，稍等片刻就继续…');renderUnderstanding();await new Promise(resolve=>setTimeout(resolve,11000));}else throw error;}
  }
  if(!active())return;
  if(answer.result.mode!=='model')throw Error(answer.result.message||tr('这次解读未能生成，本机记录仍保留。'));
  workAnswer={result:answer.result,references:answer.references,revision:frozen.revision,source:frozen};workMessage='';
 }catch(error){if(active())workMessage=error.message;}
 finally{workInFlight=false;if(workData)renderUnderstanding();else understandingControls();}
}
$('scopeChat').onclick=()=>chooseWorkScope('chat');$('scopeProject').onclick=()=>chooseWorkScope('project');$('understandingExplain').onclick=explainUnderstanding;
for(const part of ['content','explanation','reason'])$(part+'Basis').onclick=()=>{const box=$(part+'Proof');box.hidden=!box.hidden;$(part+'Basis').setAttribute('aria-expanded',String(!box.hidden));};
window.addEventListener('pagehide',closePage);
window.addEventListener('pageshow',()=>{pageClosed=false;nextRetry=0;void automatic();});
(async()=>{try{const initial=new URLSearchParams(location.search);if(names[initial.get('client')]&&/^[A-Za-z0-9_-]{1,4096}$/.test(initial.get('key')||''))selected={client:initial.get('client'),key:initial.get('key')};const data=await api('clients');model=data.explanation;renderProviderSettings();synthetic=data.mode==='synthetic';if(synthetic)$('connection').textContent=tr('模拟活动 · 用于检查');$('modelDetails').textContent=model?.configured?tr('使用你设置的模型，每小时最多 ')+model.max_calls_per_hour+tr(' 次。'):tr('未配置模型，仍可查看本机说明。');await refresh(true);if(data.mode==='synthetic'){$('refreshNote').textContent=tr('模拟活动 · 用于检查');document.title=tr('雪绪 · 模拟当前工作');}}catch(error){note(error.message);}})();
setInterval(()=>refresh(),6000);setInterval(automatic,15000);
