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
function setup(){
 const elements=new Map(),pending=[],listeners={},timers=[];const document={activeElement:null,hidden:false,createElement:tag=>new Element(tag),getElementById:id=>{if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id);}};
 const context=vm.createContext({document,location:{search:''},URLSearchParams,AbortSignal,atob,setInterval(){},setTimeout(fn){timers.push(fn);},window:{addEventListener(name,fn){listeners[name]=fn;}},fetch:async (url,options)=>{
  if(url==='/api/clients')return new Promise(()=>{}); // Leave page startup out of the focused polling test.
  return new Promise(resolve=>pending.push({url,options,resolve:(value,status=200)=>resolve({ok:status<400,json:async()=>value})}));
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/glance.js'),'utf8'),context);
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
test('overlapping polls share one request and a switched chat rejects the old reply',async()=>{
 const f=setup();f.run('selected={client:"codex",key:"chat-a"}');const request=f.run('loadTaskSummary()');
 await f.run('loadTaskSummary()');assert.equal(f.pending.length,1);
 f.run('selected={client:"codex",key:"chat-b"};summaryEpoch++');f.pending[0].resolve({goal:{text:'FOREIGN'}});await request;
 assert.equal(f.document.getElementById('taskSummary').children.length,0);
 const next=f.run('loadTaskSummary()');assert.equal(f.pending.length,2);f.pending[1].resolve({goal:{text:'CURRENT'},before:[],now:{text:'checking'},outcomes:[],next:{text:'later'},handoffs:[],limits:[]});await next;
 assert.ok(f.document.getElementById('taskSummary').children.length>0);
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
test('projects precede recent chats and states remain markers instead of categories',()=>{
 const f=setup();f.context.cards=[{client:'codex',key:'a',title:'雪绪首页',project:{id:'p',name:'Yukio'},activity_state:'working'},
 {client:'claude',key:'b',title:'检查图片',project:{id:'q',name:'封面设计'},activity_state:'inactive'},
 {client:'codex',key:'c',title:'之前的工作',activity_state:'unknown'},
 {client:'codex',key:'d',title:'需要回答',activity_state:'waiting'}];
 f.run('selected={client:"codex",key:"a"};chatCatalog=cards;renderChatNavigation()');
 const list=f.elements.get('chatLists');assert.deepEqual(list.children.filter(c=>c.tag==='h2').map(c=>c.textContent),['项目','最近聊天']);
 const rows=list.children.filter(c=>c.className?.startsWith('chat-row'));
 assert.equal(rows.length,4);assert.deepEqual(rows.map(c=>c.children[1].children[0].className),['chat-state working','chat-state inactive','chat-state unknown','chat-state waiting']);
 assert.equal(f.elements.has('filterWorking'),false);assert.equal(f.elements.has('filterInactive'),false);
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');assert.doesNotMatch(html,/id="filter(?:Recent|Working|Inactive)"|按工作状态查看/);
 assert.equal(f.run('filteredChats(cards,"yukio")[0].key'),'a');assert.equal(f.run('filteredChats(cards,"claude")[0].key'),'b');
 f.run('chatSearch="图片";renderChatNavigation()');assert.equal(f.run('selected.key'),'a');assert.equal(f.pending.length,0);
});
test('project navigation uses identity instead of joining same named projects',()=>{
 const f=setup();f.context.cards=[{client:'codex',key:'a',project:{id:'one',name:'App'}},{client:'codex',key:'b',project:{id:'two',name:'App'}}];
 assert.equal(f.run('projectGroups(cards).length'),2);
 const html=fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');
 assert.match(html,/id="chat" hidden aria-hidden="true"/);assert.match(html,/id="chatSearch"/);
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
 const f=setup();enabledPage(f);f.run('grant="page-only";$("pastPanel").hidden=false');
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
 const f=setup();enabledPage(f);f.run('grant="page-only";$("deepPanel").hidden=false;$("pastPanel").hidden=false');
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
test('history uses its dedicated subject title and preserves both names after a comma',async()=>{
 const f=setup();enabledPage(f);f.run('grant="page-only";$("pastPanel").hidden=false');const request=f.run('loadPast()');
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
