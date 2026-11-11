"""Idle-only activation, preserving the main service's exact launch flags."""
from pathlib import Path
import json
import re
import subprocess
import time
import urllib.request
import psutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/workbench-20261103';OUT.mkdir(exist_ok=True)
BASE='http://127.0.0.1:8765'
html=urllib.request.urlopen(BASE+'/downloader.html',timeout=5).read().decode()
token=re.search(r'data-token="([^"]+)"',html)[1]
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE+path,headers={'X-Hinglish-Token':token}),timeout=5))
downloads=[j for j in get('/api/downloader/queue')['jobs'] if j['status'] in ('queued','running')]
chats=[c for c in get('/api/assistant/history')['chats'] if c.get('status') in ('running','planning','transcribing')]
# This exact unchanged orphan predates this task; it has no current execution.
recent=[c for c in chats if (c.get('id'),c.get('updated'))!=('f6c28ef79de448ab',1793219551.3453007)]
if downloads or recent:raise SystemExit('Activation deferred: a current download or chat is active.')
listeners=[c.pid for c in psutil.net_connections(kind='tcp') if c.laddr.port==8765 and c.status=='LISTEN']
if len(set(listeners))!=1:raise SystemExit('Activation deferred: could not identify one main listener.')
proc=psutil.Process(listeners[0]);args=proc.cmdline()
expected=['-E','-X','utf8','-m','hinglish_app','--root',str(ROOT),'--port','8765','--no-open','--no-publisher-worker']
if args[1:]!=expected:raise SystemExit('Activation deferred: main command changed.')
if proc.children(recursive=True):raise SystemExit('Activation deferred: main service owns an active child process.')
receipt={'before_pid':proc.pid,'checked':time.time(),'active_downloads':0,'current_chats':0,'unchanged_historical_orphans':len(chats),'command':args,'state':'reloading'}
def save(): (OUT/'activation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
save();proc.terminate();proc.wait(10)
with (OUT/'main.stdout.log').open('ab') as stdout,(OUT/'main.stderr.log').open('ab') as stderr:
    started=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),*expected],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
receipt['launcher_pid']=started.pid;save()
for attempt in range(60):
    try:
        health=get('/api/health')
        if 'browser_native_tools_v1' in health['capabilities']:
            receipt.update(state='active',health=health,verified=time.time());save();print(json.dumps({'state':'active','capabilities':health['capabilities'][-3:]}));break
    except (OSError,ValueError):pass
    time.sleep(.25)
else:
    receipt['state']='needs_recovery';save();raise SystemExit('The new service did not answer. Check main.stderr.log; saved user data is kept.')
