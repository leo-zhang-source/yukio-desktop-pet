import hashlib
import http.client
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from launcher import core_path
sys.path.insert(0,str(core_path()))
from yukio.activity_history import ActivityHistory
from history_view import HistoryView,key_for
from glance_view import GlanceView,waiting_request
from glance_automation import GlanceAutomation
from source_context import clean,extract,operation,user_text,tool_material
from explanation import ExplanationService,ExplanationError,validate_output,encode,schema_for
from server import create_server
from test_explanation import config


def result(payload):
    anchor=payload.get('scope',{}).get('current_operation_evidence_id')
    state=payload.get('scope',{}).get('current_operation_status')
    content={'failed':'查看入口文件报告失败，仍需处理。','no_receipt':'请求查看入口文件，还没看到对应结果。','cancelled':'查看入口文件已取消。','conflict':'查看入口文件的结果有冲突。','unresolved':'查看入口文件的对应关系不清楚。','unknown':'查看入口文件，已收到结果，是否成功还不清楚。'}.get(state,'查看入口文件，准备简化首页。')
    bridge=payload['scope'].get('context_bridge_evidence_ids',[])
    goal=payload['scope'].get('project_goal_evidence_id')
    return [dict(part='content',text=content,basis='inference' if bridge else payload['facts'][1]['evidence_class'],evidence_ids=['E2']+([anchor] if anchor else [])),
            dict(part='explanation',text='这一步对应你希望页面更容易理解的要求。',basis='inference',evidence_ids=list(dict.fromkeys(['E1','E2']+([anchor] if anchor else [])+bridge))),
            dict(part='reason',text='助手说，先了解入口才能保留原来的使用方式。',basis='inference' if goal or bridge else 'assistant',evidence_ids=['E4']+([goal] if goal else []))]


class GlanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.sources=self.root/'sessions';self.sources.mkdir()
        self.path=self.sources/'demo.jsonl';self.db=self.root/'history.sqlite';self.now=2000.
        self.rows=[dict(type='session_meta',payload=dict(id='chat-one')),
            dict(type='event_msg',payload=dict(type='task_started',turn_id='turn')),
            dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='请简化首页，让我一眼看懂现在做什么。')])),
            dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我先查看入口文件。为了保留原来的使用方式，先确认页面怎样启动。')])),
            dict(type='response_item',payload=dict(type='function_call',name='Read',call_id='c',arguments=json.dumps(dict(file_path='/private/project/main.py'))))]
        self.write();self.ingest();(self.root/'session_index.jsonl').write_text(json.dumps(dict(id='chat-one',thread_name='简化雪绪首页'))+'\n')
        self.history=HistoryView({'codex':self.db});self.glance=GlanceView(self.history,{'codex':self.sources},clock=lambda:self.now)
        self.key=self.history.groups('codex')['groups'][0]['key']
    def tearDown(self):self.temp.cleanup()
    def write(self):self.path.write_text(''.join(json.dumps(dict(r,timestamp='1970-01-01T00:33:20Z'),ensure_ascii=False)+'\n' for r in self.rows))
    def ingest(self):
        store=ActivityHistory(self.db)
        try:store.ingest(self.path)
        finally:store.close()
    def detail(self):return self.glance.detail('codex',self.key)

    def test_client_scaffolding_is_not_a_user_request(self):
        for context in ('<system-reminder>Use a scratch workspace.</system-reminder>',
                        '<task-notification><summary>A subscription paused.</summary></task-notification>',
                        'This session is being continued from a previous conversation that ran out of context. Old task summary.',
                        '[Request interrupted by user for tool use]',
                        '<system-reminder>Truncated client title…'):
            with self.subTest(context=context):self.assertEqual(user_text(context),'')
        self.assertEqual(user_text('<system-reminder>Internal note.</system-reminder>\n请修复聊天列表。'),'请修复聊天列表。')
        self.assertEqual(user_text('请解释 system-reminder 是什么。'),'请解释 system-reminder 是什么。')

    def test_bad_client_title_uses_real_request_after_context_and_tool_rows(self):
        self.rows = [self.rows[0]] + [dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='<system-reminder>Internal note.</system-reminder>')])) for _ in range(8)] + self.rows[1:]
        self.write();self.ingest()
        (self.root/'session_index.jsonl').write_text(json.dumps(dict(id='chat-one',thread_name='<system-reminder>Internal note…'))+'\n')
        self.key=self.history.groups('codex')['groups'][0]['key']
        card=self.glance.cards()['cards'][0];detail=self.detail()
        self.assertIn('请简化首页',card['title']);self.assertEqual(card['title'],detail['title'])
        for value in (card['title'],detail['goal'],str(detail['work_notes'])):
            self.assertNotIn('system-reminder',value);self.assertNotIn('Internal note',value)

    def test_attached_image_envelopes_do_not_leak_into_the_short_request(self):
        request='请修正重复聊天。\n<image name=[Image #1] path="/private/'+('long-folder/'*60)+'screenshot.png">Attachment context only.</image>\n也要核对 Claude。'
        self.rows[2]['payload']['content'][0]['text']=request
        self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key']
        detail=self.detail()
        self.assertEqual(user_text(request),'请修正重复聊天。 也要核对 Claude。')
        for value in (detail['goal'],detail['goal_short']):
            self.assertIn('核对 Claude',value);self.assertNotIn('<image',value);self.assertNotIn('path=',value)
        self.assertEqual(user_text('请解释 HTML 中的 <image> 元素。'),'请解释 HTML 中的 <image> 元素。')

    def test_fallback_title_does_not_change_when_opening_a_long_chat(self):
        (self.root/'session_index.jsonl').unlink()
        def message(text,role='user'):
            return dict(type='response_item',payload=dict(type='message',role=role,content=[dict(type='input_text',text=text)]))
        self.rows=[self.rows[0]]+[message('<system-reminder>Context only.</system-reminder>') for _ in range(35)]+[message('请修复聊天列表。')]+[message('正在检查。','assistant') for _ in range(120)]+[message('还要保留搜索。')]
        self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key']
        self.assertEqual(self.glance.cards()['cards'][0]['title'],'请修复聊天列表')
        self.assertEqual(self.detail()['title'],'请修复聊天列表')

    def test_title_goal_file_and_reason_have_concrete_content(self):
        d=self.detail();self.assertEqual(d['title'],'简化雪绪首页');self.assertIn('简化首页',d['goal']);self.assertTrue(d['content'].startswith('我先查看入口文件。'));self.assertIn('还没看到结果',d['content']);self.assertIn('main.py',str(d['results']))
        self.assertIn('保留原来的使用方式',d['reason']);self.assertEqual(d['reason_basis'],'assistant')
        self.assertEqual(d['status'],'刚有新活动');self.assertNotIn('/private/',encode(d))

    def test_local_story_is_short_and_context_is_not_a_repeated_update(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='我正在简化首页。为了让你一眼看懂，先收起详细记录。')])));self.write();self.ingest()
        d=self.detail();self.assertEqual(d['content'],'我正在简化首页。');self.assertIn('调整',d['explanation']);self.assertEqual(d['explanation_basis'],'inference')
        _,payload,_=self.glance.prepared('codex',self.key);self.assertIn('为了让你一眼看懂',payload['facts'][2]['excerpt'])
        self.assertNotEqual(d['content'],d['explanation']);self.assertNotEqual(d['explanation'],d['reason'])

    def test_unknown_assistant_phase_is_not_public_text(self):
        self.assertEqual(extract('codex',dict(type='response_item',payload=dict(type='message',role='assistant',phase='new-private-phase',content=[dict(type='output_text',text='HIDDEN')]))),[])

    def test_windows_public_final_answer_replaces_commentary_and_survives_next_turn(self):
        self.rows.extend([
            dict(type='response_item',payload=dict(type='message',role='assistant',phase='final_answer',content=[dict(type='output_text',text='已整理出三项需要核对的事项。为了避免误用结果，仍需确认原始资料。')])),
            dict(type='event_msg',payload=dict(type='task_complete',turn_id='turn'))])
        self.write();self.ingest();d=self.detail()
        self.assertIn('已整理出三项',d['content'])
        self.assertEqual(d['content_basis'],'assistant')
        self.assertEqual(d['evidence']['content']['phase'],'final')
        self.assertEqual(d['status'],'这一轮已结束')
        self.assertIn('仍需确认',d['reason'])
        self.rows.append(dict(type='event_msg',payload=dict(type='task_started',turn_id='next')))
        self.write();self.ingest();d=self.detail()
        self.assertNotIn('已整理出三项',d['content'])
        self.assertIn('已整理出三项',d['previous_progress'][0]['text'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertNotIn('已整理出三项',''.join(r[0] for r in db.execute('SELECT record FROM events')))

    def test_app_mention_keeps_readable_name_and_request(self):
        request='[@Google Drive](plugin://google-drive@openai-curated-remote) review the latest project results and plans'
        self.assertEqual(user_text(request),'@Google Drive review the latest project results and plans')

    def test_read_does_not_change_history_or_copy_content_to_it(self):
        before=self.db.read_bytes();self.detail();self.glance.cards();self.assertEqual(self.db.read_bytes(),before)
        with closing(sqlite3.connect(self.db)) as db, db:records=''.join(r[0] for r in db.execute('SELECT record FROM events'))
        self.assertNotIn('简化首页',records);self.assertNotIn('main.py',records)

    def test_modified_source_does_not_supply_unverified_text(self):
        self.path.write_text(self.path.read_text().replace('main.py','evil.py'))
        d=self.detail();self.assertNotIn('evil.py',encode(d));self.assertGreater(d['source_missing'],0)

    def test_replaced_file_rejected_even_if_bytes_match(self):
        data=self.path.read_bytes();self.path.unlink();self.path.write_bytes(data)
        # Force a distinct file identity regardless of filesystem inode reuse.
        with closing(sqlite3.connect(self.db)) as db, db:
            source,state=db.execute('SELECT source_id,state FROM sources').fetchone();state=json.loads(state);state['file_identity']='other';db.execute('UPDATE sources SET state=? WHERE source_id=?',(json.dumps(state),source))
        self.assertTrue(self.detail()['source_unavailable'])

    def test_missing_source_still_names_chat_without_inventing_content(self):
        self.path.unlink();d=self.detail();self.assertEqual(d['title'],'简化雪绪首页');self.assertTrue(d['source_unavailable']);self.assertFalse(d['evidence'])

    def test_navigation_hides_missing_source_and_restores_it_when_readable(self):
        self.assertEqual(len(self.glance.cards()['cards']),1)
        parked=self.path.with_suffix('.parked');self.path.rename(parked)
        before=self.db.read_bytes()
        self.assertEqual(self.glance.cards()['cards'],[])
        self.assertEqual(len(self.history.groups('codex')['groups']),1)
        parked.rename(self.path)
        self.assertEqual(self.glance.cards()['cards'][0]['session_id'],'chat-one')
        self.assertEqual(self.db.read_bytes(),before)

    def test_navigation_hides_named_metadata_and_system_only_chats(self):
        self.rows=[self.rows[0],dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='<system-reminder>Internal context only.</system-reminder>')]))]
        self.write();self.ingest()
        self.assertEqual(self.glance.cards()['cards'],[])
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='好')])) )
        self.write();self.ingest()
        self.assertEqual(len(self.glance.cards()['cards']),1)

    def test_navigation_retains_readable_opening_when_recent_records_have_no_text(self):
        self.rows=[self.rows[0],self.rows[2]]+[dict(type='event_msg',payload=dict(type='token_count')) for _ in range(100)]
        self.write();self.ingest()
        self.assertEqual(self.glance.cards()['cards'][0]['session_id'],'chat-one')

    def test_navigation_retains_public_assistant_only_chat_but_not_reasoning_only(self):
        self.rows=[self.rows[0],self.rows[3]]+[dict(type='event_msg',payload=dict(type='token_count')) for _ in range(100)]
        self.write();self.ingest()
        self.assertEqual(len(self.glance.cards()['cards']),1)
        self.rows[1]['payload']['phase']='analysis'
        self.write();self.ingest()
        self.assertEqual(self.glance.cards()['cards'],[])

    def test_empty_recent_chats_do_not_displace_older_readable_chat(self):
        store=ActivityHistory(self.db)
        try:
            for i in range(55):
                path=self.sources/('empty-'+str(i)+'.jsonl')
                path.write_text(json.dumps(dict(type='session_meta',payload=dict(id='empty-'+str(i))))+'\n')
                store.ingest(path)
        finally:store.close()
        self.assertEqual([c['session_id'] for c in self.glance.cards()['cards']],['chat-one'])

    def test_client_title_database_is_closed_after_read(self):
        from unittest.mock import patch
        from source_context import SourceContext
        state=self.root/'state_5.sqlite'
        with closing(sqlite3.connect(state)) as db, db:
            db.execute('CREATE TABLE threads(id TEXT,title TEXT,rollout_path TEXT)')
            db.execute('INSERT INTO threads VALUES (?,?,?)',('chat-one','Windows title',str(self.path)))
        (self.root/'session_index.jsonl').unlink()
        connection=sqlite3.connect(state)
        with patch('source_context.sqlite3.connect',return_value=connection):
            title,path=SourceContext({'codex':self.sources}).title_and_path('codex','chat-one',hashlib.sha256(str(self.path.resolve()).encode()).hexdigest())
        self.assertEqual(title,'Windows title');self.assertEqual(path,self.path)
        with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')

    def test_old_generation_never_reads_new_source(self):
        parts=json.loads(__import__('base64').urlsafe_b64decode(self.key+'='*(-len(self.key)%4)));parts[1]+=1
        with self.assertRaises(ValueError):self.glance.detail('codex',key_for(parts))

    def test_same_source_wrong_session_rejected(self):
        parts=json.loads(__import__('base64').urlsafe_b64decode(self.key+'='*(-len(self.key)%4)));parts[2]='someone-else'
        with self.assertRaises(ValueError):self.glance.detail('codex',key_for(parts))

    def test_no_reasoning_or_tool_output_is_extracted(self):
        for obj in [dict(type='response_item',payload=dict(type='reasoning',text='HIDDEN')),dict(type='response_item',payload=dict(type='message',role='assistant',channel='analysis',content=[dict(type='output_text',text='HIDDEN')])),dict(type='response_item',payload=dict(type='function_call_output',output='PRIVATE OUTPUT'))]:
            self.assertEqual(extract('codex',obj),[])
        self.assertEqual(extract('claude',dict(type='assistant',message=dict(content=[dict(type='thinking',thinking='HIDDEN')]))),[])
        self.assertEqual(extract('deepcode',dict(role='tool',content='PRIVATE OUTPUT')),[])

    def test_new_turn_does_not_reuse_old_action_or_reason(self):
        self.rows.append(dict(type='event_msg',payload=dict(type='task_started',turn_id='new')));self.write();self.ingest();d=self.detail()
        self.assertNotIn('content',d['evidence']);self.assertEqual(d['reason_basis'],'unknown')

    def test_many_bookkeeping_rows_do_not_hide_user_request(self):
        for _ in range(400):self.rows.append(dict(type='event_msg',payload=dict(type='token_count')))
        self.write();self.ingest();self.assertIn('简化首页',self.detail()['goal'])

    def test_newer_assistant_update_replaces_older_operation_on_glance(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='首页已经改好，接下来检查按钮。')])));self.write();self.ingest();d=self.detail()
        self.assertIn('接下来检查按钮',d['content']);self.assertEqual(d['content_basis'],'assistant')

    def test_quiet_and_end_do_not_claim_still_working_or_task_complete(self):
        self.now+=200;self.assertEqual(self.detail()['status'],'暂时没有新消息')
        self.rows.append(dict(type='event_msg',payload=dict(type='task_complete',turn_id='turn')));self.write();self.ingest()
        self.assertEqual(self.detail()['status'],'这一轮已结束')

    def test_prompt_wrapper_and_credentials_are_filtered(self):
        self.assertEqual(user_text('<in-app-browser-context>SECRET PAGE</in-app-browser-context>\n## My request:\n请简化首页'),'请简化首页')
        self.assertEqual(user_text('# AGENTS.md instructions\nsecret instructions'),'')
        text=clean('api_key=hidden password:secrets Bearer abcdef sk-abcdefghijklmnopqrstuvwxyz person@example.com https://private.test?q=secret')
        for value in ('hidden','secrets','abcdef','person@example.com','private.test'):self.assertNotIn(value,text)

    def test_operations_do_not_echo_arbitrary_shell_or_code(self):
        self.assertEqual(operation('exec_command',{'cmd':'python3 -m unittest discover'}),'请求运行测试，检查改动是否正常')
        self.assertEqual(operation('Read',{'file_path':'/Users/private/project/foo.py'}),'请求查看 foo.py')
        self.assertIsNone(operation('exec_command',{'cmd':'curl -H "Authorization: secret" private.test'}))

    def test_all_three_clients_extract_public_speech_and_explicit_objects(self):
        examples={'claude':dict(type='assistant',sessionId='claude-chat',message=dict(role='assistant',content=[dict(type='text',text='为了确认配置，先查看说明。'),dict(type='tool_use',id='c',name='Read',input=dict(file_path='/private/config.md'))])),
            'deepcode':dict(role='assistant',sessionId='deep-chat',content='为了确认配置，先查看说明。',messageParams=dict(tool_calls=[dict(type='function',id='c',function=dict(name='read',arguments=json.dumps(dict(file_path='/private/config.md'))))]))}
        for client,obj in examples.items():
            source=self.sources/(client+'.jsonl');source.write_text(json.dumps(obj)+'\n');dbpath=self.root/(client+'.sqlite');store=ActivityHistory(dbpath);store.ingest(source,source_format=client);store.close()
            history=HistoryView({client:dbpath});glance=GlanceView(history,{client:self.sources});key=history.groups(client)['groups'][0]['key'];d=glance.detail(client,key)
            self.assertTrue(d['content'].startswith('为了确认配置，先查看说明。'));self.assertIn('还没看到结果',d['content']);self.assertIn('config.md',str(d['results']));self.assertEqual(d['reason_basis'],'assistant')

    def test_preview_freezes_actual_excerpts_but_does_not_send(self):
        data,payload,refs=self.glance.prepared('codex',self.key);sent=[];service=ExplanationService(config(),sender=lambda c,p:sent.append(p) or result(p))
        preview=service.preview_prepared(dict(client='codex',key=self.key),payload,refs);self.assertFalse(sent)
        self.assertIn('main.py',encode(preview['payload']));self.assertIn('简化首页',encode(preview['payload']));self.assertNotIn('chat-one',encode(payload));self.assertNotIn('/private/',encode(payload))
        self.assertIn('短片段',preview['excluded']);self.assertIn('不可信',preview['instructions'])
        with self.assertRaises(ExplanationError):service.generate(preview['token'],False)
        self.assertEqual(service.generate(preview['token'],True)['mode'],'model');self.assertEqual(sent,[payload])

    def test_model_response_requires_three_parts_and_valid_basis(self):
        _,payload,_=self.glance.prepared('codex',self.key);good=result(payload);self.assertEqual(validate_output(encode(dict(explanations=good)),payload),good)
        self.assertEqual(schema_for(payload)['properties']['explanations']['minItems'],3)
        for change in [dict(part='content'),dict(evidence_ids=['E99']),dict(basis='observed'),dict(text='x'*361)]:
            bad=json.loads(encode(good));bad[2].update(change)
            with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=bad)),payload)

    def test_model_failure_keeps_local_story(self):
        _,payload,refs=self.glance.prepared('codex',self.key)
        def fail(c,p):raise ExplanationError('service_unavailable')
        service=ExplanationService(config(),sender=fail);p=service.preview_prepared(dict(client='codex',key=self.key),payload,refs)
        answer=service.generate(p['token'],True);self.assertEqual(answer['mode'],'fallback');self.assertEqual(answer['explanations'],[])
        self.assertTrue(self.detail()['content'].startswith('我先查看入口文件。'));self.assertIn('还没看到结果',self.detail()['content'])

    def test_auto_consent_scope_interval_unchanged_and_stop(self):
        now=[0.];sent=[];service=ExplanationService(config(),clock=lambda:now[0],sender=lambda c,p:sent.append(p) or result(p));auto=GlanceAutomation(self.glance,service,clock=lambda:now[0])
        _,payload,refs=self.glance.prepared('codex',self.key);p=service.preview_prepared(dict(client='codex',key=self.key),payload,refs)
        with self.assertRaises(ExplanationError):auto.authorize(p['token'],False)
        token=auto.authorize(p['token'],True)['grant'];self.assertEqual(auto.refresh(token)['mode'],'waiting');self.assertFalse(sent)
        now[0]=181;self.assertEqual(auto.refresh(token)['mode'],'unchanged');self.assertFalse(sent)
        self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='Read',call_id='d',arguments=json.dumps(dict(file_path='/private/other.py')))));self.write();self.ingest()
        now[0]=362;self.assertEqual(auto.refresh(token)['mode'],'updated');self.assertEqual(len(sent),1);self.assertIn('other.py',encode(sent[0]));auto.revoke(token)
        now[0]=543
        with self.assertRaises(ExplanationError):auto.refresh(token)
        self.assertEqual(len(sent),1)

    def test_auto_grant_expires_and_cannot_authorize_old_style_preview(self):
        now=[0.];service=ExplanationService(config(),clock=lambda:now[0]);auto=GlanceAutomation(self.glance,service,clock=lambda:now[0]);_,payload,refs=self.glance.prepared('codex',self.key)
        p=service.preview_prepared(dict(client='codex',key=self.key),payload,refs);token=auto.authorize(p['token'],True)['grant'];now[0]=7201
        with self.assertRaises(ExplanationError):auto.refresh(token)
        p=service.preview_prepared('old',dict(scope={},facts=[]),[])
        with self.assertRaises(ExplanationError):auto.authorize(p['token'],True)

    def add_read_result(self,**extra):
        payload=dict(type='function_call_output',call_id='c',output=json.dumps(dict(exit_code=0,content='这里控制首页的聊天名称和活动卡片排列。')));payload.update(extra)
        self.rows.append(dict(type='response_item',payload=payload));self.write();self.ingest()

    def test_verified_read_fragment_and_result_are_in_explanation_context(self):
        self.add_read_result();d,payload,refs=self.glance.prepared('codex',self.key)
        self.assertIn('卡片排列',d['fragment']['text']);self.assertIn('不代表完整文件',d['fragment']['text'])
        self.assertIn('收到成功回执',encode(payload));self.assertIn('卡片排列',encode(payload))
        with closing(sqlite3.connect(self.db)) as db, db:self.assertNotIn('卡片排列',''.join(r[0] for r in db.execute('SELECT record FROM events')))

    def test_changed_result_never_supplies_replacement_fragment(self):
        self.add_read_result();self.path.write_text(self.path.read_text().replace('卡片排列','HACK'))
        # Source is escaped JSON; replace an ASCII result marker as well.
        self.path.write_text(self.path.read_text().replace('exit_code','exit_FAIL'))
        self.assertIsNone(self.detail()['fragment'])

    def test_unpaired_foreign_turn_or_duplicate_results_do_not_supply_fragment(self):
        self.add_read_result(turn_id='other');self.assertIsNone(self.detail()['fragment'])
        self.rows.append(self.rows[4]);self.write();self.ingest();self.add_read_result();self.assertIsNone(self.detail()['fragment'])

    def test_shell_output_is_not_a_read_file_fragment(self):
        self.rows[4]['payload'].update(name='exec_command',arguments=json.dumps(dict(cmd='echo example')));self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key'];self.add_read_result()
        d,payload,_=self.glance.prepared('codex',self.key)
        self.assertEqual(d['fragment']['material_kind'],'tool_output');self.assertIn('工具返回短片段',d['fragment']['text'])
        self.assertIn('未单独确认',d['fragment']['text']);self.assertIn('卡片排列',encode(payload))

    def test_old_reason_is_not_attached_to_a_new_public_update(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='现在开始另一项检查。')])));self.write();self.ingest()
        self.assertNotIn('保留原来的使用方式',self.detail()['reason'])

    def test_script_text_is_not_treated_as_executed_suboperations(self):
        for command in ['cat > /tmp/a.py <<END\nprint(1)\nEND','python3 - <<END\n# pytest or cat foo.py\nEND','echo "cat foo.py"','cat one.py && cat two.py']:
            self.assertIsNone(operation('exec_command',dict(cmd=command)))

    def test_meaning_revision_changes_for_goal_or_result_but_not_bookkeeping(self):
        first=self.detail()['revision'];self.rows.append(dict(type='event_msg',payload=dict(type='token_count')));self.write();self.ingest()
        self.assertEqual(first,self.detail()['revision']);self.now+=200;self.assertEqual(first,self.detail()['revision']);self.add_read_result();self.assertNotEqual(first,self.detail()['revision'])

    def test_observed_claim_cannot_borrow_status_to_promote_assistant_statement(self):
        _,payload,_=self.glance.prepared('codex',self.key);bad=result(payload);bad[0].update(basis='observed',evidence_ids=['E3','E5'])
        with self.assertRaises(ExplanationError):validate_output(encode(dict(explanations=bad)),payload)

    def test_mentioning_the_word_reason_is_not_a_purpose_statement(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='本页已经显示内容、解释、原因三部分。')])));self.write();self.ingest()
        self.assertEqual(self.detail()['reason_basis'],'unknown')

    def test_recent_steering_keeps_prior_goal_as_separate_context(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='所有更改是希望达到的效果，执行方案以原计划为主。')])));self.write();self.ingest()
        d=self.detail();self.assertIn('简化首页',d['goal']);self.assertIn('原计划为主',d['goal']);self.assertIn('后来补充',d['goal'])
        self.assertNotIn('content',d['evidence'])

    def test_claude_and_deepcode_explicit_read_fragments(self):
        examples={
            'claude':[dict(type='assistant',sessionId='fragment',message=dict(content=[dict(type='tool_use',id='read',name='Read',input=dict(file_path='/demo/intro.md'))])),dict(type='user',sessionId='fragment',message=dict(content=[dict(type='tool_result',tool_use_id='read',is_error=False,content='首页让你快速了解当前工作。')]))],
            'deepcode':[dict(role='assistant',sessionId='fragment',messageParams=dict(tool_calls=[dict(id='read',type='function',function=dict(name='Read',arguments=json.dumps(dict(file_path='/demo/intro.md'))))])),dict(role='tool',sessionId='fragment',messageParams=dict(tool_call_id='read'),content=json.dumps(dict(ok=True,content='首页让你快速了解当前工作。')))]}
        for client,rows in examples.items():
            source=self.sources/(client+'-fragment.jsonl');source.write_text(''.join(json.dumps(r)+'\n' for r in rows));dbpath=self.root/(client+'-fragment.sqlite');store=ActivityHistory(dbpath);store.ingest(source,source_format=client);store.close()
            history=HistoryView({client:dbpath});key=history.groups(client)['groups'][0]['key'];view=GlanceView(history,{client:self.sources})
            self.assertIn('快速了解',view.detail(client,key)['fragment']['text'])

    def test_invalid_tool_collection_does_not_break_text_reading(self):
        obj=dict(role='assistant',content='可显示的公开说明',messageParams=dict(tool_calls={'invalid':'shape'}))
        self.assertEqual(extract('deepcode',obj),[('assistant','可显示的公开说明')]);self.assertEqual(tool_material('deepcode',obj),([],[]))
        self.assertEqual(extract('codex',dict(type='event_msg',payload=dict(type='agent_message',channel='analysis',message='HIDDEN'))),[])

    def test_http_local_boundaries_and_context_preview(self):
        server=create_server(0,{'codex':self.db},source_roots={'codex':self.sources},explanation_service=ExplanationService(config(),sender=lambda c,p:result(p)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,body=None,headers=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port);h={'X-Yukio-Workbench':'1','Content-Type':'application/json'};h.update(headers or {});c.request(method,path,json.dumps(body) if body else None,h);r=c.getresponse();data=r.read();c.close();return r.status,data
        try:
            status,raw=request('GET','/api/current');self.assertEqual(status,200);self.assertIn('简化雪绪首页',raw.decode())
            self.assertEqual(request('GET','/api/current',headers={'Origin':'https://evil.test'})[0],403)
            status,raw=request('POST','/api/glance-preview',dict(client='codex',key=self.key));self.assertEqual(status,200);p=json.loads(raw);self.assertIn('snapshot',p)
            self.assertEqual(request('POST','/api/glance-authorize',dict(token=p['token'],consent=False))[0],409)
            self.assertEqual(request('GET','/api/glance?'+urlencode(dict(client='codex',key=self.key,path='/etc/passwd')))[0],400)
            self.assertEqual(request('GET','/history')[0],200)
        finally:server.shutdown();server.server_close();thread.join()

    def test_short_correction_is_visible_and_previous_goal_remains_background(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='先别发云端')])));self.write();self.ingest()
        d=self.detail();self.assertEqual(d['goal_short'],'先别发云端');self.assertIn('简化首页',d['goal'])
        self.assertNotIn('content',d['evidence']);self.assertEqual(d['reason_basis'],'unknown')
        _,payload,_=self.glance.prepared('codex',self.key);self.assertIn('先别发云端',payload['facts'][0]['excerpt'])

    def test_continue_keeps_goal_but_does_not_reuse_old_current_work(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='继续。')])));self.write();self.ingest()
        d=self.detail();self.assertIn('简化首页',d['goal_short']);self.assertIsNone(d['last_step']);self.assertNotIn('content',d['evidence'])

    def test_latest_step_reports_request_and_receipt_separately_from_assistant(self):
        d=self.detail();self.assertTrue(d['content'].startswith('我先查看入口文件。'));self.assertIn('还没看到结果',d['content']);self.assertIn('main.py',d['last_step']['action'])
        self.assertEqual(d['last_step']['result'],'还没看到对应结果')
        self.add_read_result();d=self.detail();self.assertEqual(d['last_step']['result'],'这次操作报告成功')
        self.assertNotIn('全部完成',encode(d['last_step']))

    def test_bookkeeping_timestamp_does_not_make_old_work_look_fresh(self):
        with self.path.open('a') as f:f.write(json.dumps(dict(timestamp='1970-01-01T00:38:20Z',type='event_msg',payload=dict(type='token_count')))+'\n')
        self.ingest();self.now=2300.;d=self.detail();self.assertEqual(d['status'],'暂时没有新消息');self.assertEqual(d['last_activity_ms'],2000000.)

    def test_later_activity_is_not_labeled_with_old_end_marker(self):
        self.rows += [dict(type='event_msg',payload=dict(type='task_complete',turn_id='turn')),dict(type='response_item',payload=dict(type='function_call',name='Read',call_id='new',arguments='{}'))]
        self.write();self.ingest();self.assertEqual(self.detail()['status'],'刚有新活动')

    def test_helper_chats_are_identified_and_follow_main_chats(self):
        p=self.sources/'helper.jsonl';p.write_text(json.dumps(dict(type='session_meta',timestamp='2026-10-24T12:00:00Z',payload=dict(id='helper',source=dict(subagent=dict(thread_spawn=dict(parent_thread_id='chat-one')))) ))+'\n'+json.dumps(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='检查首页')])) )+'\n')
        store=ActivityHistory(self.db)
        try:store.ingest(p)
        finally:store.close()
        cards=self.glance.cards()['cards'];self.assertEqual(cards[0]['session_id'],'chat-one');self.assertFalse(cards[0]['is_helper']);self.assertTrue(cards[1]['is_helper'])

    def test_chat_list_does_not_reconstruct_each_conversation(self):
        from datetime import datetime, timezone
        (self.root/'codex-workbench-status.json').write_text(json.dumps(dict(state='active',updated_at=datetime.now(timezone.utc).isoformat())))
        def forbidden(*_):raise AssertionError('Chat list must not read full task details')
        self.glance.detail=forbidden
        card=self.glance.cards()['cards'][0]
        self.assertEqual(card['session_id'],'chat-one')
        self.assertEqual(card['title'],'简化雪绪首页')
        self.assertEqual(card['activity_state'],'working')
        self.assertNotIn('goal',card);self.assertNotIn('content',card)

    def test_old_waiting_signal_clears_after_outcome_answer_or_closed_turn(self):
        request=dict(sequence=5);waiting=dict(sequence=6,reported_await_user_response=True)
        op=dict(request=request,receipts=[waiting],status='unknown')
        self.assertEqual(waiting_request([op],4,0),waiting)
        self.assertIsNone(waiting_request([op],7,0));self.assertIsNone(waiting_request([op],4,7))
        for status in ('succeeded','failed','cancelled','conflict','unresolved'):
            self.assertIsNone(waiting_request([dict(op,status=status)],4,0))
        op['receipts'].append(dict(sequence=8,reported_await_user_response=False));self.assertIsNone(waiting_request([op],4,0))

    def test_agent_tool_caption_is_labeled_as_self_report_and_does_not_execute_code(self):
        self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='js',namespace='mcp__cua_repl',call_id='ui',arguments=json.dumps(dict(title='检查首页按钮是否清楚',code='PRIVATE_SENTINEL_CODE')))))
        self.write();self.ingest();d=self.detail();self.assertIn('助手标注：检查首页按钮',d['last_step']['action'])
        _,payload,_=self.glance.prepared('codex',self.key)
        fact=next(f for f in payload['facts'] if '助手标注' in f['excerpt']);self.assertEqual(fact['evidence_class'],'assistant');self.assertNotIn('PRIVATE_SENTINEL_CODE',encode(payload))
        self.assertIsNone(operation('unrecognized.js',dict(title='fake',code='PRIVATE_SENTINEL_CODE')))

    def test_unreadable_operation_does_not_fill_home_with_generic_tool_labels(self):
        self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='unknown',call_id='x',arguments='{}')));self.write();self.ingest()
        self.assertIsNone(self.detail()['last_step']);self.assertIn('一次工具操作',str(self.detail()['results']))

    def test_negative_because_description_is_not_a_reason_for_the_current_step(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='短的要求不会再因为字数少被漏掉。')])));self.write();self.ingest()
        self.assertEqual(self.detail()['reason_basis'],'unknown')

    def test_many_recent_helpers_do_not_displace_main_chat(self):
        store=ActivityHistory(self.db)
        try:
            for i in range(12):
                p=self.sources/('helper-'+str(i)+'.jsonl')
                p.write_text(json.dumps(dict(type='session_meta',payload=dict(id='helper-'+str(i),source=dict(subagent=dict(thread_spawn=dict(parent_thread_id='chat-one'))))))+'\n')
                store.ingest(p)
        finally:store.close()
        self.assertEqual(self.glance.cards()['cards'][0]['session_id'],'chat-one')

    def test_missing_file_fragment_does_not_disable_contextual_explanation(self):
        self.rows[3]['payload']['content'][0]['text']='我先查看入口文件。'
        self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key'];d,payload,_=self.glance.prepared('codex',self.key)
        self.assertEqual(d['explanation_basis'],'inference');self.assertIn('核对现有内容',d['explanation'])
        self.assertEqual(d['reason_basis'],'inference');self.assertIn('先弄清现状',d['reason'])
        self.assertEqual(d['part_evidence']['reason'][0]['text'],'请简化首页，让我一眼看懂现在做什么。')
        self.assertIn('main.py',encode(d['part_evidence']['reason']))
        # A rule's inferred purpose is never fed back as the assistant's words.
        self.assertEqual(payload['facts'][3]['evidence_class'],'unknown');self.assertNotIn('先弄清现状',encode(payload))

    def test_visible_question_answer_is_current_steering_not_opaque_metadata(self):
        reply='<send_user_message_question_reply>\n'+json.dumps([dict(answer='解释和原因都没有。无法评估',question='PRIVATE_QUESTION',questionItemId='PRIVATE_ID')],ensure_ascii=False)+'\n</send_user_message_question_reply>'
        self.assertEqual(user_text(reply),'解释和原因都没有。无法评估')
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text=reply)])))
        self.write();self.ingest();d=self.detail()
        self.assertEqual(d['goal_short'],'解释和原因都没有。无法评估');self.assertIn('简化首页',d['goal'])
        self.assertNotIn('PRIVATE_',encode(d));self.assertNotIn('content',d['evidence'])
        for bad in ['<send_user_message_question_reply>bad</send_user_message_question_reply>', '<send_user_message_question_reply>{}</send_user_message_question_reply>']:
            self.assertEqual(user_text(bad),'')

    def test_public_causal_explanation_is_not_limited_to_the_word_because(self):
        for text in ['旧页面只在读到文件时才解释，所以日常工作经常缺少说明。','我会保留简短说明，让你能跟上当前工作。']:
            self.rows[3]['payload']['content'][0]['text']=text;self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key'];d=self.detail()
            self.assertEqual(d['reason_basis'],'assistant');self.assertEqual(d['reason'],text)

    def test_new_operation_does_not_inherit_an_older_file_fragment(self):
        self.add_read_result()
        self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='exec_command',call_id='test',arguments=json.dumps(dict(cmd='python3 -m unittest discover')))))
        self.write();self.ingest();d=self.detail()
        self.assertIsNone(d['fragment']);self.assertIn('检查改动',d['explanation']);self.assertNotIn('卡片排列',d['explanation'])

    def test_failed_test_receipt_stays_failed_in_contextual_story(self):
        self.rows[4]['payload'].update(name='exec_command',arguments=json.dumps(dict(cmd='python3 -m unittest discover')))
        self.rows[3]['payload']['content'][0]['text']='我先运行测试。'
        self.add_read_result(output=json.dumps(dict(exit_code=1)))
        self.key=self.history.groups('codex')['groups'][0]['key']
        d=self.detail();self.assertEqual(d['last_step']['result'],'这次操作报告失败')
        self.assertEqual(d['reason_basis'],'inference');self.assertNotIn('测试通过',d['explanation'])

    def test_public_plan_can_support_only_a_labeled_inferred_purpose(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='接下来检查新版的按钮。')])))
        self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key'];d=self.detail()
        self.assertIn('按助手的公开说明',d['explanation']);self.assertEqual(d['reason_basis'],'inference')
        self.assertNotIn('保留原来的使用方式',d['reason'])

    def test_contextual_fallback_does_not_guess_unreadable_script_purpose(self):
        self.rows[3]['payload']['content'][0]['text']='正在处理。'
        self.rows[4]['payload'].update(name='exec_command',arguments=json.dumps(dict(cmd='python3 - <<END\nprint("test")\nEND')))
        self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key'];d=self.detail()
        self.assertEqual(d['reason_basis'],'unknown');self.assertEqual(d['explanation_basis'],'unknown')

    def test_model_cannot_silently_omit_the_current_operation_result(self):
        _,payload,_=self.glance.prepared('codex',self.key)
        self.assertIn('current_operation_evidence_id',payload['scope'])
        bad=result(payload);bad[0]['evidence_ids']=['E2']
        with self.assertRaises(ExplanationError) as error:validate_output(encode(dict(explanations=bad)),payload)
        self.assertEqual(error.exception.code,'missing_current_result')

    def test_explanation_consent_does_not_replace_the_work_request(self):
        reply='<send_user_message_question_reply>'+json.dumps([dict(answer='同意，开启本页当前聊天的自动说明')],ensure_ascii=False)+'</send_user_message_question_reply>'
        self.assertEqual(user_text(reply),'')
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text=reply)])))
        self.write();self.ingest();d=self.detail()
        self.assertIn('简化首页',d['goal_short']);self.assertIn('content',d['evidence'])

    def test_repeated_opaque_calls_do_not_invalidate_an_explanation(self):
        self.rows=self.rows[:4]
        for i in range(4):self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='opaque',call_id='x'+str(i),arguments='{}')))
        self.write();self.ingest();self.key=self.history.groups('codex')['groups'][0]['key'];before=self.detail()['revision']
        self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='opaque',call_id='new',arguments='{}')))
        self.write();self.ingest();self.assertEqual(before,self.detail()['revision'])
        _,payload,_=self.glance.prepared('codex',self.key)
        self.assertNotIn('一次工具操作',encode(payload));self.assertNotIn('current_operation_evidence_id',payload['scope'])

    def test_initial_goal_and_prior_summary_survive_many_recent_updates(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='final',content=[dict(type='output_text',text='前一步已报告完成聊天关联，接下来整理简洁首页。')])))
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='现在让说明能接上前面的工作。')])))
        for i in range(110):self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='检查当前页面 '+str(i))])))
        self.write();self.ingest();d,payload,_=self.glance.prepared('codex',self.key)
        self.assertIn('简化首页',d['project_goals'][0]['text']);self.assertIn('聊天关联',d['previous_progress'][0]['text'])
        self.assertIn('聊天关联',encode(payload));self.assertIn('较早的要求',encode(payload))

    def test_large_user_goal_keeps_the_goal_section_not_just_the_intro(self):
        text='# 项目\n'+('介绍资料。'*180)+'\n## 三、总体开发目标\n让用户工作时一眼看懂 AI 的进展和原因。\n## 四、其他\n后面的内容'
        compact=user_text(text);self.assertIn('一眼看懂',compact);self.assertLessEqual(len(compact),801)

    def test_actual_custom_script_return_is_bounded_and_not_a_file_claim(self):
        code='text((await tools.exec_command({cmd:"cat display.py"})).output);'
        self.rows += [dict(type='response_item',payload=dict(type='custom_tool_call',name='exec',call_id='batch',input=code)),dict(type='response_item',payload=dict(type='custom_tool_call_output',call_id='batch',output=[dict(type='input_text',text='Script completed\nWall time 0.1 seconds\nOutput:\n'),dict(type='input_text',text=json.dumps(dict(exit_code=0,output='这里把原来的任务目标保留给解释功能。api_key=HIDDEN_SENTINEL'))),dict(type='input_image',image_url='PRIVATE_IMAGE')]))]
        self.write();self.ingest();d,payload,_=self.glance.prepared('codex',self.key)
        self.assertEqual(d['fragment']['material_kind'],'tool_output');self.assertIn('保留给解释',encode(payload))
        self.assertIn('未单独确认脚本',d['fragment']['text']);self.assertNotIn('HIDDEN_SENTINEL',encode(payload));self.assertNotIn('PRIVATE_IMAGE',encode(payload));self.assertNotIn('Script completed',d['fragment']['text'])
        self.assertEqual(d['last_step']['result'],'已收到结果，是否成功还不清楚')

    def test_script_change_is_a_proposal_not_an_observed_success(self):
        patch='*** Begin Patch\n*** Update File: /private/project/context.py\n@@\n- context = latest_message\n+ context = original_goal + previous_steps + latest_message\n*** End Patch'
        code='text(await tools.apply_patch('+json.dumps(patch)+'));'
        self.rows.append(dict(type='response_item',payload=dict(type='custom_tool_call',name='exec',call_id='patch',input=code)))
        self.write();self.ingest();d,payload,_=self.glance.prepared('codex',self.key)
        self.assertIn('original_goal',encode(payload));self.assertIn('尚未确认写入',encode(payload));self.assertNotIn('/private/',encode(payload))
        self.assertEqual(d['last_step']['result'],'还没看到对应结果');self.assertIsNone(d['fragment'])

    def test_foreign_custom_return_does_not_supply_a_fragment(self):
        self.rows += [dict(type='response_item',payload=dict(type='custom_tool_call',name='exec',call_id='batch',input='text((await tools.exec_command({cmd:"cat file.py"})).output);')),dict(type='response_item',payload=dict(type='custom_tool_call_output',call_id='other',output=[dict(type='input_text',text='FOREIGN_BODY')]))]
        self.write();self.ingest();_,payload,_=self.glance.prepared('codex',self.key);self.assertNotIn('FOREIGN_BODY',encode(payload))

    def test_force_refresh_reuses_consent_and_still_requires_a_live_grant(self):
        now=[0.];sent=[];service=ExplanationService(config(),clock=lambda:now[0],sender=lambda c,p:sent.append(p) or result(p));auto=GlanceAutomation(self.glance,service,clock=lambda:now[0])
        _,payload,refs=self.glance.prepared('codex',self.key);p=service.preview_prepared(dict(client='codex',key=self.key),payload,refs)
        token=auto.authorize(p['token'],True)['grant'];self.assertEqual(auto.refresh(token)['mode'],'waiting')
        self.assertEqual(auto.refresh(token,True)['mode'],'updated');self.assertEqual(len(sent),1)
        self.assertTrue(auto.refresh(token,True)['result']['cached']);self.assertEqual(len(sent),1)
        auto.revoke(token)
        with self.assertRaises(ExplanationError):auto.refresh(token,True)

    def test_project_bridge_is_separate_from_observed_activity_and_required_in_explanation(self):
        from project_context import ProjectContext
        path=self.root/'work-context.json'
        entry=dict(client='codex',key=self.key,goal='工作时扫一眼就能懂。',before='前面已报告完成记录保存。',now='现在把记录整理成说明。',next='之后检查解释质量。',source_note='用户目标与开发记录，不是原始活动。')
        path.write_text(json.dumps(dict(version=1,contexts=[entry]),ensure_ascii=False),encoding='utf-8');self.glance.project_context=ProjectContext(path)
        d,payload,refs=self.glance.prepared('codex',self.key)
        self.assertEqual(d['project_context']['goal'],entry['goal']);self.assertEqual(len(payload['scope']['context_bridge_evidence_ids']),2)
        facts={x['evidence_id']:x for x in payload['facts']}
        self.assertEqual(facts[payload['scope']['context_bridge_evidence_ids'][0]]['evidence_class'],'assistant')
        good=result(payload)
        for part in good:part['basis']='inference'
        good[1]['evidence_ids']=payload['scope']['context_bridge_evidence_ids']+[payload['scope'].get('current_operation_evidence_id') or payload['scope']['current_work_evidence_id']];good[2]['evidence_ids']+= [payload['scope']['project_goal_evidence_id']]
        self.assertEqual(validate_output(encode(dict(explanations=good)),payload),good)
        bad=json.loads(encode(good));bad[1]['evidence_ids']=[payload['scope'].get('current_operation_evidence_id') or payload['scope']['current_work_evidence_id']]
        with self.assertRaises(ExplanationError) as error:validate_output(encode(dict(explanations=bad)),payload)
        self.assertEqual(error.exception.code,'missing_project_context')
        first=d['revision'];entry['now']='继续补齐前后关联。';path.write_text(json.dumps(dict(version=1,contexts=[entry])),encoding='utf-8')
        self.assertNotEqual(first,self.detail()['revision'])

    def test_temporary_budget_wait_does_not_revoke_existing_consent(self):
        now=[0.];service=ExplanationService(config(),clock=lambda:now[0],sender=lambda c,p:result(p));auto=GlanceAutomation(self.glance,service,clock=lambda:now[0])
        _,payload,refs=self.glance.prepared('codex',self.key);p=service.preview_prepared(dict(client='codex',key=self.key),payload,refs);token=auto.authorize(p['token'],True)['grant']
        auto.refresh(token,True)
        self.rows.append(dict(type='response_item',payload=dict(type='function_call',name='Read',call_id='d',arguments=json.dumps(dict(file_path='/demo/new.py')))));self.write();self.ingest()
        with self.assertRaises(ExplanationError) as error:auto.refresh(token,True)
        self.assertEqual(error.exception.code,'rate_limited');self.assertIn(token,auto.grants)
        now[0]=61;self.assertEqual(auto.refresh(token,True)['mode'],'updated')

    def test_polite_acknowledgement_is_not_the_current_work_headline(self):
        self.rows.append(dict(type='response_item',payload=dict(type='message',role='assistant',phase='commentary',content=[dict(type='output_text',text='不会停。正在把前面的进展和当前步骤联系起来。')])));self.write();self.ingest()
        self.assertEqual(self.detail()['content'],'正在把前面的进展和当前步骤联系起来。')
