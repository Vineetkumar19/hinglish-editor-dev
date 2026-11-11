"""Offline local director. Reuse approved animation code without changing it.

Qwen chooses the sequence, durations, assets, text slots and sound cues.
This adapter binds those choices to existing renderers; it creates no choreography.
"""
import hashlib, html, json, math, os, subprocess, sys, time, traceback
from pathlib import Path
from fractions import Fraction
from io import BytesIO

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/reference-analysis/local-documentary-best'
OUT.mkdir(parents=True,exist_ok=True)
MODEL='qwen3:8b'
FPS=30
ASSETS=ROOT/'output/reference-analysis/crick-edit-editing-style/demo/assets'
EFFECTS={
 'crick-book':{'chapter':0,'description':'Existing hinged book opening, portrait ink aperture, warm desk light and camera push.'},
 'crick-hero':{'chapter':1,'description':'Existing Dale Steyn cutout, oversized red name, separately timed typography and light.'},
 'crick-evidence':{'chapter':2,'description':'Existing paper field notes, three separately highlighted rows, cutout and slow camera push.'},
 'crick-tv':{'chapter':3,'description':'Existing physical CRT, short static introduction, broadcast action playback and camera push.'},
 'crick-paper':{'chapter':4,'description':'Existing torn-paper photographic masks, two depth layers, ghosted photo background and ink circle.'},
 'crick-film':{'chapter':5,'description':'Existing rounded film gate: action then reaction, camera push and closing title.'},
 'beneath-road':{'style':'map','composition':'road-travel','description':'Approved drawn timeline: camera travels right, old photos exit left, new photos enter right, depth parallax.'},
 'beneath-reel':{'style':'slate','composition':'horizontal-reel','description':'Approved aligned film windows, connected strip and shared horizontal camera motion.'},
 'beneath-cinema':{'style':'night','composition':'cinema','description':'Approved one-centred-image succession with aperture reveal, focus dissolve and photographic background.'},
 'beneath-glass':{'style':'glass','composition':'hinged-triptych','description':'Approved equal glass panels, separate opening hinges and reflective photographic background.'},
 'beneath-album':{'style':'album','composition':'turning-album','description':'Approved photographs attached to turning album pages, walnut desk and paper.'},
}
PICTURES={
 'bowler':'bowler.jpg', 'team':'team.jpg', 'portrait':'portrait.jpg', 'pointing':'pointing.jpg'
}
SOUNDS={
 'paper':'whoosh/paper_slide_mixkit1530.mp3',
 'sweep':'whoosh/short_transition_sweep_mixkit175.mp3',
 'impact':'impact/cinematic_whoosh_deep_impact_mixkit1143.mp3',
 'glitch':'glitch/small_electric_glitch_mixkit2595.mp3',
 'riser':'riser/cinematic_rumbling_swell_mixkit2664.mp3'
}
ANIMATION_FILES=['hinglish_motion/web/crick_demo.html','hinglish_motion/web/scene.html',
 'hinglish_motion/web/archive_layouts.js','hinglish_motion/web/archive_cinematic.js','hinglish_motion/web/archive_cinematic.css']

def effect_label(effect):
 labels={'book':'Historical Book','hero':'Player & Typography','evidence':'Evidence Highlights',
  'tv':'Vintage Television','paper':'Paper & Ink','film':'Film Window','road':'Road Timeline',
  'reel':'Aligned Film Reel','cinema':'Centred Photo Reveal','glass':'Hinged Glass Panels','album':'Turning Photo Album'}
 prefix,kind=effect.split('-',1)
 group='cricAddict' if prefix=='crick' else 'vineet documentry edit'
 return group+' · '+labels.get(kind,kind)

