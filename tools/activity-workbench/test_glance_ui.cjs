/* Exercise the shipped script's polling behavior without an external browser dependency. */
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.open=false;this.parent=null;this.textContent='';}
 append(...items){for(const item of items){item.parent=this;this.children.push(item);}}
 replaceChildren(...items){this.children=[];this.append(...items);}
 addEventListener(){} setAttribute(){}
 contains(item){return item===this||this.children.some(c=>c.contains(item));}
 closest(tag){return this.tag===tag?this:this.parent?.closest(tag);}
 querySelectorAll(selector){const items=this.children.flatMap(c=>[c,...c.querySelectorAll('*')]);return items.filter(c=>selector==='*'||c.tag==='details'&&(selector==='details'||c.open));}
 querySelector(tag){return this.children.find(c=>c.tag===tag);}
 focus(){this.focused=true;}
}
function setup({clientRequests=false}={}){
 const elements=new Map(),pending=[],listeners={},timers=[];const document={activeElement:null,hidden:false,createElement:tag=>new Element(tag),getElementById:id=>{const live=[...elements.values()].flatMap(e=>[e,...e.querySelectorAll('*')]).find(e=>e.id===id);if(live)return live;if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id);}};
 const context=vm.createContext({document,location:{search:''},URLSearchParams,AbortSignal,atob,setInterval(){},setTimeout(fn){timers.push(fn);},window:{addEventListener(name,fn){listeners[name]=fn;}},fetch:async (url,options)=>{
  if(url==='/api/clients'&&!clientRequests)return new Promise(()=>{}); // Leave page startup out of the focused polling test.
  return new Promise(resolve=>pending.push({url,options,resolve:(value,status=200)=>resolve({ok:status<400,json:async()=>value})}));
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/glance.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/history-review.js'),'utf8'),context);
 return {context,document,elements,pending,listeners,timers,run:code=>vm.runInContext(code,context)};
}
test('unchanged polling retains the same evidence subtree and focus',()=>{
 const f=setup(),box=new Element('div'),proof=new Element('details');proof.dataset.detailKey='goal';proof.open=true;box.append(proof);
 let draws=0;Object.assign(f.context,{box,draw:()=>{draws++;box.append(proof);}});
 f.run('updateExpanded(box,{snapshot:1,goal:"same"},draw)');f.document.activeElement=proof;
 f.run('updateExpanded(box,{snapshot:999,goal:"same"},draw)');assert.equal(draws,1);assert.equal(box.children[0],proof);assert.equal(proof.open,true);
});
test('changed content retains an opened matching proof and keyboard position',()=>{
 const f=setup(),box=new Element('div');let proof;
 Object.assign(f.context,{box,draw:()=>{proof=new Element('details');proof.dataset.detailKey='goal';proof.append(new Element('summary'));box.append(proof);}});
 f.run('updateExpanded(box,{snapshot:1,now:"old"},draw)');proof.open=true;f.document.activeElement=proof.children[0];
 f.run('updateExpanded(box,{snapshot:2,now:"new"},draw)');assert.equal(proof.open,true);assert.equal(proof.children[0].focused,true);
});
function currentWork(revision='r1'){
 return {client:'codex',key:'chat-a',title:'模拟任务',status:'这一轮已结束',tone:'quiet',goal:'简化首页',goal_short:'简化首页',revision,
 evidence:{goal:{text:'要求'},content:{text:'助手报告'}},recent:[],last_activity_ms:Date.now(),content:'本机内容',explanation:'本机解释',reason:'本机原因',content_basis:'assistant',explanation_basis:'inference',reason_basis:'inference',recorder:{state:'waiting'}};
}
test('a limited explanation excerpt does not overwrite the chat navigation state',()=>{
 const f=setup();f.context.data={...currentWork(),activity_state:'unknown'};
 f.run('chatCatalog=[{client:"codex",key:"chat-a",title:"模拟任务",activity_state:"working"}];render(data)');
 assert.equal(f.run('chatCatalog[0].activity_state'),'working');
});
test('the page has no manual-start explanation controls and distinguishes temporary local prose',()=>{
 const f=setup();f.context.data=currentWork();f.run('model={configured:true,automatic_on_open:true};render(data)');
 assert.equal(f.elements.has('explain'),false);assert.equal(f.elements.has('stopAuto'),false);
 assert.match(f.elements.get('modelNote').textContent,/自动解释.*暂为本机记录/);
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');
 assert.doesNotMatch(html,/id="(?:explain|stopAuto)"/);
});
test('an untranslated local note does not promise a model call or invent an assistant update',()=>{
 const f=setup();f.context.data=currentWork();f.run('uiLanguage="en";model={configured:false};render(data)');
 assert.match(f.elements.get('content').textContent,/not available yet/);
 assert.doesNotMatch(f.elements.get('content').textContent,/being prepared|assistant has shared/i);
 assert.match(f.elements.get('contentBasis').textContent,/尚不清楚/);
});
test('a model answer stays readable while new work is marked for automatic update',()=>{
 const f=setup();f.context.data=currentWork();f.run('model={configured:true,automatic_on_open:true};render(data)');
 f.context.result={mode:'model',explanations:['content','explanation','reason'].map(part=>({part,text:'模型'+part,basis:'inference',evidence_ids:[]}))};
 f.run('showAnswer(result,[],1,"r1")');assert.equal(f.elements.get('content').textContent,'模型content');
 assert.match(f.elements.get('modelNote').textContent,/模型说明.*自动跟进/);
 f.context.data=currentWork('r2');f.run('render(data)');assert.equal(f.elements.get('content').textContent,'模型content');
 assert.match(f.elements.get('modelNote').textContent,/稍早.*自动更新/);
});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function reviewData(section='overview'){
 const parts=section==='overview'?['goal','before','now','next']:['step1'];
 return {snapshot:42,next_before:21,has_more:true,note:'有限范围',references:[{evidence_id:'R1',title:'来源',quote:'RAW_SOURCE_NOT_A_RECAP'}],
 parts:parts.map(part=>({part,title:part,allowed:['R1'],required:['R1']})),...(section==='steps'?{items:[{part:'step1',title:'请求读取文件',tool:'Read',kind:'operation',status:'结果仍不明确'}]}:{})};
}
test('history has two independent top-level disclosures and retains older history',()=>{
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');
 assert.equal((html.match(/class="review-group"/g)||[]).length,2);
 for(const id of ['taskSummaryBox','detailsBox','pastRead','pastOlder','historyRecords'])assert.ok(html.includes('id="'+id+'"'));
});
test('history without a model shows placeholders, with source text only under folded evidence',async()=>{
 const f=setup();f.run('selected={client:"codex",key:"chat-a"};$("taskSummaryBox").open=true');
 const request=f.run('loadReview("overview")');f.pending[0].resolve(reviewData());await request;
 assert.equal(f.pending.length,1);assert.equal(f.run('Object.keys(reviews.overview.nodes).length'),4);
 assert.equal(f.run('reviews.overview.nodes.goal.textContent'),'等待模型解读');
 const row=f.elements.get('taskSummary').children[0],proof=row.children.at(-1);
 assert.equal(proof.open,false);assert.match(proof.children[1].textContent,/RAW_SOURCE/);
});
test('switching chats rejects late history data',async()=>{
 const f=setup();f.run('selected={client:"codex",key:"chat-a"};$("detailsBox").open=true');
 const request=f.run('loadReview("steps")');f.run('resetHistoryReview();selected={client:"codex",key:"chat-b"}');
 f.pending[0].resolve(reviewData('steps'));await request;
 assert.equal(f.elements.get('reviewSteps').children.length,0);
});
test('closing a history block after preparing prevents a model send',async()=>{
 const f=setup();enabledPage(f);f.context.review=reviewData();
 f.run('grant="page-only";$("taskSummaryBox").open=true;reviews.overview.data=review;drawReview("overview")');
 const request=f.run('generateReview("overview")');f.run('$("taskSummaryBox").open=false');
 f.pending[0].resolve({...reviewData(),token:'frozen'});await request;
 assert.equal(f.pending.length,1);assert.equal(f.run('readingBusy'),false);
});
test('each history paragraph requests a fresh focused explanation and shows failures honestly',async()=>{
 const f=setup();enabledPage(f);f.context.review=reviewData();
 f.run('grant="page-only";$("taskSummaryBox").open=true;reviews.overview.data=review;drawReview("overview");reviews.overview.details.before.element.open=true');
 const request=f.run('generateReview("overview","before")');
 assert.deepEqual(JSON.parse(f.pending[0].options.body),{grant:'page-only',section:'overview',part:'before'});
 f.pending[0].resolve({...reviewData(),token:'fresh'});await tick();
 f.pending[1].resolve({result:{mode:'fallback',message:'请重新登录所选解释来源。'}});await request;
 assert.match(f.run('reviews.overview.details.before.status.textContent'),/重新登录/);
 assert.equal(f.run('reviews.overview.details.before.body.children.length'),0);
 assert.equal(f.run('reviews.overview.nodes.before.textContent'),'等待模型解读');
});
test('step summaries and tools remain separate and detailed explanation uses the frozen page',async()=>{
 const f=setup();enabledPage(f);f.context.review=reviewData('steps');
 f.run('grant="page-only";$("detailsBox").open=true;reviews.steps.data=review;reviews.steps.before=30;drawReview("steps");reviews.steps.details.step1.element.open=true');
 const request=f.run('generateReview("steps","step1")');
 assert.deepEqual(JSON.parse(f.pending[0].options.body),{grant:'page-only',section:'steps',snapshot:42,before:30,part:'step1'});
 f.pending[0].resolve({...reviewData('steps'),token:'frozen'});await tick();
 f.pending[1].resolve({result:{mode:'model',explanations:[{part:'step1',text:'这一步查看了入口说明，结果还需核对。',evidence_ids:['R1']}]},references:reviewData().references});await request;
 assert.match(f.run('reviews.steps.details.step1.body.children[0].textContent'),/入口说明/);
 const row=f.elements.get('reviewSteps').children[0];assert.ok(row.children[1].children.some(n=>n.textContent==='Read'));
});
function understanding(scope='chat',revision='work-r1'){
 return {scope,revision,title:scope==='project'?'页面项目':'简化首页',project:{id:'project-a',name:'页面项目'},
  chats:[{client:'codex',key:'chat-a',title:'简化首页',last_activity_ms:1}],included_chats:1,known_chats:1,max_chats:6,note:'有限公开摘录',references:[{evidence_id:'E1',title:'要求',quote:'让页面易懂',chat:'简化首页'}],
  local:Object.fromEntries(['goal','strategy','effectiveness'].map(part=>[part,{text:scope+' '+part,basis:'unknown',evidence_ids:['E1']}]))};
}
test('existing content has one category and work understanding has its own scope',()=>{
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');
 assert.match(html,/id="happeningHeading">正在发生/);assert.match(html,/id="activityDetails"/);
 assert.match(html,/id="understandingHeading">这项工作如何推进/);
 assert.match(html,/id="scopeProject"[^>]*disabled/);
 assert.doesNotMatch(html,/part-number|part-title">内容|part-title">解释|part-title">原因/);
 assert.ok(html.indexOf('id="deepRead"')<html.indexOf('id="activityDetails"'));
 assert.ok(html.indexOf('id="historyHeading"')>html.indexOf('id="workUnderstanding"'));
});
function detailedUnderstanding(scope='chat',revision='details-r1'){
 const data=understanding(scope,revision);
 data.details=Object.fromEntries(['goal','strategy','effectiveness'].map(part=>[part,[{part:part+'_origin',title:'来源与范围',text:'记录支持的说明 '+part,evidence_ids:['E1'],basis:'unknown'}]]));
 return data;
}
test('each work part expands locally without a model account',()=>{
 const f=setup();f.context.work=detailedUnderstanding();f.run('workData=work;renderUnderstanding()');
 for(const part of ['goal','strategy','effectiveness']){
  const detail=f.document.getElementById('workDetail-'+part);detail.open=true;
  assert.match(detail.children[0].textContent,/详细解释/);
  assert.match(detail.children[1].children[1].children[0].children[1].textContent,/记录支持/);
 }
 assert.equal(f.pending.length,0);
});
test('a focused reading freezes the clicked part and keeps its earlier version labeled',async()=>{
 const f=setup();enabledPage(f);f.context.work=detailedUnderstanding();f.run('grant="page-only";workData=work;renderUnderstanding();$("workDetail-goal").open=true');
 const request=f.run('explainWorkDetail("goal")');assert.deepEqual(JSON.parse(f.pending[0].options.body),{grant:'page-only',scope:'chat',part:'goal'});
 f.pending[0].resolve({...detailedUnderstanding(),focus:'goal',token:'only-goal',parts:[{part:'goal_origin',title:'目标来源'}]});await tick();
 assert.equal(JSON.parse(f.pending[1].options.body).token,'only-goal');
 f.pending[1].resolve({result:{mode:'model',explanations:[{part:'goal_origin',text:'目标是让工作进展更容易理解，效果尚待验证。',evidence_ids:['E1']}]},references:understanding().references});await request;
 assert.equal(f.run('workDetails.goal.answer.result.mode'),'model');assert.equal(f.run('readingBusy'),false);
 f.context.later=detailedUnderstanding('chat','details-r2');f.run('workData=later;renderUnderstanding()');
 assert.match(f.document.getElementById('workDetail-goal').children[1].children[0].textContent,/记录已有变化/);
 assert.equal(f.document.getElementById('workDetail-goal').open,true);
});
test('closing a detail before preparation completes prevents a model send',async()=>{
 const f=setup();enabledPage(f);f.context.work=detailedUnderstanding();f.run('grant="page-only";workData=work;renderUnderstanding();$("workDetail-strategy").open=true');
 const request=f.run('explainWorkDetail("strategy")');f.document.getElementById('workDetail-strategy').open=false;
 f.pending[0].resolve({...detailedUnderstanding(),token:'late',parts:[]});await request;
 assert.equal(f.pending.length,1);assert.equal(f.run('readingBusy'),false);
});
test('switching work scopes rejects a late detailed result and retains local reading',async()=>{
 const f=setup();enabledPage(f);f.context.work=detailedUnderstanding('project');
 f.run('grant="page-only";current.project={id:"project-a"};workScope="project";workData=work;renderUnderstanding();$("workDetail-effectiveness").open=true');
 const request=f.run('explainWorkDetail("effectiveness")');
 f.pending[0].resolve({...detailedUnderstanding('project'),token:'earlier-project',parts:[]});await tick();
 const change=f.run('chooseWorkScope("chat")');f.pending[2].resolve(detailedUnderstanding());await change;
 f.pending[1].resolve({result:{mode:'model',explanations:[]},references:[]});await request;
 assert.equal(f.run('workScope'),'chat');assert.equal(f.run('workDetails.effectiveness'),undefined);assert.equal(f.run('readingBusy'),false);
});
test('current details and paged history remain readable with explanations off',async()=>{
 const f=setup();f.context.work=currentWork();f.run('current=work;selected={client:"codex",key:"chat-a"};$("deepPanel").hidden=false');
 await f.run('loadDeep()');assert.equal(f.pending.length,0);assert.equal(f.elements.get('deepText').children.length,3);
 f.run('$("taskSummaryBox").open=true;$("pastPanel").hidden=false');const request=f.run('loadPast(42,21)');
 assert.match(f.pending[0].url,/reading-history\?.*snapshot=42&before=21/);assert.equal(f.pending[0].options.method,'GET');
 const card={id:'section1',title:'较早要求',stamp:1,parts:[{part:'request',title:'当时的要求'}],local:[{part:'request',text:'较早的公开记录',evidence_ids:[]}],references:[]};
 f.pending[0].resolve({cards:[card],token:null,snapshot:42,next_before:10,has_more:true,note:'每次三段'});await request;
 assert.equal(f.elements.get('pastOlder').hidden,false);
 f.run('$("offlineDetail").hidden=true');await f.run('loadPastDetail(pastPage.cards[0],$("offlineButton"),$("offlineDetail"))');
 assert.equal(f.elements.get('offlineDetail').children[0].children[1].textContent,'较早的公开记录');assert.equal(f.pending.length,1);
});
test('English current details keep untranslated excerpts in supporting notes',async()=>{
 const f=setup();f.context.work=currentWork();f.run('uiLanguage="en";current=work;$("deepPanel").hidden=false');
 await f.run('loadDeep()');
 for(const section of f.elements.get('deepText').children)assert.doesNotMatch(section.children[1].textContent,/[\u3400-\u9fff]/);
 assert.match(f.elements.get('deepText').children[0].children[2].children[1].textContent,/助手报告/);
});
test('scope change only reads locally and rejects an older scope response',async()=>{
 const f=setup();f.context.data=currentWork();f.run('selected={client:"codex",key:"chat-a"};current={...data,project:{id:"project-a"}}');
 const first=f.run('loadUnderstanding(true)');assert.match(f.pending[0].url,/scope=chat/);
 const second=f.run('chooseWorkScope("project")');assert.match(f.pending[1].url,/scope=project/);
 f.pending[1].resolve(understanding('project'));await second;
 f.pending[0].resolve(understanding('chat'));await first;
 assert.equal(f.run('workData.scope'),'project');assert.equal(f.run('workAnswer'),null);
 assert.ok(f.pending.every(p=>p.options.method==='GET'));
});
test('work generation freezes selected project and an older model reply cannot cross scopes',async()=>{
 const f=setup();enabledPage(f);f.context.work=understanding('project');
 f.run('current.project={id:"project-a"};grant="page-only";workScope="project";workData=work;renderUnderstanding()');
 const request=f.run('explainUnderstanding()');assert.equal(f.pending[0].url,'/api/reading-work');
 assert.equal(JSON.parse(f.pending[0].options.body).scope,'project');
 f.pending[0].resolve({...understanding('project'),token:'frozen-project'});await tick();
 assert.equal(f.pending[1].url,'/api/reading-explain');
 f.run('resetUnderstanding("chat")');
 f.pending[1].resolve({result:{mode:'model',explanations:[]},references:[]});await request;
 assert.equal(f.run('workAnswer'),null);assert.equal(f.run('workInFlight'),false);
});
test('closing during project preparation prevents a model request',async()=>{
 const f=setup();enabledPage(f);f.context.work=understanding('project');
 f.run('current.project={id:"project-a"};grant="page-only";workScope="project";workData=work');
 const request=f.run('explainUnderstanding()');f.listeners.pagehide();
 f.pending[0].resolve({...understanding('project'),token:'frozen-project'});await request;
 assert.ok(!f.pending.some(p=>p.url==='/api/reading-explain'));assert.equal(f.run('workAnswer'),null);
});
test('switching scopes keeps local reading available during a slow model request',async()=>{
 const f=setup();enabledPage(f);f.context.work=understanding();
 f.run('current.project={id:"project-a"};grant="page-only";workData=work');
 const generation=f.run('explainUnderstanding()');f.pending[0].resolve({...understanding(),token:'chat-frozen'});await tick();
 const local=f.run('chooseWorkScope("project")');assert.match(f.pending[2].url,/work-understanding.*scope=project/);
 f.pending[2].resolve(understanding('project'));await local;
 assert.equal(f.run('workData.scope'),'project');assert.match(f.elements.get('understandingNote').textContent,/上一段说明仍在生成/);
 f.pending[1].resolve({result:{mode:'model',explanations:[]},references:[]});await generation;
 assert.equal(f.run('workAnswer'),null);assert.doesNotMatch(f.elements.get('understandingNote').textContent,/仍在生成/);
});
test('failed work generation retains local evidence and later changes label an old answer',async()=>{
 const f=setup();enabledPage(f);f.context.work=understanding();
 f.run('grant="page-only";workData=work');const request=f.run('explainUnderstanding()');
 f.pending[0].resolve({...understanding(),token:'frozen-chat'});await tick();
 f.pending[1].resolve({result:{mode:'fallback',message:'模型暂不可用'},references:[]});await request;
 assert.equal(f.run('workAnswer'),null);assert.equal(f.run('workData.local.goal.text'),'chat goal');
 assert.equal(f.elements.get('understandingNote').textContent,'模型暂不可用');
 f.context.answer={result:{mode:'model',explanations:[{part:'goal',text:'Earlier goal',basis:'inference',evidence_ids:['E1']}]},references:understanding().references,revision:'older',source:understanding()};
 f.run('workAnswer=answer;workMessage="";renderUnderstanding()');
 assert.match(f.elements.get('understandingNote').textContent,/较早.*变化/);
});
test('reassigned project clears old narrative even when its display name is unchanged',async()=>{
 const f=setup();enabledPage(f);f.context.work=understanding('project');
 f.run('current.project={id:"new-project",name:"页面项目"};workData=work;workScope="project";workAnswer={revision:"private-old"}');
 const request=f.run('loadUnderstanding(true)');assert.equal(f.run('workAnswer'),null);
 f.pending[0].resolve({...understanding('project'),project:{id:'new-project',name:'页面项目'}});await request;
 assert.equal(f.run('workData.project.id'),'new-project');
});
test('a long project reading renews the lease without triggering another explanation',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";workInFlight=true');
 const poll=f.run('automatic()');assert.equal(f.pending[0].url,'/api/glance-heartbeat');
 f.pending[0].resolve({alive:true});await poll;assert.equal(f.pending.length,1);
});
test('client sections start collapsed and list chats directly without project folders',()=>{
 const f=setup();f.context.cards=[{client:'codex',key:'a',title:'雪绪首页',project:{id:'p',name:'Yukio'},activity_state:'working'},
 {client:'claude',key:'b',title:'检查图片',project:{id:'q',name:'封面设计'},activity_state:'inactive'},
 {client:'codex',key:'c',title:'之前的工作',activity_state:'unknown'},
 {client:'codex',key:'d',title:'需要回答',activity_state:'waiting'}];
 f.run('selected={client:"codex",key:"a"};chatCatalog=cards;renderChatNavigation()');
 const list=f.elements.get('chatLists'),sections=list.children.filter(c=>c.tag==='details');
 assert.deepEqual(sections.map(c=>c.dataset.client),['claude','codex']);assert.ok(sections.every(c=>!c.open));
 const rows=list.querySelectorAll('*').filter(c=>c.tag==='button'&&c.className?.startsWith('chat-row'));
 assert.equal(rows.length,4);assert.deepEqual(rows.map(c=>c.children[1].children[0].className),['chat-state inactive','chat-state working','chat-state unknown','chat-state waiting']);
 assert.equal(new Set(rows.map(c=>c.dataset.chatValue)).size,4);assert.equal(list.querySelectorAll('details').length,2);
 assert.deepEqual(sections.map(c=>c.children[0].children[1].textContent),['1','3']);
 assert.equal(f.elements.has('filterWorking'),false);assert.equal(f.elements.has('filterInactive'),false);
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');assert.doesNotMatch(html,/id="filter(?:Recent|Working|Inactive)"|按工作状态查看/);
 assert.equal(f.run('filteredChats(cards,"雪绪")[0].key'),'a');assert.equal(f.run('filteredChats(cards,"claude")[0].key'),'b');
 f.run('chatSearch="图片";renderChatNavigation()');assert.equal(f.run('selected.key'),'a');assert.equal(f.pending.length,0);
});
test('identical titles across clients remain separate and helper chats keep their source',()=>{
 const f=setup();f.context.cards=[{client:'codex',key:'a',title:'App'},{client:'claude',key:'b',title:'App'},{client:'claude',key:'helper',title:'协助检查',is_helper:true}];
 f.run('chatCatalog=cards;renderChatNavigation()');
 const children=f.elements.get('chatLists').children;
 assert.deepEqual(children.map(c=>c.dataset.client),['claude','codex']);
 const rows=f.elements.get('chatLists').querySelectorAll('*').filter(c=>c.tag==='button'&&c.className?.startsWith('chat-row'));
 assert.equal(rows.length,3);assert.equal(children[0].children[1].children[1].dataset.chatValue,JSON.stringify({client:'claude',key:'helper'}));
 assert.match(children[0].children[1].children[1].children[0].children[1].textContent,/协助助手/);
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');
 assert.match(html,/id="chat" hidden aria-hidden="true"/);assert.match(html,/id="chatSearch"/);
});
test('polling preserves client disclosure, focused summary and scroll position',()=>{
 const f=setup();f.context.cards=[{client:'claude',key:'a',title:'一个聊天'},{client:'codex',key:'b',title:'另一个聊天'}];
 f.run('chatCatalog=cards;renderChatNavigation()');const list=f.elements.get('chatLists');
 list.children[0].open=true;f.document.activeElement=list.children[0].children[0];list.scrollTop=48;
 f.run('chatCatalog[0].title="改过名字";renderChatNavigation()');
 assert.equal(list.children[0].open,true);assert.equal(list.children[1].open,false);
 assert.equal(list.children[0].children[0].focused,true);assert.equal(list.scrollTop,48);
 list.children[0].open=false;f.run('chatCatalog[0].activity_state="working";renderChatNavigation()');
 assert.equal(list.children[0].open,false);
});
test('search temporarily reveals matches and clearing it restores manual folds without selecting a chat',()=>{
 const f=setup();f.context.cards=[{client:'claude',key:'a',title:'图片处理'},{client:'codex',key:'b',title:'页面设计'}];
 f.run('chatCatalog=cards;selected={client:"codex",key:"b"};renderChatNavigation()');const list=f.elements.get('chatLists');
 list.children[1].open=true;
 f.run('chatSearch="图片";renderChatNavigation()');assert.equal(list.children.length,1);assert.equal(list.children[0].open,true);
 f.run('chatCatalog[0].activity_state="working";renderChatNavigation();chatSearch="";renderChatNavigation()');
 assert.equal(list.children[0].open,false);assert.equal(list.children[1].open,true);
 assert.equal(f.run('selected.key'),'b');assert.equal(f.pending.length,0);
});
test('unreadable and explicitly empty chats do not appear in counts or search',()=>{
 const f=setup();f.context.cards=[{client:'claude',key:'gone',title:'空聊天',source_unavailable:true},{client:'codex',key:'empty',title:'只有名字',has_content:false},{client:'claude',key:'readable',title:'好',has_content:true}];
 f.run('chatCatalog=cards;renderChatNavigation()');const list=f.elements.get('chatLists');
 assert.equal(list.children.length,1);assert.equal(list.children[0].children[0].children[1].textContent,'1');
 assert.equal(list.children[0].children[1].children.length,1);
 assert.equal(f.run('filteredChats(cards,"空聊天").length'),0);
});
function enabledPage(f){f.context.data=currentWork();f.run('selected={client:"codex",key:"chat-a"};model={configured:true,automatic_on_open:true};render(data)');}
test('opening the page starts one page-owned explanation without any click',async()=>{
 const f=setup();enabledPage(f);const request=f.run('automatic()');
 assert.equal(f.pending[0].url,'/api/glance-preview');await f.run('automatic()');assert.equal(f.pending.length,1);
 f.pending[0].resolve({token:'bounded'});await tick();assert.equal(f.pending[1].url,'/api/glance-authorize');
 assert.equal(JSON.parse(f.pending[1].options.body).page_owned,true);
 f.pending[1].resolve({grant:'page-only'});await tick();assert.equal(f.pending[2].url,'/api/glance-refresh');
 assert.equal(JSON.parse(f.pending[2].options.body).force,true);
 f.pending[2].resolve({mode:'updated',result:{mode:'model',explanations:[]},references:[],snapshot:1,revision:'r1'});await tick();
 f.pending[3].resolve(currentWork());await request;
 assert.equal(f.run('grant'),'page-only');assert.equal(f.elements.has('preview'),false);
 const ongoing=f.run('automatic()');assert.equal(f.pending[4].url,'/api/glance-heartbeat');
 f.pending[4].resolve({alive:true});await tick();assert.equal(f.pending[5].url,'/api/glance-refresh');
 assert.equal(JSON.parse(f.pending[5].options.body).force,undefined);f.pending[5].resolve({mode:'waiting'});await ongoing;
});
test('closing the page revokes it and prevents any later update',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only"');f.listeners.pagehide();
 assert.equal(f.pending[0].url,'/api/glance-stop');assert.equal(f.pending[0].options.keepalive,true);
 assert.equal(f.run('grant'),null);await f.run('automatic()');assert.equal(f.pending.length,1);
});
test('a grant arriving after close is revoked before any model request',async()=>{
 const f=setup();enabledPage(f);const request=f.run('automatic()');f.pending[0].resolve({token:'bounded'});await tick();
 f.listeners.pagehide();f.pending[1].resolve({grant:'late-page'});await request;
 assert.equal(f.pending[2].url,'/api/glance-stop');assert.equal(f.pending.length,3);
 assert.equal(f.run('grant'),null);assert.equal(f.run('pageClosed'),true);
});
test('no model starts without configured page permission or a selected readable chat',async()=>{
 const f=setup();enabledPage(f);f.run('model.automatic_on_open=false');await f.run('automatic()');assert.equal(f.pending.length,0);
 f.run('model.automatic_on_open=true;current=null');await f.run('automatic()');assert.equal(f.pending.length,0);
});

const chatKey=(file,generation,session,agent='',side=0)=>Buffer.from(JSON.stringify([file,generation,session,agent,side])).toString('base64url');
test('resuming the same explicit chat finds the latest file without matching titles',()=>{
 const f=setup();f.context.old={client:'codex',key:chatKey('old',2,'chat-a')};
 f.context.cards=[{client:'codex',key:chatKey('new',1,'chat-a'),title:'changed title'}];
 assert.equal(f.run('continuation(old,cards).key'),f.context.cards[0].key);
 for(const foreign of [{client:'claude',key:chatKey('new',1,'chat-a')},{client:'codex',key:chatKey('new',1,'chat-b')},{client:'codex',key:chatKey('new',1,'chat-a','helper')},{client:'codex',key:chatKey('new',1,'chat-a','',1)}]){
  f.context.cards=[foreign];assert.equal(f.run('continuation(old,cards)'),null);
 }
 f.context.cards=[{client:'codex',key:chatKey('new',1,'chat-a')},{client:'codex',key:chatKey('other',1,'chat-a')}];
 assert.equal(f.run('continuation(old,cards)'),null);
});
test('a continuation resets the model answer and revokes the old send grant',async()=>{
 const f=setup();f.run('busy=true;modelAnswer={private:"old"};grant="old-grant"');
 const next={client:'codex',key:chatKey('new',1,'chat-a')};f.context.next=next;
 const request=f.run('choose(JSON.stringify(next))');assert.equal(f.pending[0].url,'/api/glance-stop');
 f.pending[0].resolve({stopped:true});await request;
 assert.equal(f.run('grant'),null);assert.equal(f.run('modelAnswer'),null);assert.equal(f.run('modelPending'),false);
 assert.equal(f.run('selected.key'),next.key);assert.equal(f.run('refreshAgain'),true);
});

test('Claude desktop continuation uses explicit members, never a matching title or child agent',()=>{
 const f=setup();f.context.old={client:'claude',key:chatKey('old',1,'prior-cli')};
 f.context.cards=[{client:'claude',key:chatKey('current',1,'current-cli'),title:'Same title',conversation_id:'desktop-chat',continuation_sessions:['prior-cli','current-cli']}];
 assert.equal(f.run('continuation(old,cards).key'),f.context.cards[0].key);
 f.context.old={client:'claude',key:chatKey('old',1,'prior-cli','helper',1)};
 assert.equal(f.run('continuation(old,cards)'),null);
 f.context.old={client:'codex',key:chatKey('old',1,'prior-cli')};assert.equal(f.run('continuation(old,cards)'),null);
 f.context.old={client:'claude',key:chatKey('old',1,'unrelated'),title:'Same title'};assert.equal(f.run('continuation(old,cards)'),null);
 f.context.old={client:'claude',key:chatKey('old',1,'prior-cli')};f.context.cards.push({...f.context.cards[0],key:chatKey('other',1,'another-cli')});
 assert.equal(f.run('continuation(old,cards)'),null);
});
test('rewinding a Claude desktop chat clears old-branch explanations and revokes their grant',async()=>{
 const f=setup();f.context.old={client:'claude',key:chatKey('old',1,'prior-cli')};
 f.context.next={client:'claude',key:chatKey('new',1,'current-cli')};
 f.run('selected=old;busy=true;modelAnswer={snapshot:"abandoned branch"};grant="old-grant"');
 const request=f.run('continueSelection(next)');assert.equal(f.pending[0].url,'/api/glance-stop');
 f.pending[0].resolve({stopped:true});await request;
 assert.equal(f.run('modelAnswer'),null);assert.equal(f.run('grant'),null);assert.equal(f.run('selected.key'),f.context.next.key);
});

test('a confirmed same-chat continuation retains the earlier explanation while replacing its grant',async()=>{
 const f=setup();f.run('busy=true;modelAnswer={snapshot:1};grant="old-grant"');
 const next={client:'codex',key:chatKey('new',1,'chat-a')};f.context.next=next;
 const request=f.run('choose(JSON.stringify(next),true)');f.pending[0].resolve({stopped:true});await request;
 assert.equal(f.run('modelAnswer.snapshot'),1);assert.equal(f.run('grant'),null);
});

test('deep explanation is requested on demand and reopening preserves its readable result',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("deepPanel").hidden=false');
 const request=f.run('loadDeep()');assert.equal(f.pending[0].url,'/api/reading-current');
 f.pending[0].resolve({token:'detail',parts:[{part:'action',title:'具体做什么'}],note:'点击时的片段'});await tick();
 assert.equal(f.pending[1].url,'/api/reading-explain');assert.equal(JSON.parse(f.pending[1].options.body).token,'detail');
 f.pending[1].resolve({result:{mode:'model',explanations:[{part:'action',text:'把旧记录分段讲清楚。',evidence_ids:[]}]},references:[]});await request;
 assert.equal(f.elements.get('deepText').children[0].children[1].textContent,'把旧记录分段讲清楚。');
 f.elements.get('deepRead').onclick();f.elements.get('deepRead').onclick();assert.equal(f.pending.length,2);
});
test('closing during detailed preparation prevents its model send',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("deepPanel").hidden=false');
 const request=f.run('loadDeep()');f.listeners.pagehide();
 f.pending[0].resolve({token:'late-detail',parts:[]});await request;
 assert.equal(f.pending.filter(p=>p.url==='/api/reading-explain').length,0);
 assert.equal(f.elements.get('deepText').children.length,0);
});
test('history summarizes one visible page in one call and details only the clicked section',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("taskSummaryBox").open=true;$("pastPanel").hidden=false');
 const request=f.run('loadPast(42,21)');assert.deepEqual(JSON.parse(f.pending[0].options.body),{grant:'page-only',snapshot:42,before:21});
 f.pending[0].resolve({cards:[{id:'section1',title:'调整首页',stamp:1,detail_token:'only-this-section',parts:[{part:'work',title:'具体做了什么'}]}],token:'one-page',snapshot:42,next_before:10,has_more:true,note:'三段一页'});await tick();
 assert.equal(f.pending[1].url,'/api/reading-explain');assert.equal(JSON.parse(f.pending[1].options.body).token,'one-page');
 f.pending[1].resolve({result:{mode:'model',explanations:[{part:'section1',text:'助手汇报调整了首页。',evidence_ids:[]}]},references:[]});await request;
 assert.equal(f.elements.get('pastText').children[0].children[2].textContent,'助手汇报调整了首页。');
 const detail=f.run('loadPastDetail(pastPage.cards[0],$("fakeButton"),$("fakeBox"))'); // Initially open: just fold it.
 await detail;f.run('$("fakeBox").hidden=true');const open=f.run('loadPastDetail(pastPage.cards[0],$("fakeButton"),$("fakeBox"))');
 assert.equal(JSON.parse(f.pending[2].options.body).token,'only-this-section');
 f.pending[2].resolve({result:{mode:'model',explanations:[{part:'work',text:'收起了复杂的记录。',evidence_ids:[]}]},references:[]});await open;
 assert.equal(f.elements.get('fakeBox').children[0].children[1].textContent,'收起了复杂的记录。');
});
test('a second reading click cannot unlock an in-flight reading request',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("deepPanel").hidden=false;$("taskSummaryBox").open=true;$("pastPanel").hidden=false');
 const request=f.run('loadDeep()');await f.run('loadPast()');assert.equal(f.run('readingBusy'),true);assert.equal(f.pending.length,1);
 f.listeners.pagehide();f.pending[0].resolve({token:'late',parts:[]});await request;
});
test('a slow detailed explanation keeps its page lease alive without starting a competing model call',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";readingBusy=true');const request=f.run('automatic()');
 assert.equal(f.pending[0].url,'/api/glance-heartbeat');f.pending[0].resolve({alive:true});await request;
 assert.equal(f.pending.length,1);assert.equal(f.run('readingBusy'),true);
});
test('closing while a reading call waits for the shared cooldown cancels its next send',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("deepPanel").hidden=false');
 const request=f.run('readingModel("one-detail",readingEpoch,"deepPanel",$("deepNote"))');
 f.pending[0].resolve({error:'稍后再试',reason:'rate_limited'},409);await tick();assert.equal(f.timers.length,1);
 f.listeners.pagehide();f.timers[0]();await request;
 assert.equal(f.pending.filter(p=>p.url==='/api/reading-explain').length,1);
});
test('folding a history segment during cooldown cancels its retry while the history page stays open',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("taskSummaryBox").open=true;$("pastPanel").hidden=false;$("segmentBox").hidden=true');
 f.context.segment={detail_token:'one-segment',parts:[],local:[],references:[]};
 const request=f.run('loadPastDetail(segment,$("segmentButton"),$("segmentBox"))');
 f.pending[0].resolve({error:'稍后再试',reason:'rate_limited'},409);await tick();
 await f.run('loadPastDetail(segment,$("segmentButton"),$("segmentBox"))');f.timers[0]();await request;
 assert.equal(f.pending.length,1);assert.equal(f.run('readingBusy'),false);
});
test('history uses its dedicated subject title and preserves both names after a comma',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("taskSummaryBox").open=true;$("pastPanel").hidden=false');const request=f.run('loadPast()');
 f.pending[0].resolve({cards:[{id:'section1',title:'两个按钮',stamp:1,detail_token:'section-detail',parts:[]}],token:'page',snapshot:1,next_before:0,has_more:false,note:'三段一页'});await tick();
 f.pending[1].resolve({result:{mode:'model',explanations:[{part:'section1',title:'新增“深入解释”和“之前做了什么”入口',text:'用户要求新增两个入口，名称是“深入解释”和“之前做了什么”。',evidence_ids:[]}]},references:[]});await request;
 assert.equal(f.elements.get('pastText').children[0].children[0].textContent,'新增“深入解释”和“之前做了什么”入口');
});
test('provider changes persist before a new automatic explanation can start',async()=>{
 const f=setup();f.run('model={provider:"auto",automatic_on_open:false};$("explanationProvider").value="claude"');
 const change=f.run('setExplanationProvider(true)');assert.equal(f.pending[0].url,'/api/explanation-settings');
 assert.deepEqual(JSON.parse(f.pending[0].options.body),{provider:'claude',automatic_on_open:true});
 assert.equal(f.pending.length,1);f.pending[0].resolve({provider:'claude',automatic_on_open:true,providers:[]});await change;
 assert.equal(f.run('model.provider'),'claude');assert.equal(f.run('grant'),null);
});
test('changing the provider dropdown saves immediately and survives a fresh page',async()=>{
 const f=setup();f.run('model={provider:"claude",automatic_on_open:true};renderProviderSettings();$("explanationProvider").value="codex"');
 assert.equal(typeof f.elements.get('explanationProvider').onchange,'function');
 const change=f.elements.get('explanationProvider').onchange();
 assert.deepEqual(JSON.parse(f.pending[0].options.body),{provider:'codex',automatic_on_open:true});
 assert.equal(f.elements.get('explanationProvider').disabled,true);
 const saved={provider:'codex',automatic_on_open:true,providers:[]};f.pending[0].resolve(saved);await change;
 assert.equal(f.run('model.provider'),'codex');assert.equal(f.elements.get('explanationProvider').value,'codex');
 const reopened=setup({clientRequests:true});reopened.pending[0].resolve({explanation:saved});await tick();
 assert.equal(reopened.elements.get('explanationProvider').value,'codex');
});
test('selecting a provider while explanation is off saves without enabling or checking it',async()=>{
 const f=setup();f.run('model={provider:"claude",automatic_on_open:false};$("explanationProvider").value="codex"');
 assert.equal(typeof f.elements.get('explanationProvider').onchange,'function');
 const change=f.elements.get('explanationProvider').onchange();
 assert.deepEqual(JSON.parse(f.pending[0].options.body),{provider:'codex',automatic_on_open:false});
 f.pending[0].resolve({provider:'codex',automatic_on_open:false,providers:[]});await change;
 assert.equal(f.run('model.automatic_on_open'),false);assert.equal(f.pending.length,1);
});
test('failed provider saves show the active provider and the failure, with no new explanation',async()=>{
 const f=setup();f.run('model={provider:"claude",automatic_on_open:true};$("explanationProvider").value="codex"');
 const change=f.run('setExplanationProvider(true)');f.pending[0].resolve({error:'请登录 Codex。'},409);await change;
 assert.equal(f.elements.get('explanationProvider').value,'claude');assert.equal(f.run('model.provider'),'claude');
 assert.match(f.elements.get('providerNote').textContent,/未保存.*请登录 Codex/);assert.equal(f.pending.length,1);
});
test('a busy explanation rejects a provider change visibly instead of leaving an unsaved selection',async()=>{
 const f=setup();f.run('model={provider:"claude",automatic_on_open:true};workInFlight=true;$("explanationProvider").value="codex"');
 const change=f.run('setExplanationProvider(true)');
 assert.equal(f.pending.length,0);await change;assert.equal(f.elements.get('explanationProvider').value,'claude');
 assert.match(f.elements.get('providerNote').textContent,/尚未保存/);
});
test('provider saving suppresses overlapping settings and automatic model requests',async()=>{
 const f=setup();enabledPage(f);f.run('model.provider="claude";$("explanationProvider").value="codex"');
 const change=f.run('setExplanationProvider(true)');f.run('automatic()');f.run('setExplanationProvider(true)');
 assert.equal(f.pending.length,1);
 f.pending[0].resolve({provider:'codex',automatic_on_open:true,providers:[]});await change;await tick();
 assert.equal(f.pending[1].url,'/api/glance-preview');
});
test('stop remains usable while an automatic explanation is in flight',async()=>{
 const f=setup();f.run('model={provider:"codex",automatic_on_open:true};autoRun={};grant="old";$("explanationProvider").value="claude"');
 const stop=f.run('setExplanationProvider(false)');assert.deepEqual(JSON.parse(f.pending[0].options.body),{provider:'codex',automatic_on_open:false});
 f.pending[0].resolve({provider:'codex',automatic_on_open:false,providers:[]});await stop;
 assert.equal(f.run('model.automatic_on_open'),false);assert.equal(f.run('grant'),null);assert.equal(f.run('autoRun'),null);
});
test('a recipient changed by another page cannot inherit this page sending grant',async()=>{
 const f=setup();enabledPage(f);f.run('model.destination="agent://codex"');
 const run=f.run('automatic()');f.pending[0].resolve({token:'preview',destination:'agent://claude'});await run;
 assert.equal(f.pending.length,1);assert.equal(f.run('model.automatic_on_open'),false);
});

// Reproduce an empty installation, including the asynchronous recorder status.
test('a fresh empty workbench shows source status and rejects late empty responses',async()=>{
 const f=setup({clientRequests:true});
 // Startup is left pending; drive the refresh independently.
 const request=f.run('refresh(true)');
 f.pending.find(r=>r.url==='/api/current').resolve({cards:[]});await tick();
 const clients=f.pending.filter(r=>r.url==='/api/clients');
 clients.at(-1).resolve({clients:[{id:'codex',recorder:{state:'source_unavailable'}}]});
 await request;assert.match(f.elements.get('emptyClients').children[0].textContent,/Codex.*暂时没读到/);
 const second=f.run('refresh(true)');
 f.pending.filter(r=>r.url==='/api/current').at(-1).resolve({cards:[]});await tick();
 f.run('epoch++;$("emptyClients").replaceChildren()');
 f.pending.filter(r=>r.url==='/api/clients').at(-1).resolve({clients:[{id:'claude',recorder:{state:'source_unavailable'}}]});
 await second;assert.equal(f.elements.get('emptyClients').children.length,0);
});
