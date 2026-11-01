const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.hidden=false;this.textContent='';}
 append(...items){this.children.push(...items);}
 setAttribute(){}
 focus(){this.focused=true;}
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function setup({native=false,clipboard}={}){
 const root=new Element('div'),requests=[],messages=[];
 const window={...(native?{webkit:{messageHandlers:{yukio:{postMessage:m=>messages.push(m)}}}}:{})};
 const ctx=vm.createContext({window,document:{createElement:t=>new Element(t)},navigator:{clipboard},Map});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/agent-setup.js'),'utf8'),ctx);
 const api=(route,body)=>new Promise((resolve,reject)=>requests.push({route,body,resolve,reject}));
 const controller=window.YukioAgentSetup.mount({root,api,tr:s=>s});
 const card=p=>{const box=root.children[p==='codex'?0:1];return {box,status:box.children[1],check:box.children[2].children[0],guide:box.children[2].children[1],login:box.children[3],code:box.children[3].children[0],actions:box.children[3].children[1],note:box.children[3].children[2]};};
 return {root,requests,messages,card,controller};
}
test('opening setup only inventories; parallel assistant responses stay on their own cards',async()=>{
 const s=setup();assert.deepEqual(s.requests.map(r=>r.route),['agent-status']);
 const a=s.controller.check('codex'),b=s.controller.check('claude');
 assert.equal(s.requests[1].body.provider,'codex');assert.equal(s.requests[2].body.provider,'claude');
 s.requests[2].resolve({provider:'claude',state:'login_required',login_command:"'/路径 有空格/claude' auth login"});await b;
 s.requests[1].resolve({provider:'codex',state:'ready'});await a;
 s.requests[0].resolve({agents:[{provider:'codex',state:'not_found'},{provider:'claude',state:'not_found'}]});await settle();
 assert.equal(s.card('codex').box.dataset.state,'ready');assert.equal(s.card('claude').box.dataset.state,'login_required');
 assert.equal(s.card('codex').login.hidden,true);assert.match(s.card('claude').code.textContent,/auth login$/);
 assert.equal(s.requests.length,3);
});
test('retry hides an old login command and unsupported or unknown status offers none',async()=>{
 const s=setup();s.requests[0].resolve({agents:[]});
 let p=s.controller.check('claude');s.requests[1].resolve({provider:'claude',state:'login_required',login_command:'claude auth login'});await p;
 p=s.controller.check('claude');assert.equal(s.card('claude').login.hidden,true);assert.equal(s.card('claude').code.textContent,'');
 s.requests[2].resolve({provider:'claude',state:'unverified'});await p;assert.equal(s.card('claude').login.hidden,true);
 p=s.controller.check('claude');s.requests[3].resolve({provider:'codex',state:'ready'});await p;assert.equal(s.card('claude').box.dataset.state,'check_failed');
});
test('manual copy fallback remains usable and native action can only open Terminal',async()=>{
 const s=setup({native:true});s.requests[0].resolve({agents:[]});
 const p=s.controller.check('codex');s.requests[1].resolve({provider:'codex',state:'login_required',login_command:'codex login'});await p;
 await s.card('codex').actions.children[0].onclick();assert.match(s.card('codex').note.textContent,/手动复制/);assert.equal(s.card('codex').code.focused,true);
 s.card('codex').actions.children[1].onclick();assert.deepEqual(s.messages,['terminal']);
 assert.equal(s.card('codex').guide.href,'https://learn.chatgpt.com/docs/cli');assert.equal(s.card('claude').guide.href,'https://code.claude.com/docs/en/setup');
});
test('auto checks both providers when needed, explicit choice never checks the other',async()=>{
 const s=setup();s.requests[0].resolve({agents:[]});
 let p=s.controller.available('auto','claude');assert.equal(s.requests[1].body.provider,'claude');s.requests[1].resolve({provider:'claude',state:'not_found'});await settle();
 assert.equal(s.requests[2].body.provider,'codex');s.requests[2].resolve({provider:'codex',state:'ready'});assert.equal(await p,true);
 p=s.controller.available('claude','codex');s.requests[3].resolve({provider:'claude',state:'login_required'});assert.equal(await p,false);assert.equal(s.requests.length,4);
});
