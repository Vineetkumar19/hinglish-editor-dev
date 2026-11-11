"""A fresh three-player poster from independent photographs and locally authored layers."""
import html
import os
from pathlib import Path
import random
import shutil
import subprocess

from PIL import Image,ImageEnhance,ImageFilter


def painted_band(seed):
    rng=random.Random(seed)
    flecks=[]
    for y in (509,703):
        for _ in range(42):
            x=rng.randint(32,1220);length=rng.randint(8,65);dy=rng.randint(-8,8)
            flecks.append(f'<path d="M{x},{y+dy} q{length/2},-2 {length},0" stroke="#c40615" stroke-width="{rng.randint(2,6)}"/>')
    return '''<svg class="brush" viewBox="0 0 1280 720" aria-hidden="true"><defs>
<linearGradient id="paint" x2="0" y2="1"><stop stop-color="#e01020"/><stop offset=".55" stop-color="#cb0011"/><stop offset="1" stop-color="#a80013"/></linearGradient>
<filter id="rough-paint" x="-5%" y="-20%" width="110%" height="140%"><feTurbulence type="fractalNoise" baseFrequency=".028 .095" numOctaves="3" seed="31" result="grain"/><feDisplacementMap in="SourceGraphic" in2="grain" scale="22" xChannelSelector="R" yChannelSelector="G"/></filter>
</defs><g filter="url(#rough-paint)"><path d="M34 511 Q380 502 637 510 T1244 508 L1250 703 Q910 709 640 704 T29 707Z" fill="url(#paint)"/></g>'''+''.join(flecks)+'</svg>'


def render(root,folder,config,hook,photos,index=0):
    root,folder=Path(root),Path(folder);work=folder/f'design-{index+1}';work.mkdir(parents=True,exist_ok=True)
    for key in ('left','center','right','crest','background'):
        source=Path(photos[key]['path'])
        if not source.is_file():raise ValueError('A saved thumbnail source photo is missing. Restore the photo and try again.')
        if 'kkr' in str(source).casefold():raise ValueError('This independent poster requires its own source photographs.')
        with Image.open(source) as original:
            image=original.convert('RGBA')
            if key in ('left','center','right'):
                alpha=image.getchannel('A').filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(.35))
                image=ImageEnhance.Contrast(image.convert('RGB')).enhance(1.08)
                image=ImageEnhance.Color(image).enhance(1.04).filter(ImageFilter.UnsharpMask(radius=.85,percent=55,threshold=3))
                image.putalpha(alpha)
            elif key=='crest':
                bounds=image.getbbox()
                if bounds:image=image.crop(bounds)
            image.save(work/f'{key}.png')
    shutil.copyfile('C:/Windows/Fonts/impact.ttf',work/'headline.ttf')
    width,height=config['width'],config['height']
    markup='''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:Headline;src:url(headline.ttf)}*{box-sizing:border-box}html,body{margin:0;background:#020a1c;width:WIDTHpx;height:HEIGHTpx;overflow:hidden}
#composition{position:relative;width:WIDTHpx;height:HEIGHTpx;overflow:hidden}#design{position:relative;width:1280px;height:720px;transform:scale(SCALE);transform-origin:0 0;overflow:hidden;background:#031634}
.background{position:absolute;inset:0;width:1280px;height:720px;object-fit:cover;filter:saturate(1.12) brightness(.85)}
.wash{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 48%,#009fff25,transparent 50%),linear-gradient(0deg,#01050bdd,transparent 55%)}
.crest{position:absolute;left:306px;top:-8px;width:688px;height:520px;object-fit:contain;opacity:.50;filter:drop-shadow(0 0 9px #fac63d4d)}
.portrait{position:absolute;height:auto;filter:drop-shadow(0 0 1px #fff4cdaa) drop-shadow(0 0 10px #00a8ffa0) drop-shadow(0 14px 14px #010711aa)}
.left{width:1120px;left:-340px;top:30px;transform:rotate(-2deg);transform-origin:50% 60%}.right{width:1120px;left:480px;top:38px;transform:rotate(2deg);transform-origin:50% 60%}
.center{width:1260px;left:10px;top:-40px;filter:drop-shadow(0 0 2px #fff5c999) drop-shadow(0 0 13px #099fffc0) drop-shadow(0 13px 12px #01030cb0)}
.lower-shade{position:absolute;inset:0;background:linear-gradient(0deg,#001128 0,#00112877 22%,transparent 45%)}
.brush{position:absolute;inset:0;width:1280px;height:720px;filter:drop-shadow(0 6px 4px #0008)}
.headline{position:absolute;left:0;top:508px;width:1280px;height:200px;overflow:visible;filter:drop-shadow(0 3px 2px #64000a88)}
#title{font-family:Headline;font-size:230px;letter-spacing:2px;fill:url(#silver);stroke:#fff9;stroke-width:.5px;paint-order:stroke fill}
</style></head><body><main id="composition" data-composition-id="main" data-no-timeline data-start="0" data-duration="1" data-width="WIDTH" data-height="HEIGHT" data-fps="30"><div id="design">
<img class="background" src="background.png" alt="New locally generated blue smoke and gold ember texture, without people"><div class="wash"></div><img class="crest" src="crest.png" alt="Authentic Mumbai Indians crest">
<img class="portrait left" src="left.png" alt="Jasprit Bumrah, official MI photograph"><img class="portrait right" src="right.png" alt="Suryakumar Yadav, official MI photograph"><img class="portrait center" src="center.png" alt="Rohit Sharma, official MI photograph"><div class="lower-shade"></div>BRUSH
<svg class="headline" viewBox="0 0 1280 200" role="img" aria-label="HEADLINE"><defs><linearGradient id="silver" x2="0" y2="1"><stop stop-color="#fff"/><stop offset=".5" stop-color="#f3f3f5"/><stop offset="1" stop-color="#d5d5db"/></linearGradient></defs><text id="title" x="640" y="180" text-anchor="middle">HEADLINE</text></svg>
</div></main><script>window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
window.__hf.buildReady.poster=document.fonts.load('248px Headline').then(()=>{let t=document.getElementById('title'),s=248,c=document.createElement('canvas').getContext('2d'),m;do{c.font=s+'px Headline';m=c.measureText(t.textContent);if(m.width+2*t.textContent.length<=1165&&m.actualBoundingBoxAscent+m.actualBoundingBoxDescent<=172)break;s--}while(s>28);t.style.fontSize=s+'px';t.setAttribute('y',100+(m.actualBoundingBoxAscent-m.actualBoundingBoxDescent)/2);return Promise.all([...document.images].map(im=>im.decode()))});</script></body></html>'''
    for key,value in {'WIDTH':str(width),'HEIGHT':str(height),'SCALE':str(width/1280),'BRUSH':painted_band(config['seed']+index),'HEADLINE':html.escape(hook)}.items():markup=markup.replace(key,value)
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
