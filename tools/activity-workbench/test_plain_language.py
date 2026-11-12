import unittest
from plain_language import plain_words
from explanation import complete_response,encode,ExplanationError,RESULT_SENTENCES


class PlainLanguageTests(unittest.TestCase):
    def test_protocol_blocks_do_not_turn_into_mangled_paths(self):
        text='正在检查首页。<task-notification><task-type>artifact-auto-react</task-type><summary>Internal event</summary></task-notification>'
        self.assertEqual(plain_words(text),'正在检查首页。')
        self.assertNotIn('<',plain_words('正在核对 <summary>页面说明</summary>。'))

    def test_explicit_role_survives_without_filename_path_code_or_id(self):
        text='调整雪绪 App 封面图（`/Users/demo/assets/cover_839174.png`），修改 `render_cover()`。'
        result=plain_words(text)
        self.assertIn('雪绪 App 封面图',result)
        for technical in ('/Users','839174','.png','render_cover','`','()'):
            self.assertNotIn(technical,result)

    def test_unknown_image_does_not_gain_an_invented_purpose(self):
        for text in ('查看 `/tmp/431e5c5.png`。','查看图片编号xxxx123。','查看 C:\\demo\\image.png。'):
            result=plain_words(text)
            self.assertIn('这张图片',result);self.assertNotIn('封面',result)

    def test_technical_blocks_are_not_shown_as_story_prose(self):
        result=plain_words('正在调整首页。```js\nconst x = fn();\n```查看 [按钮说明](http://192.168.1.2/private)。')
        self.assertIn('正在调整首页',result);self.assertIn('按钮说明',result)
        for technical in ('const','fn','http','192.168','```'):self.assertNotIn(technical,result)


def fixture(status='unknown'):
    payload=dict(scope=dict(glance=True,compose_current_result=True,current_work_evidence_id='E2',
        current_operation_evidence_id='E3',current_operation_status=status),facts=[
        dict(evidence_id='E1',evidence_class='user_request'),dict(evidence_id='E2',evidence_class='assistant'),
        dict(evidence_id='E3',evidence_class='observed')])
    items=[dict(part='content',text='正在调整工作台首页的解释按钮。',basis='assistant',evidence_ids=['E2']),
           dict(part='explanation',text='前面交付了工作台，这次继续检查说明是否容易阅读。',basis='inference',evidence_ids=['E2']),
           dict(part='reason',text='减少工作时翻记录找背景的麻烦。',basis='inference',evidence_ids=['E1'])]
    return payload,items


class ResultCompositionTests(unittest.TestCase):
    def test_missing_formula_and_receipt_reference_are_composed_from_local_record(self):
        for status,sentence in RESULT_SENTENCES.items():
            with self.subTest(status=status):
                payload,items=fixture(status)
                done=complete_response(encode(dict(explanations=items)),payload)
                self.assertIn(sentence,done[0]['text']);self.assertIn('E3',done[0]['evidence_ids'])
                self.assertEqual(done[0]['basis'],'inference')
                self.assertEqual(complete_response(encode(dict(explanations=done)),payload),done)

    def test_cannot_append_a_receipt_to_an_unrelated_or_invalid_action(self):
        for ids in (['E1'],['E99'],[],['E2','E99']):
            payload,items=fixture();items[0]['evidence_ids']=ids
            with self.assertRaises(ExplanationError):complete_response(encode(dict(explanations=items)),payload)

    def test_uncertainty_does_not_launder_a_contradictory_outcome(self):
        for status,text in [('unknown','检查已通过。'),('failed','测试成功。'),('unknown','还没看到对应结果。'),('no_receipt','修改报告成功。')]:
            payload,items=fixture(status);items[0]['text']=text
            with self.assertRaises(ExplanationError) as error:complete_response(encode(dict(explanations=items)),payload)
            self.assertEqual(error.exception.code,'contradictory_result')

    def test_no_receipt_is_invented_when_there_is_no_current_operation(self):
        payload,items=fixture()
        payload['scope'].pop('current_operation_evidence_id');payload['scope'].pop('current_operation_status')
        done=complete_response(encode(dict(explanations=items)),payload)
        self.assertNotIn('收到结果',done[0]['text']);self.assertEqual(done[0]['evidence_ids'],['E2'])

    def test_output_roles_replace_technical_details_but_keep_the_evidence(self):
        payload,items=fixture();items[0]['text']='正在调整雪绪 App 封面图 `/tmp/1242315.png`。'
        done=complete_response(encode(dict(explanations=items)),payload)
        self.assertIn('雪绪 App 封面图',done[0]['text']);self.assertNotIn('/tmp',done[0]['text'])
        self.assertNotIn('.png',done[0]['text']);self.assertEqual(done[0]['evidence_ids'],['E2','E3'])

    def test_old_guards_for_diagnosis_guarantees_and_closed_turns_still_apply(self):
        for part,text,scope in [(2,'这确保解释可信。',{}),(1,'任务卡住了。',{}),(0,'正在调整解释按钮。',dict(current_turn_state='ended'))]:
            payload,items=fixture();items[part]['text']=text;payload['scope'].update(scope)
            with self.assertRaises(ExplanationError):complete_response(encode(dict(explanations=items)),payload)
