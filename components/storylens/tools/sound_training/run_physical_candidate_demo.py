"""Submit an ordinary Storylens job. No teacher-authored scene/cue plan."""
import json, shutil, sys,argparse
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-physical-sources'
MODEL='storylens-sound:14b-physical-candidate'
def main():
 global OUT,MODEL
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--model',default=MODEL);args=parser.parse_args();OUT=args.output.resolve();MODEL=args.model
 if not OUT.is_relative_to((ROOT/'output/sound-training').resolve()):raise ValueError('Invalid output')
 checks=json.loads((OUT/'candidate-id-checks.json').read_text())
 if len(checks)!=4 or not all(x['passed'] for x in checks):raise RuntimeError('Candidate selection checks incomplete')
 if (OUT/'demo-submission.json').exists():raise RuntimeError('A demo was already submitted; inspect it instead of duplicating')
 for name in ('config.sound.local.json','config.context.local.json'):
  path=ROOT/name;backup=OUT/(name+'.before-demo')
  if not backup.exists():shutil.copy2(path,backup)
  data=json.loads(path.read_text(encoding='utf-8-sig'))
  if name=='config.sound.local.json':data['think_model']=MODEL
  else:data['features']['sound']['text_model']=MODEL
  path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
 bridge=json.loads((ROOT/'cache/app/bridge.json').read_text())
 session=requests.Session();session.trust_env=False;session.headers['X-Hinglish-Token']=bridge['token']
 payload=dict(mode='sound',profile='general',device='cuda',
  input_path='D:/Chrome Downloads/Instagram Downloader Pro/vineet_2919/vineet_2919_2026-07-09_12-29-09_3937279375509968188_6252883210 (1).mp4',
  sound_style='auto',sound_density='high',sound_music=False,sound_effects=True,sound_transitions=True,sound_layered=True,sound_remove_music=False)
 response=session.post(bridge['url'].rstrip('/')+'/api/jobs',json=payload,timeout=30);response.raise_for_status()
 result=response.json()
 (OUT/'demo-submission.json').write_text(json.dumps(dict(model=MODEL,payload=payload,response=result,teacher_cue_plan_supplied=False),indent=2),encoding='utf8')
 print(json.dumps(result))
if __name__=='__main__':main()
