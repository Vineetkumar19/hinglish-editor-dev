"""Measure source ink and compare installed font silhouettes; no AE/model calls."""
from pathlib import Path
import json,hashlib,re,time
import av,numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[2];out=root/'output/caption-two-ae/fidelity-rebuild';out.mkdir(parents=True,exist_ok=True)
source=Path('D:/Full Drive/Styles/Videos/Caption 02 - Lime Keyword Zoom.mp4')
samples={41:'Prospects',83:'Understand',123:'Content'};targets={};measurements=[];started=time.monotonic()
with av.open(str(source)) as video:
 for index,frame in enumerate(video.decode(video=0)):
  rgb=np.array(frame.to_image());r,g,b=[rgb[:,:,i].astype(float) for i in range(3)]
  mask=(r>130)&(g>185)&(g>r*.99)&(b<155)&(b<r*.75);mask[:130]=False;mask[1100:]=False
  active=np.flatnonzero(mask.sum(axis=1)>8);bands=[]
  for y in active:
   if not bands or y-bands[-1][-1]>3:bands.append([int(y)])
   else:bands[-1].append(int(y))
  boxes=[]
  for band in bands:
   y0,y1=band[0],band[-1]+1;yy,xx=np.where(mask[y0:y1])
   if len(xx)>700 and y1-y0>15:boxes.append((len(xx),[int(xx.min()),y0,int(xx.max())+1,y1]))
  box=max(boxes,default=(0,None))[1];row={'frame':index,'time':float(frame.time or 0),'main_ink_box':box}
  if box:
   x0,y0,x1,y1=box;core=mask[y0:y1,x0:x1];pixels=rgb[y0:y1,x0:x1][core];bright=pixels[pixels[:,1]>235]
   row['core_colour_rgb']=np.median(bright if len(bright) else pixels,axis=0).round(2).tolist()
  measurements.append(row)
  if index in samples and box:
   im=Image.fromarray((core*255).astype('uint8'));targets[index]=(samples[index],im)
   Image.fromarray(rgb).save(out/f'source-{index:04d}.png');im.save(out/f'ink-{index:04d}.png')
(out/'all-frame-measurements.json').write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'frames':measurements},indent=2),encoding='utf8')
paths=[]
for directory in [root/'hinglish_captions/fonts',Path('C:/Windows/Fonts'),Path('C:/Users/Vineet Kumar/AppData/Local/Microsoft/Windows/Fonts')]:
 for p in directory.glob('*'):
  if p.suffix.lower() not in ('.ttf','.otf','.ttc'):continue
  try:
   f=ImageFont.truetype(str(p),160);family,style=f.getname()
   if not re.search(r'bold|heavy|black|demi',style+' '+p.stem,re.I) or re.search(r'italic|oblique|condensed|narrow|script|serif',family+' '+style,re.I):continue
   paths.append((p,f,family,style))
  except (OSError,ValueError):continue
fits=[];seen=set()
def norm(im):return np.asarray(im.crop(im.getbbox()).resize((384,64),Image.Resampling.LANCZOS))>96
for path,font,family,style in paths:
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest in seen:continue
 seen.add(digest)
 for tracking in [-.075,-.06,-.045,-.03,-.015,0]:
  scores=[]
  for frame,(word,target) in targets.items():
   im=Image.new('L',(2400,300));draw=ImageDraw.Draw(im)
   for j,char in enumerate(word):draw.text((20+font.getlength(word[:j])+j*font.size*tracking,20),char,font=font,fill=255)
   im=im.crop(im.getbbox());a,z=norm(im),norm(target);iou=float((a&z).sum()/max(1,(a|z).sum()));aspect=abs(im.width/im.height-target.width/target.height)/(target.width/target.height)
   scores.append({'frame':frame,'iou':iou,'aspect_error':aspect,'score':iou-.4*aspect})
  fits.append({'path':str(path),'family':family,'style':style,'tracking':tracking,'sha256':digest,'score':sum(s['score'] for s in scores)/len(scores),'samples':scores})
fits.sort(key=lambda f:-f['score']);(out/'installed-font-fit.json').write_text(json.dumps(fits,indent=2),encoding='utf8')
print(json.dumps({'frames':len(measurements),'font_candidates':len(seen),'seconds':time.monotonic()-started,'best':fits[:5]}),flush=True)
