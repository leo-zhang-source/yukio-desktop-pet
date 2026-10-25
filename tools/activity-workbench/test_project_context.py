import json
from pathlib import Path
import tempfile
import unittest
from project_context import ProjectContext


class ProjectContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'context.json'
        self.entry=dict(client='codex',key='exact-chat',goal='让工作时一眼能懂。',before='前面已报告保存记录。',now='把记录联系到整个任务。',next='后续再验收解释质量。',source_note='本机项目说明，不是观察事实。')
        self.write([self.entry]);self.reader=ProjectContext(self.path)
    def tearDown(self):self.temp.cleanup()
    def write(self,entries):self.path.write_text(json.dumps(dict(version=1,contexts=entries),ensure_ascii=False),encoding='utf-8')
    def test_context_is_bound_to_exact_chat_and_client(self):
        self.assertIn('一眼能懂',self.reader.get('codex','exact-chat')['goal'])
        self.assertIsNone(self.reader.get('claude','exact-chat'));self.assertIsNone(self.reader.get('codex','another-chat'))
    def test_missing_invalid_or_ambiguous_context_is_not_guessed(self):
        self.write([self.entry,self.entry]);self.assertIsNone(self.reader.get('codex','exact-chat'))
        self.path.write_text('broken');self.assertIsNone(self.reader.get('codex','exact-chat'))
        self.path.unlink();self.assertIsNone(self.reader.get('codex','exact-chat'))
    def test_credentials_filtered_and_reads_do_not_mutate_the_file(self):
        self.write([dict(self.entry,goal='api_key=PRIVATE_SENTINEL 让说明更清楚。')]);before=self.path.read_bytes()
        self.assertNotIn('PRIVATE_SENTINEL',self.reader.get('codex','exact-chat')['goal']);self.assertEqual(before,self.path.read_bytes())
    def test_context_is_bounded_and_refreshes_from_edited_brief(self):
        self.write([dict(self.entry,now='新的工作重点')]);self.assertEqual(self.reader.get('codex','exact-chat')['now'],'新的工作重点')
        self.path.write_text('x'*32769);self.assertIsNone(self.reader.get('codex','exact-chat'))
