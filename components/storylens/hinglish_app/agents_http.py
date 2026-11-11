"""Local Agent Suite bridge. Opening the console never starts outreach."""
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
import secrets
import subprocess
import threading
import time
import uuid

SUITE=Path('D:/Agents')
PORT=8898
_guard=threading.RLock()

class Agents:
    def __init__(self,state):
        self.state=state
        self.folder=state.root/'cache/agents'
        self.folder.mkdir(parents=True,exist_ok=True)
        token_file=self.folder/'suite-token'
        if not token_file.exists():
            try:
                with token_file.open('x',encoding='utf-8') as f:f.write(secrets.token_urlsafe(32))
            except FileExistsError:pass
        self.token=token_file.read_text('utf-8').strip()
        self.port=int(os.environ.get('STORYLENS_AGENT_SUITE_PORT',PORT))
        if not 1024<=self.port<=65535:raise ValueError('Invalid Agent Suite port')
        self.base=f'http://127.0.0.1:{self.port}'
        self.process=None
        self.tasks={}
        self.active={}
        self.lock=threading.RLock()
        self._comments=None

    @property
    def comments(self):
        with self.lock:
            if self._comments is None:
                from .social_comments import SocialComments
                from hinglish_publish.instagram_comments import InstagramComments
                self._comments=SocialComments(self.state.root,instagram=InstagramComments(self.state.local_browser))
                self._comments.start()
            return self._comments

    def request(self,path,payload=None):
        request=Request(self.base+path,data=None if payload is None else json.dumps(payload).encode(),
            headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'application/json'})
        try:
            with urlopen(request,timeout=8) as response:return json.load(response)
        except HTTPError as e:
            try:value=json.loads(e.read(65536))
            except Exception:value={}
            raise ValueError(value.get('error') or value.get('reason') or f'Agent Suite returned HTTP {e.code}') from None
        except (URLError,TimeoutError,OSError):
            raise ValueError('Agent Suite is not connected. Open it below to reconnect.') from None

    def snapshot(self):
        try:
            result=self.request('/api/storylens/status')
            result.update(connected=True)
            return result
        except ValueError as e:return {'connected':False,'error':str(e),'agents':[],'connections':{}}

    def connect(self):
        with _guard:
            existing=self.snapshot()
            if existing['connected']:return existing
            script=SUITE/'scripts/storylens_server.py'
            python=SUITE/'.venv/Scripts/python.exe'
            if not script.is_file() or not python.is_file():raise ValueError('The installed Agent Suite launcher is unavailable.')
            import socket
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1',self.port))==0:
                    raise ValueError('The Agent Suite port is in use by a different session. No process was replaced.')
            env=os.environ.copy()
            env.update(DASHBOARD_TOKEN=self.token,LLM_PROVIDER='chatgpt',LLM_FALLBACK_OFFLINE='false',SUITE_CHATGPT_MODEL='gpt-6.1-sol', STORYLENS_APP_PORT=str(self.state.port))
            with (self.folder/'suite.log').open('ab') as log:
                self.process=subprocess.Popen([str(python),'-B',str(script),'--port',str(self.port)],cwd=SUITE,
                    env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            for _ in range(40):
                if self.process.poll() is not None:raise ValueError('Agent Suite could not start. Its local log has the startup error.')
                result=self.snapshot()
                if result['connected']:return result
                time.sleep(.25)
            raise ValueError('Agent Suite is still starting. Try reconnecting in a moment.')

    def console_url(self,path):
        import re
        fragment=''
        if isinstance(path,str) and '#' in path:
            path,fragment=path.split('#',1)
            if not re.fullmatch(r'[A-Za-z0-9_-]+',fragment):raise ValueError('Invalid workspace section')
        if not isinstance(path,str) or not re.fullmatch(r'/(?:|workflows(?:/[A-Za-z0-9_/-]+)?|approvals(?:/[A-Za-z0-9_.-]+)?|agent/[a-z_]+)',path):
            raise ValueError('Choose an Agent Suite workspace.')
        self.connect()
        return {'url':self.base+path+'?'+urlencode({'token':self.token})+('#'+fragment if fragment else '')}

    def start(self,action,payload):
        allowed={'check','connect','refresh','draft','send','settings','run','pause'}
        if action not in allowed:raise ValueError('Unknown comment action')
        platform=payload.get('platform');profile=payload.get('profile');comment=payload.get('comment_id')
        key=(action,platform,profile,comment)
        with self.lock:
            previous=self.active.get(key)
            if previous and self.tasks[previous]['status']=='running':return self.tasks[previous].copy()
            task={'id':uuid.uuid4().hex,'status':'running','action':action,'created':time.time()}
            self.tasks[task['id']]=task;self.active[key]=task['id']
        def work():
            try:
                service=self.comments
                if action in ('check','refresh','pause'):result=getattr(service,action)(platform,profile)
                elif action=='connect':result=service.connect(platform,profile)
                elif action in ('draft','send'):result=getattr(service,action)(platform,profile,comment)
                elif action=='settings':result=service.settings(platform,profile,payload.get('mode'),daily_cap=payload.get('daily_cap'),include_history=payload.get('include_history') is True)
                else:result=service.run(platform,profile)
                with self.lock:task.update(status='complete',result=result,finished=time.time())
            except Exception as e:
                with self.lock:task.update(status='failed',error=str(e)[:1000],finished=time.time())
        threading.Thread(target=work,daemon=True,name='storylens-comments-'+action).start()
        return task.copy()


def service(state):
    with _guard:
        if not hasattr(state,'_agent_suite'):state._agent_suite=Agents(state)
        return state._agent_suite


def get(handler,state,parsed):
    if not handler._authorized():return handler._json(403,{'error':'Not connected'})
    bridge=service(state)
    if parsed.path=='/api/agents/status':return handler._json(200,bridge.snapshot())
    if parsed.path=='/api/agents/comments/status':return handler._json(200,bridge.comments.status())
    if parsed.path=='/api/agents/task':
        key=parse_qs(parsed.query).get('id',[''])[0]
        with bridge.lock:task=bridge.tasks.get(key)
        return handler._json(200 if task else 404,task or {'error':'Task unavailable; refresh the saved comment status.'})
    return handler._json(404,{'error':'Unknown agent action'})


def post(handler,state,path,payload):
    bridge=service(state)
    if path=='/api/agents/connect':return handler._json(200,bridge.connect())
    if path=='/api/agents/open':return handler._json(200,bridge.console_url(payload.get('path','/')))
    if path=='/api/agents/run':
        bridge.connect()
        return handler._json(202,bridge.request('/api/storylens/run',{'agent':payload.get('agent')}))
    if path.startswith('/api/agents/comments/'):
        return handler._json(202,bridge.start(path.rsplit('/',1)[-1],payload))
    return handler._json(404,{'error':'Unknown agent action'})
