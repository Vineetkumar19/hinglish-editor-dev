"""Reference-inspired KKR poster: original portrait pixels and local vector effects."""
import html
import os
from pathlib import Path
import random
import shutil
import subprocess

from PIL import Image


def effects(seed):
    rng=random.Random(seed)
    embers=[]
    for _ in range(205):
        x,y=rng.randrange(1280),rng.randrange(500)
        size=rng.uniform(.7,2.2);colour=rng.choice(['#ffb83e','#ed6ef5','#ff7525','#cc9dff'])
        embers.append(f'<circle cx="{x}" cy="{y}" r="{size:.2f}" fill="{colour}" opacity="{rng.uniform(.25,.85):.2f}"/>')
    flames=[]
    for x in range(-30,1340,58):
        h=rng.randrange(95,270);lean=rng.randrange(-55,55)
        flames.append(f'<path d="M{x-60},570 Q{x+80},470 {x+lean},{570-h} Q{x+80},500 {x+60},570Z" fill="url(#fire)"/>')
    return '''<svg class="atmosphere" viewBox="0 0 1280 720" aria-hidden="true"><defs>
<linearGradient id="fire" x2="0" y2="1"><stop stop-color="#fff4b0"/><stop offset=".3" stop-color="#ffbd35"/><stop offset=".6" stop-color="#ee4418"/><stop offset="1" stop-color="#b5154d" stop-opacity="0"/></linearGradient>
<filter id="fire-warp" x="-30%" y="-40%" width="160%" height="190%"><feTurbulence type="fractalNoise" baseFrequency=".018 .011" numOctaves="3" seed="17" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="58" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation="3"/></filter>
</defs><g filter="url(#fire-warp)" opacity=".83">'''+''.join(flames)+'</g><g>'+''.join(embers)+'</g></svg>'


def brush(seed):
    rng=random.Random(seed)
    top=[(27,519)]+[(x,511+rng.randrange(-8,9)) for x in range(50,1241,21)]+[(1254,514)]
    bottom=[(1248,704)]+[(x,706+rng.randrange(-7,9)) for x in range(1230,39,-22)]+[(26,704)]
    points=' '.join(f'{x},{y}' for x,y in top+bottom)
    streaks=''.join(f'<path d="M{x},500 l{rng.randrange(35,105)},2" stroke="#cf131f" stroke-width="{rng.randrange(3,8)}"/>' for x in range(45,1200,135))
    return f'<svg class="brush" viewBox="0 0 1280 720" aria-hidden="true"><defs><linearGradient id="red" x2="0" y2="1"><stop stop-color="#df1520"/><stop offset=".55" stop-color="#d30013"/><stop offset="1" stop-color="#a80014"/></linearGradient></defs><polygon points="{points}" fill="url(#red)"/>{streaks}</svg>'


