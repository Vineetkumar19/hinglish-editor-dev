from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np,json
root=Path(__file__).resolve().parents[1];out=root/'tmp/serif-font-study'
im=np.asarray(Image.open(out/'frame-0.233.png').convert('RGB'))[808:880,230:450].astype(float)
b=(im.min(2)>205)&(im.max(2)-im.min(2)<35);ys,xs=np.where(b);b=b[ys.min():ys.max()+1,xs.min():xs.max()+1];target=Image.fromarray((b*255).astype('uint8'))
files=[root/'hinglish_captions/fonts'/n for n in ('Inter-Bold.otf','Inter-Medium.otf','Inter-Variable.ttf','Roboto-Regular.ttf','Roboto-Black.ttf')]+[Path('C:/Windows/Fonts')/n for n in ('arialbd.ttf','arial.ttf','segoeuib.ttf','Inter-SemiBold.ttf')]
rows=[]
for path in files:
 for weight in ([500,600,650,700,750,800] if 'Variable' in path.name else [0]):
  f=ImageFont.truetype(str(path),150)
  if weight:f.set_variation_by_axes([32,weight])
  for tracking in [-.06,-.05,-.04,-.03,-.02,-.01,0]:
   ink=Image.new('L',(1500,300));d=ImageDraw.Draw(ink);text='Por que'
   for j,c in enumerate(text):d.text((30+f.getlength(text[:j])+j*f.size*tracking,0),c,font=f,fill=255)
   ink=ink.crop(ink.getbbox()).resize(target.size,Image.Resampling.LANCZOS);a=np.array(ink)>150
   rows.append((float((a&b).sum()/max(1,(a|b).sum())),path.name,weight,tracking,ink))
rows.sort(key=lambda r:r[0],reverse=True)
print(json.dumps([r[:4] for r in rows[:15]],indent=2))
canvas=Image.new('RGB',(950,100*9),'#111');d=ImageDraw.Draw(canvas);label=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
canvas.paste(target.resize((400,94)),(0,0));d.text((420,30),'Source',font=label,fill='white')
for i,r in enumerate(rows[:8],1):canvas.paste(r[4].resize((400,94)),(0,i*100));d.text((420,i*100+25),str(r[:4]),font=label,fill='white')
canvas.save(out/'sans-matches.jpg')
