"""Hash existing project records outside the authorized first-video addition."""
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01'

def snapshot():
 digest=hashlib.sha256();count=0
 with sqlite3.connect(ROOT/'library/creator-profiles/editing-dna.sqlite3') as db:
  for row in db.execute("SELECT * FROM records WHERE NOT(style='crick-edit-editing-style' AND source='single-video/reference-01') ORDER BY id"):
   for cell in row:
    value=cell if isinstance(cell,bytes) else json.dumps(cell,ensure_ascii=False).encode('utf8')
    digest.update(len(value).to_bytes(8,'big'));digest.update(value)
   count+=1
 files=[ROOT/'library/creator-profiles/documentary-memory/preferences.json',
        ROOT/'library/creator-profiles/documentary-memory/manifest.json',
        ROOT/'library/creator-profiles/crick-edit-editing-style.json',
        ROOT/'library/creator-profiles/beneath-documentary-edit.json']
 files+=list((ROOT/'library/creator-profiles/documentary-memory/brains').glob('*.md'))
 return {'outside_first_video_records':count,'outside_first_video_sha256':digest.hexdigest(),
  'preference_and_style_files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}}

def main():
 current=snapshot();baseline=OUT/'preservation-baseline.json'
 if not baseline.exists():baseline.write_text(json.dumps(current,indent=2),encoding='utf8');print('Saved existing record and preference baseline');return
 prior=json.loads(baseline.read_text(encoding='utf8'))
 receipt={'outside_first_video_records_unchanged':current['outside_first_video_sha256']==prior['outside_first_video_sha256'],
  'preferences_styles_and_brains_unchanged':current['preference_and_style_files']==prior['preference_and_style_files'],
  'before':prior,'after':current}
 (OUT/'preservation-verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
 print(json.dumps({k:v for k,v in receipt.items() if isinstance(v,bool)}))
 if not all(v for v in receipt.values() if isinstance(v,bool)):raise ValueError('Existing records or preferences changed; inspect before claiming preservation')

if __name__=='__main__':main()
