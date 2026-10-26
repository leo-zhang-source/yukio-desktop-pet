"""Task recaps retain source boundaries, failed outcomes and recipient identity."""
import json
import http.client
import threading
import unittest
import test_glance
import test_handoffs
from task_summary import recap
from explanation import ExplanationError,validate_output,encode
from server import create_server
from urllib.parse import urlencode


class TaskSummaryTests(unittest.TestCase):
    def setUp(self):
        self.fx=test_glance.GlanceTests();self.fx.setUp()
    def tearDown(self):self.fx.tearDown()

    def test_quoted_example_keeps_framing_and_is_not_a_public_reason(self):
        from glance_view import progress_headline,public_reason
        note='例如“正在修复按钮。为了存下名称，先检查。”这只是模拟示例。'
        self.assertIn('模拟示例',progress_headline(note));self.assertIsNone(public_reason(dict(text=note)))

    def test_missing_result_cannot_become_a_stuck_or_off_topic_diagnosis(self):
        f=self.fx;_,payload,_=f.glance.prepared('codex',f.key)
        for text in ['当前卡在检查环节。','任务已经偏题。']:
            bad=test_glance.result(payload);bad[2]['text']=text
            with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
            self.assertEqual(exc.exception.code,'unsupported_diagnosis')

    def test_completed_milestone_does_not_hide_the_explicit_current_action(self):
        from glance_view import progress_headline
        f=self.fx;note='新版已装到 Mac。我正在核对历史有没有丢。为了保留之前的工作，先检查已有记录。'
        f.rows[3]['payload']['content'][0]['text']=note;f.rows=f.rows[:4];f.write();f.ingest();f.key=f.history.groups('codex')['groups'][0]['key']
        d=f.detail();self.assertEqual(d['content'],'我正在核对历史有没有丢。')
        self.assertIn('按助手的公开说明',d['explanation'])
        example='新版已完成。例如“我正在删除记录。”这只是例子。'
        self.assertEqual(progress_headline(example),'新版已完成。')

    def test_real_chat_overclaim_regressions_fall_back_but_uncertainty_is_allowed(self):
        f=self.fx;_,payload,_=f.glance.prepared('codex',f.key)
        for text in ['这确保解释可信。','这保证进度真实。','通过确认数据没丢，你能放心地根据这些记录判断AI的工作质量。']:
            bad=test_glance.result(payload);bad[2]['text']=text
            with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
            self.assertEqual(exc.exception.code,'unsupported_guarantee')
        good=test_glance.result(payload);good[2]['text']='核对记录数量不能保证解释可信，只能帮助发现旧记录有没有少。'
        self.assertEqual(validate_output(encode(dict(explanations=good)),payload),good)

    def test_summary_uses_earlier_goal_keeps_current_work_and_does_not_certify_completion(self):
        f=self.fx
        f.rows += [dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='已报告把按钮放到了首页，尚未检查保存功能。')])),
                   dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='接下来检查保存是否正常。')])),
                   dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我先检查保存按钮。')]))]
        f.write();f.ingest();d=f.glance.summary('codex',f.key)
        self.assertIn('简化首页',d['goal']['text']);self.assertIn('保存按钮',d['now']['text'])
        self.assertIn('尚未检查',d['before'][-1]['text']);self.assertEqual(d['before'][-1]['basis'],'assistant')
        self.assertEqual(d['whole_task_status'],'unknown');self.assertEqual(d['next']['basis'],'unknown')
        self.assertFalse(d['handoffs']);self.assertIn('不代表',d['handoff_empty'])

    def test_closed_turn_cannot_be_reported_as_still_working(self):
        f=self.fx
        for kind,state in [('task_complete','ended'),('turn_aborted','cancelled')]:
            with self.subTest(state=state):
                f.rows=f.rows[:4]+[dict(type='event_msg',payload=dict(type=kind,turn_id='turn'))]
                f.write();f.ingest();f.key=f.history.groups('codex')['groups'][0]['key']
                _,payload,_=f.glance.prepared('codex',f.key)
                self.assertEqual(payload['scope']['current_turn_state'],state)
                bad=test_glance.result(payload);bad[0]['basis']='inference';bad[0]['text']='正在查看样例排班表。'
                with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
                self.assertEqual(exc.exception.code,'closed_turn_claim')
                good=test_glance.result(payload);good[0]['basis']='assistant';good[0]['text']='这一轮已结束，助手汇报查看了样例排班表。'
                self.assertEqual(validate_output(encode(dict(explanations=good)),payload),good)

    def test_user_request_cannot_support_a_claim_of_earlier_progress(self):
        f=self.fx;_,payload,_=f.glance.prepared('codex',f.key)
        self.assertEqual(payload['scope']['previous_progress_evidence_ids'],[])
        bad=test_glance.result(payload);bad[1]['text']='前面已报告修改了首页，现在检查改动。'
        with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
        self.assertEqual(exc.exception.code,'unsupported_previous_progress')
        good=test_glance.result(payload);good[1]['text']='这一步对应你的首页要求；前面进展的联系尚不能确认。'
        self.assertEqual(validate_output(encode(dict(explanations=good)),payload),good)

    def test_unknown_result_formula_requires_a_current_operation_result(self):
        f=self.fx;f.rows=f.rows[:4];f.write();f.ingest();f.key=f.history.groups('codex')['groups'][0]['key']
        _,payload,_=f.glance.prepared('codex',f.key)
        self.assertNotIn('current_operation_status',payload['scope'])
        bad=test_glance.result(payload);bad[0]['basis']='inference';bad[0]['text']='查看排班表，已收到结果，是否成功还不清楚。'
        with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
        self.assertEqual(exc.exception.code,'unanchored_operation_result')

    def test_same_turn_public_progress_is_deduplicated_and_separate_from_requirements(self):
        f=self.fx
        f.rows += [dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我先查看入口文件。为了保留原来的使用方式，先确认页面怎样启动。')])),
                   dict(type='response_item',payload=dict(type='message',role='assistant',phase='final_answer',content=[dict(type='output_text',text='已汇报完成页面整理，按钮还需验收。')])),
                   dict(type='event_msg',payload=dict(type='task_complete',turn_id='turn'))]
        f.write();f.ingest();d,payload,_=f.glance.prepared('codex',f.key)
        self.assertEqual(len(d['earlier_activity']),1)
        ids=payload['scope']['previous_progress_evidence_ids'];self.assertEqual(len(ids),1)
        self.assertEqual(next(x['evidence_class'] for x in payload['facts'] if x['evidence_id']==ids[0]),'assistant')
        self.assertIn('入口文件',f.glance.summary('codex',f.key)['before'][0]['text'])
        good=test_glance.result(payload);good[0]['basis']='assistant';good[0]['text']='这一轮已结束，助手已汇报整理页面。'
        good[1]['text']='前面已报告查看入口，随后整理页面，按钮仍需验收。';good[1]['evidence_ids']+=ids
        good[2].update(text='帮助核对首页是否可以使用。',basis='inference',evidence_ids=['E1','E2',payload['scope']['project_goal_evidence_id']])
        self.assertEqual(validate_output(encode(dict(explanations=good)),payload),good)
        bad=json.loads(encode(good));bad[1]['evidence_ids']=['E1','E2']
        with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
        self.assertEqual(exc.exception.code,'unsupported_previous_progress')

    def test_failed_or_missing_result_survives_task_recap(self):
        f=self.fx;f.add_read_result(output=json.dumps(dict(exit_code=1)))
        d=f.glance.summary('codex',f.key);self.assertIn('失败',d['outcomes'][-1]['text']);self.assertEqual(d['whole_task_status'],'unknown')
        self.assertIn('失败',d['now']['text'])

    def test_summary_http_scope_and_local_only_guards(self):
        f=self.fx;server=create_server(0,{'codex':f.db},source_roots={'codex':f.sources})
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def get(params,headers=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            connection.request('GET','/api/task-summary?'+urlencode(params),headers=headers or {'X-Yukio-Workbench':'1'})
            response=connection.getresponse();status=response.status;raw=response.read();connection.close();return status,raw
        try:
            selection=dict(client='codex',key=f.key)
            status,raw=get(selection);self.assertEqual(status,200);self.assertEqual(json.loads(raw)['whole_task_status'],'unknown')
            self.assertEqual(get(selection,{'X-Yukio-Workbench':'1','Origin':'https://example.test'})[0],403)
            self.assertEqual(get(selection,{'X-Yukio-Workbench':'0'})[0],403)
            self.assertEqual(get(dict(selection,path='/private/file'))[0],400)
            self.assertEqual(get(dict(selection,client='claude'))[0],400)
        finally:server.shutdown();server.server_close();thread.join()

    def test_foreign_chat_and_changed_source_never_supply_recap_text(self):
        f=self.fx;f.path.write_text(f.path.read_text().replace('简化首页','FOREIGN_SENTINEL'))
        d=f.glance.summary('codex',f.key);self.assertNotIn('FOREIGN_SENTINEL',encode(d));self.assertTrue(d['limited'])
        with self.assertRaises(ValueError):f.glance.summary('claude',f.key)

    def test_snapshot_summary_does_not_turn_supplied_plan_into_observed_work(self):
        d=self.fx.detail();d['project_context']=dict(goal='方便工作时扫一眼',before='此前汇报已改首页',next='以后再检查',source_note='用户提供的任务说明')
        s=recap(d,dict(items=[],limited=True));self.assertEqual(s['goal']['basis'],'user_request');self.assertEqual(s['before'][0]['basis'],'assistant');self.assertEqual(s['next']['basis'],'plan');self.assertTrue(s['limited'])

    def test_same_display_name_cannot_mix_worker_replies_or_claim_adoption(self):
        card=dict(title='查看回复',sent='分别检查按钮和颜色',status='已看到回复',targets=[dict(id='a',label='检查助手',state='completed',input_note='只确认发出的要求'),dict(id='b',label='检查助手',state='errored',input_note='背景不完整')],returns=[dict(target_id='a',who='检查助手',text='按钮通过'),dict(target_id='b',who='检查助手',text='颜色失败')],evidence=[dict(label='交接',id='synthetic')])
        s=recap(self.fx.detail(),dict(items=[card],limited=False));receivers=s['handoffs'][0]['receivers']
        self.assertEqual(receivers[0]['reply'],'按钮通过');self.assertEqual(receivers[1]['reply'],'颜色失败')
        self.assertIn('尚未确认',s['handoffs'][0]['adoption'])
        card['returns']=[dict(who='检查助手',text='UNATTRIBUTED')]
        self.assertNotIn('UNATTRIBUTED',encode(recap(self.fx.detail(),dict(items=[card],limited=False))))

    def test_model_must_anchor_current_work_even_when_there_is_no_readable_tool(self):
        f=self.fx;f.rows=f.rows[:4];f.write();f.ingest();f.key=f.history.groups('codex')['groups'][0]['key'];_,payload,_=f.glance.prepared('codex',f.key)
        self.assertIn('current_work_evidence_id',payload['scope']);good=test_glance.result(payload);good[0]['basis']='inference';good[0]['evidence_ids']=['E1']
        with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=good)),payload)
        self.assertEqual(exc.exception.code,'missing_current_work')

    def test_model_cannot_cite_failed_result_but_omit_failure_in_words(self):
        f=self.fx;f.add_read_result(output=json.dumps(dict(exit_code=1)));_,payload,_=f.glance.prepared('codex',f.key)
        good=test_glance.result(payload);good[0]['text']='正在检查按钮。'
        with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=good)),payload)
        self.assertEqual(exc.exception.code,'missing_current_result')

    def test_explanation_cannot_only_cite_phase_background(self):
        f=self.fx;_,payload,_=f.glance.prepared('codex',f.key);good=test_glance.result(payload);good[1]['evidence_ids']=['E1']
        with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=good)),payload)
        self.assertEqual(exc.exception.code,'missing_current_work')

    def test_unknown_outcome_is_not_missing_receipt_or_unclear_attribution(self):
        f=self.fx;f.add_read_result(output='已返回一段内容，没有明确成功标记。');_,payload,_=f.glance.prepared('codex',f.key)
        self.assertEqual(payload['scope']['current_operation_status'],'unknown')
        for text in ['还没看到对应结果。','已收到回执，但对应关系不清楚。','正在检查按钮，准备交付。']:
            bad=test_glance.result(payload);bad[0]['text']=text
            with self.assertRaises(ExplanationError) as exc:validate_output(encode(dict(explanations=bad)),payload)
            self.assertEqual(exc.exception.code,'missing_current_result')


