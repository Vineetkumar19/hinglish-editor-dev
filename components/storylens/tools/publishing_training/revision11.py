"""Full-context correction; preserve creator profile instead of hiding it."""
import copy,json,sys,hashlib
from tools.publishing_training import revision9 as v9,revision10 as v10
ROOT=v9.ROOT
OUT=ROOT/'output/publishing-training/20261030-v11'
def build():
 if OUT.exists():raise RuntimeError('Preserve frozen dataset')
 (OUT/'dataset').mkdir(parents=True)
 production=v10.read(v9.OUT/'dataset/production-replay.jsonl')
 train=copy.deepcopy(production)
 for r in train:r['id']='v11-full-teaching-'+r['id']
 train+=v10.read(v10.OUT/'dataset/train.jsonl')[::10]
 def sample(subject,theme,domain,index,held=False):
  original=production[index%len(production)];data=json.loads(original['messages'][1]['content'])
  data['checked_topic']={'title':subject+' '+theme,'description':f'This excerpt discusses {theme} involving {subject}. No exact year, score, record, trophy total or player name is verified.','tags':[subject,theme,domain]}
  data['correction']='Omit all dates, scores, quantities, records and uncertain details. Keep the supported central topic and use individual word tokens.'
  data['rejected_draft']={'caption_words':[subject,'sets records','in','2027'],'instagram_hashtags':['WorldRecord']}
  answer={'caption_words':[*subject.split(),theme,'takes','the','spotlight.'],'instagram_hashtags':[''.join(subject.split()),theme.title(),domain]}
  r=v9.row(f'v11-{"held" if held else "train"}-{index}',original['messages'][0]['content'],data,answer)
  r.update(required_subject=subject,theme=theme,full_creator_context_preserved=True)
  return r
 for i,(s,t,d) in enumerate([('Kolkata','batting','Cricket'),('Mumbai','bowling','Cricket'),('Punjab','teamwork','Cricket'),('Chennai','fielding','Cricket'),('Lucknow','leadership','Cricket'),('Hyderabad','batting','Cricket'),('Royal Challengers Bengaluru','batting','Cricket'),('Gujarat','bowling','Cricket'),('Delhi','teamwork','Cricket')]):
  train.append(sample(s,t,d,i))
 held=[sample(s,t,d,i,True) for i,(s,t,d) in enumerate([('Rajasthan Royals','fielding','Cricket'),('Sunrisers Hyderabad','teamwork','Cricket'),('Punjab Kings','leadership','Cricket'),('Chennai Super Kings','bowling','Cricket'),('Gujarat Titans','batting','Cricket'),('Delhi Capitals','fielding','Cricket')])]
 for name,rows in [('train',train),('holdout',held),('production-replay',production),('acceptance',v10.read(v10.OUT/'dataset/holdout.jsonl')+v10.read(v10.OUT/'dataset/acceptance.jsonl'))]:
  (OUT/f'dataset/{name}.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf8')
 info=dict(train=len(train),heldout=len(held),full_context=True,max_seq_length=8192,actual_production_replay_is_seen=True,parent='20261030-v10',auto_deploy=False,live_actions=False)
 info['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'dataset').glob('*.jsonl')}
 (OUT/'curriculum.json').write_text(json.dumps(info,indent=2),encoding='utf8');print(json.dumps(info))
if __name__=='__main__':
 if '--evaluate' in sys.argv:
  from tools.publishing_training import evaluate as e
  v9.OUT=OUT;e.CONTEXT_SIZE=8192
  if '--regression' in sys.argv:
   e.DATASET='acceptance';e.PREFIX='acceptance-';e.COMPARE_BASE=False
  v9.evaluate()
 else:build()
