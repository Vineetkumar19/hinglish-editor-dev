"""Locate each reference row by restricted glyph-template matching."""
from pathlib import Path
import json,av,cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[2];out=root/'output/caption-two-ae/fidelity-rebuild'
source=json.loads((root/'hinglish_captions/caption_two_reference.json').read_text('utf8'))['recipes']
measure=json.loads((out/'all-frame-measurements.json').read_text('utf8'))['frames']
chosen={41:0,83:1,123:2,229:4,294:5,490:8};results=[]
def template(text,size,regular,tracking):
 f=ImageFont.truetype(str(root/'hinglish_captions/fonts'/('StorylensInterCaption-Regular.ttf' if regular else 'Inter-Bold.otf')),size)
 im=Image.new('L',(1800,200));d=ImageDraw.Draw(im)
 for i,c in enumerate(text):d.text((12+f.getlength(text[:i])+i*size*tracking,12),c,font=f,fill=255)
 return np.asarray(im.crop(im.getbbox()))
with av.open('D:/Full Drive/Styles/Videos/Caption 02 - Lime Keyword Zoom.mp4') as video:
 for index,frame in enumerate(video.decode(video=0)):
  if index not in chosen:continue
  slot=chosen[index];recipe=source[slot];rgb=np.asarray(frame.to_image());box=measure[index]['main_ink_box'];debug=Image.fromarray(rgb);draw=ImageDraw.Draw(debug);words=recipe['text'].split();rows=[]
  if not box:continue
  x0,y0,x1,y1=box
  r,g,b=[rgb[:,:,k].astype(float) for k in range(3)];white=(np.minimum.reduce([r,g,b])>175)&(np.maximum.reduce([r,g,b])-np.minimum.reduce([r,g,b])<48);green=(r>130)&(g>185)&(b<155);ink=((white|green)*255).astype('uint8')
  for row in recipe['rows']:
   if row['role']=='main':rows.append({'id':'main','box':box,'score':1.});continue
   name=row.get('align','bottom');top=name.startswith('top');a=max(0,y0-145) if top else max(0,y1-14);z=min(rgb.shape[0],y0+20) if top else min(rgb.shape[0],y1+160)
   text=' '.join(words[i] for i in row['words']);size=row.get('size',recipe.get('support_size',44));best=None
   for factor in np.arange(.78,1.221,.04):
    mask=template(text,max(8,round(size*factor)),row.get('regular',False),row.get('tracking',-.06));h,w=mask.shape
    if h>z-a or w>=720:continue
    scores=cv2.matchTemplate(ink[a:z],mask,cv2.TM_CCORR_NORMED);_,score,_,where=cv2.minMaxLoc(scores);x,y=where
    if best is None or score>best['score']:best={'id':name,'text':text,'box':[x,a+y,x+w,a+y+h],'score':score,'size':round(size*factor),'font':'regular' if row.get('regular') else 'bold'}
   if best:rows.append(best)
  for row in rows:draw.rectangle(row['box'],outline='#00aaff' if row['id']=='main' else '#ff00ff',width=2);draw.text((row['box'][0],row['box'][1]-12),row['id']+' '+format(row['score'],'.2f'),fill='white')
  debug.save(out/f'rows-{index:04d}.jpg',quality=94);results.append({'source_slot':slot,'frame':index,'rows':rows})
(out/'row-measurements.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps(results))
