const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
class Element{
 constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.events={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 addEventListener(name,fn){this.events[name]=fn;}
 setAttribute(){}
 all(){return [this,...this.children.flatMap(c=>c.all())];}
}
function setup(language='zh'){
 const status=new Element('p'),calls=[],words=JSON.parse(fs.readFileSync(path.join(__dirname,'dist/en.json'),'utf8'));
 const preview={token:'frozen-token',recipient:{provider:'claude',model:'Claude Code',destination:'agent://claude'},excluded:'bounded',payload:{scope:{},facts:[]},references:[]};
 const context=vm.createContext({window:{},document:{getElementById:()=>status,createElement:tag=>new Element(tag)},YukioI18n:{language,t:value=>language==='en'?(words[value]??value):value},fetch:async(url,options)=>{
  calls.push({url,body:JSON.parse(options.body)});
  return {ok:!url.endsWith('generate'),json:async()=>url.endsWith('generate')?{error:'recipient changed'}:preview};
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'dist/explanation.js'),'utf8'),context);
 const api=context.window.YukioExplanation;api.configure({configured:true,provider:'auto',model:'Automatic',max_calls_per_hour:20});
 return {api,calls,preview,box:api.controls({client:'codex',key:'synthetic',sequence:1})};
}
for(const lang of ['zh','en'])test(`preview uses resolved recipient, not mutable settings (${lang})`,async()=>{
 const f=setup(lang);await f.box.children[0].events.click();
 assert.ok(f.box.all().some(e=>e.textContent.includes('Claude Code')));
 f.api.configure({configured:true,provider:'lan',model:'different',destination:'http://example.test',max_calls_per_hour:20});
 assert.ok(f.box.all().some(e=>e.textContent.includes('Claude Code')));
 const send=f.box.all().filter(e=>e.tag==='button')[1];
 assert.ok(send);await send.events.click();
 assert.deepEqual(f.calls[1].body,{token:'frozen-token',consent:true});
 assert.ok(f.box.all().some(e=>e.textContent==='recipient changed'));
 assert.ok(!f.box.all().some(e=>/内网千问/.test(e.textContent)));
});
test('cancel never sends and an unresolved recipient has no send button',async()=>{
 const f=setup();await f.box.children[0].events.click();
 f.box.all().find(e=>e.textContent==='暂不发送').events.click();
 assert.equal(f.calls.length,1);
 delete f.preview.recipient;await f.box.children[0].events.click();
 assert.equal(f.calls.length,2);
 assert.ok(!f.box.all().some(e=>e.textContent==='发送以上内容并生成说明'));
});
