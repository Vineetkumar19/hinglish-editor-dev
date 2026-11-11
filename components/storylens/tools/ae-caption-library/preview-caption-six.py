"""Offline native-plan preview/alpha audit. Does not launch or control Adobe."""
from pathlib import Path
import json,subprocess,math
from PIL import Image,ImageDraw,ImageFont,ImageFilter
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'output/caption-six-ae'
profile=json.loads((ROOT/'editor_plugins/caption-six/profile.json').read_text(encoding='utf8'))
fonts={k:ROOT/'hinglish_captions/fonts'/v for k,v in profile['font_files'].items()}
requests=[]
for slot,r in enumerate(profile['recipes']):
    words=[];duration=(r['source_end']-r['source_start'])/30
    for i,text in enumerate(r['text'].split()):
        row=next(x for x in r['rows'] if i in x['words']);start=(row['source_onset']-r['source_start'])/30
        end=(row.get('source_off',r['source_end'])-r['source_start'])/30
        words.append({'text':text,'start':start,'end':max(start+.01,end)})
    requests.append({'script':r['text'],'duration':duration,'template_slot':slot,'words':words})
owner='Bhukh lagi, Zomato khola, order kiya… aur yahin se meri barbaadi shuru hoti hai. Location map mein clearly marked hai. Pin drop bhi kiya hua hai. Photo bhi lagaya hua hai. Phir bhi delivery wala kahin aur hi ghoom raha hota hai. Do call, teen call, chaar call… har call Tamil mein. Main Hindi bolta hoon aur woh Tamil bolta hai. Beech mein Google Translator mediator ban jaata hai. Das-pandrah minute extra har order pe. Aur cash on delivery book nahi kiya, yeh toh aur bada risk hai non-Tamilian ke liye. Flipkart aur Amazon abhi tak try nahi kiya hai maine. Dua karo mere liye.'
requests.append({'script':owner,'duration':36})
js="const fs=require('fs'),m=require('./editor_plugins/caption-six/model.cjs');console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(r=>m.prepare(r))));"
plans=json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(requests).encode(),cwd=ROOT))
def measure(w):
    f=ImageFont.truetype(str(fonts[w['font']]),round(w['size'])); boxes=[];pen=0
    for c in w['text']:
        b=f.getbbox(c,anchor='ls');boxes.append((pen+b[0],b[1],pen+b[2],b[3]));pen+=f.getlength(c)+w['size']*w['tracking']/1000
    l=min(b[0] for b in boxes);t=min(b[1] for b in boxes)
    return {'left':l,'top':t,'width':max(b[2] for b in boxes)-l,'height':max(b[3] for b in boxes)-t}
jobs=[]
for p in plans:
    for q in p['pages']:jobs.append({'page':q,'metrics':[measure(w) for w in q['words']]})
js="const fs=require('fs'),vm=require('vm'),c={};vm.runInNewContext(fs.readFileSync('editor_plugins/caption-six/geometry.jsx','utf8'),c);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(v=>c.StorylensCaptionGeometry.layout(v.page,v.metrics,720,1280))));"
geos=json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(jobs).encode(),cwd=ROOT));index=0
for p in plans:
    for q in p['pages']:q['preview_geometry']=geos[index];q['preview_metrics']=jobs[index]['metrics'];index+=1
(OUT/'sample-plans.json').write_text(json.dumps(plans,indent=2,ensure_ascii=False),encoding='utf8')
def out(t): return 1-(1-max(0,min(1,t)))**3
def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)
def draw_path(stage,q,t):
    g=q['preview_geometry'];fac=g['factor']*g['fit']
    for s in q['decorations']:
        target=[g['rows'][r['id']] for r in q['rows'] if r['source_row'] in s.get('target_rows',[])]
        if not target:continue
        trigger=min(len(q['words'])-1,math.floor(s.get('trigger',0)*len(q['words'])/len(q['template_source'].split())));age=t-q['words'][trigger]['start']-s.get('delay',0)
        if age<0:continue
        progress=min(1,age/max(.001,min(s.get('duration',.45),q['end']-q['words'][trigger]['start']-s.get('delay',0))))
        box=[min(b['left'] for b in target),min(b['top'] for b in target),max(b['right'] for b in target),max(b['bottom'] for b in target)]
        pts=[p for seg in s['path'] for p in seg];mn=[min(p[d] for p in pts) for d in [0,1]];mx=[max(p[d] for p in pts) for d in [0,1]];circle=s['kind']=='circle';pad=(76 if circle else 10)*fac
        x0=box[0]-pad;x1=box[2]+pad;y0=box[1]-14*fac if circle else box[3]+14*fac;y1=box[3]+(16 if circle else 62)*fac
        def point(p):return (x0+(p[0]-mn[0])/max(1,mx[0]-mn[0])*(x1-x0),y0+(p[1]-mn[1])/max(1,mx[1]-mn[1])*(y1-y0))
        path=[]
        for seg in s['path']:
            for i in range(61):
                u=i/60;p=[(1-u)**3*seg[0][d]+3*(1-u)**2*u*seg[1][d]+3*(1-u)*u*u*seg[2][d]+u**3*seg[3][d] for d in [0,1]];path.append(point(p))
        dist=[0]
        for a,b in zip(path,path[1:]):dist.append(dist[-1]+math.dist(a,b))
        visible=[pt for d,pt in zip(dist,path) if d<=dist[-1]*progress]
        if len(visible)<2:continue
        layer=Image.new('RGBA',stage.size);d=ImageDraw.Draw(layer);d.line(visible,fill=s.get('color','#FFFFFF'),width=max(1,round(s.get('stroke',3)*fac)),joint='curve')
        if s.get('glow'):
            glow=layer.filter(ImageFilter.GaussianBlur(6*fac));glow.putalpha(glow.getchannel('A').point(lambda x:round(x*.55)));stage.alpha_composite(glow)
        stage.alpha_composite(layer)
