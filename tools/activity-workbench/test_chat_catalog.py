import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from chat_catalog import activity_state, readable_title, project_label, codex_project
from source_context import SourceContext


class ChatCatalogTests(unittest.TestCase):
    def test_claude_title_reads_exact_session_and_latest_rename(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'one.jsonl'
            rows=[dict(type='custom-title',sessionId='session',customTitle='检查工作台'),
                  dict(type='custom-title',sessionId='other',customTitle='别人的聊天')]
            source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            reader=SourceContext({'claude':root});key=hashlib.sha256(str(source.resolve()).encode()).hexdigest()
            self.assertEqual(reader.title_and_path('claude','session',key)[0],'检查工作台')
            with source.open('a') as f:
                f.write(json.dumps(dict(type='custom-title',sessionId='session',customTitle='修复工作台'))+'\n')
                f.write(json.dumps(dict(type='ai-title',sessionId='session',aiTitle='较弱的自动名称'))+'\n')
            self.assertEqual(reader.title_and_path('claude','session',key)[0],'修复工作台')
            self.assertEqual(reader.title_and_path('claude','absent',key)[0],'')
            self.assertEqual(reader.title_and_path('claude','session','wrong-source')[0],'')

    def test_claude_title_handles_large_transcripts_and_partial_last_line(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'one.jsonl'
            source.write_text(json.dumps(dict(type='ai-title',sessionId='s',aiTitle='原来的名称'))+'\n'+json.dumps(dict(type='attachment',data='x'*600000))+'\n'+json.dumps(dict(type='custom-title',sessionId='s',customTitle='新的名称'))+'\n'+ '{"type":"custom-title"')
            reader=SourceContext({'claude':root});key=hashlib.sha256(str(source.resolve()).encode()).hexdigest()
            self.assertEqual(reader.title_and_path('claude','s',key)[0],'新的名称')

    def test_recent_messages_do_not_prove_work_and_old_open_turn_is_unknown(self):
        base=dict(source_unavailable=False,recorder=dict(state='active'),tone='fresh',status='刚有新活动',age_seconds=1)
        self.assertEqual(activity_state(base),'unknown')
        self.assertEqual(activity_state(dict(base,turn_marker='turn_started')),'working')
        self.assertEqual(activity_state(dict(base,turn_marker='turn_started',age_seconds=300)),'unknown')
        self.assertEqual(activity_state(dict(base,status='这一轮已结束',turn_marker='turn_ended')),'inactive')
        self.assertEqual(activity_state(dict(base,tone='attention')),'waiting')
        self.assertEqual(activity_state(dict(base,tone='attention',source_unavailable=True)),'unknown')

    def test_project_names_never_join_same_named_folders(self):
        first=project_label('/one/my-app',client='codex',explicit=('one','My app'));other=project_label('/two/my-app',client='codex',explicit=('two','My app'))
        self.assertEqual(first['name'],other['name']);self.assertNotEqual(first['id'],other['id'])
        self.assertNotIn('/one',json.dumps(first))
        roots=[('a','My app','/one'),('b','App design','/one/my-app')]
        found=project_label('/one/my-app/sub',client='codex',roots=roots)
        self.assertEqual(found['name'],'App design');self.assertEqual(found['source'],'client_project')
        self.assertIsNone(project_label('/one-other/my-app',client='codex',roots=roots))
        self.assertIsNone(project_label('/one',client='codex',roots=[('a','A','/one'),('b','B','/one')]))
        self.assertIsNone(project_label('/scratch-2026/worktree/my-app',client='claude'))
        self.assertNotEqual(first['id'],project_label('/one/my-app',client='claude',explicit=('one','My app'))['id'])

    def test_shell_input_is_not_presented_as_a_chat_name(self):
        for text in ('<bash-input>pkill -f private</bash-input>','rm -rf /private/project','Codex · 暂未取得聊天名称','/Users/example/private','@"~/Desktop/private/project.md','~/private'):
            self.assertNotIn('private',readable_title(text));self.assertNotIn('bash-input',readable_title(text))
        self.assertEqual(readable_title('调查 Yukio 活动检测代码'),'调查 Yukio 活动检测代码')

    def test_project_metadata_requires_the_exact_registered_source_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sessions=root/'sessions';sessions.mkdir();source=sessions/'one.jsonl';source.write_text('{}\n')
            state=root/'state_5.sqlite'
            with closing(sqlite3.connect(state)) as c, c:
                c.executescript('CREATE TABLE threads(id TEXT,cwd TEXT,rollout_path TEXT,project_id TEXT);CREATE TABLE projects(id TEXT,name TEXT);CREATE TABLE project_roots(project_id TEXT,path TEXT);')
                c.execute('INSERT INTO threads VALUES(?,?,?,?)',('session','/work/app',str(source),None))
                c.execute('INSERT INTO projects VALUES(?,?)',('p','雪绪'));c.execute('INSERT INTO project_roots VALUES(?,?)',('p','/work/app'))
            before=hashlib.sha256(state.read_bytes()).hexdigest();reader=SourceContext({'codex':sessions})
            key=hashlib.sha256(str(source.resolve()).encode()).hexdigest()
            project=codex_project(reader,[key,1,'session','',0]);self.assertEqual(project['name'],'雪绪')
            self.assertIsNone(codex_project(reader,['wrong-source',1,'session','',0]))
            self.assertIsNone(codex_project(reader,[key,1,'another-session','',0]))
            self.assertEqual(hashlib.sha256(state.read_bytes()).hexdigest(),before)


class ClaudeDesktopChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.transcripts=self.root/'projects';self.transcripts.mkdir()
        self.desktop=self.root/'desktop';self.account=self.desktop/'account'/'org';self.account.mkdir(parents=True)
        self.db=self.root/'history.sqlite'

    @staticmethod
    def sid(n):return '00000000-0000-4000-8000-'+str(n).zfill(12)

    def metadata(self,n,current,prior=(),title='同名聊天',**extra):
        row=dict(sessionId='local_'+self.sid(n),cliSessionId=self.sid(current),
                 priorCliSessionIds=[self.sid(i) for i in prior],title=title,isArchived=False,**extra)
        path=self.account/(row['sessionId']+'.json');path.write_text(json.dumps(row,ensure_ascii=False))
        return path

    def record(self,n,text,folder=""):
        from launcher import core_path
        import sys
        sys.path.insert(0,str(core_path()))
        from yukio.activity_history import ActivityHistory
        directory=self.transcripts/folder;directory.mkdir(exist_ok=True)
        path=directory/(self.sid(n)+'.jsonl')
        rows=[dict(type='custom-title',sessionId=self.sid(n),customTitle='同名聊天'),
              dict(type='user',sessionId=self.sid(n),isSidechain=False,timestamp='2026-11-10T08:00:00Z',message=dict(role='user',content=text))]
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        store=ActivityHistory(self.db)
        try:store.ingest(path,source_format='claude')
        finally:store.close()

    def glance(self):
        from glance_view import GlanceView
        from history_view import HistoryView
        return GlanceView(HistoryView({'claude':self.db}),{'claude':self.transcripts},claude_desktop_root=self.desktop)

    def test_five_cli_segments_are_one_desktop_chat_using_current_branch(self):
        self.metadata(100,5,[1,2,3,4],title='复古网站')
        self.record(5,'请保留新版车辆。')
        for i in range(1,5):self.record(i,'这是旧分支要求，不是当前要求。')
        self.record(6,'这是另一个同名聊天。');self.metadata(101,6,title='复古网站')
        view=self.glance();cards=view.cards()['cards']
        self.assertEqual(len(cards),2)
        chosen=next(c for c in cards if c['session_id']==self.sid(5))
        self.assertEqual(set(chosen['continuation_sessions']),{self.sid(i) for i in range(1,6)})
        self.assertEqual(chosen['title'],'复古网站')
        detail=view.detail('claude',chosen['key'])
        self.assertEqual(detail['title'],chosen['title']);self.assertIn('新版车辆',detail['goal'])
        self.assertNotIn('旧分支',detail['goal'])
        self.assertEqual(len(view.history.groups('claude')['groups']),6) # Raw history remains scoped and intact.

    def test_unobserved_current_branch_does_not_present_an_old_branch_as_current(self):
        self.metadata(100,5,[1,2]);self.record(1,'旧要求');self.record(2,'另一条旧要求')
        self.record(6,'独立终端聊天')
        self.assertEqual([c['session_id'] for c in self.glance().cards()['cards']],[self.sid(6)])

    def test_missing_desktop_metadata_does_not_merge_same_titles(self):
        self.record(1,'第一个聊天');self.record(2,'另一个聊天')
        self.assertEqual(len(self.glance().cards()['cards']),2)

    def test_named_desktop_chat_without_readable_content_is_hidden_not_deleted(self):
        self.metadata(100,1,title='已有名称');self.record(1,'<system-reminder>Internal note.</system-reminder>')
        view=self.glance();before=self.db.read_bytes()
        self.assertEqual(view.cards()['cards'],[])
        self.assertEqual(len(view.history.groups('claude')['groups']),1)
        self.assertEqual(self.db.read_bytes(),before)
        self.record(1,'请查看图片')
        self.assertEqual(len(view.cards()['cards']),1)

    def test_claude_source_disappearance_does_not_leave_an_empty_desktop_row(self):
        self.metadata(100,1);self.record(1,'请查看图片')
        view=self.glance();self.assertEqual(len(view.cards()['cards']),1)
        path=self.transcripts/(self.sid(1)+'.jsonl');parked=path.with_suffix('.parked');path.rename(parked)
        self.assertEqual(view.cards()['cards'],[])
        parked.rename(path)
        self.assertEqual(len(view.cards()['cards']),1)

    def test_live_rewind_reads_the_new_transcript_without_waiting_for_the_directory_cache(self):
        self.metadata(100,1);self.record(1,'旧记录内容',folder='project')
        view=self.glance();now=[0.];view.reader.claude_desktop.clock=lambda:now[0]
        self.assertFalse(view.cards()['cards'][0]['source_unavailable'])
        self.record(2,'新记录内容',folder='project');self.metadata(100,2,[1]);now[0]=3.
        card=view.cards()['cards'][0]
        self.assertEqual(card['session_id'],self.sid(2));self.assertFalse(card['source_unavailable'])
        self.assertIn('新记录内容',view.detail('claude',card['key'])['goal'])
        self.assertIsNone(view.reader.title_and_path('claude',self.sid(2),'wrong-source')[1])

    def test_shared_fork_ancestor_and_archived_chat_do_not_join_current_chats(self):
        self.metadata(100,2,[1]);self.metadata(101,3,[1])
        path=self.metadata(102,4);row=json.loads(path.read_text());row['isArchived']=True;path.write_text(json.dumps(row))
        for i in (1,2,3,4):self.record(i,'独立要求 '+str(i))
        cards=self.glance().cards()['cards']
        self.assertEqual({c['session_id'] for c in cards},{self.sid(i) for i in (1,2,3)})
        for card in cards:self.assertNotIn(self.sid(1),card.get('continuation_sessions',[]))

    def test_index_refreshes_rename_rewind_and_removed_metadata_without_profile_writes(self):
        from claude_desktop import ClaudeDesktopIndex
        now=[0.];path=self.metadata(100,2,[1]);index=ClaudeDesktopIndex(self.desktop,clock=lambda:now[0])
        self.assertEqual(index.snapshot()[self.sid(1)]['current'],self.sid(2))
        self.metadata(100,3,[1,2],title='改过的名字');now[0]=3.
        self.assertEqual(index.snapshot()[self.sid(1)]['title'],'改过的名字')
        self.assertEqual(index.snapshot()[self.sid(2)]['current'],self.sid(3))
        before=path.read_bytes();index.snapshot();self.assertEqual(path.read_bytes(),before)
        path.unlink();now[0]=6.;self.assertEqual(index.snapshot(),{})

    def test_index_rejects_malformed_identity_symlink_and_partial_file(self):
        from claude_desktop import ClaudeDesktopIndex
        good=self.metadata(100,2,[1]);bad=self.metadata(101,3)
        row=json.loads(bad.read_text());row['sessionId']='local_'+self.sid(102);bad.write_text(json.dumps(row))
        (self.account/('local_'+self.sid(103)+'.json')).symlink_to(good)
        (self.account/('local_'+self.sid(104)+'.json')).write_text('{"cliSessionId":')
        result=ClaudeDesktopIndex(self.desktop).snapshot()
        self.assertEqual(set(result),{self.sid(1),self.sid(2)})

    def test_index_keeps_only_chat_metadata_and_rejects_cross_account_ambiguity(self):
        from claude_desktop import ClaudeDesktopIndex
        self.metadata(100,2,[1],promptAppendSnapshot={'append':'PRIVATE PROMPT'},remoteMcpServersConfig=[{'secret':'PRIVATE CREDENTIAL'}])
        index=ClaudeDesktopIndex(self.desktop);result=index.snapshot()
        self.assertNotIn('PRIVATE',json.dumps(result))
        other=self.desktop/'another-account'/'org';other.mkdir(parents=True)
        (other/('local_'+self.sid(101)+'.json')).write_text(json.dumps(dict(sessionId='local_'+self.sid(101),cliSessionId=self.sid(2),title='另一个账号')))
        self.assertNotIn(self.sid(2),ClaudeDesktopIndex(self.desktop).snapshot())

    def test_large_or_symlinked_profile_metadata_is_not_used(self):
        from claude_desktop import ClaudeDesktopIndex,MAX_FILE
        path=self.metadata(100,2,[1]);path.write_text(path.read_text()+' '*(MAX_FILE+1))
        self.assertEqual(ClaudeDesktopIndex(self.desktop).snapshot(),{})
        outside=self.root/'outside';outside.mkdir()
        (outside/('local_'+self.sid(101)+'.json')).write_text(json.dumps(dict(sessionId='local_'+self.sid(101),cliSessionId=self.sid(3))))
        (self.account.parent/'linked-org').symlink_to(outside,target_is_directory=True)
        self.assertEqual(ClaudeDesktopIndex(self.desktop).snapshot(),{})

    def test_custom_transcript_profiles_cannot_borrow_the_logged_in_desktop_profile(self):
        from claude_desktop import default_directory
        from unittest.mock import patch
        with patch('claude_desktop.sys.platform','darwin'),patch('claude_desktop.Path.home',return_value=self.root):
            self.assertIsNone(default_directory(self.transcripts))
            self.assertEqual(default_directory(self.root/'.claude/projects'),self.root/'Library/Application Support/Claude/claude-code-sessions')


if __name__=='__main__':unittest.main()
