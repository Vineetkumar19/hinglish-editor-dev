"""Explicit browser choices delivered to one connected Adobe timeline.

The browser cannot submit native code or arbitrary import paths. Only a typed,
checked bank choice produces a receipt-bound command. Pending operations are
durable; no receipt means no claim of insertion, and retry keeps the same ID.
"""
from pathlib import Path
import re
import threading
import time
import uuid

from hinglish_broll.recovery import read_json,write_json


class NativeChoiceMailbox:
    def __init__(self,root,contexts,*,clock=time.monotonic):
        self.root=Path(root).resolve();self.contexts=contexts;self.clock=clock
        self.folder=self.root/'cache/editor-panel/timed-mailbox'
        self.sessions={};self.lock=threading.RLock()

    def register(self,client,context_id):
        if not isinstance(client,str) or not re.fullmatch('[a-f0-9]{32}',client):
            raise ValueError('Reconnect this Storylens editor panel.')
        context=self.contexts.load(context_id)
        if context['host'] not in ('premiere','aftereffects') or context['sequence_id']=='_project_':
            raise ValueError('Connect the actual Adobe timeline or composition for B-roll.')
        with self.lock:
            session=self.sessions.get(context_id)
            if session and self.clock()-session['seen']<30 and session['client']!=client:
                raise ValueError('This timeline is already connected in another panel. Use that panel or close it first.')
            session={**(session or {}),'lease':(session or {}).get('lease',uuid.uuid4().hex),
                     'context':context,'client':client,'seen':self.clock()}
            self.sessions[context_id]=session
            return {'lease':session['lease'],'context':context}

    def _session(self,lease,client):
        rows=[s for s in self.sessions.values() if s['lease']==lease and s['client']==client]
        if len(rows)!=1:raise ValueError('Reconnect the B-roll panel in this editor.')
        rows[0]['seen']=self.clock();return rows[0]

    def connection(self,host):
        if host not in ('premiere','aftereffects'):raise ValueError('Choose an Adobe editor.')
        rows=[s for s in self.sessions.values() if s['context']['host']==host and self.clock()-s['seen']<30]
        if not rows:raise ValueError('Open Storylens in this editor, connect the intended timeline, then open its saved B-roll collection.')
        if len(rows)!=1:raise ValueError('Several timelines are connected. Keep one B-roll panel connected before sending this choice.')
        return rows[0]

    def _file(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{32}',key):
            raise ValueError('Choose the saved B-roll delivery again.')
        return self.folder/(key+'.json')

    def status(self,key):
        record=read_json(self._file(key),{})
        if record.get('id')!=key:raise ValueError('This B-roll delivery is unavailable. Retry the same choice.')
        return {k:record[k] for k in ('id','status','message','receipt') if k in record}

    def submit(self,host,value):
        from .panel_broll_choices import select_timed
        with self.lock:
            session=self.connection(host);context=session['context']
            # Never forward a caller's delivery/host/path/code override.
            request={k:value.get(k) for k in ('folder','project','slot_id','candidate_id')}
            request['state']='selected'
            result=select_timed(self.root,request['folder'],request,context)
            manifest=result['manifest'];key=manifest['operation_id'];file=self._file(key)
            old=read_json(file,{})
            if old.get('status')=='confirmed':return self.status(key)
            record={'id':key,'status':'queued','message':'Waiting for the connected editor to confirm this choice.',
                'context_id':context['id'],'manifest':manifest,'created':time.time()}
            write_json(file,record);return self.status(key)

    def poll(self,lease,client):
        with self.lock:
            session=self._session(lease,client);rows=[]
            for file in self.folder.glob('*.json'):
                record=read_json(file,{})
                if record.get('context_id')==session['context']['id'] and record.get('status') in ('queued','sent'):
                    rows.append(record)
            if not rows:return None
            record=min(rows,key=lambda r:r['created']);record['status']='sent'
            write_json(self._file(record['id']),record)
            return {'id':record['id'],'manifest':record['manifest']}

    def ack(self,lease,client,key,receipt,*,error=''):
        from .timed_choice_delivery import TimedChoiceDelivery
        with self.lock:
            session=self._session(lease,client);file=self._file(key);record=read_json(file,{})
            if record.get('context_id')!=session['context']['id']:
                raise ValueError('This delivery belongs to a different editor timeline.')
            if record.get('status')=='confirmed':return self.status(key)
            if error:
                record.update(status='unconfirmed',message='The editor has not confirmed this choice. Retry the same choice to reconcile it.',
                              technical_details=str(error)[:1600])
            else:
                accepted=TimedChoiceDelivery(self.root).accept(key,receipt,context=session['context'])
                record.update(status='confirmed',receipt=accepted,message=receipt.get('message','Editor confirmed this choice.'))
            write_json(file,record);return self.status(key)


def service(state):
    from .editor_panel import panel_service
    contexts=panel_service(state).contexts
    # The HTTP server is multithreaded. Use the existing state lock for creation.
    with state.lock:
        if not hasattr(state,'broll_native_mailbox'):
            state.broll_native_mailbox=NativeChoiceMailbox(state.root,contexts)
        return state.broll_native_mailbox