def render(q,t):
    stage=Image.new('RGBA',(720,1280));g=q['preview_geometry']
    for i,w in enumerate(q['words']):
        if not w['start']<=t<w['visible_end']:continue
        pos=g['words'][i];m=q['preview_metrics'][i];fac=pos['scale'];available=w['visible_end']-w['start'];age=t-w['start'];rise=min(w['motion']['seconds'],available*.55);fade=min(w['motion']['fade_seconds'],available*.45);cut=q['motion_kind']=='cut';p=1 if cut else out(age/max(.001,rise));alpha=1 if cut else smooth(age/max(.001,fade));dy=w['motion']['y']*(1-p);blur=0 if cut else 7.5*(1-p)
        if q['motion_kind']=='count' and available>.16:
            leave=min(.14,available*.30);phase=max(0,(t-(w['visible_end']-leave))/leave);dy-=32*out(phase);alpha*=1-smooth(phase);blur+=7.5*out(phase)
        font=ImageFont.truetype(str(fonts[w['font']]),round(w['size']));layer=Image.new('RGBA',(max(1,math.ceil(m['width']+40)),max(1,math.ceil(m['height']+40))));d=ImageDraw.Draw(layer);pen=20-m['left']
        for c in w['text']:d.text((pen,20-m['top']),c,font=font,fill=tuple(w['fill_rgb'])+(round(alpha*255),),anchor='ls');pen+=font.getlength(c)+font.size*w['tracking']/1000
        if blur:layer=layer.filter(ImageFilter.GaussianBlur(blur))
        layer=layer.resize((max(1,round(layer.width*fac)),max(1,round(layer.height*fac))),Image.Resampling.LANCZOS);stage.alpha_composite(layer,(round(pos['x']-layer.width/2),round(pos['y']-layer.height/2+dy*fac)))
    draw_path(stage,q,t);return stage
tiles=[];alpha_checks=[]
for i,p in enumerate(plans[:16]):
    q=p['pages'][0];t=min(q['end']-.025,max(w['start'] for w in q['words'])+.22);im=render(q,t);im.save(OUT/f'pattern-{i:02}.png');alpha_checks.append({'slot':i,'transparent_corners':all(im.getpixel(pt)[3]==0 for pt in [(0,0),(719,0),(0,1279),(719,1279)]),'alpha_bbox':im.getchannel('A').getbbox()});background=Image.new('RGBA',im.size,(0,0,0,255));background.alpha_composite(im);tile=background.crop((0,610,720,1010)).resize((360,200)).convert('RGB');ImageDraw.Draw(tile).text((6,5),q['pattern_id'],fill=(180,180,180));tiles.append(tile)
sheet=Image.new('RGB',(1440,800))
for i,tile in enumerate(tiles):sheet.paste(tile,(i%4*360,i//4*200))
sheet.save(OUT/'patterns.jpg',quality=95)
# Compare entrance/hold/exit at corresponding source frames for the first group.
sheet=Image.new('RGB',(1200,5*210),(16,16,16));comparison=[]
q=plans[0]['pages'][0]
for j,frame in enumerate([3,12,20,30,35]):
    source=Image.open(OUT/'frames'/f'{frame:04}.jpg').crop((30,390,320,525)).resize((580,270));native=Image.new('RGBA',(720,1280),(0,0,0,255));native.alpha_composite(render(q,frame/30));native=native.crop((70,680,650,950)).convert('RGB');source.thumbnail((580,180));native.thumbnail((580,180));sheet.paste(source,(5,j*210+25));sheet.paste(native,(610,j*210+25));ImageDraw.Draw(sheet).text((6,j*210+4),f'Frame {frame}: actual source / offline native-plan reconstruction (not AE)',fill='white');comparison.append({'frame':frame,'time':frame/30})
sheet.save(OUT/'source-motion-comparison.jpg',quality=95)
from imageio_ffmpeg import get_ffmpeg_exe
process=subprocess.Popen([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','360x640','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(OUT/'caption-six-preview-10s.mp4')],stdin=subprocess.PIPE)
p=plans[-1]
for frame in range(300):
    t=frame/30;q=next((q for q in p['pages'] if q['start']<=t<q['end']),None);im=Image.new('RGBA',(720,1280),(0,0,0,255))
    if q:im.alpha_composite(render(q,t))
    process.stdin.write(im.convert('RGB').resize((360,640),Image.Resampling.LANCZOS).tobytes())
process.stdin.close();assert process.wait()==0
(OUT/'offline-preview-audit.json').write_text(json.dumps({'scope':'Offline PIL rendering of production plans and geometry, 10 seconds; no native AE run','alpha_checks':alpha_checks,'source_comparison_frames':comparison,'owner_script_words':len(owner.split()),'plans':len(plans),'limitations':['Exact source font identity unresolved','Native AE rendering and visual/motion acceptance remain owner testing','Source underline taper is approximated by editable round stroke in native code','Offline alpha samples are not native transparency proof']},indent=2),encoding='utf8')
print('Prepared 16 transparent pattern images, source motion comparisons and a 10-second offline owner-script preview.')
