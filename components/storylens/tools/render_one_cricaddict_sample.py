"""WITHDRAWN reference-media sample adapter. It must not render production.

The director is local. This adapter does not choose a scene, photo, headline or
sound cue. Original rig source remains unchanged and its hashes are checked.
"""
import hashlib,json,math,os,re,subprocess,sys,time
from pathlib import Path
from fractions import Fraction
from io import BytesIO
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from study_one_cricaddict_director import OUT,EFFECTS,SOUNDS,load,save,validate
from hinglish_motion.speech_clock import retimed_phase,frame_at
FPS=30

def slots(s):
 h,sub,cap=s['headline'],s['subline'],s['caption']
 common={'DALE STEYN · A PORTRAIT':(s['name_first']+' '+s['name_last']).strip() or cap,
  'A rhythm. A release. A reaction.':'','The details that stay with us.':'','A study in cricket storytelling.':'',
  'THE ART OF FAST BOWLING':'','FIELD NOTES   /   ANATOMY OF PACE':'CRICKET ARCHIVE',
  'PACE  / PRECISION  /  PRESENCE':'','CRICK EDIT':''}
 maps={
  'crick-book':{'Every story':h,'has a first':sub,'page.':'','The art':h,'of pace.':sub,'Open the archive':cap},
  'crick-hero':{'A force of nature':h},'crick-evidence':{'Not just speed.':h},
  'crick-tv':{'THE ARCHIVE':h,'Let the action speak.':cap},
  'crick-paper':{'More than a moment.':h,'A memory.':sub},
  'crick-film':{'The art of pace.':cap,'Every moment':h,'has a story.':sub,'THE RELEASE':h,'THE REACTION':sub}}
 result={**common,**maps[s['effect']]}
 if s['effect']=='crick-evidence':
  for old,n in zip([('THE RUN-UP','Build the rhythm.'),('THE RELEASE','Make the moment count.'),('THE REACTION','Let the emotion breathe.')],s['notes']):
   result[old[0]]=n['heading'];result[old[1]]=n['detail']
 return result

