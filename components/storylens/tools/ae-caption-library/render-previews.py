"""Generate reference-informed static projective thumbnails, not AE render evidence."""
from pathlib import Path
import json,subprocess,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[2];catalog=json.loads((root/'editor_plugins/caption-3d/catalog.json').read_text());fontpath=str(root/'hinglish_app/static/fonts/Storylens-Anton-Regular.ttf');out=root/'hinglish_app/static/caption-3d-previews';out.mkdir(exist_ok=True)
requests=[];canvases={}
for fam in catalog['families'][1:]:
 for v in fam['variants']:
  words=v['text'].split();cursor=0;rows=[]
  for r in v['rows']:
   row=dict(r,text=' '.join(words[cursor:cursor+r['count']]));cursor+=r['count'];f=ImageFont.truetype(fontpath,row['size']);bbox=f.getbbox(row['text']);ink=Image.new('RGBA',(bbox[2]-bbox[0]+8,bbox[3]-bbox[1]+8));ImageDraw.Draw(ink).text((4-bbox[0],4-bbox[1]),row['text'],font=f,fill=tuple(int(c*255) for c in catalog['colours'][v['colour']])+(255,));s=min(1,1120/ink.width);ink=ink.resize((round(ink.width*s),round(ink.height*s)),Image.Resampling.LANCZOS);row['image']=ink;rows.append(row)
  default_side='left' if v.get('orientation',[0,0])[1]>0 else 'right';groups=[(default_side,rows)]
  if v['layout']=='ground':groups=[('ground',rows)]
  if v['layout']=='corner':groups=[('left',[r for r in rows if r['side']=='left']),('right',[r for r in rows if r['side']=='right'])]
  specs=[];imgs=[]
  for side,rs in groups:
   canvas=Image.new('RGBA',(1400,1700));bounds=[];y=(1700-sum(r['image'].height for r in rs)-22*(len(rs)-1))/2
   for ri,r in enumerate(rs):
    im=r['image'];x=(1400-im.width)/2
    if v['layout']=='corner':x=1370-im.width if side=='left' else 30
    yy=y
    if v['layout']=='column':
     if ri==1:im=im.rotate(90,expand=True);x=800;yy=1450-im.height
     else:x=788-im.width;yy=1426-im.height
    canvas.alpha_composite(im,(round(x),round(yy)));bounds.append(dict(x=x,y=yy,w=im.width,h=im.height));y+=r['image'].height+22
   specs.append(dict(side=side,ink=bounds,source=dict(width=1400,height=1700)));imgs.append(canvas)
  ident=fam['id']+'-'+v['id'];requests.append(dict(id=ident,plan=dict(layout=v['layout'],surface='ground' if v['layout']=='ground' else 'both' if v['layout']=='corner' else default_side,perspective={}),specs=specs));canvases[ident]=imgs
work=root/'output/ae-3d-caption-library/perspective-revision';f=work/'preview-input.json';f.write_text(json.dumps(requests));p=subprocess.run(['node','tools/ae-caption-library/preview-geometry.cjs',str(f)],cwd=root,capture_output=True,text=True,check=True);geometry=json.loads(p.stdout);(work/'preview-geometry.json').write_text(json.dumps(geometry,indent=2))
for result in geometry:
 target=Image.new('RGBA',(1080,1920))
 for source,plane in zip(canvases[result['id']],result['geometry']['planes']):
  q=plane['quad'];xy=[(0,0),(1400,0),(0,1700),(1400,1700)];a=[];b=[]
  for (x,y),(u,v) in zip(q,xy):a.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]);b.extend([u,v])
  matrix=np.linalg.solve(np.array(a),np.array(b));warped=source.transform((1080,1920),Image.Transform.PERSPECTIVE,matrix,Image.Resampling.BICUBIC);target.alpha_composite(warped)
 box=target.getbbox();target=target.crop((max(0,box[0]-22),max(0,box[1]-22),min(1080,box[2]+22),min(1920,box[3]+22)));target.thumbnail((600,460),Image.Resampling.LANCZOS);target.save(out/(result['id']+'.png'))
sheet=Image.new('RGB',(1200,420),'#11161b');d=ImageDraw.Draw(sheet)
for i,name in enumerate(['ground','wall','corner','column']):
 im=Image.open(out/('3d3-'+name+'.png'));im.thumbnail((280,325),Image.Resampling.LANCZOS);sheet.paste(im,(i*300+(300-im.width)//2,45+(325-im.height)//2),im);d.text((i*300+12,12),name.title()+' - geometry preview',fill='white')
sheet.save(work/'geometry-preview.jpg');print('Eight projective thumbnails generated; these are not AE frames.')
