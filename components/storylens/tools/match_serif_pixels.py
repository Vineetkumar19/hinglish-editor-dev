"""Compare lowercase ink silhouettes from the source, not font-name guesses."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tmp/serif-font-study'
im=np.asarray(Image.open(ROOT/'tmp/herb-reference-two/detail.jpg').convert('RGB'))
crop=im[899:946,243:443].astype(float)
mask=(crop.min(2)>170)&(crop.max(2)-crop.min(2)<55)
ys,xs=np.where(mask);mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
target=Image.fromarray((mask*255).astype('uint8'));target.save(OUT/'source-ink.png')
fonts=list(OUT.glob('*.ttf'))+[Path('C:/Windows/Fonts')/n for n in ('timesbi.ttf','BOD_BI.TTF','BOD_I.TTF','georgiaz.ttf')]
results=[]
for path in fonts:
 for weight in ([400,500,600,700,800,900] if '[' in path.name else [400]):
  f=ImageFont.truetype(str(path),180)
  if '[' in path.name:f.set_variation_by_axes([weight])
  for tracking in [-.08,-.06,-.04,-.02,0]:
   for stroke in ([0,1,2,3] if 'Instrument' in path.name else [0]):
    ink=Image.new('L',(1400,400));d=ImageDraw.Draw(ink);text='unico'
    for j,c in enumerate(text):d.text((40+f.getlength(text[:j])+j*f.size*tracking,0),c,font=f,fill=255,stroke_width=stroke)
    box=f.getbbox('n');ink=ink.crop((0,box[1],ink.width,box[3]));ink=ink.crop(ink.getbbox())
    ink=ink.resize(target.size,Image.Resampling.LANCZOS)
    a=np.array(ink)>150;b=mask
    score=(a&b).sum()/max(1,(a|b).sum())
    results.append((float(score),path.name,weight,tracking,stroke,ink.copy()))
results.sort(key=lambda r:r[0],reverse=True)
(OUT/'scores.json').write_text(json.dumps([r[:5] for r in results[:40]],indent=2),'utf-8')
canvas=Image.new('RGB',(850,100*11),'#111');d=ImageDraw.Draw(canvas);label=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
canvas.paste(target.resize((400,94)),(0,0));d.text((420,30),'Source lower-case body',font=label,fill='white')
for i,r in enumerate(results[:10],1):
 canvas.paste(r[5].resize((400,94)),(0,i*100));d.text((420,i*100+25),str(r[:5]),font=label,fill='white')
canvas.save(OUT/'best-matches.jpg');print(json.dumps([r[:5] for r in results[:12]],indent=2))
