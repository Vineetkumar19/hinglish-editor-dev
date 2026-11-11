from pathlib import Path
import json,numpy as np,cv2
from PIL import Image,ImageFont,ImageDraw
from collections import Counter
out=Path('output/caption-three-ae')
rois=[(40,"you're",(140,450,560,568)),(105,'Clinics',(110,345,610,470)),(180,'Playful Fonts',(110,260,630,365)),(250,'Calm Blue text',(50,735,680,820))]
fonts=list(Path('C:/Windows/Fonts').glob('*.ttf'))+list(Path('hinglish_captions/fonts/caption-three').glob('*.ttf'))
fonts=[f for f in fonts if any(s in f.name.lower() for s in ['i.ttf','bi.ttf','italic','playful','school','it.ttf','it1','serif'])]
report=[]
for frame,text,roi in rois:
 a=np.asarray(Image.open(out/f'source-{frame:03}.png').crop(roi).convert('RGB'));blue=frame==250
 mask=((a[:,:,2]>180)&(a[:,:,0]<80)&(a[:,:,1]>90)&(a[:,:,1]<200)) if blue else (a.max(2)<135)
 y,x=np.where(mask);mask=mask[y.min():y.max()+1,x.min():x.max()+1].astype('uint8');target=cv2.resize(mask,(500,140),interpolation=cv2.INTER_NEAREST)>0
 core=cv2.erode(mask,np.ones((3,3),np.uint8)).astype(bool);pix=a[y.min():y.max()+1,x.min():x.max()+1][core];colour=Counter(map(tuple,pix)).most_common(3)
 scores=[]
 for f in fonts:
  try:font=ImageFont.truetype(str(f),140)
  except OSError:continue
  best=(0,0)
  for tracking in [-60,-45,-30,-15,0]:
   canvas=Image.new('L',(2400,450));draw=ImageDraw.Draw(canvas)
   try:
    for i,c in enumerate(text):draw.text((40+font.getlength(text[:i])+i*140*tracking/1000,200),c,font=font,fill=255,anchor='ls')
   except OSError:continue
   m=np.asarray(canvas)>120;yy,xx=np.where(m)
   if not len(xx):continue
   m=m[yy.min():yy.max()+1,xx.min():xx.max()+1].astype('uint8');ratio=abs(np.log((m.shape[1]/m.shape[0])/(mask.shape[1]/mask.shape[0])));render=cv2.resize(m,(500,140),interpolation=cv2.INTER_NEAREST)>0
   iou=(render&target).sum()/(render|target).sum();score=float(iou)-.2*ratio
   if score>best[0]:best=(score,tracking)
  scores.append({'font':str(f),'score':best[0],'tracking':best[1]})
 scores.sort(key=lambda v:-v['score']);report.append({'frame':frame,'text':text,'bbox':[roi[0]+int(x.min()),roi[1]+int(y.min()),roi[0]+int(x.max()+1),roi[1]+int(y.max()+1)],'sampled_core_rgb':[{'rgb':list(map(int,c)),'count':n} for c,n in colour],'font_candidates':scores[:8]})
(out/'font-colour-analysis.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
