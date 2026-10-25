import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from chat_catalog import activity_state, readable_title, project_label, codex_project
from source_context import SourceContext


class ChatCatalogTests(unittest.TestCase):
    def test_recent_messages_do_not_prove_work_and_old_open_turn_is_unknown(self):
        base=dict(source_unavailable=False,recorder=dict(state='active'),tone='fresh',status='刚有新活动',age_seconds=1)
        self.assertEqual(activity_state(base),'unknown')
        self.assertEqual(activity_state(dict(base,turn_marker='turn_started')),'working')
        self.assertEqual(activity_state(dict(base,turn_marker='turn_started',age_seconds=300)),'unknown')
        self.assertEqual(activity_state(dict(base,status='这一轮已结束',turn_marker='turn_ended')),'inactive')
        self.assertEqual(activity_state(dict(base,tone='attention')),'waiting')
        self.assertEqual(activity_state(dict(base,tone='attention',source_unavailable=True)),'unknown')

    def test_project_names_never_join_same_named_folders(self):
        first=project_label('/one/my-app',client='codex');other=project_label('/two/my-app',client='codex')
        self.assertEqual(first['name'],other['name']);self.assertNotEqual(first['id'],other['id'])
        self.assertNotIn('/one',json.dumps(first))
        roots=[('a','My app','/one'),('b','App design','/one/my-app')]
        found=project_label('/one/my-app/sub',client='codex',roots=roots)
        self.assertEqual(found['name'],'App design');self.assertEqual(found['source'],'client_project')
        self.assertEqual(project_label('/one-other/my-app',client='codex',roots=roots)['source'],'workspace')
        self.assertEqual(project_label('/one',client='codex',roots=[('a','A','/one'),('b','B','/one')])['source'],'workspace')

    def test_shell_input_is_not_presented_as_a_chat_name(self):
        for text in ('<bash-input>pkill -f private</bash-input>','rm -rf /private/project','Codex · 暂未取得聊天名称','/Users/example/private','@"~/Desktop/private/project.md','~/private'):
            self.assertNotIn('private',readable_title(text));self.assertNotIn('bash-input',readable_title(text))
        self.assertEqual(readable_title('调查 Yukio 活动检测代码'),'调查 Yukio 活动检测代码')

    def test_project_metadata_requires_the_exact_registered_source_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sessions=root/'sessions';sessions.mkdir();source=sessions/'one.jsonl';source.write_text('{}\n')
            state=root/'state_5.sqlite'
            with sqlite3.connect(state) as c:
                c.executescript('CREATE TABLE threads(id TEXT,cwd TEXT,rollout_path TEXT,project_id TEXT);CREATE TABLE projects(id TEXT,name TEXT);CREATE TABLE project_roots(project_id TEXT,path TEXT);')
                c.execute('INSERT INTO threads VALUES(?,?,?,?)',('session','/work/app',str(source),None))
                c.execute('INSERT INTO projects VALUES(?,?)',('p','雪绪'));c.execute('INSERT INTO project_roots VALUES(?,?)',('p','/work/app'))
            before=hashlib.sha256(state.read_bytes()).hexdigest();reader=SourceContext({'codex':sessions})
            key=hashlib.sha256(str(source.resolve()).encode()).hexdigest()
            project=codex_project(reader,[key,1,'session','',0]);self.assertEqual(project['name'],'雪绪')
            self.assertIsNone(codex_project(reader,['wrong-source',1,'session','',0]))
            self.assertIsNone(codex_project(reader,[key,1,'another-session','',0]))
            self.assertEqual(hashlib.sha256(state.read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
