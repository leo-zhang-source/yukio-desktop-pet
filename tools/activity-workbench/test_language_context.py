import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
from localization import current_language,language_context,localize,normalize_language
from plain_language import plain_words,readable_fragment
from explanation import complete_response,encode,ExplanationError,ExplanationService,output_system,schema_for,RESULT_SENTENCES_EN,add_object_names,validate_named_subject
from test_explanation import config
from test_plain_language import fixture
import test_glance


class LanguageAndContextTests(unittest.TestCase):
    def test_dynamic_english_ui_is_complete_without_translating_source_names_or_quotes(self):
        from localization import english_text
        with language_context('en'):
            shown=localize(dict(client='codex',key='private_key',title='最近的工作',title_source='客户端聊天名称',
                status='这一轮已结束',quote='这次操作报告失败',
                action='请求查看 /tmp/main.py',
                note='请求查看 the program；尚未见到可配对的回执。不表示仍在运行，也不证明执行失败；结果可能尚未出现或未被观察到。'))
        self.assertEqual(shown['title'],'最近的工作')
        self.assertEqual(shown['quote'],'这次操作报告失败')
        self.assertEqual(shown['key'],'private_key')
        for key in ['title_source','status','action','note']:
            self.assertNotRegex(shown[key],r'[\u3400-\u9fff]',key)
        self.assertEqual(english_text('This is an English update.'),'This is an English update.')
        self.assertEqual(english_text('原文有尚未翻译的内容。'),'原文有尚未翻译的内容。')
        with language_context('en'):
            self.assertEqual(localize(dict(kind='assistant',text='这次操作报告失败'))['text'],'这次操作报告失败')
            inferred=localize(dict(text='前面进展：尚未翻译的项目背景。',basis='inference',evidence=[dict(quote='项目原文')]))
            self.assertNotRegex(inferred['text'],r'[\u3400-\u9fff]')
            self.assertEqual(inferred['evidence'][0]['quote'],'项目原文')

    def test_generated_fallback_names_are_english_but_actual_chat_names_are_preserved(self):
        from chat_catalog import readable_title
        with language_context('en'):
            self.assertEqual(readable_title(''),'Unnamed chat')
            self.assertEqual(readable_title('python3 -c print(1)'),'Local activity record')
            self.assertEqual(readable_title('调查雪绪的活动记录'),'调查雪绪的活动记录')

    def test_home_and_task_recap_use_english_for_generated_notes(self):
        fx=test_glance.GlanceTests();fx.setUp()
        try:
            for row in fx.rows:
                message=row.get('payload',{})
                for item in message.get('content',[]):
                    if 'text' in item:item['text']='Please simplify the home page.' if message.get('role')=='user' else 'I will inspect the home page. This helps preserve the current controls.'
            fx.write();fx.ingest();fx.key=fx.history.groups('codex')['groups'][0]['key']
            (fx.root/'session_index.jsonl').write_text(json.dumps(dict(id='chat-one',thread_name='Improve the workbench'))+'\n')
            def check(value):
                if isinstance(value,str):self.assertNotRegex(value,r'[\u3400-\u9fff]')
                elif isinstance(value,list):
                    for item in value:check(item)
                elif isinstance(value,dict):
                    for item in value.values():check(item)
            with language_context('en'):
                check(localize(fx.glance.cards()))
                check(localize(fx.detail()))
                check(localize(fx.glance.summary('codex',fx.key)))
        finally:fx.tearDown()

    def test_all_operation_outcomes_and_handoff_limits_are_english(self):
        from context_view import STATUS
        from localization import english_text
        for status,(label,note) in STATUS.items():
            with self.subTest(status=status):
                self.assertNotRegex(english_text(label),r'[\u3400-\u9fff]')
                self.assertNotRegex(english_text('请求查看 the document；'+label+'。'+note),r'[\u3400-\u9fff]')
        for message in ['接收者实际拿到的完整背景尚不可确认。','尚未观察到回复如何被采用；收到回复不代表已经采用。','这次交接没有可确认的回复正文。']:
            self.assertNotRegex(english_text(message),r'[\u3400-\u9fff]')

    def test_english_generated_prose_rejects_mixed_language_but_chinese_is_unchanged(self):
        payload,items=fixture()
        payload['scope']['language']='en'
        for item,text in zip(items,['The assistant is checking the home page.','This check connects the page change to the user’s request.','It helps the user understand the current work.']):item['text']=text
        complete_response(encode(dict(explanations=items)),payload)
        items[1]['text']='The assistant is checking 工作台.'
        with self.assertRaises(ExplanationError):complete_response(encode(dict(explanations=items)),payload)
        payload['scope']['language']='zh'
        self.assertIn('工作台',complete_response(encode(dict(explanations=items)),payload)[1]['text'])
        self.assertIn('entirely in English',output_system({'scope':{'language':'en','reading':'summary'}}))

    def test_language_is_request_local_and_chinese_variants_share_the_translation(self):
        self.assertEqual(normalize_language('zh-Hant-TW,en;q=0.8'),'zh')
        self.assertEqual(normalize_language('en-GB,zh;q=0.7'),'en')
        def read(lang):
            with language_context(lang):return current_language(),localize({'title':'当前工作'})['title']
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(list(pool.map(read,['en','zh'])),[('en','Current work'),('zh','当前工作')])
        self.assertEqual(current_language(),'zh')

    def test_screenshot_diagnostic_cannot_become_a_local_explanation(self):
        raw='其中一项返回退出码 0; \'Sample Video App\' link False dir True sample-library {"id": "sample-library", "source": "...'
        self.assertEqual(readable_fragment(raw),'')
        shown=localize({'text':raw,'key':'private_chat_key','sequence':42})
        for forbidden in ['退出码','link False','dir True','sample-library','"id"','{']:
            self.assertNotIn(forbidden,shown['text'])
        self.assertEqual(shown['key'],'private_chat_key');self.assertEqual(shown['sequence'],42)
        self.assertIn('视频播放',readable_fragment('已经检查视频播放，开头和中段都可以打开。'))

    def test_commands_partial_json_and_identifiers_stay_out_of_visible_prose(self):
        for raw in ['```python\nx = 1\n```','{"source": "file', 'SELECT id FROM events', 'ssh host --config config.json', 'Run readFile() for /tmp/source.py at 192.168.2.3:22.']:
            shown=plain_words(raw,'en')
            for token in ['```','{"source"','SELECT id','ssh host','readFile','source.py','192.168.2.3']:
                self.assertNotIn(token,shown)
        self.assertIn('GitHub',plain_words('Check GitHub and DeepSeek.','en'))
        natural='These settings let the video app find videos after you return to your Mac. It also works on macOS.'
        self.assertEqual(plain_words(natural,'en'),natural)

    def test_ordinary_chat_supplies_previous_work_without_a_private_project_brief(self):
        fx=test_glance.GlanceTests();fx.setUp()
        try:
            fx.rows += [dict(type='event_msg',payload=dict(type='task_complete',turn_id='old')),
                        dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='已整理视频资料列表，接下来检查能否播放。')])),
                        dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='现在修复视频播放。')]))]
            fx.write();fx.ingest()
            with language_context('en'):_,payload,_=fx.glance.prepared('codex',fx.key)
            self.assertEqual(payload['scope']['language'],'en')
            self.assertTrue(payload['scope']['context_bridge_evidence_ids'])
            self.assertTrue(payload['scope']['writing_anchors']['reason'])
            self.assertIn('natural English',output_system(payload))
            self.assertIn('on its own',output_system(payload))
        finally:fx.tearDown()

    def test_english_result_composition_keeps_uncertainty_and_accepts_useful_background(self):
        p,items=fixture();p['scope']['language']='en'
        texts=[
            'The assistant is adjusting the video library so the app can find videos again.',
            'The video library is the list the app uses to find videos for playback. Earlier notes describe restoring that list. This check concerns whether the app can open a video from the beginning and after jumping to its middle, rather than just showing a video name.',
            'You want to watch videos while using the app. Checking both starting and jumping ahead helps reveal cases where a video is listed but cannot actually be watched. It does not establish that every video will play correctly.']
        for item,text in zip(items,texts):item['text']=text
        out=complete_response(encode(dict(explanations=items)),p)
        self.assertIn(RESULT_SENTENCES_EN['unknown'],out[0]['text'])
        self.assertGreater(len(out[1]['text']),100)
        self.assertGreater(schema_for(p)['properties']['explanations']['items']['properties']['text']['maxLength'],100)
        p['scope']['current_turn_state']='ended'
        with self.assertRaises(ExplanationError) as e:complete_response(encode(dict(explanations=items)),p)
        self.assertEqual(e.exception.code,'closed_turn_claim')

    def test_both_locales_have_the_current_home_controls(self):
        words=json.loads((Path(__file__).parent/'dist/en.json').read_text())
        for phrase in ['内容','解释','原因','深入解释','之前做了什么','搜索聊天或项目','任务背景','任务与交接小结']:
            self.assertTrue(words[phrase]);self.assertNotEqual(words[phrase],phrase)

    def test_record_explanations_keep_their_own_contract_and_language_cache(self):
        service=ExplanationService(config())
        tokens=[]
        for language in ['en','zh']:
            payload={'scope':{},'facts':[{'evidence_id':'E1','record_marker':'工具提出请求','boundary':'结果尚不明确'}]}
            with language_context(language):preview=service.preview_prepared({'client':'codex','key':'synthetic'},payload,[])
            self.assertEqual(preview['payload']['scope']['language'],language)
            if language=='en':
                self.assertIn('one item per fact',preview['instructions'])
                result=complete_response(encode({'explanations':[{'evidence_id':'E1','text':'The assistant requested an operation. Its result is not known yet.'}]}),preview['payload'])
                self.assertEqual(result[0]['evidence_id'],'E1')
            tokens.append(preview['token'])
        self.assertNotEqual(*tokens)

    def test_english_button_names_are_supplied_without_turning_the_glossary_into_progress(self):
        facts=[];refs=[]
        with language_context('en'):
            alias=add_object_names(facts,refs,{'object_names':'“深入解释”和“之前做了什么”是两个不同入口。','source_note':'仅供称呼'})
        self.assertIn('More detail',facts[0]['excerpt']);self.assertIn('Earlier work',facts[0]['excerpt'])
        self.assertEqual(facts[0]['evidence_class'],'project_context')
        payload={'scope':{'language':'en','naming_context_evidence_id':alias},'facts':facts}
        validate_named_subject('The More Detail button opens a fuller explanation.',payload)
        with self.assertRaises(ExplanationError):validate_named_subject('The two buttons were changed.',payload)



class ExampleIsolationTests(unittest.TestCase):
    def test_prompts_do_not_seed_unrelated_project_examples(self):
        for language in ['zh','en']:
            for view in [{'glance':True},{'reading':'detail'}]:
                prompt=output_system({'scope':dict(language=language,**view)})
                self.assertNotRegex(prompt.lower(),r'videos|服务器存放视频|开机后自动找到|家庭资料服务器')
        self.assertIn('测试、演示、举例',output_system({'scope':{'glance':True,'language':'zh'}}))
        self.assertIn('examples, quotations',output_system({'scope':{'glance':True,'language':'en'}}))

    def test_model_action_comes_from_source_without_a_local_result_suffix(self):
        fx=test_glance.GlanceTests();fx.setUp()
        try:
            data,payload,_=fx.glance.prepared('codex',fx.key)
            self.assertEqual(payload['facts'][1]['excerpt'],data['evidence']['content']['text'])
        finally:fx.tearDown()
