"""Use Storylens' existing browser adapter for account inspection only."""
from pathlib import Path
import json,urllib.request,sys
root=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8765'
def request(path,token=None,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    headers={'Content-Type':'application/json'}
    if token:headers['X-Hinglish-Token']=token
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=20) as response:return json.load(response)
token=request('/api/bridge')['token']
snapshot=request('/api/local-browser',token)
out=root/'output/publisher-repair-2026-10-26/instagram-inspection.json'
if '--start' in sys.argv:
    if any(j.get('status') in ('queued','running','sharing') for j in snapshot.get('jobs',[])):
        raise SystemExit('Existing Chrome work is active; account check not started.')
    if not snapshot.get('connected'):raise SystemExit('Chrome bridge is offline; no account check started.')
    result=request('/api/local-browser/inspect',token,{'profile':'cricket'} if '--cricket' in sys.argv else {})
    out.write_text(json.dumps({'id':result['id'],'status':'queued'},indent=2))
else:
    saved=json.loads(out.read_text());job=next(j for j in snapshot.get('jobs',[]) if j.get('id')==saved['id'])
    result={k:job.get(k) for k in ('id','action','status','account','message','result')}
    out.write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