class RealHandoffRecapTests(unittest.TestCase):
    def test_model_context_keeps_both_worker_replies_without_private_recipient_ids(self):
        from glance_view import GlanceView
        f=test_handoffs.HandoffTests();f.setUp()
        try:
            h=test_handoffs
            f.save([h.header('main'),h.start(),h.text('检查按钮和颜色'),h.item(prompt='检查按钮'),h.item('spawn2',targets=['PRIVATE-CHILD-2'],prompt='检查颜色'),h.item('wait','wait',targets=['child','PRIVATE-CHILD-2'],states={'child':{'completed':'按钮通过'},'PRIVATE-CHILD-2':{'completed':'颜色未通过'}})])
            key=next(g['key'] for g in f.history.groups('codex')['groups'] if g['session_id']=='main')
            _,payload,_=GlanceView(f.history,{'codex':f.sources}).prepared('codex',key)
            self.assertIn('按钮通过',encode(payload));self.assertIn('颜色未通过',encode(payload));self.assertNotIn('PRIVATE-CHILD-2',encode(payload))
            combined=next(x for x in payload['facts'] if '按钮通过' in x['excerpt']);self.assertEqual(combined['evidence_class'],'assistant')
        finally:f.tearDown()

    def test_two_native_workers_and_reply_are_preserved_as_separate_exchanges(self):
        f=test_handoffs.HandoffTests();f.setUp()
        try:
            h=test_handoffs
            f.save([h.header('main'),h.start(),h.item(prompt='检查按钮'),h.item('wait','wait',states={'child':{'completed':'按钮未通过检查'}})])
            cards=f.detail();s=recap(dict(project_context=None,project_goals=[],goal='检查页面',evidence={},previous_progress=[],content='等待检查回复',content_basis='assistant',part_evidence={},results=[],snapshot=cards['snapshot'],partial=False,source_unavailable=False),cards)
            self.assertEqual(len(s['handoffs']),2);self.assertIn('未通过',s['handoffs'][0]['receivers'][0]['reply']);self.assertNotIn('未通过',s['handoffs'][1]['receivers'][0]['reply']);self.assertEqual(s['whole_task_status'],'unknown')
        finally:f.tearDown()


if __name__=='__main__':unittest.main()
