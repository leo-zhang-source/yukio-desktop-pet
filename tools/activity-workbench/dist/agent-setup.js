'use strict';
// Each card owns its request and state. Checks never change explanation grants.
window.YukioAgentSetup={mount({root,api,tr,onState=()=>{}}){
 const cards=new Map();
 const labels={codex:'Codex',claude:'Claude Code'};
 const guides={codex:'https://learn.chatgpt.com/docs/cli',claude:'https://code.claude.com/docs/en/setup'};
 const messages={
  not_found:tr('还未找到助手。先按官方说明安装，再回来检查。'),
  not_checked:tr('已找到助手，尚未检查登录。'),
  checking:tr('正在检查版本和登录状态，不会发送聊天。'),
  ready:tr('已登录，版本支持解释。可在上方选择并开启。'),
  login_required:tr('还未登录。复制下面的命令，在这台电脑的终端粘贴并回车，按官方页面完成登录，再回来检查。'),
  incompatible:tr('当前版本不支持所需的解释方式，请按官方说明更新后重试。'),
  compatibility_timeout:tr('读取助手版本超时。请确认助手能正常打开，再重试。'),
  login_check_timeout:tr('检查登录状态超时。请先在助手中确认登录，再重试。'),
  unverified:tr('已找到兼容版本，但无法确认登录。可先在助手中登录；开启解释时会再次检查。'),
  check_failed:tr('暂时无法检查。请确认助手能正常打开，再重试。')
 };
 const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
 function render(card,result){
  card.result=result;
  card.status.textContent=messages[result.state]||messages.check_failed;
  card.box.dataset.state=result.state;
  card.login.hidden=result.state!=='login_required'||typeof result.login_command!=='string';
  card.code.textContent=card.login.hidden?'':result.login_command;
  card.copyNote.textContent='';onState(result);
 }
 async function check(provider){
  const card=cards.get(provider);if(card.pending)return card.pending;
  card.version++;card.button.disabled=true;render(card,{state:'checking'});
  card.pending=(async()=>{
   let result;
   try{result=await api('agent-check',{provider});if(result.provider!==provider)throw Error('Invalid assistant');}
   catch{result={provider,state:'check_failed'};}
   render(card,result);return result;
  })();
  try{return await card.pending;}finally{card.pending=null;card.button.disabled=false;}
 }
 for(const provider of ['codex','claude']){
  const box=make('section',null,'agent-card'),title=make('h4',labels[provider]),status=make('p',messages.not_checked,'set-note');
  const actions=make('div',null,'set-actions'),button=make('button',tr('检查安装与登录'),'btn'),guide=make('a',tr('官方安装与登录说明'),'btn-text');
  button.type='button';guide.href=guides[provider];guide.rel='noreferrer';actions.append(button,guide);status.setAttribute('role','status');
  const login=make('div',null,'agent-login'),code=make('code'),loginActions=make('div',null,'set-actions'),copy=make('button',tr('复制登录命令'),'btn'),copyNote=make('p',null,'set-note');
  code.tabIndex=0;copy.type='button';copyNote.setAttribute('role','status');login.hidden=true;loginActions.append(copy);
  if(window.webkit?.messageHandlers?.yukio){const terminal=make('button',tr('打开终端'),'btn');terminal.type='button';terminal.onclick=()=>window.webkit.messageHandlers.yukio.postMessage('terminal');loginActions.append(terminal);}
  login.append(code,loginActions,copyNote);box.append(title,status,actions,login);root.append(box);
  const card={box,status,button,login,code,copyNote,version:0,pending:null};cards.set(provider,card);
  button.onclick=()=>check(provider);
  copy.onclick=async()=>{const command=code.textContent;if(!command)return;try{await navigator.clipboard.writeText(command);if(code.textContent===command)copyNote.textContent=tr('已复制。在终端粘贴并回车，完成官方登录后回来检查。');}catch{if(code.textContent===command){copyNote.textContent=tr('无法自动复制，请选中上面的整行命令手动复制。');code.focus();}}};
 }
 const versions=new Map([...cards].map(([p,c])=>[p,c.version]));
 void api('agent-status').then(data=>{for(const result of data.agents||[]){const card=cards.get(result.provider);if(card&&card.version===versions.get(result.provider))render(card,result);}}).catch(()=>{for(const [p,c] of cards)if(c.version===versions.get(p))render(c,{state:'check_failed'});});
 return {check,async available(provider,client){
  if(provider==='lan')return true;
  const first=client==='claude'?'claude':'codex';
  const order=provider==='auto'?[first,first==='codex'?'claude':'codex']:[provider];
  for(const name of order){const result=await check(name);if(['ready','unverified'].includes(result.state))return true;}
  return false;
 }};
}};
