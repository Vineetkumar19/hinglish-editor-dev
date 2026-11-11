"""Persist the native-window observations reviewed after the full frame scan."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_crick_edit_dna import PATTERNS,build_report
from hinglish_niche.reference_dna import StyleDatabase
from hinglish_niche.style_memory import StyleEmbedder
BASE=ROOT/'output/reference-analysis/crick-edit-editing-style'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
windows=[('reference-01','1_400','history-book'),('reference-02','9_000','article-proof'),
 ('reference-03','17_000','history-roster'),('reference-04','0_500','crt-archive'),('reference-08','0_000','cutout-type')]
reviews=[]
for source,stamp,pattern in windows:
 receipt=read(BASE/source/'details'/stamp/'coverage.json')
 reviews.append({'source':source,'pattern':pattern,'window':receipt,
  'review':'Contact frames inspected at stride 3 native frames; all extracted native frames retained. Times are approximate seek-window times, not recovered keyframes.',
  'observation':next(p['observation'] for p in PATTERNS if p['id']==pattern)})
(BASE/'native-window-review.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2),encoding='utf-8')
records=[{'start':p['start'],'end':p['end'],'kind':'reviewed-pattern','text':p['name']+'. '+p['observation']+' Editing rule: '+p['application'],
 'data':{**p,'status':'Reviewed distributed and native-window contact samples; approximate timing observations, not recovered source project keyframes.'}} for p in PATTERNS]
model=StyleEmbedder(ROOT);vectors=model.encode([r['text'] for r in records])
for r,v in zip(records,vectors):r.update(vector=v,model=model.model_name)
db=StyleDatabase(ROOT/'library/creator-profiles/editing-dna.sqlite3');db.replace_source('crick-edit-editing-style','reviewed-patterns',records);db.close()
profile_path=ROOT/'library/creator-profiles/crick-edit-editing-style.json';profile=read(profile_path)
profile['learned_patterns']=PATTERNS;profile['native_motion_review']=str(BASE/'native-window-review.json')
profile['rules']=[p['application'] for p in PATTERNS]+profile['rules'][len(PATTERNS):]
profile_path.write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
dna=read(BASE/'editing-dna.json');dna['patterns']=PATTERNS;dna['native_motion_reviews']=reviews
(BASE/'editing-dna.json').write_text(json.dumps(dna,ensure_ascii=False,indent=2),encoding='utf-8')
build_report(read(BASE/'inventory.json'),read(BASE/'coverage.json'),dna['videos'])
print('Reviewed motion phases and approximate timing saved into the searchable memory and report.',flush=True)
