#!/usr/bin/env python3
"""Serve the private workbench on loopback. Explicit databases, read-only routes."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
import json
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit

from history_view import HistoryView
from context_view import ContextView
from glance_view import GlanceView
from handoff_view import HandoffView
from glance_automation import GlanceAutomation
from reading_view import ReadingView
from work_understanding import WorkUnderstanding
from project_context import ProjectContext
from runtime_identity import identity
from collector_status import read_status
from explanation import ExplanationService, ExplanationError, MESSAGES, load_config
from page_explanation_policy import enabled as page_policy_enabled
from agent_explanation import configuration, save_preferences, provider_options
from agent_setup import AgentSetup
from localization import language_context,localize,catalog

ROOT = Path(__file__).resolve().parent
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/history': ('history.html', 'text/html; charset=utf-8'),
          '/glance.js': ('glance.js', 'text/javascript; charset=utf-8'),
          '/glance.css': ('glance.css', 'text/css; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/explanation.js': ('explanation.js', 'text/javascript; charset=utf-8'),
          '/context.js': ('context.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}
ASSETS['/i18n.js']=('i18n.js','text/javascript; charset=utf-8')
ASSETS['/agent-setup.js']=('agent-setup.js','text/javascript; charset=utf-8')


class LocalHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # This service always binds to 127.0.0.1. HTTPServer's reverse hostname
        # lookup can stall on machines with different DNS/VPN configurations.
        TCPServer.server_bind(self)
        self.server_name='localhost'
        self.server_port=self.server_address[1]


def create_server(port, databases, *, synthetic=False, model_config=None, explanation_service=None, source_roots=None):
    view = HistoryView(databases)
    context = ContextView(view)
    parents={Path(p).parent.resolve() for p in databases.values()}
    directory=next(iter(parents)) if len(parents)==1 else None
    active_config=model_config or configuration(directory)
    explainer = explanation_service or ExplanationService(active_config)
    glance = GlanceView(view,{} if synthetic and source_roots is None else source_roots)
    parents={Path(p).parent.resolve() for p in databases.values()}
    glance.project_context=ProjectContext(next(iter(parents))/'work-context.json' if len(parents)==1 else None)
    directory=next(iter(parents)) if len(parents)==1 else None
    page_allowed=lambda:page_policy_enabled(directory,active_config)
    automation = GlanceAutomation(glance,explainer,page_allowed=page_allowed) if explainer else None
    reading = ReadingView(glance,explainer,automation) if explainer else None
    agent_setup = AgentSetup()

    def explanation_info():
        return dict(explainer.info(), automatic_on_open=bool(page_allowed()),
                    providers=provider_options(directory))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No session IDs or local paths in access logs.

        def do_GET(self):
            with language_context(self.headers.get('X-Yukio-Language',self.headers.get('Accept-Language','zh'))):
                return self.get()

        def get(self):
            host = self.headers.get('Host')
            allowed = {'127.0.0.1:%d' % self.server.server_port, 'localhost:%d' % self.server.server_port}
            if host not in allowed:
                return self.reply(403, b'Local access only', 'text/plain')
            if len(self.path) > 12000:
                return self.reply(400, b'Invalid request', 'text/plain')
            url = urlsplit(self.path)
            if url.path in ASSETS:
                name, mime = ASSETS[url.path]
                raw=(ROOT/'dist'/name).read_bytes()
                if name=='i18n.js':raw=('globalThis.YukioEnglish='+json.dumps(catalog(),ensure_ascii=False)+';\n').encode()+raw
                return self.reply(200,raw,mime)
            routes = {'/api/agent-status': set(), '/api/health': set(), '/api/clients': set(), '/api/groups': {'client','archive','offset','snapshot'},
                      '/api/timeline': {'client','key','before','snapshot'}, '/api/blocks': {'client','key','sequence','offset'},
                      '/api/handoffs': {'client','key','snapshot'}, '/api/context': {'client','key','snapshot','offset','filter'}, '/api/relations': {'client','key','snapshot'},
                      '/api/current':set(), '/api/glance':{'client','key'}, '/api/task-summary':{'client','key'},
                      '/api/work-understanding':{'client','key','scope'},
                      '/api/reading-history':{'client','key','snapshot','before'}}
            if url.path not in routes:
                return self.reply(404, b'Not found', 'text/plain')
            if self.headers.get('Sec-Fetch-Site') == 'cross-site' or self.headers.get('Origin', 'http://'+host) != 'http://'+host:
                return self.reply(403, b'Local access only', 'text/plain')
            if self.headers.get('X-Yukio-Workbench') != '1':
                return self.reply(403, b'Open the local workbench page', 'text/plain')
            try:
                params = parse_qs(url.query, keep_blank_values=True, max_num_fields=8)
                if set(params)-routes[url.path] or any(len(v)!=1 for v in params.values()):
                    raise ValueError('Invalid parameters')
                p = {k:v[0] for k,v in params.items()}
                for field in ('offset','snapshot','before','sequence'):
                    if field in p:
                        if not p[field].isdigit() or len(p[field])>19: raise ValueError('Invalid number')
                        p[field] = int(p[field])
                        if p[field]>=2**63: raise ValueError('Number too large')
                if 'archive' in p:
                    if p['archive'] not in ('0','1'): raise ValueError('Invalid archive')
                    p['archive'] = p['archive']=='1'
                if url.path=='/api/agent-status':result=agent_setup.inventory()
                elif url.path=='/api/current':result=glance.cards()
                elif url.path=='/api/glance':result=glance.detail(**p)
                elif url.path=='/api/task-summary':result=glance.summary(**p)
                elif url.path=='/api/work-understanding':result=WorkUnderstanding(glance).detail(**p)
                elif url.path=='/api/reading-history':result=reading.history_local(**p)
                elif url.path=='/api/handoffs':result=HandoffView(view,glance.reader).detail(**p)
                else:result = identity(databases,active_config) if url.path=='/api/health' else getattr(context if url.path in ('/api/context','/api/relations') else view, url.path.rsplit('/',1)[1])(**p)
                if url.path == '/api/clients':
                    result['mode'] = 'synthetic' if synthetic else 'local'
                    result['explanation'] = explanation_info()
                    for client in result['clients']:
                        client['recorder'] = dict(state='synthetic') if synthetic else read_status(databases[client['id']],client['id'])
                return self.reply(200, json.dumps(localize(result), ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')
            except (ValueError, TypeError, KeyError):
                return self.json_reply(400,dict(error='这段聊天暂时读不到，请重新选择聊天。'))
            except (sqlite3.Error, OSError):
                return self.json_reply(503,dict(error='暂时无法读取历史，已经保存的记录仍然保留。'))

        def do_POST(self):
            with language_context(self.headers.get('X-Yukio-Language',self.headers.get('Accept-Language','zh'))):
                return self.post()

        def post(self):
            nonlocal explainer, automation, reading, active_config
            host=self.headers.get('Host')
            allowed={'127.0.0.1:%d'%self.server.server_port,'localhost:%d'%self.server.server_port}
            if (host not in allowed or self.headers.get('Sec-Fetch-Site')=='cross-site' or
                    self.headers.get('Origin','http://'+host)!='http://'+host or self.headers.get('X-Yukio-Workbench')!='1'):
                return self.reply(403,b'Local access only','text/plain')
            if self.path not in ('/api/agent-check','/api/explanation-settings','/api/explanation-preview','/api/explanation-generate','/api/context-preview','/api/glance-preview','/api/glance-authorize','/api/glance-refresh','/api/glance-stop','/api/glance-heartbeat','/api/reading-current','/api/reading-history','/api/reading-explain','/api/reading-work'):
                return self.reply(404,b'Not found','text/plain')
            if explainer is None:
                return self.json_reply(503,dict(error='尚未配置模型，本机记录仍可查看。'))
            try:
                length=self.headers.get('Content-Length','')
                if (self.headers.get('Transfer-Encoding') or not length.isdigit() or not 1<=int(length)<=16384 or
                        self.headers.get('Content-Type','').split(';')[0]!='application/json'):
                    raise ValueError('Invalid request')
                self.connection.settimeout(5)
                data=json.loads(self.rfile.read(int(length)))
                if not isinstance(data,dict):raise ValueError('Invalid request')
                if self.path=='/api/agent-check':
                    if set(data)!={'provider'}:raise ValueError('Invalid assistant check')
                    result=agent_setup.check(data['provider'])
                elif self.path=='/api/explanation-settings':
                    if set(data)!={'provider','automatic_on_open'} or not isinstance(data['provider'],str) or type(data['automatic_on_open']) is not bool:
                        raise ValueError('Invalid explanation settings')
                    replacement=configuration(directory,data['provider'])
                    previous=explainer
                    with previous.lock:
                        if previous.retired:raise ExplanationError('busy')
                        if not data['automatic_on_open'] and data['provider']==active_config.get('agent','lan'):
                            save_preferences(directory,data['provider'],False)
                            with automation.lock:automation.grants.clear()
                            return self.json_reply(200,explanation_info())
                        if previous.running:raise ExplanationError('busy')
                        save_preferences(directory,data['provider'],data['automatic_on_open'])
                        previous.retired=True
                        # Retain the hourly budget when changing recipients.
                        explainer=ExplanationService(replacement)
                        explainer.calls=previous.calls.copy()
                        active_config=replacement
                        automation=GlanceAutomation(glance,explainer,page_allowed=page_allowed)
                        reading=ReadingView(glance,explainer,automation)
                    result=explanation_info()
                elif self.path.startswith('/api/reading-'):

                    fields={'grant','token'} if self.path=='/api/reading-explain' else {'grant','snapshot','before'} if self.path=='/api/reading-history' else {'grant','scope','part'} if self.path=='/api/reading-work' else {'grant'}
                    if 'grant' not in data or set(data)-fields or not isinstance(data['grant'],str) or len(data['grant'])>100:raise ValueError('Invalid reading selection')
                    if self.path=='/api/reading-explain':
                        if set(data)!=fields or not isinstance(data['token'],str) or len(data['token'])>100:raise ValueError('Invalid reading token')
                        result=reading.explain(**data)
                    elif self.path=='/api/reading-history':result=reading.history_page(**data)
                    elif self.path=='/api/reading-work':result=reading.work(**data)
                    else:result=reading.current(**data)
                elif self.path=='/api/glance-preview':
                    if set(data)!={'client','key'} or not all(isinstance(v,str) for v in data.values()):raise ValueError('Invalid selection')
                    observed,payload,references=glance.prepared(**data)
                    result=explainer.preview_prepared(data,payload,references)
                    result['snapshot']=observed['snapshot']
                    result['revision']=observed['revision']
                elif self.path=='/api/glance-authorize':
                    if not {'token','consent'}<=set(data) or set(data)-{'token','consent','page_owned'} or not isinstance(data['token'],str):raise ValueError('Invalid consent')
                    result=automation.authorize(data['token'],data['consent'],data.get('page_owned',False))
                elif self.path in ('/api/glance-refresh','/api/glance-stop','/api/glance-heartbeat'):
                    allowed={'grant','force'} if self.path=='/api/glance-refresh' else {'grant'}
                    if 'grant' not in data or set(data)-allowed or not isinstance(data['grant'],str) or len(data['grant'])>100 or type(data.get('force',False)) is not bool:raise ValueError('Invalid grant')
                    if self.path=='/api/glance-refresh':result=automation.refresh(data['grant'],data.get('force',False))
                    elif self.path=='/api/glance-heartbeat':result=automation.heartbeat(data['grant'])
                    else:result=automation.revoke(data['grant'])
                elif self.path=='/api/explanation-preview':
                    if set(data)!={'client','key','sequence'}:raise ValueError('Invalid selection')
                    if not isinstance(data['client'],str) or not isinstance(data['key'],str):raise ValueError('Invalid selection')
                    item,warnings=view.explanation_record(**data)
                    result=explainer.preview(data,item,warnings)
                elif self.path=='/api/context-preview':
                    if set(data)!={'client','key','snapshot'} or not isinstance(data['client'],str) or not isinstance(data['key'],str):
                        raise ValueError('Invalid context selection')
                    snapshot,facts=context.explanation_context(**data)
                    result=explainer.preview_context(data,snapshot,facts)
                else:
                    if set(data)!={'token','consent'} or not isinstance(data['token'],str) or len(data['token'])>100:
                        raise ValueError('Invalid confirmation')
                    result=explainer.generate(data['token'],data['consent'])
                return self.json_reply(200,result)
            except ExplanationError as exc:
                return self.json_reply(409,dict(error=MESSAGES.get(exc.code,'暂时无法生成说明。'),reason=exc.code))
            except (ValueError,TypeError,KeyError,RecursionError):
                return self.json_reply(400,dict(error='请求无效，请重新选择记录。'))
            except (sqlite3.Error,OSError):
                return self.json_reply(503,dict(error='暂时无法读取，已有记录没有改变。'))

        def json_reply(self,code,data):
            return self.reply(code,json.dumps(localize(data),ensure_ascii=False,allow_nan=False).encode(),'application/json; charset=utf-8')

        def reply(self, code, data, mime):
            self.send_response(code)
            for name, value in {
                'Content-Type': mime, 'Content-Length': str(len(data)), 'Cache-Control':'no-store',
                'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer',
                'Cross-Origin-Resource-Policy':'same-origin',
                'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            }.items(): self.send_header(name,value)
            self.end_headers()
            self.wfile.write(data)

    return LocalHTTPServer(('127.0.0.1',port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', type=Path)
    parser.add_argument('--claude', type=Path)
    parser.add_argument('--deepcode', type=Path)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--synthetic', action='store_true', help='Label all displayed data as simulated')
    parser.add_argument('--model-config', type=Path, help='Private LAN model configuration file; no credentials')
    args = parser.parse_args()
    databases = {k:getattr(args,k) for k in ('codex','claude','deepcode') if getattr(args,k)}
    if not databases: parser.error('Select at least one existing activity database')
    model_config=load_config(args.model_config) if args.model_config else None
    server = create_server(args.port, databases, synthetic=args.synthetic, model_config=model_config)
    print('Yukio local workbench: http://127.0.0.1:%d' % server.server_port, flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
