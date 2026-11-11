"""Read-only current channel verification; never upload or modify a queue."""
from pathlib import Path
import argparse, json, urllib.request
from hinglish_publish.readiness import report

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['cricket','gaming'],default='cricket');profile=parser.parse_args().profile
base='http://127.0.0.1:8765'
def get(path, token=None):
    request=urllib.request.Request(base+path,headers={'X-Hinglish-Token':token} if token else {})
    with urllib.request.urlopen(request,timeout=20) as response:return json.load(response)
token=get('/api/bridge')['token']
publisher=get('/api/publisher?profile='+profile,token)
tasks=publisher.get('tasks',[])
if isinstance(tasks,dict):tasks=list(tasks.values())
summary=[{'id':t.get('id'),'status':t.get('status'),'message':t.get('message',''),'result':t.get('result')} for t in tasks]
browser=get('/api/local-browser',token)
result=report(root,profile,online=True,browser=browser)
result['recent_tasks']=summary
result['worker_enabled']=publisher.get('worker_enabled',False)
out=root/'output/publisher-repair-2026-10-26'/('connection-after-reconnect.json' if profile=='cricket' else 'connection-gaming-current.json')
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
