"""Saved asynchronous Template Text jobs. No native editor operations in this process."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from .template_text_model import validate_snapshot,signature

TERMINAL={'ready','applied','failed','cancelled'}
SERVICES={};LOCK=threading.RLock()

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.'+uuid.uuid4().hex[:8]+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8');os.replace(temp,path)

class TemplateTextJobs:
    def __init__(self,root):self.root=Path(root).resolve();self.base=self.root/'output/template-text';self.lock=threading.RLock();self.processes={}
    def folder(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{24}',key):raise ValueError('Template Text: choose the current saved text pass.')
        return self.base/key
    def snapshot(self,key):
        folder=self.folder(key)
        if not (folder/'status.json').is_file():raise ValueError('Template Text: this saved pass is unavailable. Run it again.')
        value=json.loads((folder/'status.json').read_text('utf8'))
        if (folder/'cancel').exists() and value.get('status')!='applied':return {**value,'status':'cancelled','stage':'Stopped. Your project is unchanged.'}
        # Persisted workers outlive an idle service reload; distinguish a real
        # worker exit from an unfinished request rather than showing endless loading.
        proc=self.processes.get(key)
        if proc is None and value.get('status') not in TERMINAL and (folder/'worker-lease.json').is_file():
            lease=json.loads((folder/'worker-lease.json').read_text('utf8'))
            try:
                import psutil
                worker=psutil.Process(lease['pid']);args=worker.cmdline()
                alive=abs(worker.create_time()-lease['started'])<20 and 'hinglish_app.template_text_worker' in args and key in args
            except (ImportError,KeyError,OSError):alive=True
            except Exception:alive=False
            if not alive:
                value={**value,'status':'failed','stage':'The local text worker stopped. Run Template Text again; your project is unchanged.'};save(folder/'status.json',value)
        if value.get('status') not in TERMINAL and proc is not None and proc.poll() is not None:
            value={**value,'status':'failed','stage':'The local text worker stopped. Run Template Text again; your project is unchanged.','error':{'message':'The local text worker stopped. Run Template Text again; your project is unchanged.','details':'Worker exit '+str(proc.returncode)}};save(folder/'status.json',value)
        return value
    def start(self,value):
        script=value.get('script','')
        if not isinstance(script,str) or not script.strip() or len(script)>100000:raise ValueError('Template Text: paste the final spoken script in Script & timeline first (up to 100,000 characters).')
        scan=value.get('snapshot');override=value.get('narration_path','')
        if override:
            from .template_text_audio import local_file
            override=str(local_file(override));scan={**scan,'audio':[{'path':override,'start':0,'end':scan['duration'],'source_in':0,'rate':1,'gain':1}],'warnings':[w for w in scan.get('warnings',[]) if not w.lower().startswith('audio:')]}
        scan=validate_snapshot(scan)
        if any('audio:' in str(w).lower() for w in scan.get('warnings',[])) and not override:raise ValueError('Template Text audio: the final mix contains unsupported effects or remapping. Choose the final narrated video/audio in Settings; no project edits were made.')
        from hinglish_cut.model_preferences import preferences
        selected=preferences(self.root);python=Path(selected.get('cuda_runtime_python') or sys.executable)
        if not python.is_file():raise ValueError('Template Text runtime: the selected local model runtime is unavailable. Check model settings.')
        with self.lock:
            self.base.mkdir(parents=True,exist_ok=True)
            for folder in self.base.iterdir():
                if folder.is_dir() and re.fullmatch('[a-f0-9]{24}',folder.name) and (folder/'status.json').exists():
                    state=self.snapshot(folder.name)
                    prior=json.loads((folder/'request.json').read_text('utf8')) if (folder/'request.json').is_file() else {}
                    if state['status'] in ('queued','running','ready') and prior.get('snapshot_sha256')==signature(scan) and prior.get('script')==script.strip():return state
                    if state['status'] not in TERMINAL:raise ValueError('Template Text busy: wait for the current text pass or press Stop before starting another.')
            key=uuid.uuid4().hex[:24];folder=self.folder(key);folder.mkdir();save(folder/'request.json',{'version':1,'id':key,'script':script.strip(),'snapshot':scan,'snapshot_sha256':signature(scan)})
            status={'id':key,'status':'queued','stage':'Waiting for the local models…','progress':0,'created':time.time()};save(folder/'status.json',status)
            log=(folder/'worker.log').open('wb')
            try:proc=subprocess.Popen([str(python),'-E','-X','utf8','-m','hinglish_app.template_text_worker','--root',str(self.root),'--id',key],cwd=self.root,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except Exception:
                save(folder/'status.json',{**status,'status':'failed','stage':'The local text worker could not start. Check model settings and retry.'});raise
            finally:log.close()
            self.processes[key]=proc;save(folder/'worker-lease.json',{'pid':proc.pid,'started':time.time(),'root':str(self.root),'id':key})
            return status
    def cancel(self,key):
        with self.lock:
            folder=self.folder(key);status=self.snapshot(key)
            if status['status']=='applied':return status
            (folder/'cancel').touch();proc=self.processes.get(key)
            if proc is not None and proc.poll() is None:
                try:proc.terminate()
                except OSError:pass
            status={**status,'status':'cancelled','stage':'Stopped. Your project is unchanged.','progress':0};save(folder/'status.json',status);return status
    def plan(self,key):
        folder=self.folder(key);state=self.snapshot(key)
        if state['status'] not in ('ready','applied') or (folder/'cancel').exists():raise ValueError('Template Text: wait for the plan to finish before applying it.')
        return json.loads((folder/'plan.json').read_text('utf8'))
    def accept(self,key,receipt):
        plan=self.plan(key)
        if not isinstance(receipt,dict) or not receipt.get('ok') or any(str(receipt.get(k))!=str(plan[k]) for k in ('job_id','project_id','composition_id')):raise ValueError('Template Text: After Effects has not confirmed this pass. Check the project before retrying.')
        save(self.folder(key)/'native-receipt.json',receipt);state=self.snapshot(key);state.update(status='applied',stage='Template text updated.',receipt=receipt,progress=100);save(self.folder(key)/'status.json',state);return state

def service(root):
    key=str(Path(root).resolve())
    with LOCK:
        if key not in SERVICES:SERVICES[key]=TemplateTextJobs(root)
        return SERVICES[key]
