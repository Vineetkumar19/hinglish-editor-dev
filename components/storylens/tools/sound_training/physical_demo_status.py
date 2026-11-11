"""Read the submitted normal Storylens job without printing bridge credentials."""
import json,sys
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-physical-sources'
if len(sys.argv)>1:
 OUT=Path(sys.argv[1]).resolve()
 if not OUT.is_relative_to((ROOT/'output/sound-training').resolve()):raise ValueError('Invalid output')
b=json.loads((ROOT/'cache/app/bridge.json').read_text())
s=requests.Session();s.trust_env=False;s.headers['X-Hinglish-Token']=b['token']
job=json.loads((OUT/'demo-submission.json').read_text())['response']['id']
r=s.get(b['url'].rstrip('/')+'/api/jobs/'+job,timeout=15);r.raise_for_status();d=r.json()
(OUT/'demo-status.json').write_text(json.dumps(d,indent=2),encoding='utf8')
print(json.dumps({k:d.get(k) for k in ('id','status','progress','stage','result')}))
print(json.dumps(d.get('logs',[])[-8:]))
