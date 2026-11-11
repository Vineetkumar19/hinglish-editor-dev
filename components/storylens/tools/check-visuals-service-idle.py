"""Read-only idle guard for the shared service; never restarts or stops work."""
import json
import sys
from pathlib import Path
import requests

root=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8765'
token=json.loads((root/'cache/app/bridge.json').read_text('utf-8'))['token']
session=requests.Session();session.trust_env=False
def get(path):
    response=session.get(base+path,headers={'X-Hinglish-Token':token},timeout=10)
    response.raise_for_status();return response.json()
active=[];known=set()
for folder in (root/'cache/app/jobs').iterdir():
    if folder.is_dir():known.add(folder.name)
for kind in ('broll-jobs','visuals-jobs'):
    for file in (root/'cache/app'/kind/'8765').glob('*.json'):known.add(file.stem)
for identity in sorted(known):
    response=session.get(base+'/api/jobs/'+identity,headers={'X-Hinglish-Token':token},timeout=5)
    if response.status_code==404:continue
    response.raise_for_status();job=response.json()
    if job.get('status') in ('running','queued','starting','recovering'):
        active.append({'type':'edit','id':identity,'status':job['status']})
for name,path,key in [('assistant','/api/assistant/history','chats'),('photos','/api/photos/history','jobs'),
                      ('downloader','/api/downloader/history','jobs'),('browser','/api/local-browser','jobs')]:
    data=get(path)
    rows=data.get(key,[]);rows=list(rows.values()) if isinstance(rows,dict) else rows
    for row in rows:
        if row.get('status') in ('running','queued','starting','recovering','sharing','preparing'):
            active.append({'type':name,'id':row.get('id'),'status':row['status']})
for profile in ('cricket','gaming'):
    data=get('/api/publisher?profile='+profile)
    if data.get('worker_enabled'):active.append({'type':'publisher','profile':profile,'worker_enabled':True})
    rows=data.get('tasks',[]);rows=list(rows.values()) if isinstance(rows,dict) else rows
    active.extend({'type':'publisher','profile':profile,'id':row.get('id'),'status':row['status']}
        for row in rows if row.get('status') in ('running','uploading','publishing','preparing','sharing'))
proof={'active':active,'checked_edit_ids':len(known),'idle':not active}
folder=root/'output/visuals/website-manual-app-evidence-20261029';folder.mkdir(parents=True,exist_ok=True)
(folder/'service-idle.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
sys.exit(0 if not active else 2)
