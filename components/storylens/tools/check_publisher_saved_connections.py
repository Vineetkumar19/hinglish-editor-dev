"""Read existing channel identities; never upload, schedule or save credentials."""
import json
from pathlib import Path
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from hinglish_publish.readiness import report

def get(path,token=None):
    request=urllib.request.Request('http://127.0.0.1:8765'+path,headers={'X-Hinglish-Token':token} if token else {})
    with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)

token=get('/api/bridge')['token']
browser=get('/api/local-browser',token)
results=[report(root,profile,online=True,browser=browser) for profile in ('cricket','gaming')]
folder=root/'output/publisher-repair-2026-10-26'
folder.mkdir(exist_ok=True)
(folder/'latest-saved-connections.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for value in results:
    yt=value['youtube'];ig=value['instagram']
    print(json.dumps({'profile':value['profile'],'youtube':{k:yt.get(k) for k in ('state','id','name','message','technical')},'instagram':{k:ig.get(k) for k in ('state','account','bridge_connected')}}))
