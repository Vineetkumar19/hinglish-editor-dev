"""Offline production-plan preview; not a native AE or exact-source claim."""
from pathlib import Path
import json,subprocess,math
from PIL import Image,ImageFont,ImageDraw,ImageFilter
root=Path(__file__).resolve().parents[2];out=root/'output/caption-three-ae';profile=json.loads((root/'editor_plugins/caption-three/profile.json').read_text())
fontfiles={'bold':root/'hinglish_captions/fonts/caption-three/CaptionThree-BoldItalic.ttf','support':root/'hinglish_captions/fonts/caption-three/CaptionThree-RegularItalic.ttf','regular':root/'hinglish_captions/fonts/caption-three/CaptionThree-RegularItalic.ttf','playful':root/'hinglish_captions/fonts/caption-three/CaptionThree-Playful.ttf','blue':Path('C:/Windows/Fonts/arialbi.ttf')}
requests=[]
for i,r in enumerate(profile['recipes']):
 words=[]
 for j,text in enumerate(r['text'].split()):
  row=next(row for row in r['rows'] if j in row['words']);start=(row['source_onset']-r['source_start'])/30
  words.append({'text':text,'start':start,'end':(r['source_end']-r['source_start'])/30})
 requests.append({'script':r['text'],'duration':(r['source_end']-r['source_start'])/30,'template_slot':i,'words':words})
requests+= [{'script':s,'duration':30} for s in ['Toh flat nahi mila, PG le liya. Socha chalo PG mein basic cheezein hongi hi. Washing machine fridge laptop aur accommodation har video mein alag text reh sakta hai.','Every new script deserves clear readable typography. International communication builds meaningful relationships. Keep the style consistent when 12 words change into a much longer paragraph.']]
js="const fs=require('fs'),m=require('./editor_plugins/caption-three/model.cjs');console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(r=>m.prepare(r))));"
plans=json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(requests).encode('utf8'),cwd=root))
geo="const fs=require('fs'),vm=require('vm'),c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-three/geometry.jsx','utf8'),c);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(v=>c.StorylensCaptionGeometry.layout(v.page,v.metrics,720,1280))));"
jobs=[]
def measure(w):
 f=ImageFont.truetype(str(fontfiles[w['font']]),round(w['size']));boxes=[]
 for j,c in enumerate(w['text']):
  b=f.getbbox(c,anchor='ls');x=f.getlength(w['text'][:j])+j*f.size*w['tracking']/1000;boxes.append([b[0]+x,b[1],b[2]+x,b[3]])
 l=min(b[0] for b in boxes);t=min(b[1] for b in boxes);return {'left':l,'top':t,'width':max(b[2] for b in boxes)-l,'height':max(b[3] for b in boxes)-t}
for p in plans:
 for q in p['pages']:jobs.append({'page':q,'metrics':[measure(w) for w in q['words']]})
geometries=json.loads(subprocess.check_output(['node','-e',geo],input=json.dumps(jobs).encode('utf8'),cwd=root));index=0
for p in plans:
 for q in p['pages']:q['preview_geometry']=geometries[index];q['preview_metrics']=jobs[index]['metrics'];index+=1
(out/'sample-plans.json').write_text(json.dumps(plans,indent=2))
def smooth(x):
 x=min(1,max(0,x));return x*x*x*(x*(x*6-15)+10)
def at(keys,t,n):
 a=keys[0]
 for b in keys[1:]:
  if t<=b[0]:
   f=min(1,max(0,(t-a[0])/max(.000001,b[0]-a[0])));return a[n]+(b[n]-a[n])*f
  a=b
 return a[n]
def render(page,t):
 stage=Image.new('RGBA',(720,1280));g=page['preview_geometry'];span=page['end']-page['start'];age=t-page['start'];phase=age/span
 for i,w in enumerate(page['words']):
  m=page['preview_metrics'][i];p=g['words'][i];onset=w['start']-page['start'];fade=min(.24,max(.001,span-onset)*.45);gate=smooth((age-onset)/max(.001,fade));leave=smooth((span-age)/max(.001,min(.20,span*.18)));alpha=gate*leave*at(w['focus_track'],phase,1)
  if alpha<.001:continue
  font=ImageFont.truetype(str(fontfiles[w['font']]),round(w['size']));layer=Image.new('RGBA',(max(1,math.ceil(m['width']+40)),max(1,math.ceil(m['height']+40))));draw=ImageDraw.Draw(layer)
  for j,c in enumerate(w['text']):draw.text((20-m['left']+font.getlength(w['text'][:j])+j*font.size*w['tracking']/1000,20-m['top']),c,font=font,fill=tuple(w['fill_rgb'])+(round(alpha*255),),anchor='ls')
  blur=(at(w['focus_track'],phase,2)+6*(1-gate));layer=layer.filter(ImageFilter.GaussianBlur(blur));scale=p['scale'];layer=layer.resize((max(1,round(layer.width*scale)),max(1,round(layer.height*scale))),Image.Resampling.LANCZOS);stage.alpha_composite(layer,(round(p['x']-layer.width/2),round(p['y']-layer.height/2)))
 z=at(page['camera'],phase,1);pivot=g['pivot'];stage=stage.transform(stage.size,Image.Transform.AFFINE,(1/z,0,pivot[0]*(1-1/z),0,1/z,pivot[1]*(1-1/z)),Image.Resampling.BICUBIC)
 return stage
images=[]
for i,p in enumerate(plans[:12]):
 q=p['pages'][0];t=max(w['start'] for w in q['words'])+.90;t=min(t,q['end']-.22);im=Image.new('RGBA',(720,1280),(237,237,235,255));im.alpha_composite(render(q,t));im.convert('RGB').save(out/f'pattern-{i:02}.png');tile=im.crop((0,490,720,1120)).resize((360,315)).convert('RGB');ImageDraw.Draw(tile).text((6,5),profile['recipes'][i]['id'],fill=(0,0,0));images.append(tile)
sheet=Image.new('RGB',(1440,335*3),(220,220,220))
for i,tile in enumerate(images):sheet.paste(tile,(i%4*360,i//4*335))
sheet.save(out/'caption-only-patterns.jpg',quality=95)
# One small ten-second continuous preview; no Adobe or source footage involved.
from imageio_ffmpeg import get_ffmpeg_exe
p=plans[12];fps=30;process=subprocess.Popen([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','360x640','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(out/'caption-three-preview-10s.mp4')],stdin=subprocess.PIPE)
for n in range(fps*10):
 t=n/fps;q=next((q for q in p['pages'] if q['start']<=t<q['end']),None);im=Image.new('RGBA',(720,1280),(237,237,235,255))
 if q:im.alpha_composite(render(q,t))
 process.stdin.write(im.convert('RGB').resize((360,640),Image.Resampling.LANCZOS).tobytes())
process.stdin.close();assert process.wait()==0
print('Prepared twelve recipe frames and one ten-second motion preview.')
