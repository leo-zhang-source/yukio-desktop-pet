import json
from pathlib import Path
import tempfile
import unittest
from history_view import key_for
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

    def test_object_names_are_optional_bounded_and_do_not_cross_chats(self):
        self.write([dict(self.entry,object_names='说明按钮：“解释一次”和“持续解释”。')])
        self.assertIn('解释一次',self.reader.get('codex','exact-chat')['object_names'])
        self.assertIsNone(self.reader.get('codex','other-chat'))
        self.write([dict(self.entry,object_names=['not a string'])]);self.assertIsNone(self.reader.get('codex','exact-chat'))

    def test_same_explicit_chat_keeps_its_background_when_the_record_file_moves(self):
        key=lambda file,generation,session,agent='',branch=0:key_for([file,generation,session,agent,branch])
        self.write([dict(self.entry,key=key('old-file',2,'chat-a'))])
        self.assertIn('一眼能懂',self.reader.get('codex',key('new-file',1,'chat-a'))['goal'])
        for session,agent,branch in [('chat-b','',0),('chat-a','helper',0),('chat-a','',1),('source-anonymous','',0)]:
            self.assertIsNone(self.reader.get('codex',key('new-file',1,session,agent,branch)))
        self.assertIsNone(self.reader.get('claude',key('new-file',1,'chat-a')))

    def test_ambiguous_background_is_not_selected_by_chat_name_or_recency(self):
        key=lambda file:key_for([file,1,'chat-a','',0])
        self.write([dict(self.entry,key=key('old-a')),dict(self.entry,key=key('old-b'),goal='不同的说明')])
        self.assertIsNone(self.reader.get('codex',key('new')))
