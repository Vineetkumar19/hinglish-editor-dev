"""Exercise the mechanical adapter with placeholder copy, not a storyboard."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from render_one_cricaddict_sample import BINDING_JS
from hinglish_motion.render import SceneRenderer
evidence=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01/frames/00000.jpg'
out=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01/binding-smoke.json'
r=SceneRenderer(1280,720)
try:
 p=r.browser.new_page(viewport={'width':1280,'height':720},device_scale_factor=1)
 p.goto((ROOT/'hinglish_motion/web/crick_demo.html').as_uri());p.evaluate(BINDING_JS)
 p.evaluate('async url=>{const im=await img(url);for(const k of ["bowler","team","portrait","cutout"])A[k]=im;frame=async()=>im}',evidence.as_uri())
 p.evaluate('()=>{window.binding.nameFirst="TEST";window.binding.nameLast="SUBJECT";window.heroFont=100;window.heroSpacing=90}')
 rows=[]
 for chapter in range(6):
  for phase in [0.,3.,7.]:
   p.evaluate('gain=>window.binding.motionGain=gain',1 if phase==0 else 3)
   state=p.evaluate('d=>window.renderBound(d)',{'chapter':chapter,'phase':phase,'time':phase,'sourceFrame':1})
   rows.append({'chapter':chapter,'phase':phase,'photo_draws':len(state['geometry']),'screenshot_bytes':len(p.screenshot(type='jpeg',quality=80))})
 out.write_text(json.dumps({'status':'passed','frames':len(rows),'tests':rows,'placeholder_copy_only':True,'creative_output':False},indent=2),encoding='utf8')
 print('Passed 18 real browser frames across all six existing rigs',flush=True)
finally:r.close()
