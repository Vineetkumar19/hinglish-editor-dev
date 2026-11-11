"""Correct the observed one-event bias with multi-source production targets."""
import json,random,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-multi-source'
def build():
 p=ROOT/'output/sound-training/20261030-production-decisions/dataset/train.jsonl'
 old=[json.loads(x) for x in p.read_text().splitlines()]
 singles=[r for r in old if r['id'].startswith('production-source-')]
 replay=[r for r in old if r not in singles]
 rows=replay[:20]+singles
 rng=random.Random(1341)
 for n in range(48):
  selected=rng.sample(singles,2 if n<32 else 3);events=[];layers=[]
  for i,r in enumerate(selected):
   data=json.loads(r['messages'][1]['content']);event=copy.deepcopy(data['events'][0]);layer=copy.deepcopy(json.loads(r['messages'][2]['content'])['layers'][0])
   identity=f'source-{n*29+i*41+773}';duration=round(1.3+(n%4)*.4+i*.2,2);start=round(i*3.1,2)
   event.update(id=identity,time=start,end=round(start+duration,2));layer.update(event_id=identity,duration=duration,why='This observed source belongs in this scene.',duration_reason='Continuous source through its observed interval.')
   events.append(event);layers.append(layer)
  data={'events':events,'source_audio':'Only the existing song is present; the visible physical sources need sound effects. Preserve the song once.','task':'Compose each clearly observed physical source in its own interval. Multiple events need multiple relevant layers; do not stop after the first. No unrelated sounds.','mix_level_contract':{'target_level_db':'Numeric final level before speech ducking; do not add a category reduction.'}}
  rows.append({'id':f'multi-source-{n}','messages':[copy.deepcopy(selected[0]['messages'][0]),{'role':'user','content':json.dumps(data)},{'role':'assistant','content':json.dumps({'layers':layers})}],'rubric':['All supplied real sources considered, concrete intents, full intervals, numeric levels']})
 held=[]
 for n,sources in enumerate([
  [('Turning ceiling fan','fan blades rotating and air moving','ambience','bed'),('Bicycle pedals turning','bicycle chain and wheel rolling','foley','detail')],
  [('Electric kettle visibly boiling','boiling kettle bubbling and steam hiss','foley','detail'),('Gentle waves at lakeside','gentle lake waves washing the bank','ambience','bed')]]):
  events=[dict(id=f'fresh-{n}-{i}',time=i*4.,end=i*4.+3.,kind=f,precision='visual_interval',label=label,sound_evidence=sound) for i,(label,sound,f,role) in enumerate(sources)]
  data=dict(events=events,source_audio='Only the existing song is present. Add each observed physical source. Preserve the song.',task='Return layers for the separate observed scenes; strength is an integer, offset is relative to the event, target_level_db is a numeric final relative level before ducking.')
  target=[dict(event_id=e['id'],role=role,type=f,intent=sound,why='Observed physical source',strength=2,offset=0,duration=3.,duration_reason='Full observed interval',target_level_db=-14 if f=='ambience' else -8) for e,(_,sound,f,role) in zip(events,sources)]
  held.append(dict(id=f'multi-unseen-{n}',messages=[copy.deepcopy(singles[0]['messages'][0]),dict(role='user',content=json.dumps(data)),dict(role='assistant',content=json.dumps({'layers':target}))],rubric=['Two actual sources, two scene intervals, concrete sound names, numeric gain']))
 folder=OUT/'dataset';folder.mkdir(parents=True,exist_ok=True)
 for name,items in [('train',rows),('holdout',held)]:
  (folder/(name+'.jsonl')).write_text('\n'.join(json.dumps(x) for x in items)+'\n')
 (OUT/'curriculum.json').write_text(json.dumps(dict(replay=20,single_source=36,multi_source=48,heldouts=2,parent='20261030-production-decisions',reason='Actual production probe repeatedly omitted its second physical source'),indent=2))
 print(len(rows),'training examples')
if __name__=='__main__':build()
