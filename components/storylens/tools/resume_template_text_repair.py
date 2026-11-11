"""Resume the owner's real panel request after repairing the local worker."""
import json
from pathlib import Path
import urllib.request
import argparse

root=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8765'
with urllib.request.urlopen(base+'/api/bridge',timeout=20) as response:
    token=json.load(response)['token']
parser=argparse.ArgumentParser();parser.add_argument('--stop');args=parser.parse_args()
if args.stop:
    request=urllib.request.Request(base+'/api/panel/template-text-stop',data=json.dumps({'id':args.stop}).encode(),headers={'Content-Type':'application/json','X-Hinglish-Token':token})
    with urllib.request.urlopen(request,timeout=30) as response:print(json.dumps(json.load(response)))
    raise SystemExit()
saved=json.loads((root/'output/template-text/cfc2a8c53c1a48849d290ed0/request.json').read_text('utf8'))
request=urllib.request.Request(base+'/api/panel/template-text-start',data=json.dumps({'snapshot':saved['snapshot'],'script':saved['script']}).encode(),headers={'Content-Type':'application/json','X-Hinglish-Token':token})
with urllib.request.urlopen(request,timeout=30) as response:
    state=json.load(response)
(root/'output/template-text-repair/resumed-job.json').write_text(json.dumps(state,indent=2),encoding='utf8')
print(json.dumps(state))
