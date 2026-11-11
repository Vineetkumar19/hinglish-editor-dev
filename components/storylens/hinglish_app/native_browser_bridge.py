"""Receipt-bound browser commands to the owner's existing Adobe panel.

No application launch, JSX evaluation or keyboard interception in the web server.
The installed panel uses its existing native dispatch and verifies the project.
Sent commands are never automatically replayed after an uncertain result.
"""
from pathlib import Path
import copy
import json
import re
import threading
import time
import uuid
import hashlib

ACTIONS={'context','projectContext','selectedMedia','music','import','markBeats',
         'templateImport','templateAlign','templateFonts','templateCollapseFolders',
         'templateText','copyPaste','imageDownload','downloadImport','caption3d',
         'animationPresets','presetLibrary','cinematicText','effectsLibrary',
         'clipboardWatch','copyPasteKeys','explorerSelection','shortcutWatch'}


class BrowserNativeBridge:
    def __init__(self,root,clock=time.monotonic):
        self.folder=Path(root)/'cache/editor-panel/browser-commands'
        self.clock=clock;self.lock=threading.RLock();self.sessions={};self.records={}
        self.requests=self.folder/'requests'
    def _file(self,id):
        if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Choose the saved editor action.')
        return self.folder/(id+'.json')
    def _save(self,row):
        self.folder.mkdir(parents=True,exist_ok=True)
        file=self._file(row['id']);temp=file.with_suffix('.tmp')
        temp.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8');temp.replace(file)
        self.records[row['id']]=row
        # Keep only a small recent cache; durable receipts remain on disk.
        for key in list(self.records):
            if len(self.records)<=32:break
            if self.records[key]['status'] not in ('queued','sent'):self.records.pop(key)
        return copy.deepcopy(row)
    def _request_file(self,request):
        return self.requests/(hashlib.sha256(request.encode()).hexdigest()+'.json')
    def status(self,id):
        with self.lock:
            if id not in self.records:
                file=self._file(id)
                if not file.is_file():raise ValueError('This editor action is unavailable.')
                row=json.loads(file.read_text('utf-8'))
                if row['status'] in ('queued','sent'):
                    row.update(status='unconfirmed',error='The connection restarted. Check the editor before running this action again.')
                self.records[id]=row
            row=self.records[id]
            if row['status'] in ('queued','sent') and time.time()-row['created']>(60 if row['status']=='queued' else 7200 if row['action']=='context' and row['payload'].get('appearance_cache') else 1200):
                row.update(status='unconfirmed',error='The editor has not confirmed this action. Check the project before repeating it.')
                self._save(row)
            return copy.deepcopy(row)
    def register(self,client,host,project_id):
        if host not in ('aftereffects','premiere') or not isinstance(client,str) or not 1<=len(client)<=100 or not isinstance(project_id,str) or not 1<=len(project_id)<=2048:
            raise ValueError('Connect an open Storylens Adobe panel.')
        with self.lock:
            old=self.sessions.get(client)
            row={'client':client,'lease':old['lease'] if old else uuid.uuid4().hex,
                 'host':host,'project_id':project_id,'seen':self.clock()}
            self.sessions[client]=row
            return {'client':client,'lease':row['lease']}
    def _session(self,client,lease):
        row=self.sessions.get(client)
        if not row or row['lease']!=lease:raise ValueError('Reconnect the Storylens panel.')
        row['seen']=self.clock();return row
    def connections(self):
        with self.lock:return [{k:s[k] for k in ('host','project_id')} for s in self.sessions.values() if self.clock()-s['seen']<30]
    def submit(self,value):
        action=value.get('action');payload=value.get('payload',{});request=value.get('request_id');host=value.get('host','aftereffects')
        if action not in ACTIONS or not isinstance(payload,dict) or not isinstance(request,str) or not re.fullmatch(r'[\w-]{1,100}',request) or len(json.dumps(payload))>4_000_000:
            raise ValueError('Choose a supported Storylens editor action.')
        with self.lock:
            index=self._request_file(request)
            if index.is_file():
                row=self.status(json.loads(index.read_text('utf-8'))['id'])
                if (row['action'],row['payload'],row['host'])!=(action,payload,host):raise ValueError('This request already belongs to another editor action.')
                return row
            sessions=[s for s in self.sessions.values() if s['host']==host and self.clock()-s['seen']<30]
            if len(sessions)!=1:raise ValueError('Open one Storylens panel in '+('After Effects' if host=='aftereffects' else 'Premiere Pro')+' and keep it connected, then retry.')
            session=sessions[0]
            for key in list(self.records):self.status(key)
            if any(r['status'] in ('queued','sent') and r['client']==session['client'] for r in self.records.values()):
                raise ValueError('Wait for the current editor action to finish.')
            row=self._save({'id':uuid.uuid4().hex,'request_id':request,'host':host,'action':action,'payload':copy.deepcopy(payload),
                'project_id':session['project_id'],'client':session['client'],'lease':session['lease'],
                'status':'queued','created':time.time()})
            self.requests.mkdir(parents=True,exist_ok=True)
            temp=index.with_suffix('.tmp');temp.write_text(json.dumps({'id':row['id']}),encoding='utf-8');temp.replace(index)
            return row
    def poll(self,client,lease):
        with self.lock:
            self._session(client,lease)
            rows=[r for r in self.records.values() if r['client']==client and r['lease']==lease and r['status']=='queued']
            if not rows:return {'command':None}
            row=min(rows,key=lambda r:r['created']);row['status']='sent';self._save(row)
            return {'command':copy.deepcopy(row)}
    def ack(self,client,lease,id,result=None,error=None):
        with self.lock:
            self._session(client,lease);row=self.status(id)
            if row['client']!=client or row['lease']!=lease:raise ValueError('This action belongs to another editor connection.')
            if row['status'] not in ('queued','sent'):return row
            row.update(status='failed' if error else 'confirmed',result=result,error=error,finished=time.time())
            return self._save(row)


def service(state):
    with state.lock:
        if not hasattr(state,'browser_native_bridge'):state.browser_native_bridge=BrowserNativeBridge(state.root)
        return state.browser_native_bridge


def get(handler,state,parsed):
    from urllib.parse import parse_qs
    if not handler._authorized():return handler._json(403,{'error':'Not connected'})
    bridge=service(state)
    if parsed.path.endswith('/connections'):return handler._json(200,{'connections':bridge.connections()})
    return handler._json(200,public(bridge.status(parse_qs(parsed.query).get('id',[''])[0])))


def post(handler,state,path,value):
    bridge=service(state);action=path.rsplit('/',1)[-1]
    if action=='catalog':
        from .native_catalogue import read
        return handler._json(200,read(value.get('action'),value.get('payload',{})))
    if action in ('command','register'):
        from .editor_panel import ensure_license
        ensure_license(state,value.get('host','aftereffects'))
    if action=='register':answer=bridge.register(value.get('client'),value.get('host'),value.get('project_id'))
    elif action=='poll':answer=bridge.poll(value.get('client'),value.get('lease'))
    elif action=='receipt':answer=bridge.ack(value.get('client'),value.get('lease'),value.get('id'),value.get('result'),value.get('error'))
    elif action=='command':answer=bridge.submit(value)
    else:raise ValueError('Choose a supported browser editor action.')
    return handler._json(200,public(answer) if action in ('command','receipt') else answer)


def public(row):
    return {k:row[k] for k in ('id','status','result','error','action','host') if k in row}
