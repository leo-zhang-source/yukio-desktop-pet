'use strict';
var tr=globalThis.YukioI18n?.t||(value=>value);
var uiLanguage=globalThis.YukioI18n?.language||'zh';
// Opening or polling history never calls a model. Each card owns its preview.
window.YukioExplanation = (() => {
  let configuration = {configured: false};
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  async function post(route, body) {
    const response = await fetch('/api/' + route, {
      method: 'POST', cache: 'no-store',
      headers: {'Content-Type': 'application/json', 'X-Yukio-Workbench': '1', 'X-Yukio-Language':uiLanguage},
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || tr('暂时无法生成说明，请稍后重试。'));
    return data;
  }
  function configure(value) {
    configuration = value || {configured: false};
    const status = document.getElementById('modelStatus');
    status.textContent = configuration.configured
      ? tr('解释交给 ') + configuration.model + tr(' · 手动发送 · 每小时最多 ') + configuration.max_calls_per_hour + tr(' 次。配置就绪不代表服务一直在线。')
      : tr('尚未配置模型，仍可查看本机说明和依据。');
  }
  function controls(selection, contextual=false) {
    const box = node('section', undefined, 'explanation-control');
    if (!configuration.configured) return box;
    const start = node('button', contextual ? tr('让模型解释这段已观察记录') : tr('让模型解释这条记录'));
    start.type = 'button';
    const panel = node('div');
    box.append(start, panel);
    start.addEventListener('click', async () => {
      start.disabled = true;
      panel.replaceChildren(node('p', tr('正在准备发送预览，此时尚未调用模型。')));
      try {
        const preview = await post(contextual ? 'context-preview' : 'explanation-preview', selection);
        panel.replaceChildren();
        const review = node('div', undefined, 'send-preview');
        review.append(node('h4', tr('先看清楚会发送什么')));
        review.append(node('p', tr('解释交给 ') + configuration.model));
        review.append(node('p', preview.excluded));
        review.append(node('p', (contextual ? tr('只解释本次读取范围的统计和限制，不是完整任务总结。') : tr('只解释选中的一条已保存记录。')) +
          (preview.payload.scope.blocks_in_record ? tr('消息内共有 ') + preview.payload.scope.blocks_in_record + tr(' 项，本次仅发送前 ') + preview.payload.scope.blocks_included + tr(' 项。') : '') +
          (configuration.provider === 'lan'
            ? tr(' 发送后由你配置的内网模型处理；当前内网接口没有鉴权。')
            : tr(' 发送后由工作台所选的本机 Agent 处理，使用该 Agent 的服务和账号额度。自动模式会在发送前检查可用助手，实际来源显示在结果中。'))));
        for (const fact of preview.payload.facts) {
          review.append(node('p', '' +
            (fact.evidence_class === 'self_report' ? tr('自述存在标记：') : fact.evidence_class === 'rule_summary' ? tr('本机整理：') : tr('已观察标记：')) +
            fact.record_marker + '。' + fact.boundary));
        }
        const send = node('button', preview.cached ? tr('查看刚才的解释（不重复发送）') : tr('发送以上内容并生成说明'));
        send.type = 'button';
        const cancel = node('button', tr('暂不发送'));
        cancel.type = 'button';
        cancel.addEventListener('click', () => {panel.replaceChildren(); start.disabled = false;});
        review.append(send, cancel);
        panel.append(review);
        send.addEventListener('click', async () => {
          send.disabled = true; cancel.disabled = true;
          const pending = node('p', tr('正在生成说明…本机原记录仍可查看。'), 'model-pending');
          pending.setAttribute('role', 'status'); panel.append(pending);
          try {
            const result = await post('explanation-generate', {token: preview.token, consent: true});
            const answer = node('div', undefined, 'model-answer');
            answer.append(node('h4', result.mode === 'model' ? tr('模型解释 · ') + result.model : tr('本机说明 · 模型暂不可用')));
            answer.append(node('p', result.warning || result.message));
            if (result.cached) answer.append(node('p', tr('使用刚才的结果，没有重复调用模型。')));
            for (const item of result.explanations) {
              const paragraph = node('div', undefined, 'model-claim');
              paragraph.append(node('p', item.text));
              const ref = preview.references.find(r => r.evidence_id === item.evidence_id);
              const details = node('details');
              details.append(node('summary', tr('对应依据 ') + item.evidence_id));
              if (ref) details.append(node('p', ref.title + tr(' · 保存 #') + ref.sequence), node('p', tr('依据编号：') + ref.record_id));
              if (ref?.record_ids) {
                details.append(node('p',tr('关联依据共 ')+ref.total_references+tr(' 条，以下最多列出前 10 条；完整记录可在时间线查看。')));
                for (const id of ref.record_ids) details.append(node('p',id));
              }
              paragraph.append(details); answer.append(paragraph);
            }
            panel.replaceChildren(answer);
          } catch (error) {
            pending.textContent = error.message || tr('连接中断，原记录仍然保留。');
            send.disabled = false; cancel.disabled = false;
          } finally { start.disabled = false; }
        });
      } catch (error) {
        panel.replaceChildren(node('p', error.message || tr('无法准备预览，未发送任何活动。')));
        start.disabled = false;
      }
    });
    return box;
  }
  return {configure, controls};
})();
