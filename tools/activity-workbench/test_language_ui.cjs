const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'dist'),words=JSON.parse(fs.readFileSync(path.join(root,'en.json'),'utf8'));
function page(language,search=''){
 const nodes=['内容','解释','原因','深入解释','之前做了什么'].map(textContent=>({textContent,parentElement:{tagName:'SPAN'}}));
 let index=-1;const walker={nextNode(){index++;this.currentNode=nodes[index];return index<nodes.length;}};
 const links=['/','/history','https://example.com'].map(href=>({href,getAttribute(){return this.href;},setAttribute(key,value){this.href=value;}}));
 const document={body:{},title:'雪绪 · 当前工作',documentElement:{},createTreeWalker:()=>walker,querySelectorAll:s=>s==='a[href]'?links:[]};
 const context=vm.createContext({document,navigator:{languages:[language]},location:{search,href:'http://localhost:8767/'+search},URL,URLSearchParams,NodeFilter:{SHOW_TEXT:4},YukioEnglish:words});
 vm.runInContext(fs.readFileSync(path.join(root,'i18n.js'),'utf8'),context);
 return {context,document,nodes,links};
}
test('the system language selects English text and headings without a new switch',()=>{
 const p=page('en-GB');assert.equal(p.document.documentElement.lang,'en');
 assert.deepEqual(p.nodes.map(n=>n.textContent),['What is happening','What this means','Why it matters','More detail','Earlier work']);
 assert.equal(p.document.title,'Yukio · Current Work');
 assert.deepEqual(p.links.map(l=>l.href),['/?lang=en','/history?lang=en','https://example.com']);
});
test('the native preferred language takes precedence over a different web language',()=>{
 const p=page('en-US','?client=codex&key=chat&lang=zh');assert.equal(p.document.documentElement.lang,'zh-CN');
 assert.equal(p.nodes[0].textContent,'内容');assert.equal(p.context.YukioI18n.language,'zh');
});
test('Chinese variants use Chinese, other unsupported system languages fall back to English',()=>{
 assert.equal(page('zh-Hant-TW').nodes[0].textContent,'内容');assert.equal(page('fr-FR').nodes[0].textContent,'What is happening');
});
test('all translated home UI literals have an English entry',()=>{
 const source=fs.readFileSync(path.join(root,'glance.js'),'utf8');
 const literals=[...source.matchAll(/tr\((['"])((?:\\.|(?!\1)[^\n])*?)\1\)/g)].map(m=>m[2]);
 const missing=literals.filter(s=>/[\u4e00-\u9fff]/.test(s)&&!words[s]);assert.deepEqual(missing,[]);
 assert.match(source,/'X-Yukio-Language':uiLanguage/);
 assert.match(source,/lang:uiLanguage/);
 assert.doesNotMatch(source,/ref\.label\+' · '\+ref\.id/);
});
test('history, explanation and handoff controls all have English translations',()=>{
 for(const name of ['app.js','context.js','explanation.js']){
  const source=fs.readFileSync(path.join(root,name),'utf8');
  const labels=[...source.matchAll(/tr\((['"])((?:\\.|(?!\1)[^\n])*?)\1\)/g)].map(m=>m[2]);
  assert.deepEqual(labels.filter(s=>/[\u3400-\u9fff]/.test(s)&&!words[s]),[],name);
 }
 for(const [key,value] of Object.entries(words))assert.doesNotMatch(value,/[\u3400-\u9fff]/,key);
});
test('history send previews describe the chosen agent or LAN service accurately',async()=>{
 for(const provider of ['auto','codex','claude','lan']){
  function element(tag){return {tag,children:[],listeners:{},textContent:'',append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},addEventListener(name,listener){this.listeners[name]=listener;}};}
  const status=element('p'),document={createElement:element,getElementById:()=>status};
  const context=vm.createContext({document,window:{},fetch:async()=>({ok:true,json:async()=>({payload:{scope:{},facts:[]},excluded:'Short excerpts only'})})});
  vm.runInContext(fs.readFileSync(path.join(root,'explanation.js'),'utf8'),context);
  const api=context.window.YukioExplanation;
  api.configure({configured:true,provider,model:provider==='lan'?'Selected LAN model':provider==='auto'?'My agent':provider,max_calls_per_hour:20});
  const controls=api.controls({client:'codex',key:'chat',sequence:1});
  await controls.children[0].listeners.click();
  const content=node=>node.textContent+' '+node.children.map(content).join(' ');
  const text=status.textContent+' '+content(controls);
  assert.doesNotMatch(text,/千问|Qwen/);
  assert.match(text,/解释交给/);
  if(provider==='lan'){assert.match(text,/内网接口没有鉴权/);assert.doesNotMatch(text,/账号额度/);}
  else{assert.match(text,/该 Agent 的服务和账号额度/);assert.doesNotMatch(text,/内网模型|没有鉴权/);}
 }
});
