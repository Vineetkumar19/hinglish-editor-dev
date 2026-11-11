"""Register only an audited, actual AE receipt with the existing local service."""
import json
from pathlib import Path
import urllib.request
import argparse

root=Path(__file__).resolve().parents[1]
folder=root/'output/template-text-repair'
parser=argparse.ArgumentParser()
parser.add_argument('--report',default='full-native-progress.json')
parser.add_argument('--output',default='full-accepted.json')
args=parser.parse_args()
result=json.loads((folder/args.report).read_text('utf-8-sig'))
if result.get('phase')!='complete' or result.get('audit',{}).get('failures'):
    raise SystemExit('The full native pass is not confirmed; no completion was recorded.')
receipt=result['result']
with urllib.request.urlopen('http://127.0.0.1:8765/api/bridge',timeout=15) as response:
    token=json.load(response)['token']
request=urllib.request.Request('http://127.0.0.1:8765/api/panel/template-text-receipt',data=json.dumps({'id':receipt['job_id'],'receipt':receipt}).encode(),headers={'Content-Type':'application/json','X-Hinglish-Token':token})
with urllib.request.urlopen(request,timeout=30) as response:
    state=json.load(response)
(folder/args.output).write_text(json.dumps(state,indent=2),encoding='utf-8')
print(json.dumps({'id':state['id'],'status':state['status'],'changed':receipt['changed'],'hidden':receipt['hidden']}))
