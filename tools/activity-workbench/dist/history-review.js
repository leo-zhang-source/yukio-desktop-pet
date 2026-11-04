'use strict';
// History readings are frozen on demand. Polling never rewrites an open recap.
let reviewEpoch=0,reviewLock=null;
const reviews={overview:{},steps:{}};
const reviewIDs={overview:{fold:'taskSummaryBox',body:'taskSummary',note:'overviewNote',button:'overviewGenerate'},steps:{fold:'detailsBox',body:'reviewSteps',note:'stepsNote',button:'stepsGenerate'}};
function resetHistoryReview(){
 reviewEpoch++;reviewLock=null;
 for(const section of ['overview','steps']){reviews[section]={};const ids=reviewIDs[section];$(ids.fold).open=false;$(ids.body).replaceChildren();$(ids.note).textContent='';}
 $('stepsOlder').hidden=true;$('stepsNewer').hidden=true;
}
function reviewProof(refs){
 const detail=make('details');detail.className='review-proof';detail.append(make('summary',tr('查看依据')));
 for(const ref of refs)detail.append(make('blockquote',ref.title+tr('：')+ref.quote));
 if(!refs.length)detail.append(make('p',tr('没有足够的可读依据。')));return detail;
}
function reviewHint(){return model?.automatic_on_open?tr('点击生成，用所选解释来源讲清这段工作。'):tr('请先开启上方的解释来源，再生成通俗解读。');}
function drawReview(section){
 const state=reviews[section],data=state.data,ids=reviewIDs[section];if(!data)return;
 const box=$(ids.body);box.replaceChildren();state.nodes={};state.details={};
 for(const part of data.parts){
  const item=data.items?.find(i=>i.part===part.part),row=make('section');row.className='review-entry '+(item?'review-step':'review-paragraph');
  if(!item)row.append(make('h3',tr(part.title)));
  const answer=state.answer?.result.explanations.find(i=>i.part===part.part),prose=make('p',answer?.text||(item?tr(item.title):tr('等待模型解读')));
  prose.className='review-prose'+(answer?'':' review-pending');row.append(prose);
  if(item){const meta=make('p');meta.className='review-tool';meta.append(make('span',item.kind==='report'?tr('公开进展说明'):item.kind==='handoff'?tr('助手交接'):tr('使用工具')));
   if(item.tool)meta.append(make('span',item.tool));meta.append(make('span',tr(item.status)));row.append(meta);}
  const detail=make('details');detail.className='review-detail';detail.dataset.part=part.part;
  detail.append(make('summary',tr('详细解释')));
  const detailBody=make('div'),status=make('p',reviewHint()),long=make('div'),retry=make('button',tr('现场生成详细解释'));
  status.className='review-note';status.setAttribute('role','status');retry.type='button';
  detailBody.append(status,long,retry);detail.append(detailBody);row.append(detail);
  const refs=(state.answer?.references||data.references).filter(r=>(answer?.evidence_ids||part.allowed).includes(r.evidence_id));row.append(reviewProof(refs));
  state.nodes[part.part]=prose;state.details[part.part]={element:detail,status,body:long,button:retry};
  detail.addEventListener('toggle',()=>{if(detail.open&&!long.children.length)void generateReview(section,part.part);});
  retry.onclick=()=>generateReview(section,part.part);box.append(row);
 }
 if(!data.parts.length)box.append(make('p',tr('这一页还没有可读取的公开步骤。')));
 if(section==='steps'){$('stepsOlder').hidden=!data.has_more;$('stepsNewer').hidden=!state.before;}
}
async function loadReview(section,snapshot=0,before=0){
 if(!selected)return;const ids=reviewIDs[section],prior=reviews[section];if(prior.loading)return;
 const own=reviewEpoch,selection=JSON.stringify(selected),state={loading:true,before};reviews[section]=state;
 const active=()=>own===reviewEpoch&&reviews[section]===state&&selection===JSON.stringify(selected)&&$(ids.fold).open&&!pageClosed;
 $(ids.note).textContent=tr('正在整理这部分记录…');$(ids.button).disabled=true;
 try{
  const data=await api('history-review?'+new URLSearchParams({...selected,section,snapshot,before}));if(!active())return;
  state.data=data;drawReview(section);$(ids.note).textContent=data.note+' '+reviewHint();
 }catch(error){if(active())$(ids.note).textContent=error.message;}
 finally{state.loading=false;if(active())$(ids.button).disabled=false;}
 if(active()&&state.data?.parts.length&&model?.automatic_on_open&&grant&&!readingBusy&&!workInFlight&&!autoRun)void generateReview(section);
}
async function generateReview(section,part=null){
 const ids=reviewIDs[section],state=reviews[section];if(!state.data){return loadReview(section);}
 const detail=part?state.details[part]:null,status=detail?.status||$(ids.note),button=detail?.button||$(ids.button);
 if(!model?.automatic_on_open){status.textContent=reviewHint();return;}
 if(!grant){status.textContent=tr('解释来源正在准备，请稍后点击生成。');void automatic();return;}
 if(readingBusy||workInFlight||autoRun){status.textContent=tr('另一段说明正在生成，完成后可点击重试。');return;}
 const own=reviewEpoch,selection=JSON.stringify(selected),token=grant,lock={};reviewLock=lock;readingBusy=true;button.disabled=true;
 const active=()=>own===reviewEpoch&&reviews[section]===state&&selection===JSON.stringify(selected)&&grant===token&&!pageClosed&&$(ids.fold).open&&(!detail||detail.element.open);
 status.textContent=tr('正在用所选来源生成通俗解释…');
 try{
  const frozen=await api('reading-review',{grant:token,section,...(section==='steps'?{snapshot:state.data.snapshot,before:state.before}:{}),...(part?{part}:{})});if(!active())return;
  if(!frozen.token){status.textContent=tr('这一页还没有可读取的公开步骤。');return;}
  let answer;
  for(let attempt=0;attempt<2;attempt++){
   if(!active())return;
   try{answer=await api('reading-explain',{grant:token,token:frozen.token});break;}
   catch(error){if(!attempt&&['rate_limited','busy'].includes(error.reason)){status.textContent=tr('模型刚处理过一段说明，稍等片刻就继续…');await new Promise(resolve=>setTimeout(resolve,11000));}else throw error;}
  }
  if(!active())return;
  if(answer.result.mode!=='model')throw Error(answer.result.message||tr('解释暂未生成，请稍后重试。'));
  if(detail){detail.body.replaceChildren();for(const item of answer.result.explanations)detail.body.append(make('p',item.text));detail.body.append(reviewProof(answer.references));detail.button.textContent=tr('重新生成详细解释');}
  else{state.data=frozen;state.answer=answer;drawReview(section);$(ids.button).textContent=tr('重新生成概括');}
  status.textContent=tr('由所选来源解释 · 基于本次展开的记录。')+' '+(detail?'':state.data.note);
 }catch(error){if(active())status.textContent=error.message;}
 finally{if(reviewLock===lock){reviewLock=null;readingBusy=false;}if(own===reviewEpoch)button.disabled=false;}
}
for(const section of ['overview','steps']){
 const ids=reviewIDs[section];$(ids.fold).addEventListener('toggle',()=>{if($(ids.fold).open&&!reviews[section].data)void loadReview(section);});
 $(ids.button).onclick=()=>generateReview(section);
}
$('stepsOlder').onclick=()=>{const state=reviews.steps;void loadReview('steps',state.data.snapshot,state.data.next_before);};
$('stepsNewer').onclick=()=>loadReview('steps');
