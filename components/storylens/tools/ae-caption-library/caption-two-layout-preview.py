"""Offline layout evidence from the same recipe/geometry modules, not a native AE render."""
import sys
from pathlib import Path
import json,subprocess,math
from PIL import Image,ImageFont,ImageDraw
root=Path(__file__).resolve().parents[2];out=root/'output/caption-two-ae';out.mkdir(parents=True,exist_ok=True)
samples=[{'script':text,'duration':6,'template_slot':i} for i,text in enumerate(['If the Prospects have to meet you','to Understand your value','your Content is failing','being on Camera Stresses you out','even if You record you are unsure','we take it off Your plate','and for the next day'])]
code="const m=require('./editor_plugins/caption-two/model.cjs');process.stdout.write(JSON.stringify("+json.dumps(samples)+".map(x=>m.prepare(x))));"
if '--failed-pg' in sys.argv:
 saved=json.loads((root/'output/captions/ae-patterns/a0b1f1010c6eed6fd010be853c7411fb/plan.json').read_text('utf8'));samples=[{'script':saved['plan']['script'],'duration':saved['plan']['duration']}];out=root/'output/caption-two-ae/native-failure-repair';out.mkdir(exist_ok=True);code="const m=require('./editor_plugins/caption-two/model.cjs');process.stdout.write(JSON.stringify("+json.dumps(samples)+".map(x=>m.prepare(x))));"
plans=json.loads(subprocess.check_output(['node','-e',code],cwd=root,text=True,encoding="utf8"));fonts={}
def font(role,size):
 key=(role,round(size));fonts.setdefault(key,ImageFont.truetype(str(root/'hinglish_captions/fonts'/('Inter-Bold.otf' if role=='bold' else 'StorylensInterCaption-Regular.ttf' if role=='regular' else 'Inter-Medium.otf')),max(2,round(size))));return fonts[key]
def metrics(w):
 f=font(w['font'],w['size']);tracking=w.get('tracking',-60)/1000;boxes=[]
 for i,c in enumerate(w['text']):
  x=f.getlength(w['text'][:i])+i*f.size*tracking;l,t,r,b=f.getbbox(c,anchor='ls');boxes.append((x+l,t,x+r,b))
 l=min(b[0] for b in boxes);t=min(b[1] for b in boxes);r=max(b[2] for b in boxes);b=max(b[3] for b in boxes);return dict(left=l,top=t,width=r-l,height=b-t)
data=[{'page':p,'metrics':[metrics(w) for w in p['words']]} for plan in plans for p in plan['pages']]
code="const fs=require('fs'),vm=require('vm'),c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-two/geometry.jsx','utf8'),c);let s='';process.stdin.on('data',v=>s+=v);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s).map(x=>c.StorylensCaptionGeometry.layout(x.page,x.metrics,720,1280)))));"
layouts=json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(data),cwd=root,text=True,encoding="utf8"))
gradient=Image.open(root/'editor_plugins/caption-patterns/caption-1-gradient.png').convert('RGBA');tiles=[]
for item,layout in zip(data,layouts):
 page=item['page'];canvas=Image.new('RGBA',(720,400),(0,0,0,255))
 for w,m,position in zip(page['words'],item['metrics'],layout['words']):
  f=font(w['font'],w['size']);tracking=w.get('tracking',-60)/1000;mask=Image.new('L',(math.ceil(m['width'])+4,math.ceil(m['height'])+4));pen=ImageDraw.Draw(mask)
  for i,c in enumerate(w['text']):pen.text((2-m['left']+f.getlength(w['text'][:i])+i*f.size*tracking,2-m['top']),c,font=f,anchor='ls',fill=255)
  scale=position['scale'];mask=mask.resize((max(1,round(mask.width*scale)),max(1,round(mask.height*scale))),Image.Resampling.LANCZOS);tile=Image.new('RGBA',mask.size,tuple(w['fill_rgb']));tile.putalpha(mask);x=round(position['x']-m['width']*scale/2-2*scale);y=round(position['y']-440-m['height']*scale/2-2*scale);canvas.alpha_composite(tile,(x,y))
 title='OFFLINE layout | '+page['pattern_id']+' | '+str(len(page['words']))+' words';ImageDraw.Draw(canvas).text((16,14),title,fill=(140,150,160));tiles.append(canvas.convert('RGB'))
cols=3;tw,th=480,267;sheet=Image.new('RGB',(cols*tw,math.ceil(len(tiles)/cols)*th),(25,25,25))
for i,im in enumerate(tiles):sheet.paste(im.resize((tw,th),Image.Resampling.LANCZOS),(i%cols*tw,i//cols*th))
sheet.save(out/'layout-study.jpg',quality=92);(out/'sample-plans.json').write_text(json.dumps(plans,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');(out/'sample-layouts.json').write_text(json.dumps(layouts,indent=2)+'\n',encoding='utf-8');print(str((out/'layout-study.jpg').resolve()))
