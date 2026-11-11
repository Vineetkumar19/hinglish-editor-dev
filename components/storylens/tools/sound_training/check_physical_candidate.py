"""Fresh candidate checks with shuffled identities; no reference answers sent."""
import json, sys, time,argparse
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/sound-training/20261030-physical-sources'
MODEL='storylens-sound:14b-physical-candidate'
CASES=[
 ('motorcycle','A moving motorcycle is visible. Choose its primary physical sound.', [('r7','keyboard click'),('b3','motorcycle accelerating'),('k9','horse hooves')],'b3'),
 ('wet_steps','A person steps through shallow puddles. Choose the footsteps.', [('p8','heels on dry pavement'),('w4','muddy puddle footsteps'),('a2','faucet water running')],'w4'),
 ('waterfall','A broad waterfall pours over rocks continuously. Choose the environmental bed.', [('f2','large close waterfall roar'),('c1','tap filling a sink'),('z8','computer notification')],'f2'),
 ('bike_reverse_order','A moving motorcycle is visible. Choose its primary physical sound.', [('u4','motorcycle accelerating'),('b3','keyboard click'),('r7','horse hooves')],'u4'),
]
def main():
 global OUT,MODEL
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--model',default=MODEL);args=parser.parse_args();OUT=args.output.resolve();MODEL=args.model
 if not OUT.is_relative_to((ROOT/'output/sound-training').resolve()):raise ValueError('Invalid output')
 from hinglish_cut.gpu_lock import gpu_lock
 session=requests.Session();session.trust_env=False
 rows=[]
 schema={'type':'object','properties':{'asset_id':{'type':'string'},'reason':{'type':'string'}},'required':['asset_id','reason'],'additionalProperties':False}
 with gpu_lock(ROOT):
  for ident,question,assets,expected in CASES:
   start=time.monotonic()
   payload={'model':MODEL,'stream':False,'think':False,'format':schema,'messages':[{'role':'system','content':'Choose one supplied sound by its actual physical source. Return JSON only.'},{'role':'user','content':json.dumps({'question':question,'assets':[dict(id=i,description=d) for i,d in assets]})}],'options':{'temperature':0,'num_ctx':4096,'num_predict':160},'keep_alive':'5m'}
   response=session.post('http://127.0.0.1:11434/api/chat',json=payload,timeout=180);response.raise_for_status()
   raw=response.json();answer=json.loads(raw['message']['content'])
   rows.append(dict(id=ident,request=payload,answer=answer,expected=expected,passed=answer.get('asset_id')==expected,seconds=round(time.monotonic()-start,2),eval_count=raw.get('eval_count')))
   (OUT/'candidate-id-checks.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
   print(ident,rows[-1]['passed'],answer,flush=True)
 if not all(r['passed'] for r in rows):raise RuntimeError('Candidate failed physical selection checks; do not activate')
if __name__=='__main__':main()
