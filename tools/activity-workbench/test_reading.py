import http.client
import json
import threading
import unittest
from contextlib import closing
from explanation import ExplanationError,ExplanationService,encode,validate_output,schema_for,complete_response,concrete_title
from project_context import ProjectContext
from plain_language import plain_words
from glance_automation import GlanceAutomation
from reading_view import ReadingView
from test_explanation import config
import test_glance


def with_titles(payload,items):
    if payload['scope'].get('reading')=='summary':
        for item in items:item.setdefault('title','检查工作台页面')
    return items


class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.fx=test_glance.GlanceTests();self.fx.setUp();self.now=[0.];self.sent=[]
        def sender(cfg,payload):
            self.sent.append(payload)
            return with_titles(payload,[dict(part=p['part'],text='助手汇报检查工作台，具体效果仍需确认。',basis='inference',evidence_ids=p['required'] or p['allowed'][:1]) for p in payload['scope']['reading_parts']])
        self.service=ExplanationService(dict(config(),max_calls_per_hour=20),sender=sender,clock=lambda:self.now[0])
        self.auto=GlanceAutomation(self.fx.glance,self.service,clock=lambda:self.now[0],page_allowed=lambda:True)
        _,payload,refs=self.fx.glance.prepared('codex',self.fx.key)
        preview=self.service.preview_prepared(dict(client='codex',key=self.fx.key),payload,refs)
        self.grant=self.auto.authorize(preview['token'],True,page_owned=True)['grant']
        self.reading=ReadingView(self.fx.glance,self.service,self.auto)

    def tearDown(self):self.fx.tearDown()

    def add_turns(self,n=7):
        for i in range(n):
            self.fx.rows.extend([
                dict(type='event_msg',payload=dict(type='task_started',turn_id='t'+str(i))),
                dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='请完成第'+str(i)+'项页面调整。')])),
                dict(type='response_item',payload=dict(type='message',role='assistant',phase='analysis',content=[dict(type='output_text',text='PRIVATE_HIDDEN_REASONING')])),
                dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='助手汇报第'+str(i)+'项页面已经调整，尚需体验。')])),
                dict(type='event_msg',payload=dict(type='task_complete',turn_id='t'+str(i)))])
        self.fx.write();self.fx.ingest()

    def test_current_details_are_frozen_and_use_same_shared_budget(self):
        current=self.reading.current(self.grant);self.assertEqual(len(current['parts']),4);self.assertFalse(self.sent)
        result=self.reading.explain(self.grant,current['token']);self.assertEqual(result['result']['mode'],'model')
        self.assertEqual(len(self.sent),1);self.assertEqual(len(self.service.calls),1)
        self.reading.explain(self.grant,current['token']);self.assertEqual(len(self.sent),1)

    def test_history_pages_are_short_disjoint_and_snapshot_is_fixed(self):
        self.add_turns();first=self.reading.history_page(self.grant)
        self.assertEqual(len(first['cards']),3);self.assertTrue(first['has_more']);self.assertFalse(self.sent)
        entry=self.service.entries[first['token']]
        self.assertLess(len(encode(entry['payload'])),9000);self.assertNotIn('PRIVATE_HIDDEN_REASONING',encode(entry))
        self.assertEqual(self.reading.explain(self.grant,first['token'])['result']['mode'],'model');self.assertEqual(len(self.sent),1)
        self.add_turns(1)
        second=self.reading.history_page(self.grant,first['snapshot'],first['next_before'])
        self.assertEqual(second['snapshot'],first['snapshot'])
        self.assertFalse({c['title'] for c in first['cards']} & {c['title'] for c in second['cards']})
        self.assertEqual(len(second['cards']),3)

    def test_each_section_detail_has_only_its_own_evidence(self):
        self.add_turns();page=self.reading.history_page(self.grant)
        for card in page['cards']:
            entry=self.service.entries[card['detail_token']]
            requests=[f['excerpt'] for f in entry['payload']['facts'] if f['record_marker']=='这一段的用户要求']
            self.assertEqual(requests,[card['title']]);self.assertLessEqual(len(entry['payload']['facts']),4)
        payload=self.service.entries[page['token']]['payload']
        value=[dict(part=p['part'],text='助手汇报过调整，尚需验收。',basis='inference',evidence_ids=p['required']) for p in payload['scope']['reading_parts']]
        value[0]['evidence_ids']=value[1]['evidence_ids']
        with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=with_titles(payload,value))),payload)

    def test_close_expiry_and_another_page_cannot_send_old_details(self):
        token=self.reading.current(self.grant)['token']
        with self.assertRaises(ExplanationError):self.reading.explain('another-page',token)
        self.auto.revoke(self.grant)
        with self.assertRaises(ExplanationError):self.reading.explain(self.grant,token)
        self.assertFalse(self.sent)

    def test_close_during_current_preparation_does_not_freeze_or_send(self):
        original=self.fx.glance.prepared
        def prepare(**selection):
            result=original(**selection);self.auto.revoke(self.grant);return result
        self.fx.glance.prepared=prepare
        with self.assertRaises(ExplanationError):self.reading.current(self.grant)
        self.assertFalse(self.sent)

    def test_unavailable_source_does_not_invent_history(self):
        self.fx.path.unlink();page=self.reading.history_page(self.grant)
        self.assertFalse(page['cards']);self.assertIsNone(page['token']);self.assertIn('暂时读不到',page['note'])

    def test_other_chat_and_agent_are_not_included(self):
        self.add_turns(2)
        other=self.fx.sources/'other.jsonl';other.write_text(''.join(json.dumps(r)+'\n' for r in [dict(type='session_meta',payload=dict(id='other-chat')),dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='OTHER_PRIVATE_CHAT')]))]))
        from yukio.activity_history import ActivityHistory
        store=ActivityHistory(self.fx.db)
        try:store.ingest(other)
        finally:store.close()
        page=self.reading.history_page(self.grant)
        self.assertNotIn('OTHER_PRIVATE_CHAT',encode(self.service.entries[page['token']]))

    def test_same_explicit_chat_can_read_an_older_file_without_merging_other_agents(self):
        from yukio.activity_history import ActivityHistory
        other=self.fx.sources/'earlier.jsonl'
        rows=[dict(type='session_meta',payload=dict(id='chat-one')),
              dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='较早文件里的明确要求')])),
              dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='较早的助手汇报，尚未验收。')]))]
        other.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        store=ActivityHistory(self.fx.db)
        try:store.ingest(other)
        finally:store.close()
        self.fx.glance.reader.scan_at.clear()  # Let the normal bounded rescan discover the new fixture file.
        page=self.reading.history_page(self.grant)
        self.assertIn('较早文件里的明确要求',[c['title'] for c in page['cards']])
        import sqlite3
        with closing(sqlite3.connect(self.fx.db)) as db, db:
            db.execute("UPDATE events SET record=json_set(record,'$.agent_id','another-agent') WHERE json_extract(record,'$.source_id')<>?",(__import__('history_view').key_parts(self.fx.key)[0],))
        page=self.reading.history_page(self.grant)
        self.assertNotIn('较早文件里的明确要求',[c['title'] for c in page['cards']])

    def test_long_public_turn_keeps_a_labeled_fragment_and_can_continue_backwards(self):
        for i in range(110):
            self.fx.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='助手汇报检查第'+str(i)+'项。')])))
        self.fx.write();self.fx.ingest()
        page=self.reading.history_page(self.grant)
        self.assertEqual(page['cards'][0]['title'],'较早的工作片段（要求未读到）');self.assertTrue(page['has_more'])
        entry=self.service.entries[page['token']]
        self.assertEqual(entry['payload']['facts'][0]['evidence_class'],'unknown')

    def test_http_routes_require_live_page_scope_and_reject_arbitrary_selection(self):
        from server import create_server
        cfg=self.service.config
        (self.fx.root/'page-explanation-policy.json').write_text(json.dumps(dict(version=1,automatic_on_open=True,scope='selected_chat_short_excerpts',destination=cfg['base_url'])))
        server=create_server(0,{'codex':self.fx.db},explanation_service=self.service,model_config=cfg,source_roots={'codex':self.fx.sources})
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def post(route,data,header=True):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            connection.request('POST','/api/'+route,encode(data),{'Content-Type':'application/json',**({'X-Yukio-Workbench':'1'} if header else {})})
            response=connection.getresponse();raw=response.read();status=response.status;connection.close()
            return status,json.loads(raw) if raw.startswith(b'{') else None
        try:
            self.assertEqual(post('reading-history',{'grant':self.grant},False)[0],403)
            self.assertEqual(post('reading-history',{'grant':self.grant,'client':'other'})[0],400)
            preview=post('glance-preview',dict(client='codex',key=self.fx.key))[1]
            grant=post('glance-authorize',dict(token=preview['token'],consent=True,page_owned=True))[1]['grant']
            status,page=post('reading-history',dict(grant=grant));self.assertEqual(status,200)
            self.assertEqual(post('reading-explain',dict(grant=grant,token=page['token']))[1]['result']['mode'],'model')
            post('glance-stop',dict(grant=grant))
            self.assertEqual(post('reading-explain',dict(grant=grant,token=page['token']))[0],409)
        finally:server.shutdown();server.server_close();thread.join(3)

    def test_reading_contract_sanitizes_paths_and_rejects_unsupported_references(self):
        token=self.reading.current(self.grant)['token'];payload=self.service.entries[token]['payload']
        value=[dict(part=p['part'],text='助手汇报修改 /private/project/main.py 和 image-123.png。',basis='inference',evidence_ids=p['required'] or p['allowed'][:1]) for p in payload['scope']['reading_parts']]
        checked=validate_output(encode(dict(explanations=with_titles(payload,value))),payload)
        self.assertNotIn('main.py',encode(checked));self.assertNotIn('/private',encode(checked));self.assertNotIn('image-123.png',encode(checked))
        value[0]['evidence_ids']=['NOT_REAL']
        with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=with_titles(payload,value))),payload)
        self.assertEqual(schema_for(payload)['properties']['explanations']['minItems'],4)

    def test_model_failure_keeps_local_view_and_does_not_substitute_transcript(self):
        original=self.service.sender
        def fail(*args):raise ExplanationError('service_unavailable')
        self.service.sender=fail;token=self.reading.current(self.grant)['token']
        answer=self.reading.explain(self.grant,token)['result']
        self.assertEqual(answer['mode'],'fallback');self.assertFalse(answer['explanations'])
        self.assertTrue(self.fx.detail()['content'])
        self.now[0]=11;self.service.sender=original
        self.assertEqual(self.reading.explain(self.grant,token)['result']['mode'],'model')

    def test_model_cutoff_at_length_boundary_keeps_complete_sentences(self):
        page=self.reading.history_page(self.grant);payload=self.service.entries[page['token']]['payload']
        value=[dict(part=p['part'],text='助手汇报已经检查了工作台首页的显示方式。'+'接下来准备'+('检查'*46)+'确保其',basis='inference',evidence_ids=p['required']) for p in payload['scope']['reading_parts']]
        checked=validate_output(encode(dict(explanations=with_titles(payload,value))),payload)
        self.assertEqual(checked[0]['text'],'助手汇报已经检查了工作台首页的显示方式。')

    def test_reverse_chronological_cards_are_not_presented_as_first_then(self):
        self.add_turns(3);page=self.reading.history_page(self.grant)
        self.assertEqual([c['position'] for c in page['cards']],['最近一段','更早一段','再早一段'])
        payload=self.service.entries[page['token']]['payload'];self.assertEqual(payload['scope']['history_order'],'newest_first')
        value=[dict(part=p['part'],text='用户最初要求调整页面。助手汇报已作调整。',basis='inference',evidence_ids=p['required']) for p in payload['scope']['reading_parts']]
        checked=validate_output(encode(dict(explanations=with_titles(payload,value))),payload)
        self.assertTrue(all('用户当时要求' in i['text'] and '最初' not in i['text'] for i in checked))

    def naming_brief(self):
        path=self.fx.root/'names.json'
        path.write_text(json.dumps(dict(version=1,contexts=[dict(client='codex',key=self.fx.key,goal='让说明清楚。',
            object_names='手动说明按钮：“解释一次”和“持续解释”；查看细节入口：“深入解释”和“之前做了什么”。',source_note='已核对的本机名称，不是活动事实。')])))
        self.fx.glance.project_context=ProjectContext(path)

    def test_name_glossary_reaches_current_and_each_history_part_as_context_not_action(self):
        self.naming_brief();self.add_turns(2)
        current=self.reading.current(self.grant);page=self.reading.history_page(self.grant)
        for token in [current['token'],page['token']]+[c['detail_token'] for c in page['cards']]:
            payload=self.service.entries[token]['payload'];alias=payload['scope']['naming_context_evidence_id']
            entry=next(f for f in payload['facts'] if f['evidence_id']==alias)
            self.assertEqual(entry['evidence_class'],'project_context');self.assertIn('持续解释',entry['excerpt'])
            for part in payload['scope']['reading_parts']:self.assertIn(alias,part['allowed'])

    def test_summary_requires_its_own_concrete_title_and_does_not_accept_vague_buttons(self):
        self.naming_brief();page=self.reading.history_page(self.grant);payload=self.service.entries[page['token']]['payload']
        value=[dict(part=p['part'],title='用户要求移除按钮',text='助手汇报修改了两个按钮。',basis='inference',evidence_ids=p['required']) for p in payload['scope']['reading_parts']]
        with self.assertRaises(ExplanationError) as raised:validate_output(encode(dict(explanations=value)),payload)
        self.assertEqual(raised.exception.code,'unnamed_subject')
        for item in value:item.update(title='移除“解释一次”和“持续解释”按钮',text='助手汇报移除“解释一次”和“持续解释”按钮。')
        self.assertTrue(validate_output(encode(dict(explanations=value)),payload))
        del value[0]['title']
        with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=value)),payload)

    def test_title_carries_names_from_its_own_body_without_guessing_from_glossary(self):
        self.naming_brief();payload=self.service.entries[self.reading.history_page(self.grant)['token']]['payload']
        self.assertEqual(concrete_title('移除两个按钮','助手说移除“解释一次”和“持续解释”。',payload),'移除“解释一次”、“持续解释”按钮')
        self.assertEqual(concrete_title('移除两个按钮','助手没有说按钮名称。',payload),'移除两个按钮')
        title=concrete_title('写清按钮名称','区分“解释一次”、“持续解释”、“深入解释”和“之前做了什么”。',payload)
        self.assertTrue(title.startswith('区分'));self.assertIn('之前做了什么',title);self.assertLessEqual(len(title),44)

    def test_these_two_buttons_keep_names_from_the_preceding_public_answer(self):
        self.fx.rows.extend([
            dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='上面是“解释一次”和“持续解释”按钮，点击后生成说明。')])),
            dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='不要这两个按钮了，打开页面就解释。')])),
            dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我会移除这两个按钮。')])),
            dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='已按要求改为打开页面自动说明。')]))])
        self.fx.write();self.fx.ingest();page=self.reading.history_page(self.grant);payload=self.service.entries[page['token']]['payload']
        part=payload['scope']['reading_parts'][0]
        background=next(f for f in payload['facts'] if f['record_marker'].startswith('前一段助手'))
        self.assertIn('解释一次',background['excerpt']);self.assertIn('持续解释',background['excerpt'])
        self.assertIn(background['evidence_id'],part['required']);self.assertEqual(background['evidence_class'],'assistant')
        detail=self.service.entries[page['cards'][0]['detail_token']]['payload']
        self.assertLessEqual(len(detail['facts']),4)

    def test_current_deep_explanation_also_rejects_unnamed_buttons(self):
        self.naming_brief();token=self.reading.current(self.grant)['token'];payload=self.service.entries[token]['payload']
        value=[dict(part=p['part'],text='修改了两个按钮，让按钮更清楚。',basis='inference',evidence_ids=p['required'] or p['allowed'][:1]) for p in payload['scope']['reading_parts']]
        with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=value)),payload)
        for item in value:item['text']='修改“深入解释”和“之前做了什么”入口的说明。'
        self.assertTrue(validate_output(encode(dict(explanations=value)),payload))
        for item in value[1:]:item['text']='这些按钮的说明用于减少混淆。'
        self.assertTrue(validate_output(encode(dict(explanations=value)),payload))

    def test_homepage_three_parts_use_the_same_object_name_rule(self):
        self.naming_brief();_,payload,_=self.fx.glance.prepared('codex',self.fx.key)
        value=[dict(part=part,text='调整两个按钮的说明。',basis='inference',evidence_ids=list(payload['scope']['writing_anchors'][part])) for part in ('content','explanation','reason')]
        operation=payload['scope'].get('current_operation_evidence_id')
        if operation:value[0]['evidence_ids'].append(operation)
        with self.assertRaises(ExplanationError) as raised:complete_response(encode(dict(explanations=value)),payload)
        self.assertEqual(raised.exception.code,'unnamed_subject')
        for item in value:item['text']='区分“解释一次”和“持续解释”按钮的说明。'
        self.assertTrue(complete_response(encode(dict(explanations=value)),payload))
        for item in value[1:]:item['text']='区分这些按钮，减少误解。'
        self.assertTrue(complete_response(encode(dict(explanations=value)),payload))

    def test_unread_names_stay_unknown_instead_of_becoming_current_page_names(self):
        self.naming_brief();token=self.reading.current(self.grant)['token'];payload=self.service.entries[token]['payload']
        value=[dict(part=p['part'],text='当时用于开始说明的按钮，名称未读到，不能确认是哪一组。',basis='unknown',evidence_ids=p['required'] or p['allowed'][:1]) for p in payload['scope']['reading_parts']]
        self.assertTrue(validate_output(encode(dict(explanations=value)),payload))

    def test_ui_name_separator_is_preserved_while_real_paths_are_removed(self):
        text=plain_words('移除“解释一次/持续解释”按钮，新增“深入解释/之前做了什么”入口。')
        self.assertIn('解释一次、持续解释',text);self.assertIn('深入解释、之前做了什么',text)
        self.assertNotIn('/Users/',plain_words('查看“/Users/someone/project/image.png”文件。'))
        self.assertNotIn('image.png',plain_words('查看“/Users/someone/project/image.png”文件。'))
