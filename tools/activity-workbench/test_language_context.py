import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
from localization import current_language,language_context,localize,normalize_language
from plain_language import plain_words,readable_fragment
from explanation import complete_response,encode,ExplanationError,ExplanationService,output_system,schema_for,RESULT_SENTENCES_EN
from test_explanation import config
from test_plain_language import fixture
import test_glance


class LanguageAndContextTests(unittest.TestCase):
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

