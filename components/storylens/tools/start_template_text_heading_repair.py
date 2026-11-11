"""Submit the real owner script and fresh recovery scan to Storylens."""
import json
from pathlib import Path
import urllib.request
root=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8765'
with urllib.request.urlopen(base+'/api/bridge',timeout=20) as response:
    token=json.load(response)['token']
old=json.loads((root/'output/template-text/780d11d9727747eea2d41262/request.json').read_text('utf8'))
scan=json.loads((root/'output/template-text-repair/heading-repair-snapshot.json').read_text('utf8'))
request=urllib.request.Request(base+'/api/panel/template-text-start',data=json.dumps({'snapshot':scan,'script':old['script']}).encode(),headers={'Content-Type':'application/json','X-Hinglish-Token':token})
with urllib.request.urlopen(request,timeout=30) as response:state=json.load(response)
(root/'output/template-text-repair/heading-repair-job.json').write_text(json.dumps(state,indent=2),encoding='utf8')
print(json.dumps(state))