def save(name,data):
 (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def schema():
 text=lambda n:{'type':'string','maxLength':n}
 scene={'type':'object','properties':{
  'effect':{'type':'string','enum':list(EFFECTS)},
  'seconds':{'type':'integer','minimum':5,'maximum':10},
  'caption':text(26),'headline':text(20),'subline':text(26),
  'photos':{'type':'array','minItems':2,'maxItems':3,'items':{'type':'string','enum':list(PICTURES)}},
  'notes':{'type':'array','maxItems':3,'items':{'type':'object','properties':{'heading':text(16),'detail':text(26)},'required':['heading','detail']}},
  'sfx':{'type':'string','enum':['none',*SOUNDS]},
  'sfx_at':{'type':'number','minimum':0,'maximum':4},
 },'required':['effect','seconds','caption','headline','subline','photos','notes','sfx','sfx_at']}
 return {'type':'object','properties':{'scenes':{'type':'array','minItems':6,'maxItems':10,'items':scene}},'required':['scenes']}

def problems(answer):
 scenes=answer.get('scenes',[]);issues=[]
 if not 6<=len(scenes)<=10:issues.append('Return 6–10 scenes.')
 if sum(s.get('seconds',0) for s in scenes)!=60:issues.append('Scene seconds must total exactly 60.')
 keys=[s.get('effect') for s in scenes]
 if len(set(keys))!=len(keys):issues.append('Use each selected effect once: no repeated scene structure.')
 for prefix in ['crick-','beneath-']:
  if sum(str(k).startswith(prefix) for k in keys)<2:issues.append('Use at least two existing effects from each reference set.')
 for i,s in enumerate(scenes):
  if s.get('effect') not in EFFECTS:issues.append(f'Scene {i+1}: unavailable effect.')
  if not 5<=s.get('seconds',0)<=10:issues.append(f'Scene {i+1}: duration outside 5–10 seconds.')
  if s.get('sfx') not in ['none',*SOUNDS]:issues.append(f'Scene {i+1}: unknown sound cue.')
  if not 0<=s.get('sfx_at',-1)<=min(4,s.get('seconds',0)-1):issues.append(f'Scene {i+1}: sound cue time must be inside the allowed 0–4 second interval.')
  for f,n in [('caption',26),('headline',20),('subline',26)]:
   v=s.get(f,'')
   if len(v)>n:issues.append(f'Scene {i+1}: shorten {f}.')
   # Only numbers actually present in the first reference passage may be used.
   import re
   if any(vv not in {'93','439','26','5','3','10','150'} for vv in re.findall(r'\d+',v)):
    issues.append(f'Scene {i+1}: unsupported number in {f}.')
   if 'mph' in v.lower():issues.append(f'Scene {i+1}: source speed is km/h, not mph.')
   if re.search(r'\b(fastest|greatest|best ever|world record)\b',v,re.I):
    issues.append(f'Scene {i+1}: {f} asserts an unsupported superlative; use only source-supported claims, choose the replacement yourself.')
  if len(s.get('photos',[]))!=len(set(s.get('photos',[]))):issues.append(f'Scene {i+1}: do not repeat a photograph inside one scene.')
  if any(k not in PICTURES for k in s.get('photos',[])):issues.append(f'Scene {i+1}: unknown photo ID.')
  if s.get('effect')=='crick-evidence' and len(s.get('notes',[]))!=3:issues.append('The existing evidence layout needs three note rows.')
  for row in s.get('notes',[]):
   for k in ['heading','detail']:
    if 'mph' in row.get(k,'').lower():issues.append('No unsupported mph claim in notes.')
    if any(n not in {'93','439','26','5','3','10','150'} for n in re.findall(r'\d+',row.get(k,''))):issues.append('No unsupported numbers in notes.')
 return issues

def copy_slots(s):
 """Bind model copy to text placeholders already drawn by the approved template."""
 h,sub,cap=s['headline'],s['subline'],s['caption']
 maps={
  'crick-book':{'Every story':h,'has a first':sub,'page.':'','The art':h,'of pace.':sub,'Open the archive':cap},
  'crick-hero':{'A force of nature':h},
  'crick-evidence':{'Not just speed.':h},
  'crick-tv':{'THE ARCHIVE':h,'Let the action speak.':cap},
  'crick-paper':{'More than a moment.':h,'A memory.':sub},
  'crick-film':{'The art of pace.':cap,'Every moment':h,'has a story.':sub},
 }
 result=maps.get(s['effect'],{})
 if s['effect']=='crick-evidence':
  for original,row in zip([('THE RUN-UP','Build the rhythm.'),('THE RELEASE','Make the moment count.'),('THE REACTION','Let the emotion breathe.')],s['notes']):
   result[original[0]]=row['heading'];result[original[1]]=row['detail']
 return result

def main():
 import requests, numpy as np, av
 from PIL import Image,ImageDraw
 from imageio_ffmpeg import get_ffmpeg_exe
 from hinglish_niche.documentary import reference
 from hinglish_motion.render import SceneRenderer
 from hinglish_shorts.render import _Video
 from playwright.sync_api import sync_playwright
 budget=OUT/'budget-start.json'
 if not budget.exists():save('budget-start.json',{'started_unix':time.time()})
 start=json.loads(budget.read_text())['started_unix']
 receipt={'status':'running','started_unix':start,'model':MODEL,'budget_seconds':1800,
  'creative_planner':'Local Qwen3:8b','new_animation_code':False,'cloud_creative_plan':False,
  'method':'Local director chooses approved existing effects; adapter only binds fields and renders.'}
 hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ANIMATION_FILES}
 receipt['animation_hashes_before']=hashes
 def progress(message):
  receipt.update(stage=message,elapsed_seconds=time.time()-start);save('receipt.json',receipt)
  print(f'[{time.time()-start:.1f}s] {message}',flush=True)
 def remaining():
  value=1800-(time.time()-start)
  if value<=0:raise TimeoutError('Original 30-minute budget exhausted')
  return value
 inventory=json.loads((ROOT/'output/reference-analysis/crick-edit-editing-style/inventory.json').read_text(encoding='utf8'))
 source=next(v['path'] for v in inventory if v['slug']=='reference-08')
 transcript=json.loads((ROOT/'output/reference-analysis/crick-edit-editing-style/reference-08/transcript.json').read_text(encoding='utf8'))
 source_text=[{'start':v['start'],'end':v['end'],'original_hindi':v['raw_text']} for v in transcript if v['start']<60]
 memories=[]
 for key in ['crick-edit-editing-style','beneath-documentary-edit']:
  r=reference(ROOT,key);memories.append({'name':r['name'],'rules':r['rules'],'animation_settings':r.get('animation_settings',[])})
 payload={'request':'A strong 60-second cricket documentary study using BOTH saved styles. You choose all scene order, durations, text and assets. No external creative plan will replace yours.',
  'narration':source_text,'narration_note':'Only first 60 seconds of the existing source audio will play. Last transcript segment extends beyond 60: do not use unverified later facts. Original Hindi is supplied instead of corrupted roman transliteration. The identified subject is Dale Steyn, from the source filename and supplied asset provenance.',
  'memory':memories,'effects':EFFECTS,
  'photos':{'bowler':'Dale Steyn bowling, green/yellow South Africa kit','team':'South Africa players celebrating','portrait':'Dale Steyn holding/tossing a ball','pointing':'Dale Steyn pointing'},
  'render_contract':{'crick':'Reuses existing ten-second template motion, time-scaled to your 5–10-second scene. Existing cutout stays Dale Steyn. headline/subline/notes populate existing text slots. TV and film use existing seven-second action and five-second reaction excerpts; no new footage generated.',
   'beneath':'Your photos populate the selected approved composition, in your chosen order. Entries are evenly distributed across the scene, as in the approved preview. caption is the visible label.',
   'audio':'Original voice and background audio retained. You may choose restrained additional licensed local sound cues. No music or voice generation.'},
  'sound_catalogue':SOUNDS}
 save('director-input.json',payload)
 system='''You are the local documentary director. Use only the saved instructions, narration, assets and executable effects provided. Make the sequence coherent with the narration. Return JSON only. Plan 6–10 scenes, each 5–10 integer seconds, totaling EXACTLY 60 seconds. Include at least two cricAddict (crick- prefix) and two vineet documentry edit (beneath- prefix) effects. Use each effect at most ONCE. Choose the sequence yourself; do not recreate a repeated collage. Short English copy must fit existing slots. Use only explicitly narrated facts; never change km/h to mph. Notes for crick-evidence must contain exactly three {heading,detail} rows; notes for other effects may be empty. Asset identifiers belong only in photos, never in visible captions. Each photos array has two or three DIFFERENT IDs. Pick sound cues only when motivated, with sfx=none otherwise. Keep the original voice intelligible. No new animation code, new people, invented scorecards or unverified years.'''
 sess=requests.Session();sess.trust_env=False
 tag=next(x for x in sess.get('http://127.0.0.1:11434/api/tags',timeout=10).json()['models'] if x['name']==MODEL)
 receipt['model_digest']=tag['digest'];receipt['model_details']=tag['details'];calls=[]
 def ask(data,index,max_tokens,format_schema=None,system_override=None,think=False):
  body={'model':MODEL,'stream':True,'think':think,'format':format_schema or schema(),
   'options':{'num_ctx':8192,'num_predict':max_tokens,'temperature':.25,'seed':19},
   'messages':[{'role':'system','content':system_override or system},{'role':'user','content':json.dumps(data,ensure_ascii=False)}]}
  save(f'model-request-{index:02}.json',body);progress(f'Local model directing attempt {index}')
  began=time.time();content='';thinking='';final={};last=began
  with sess.post('http://127.0.0.1:11434/api/chat',json=body,stream=True,timeout=(10,min(900,remaining()))) as response:
   response.raise_for_status()
   for line in response.iter_lines():
    remaining()
    if not line:continue
    item=json.loads(line)
    if 'error' in item:raise RuntimeError(item['error'])
    content+=item.get('message',{}).get('content','')
    thinking+=item.get('message',{}).get('thinking','')
    if time.time()-last>30:
     save(f'model-partial-{index:02}.json',{'content':content,'thinking':thinking,'complete':False});progress(f'Local model {index}: {len(content)} response / {len(thinking)} reasoning characters written');last=time.time()
    if item.get('done'):final=item
  answer=json.loads(content);metrics={k:v for k,v in final.items() if k!='message'}
  metrics['elapsed_seconds']=time.time()-began;calls.append(metrics)
  save(f'model-response-{index:02}.json',{'answer':answer,'thinking':thinking,'metrics':metrics})
  receipt['model_calls']=calls;return answer
 def targeted_repair(answer):
  if remaining()<180:raise TimeoutError('Not enough original budget remains for local repair and rendering')
  progress('Local targeted repair of the completed plan; original effects and order remain local model choices')
  before=problems(answer);count=len(answer['scenes'])
  if before:
   patch_schema={'type':'object','properties':{
    'durations':{'type':'array','minItems':count,'maxItems':count,'items':{'type':'integer','minimum':5,'maximum':10}},
    'cue_times':{'type':'array','minItems':count,'maxItems':count,'items':{'type':'number','minimum':0,'maximum':4}},
    'text_changes':{'type':'array','maxItems':6,'items':{'type':'object','properties':{
     'scene':{'type':'integer','minimum':1,'maximum':count},'field':{'type':'string','enum':['headline','caption','subline']},'value':{'type':'string','maxLength':20}},'required':['scene','field','value']}}
   },'required':['durations','cue_times','text_changes']}
   patch_data={'source_hindi':source_text,'identified_subject':'Dale Steyn','scene_count':count,
    'current_durations':[s['seconds'] for s in answer['scenes']],
    'current_duration_sum':sum(s['seconds'] for s in answer['scenes']),'required_duration_sum':60,
    'each_duration_allowed_range':[5,10],'current_cue_times':[s['sfx_at'] for s in answer['scenes']],
    'invalid_text':[{'scene':i+1,'field':field,'current':s[field]} for i,s in enumerate(answer['scenes']) for field in ['headline','caption','subline'] if any(word in s[field].lower() for word in ['fastest','greatest','world record'])],
    'problems':before}
   patch=ask(patch_data,len(calls)+1,1800,patch_schema,
    'You are the SAME local editor resolving arithmetic and factual errors. Think through the constraints before returning your JSON. Return one duration and cue time per scene. Durations must each be 5–10 seconds and TOTAL EXACTLY 60; the current durations do not. Every sound time must be 0–4. Include text_changes for the invalid_text fields only. The source does NOT establish a fastest-bowler record: any occurrence of fastest/greatest/world record is unsupported and must be removed. Choose source-supported replacement wording yourself. Use English, no invented numbers, no mph. You are not changing scene order, effects, photos or animation code. Return the required JSON.',think=True)
   save('local-repair.json',patch)
   if len(patch['durations'])!=count or len(patch['cue_times'])!=count:raise ValueError('Local patch has wrong number of timing values')
   for scene,seconds,cue in zip(answer['scenes'],patch['durations'],patch['cue_times']):scene['seconds']=seconds;scene['sfx_at']=cue
   for change in patch['text_changes']:
    if not 1<=change['scene']<=count:raise ValueError('Local patch references unknown scene')
    answer['scenes'][change['scene']-1][change['field']]=change['value']
  issues=problems(answer);save('plan-checks.json',{'before_targeted_repair':before,'after_targeted_repair':issues})
  return answer,issues
 if '--render-valid-plan' in sys.argv:
  answer=json.loads((OUT/'local-plan.json').read_text(encoding='utf8'))
  for path in sorted(OUT.glob('model-response-*.json')):calls.append(json.loads(path.read_text(encoding='utf8'))['metrics'])
  receipt['model_calls']=calls;issues=problems(answer)
  progress('Rendering saved validated local plan without any new model generation')
 elif '--repair-last-answer' in sys.argv:
  records=sorted(OUT.glob('model-response-*.json'));answer=None
  for path in records:
   record=json.loads(path.read_text(encoding='utf8'));calls.append(record['metrics'])
   if 'scenes' in record['answer']:answer=record['answer']
  if answer is None:raise ValueError('No complete local scene plan to resume')
  receipt['model_calls']=calls
  answer,issues=targeted_repair(answer)
 elif '--reuse-first-answer' in sys.argv:
  recorded=json.loads((OUT/'model-response-01.json').read_text(encoding='utf8'))
  answer=recorded['answer'];calls.append(recorded['metrics']);receipt['model_calls']=calls
  progress('Resuming completed local answer with strengthened factual checks; no manual copy changes')
 else:answer=ask(payload,1,2400)
 if '--repair-last-answer' not in sys.argv and '--render-valid-plan' not in sys.argv:
  issues=problems(answer)
  save('plan-checks.json',{'attempt_1':issues})
 if issues and '--repair-last-answer' not in sys.argv and '--render-valid-plan' not in sys.argv:
  timing_or_copy=all(any(key in issue for key in ['seconds must total','unsupported superlative','sound cue time']) for issue in issues)
  if timing_or_copy:answer,issues=targeted_repair(answer)
  else:
   if remaining()<480:raise ValueError('Local plan failed checks and not enough budget remains for a correction: '+str(issues))
   answer=ask({**payload,'your_plan':answer,'fix_only_these_problems':issues},len(calls)+1,2400)
   issues=problems(answer);save('plan-checks.json',{'after_full_correction':issues})
   if issues:answer,issues=targeted_repair(answer)
 if issues:raise ValueError('Local plan is still invalid; do not silently replace it: '+str(issues))
 scenes=answer['scenes'];save('local-plan.json',answer)
 progress(f'Local model chose {len(scenes)} distinct effects; rendering unchanged approved code')
 sess.post('http://127.0.0.1:11434/api/generate',json={'model':MODEL,'keep_alive':0},timeout=30).raise_for_status()
 receipt['model_unloaded_before_render']=True
 raw=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-i',source,'-t','60','-vn','-ar','48000','-ac','2','-f','f32le','pipe:1'],check=True,capture_output=True,timeout=remaining()).stdout
 original=np.frombuffer(raw,dtype='<f4').reshape(-1,2).T.copy();mix=np.zeros((2,2880000),np.float32)
 mix[:,:min(mix.shape[1],original.shape[1])]=original[:,:mix.shape[1]]*.82
 position=0;sounds=[]
 for s in scenes:
  if s['sfx']!='none':
   path=ROOT/'library/sfx-pro'/SOUNDS[s['sfx']]
   data=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-i',str(path),'-t','2','-ar','48000','-ac','2','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=remaining()).stdout
   samples=np.frombuffer(data,dtype='<f4').reshape(-1,2).T.copy();samples*=.055/max(.01,float(abs(samples).max()))
   at=round((position+s['sfx_at'])*48000);length=min(samples.shape[1],mix.shape[1]-at)
   fade=min(2400,length);samples[:,-fade:]*=np.linspace(1,0,fade)
   mix[:,at:at+length]+=samples[:,:length];sounds.append({'at':at/48000,'asset':str(path),'source':'local model choice'})
  position+=s['seconds']
 if abs(mix).max()>.98:mix*=.98/float(abs(mix).max())
 save('audio-receipt.json',{'original_reference_audio':True,'new_music':False,'local_model_selected_effects':sounds})
 renderer=None;browser=None;writer=None;pw=None
 try:
  renderer=SceneRenderer(1280,720);browser=renderer.browser
  page=browser.new_page(viewport={'width':1280,'height':720},device_scale_factor=1)
  page.goto((ROOT/'hinglish_motion/web/crick_demo.html').as_uri())
  page.evaluate('d => window.mgLoad(d)',{'assets':ASSETS.as_uri()})
  # Substitute local model text in existing drawing calls; no motion, geometry or styling added.
  page.evaluate('''() => { const original=CanvasRenderingContext2D.prototype.fillText;
   window.localTextSlots={};CanvasRenderingContext2D.prototype.fillText=function(value,...args){
    return original.call(this,Object.prototype.hasOwnProperty.call(window.localTextSlots,value)?window.localTextSlots[value]:value,...args);
   }; }''')
  writer=_Video(OUT/'LOCAL_BEST_60S.mp4',1280,720,Fraction(FPS),'libx264',audio=True);writer.stream.thread_count=2
  total=0;start_at=0
  for i,s in enumerate(scenes):
   remaining();spec=EFFECTS[s['effect']];progress(f'Rendering {i+1}/{len(scenes)}: {s["effect"]}, {s["seconds"]}s')
   if 'chapter' in spec:
    photo_bindings={role:(ASSETS/PICTURES[key]).as_uri() for role,key in zip(['bowler','team','portrait'],(s['photos']+[s['photos'][0]])[:3])}
    page.evaluate('async paths => { for (const [role,url] of Object.entries(paths)) A[role]=await img(url); }',photo_bindings)
    s['photo_bindings']=photo_bindings
    page.evaluate('(slots)=>window.localTextSlots=slots',copy_slots(s))
    def frame(t):
     page.evaluate('t=>window.mgSeek(t)',spec['chapter']*10+min(9.999,t*10/s['seconds']))
     return np.asarray(Image.open(BytesIO(page.screenshot(type='jpeg',quality=95))).convert('RGB'))
   else:
    data={'label':s['caption'],'archive_style':spec['style'],'archive_composition':spec['composition'],'archive_variant':0,'archive_grade':'colour',
     'assets':[{'src':(ASSETS/PICTURES[key]).as_uri(),'enter_at':.05+j*s['seconds']/len(s['photos'])} for j,key in enumerate(s['photos'])]}
    payload_scene={'index':i,'template':'archive_board','mode':'full','duration':s['seconds'],'speed':1,'data':data}
    renderer.load(payload_scene)
    def frame(t):return renderer.frame(t)
   Image.fromarray(frame(s['seconds']*.65)).save(OUT/f'scene-{i+1:02}.jpg',quality=93)
   s['start']=start_at;s['still']=f'scene-{i+1:02}.jpg'
   for n in range(s['seconds']*FPS):
    remaining();writer.write(frame(n/FPS));total+=1
   start_at+=s['seconds']
  writer.write_audio(mix);writer.finish();writer=None
 finally:
  if writer:writer.abort()
  if renderer:renderer.close()
  elif browser:browser.close()
  if pw:pw.stop()
 progress('Verifying encoded frames and unchanged animation sources')
 sampled=[];count=0;points=list(range(1,60,3));k=0
 with av.open(str(OUT/'LOCAL_BEST_60S.mp4')) as container:
  duration=container.duration/av.time_base
  for f in container.decode(video=0):
   count+=1;t=float(f.pts*f.time_base)
   if k<len(points) and t>=points[k]:sampled.append((t,f.to_image().resize((320,180))));k+=1
 assert count==1800 and abs(duration-60)<.02,(count,duration)
 board=Image.new('RGB',(1280,math.ceil(len(sampled)/4)*204),'#101318');draw=ImageDraw.Draw(board)
 for i,(t,im) in enumerate(sampled):
  x=i%4*320;y=i//4*204;board.paste(im,(x,y));draw.text((x+6,y+185),f'{t:.2f}s',fill='white')
 board.save(OUT/'export-review.jpg',quality=92)
 after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ANIMATION_FILES}
 assert after==hashes,'Existing animation code changed during trial'
 save('rendered-plan.json',answer)
 receipt.update(status='complete',elapsed_seconds=time.time()-start,decoded_frames=count,video_seconds=duration,
  animation_sources_unchanged=True,animation_hashes_after=after,effects=[s['effect'] for s in scenes],video='LOCAL_BEST_60S.mp4')
 save('receipt.json',receipt)
 figures=''.join(f'<figure><img src="{s["still"]}"><figcaption>{s["start"]}–{s["start"]+s["seconds"]}s · {html.escape(effect_label(s["effect"]))}<br>{html.escape(s["caption"])}</figcaption></figure>' for s in scenes)
 report=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Local documentary director</title><style>body{{background:#101318;color:#e7dfcf;font:17px/1.6 system-ui;max-width:1200px;margin:auto;padding:30px}}h1{{font:42px Georgia}}video,img{{width:100%;border-radius:8px}}main{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}figure{{margin:0}}a{{color:#d5be89}}</style><h1>The local model directs.</h1><p>Qwen3:8B · 60 seconds · 720p/30fps · {receipt['elapsed_seconds']/60:.1f} minutes. Saved styles: cricAddict and vineet documentry edit. The local model chose the sequence, duration, short copy, photo order and additional sound cues. Existing approved animation code was reused unchanged; no new cloud-designed animation or manual replacement plan.</p><video controls playsinline src="LOCAL_BEST_60S.mp4"></video><p>Original reference voice/background audio retained. cricAddict templates retain some baked-in Dale Steyn typography and template decorations. The adapter fills existing text slots and time-scales existing motion to the local model’s scene lengths. This is local direction of reusable animation software, not model-weight fine-tuning or diffusion video generation.</p><p><a href="receipt.json">Runtime and source-code hashes</a> · <a href="local-plan.json">Raw local plan</a> · <a href="director-input.json">Instructions supplied</a> · <a href="model-response-01.json">Local response</a> · <a href="export-review.jpg">Encoded-frame review</a> · <a href="audio-receipt.json">Audio choices</a></p><main>{figures}</main></html>'''
 (OUT/'report.html').write_text(report,encoding='utf8');progress('COMPLETE')

if __name__=='__main__':
 try:main()
 except BaseException as e:
  traceback.print_exc();p=OUT/'receipt.json';r=json.loads(p.read_text()) if p.exists() else {}
  r.update(status='failed',error=str(e));save('receipt.json',r);sys.exit(1)
