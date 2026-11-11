"""Measure all actual Caption 3 source frames; build its separate native profile."""
from pathlib import Path
import json,hashlib,av,numpy as np,cv2
from PIL import Image
from fontTools.ttLib import TTFont
root=Path(__file__).resolve().parents[2];out=root/'output/caption-three-ae';dest=root/'editor_plugins/caption-three';dest.mkdir(exist_ok=True)
source=Path('D:/Full Drive/Styles/Videos/Caption 03 - Serif Soft Focus.mp4');old=json.loads((root/'hinglish_captions/caption_three_reference.json').read_text())
recipes=sorted(old['recipes']+old['continuations'],key=lambda r:r['start'])
# Tight text-only source windows exclude the scene artwork and backdrop echoes.
windows=[[(55,390,450,451),(140,450,555,569),(290,566,610,622)],[(90,335,465,403),(190,404,690,518)],[(180,275,535,344),(110,345,610,474)],[(180,205,580,260),(110,260,630,365)],[(150,688,600,738),(50,735,680,820)],[(80,330,500,379),(110,378,655,493)],[(160,530,540,593),(245,594,670,718)],[(60,300,490,366),(90,365,635,515),(50,850,685,952),(165,950,595,1005)],[(90,455,370,525),(155,526,595,641),(150,640,675,735)],[(90,290,485,406),(190,407,635,472),(150,680,650,790)],[(235,120,485,165),(250,166,650,238),(250,235,610,280)],[(230,355,500,408),(200,410,565,476),(280,478,470,528),(115,690,650,765)]]
# Last CTA and Expectation lettering moves: the track explicitly marks samples
# outside these windows as unavailable instead of inventing hidden pixel data.
tracks=[]
with av.open(str(source)) as v:
 for frame,decoded in enumerate(v.decode(video=0)):
  a=decoded.to_ndarray(format='rgb24');gray=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY);rows=[]
  for slot,r in enumerate(recipes):
   if not r['start']<=frame<r['end']:continue
   for ri,window in enumerate(windows[slot]):
    x0,y0,x1,y1=window;patch=gray[y0:y1,x0:x1].astype(float);background=float(np.percentile(patch,85));dark=np.maximum(0,background-patch);contrast=float(np.percentile(dark,98));mask=dark>max(7,contrast*.45);ys,xs=np.where(mask)
    valid=len(xs)>15 and contrast>6
    box=[int(x0+xs.min()),int(y0+ys.min()),int(x0+xs.max()+1),int(y0+ys.max()+1)] if valid else None
    edge=float(cv2.Laplacian(patch.astype('float32'),cv2.CV_32F).var())/(max(1,contrast)**2)
    rows.append({'slot':slot,'row':ri,'contrast':round(contrast,4),'normalised_edge_energy':round(edge,7),'bbox':box,'available':bool(valid)})
  tracks.append({'frame':frame,'time':frame/30,'rows':rows})