def render(root,folder,config,hook,photos,index=0):
    root,folder=Path(root),Path(folder)
    work=folder/f'design-{index+1}';work.mkdir(parents=True,exist_ok=True)
    for key in ('people','crest','brush'):
        source=Path(photos[key]['path'])
        if not source.is_file():raise ValueError('A saved thumbnail source photo is missing. Restore the photo and try again.')
        shutil.copyfile(source,work/f'{key}.png')
    shutil.copyfile('C:/Windows/Fonts/impact.ttf',work/'headline.ttf')
    width,height=config['width'],config['height']
    markup='''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:Headline;src:url(headline.ttf)}*{box-sizing:border-box}html,body{margin:0;background:#10041e;width:WIDTHpx;height:HEIGHTpx;overflow:hidden}
#composition{position:relative;overflow:hidden;width:WIDTHpx;height:HEIGHTpx}#design{position:relative;width:1280px;height:720px;transform:scale(SCALE);transform-origin:0 0;overflow:hidden;background:radial-gradient(ellipse at 52% 64%,#8410cf 0,#3a0b62 32%,#190528 64%,#080510 100%)}
.haze{position:absolute;inset:0;background:radial-gradient(ellipse at 17% 61%,#ec235d5c,transparent 36%),radial-gradient(ellipse at 87% 55%,#f8641052,transparent 34%),radial-gradient(ellipse at 52% 53%,#ab32fd80,transparent 30%)}
.streak{position:absolute;left:-100px;top:220px;width:1480px;height:3px;transform:rotate(-16deg);background:linear-gradient(90deg,transparent,#ff6215b0,transparent 55%);filter:blur(4px)}
.crest{position:absolute;left:298px;top:-65px;width:690px;height:650px;object-fit:contain;opacity:.54;filter:drop-shadow(0 0 8px #dba75638) saturate(.9)}
.atmosphere{position:absolute;inset:0;width:1280px;height:720px;mix-blend-mode:screen}
.people{position:absolute;left:-10px;top:22px;width:1300px;height:auto;filter:drop-shadow(0 0 2px #ffe8fa99) drop-shadow(0 0 11px #b81ef8a0) drop-shadow(0 12px 12px #08000caa)}
.bottom-shade{position:absolute;inset:0;background:linear-gradient(0deg,#08020d 0,transparent 36%);pointer-events:none}
.brush{position:absolute;left:0;top:480px;width:1280px;height:auto;filter:drop-shadow(0 5px 5px #0007)}
.headline{position:absolute;left:0;top:508px;width:1280px;height:200px;overflow:visible;filter:drop-shadow(0 3px 2px #63000977)}
#title{font-family:Headline;font-size:212px;letter-spacing:2px;fill:url(#letter-metal);stroke:#fff8;stroke-width:.4px;paint-order:stroke fill}
</style></head><body><main id="composition" data-composition-id="main" data-no-timeline data-start="0" data-duration="1" data-width="WIDTH" data-height="HEIGHT" data-fps="30"><div id="design">
<div class="haze"></div><div class="streak"></div><img class="crest" src="crest.png" alt="Kolkata Knight Riders crest">EFFECTS
<img class="people" src="people.png" alt="Real portraits of Sunil Narine, Gautam Gambhir and Andre Russell from the owner reference"><div class="bottom-shade"></div>BRUSH
<svg class="headline" viewBox="0 0 1280 200" role="img" aria-label="HEADLINE"><defs><linearGradient id="letter-metal" x2="0" y2="1"><stop stop-color="#fff"/><stop offset=".55" stop-color="#f4f4f4"/><stop offset="1" stop-color="#d2d2d5"/></linearGradient></defs><text id="title" x="640" y="171" text-anchor="middle">HEADLINE</text></svg>
</div></main><script>window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
window.__hf.buildReady.kkr=document.fonts.load('248px Headline').then(()=>{let t=document.getElementById('title'),s=248,c=document.createElement('canvas').getContext('2d'),m;do{c.font=s+'px Headline';m=c.measureText(t.textContent);if(m.width+2*t.textContent.length<=1165&&m.actualBoundingBoxAscent+m.actualBoundingBoxDescent<=172)break;s--}while(s>28);t.style.fontSize=s+'px';t.setAttribute('y',100+(m.actualBoundingBoxAscent-m.actualBoundingBoxDescent)/2);return Promise.all([...document.images].map(im=>im.decode()))});</script></body></html>'''
    for key,value in {'WIDTH':str(width),'HEIGHT':str(height),'SCALE':str(width/1280),'EFFECTS':effects(config['seed']+index),'BRUSH':'<img class="brush" src="brush.png" alt="">','HEADLINE':html.escape(hook)}.items():markup=markup.replace(key,value)
    (work/'index.html').write_text(markup,encoding='utf-8')
    node=Path('C:/Program Files/nodejs/node.exe');cli=root/'tools/hyperframes-runtime/node_modules/hyperframes/bin/hyperframes.mjs'
    env={**os.environ,'HYPERFRAMES_NO_TELEMETRY':'1','HYPERFRAMES_BROWSER_PATH':'C:/Program Files/Google/Chrome/Application/chrome.exe'}
    done=subprocess.run([str(node),str(cli),'snapshot',str(work),'--at','0','--no-end','--keep','--output',str(work/'frames'),'--describe','false','--no-browser-gpu','--json'],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (work/'render.log').write_text(done.stdout+'\n'+done.stderr,encoding='utf-8')
    frame=work/'frames/at-0s.png'
    if done.returncode or not frame.is_file():raise RuntimeError('The local thumbnail composition could not render. Your photos and editable design are saved; retry Create images.')
    target=folder/f'thumbnail-{index+1}.png'
    with Image.open(frame) as image:
        if image.size!=(width,height):raise RuntimeError('The local thumbnail has the wrong dimensions. The editable design is saved; retry Create images.')
        image.convert('RGB').save(target);image.convert('RGB').save(target.with_suffix('.jpg'),quality=95,subsampling=0)
    return target
