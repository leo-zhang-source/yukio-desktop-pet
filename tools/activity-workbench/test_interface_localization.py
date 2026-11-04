"""Regression coverage for generated UI labels, not model explanations."""
import json
import unittest

from history_view import KINDS, TOOLS, describe
from localization import language_context, localize
import test_context
import test_history_review


class InterfaceLocalizationTests(unittest.TestCase):
    def assert_english(self, value):
        self.assertNotRegex(json.dumps(value, ensure_ascii=False), r'[\u3400-\u9fff]')

    def test_every_record_kind_tool_and_receipt_has_complete_english_labels(self):
        cases = [dict(kind=kind) for kind in [*KINDS, 'future_record_kind']]
        cases += [dict(kind='tool_requested', tool_name=tool) for tool in [*TOOLS, 'unknown_tool']]
        for outcome in ['succeeded', 'failed', 'cancelled', 'unknown']:
            for flags in [{}, {'projection_eligible': True, 'call_outcome': 'unknown'},
                          {'projection_eligible': True}, {'conflicting_results': True}]:
                cases.append(dict(kind='tool_result', outcome=outcome, **flags))
        for case in cases:
            with self.subTest(record=case):
                original = describe(case)
                with language_context('en'):
                    self.assert_english(localize(original))
                with language_context('zh'):
                    self.assertEqual(localize(original), original)

    def test_context_counts_stage_and_unknown_records_are_fully_translated(self):
        fx = test_context.ContextTests(); fx.setUp()
        try:
            fx.add('turn_started')
            fx.add(tool_name='unknown_tool')
            fx.receipt('failed')
            fx.add('future_record_kind')
            fx.add('observation_gap', session_id=None)
            fx.receipt('unknown', call_id='unmatched')
            with language_context('en'):
                self.assert_english(localize(fx.context()))
                self.assert_english(localize(fx.view.explanation_context('codex', fx.key)[1]))
                self.assert_english(localize(fx.history.timeline('codex', fx.key)))
        finally:
            fx.tearDown()

    def test_review_placeholders_are_english_and_original_evidence_is_retained(self):
        fx = test_history_review.HistoryReviewTests(); fx.setUp()
        try:
            with language_context('en'):
                data = localize(fx.prepare('steps')[0])
                self.assertTrue(data['items'])
                for item in data['items']:
                    self.assert_english({key: item[key] for key in ['title', 'status']})
                overview = localize(fx.prepare()[0])
                for part in overview['parts']:
                    self.assert_english(part['title'])
                for ref in overview['references']:
                    self.assert_english(ref['title'])
                self.assertTrue(any('让我一眼看懂' in ref['quote'] for ref in overview['references']))
        finally:
            fx.tearDown()

    def test_untranslated_source_wording_never_becomes_partial_english(self):
        original = '尚未翻译的新活动记录，需要保留原文。'
        with language_context('en'):
            shown = localize(dict(note=original, quote=original, name='活动记录',
                                  title='活动记录', title_source='客户端聊天名称'))
        self.assertEqual(shown['note'], original)
        self.assertEqual(shown['quote'], original)
        self.assertEqual(shown['name'], '活动记录')
        self.assertEqual(shown['title'], '活动记录')


if __name__ == '__main__':
    unittest.main()