(out/'all-frame-text-tracks.json').write_text(json.dumps({'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'frames':tracks,'limitation':'ROI contrast/edge fitting estimates focus and camera; these are not original AE effect settings.'},indent=2))
fontpaths={'bold':root/'hinglish_captions/fonts/caption-three/CaptionThree-BoldItalic.ttf','support':root/'hinglish_captions/fonts/caption-three/CaptionThree-RegularItalic.ttf','regular':root/'hinglish_captions/fonts/caption-three/CaptionThree-RegularItalic.ttf','playful':root/'hinglish_captions/fonts/caption-three/CaptionThree-Playful.ttf','blue':Path('C:/Windows/Fonts/arialbi.ttf')}
metrics={};fonts={}
for role,path in fontpaths.items():
 with TTFont(path) as f:
  fonts[role]=[f['name'].getDebugName(6)];glyphs={};upm=f['head'].unitsPerEm;cmap=f.getBestCmap();gs=f.getGlyphSet()
  from fontTools.pens.boundsPen import BoundsPen
  for code,name in cmap.items():
   if code>1024 and code not in [8211,8212,8216,8217,8220,8221,8230]:continue
   pen=BoundsPen(gs);gs[name].draw(pen);b=pen.bounds or (0,0,0,0);glyphs[str(code)]=[f['hmtx'][name][0],*b]
  metrics[role]={'units':upm,'glyphs':glyphs,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(dest/'glyph-metrics.json').write_text(json.dumps(metrics,separators=(',',':')))
ids=['suppose','doctor','clinics','playful','calm_blue','instantly','spoken','brain','visual','design','expectations','follow']
profile={'id':'caption_3_ae_v1','name':'Caption 4','folder_name':'Caption 4','public_style':'caption_4','revision':3,'reference':str(source).replace('\\','/'),'reference_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'reference_frames':709,'source_fps':30,'anchor_y':.63,'design_unit':'short_side','safe_width_fraction':.70,'word_gap_em':.20,'ink_gap':8,'independent_fit':True,'fonts':fonts,'tracking':{'bold':-45,'support':-35,'regular':-35,'playful':-45,'blue':-45},'reference_colours':{'charcoal':[53,53,53],'blue':[5,139,252]},'colours':{'charcoal':[255,255,255],'blue':[5,139,252]},'owner_colour_override':'29 October 2026: owner approved the pattern and requested every black/gray caption face white; retain blue accents, transparent background and all existing motion/layout.','decoration_policy':'Caption text only. No source artwork, icons, arrows, UI, background, echo/backdrop duplicates. One setup per interval.','measurement_limit':'Playfair Bold Italic silhouette fit .927, Schoolbell .869 and Arial Bold Italic .815 in sampled rows. Font identity inferred, not proved; focus/zoom are source-derived fits, not pixel-exact native verification.','recipes':[]}
for slot,r in enumerate(recipes):
 row_data=[]
 for ri,row in enumerate(r['rows']):
  original_role=row.get('font_override',row.get('font','support'));role={'main':'bold','support':'support','playful':'playful','blue':'blue'}[original_role]
  observed=[(f['frame'],next((x for x in f['rows'] if x['slot']==slot and x['row']==ri),None)) for f in tracks[r['start']:r['end']]];valid=[x for _,x in observed if x and x['available']]
  peak=float(np.percentile([x['contrast'] for x in valid],90)) if valid else 1;stable=[x for frame,x in observed if x and x['available'] and x['contrast']>peak*.65 and frame>=row.get('frame',r['start'])+8 and frame<r['end']-7]
  sharp=float(np.percentile([x['normalised_edge_energy'] for x in stable],85)) if stable else 1
  focus=[]
  for frame,x in observed:
   if (frame-r['start'])%3 and frame!=r['end']-1:continue
   alpha=min(1,max(0,x['contrast']/max(1,peak))) if x and x['available'] else 0
   edge=x['normalised_edge_energy'] if x and x['available'] else 0
   relative=max(.015,min(1,edge/max(.00001,sharp)))
   blur=min(8,.85*float(np.sqrt(max(0,relative**(-2/3)-1))))
   focus.append([round((frame-r['start'])/(r['end']-r['start']),6),round(alpha,5),round(blur,4)])
  # Dense tracks include ROI boundary/scene noise. Native source-onset gate
  # excludes pre-onset detections; preserve raw data separately for comparison.
  text=' '.join(r['text'].split()[i] for i in row['words'])
  case='title' if all(t[:1].isupper() for t in text.split()) and len(text.split())>1 else 'sentence' if text[:1].isupper() else 'lower'
  row_data.append({'id':'row_'+str(ri),'words':row['words'],'size':row['size'],'font':role,'tone':'blue' if role=='blue' else 'charcoal','role':row['role'],'offset':row.get('offset',0),'source_onset':row.get('frame',r['start']),'case':case,'focus_track':focus,'gap':8})
 # Main row high-confidence width samples provide recipe-specific bounded zoom.
 main=next((i for i,row in enumerate(r['rows']) if row['role']=='main'),0);samples=[]
 for f in tracks[r['start']:r['end']]:
  x=next((x for x in f['rows'] if x['slot']==slot and x['row']==main),None)
  if x and x['available'] and f['frame']>=r['rows'][main].get('frame',r['start'])+8 and f['frame']<r['end']-7:samples.append((f['frame'],x['bbox'][2]-x['bbox'][0]))
 camera=[]
 if len(samples)>5:
  widths=np.array([s[1] for s in samples],dtype=float);base=float(np.median(widths[-min(8,len(widths)):]))
  smooth=cv2.GaussianBlur(widths.reshape(-1,1),(1,7),0).ravel()
  # Fit one smooth bounded camera curve, rather than animating pixel/threshold jitter.
  from scipy.optimize import least_squares
  t=np.array([(q[0]-r['start'])/(r['end']-r['start']) for q in samples]);y=smooth/max(1,base)
  def curve(p,x):return p[1]+(p[0]-p[1])*np.exp(-p[2]*x)
  fit=least_squares(lambda p:curve(p,t)-y,[float(np.clip(y[0],.86,1.14)),1.,3.],bounds=([.85,.85,.1],[1.15,1.15,15.]),loss='soft_l1',f_scale=.015)
  for v in np.linspace(0,1,21):camera.append([round(float(v),6),round(float(np.clip(curve(fit.x,v),.90,1.10)),5)])
 if not camera:camera=[[0,1],[1,1]]
 camera=[[0,camera[0][1]],*camera,[1,camera[-1][1]]]
 profile['recipes'].append({'id':ids[slot],'text':r['text'],'source_slot':slot,'source_start':r['start'],'source_end':r['end'],'rows':row_data,'camera_track':camera,'transition':'slide_up' if slot in [5,8,10] else 'slide_left' if slot==9 else 'focus','transition_frames':6,'focus_exit':slot not in [5,8,9,10]})
(dest/'profile.json').write_text(json.dumps(profile,indent=2))
print('Measured',len(tracks),'frames; created',len(profile['recipes']),'separate text recipes,',len(metrics),'font roles')
