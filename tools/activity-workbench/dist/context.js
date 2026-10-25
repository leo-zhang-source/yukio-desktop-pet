'use strict';
window.YukioContext = (() => {
  let generation=0;
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  async function get(route,args){const r=await fetch('/api/'+route+'?'+new URLSearchParams(args),{headers:{'X-Yukio-Workbench':'1'},cache:'no-store'});if(!r.ok)throw new Error('暂时无法整理这份记录，请刷新重试。原历史仍然保留。');return r.json();}
  function proof(value){const d=node('details');d.append(node('summary','查看对应依据'));const dl=node('dl');for(const key of ['event_id','evidence_id','sequence','call_id','turn_id','request_evidence_id','association','outcome','source_line'])if(value[key]!==undefined){const labels={event_id:'来源记录',evidence_id:'内容依据',sequence:'保存顺序',call_id:'操作编号',turn_id:'轮次编号',request_evidence_id:'对应请求',association:'客户端对应标记',outcome:'结果标记',source_line:'原记录行号'};dl.append(node('dt',labels[key]),node('dd',String(value[key])));}d.append(dl);return d;}
  function clear(){generation++;document.getElementById('contextPanel')?.remove();}
  async function load(selection,navigate){
    clear();const own=generation;
    const panel=node('section',undefined,'context-panel');panel.id='contextPanel';panel.setAttribute('aria-label','已观察到的工作概况');
    document.getElementById('notices').after(panel);panel.append(node('p','正在整理请求和结果…'));
    try{
      const data=await get('context',selection);if(own!==generation)return;
      selection={...selection,snapshot:data.snapshot};panel.replaceChildren(node('h3','这份记录里，看到了什么'));
      panel.append(node('p',data.scope_note,'hint'),node('p','读取范围：保存 #'+data.window_start+'—#'+data.window_end+' · '+data.counts.records+' 条记录。'+(data.window_limited?'已到本次读取上限，更早或更多内容请在时间线查看。':''),'hint'));
      const metrics=node('div',undefined,'context-metrics');
      for(const [key,label] of [['succeeded','收到成功回执'],['failed','收到失败回执'],['cancelled','收到取消回执'],['no_receipt','尚无可配对回执'],['conflict','回执有冲突'],['unresolved','对应有疑问'],['unknown','结果不明确']])metrics.append(node('div',label+' '+(data.status_counts[key]||0)));
      panel.append(metrics);
      if(data.latest_marker)panel.append(node('p','最后观察到的阶段标记：'+data.latest_marker.title+'。'+data.latest_marker.note),proof(data.latest_marker.evidence));
      if(data.source_warning_count||data.unlinked_receipt_count)panel.append(node('p','本次范围有 '+data.source_warning_count+' 条来源提醒、'+data.unlinked_receipt_count+' 条无法配对的回执。请保留这些不确定。','notice'));
      if(data.earlier_gap_reported)panel.append(node('p','记录报告前方存在缺口，即使缺口不在本次范围内，也不能把经过当作完整。','notice'));
      panel.append(window.YukioExplanation.controls(selection,true));
      const list=node('details',undefined,'operation-list');list.append(node('summary','按操作看请求和结果'));
      const filter=node('select');filter.setAttribute('aria-label','筛选操作结果');for(const [v,label]of [['all','全部操作'],['attention','需要留意'],['no_receipt','未见可配对回执'],['succeeded','收到成功回执']]){const o=node('option',label);o.value=v;filter.append(o);}list.append(filter);
      const content=node('div'),more=node('button','查看更多操作');more.type='button';list.append(content,more);panel.append(list);
      let page=data,busy=false;
      function render(result,append){if(!append)content.replaceChildren();for(const op of result.operations){const c=node('article',undefined,'operation');c.append(node('h4',op.title),node('strong',op.status_label),node('p',op.note),proof(op.request));for(const r of op.receipts){const names={succeeded:'成功',failed:'失败',cancelled:'取消',unknown:'不明确'};c.append(node('p','收到回执：'+(names[r.outcome]||'不明确')+' · 保存 #'+r.sequence),proof(r));}if(op.receipt_count>op.receipts.length)c.append(node('p','共 '+op.receipt_count+' 条回执，这里显示前 10 条，其他回执保留在时间线。'));content.append(c);}if(!append&&!result.operations.length)content.append(node('p','这个范围中没有符合条件的操作。'));more.hidden=!result.has_more;page=result;}
      render(data,false);
      async function update(append){if(busy)return;busy=true;more.disabled=true;filter.disabled=true;try{const p=await get('context',{...selection,offset:append?page.next_offset:0,filter:filter.value});if(own===generation)render(p,append);}catch(e){if(own===generation)content.append(node('p',e.message));}finally{busy=false;more.disabled=false;filter.disabled=false;}}
      filter.onchange=()=>update(false);more.onclick=()=>update(true);
      if(data.unlinked_receipts.length){const d=node('details');d.append(node('summary','查看无法配对的回执（最多 10 条）'));for(const r of data.unlinked_receipts)d.append(proof(r));panel.append(d);}
      const links=node('details',undefined,'related-work');links.append(node('summary','查看有关联的助手和聊天'));const body=node('div');links.append(body);panel.append(links);let loaded=false;
      links.addEventListener('toggle',async()=>{if(!links.open||loaded)return;loaded=true;body.append(node('p','正在读取明确报告的关系…'));try{const result=await get('relations',selection);if(own!==generation)return;body.replaceChildren(node('p',result.note,'hint'));if(data.archived)body.append(node('p','你正在查看旧版；下列关系导航只列当前观察版本。','notice'));if(!result.items.length)body.append(node('p','尚未保存可以确认的关系。'));for(const item of result.items){const names={spawned_from:'助手创建关系',forked_from:'聊天分支关系',belongs_to_root:'主聊天归属',parent_thread:'上级聊天声明'};body.append(node('h4',names[item.relation.kind]||'客户端报告的关系'),node('p',item.relation.from_session_id+' → '+item.relation.to_session_id),proof(item.evidence));if(!item.targets.length)body.append(node('p','对应聊天尚未保存，暂时不能打开。'));for(const target of item.targets){const b=node('button','打开关联记录 · '+target.source_id.slice(0,8)+' · 助手 '+(target.agent_id||'未报告'));b.type='button';b.onclick=()=>navigate(target);body.append(b);}if(item.more_targets)body.append(node('p','这里只列前 10 份来源，请在会话列表继续查看。'));}if(result.has_more)body.append(node('p','这里只列最近 20 条关系声明。'));}catch(e){loaded=false;body.replaceChildren(node('p',e.message));}});
    }catch(e){if(own===generation)panel.replaceChildren(node('p',e.message,'notice'));}
  }
  return {clear,load};
})();
