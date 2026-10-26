'use strict';
(() => {
 const query=new URLSearchParams(location.search);
 const requested=query.get('lang')||globalThis.navigator?.languages?.[0]||globalThis.navigator?.language||'zh';
 const language=String(requested).toLowerCase().startsWith('zh')?'zh':'en';
 const words=globalThis.YukioEnglish||{};
 const t=value=>language==='en'&&typeof value==='string'?(words[value]??value):value;
 const apply=()=>{
  document.documentElement.lang=language==='zh'?'zh-CN':'en';
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){
   const node=walker.currentNode;
   if(['SCRIPT','STYLE'].includes(node.parentElement?.tagName))continue;
   const trimmed=node.textContent.trim();
   if(words[trimmed])node.textContent=node.textContent.replace(trimmed,t(trimmed));
  }
  document.title=t(document.title);
  for(const node of document.querySelectorAll('[aria-label],[placeholder],[title]'))
   for(const key of ['aria-label','placeholder','title'])if(node.hasAttribute(key))node.setAttribute(key,t(node.getAttribute(key)));
 };
 globalThis.YukioI18n={language,t,apply};
 apply();
})();
