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
 const elements=new Map(),pending=[];const document={activeElement:null,hidden:false,createElement:tag=>new Element(tag),getElementById:id=>{if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id);}};
 const context=vm.createContext({document,location:{search:''},URLSearchParams,AbortSignal,atob,setInterval(){},window:{addEventListener(){}},fetch:async url=>{
  if(url==='/api/clients')return new Promise(()=>{}); // Leave page startup out of the focused polling test.
  return new Promise(resolve=>pending.push({url,resolve:value=>resolve({ok:true,json:async()=>value})}));
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/glance.js'),'utf8'),context);
 return {context,document,elements,pending,run:code=>vm.runInContext(code,context)};
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
test('the entry names the selected chat explanation and clearly labels local text',()=>{
 const f=setup();f.context.data=currentWork();f.run('model={configured:true};render(data)');
 assert.equal(f.elements.get('explain').textContent,'让千问解释这段聊天');
 assert.match(f.elements.get('modelNote').textContent,/当前显示本机说明/);
 assert.match(f.elements.get('modelNote').textContent,/上方按钮/);
});
test('a model answer appears in the three parts and new work restores the local label',()=>{
 const f=setup();f.context.data=currentWork();f.run('model={configured:true};render(data)');
 f.context.result={mode:'model',explanations:['content','explanation','reason'].map(part=>({part,text:'模型'+part,basis:'inference',evidence_ids:[]}))};
 f.run('showAnswer(result,[],1,"r1")');assert.equal(f.elements.get('content').textContent,'模型content');
 assert.match(f.elements.get('modelNote').textContent,/当前显示千问说明/);
 f.context.data=currentWork('r2');f.run('render(data)');assert.equal(f.elements.get('content').textContent,'本机内容');
 assert.match(f.elements.get('modelNote').textContent,/当前显示本机说明/);
 assert.equal(f.elements.get('previousModel').hidden,false);
});
test('opening the explanation entry only previews and says where the result will appear',async()=>{
 const f=setup();f.run('selected={client:"codex",key:"chat-a"};model={configured:true}');const request=f.run('explain()');
 assert.equal(f.pending.length,1);assert.equal(f.pending[0].url,'/api/glance-preview');
 f.pending[0].resolve({model:'模拟模型',destination:'模拟地址',excluded:'模拟边界',payload:{facts:[]}});await request;
 const preview=f.elements.get('preview');assert.equal(preview.hidden,false);
 assert.ok(preview.children.some(n=>n.textContent.includes('本页的“内容、解释、原因”')));
 assert.equal(f.pending.length,1); // No model request until a specific send action.
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
 const f=setup();f.run('busy=true;modelAnswer={private:"old"};grant="old-grant";previewOpen=true');
 const next={client:'codex',key:chatKey('new',1,'chat-a')};f.context.next=next;
 const request=f.run('choose(JSON.stringify(next))');assert.equal(f.pending[0].url,'/api/glance-stop');
 f.pending[0].resolve({stopped:true});await request;
 assert.equal(f.run('grant'),null);assert.equal(f.run('modelAnswer'),null);assert.equal(f.run('previewOpen'),false);
 assert.equal(f.run('selected.key'),next.key);assert.equal(f.run('refreshAgain'),true);
});