# Canvas draw interception is an API binding, not an animation replacement.
BINDING_JS=r'''() => {
 const fill=CanvasRenderingContext2D.prototype.fillText,draw=CanvasRenderingContext2D.prototype.drawImage,rect=CanvasRenderingContext2D.prototype.rect;
 window.binding={slots:{},textAt:{},imageAt:{},time:0,visible:[],blocked:[],geometry:[],nameFirst:'',nameLast:'',motionGain:1};
 CanvasRenderingContext2D.prototype.fillText=function(value,...args){
  const b=window.binding;if(b.time<(b.textAt[value]??-1))return;
  const mapped=Object.prototype.hasOwnProperty.call(b.slots,value),display=mapped?b.slots[value]:value;
  const alpha=this.globalAlpha,font=this.font;
  if(mapped){
   let limit=this.canvas.width===520?520-Number(args[0])-42:Math.min(610,this.canvas.width-Number(args[0])-52);
   if(this.textAlign==='right')limit=Number(args[0])-52;
   if(this.textAlign==='center')limit=Math.min(610,Math.min(Number(args[0]),this.canvas.width-Number(args[0]))*2-90);
   if((value==='THE RELEASE'||value==='THE REACTION')&&this.canvas.width===1280&&Number(args[0])===112)limit=420;
   if((value==='More than a moment.'||value==='A memory.')&&this.canvas.width===1280)limit=520;
   const w=this.measureText(display).width;if(w>limit&&limit>0)this.font=this.font.replace(/([\d.]+)px/,(_,n)=>`${Number(n)*limit/w}px`);
   this.globalAlpha*=ease((b.time-(b.textAt[value]??0))/.6);
  }
  try{return fill.call(this,display,...args)}finally{this.globalAlpha=alpha;this.font=font;}
 };
 CanvasRenderingContext2D.prototype.drawImage=function(im,...args){
  const b=window.binding,url=im?.src;
  if(url&&b.time<(b.imageAt[url]??-1)){b.blocked.push(url);return;}
  const composite=!url&&im?.width===520&&im?.height===580&&this.canvas.width===1280;
  if((url||composite)&&this.globalAlpha>.05){
   if(url)b.visible.push(url);const m=this.getTransform();
   b.geometry.push({url:url||'composite-book-page',canvas:[this.canvas.width,this.canvas.height],args,transform:[m.a,m.b,m.c,m.d,m.e,m.f],alpha:this.globalAlpha});
  }
  return draw.call(this,im,...args);
 };
 CanvasRenderingContext2D.prototype.rect=function(x,y,w,h){
  const b=window.binding,row=Math.round((y-232)/126);
  if(b.notesAt&&x===154&&h===55&&row>=0&&row<3&&Math.abs(y-(232+row*126))<.01)w=460*ease((b.time-b.notesAt[row])/.7);
  return rect.call(this,x,y,w,h);
 };
 const trackedOriginal=tracked;
 tracked=(s,...args)=>trackedOriginal(Object.prototype.hasOwnProperty.call(window.binding.slots,s)?window.binding.slots[s]:s,...args);
 // These substitutions parameterize hard-coded subject copy and fit the
 // existing two-line name slot. All positions, easing, cameras and layers
 // remain the approved rig's own functions.
 let heroSource=hero.toString().replace("const name='DALE'","const name=window.binding.nameFirst")
  .replace(/8\+i\*113/g,'8+g.measureText(name.slice(0,i)).width').replace(/'215px Impact'/g,'window.heroFont+"px Impact"')
  .replace(/,215,/g,',window.heroFont,').replace("'STEYN'",'window.binding.nameLast');
 hero=(0,eval)('('+heroSource+')');
 // Expose only the approved rigs' existing continuous-motion coefficients.
 // The LOCAL director supplies their common multiplier; all trajectories,
 // layout positions, reveal easing and masked shapes remain unchanged.
 function motionParameter(f){
  const source=f.toString().replace('1+t*.008','1+t*.008*window.binding.motionGain')
   .replace('t*.003','t*.003*window.binding.motionGain').replace('.016*smooth','.016*window.binding.motionGain*smooth')
   .replace('.13*smooth','.13*window.binding.motionGain*smooth').replace('.055*smooth','.055*window.binding.motionGain*smooth')
   .replace('g.translate(-t*3,','g.translate(-t*3*window.binding.motionGain,')
   .replace('g.translate(t*6,0)','g.translate(t*6*window.binding.motionGain,0)')
   .replace('1.07+t*.004','1.07+t*.004*window.binding.motionGain');
  return (0,eval)('('+source+')');
 }
 book=motionParameter(book);hero=motionParameter(hero);evidence=motionParameter(evidence);
 tv=motionParameter(tv);paper=motionParameter(paper);film=motionParameter(film);bgPhoto=motionParameter(bgPhoto);
 window.renderBound=async data=>{
  const b=window.binding;b.time=data.time;b.visible=[];b.blocked=[];b.geometry=[];
  g.setTransform(1,0,0,1,0,0);g.globalAlpha=1;g.filter='none';g.shadowColor='transparent';
  const funcs=[book,hero,evidence,tv,paper,film];
  if(data.chapter===3||data.chapter===5)funcs[data.chapter](data.phase,await frame('source',data.sourceFrame));
  else funcs[data.chapter](data.phase);
  texture(data.time);return {visible:[...new Set(b.visible)],blocked:[...new Set(b.blocked)],geometry:b.geometry};
 };
}'''

