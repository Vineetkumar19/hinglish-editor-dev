"""Photographic thumbnail compositions: real source pixels and editable HTML lettering."""
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image,ImageEnhance,ImageFilter


def cpu_only(root,payload,script):
    """Only a fully sourced, exact-text composition can bypass the model queue."""
    if payload.get('mode')!='thumbnail' or payload.get('portrait') or payload.get('background'):return False
    if payload.get('reference') or payload.get('thumbnail_design',{}).get('workflow')=='photo':return False
    if payload.get('thumbnail_design',{}).get('text_mode')!='exact':return False
    from .thumbnail_layout import style_for
    config=payload.get('thumbnail_design',{})
    try:return config.get('category','youtube')=='youtube' and bool(style_for(root,script).get('photography'))
    except (OSError,ValueError,KeyError):return False


def render(root, folder, config, hook, subtitle, photos, index=0,finish=None):
    """Render one locally editable Hyperframes composition, without diffusion."""
    if (finish or {}).get('recipe')=='trio_brush':
        from .kkr_thumbnail import render as kkr_render
        return kkr_render(root,folder,config,hook,photos,index)
    if (finish or {}).get('recipe')=='independent_trio':
        from .independent_trio import render as trio_render
        return trio_render(root,folder,config,hook,photos,index)
    root, folder = Path(root), Path(folder)
    work = folder / f'design-{index+1}'
    work.mkdir(parents=True, exist_ok=True)
    for key in ('left', 'right', 'background','left_logo','right_logo'):
        if key.endswith('_logo') and key not in photos:continue
        source = Path(photos[key]['path'])
        if not source.is_file():
            raise ValueError('A saved thumbnail source photo is missing. Restore the photo and try again.')
        shutil.copyfile(source, work / f'{key}.png')
    # Use the original portraits without mirroring faces or altering jersey lettering.
    with Image.open(work/'left.png') as im:
        box=photos['left'].get('crop')
        if box:im=im.crop(tuple(box))
        im.save(work/'left.png')
    if finish:
        for key in ('left','right'):
            with Image.open(work/f'{key}.png') as original:
                subject=original.convert('RGBA');alpha=subject.getchannel('A')
                rgb=ImageEnhance.Contrast(subject.convert('RGB')).enhance(1.035)
                rgb=rgb.filter(ImageFilter.UnsharpMask(radius=.8,percent=58,threshold=3))
                rgb.putalpha(alpha);rgb.save(work/f'{key}.png')
        for key in ('left_logo','right_logo'):
            file=work/f'{key}.png'
            if file.is_file():
                with Image.open(file) as original:
                    logo=original.convert('RGBA');bounds=logo.getbbox()
                    if bounds:logo.crop(bounds).save(file)
    font = Path('C:/Windows/Fonts/impact.ttf')
    if not font.is_file():raise ValueError('The local headline font is unavailable. Restore Impact and retry.')
    shutil.copyfile(font,work/'headline.ttf')
    width,height=config['width'],config['height']
    title=html.escape(hook)
    # The actual text stays selectable/editable in the saved composition.
    # Each phrase is measured by the browser; longer replacements shrink safely.
    words=re.split(r'\s+(?:vs\.?|versus)\s+',hook,flags=re.I)
    title=(f'<span>{html.escape(words[0])}</span><i>vs</i><span>{html.escape(words[1])}</span>'
           if len(words)==2 else f'<span>{title}</span>')
    names=[html.escape(photos[key]['name']) for key in ('left','right')]
    template='''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:Headline;src:url(headline.ttf)}*{box-sizing:border-box}html,body{margin:0;background:#061126;width:WIDTHpx;height:HEIGHTpx;overflow:hidden}
#composition{width:WIDTHpx;height:HEIGHTpx;position:relative;overflow:hidden}#design{width:1280px;height:720px;position:relative;transform-origin:0 0;transform:scale(SCALEX,SCALEY);overflow:hidden;background:#071327;font-family:Arial,sans-serif}
.stadium{position:absolute;width:100%;height:100%;object-fit:cover;filter:brightness(.7) saturate(.75)}
.colour{position:absolute;inset:0;background:linear-gradient(105deg,rgba(0,55,156,.8),rgba(0,26,78,.15) 46%,rgba(146,103,0,.16) 53%,rgba(255,184,0,.45))}
.beam{position:absolute;left:610px;top:-90px;width:2px;height:800px;background:#fff7cd;transform:rotate(15deg);box-shadow:0 0 45px 16px #ffd77a55;opacity:.48}
.portrait{position:absolute;object-fit:contain;filter:drop-shadow(0 8px 14px #020919aa)}
.left{width:600px;height:650px;left:-28px;top:26px}.right{width:545px;height:545px;right:-4px;top:32px}
.shade{position:absolute;inset:0;background:linear-gradient(0deg,#061024 0%,#061024f5 12%,#061024b8 25%,transparent 47%)}
.name{position:absolute;top:465px;font-size:18px;letter-spacing:2.6px;font-weight:700;color:#e1eeff;text-shadow:0 2px 6px #00102c}.name.left-name{left:90px}.name.right-name{right:90px;color:#fff3b0}
.live{position:absolute;top:34px;left:50%;transform:translateX(-50%);padding:12px 22px;background:#e52b35;color:white;font-size:19px;font-weight:800;letter-spacing:2px;box-shadow:0 8px 30px #0005;white-space:nowrap}
.live:before{content:"";display:inline-block;width:9px;height:9px;background:white;border-radius:50%;margin-right:12px;vertical-align:2px}
.headline{position:absolute;left:54px;right:54px;top:500px;height:122px;display:flex;align-items:center;justify-content:center;gap:27px;white-space:nowrap;font-family:Headline;font-size:116px;font-weight:400;line-height:1;filter:drop-shadow(0 5px 3px #0008)}
.headline span{color:#f4f7ff}.headline span:last-child{color:#ffcf39}.headline i{font:italic 54px Headline;color:#afc3df;flex-shrink:0}
.rule{position:absolute;left:84px;right:84px;top:638px;height:1px;background:linear-gradient(90deg,#38a0ff,transparent 43%,transparent 57%,#ffcf39)}
.footer{position:absolute;top:626px;left:50%;transform:translateX(-50%);font-size:19px;font-weight:700;letter-spacing:5px;color:#d6e1f4;background:#061024;padding:0 22px;white-space:nowrap}
</style></head><body><main id="composition" data-composition-id="main" data-no-timeline data-start="0" data-duration="1" data-width="WIDTH" data-height="HEIGHT" data-fps="30"><div id="design">
<img class="stadium" src="background.png" alt="Real stadium photograph"><div class="colour"></div><div class="beam"></div>
<img class="portrait left" src="left.png" alt="LEFTNAME"><img class="portrait right" src="right.png" alt="RIGHTNAME"><div class="shade"></div>
<div class="live">SUBTITLE</div><div class="name left-name">LEFTNAME</div><div class="name right-name">RIGHTNAME</div><div class="headline">TITLE</div><div class="rule"></div><div class="footer">MATCHDAY</div>
</div></main><script>window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
window.__hf.buildReady.design=document.fonts.ready.then(()=>{let e=document.querySelector('.headline');let s=116;while(e.scrollWidth>e.clientWidth&&s>28){e.style.fontSize=(--s)+'px'}return Promise.all([...document.images].map(im=>im.decode()))});</script></body></html>'''
    if finish:
        css=(Path(__file__).parent/'templates/cricket-photo-finish.css').read_text('utf-8')
        template=template.replace('</style>',css+'\n</style>')
        backdrops='<div class="team-field blue"></div><div class="team-field gold"></div><div class="energy"></div>'
        badges=''
        for key,side in (('left_logo','left'),('right_logo','right')):
            if key in photos:
                backdrops+=f'<img class="crest-backdrop crest-{side}" src="{key}.png" alt="">'
                badges+=f'<img class="team-badge badge-{side}" src="{key}.png" alt="{html.escape(photos[key]["name"])}">'
        template=template.replace('<div class="beam"></div>','<div class="beam"></div>'+backdrops)
        template=template.replace('<div class="live">',badges+'<div class="live">')
    replacements={'WIDTH':str(width),'HEIGHT':str(height),'SCALEX':str(width/1280),'SCALEY':str(height/720),
                  'LEFTNAME':names[0],'RIGHTNAME':names[1],'SUBTITLE':html.escape(subtitle or 'LIVE STREAM'),'TITLE':title}
    for key,value in replacements.items():template=template.replace(key,value)
    (work/'index.html').write_text(template,encoding='utf-8')
    node=Path('C:/Program Files/nodejs/node.exe');cli=root/'tools/hyperframes-runtime/node_modules/hyperframes/bin/hyperframes.mjs'
    env={**os.environ,'HYPERFRAMES_NO_TELEMETRY':'1','HYPERFRAMES_BROWSER_PATH':'C:/Program Files/Google/Chrome/Application/chrome.exe'}
    done=subprocess.run([str(node),str(cli),'snapshot',str(work),'--at','0','--no-end','--keep','--output',str(work/'frames'),'--describe','false','--no-browser-gpu','--json'],
        cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (work/'render.log').write_text(done.stdout+'\n'+done.stderr,encoding='utf-8')
    frame=work/'frames/at-0s.png'
    if done.returncode or not frame.is_file():raise RuntimeError('The local thumbnail composition could not render. Your photos and editable design are saved; retry Create images.')
    target=folder/f'thumbnail-{index+1}.png'
    with Image.open(frame) as im:
        if im.size!=(width,height):raise RuntimeError('The local thumbnail has the wrong dimensions. The editable design is saved; retry Create images.')
        im.convert('RGB').save(target);im.convert('RGB').save(target.with_suffix('.jpg'),quality=95,subsampling=0)
    return target


def create(root,folder,config,topic,style,progress,context):
    """A source-backed photo recipe never silently switches to invented players."""
    from .image_design import report
    from .thumbnail import _plan
    from hinglish_visuals.brain import open_brain
    photos=style['photography']
    from .thumbnail_memory import context as thumbnail_memory
    if config['aspect']!='16:9':raise ValueError('Choose Landscape 16:9 for this saved match-photo layout, then create the thumbnail again.')
    hook=config['title'] if config['text_mode']=='exact' else ''
    if config['text_mode']=='auto':
        brain=open_brain(root,progress=progress)
        brain.context_feature='thumbnail'
        try:
            answer=_plan(brain,'Choose one short, accurate thumbnail headline from the user request. Do not invent a match date, score or result. Return concepts with hook and background_prompt. The images are already real photographs; do not request image generation.',
                {'story':topic,'creator_profile':context,'design':config,'owner_thumbnail_guidance':thumbnail_memory(root)}, {'type':'object','properties':{'concepts':{'type':'array','minItems':1,'maxItems':1,'items':{'type':'object','properties':{'hook':{'type':'string'},'background_prompt':{'type':'string'}},'required':['hook','background_prompt']}}},'required':['concepts']},progress=progress,count=1)
            hook=str(answer['concepts'][0]['hook']).strip()
        finally:brain.close()
    if not hook:raise ValueError('Enter a headline for this match thumbnail.')
    files=[]
    for i in range(config['count']):
        progress('Composing real player photos with exact editable lettering in local Hyperframes')
        extra={'finish':style['art_direction']} if style.get('art_direction') else {}
        files.append(render(root,folder,config,hook,config['subtitle'],photos,i,**extra).name)
    project={'settings':config,'story':topic,'files':files,'concepts':[{'hook':hook} for _ in files],
        'local_model_lettering':False,'ai_backgrounds':False,'local_models':{'image':'Real source photographs','composition':'Local Hyperframes HTML/CSS'},
        'reference_style':style['id'],'sources':photos,'identity_note':'Real official team portraits over a sourced stadium photograph. Original player faces and jersey lettering are preserved. Editable HTML lettering; no diffusion-generated players or text.'}
    project['art_direction']=style.get('art_direction');project['owner_thumbnail_guidance']=thumbnail_memory(root)
    if style.get('identity_note'):project['identity_note']=style['identity_note']
    if style.get('local_models'):project['local_models']=style['local_models']
    if style.get('ai_backgrounds'):project['ai_backgrounds']=True
    if style.get('asset_preparation'):project['asset_preparation']=style['asset_preparation']
    if style.get('include_original_sources'):project['include_original_sources']=True
    (folder/'thumbnail-project.json').write_text(json.dumps(project,indent=2),encoding='utf-8')
    return report(folder,project)
