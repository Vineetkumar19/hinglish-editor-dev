"""Train actual planner-shaped decisions, rather than only prose explanations."""
from pathlib import Path
import json,random
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-production-decisions'
SYSTEM='You compose sound layers from observed events. Name the actual sound-producing source, never a generic action or emotion. Preserve intervals. Choose target_level_db as the final source level relative to retained original audio BEFORE separate ducking; the renderer handles category offsets. Return JSON layers, no prose. Do not invent unrelated sources. A relevant continuous source has a useful duration, not a click.'
def record(identity,data,layers):
 return dict(id=identity,messages=[dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(data)),dict(role='assistant',content=json.dumps({'layers':layers}))],rubric=['Concrete evidenced source, natural interval, final target not additive gain'])
def build():
 folder=OUT/'dataset';folder.mkdir(parents=True,exist_ok=True)
 cases=[('motorcycle engine rev and tire roll','Motorcycle riding along a wet road','foley','detail'),
 ('water slosh and wet footsteps','Person walking through shallow water','foley','detail'),
 ('broad waterfall roar and spray','Large waterfall cascading over rocks','ambience','bed'),
 ('rain pattering on leaves','Visible rain falling in forest, no lightning','ambience','bed'),
 ('mud squelch footsteps','Shoes lifting from sticky muddy path','foley','detail'),
 ('wooden footfalls','Person walking on a wooden bridge','foley','detail'),
 ('small stream burbling over stones','Small flowing stream, no faucet','ambience','bed'),
 ('cricket bat crack','Bat visibly strikes ball','foley','detail'),
 ('wind through tall grass','Visible wind moving open field grass','ambience','bed'),
 ('skateboard wheel roll','Skateboard rolling on concrete','foley','detail'),
 ('car engine acceleration','Car accelerating away','foley','detail'),
 ('gentle surf washing pebbles','Shore waves washing pebble beach','ambience','bed')]
 new=[]
 for i,(sound,scene,family,role) in enumerate(cases):
  for v in range(3):
   start=round((i*1.73+v*.41)%14,2);duration=round(1.5+v*.7,2);identity=f'event-{i*37+v*13+19}'
   target=(-7-v if family=='foley' else -14-v*2)
   if 'cricket' in sound:duration=.8
   data={'events':[dict(id=identity,time=start,end=round(start+duration,2),kind=family,precision='visual_interval',label=scene,sound_evidence=sound)],'source_audio':'Retain existing song once. No new music. Physical sounds should be audible.','mix_level_contract':{'target_level_db':'Final source-relative level before separate ducking. Do not add category base again.','category_base_db':{family:-10 if family=='foley' else -18}},'output_fields':['event_id','role','type','intent','why','strength','offset','duration','duration_reason','target_level_db']}
   layer=dict(event_id=identity,role=role,type=family,intent=sound,why='The observed mechanism supports this source; no unrelated action is added.',strength=2,offset=0,duration=duration,duration_reason='Retain the natural source through its observed activity.',target_level_db=target)
   new.append(record(f'production-source-{i}-{v}',data,[layer]))
 # Mix replay, retaining prior guidance on disk and in preceding trained adapter.
 prior=[json.loads(x) for x in (ROOT/'output/sound-training/20261030-physical-sources/dataset/train.jsonl').read_text(encoding='utf8').splitlines()]
 random.Random(824).shuffle(prior);train=prior[:28]+new
 held=[]
 for i,(label,sound,family,role) in enumerate([('Train wheels rolling on rails','steel wheel rumble on railway','foley','detail'),('Small waves hit a wooden jetty','lake waves gently lapping wood','ambience','bed')]):
  data={'events':[dict(id=f'unseen-{97+i}',time=4,end=7,kind=family,precision='visual_interval',label=label,sound_evidence=sound)],'source_audio':'Existing song retained. Make the observed source audible.','mix_level_contract':{'target_level_db':'Final relative level BEFORE ducking. Category base is not added again.'},'output_fields':['event_id','role','type','intent','why','strength','offset','duration','duration_reason','target_level_db']}
  held.append(record(f'production-heldout-{i}',data,[dict(event_id=f'unseen-{97+i}',role=role,type=family,intent=sound,why='Observed source',strength=2,offset=0,duration=3,duration_reason='Observed continuous activity',target_level_db=-8 if family=='foley' else -16)]))
 for name,rows in [('train',train),('holdout',held)]:
  (folder/(name+'.jsonl')).write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n',encoding='utf8')
 (OUT/'curriculum.json').write_text(json.dumps(dict(prior_replay=28,new_production_examples=36,heldouts=2,parent='20261030-physical-sources',manual_video_timeline_supplied=False),indent=2))
 print(len(train),'training examples')
if __name__=='__main__':build()