def prepare_media(scenes):
 from hinglish_motion.reference_policy import block_reference_sample
 block_reference_sample()
 from imageio_ffmpeg import get_ffmpeg_exe
 from PIL import Image
 ff=get_ffmpeg_exe();source=load('source.json');window=load('sample-window.json')
 clips=OUT/'sample-source-frames';clips.mkdir(exist_ok=True)
 if len(list(clips.glob('*.jpg')))!=1800:
  subprocess.run([ff,'-v','error','-nostdin','-threads','2','-ss',str(window['start']),'-i',source['path'],'-t','60',
   '-vf','fps=30,scale=960:540','-q:v','3','-y',str(clips/'%04d.jpg')],check=True)
 assets=OUT/'sample-assets';assets.mkdir(exist_ok=True);events=[]
 for si,scene in enumerate(scenes):
  for pi,p in enumerate(scene['photos']):
   name=f'scene-{si+1:02}-photo-{pi+1}.jpg';target=assets/name
   source_frame=min(1800,p['frame']+1)
   Image.open(clips/f'{source_frame:04d}.jpg').save(target,quality=96)
   p['path']=str(target);events.append({'scene':si+1,'slot':pi+1,'word':p['word'],'source_at':window['start']+p['global_at'],
    'source_frame':source_frame,'asset':name,'status':'Actual reference image at the local director-selected speech cue; not generated or independently face-verified.'})
 save('sample-assets.json',{'events':events,'source':source['path'],'window':window})
 return ff,clips,assets

def isolate(path):
 """Local subject isolation is image processing, not a creative image model."""
 from PIL import Image
 from rembg import remove,new_session
 os.environ['U2NET_HOME']=str(ROOT/'models/rembg');os.environ['OMP_NUM_THREADS']='2'
 if not (ROOT/'models/rembg/models/isnet-general-use/isnet-general-use.onnx').is_file():
  raise ValueError('Offline subject-isolation weights are missing; no download or cloud substitute is permitted')
 session=new_session('isnet-general-use',providers=['CPUExecutionProvider'])
 image=Image.open(path).convert('RGB');result=remove(image,session=session)
 import numpy as np
 fraction=float((np.asarray(result)[...,3]>90).mean())
 if not .04<fraction<.96:raise ValueError('Local segmentation retained no usable isolated subject')
 return result

def crop_asset(path,decision):
 """Apply only the locally chosen rectangle, with no assistant crop choice."""
 from PIL import Image
 if decision and decision.get('use_crop'):
  with Image.open(path) as im:
   box=decision['box'];pixels=tuple(round(box[j]*(im.width if j%2==0 else im.height)) for j in range(4))
   if pixels[2]<=pixels[0] or pixels[3]<=pixels[1]:raise ValueError('Local crop collapsed to an empty region')
   im.crop(pixels).save(path,quality=96)

def cached_isolation(path):
 """A changed source cue/crop cannot reuse a previous subject's silhouette."""
 path=Path(path);target=path.with_suffix('.png');receipt=path.with_suffix('.isolation.json')
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if target.is_file() and receipt.is_file():
  prior=json.loads(receipt.read_text(encoding='utf8'))
  if prior.get('source_sha256')==digest and prior.get('png_sha256')==hashlib.sha256(target.read_bytes()).hexdigest():return target
 result=isolate(path);result.save(target)
 receipt.write_text(json.dumps({'source_sha256':digest,'png_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
  'model':'Offline isnet-general-use','cloud':False},indent=2),encoding='utf8')
 return target

def render():
 from hinglish_motion.reference_policy import block_reference_sample
 block_reference_sample()
 import numpy as np,av
 from PIL import Image,ImageDraw
 from hinglish_motion.render import SceneRenderer
 from hinglish_shorts.render import _Video
 words=load('sample-words.json');plan=load('local-plan.json');errors,scenes=validate(plan,words)
 if errors:raise ValueError(str(errors))
 source=load('source.json');window=load('sample-window.json');original=ROOT/'hinglish_motion/web/crick_demo.html'
 digest=hashlib.sha256(original.read_bytes()).hexdigest();began=time.time()
 receipt={'status':'running','creative_model':'qwen3:8b','cloud_creative_plan':False,'new_animation_rigs':False,
  'source':source,'window':window,'animation_sha256_before':digest,'started_unix':began}
 def progress(stage):
  receipt.update(stage=stage,elapsed_seconds=time.time()-began);save('sample-render-receipt.json',receipt);print(stage,flush=True)
 progress('Preparing actual first-reference media at local director word cues')
 ff,clips,assets=prepare_media(scenes)
 for i,scene in enumerate(scenes):
  for photo in scene['photos']:
   if photo['asset']=='photo' and float(np.asarray(Image.open(photo['path']).convert('RGB')).std())<1:
    raise ValueError(f'Scene {i+1} selected a blank source still; return this asset failure to the local director before rendering')
 # Every isolated subject is made from this sample, never an earlier player's
 # asset. ROI refinement, if locally available, is applied before isolation.
 cropped=load('local-asset-review.json') if (OUT/'local-asset-review.json').exists() else {'assets':[]}
 crops={r['asset']:r for r in cropped['assets']}
 for scene in scenes:
  for photo in scene['photos']:
   path=Path(photo['path']);decision=crops.get(path.name)
   crop_asset(path,decision)
  if scene['effect'] in ('crick-hero','crick-evidence'):
   scene['cutout']=str(cached_isolation(Path(scene['photos'][0]['path'])))
 raw=subprocess.check_output([ff,'-v','error','-nostdin','-threads','2','-ss',str(window['start']),'-i',source['path'],
  '-t','60','-vn','-ar','48000','-ac','2','-f','f32le','-'])
 audio=np.frombuffer(raw,dtype='<f4').reshape(-1,2).T.copy();mix=np.zeros((2,2880000),np.float32)
 mix[:,:min(audio.shape[1],2880000)]=audio[:,:2880000];sounds=[]
 for scene in scenes:
  if scene['sfx']=='none':continue
  path=ROOT/'library/sfx-pro'/SOUNDS[scene['sfx']]
  raw=subprocess.check_output([ff,'-v','error','-nostdin','-i',str(path),'-t','1.5','-ar','48000','-ac','2','-f','f32le','-'])
  samples=np.frombuffer(raw,dtype='<f4').reshape(-1,2).T.copy();samples*=.025/max(.01,float(abs(samples).max()))
  onset=round(scene['sfx_at']*48000);length=min(samples.shape[1],2880000-onset);fade=min(2400,length)
  samples[:,length-fade:length]*=np.linspace(1,0,fade);mix[:,onset:onset+length]+=samples[:,:length]
  sounds.append({'word':scene['sfx_word'],'at':onset/48000,'path':str(path),'choice':'local model'})
 peak=float(abs(mix).max())
 if peak>.98:mix*=.98/peak
 save('sample-audio-receipt.json',{'source_start':window['start'],'audio_speed':1,'original_mixed_track_preserved':True,
  'source_samples':audio.shape[1],'samples':2880000,'sounds':sounds,'peak':float(abs(mix).max())})
 renderer=None;writer=None;geometry=[];audit=[]
 try:
  renderer=SceneRenderer(1280,720);canvas=renderer.browser.new_page(viewport={'width':1280,'height':720},device_scale_factor=1)
  canvas.goto(original.as_uri());canvas.evaluate(BINDING_JS)
  canvas.evaluate('path=>{window.sourceRoot=path;frame=async(name,n)=>{const k="sample/"+n;if(!frames.has(k)){frames.set(k,await img(window.sourceRoot+"/"+String(n).padStart(4,"0")+".jpg"));if(frames.size>24)frames.delete(frames.keys().next().value)}return frames.get(k)}}',clips.as_uri())
  writer=_Video(OUT/'CRICADDICT_REFERENCE_01_LOCAL_60S.mp4',1280,720,Fraction(FPS),'libx264',audio=True);writer.stream.thread_count=2
  for index,scene in enumerate(scenes):
   progress(f'Rendering local scene {index+1}/{len(scenes)}: {scene["effect"]}, {scene["start"]:.2f}–{scene["start"]+scene["seconds"]:.2f}s')
   photos=scene['photos'];first=photos[0]['at'];roles=['bowler','team','portrait'];image_at={};paths={}
   for i,role in enumerate(roles):
    p=photos[min(i,len(photos)-1)];url=Path(p['path']).as_uri();paths[role]=url;image_at[url]=min(image_at.get(url,1e9),p['at'])
   cutout=Path(scene.get('cutout',photos[0]['path'])).as_uri();paths['cutout']=cutout;image_at[cutout]=first
   canvas.evaluate('async paths=>{for(const [key,url] of Object.entries(paths))A[key]=await img(url)}',paths)
   values=slots(scene);text_at={k:0 for k in values}
   if scene['effect']=='crick-evidence':
    for old,n in zip([('THE RUN-UP','Build the rhythm.'),('THE RELEASE','Make the moment count.'),('THE REACTION','Let the emotion breathe.')],scene['notes']):
     for key in old:text_at[key]=n['at']
    cues=[n['at'] for n in scene['notes']];native=[.65,2.55,4.45];end=7.4
   elif scene['effect']=='crick-paper':cues=[p['at'] for p in photos];native=[1.,2.85];end=8.
   else:
    cues=[first];native=[{'crick-book':2.95,'crick-hero':.65,'crick-tv':2.08,'crick-film':.05}[scene['effect']]];end=7.8 if scene['effect']=='crick-film' else 8.8
   # Bind factual numbers only after their spoken token, even in headline slots.
   for key,value in values.items():
    for number in re.findall(r'\d+',value):
     matching=[w for w in words if re.search(r'(?<!\d)'+re.escape(number)+r'(?!\d)',w['text']) and w['start']<scene['start']+scene['seconds']]
     if matching:text_at[key]=max(text_at[key],max(0,matching[-1]['start']-scene['start']))
   canvas.evaluate('b=>{window.binding={...window.binding,...b};g.font="215px Impact";const width=Math.max(g.measureText(b.nameFirst).width,g.measureText(b.nameLast).width,1);window.heroFont=Math.min(215,480/width*215);window.heroSpacing=480/Math.max(1,b.nameFirst.length)}',
    {'slots':values,'textAt':text_at,'imageAt':image_at,'notesAt':[n['at'] for n in scene['notes']] or None,
     'nameFirst':scene['name_first'],'nameLast':scene['name_last'],'motionGain':scene['motion_gain']})
   for local_index in range(scene['end_frame']-scene['start_frame']):
    global_frame=scene['start_frame']+local_index;t=local_index/FPS
    phase=retimed_phase(t,cues,native,end,scene['seconds'])
    if scene['effect']=='crick-evidence':
     # Subject/camera keeps advancing independently of the three word-triggered
     # highlights; clamping a shared phase would freeze it between note cues.
     phase=2.+5.4*t/scene['seconds']
    state=canvas.evaluate('d=>window.renderBound(d)',{'time':t,'phase':phase,'chapter':EFFECTS[scene['effect']]['chapter'],'sourceFrame':global_frame+1})
    pixels=np.asarray(Image.open(BytesIO(canvas.screenshot(type='jpeg',quality=95))).convert('RGB'));writer.write(pixels)
    if local_index%3==0:geometry.append({'frame':global_frame,'scene':index+1,'phase':phase,'time':t,**state})
    if local_index==(scene['end_frame']-scene['start_frame'])//2:
     name=f'sample-scene-{index+1:02}.jpg';Image.fromarray(pixels).save(OUT/name,quality=94);scene['still']=name
   audit.extend({'scene':index+1,'kind':field,'word':p['word'],'spoken_text':p['spoken_text'],'source_onset':window['start']+p['acoustic_at'],
    'sample_onset':p['acoustic_at'],'scheduled_at':p['global_at'],'schedule_error_ms':p['schedule_error_ms']} for field in ('photos','notes') for p in scene[field])
  writer.write_audio(mix);writer.finish();writer=None
 finally:
  if writer:writer.abort()
  if renderer:renderer.close()
 progress('Checking encoded frames, audio synchronization and unchanged approved rig')
 frames=0
 with av.open(str(OUT/'CRICADDICT_REFERENCE_01_LOCAL_60S.mp4')) as container:
  duration=container.duration/av.time_base;rate=str(container.streams.video[0].average_rate)
  for f in container.decode(video=0):frames+=1
 if frames!=1800 or abs(duration-60)>.035:raise ValueError(f'Invalid export {frames} frames, {duration}s')
 from scipy.signal import correlate,correlation_lags
 decoded=[]
 with av.open(str(OUT/'CRICADDICT_REFERENCE_01_LOCAL_60S.mp4')) as container:
  audio_rate=container.streams.audio[0].sample_rate
  for f in container.decode(audio=0):
   decoded.append(f.to_ndarray())
   if sum(a.shape[1] for a in decoded)>=48000*5:break
 encoded=np.concatenate(decoded,axis=1)[0,:48000*4];expected=mix[0,:len(encoded)]
 correlation=correlate(encoded,expected,mode='full',method='fft');lags=correlation_lags(len(encoded),len(expected),mode='full');near=np.abs(lags)<=2048
 offset=int(lags[near][np.argmax(correlation[near])]);after=hashlib.sha256(original.read_bytes()).hexdigest()
 if abs(offset)>480 or digest!=after:raise ValueError('Audio offset or approved rig integrity failed')
 save('sample-rendered-plan.json',{'scenes':scenes});save('sample-geometry.json',geometry)
 save('sample-cue-audit.json',{'events':audit,'max_frame_rounding_ms':max(a['schedule_error_ms'] for a in audit),
  'limit':'Against local Whisper word estimates; not human-certified spoken onsets. Reveals start at cue and can finish later.'})
 # Independent foreground draw geometry excludes generated grain/dust. A book
 # uses a projected intermediate page: native phase + whole image-flow audit
 # remain necessary to interpret its physical page/camera motion.
 results=[]
 for i,s in enumerate(scenes):
  trace=[r for r in geometry if r['scene']==i+1 and r['time']>=1.5];changes=[];previous=None;windows={}
  for r in trace:
   # A new source JPEG URL or fading alpha is not geometric movement. Compare
   # the actual image/page draw size and transform, excluding those shortcuts.
   signature=json.dumps([[g['canvas'],g['args'],g['transform']] for g in r['geometry']],sort_keys=True)
   if previous is not None:
    changed=signature!=previous;changes.append(changed);windows.setdefault(math.floor(r['time']),[]).append(changed)
   previous=signature
  # Audit complete one-second windows, rather than allowing one entrance
  # change to hide a long frozen tail. Partial first/last windows are excluded.
  full_windows={second:sum(values) for second,values in windows.items() if second>=2 and second+1<=s['seconds'] and len(values)>=9}
  frozen=[second for second,count in full_windows.items() if count==0]
  results.append({'scene':i+1,'effect':s['effect'],'post_entry_photo_draw_geometry_changes':sum(changes),
   'compared_samples':len(changes),'geometry_sampling_fps':10,
   'complete_one_second_window_changes':full_windows,'frozen_complete_second_windows':frozen,
   'needs_review':bool(frozen) or (bool(changes) and not any(changes)),
   'limit':'Draw transform/size changes; not human visual quality certification. Book precomposed page has an additional whole-camera transform.'})
 save('sample-continuity.json',{'scenes':results,'grain_counted_as_photo_motion':False})
 if any(r['needs_review'] for r in results):raise ValueError('Photo/camera geometry has a frozen complete post-entry second; inspect continuity before completion')
 receipt.update(status='complete',stage='Complete',elapsed_seconds=time.time()-began,video='CRICADDICT_REFERENCE_01_LOCAL_60S.mp4',
  decoded_frames=frames,duration=duration,fps=rate,audio_rate=audio_rate,audio_offset_ms=offset/48,
  animation_sha256_after=after,animation_sources_unchanged=digest==after)
 save('sample-render-receipt.json',receipt);print('COMPLETE locally directed first-reference sample',flush=True)

if __name__=='__main__':render()
