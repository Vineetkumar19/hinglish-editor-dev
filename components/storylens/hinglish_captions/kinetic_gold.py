"""First supplied Klickpin caption draft; editable words with shared motion data."""
import json
from pathlib import Path
from functools import lru_cache
from contextlib import contextmanager
from contextvars import ContextVar
import math

_decorations_only = ContextVar('kinetic_gold_decorations_only', default=False)

@contextmanager
def decorations_only():
    token = _decorations_only.set(True)
    try:
        yield
    finally:
        _decorations_only.reset(token)

def echo_geometry(run, ratio, width, age):
    """Reserve room for the entire shadow, including its independent drift."""
    ratio *= min(1, width*.90/((run['width']*1.18+24)*ratio))
    maximum = min(1.42, (width*.90-24*ratio)/(run['width']*ratio))
    p=max(0,min(1,age/.95));ease=1-(1-p)**3
    fade=max(0,min(1,age/run.get('echo_fade_seconds',.30)));fade=fade*fade*(3-2*fade)
    return ratio,maximum-.12*ease,(-12+22*ease)*ratio,(5-10*ease)*ratio,.18*fade

def stripe_points(age,path=None):
    """Reveal a tapered curved brush stroke along its path, without stretching it."""
    p=max(0,min(1,age/.48));reveal=1-(1-p)**3
    if reveal<=0:return []
    upper=[];lower=[];x0,y0,x1,y1,thickness=path or [296,258,575,220,6]
    for i in range(65):
        t=reveal*i/64
        x=x0+(x1-x0)*t;y=y0+(y1-y0)*t-4*math.sin(math.pi*t)
        half=thickness*math.sin(math.pi*t)**.72
        upper.append((x,y-half));lower.append((x,y+half))
    return upper+lower[::-1]

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('kinetic_gold_reference.json').read_text('utf-8'))

def normalize(text):
    return ' '.join(''.join(c for c in w.casefold() if c.isalnum()) for w in text.split())

def recipe_for(words):
    if not words:return None
    from .template_patterns import source_text, source_slot
    recipes=profile()['recipes'];key=normalize(' '.join(words));original=normalize(source_text.get())
    saved=next((r for r in recipes if normalize(r['text'])==(original or key)),None)
    if saved is None:
        saved=recipes[source_slot.get()%len(recipes)] if source_slot.get()>=0 else min(recipes,key=lambda r:abs(len(r['text'].split())-len(words)))
    return dict(saved,adapted=normalize(saved['text'])!=key)

def motion(run,age):
    kind=run.get('motion','rise');p=max(0,min(1,age/run.get('duration',profile()['entrance_seconds'])));ease=1-(1-p)**3
    if kind=='cut':return 1,0,0,1
    if kind=='grow':return ease,0,0,.70+.30*ease
    if kind=='right':return 1,50*(1-ease),0,1
    if kind=='drop':return 1,0,run.get('rise',-32)*(1-ease),1
    return ease,0,run.get('rise',18)*(1-ease),1

@lru_cache(maxsize=8192)
def ink(text,face,size):
    from PIL import ImageFont
    from .renderer import _font_path
    font=ImageFont.truetype(str(_font_path(face)),max(2,round(size*10)))
    box=font.getbbox(text)
    return (box[2]-box[0])/10,(box[3]-box[1])/10

def bounds(runs):
    return (min(r['x']-r['width']/2 for r in runs),min(r['y']-r['height']/2 for r in runs),
            max(r['x']+r['width']/2 for r in runs),max(r['y']+r['height']/2 for r in runs))

def plan(words, measure, portrait=False, source_words=None,offset=0):
    """Lay out the complete page once; visibility never participates in fitting.

    Source row IDs and word slots replace the old proximity heuristic, which
    merged offset headers with main text and lost inline/echo patterns on edits.
    """
    if not words:return []
    recipe=recipe_for(source_words or words);old=recipe['text'].split();slots=recipe['runs']
    n=len(words);m=len(old)
    mapping=[min(m-1,math.floor((i+.5)*m/n)) for i in range(n)]
    mains=[i for i,r in enumerate(slots) if r['role']=='main']
    if mains and not any(j in mains for j in mapping):
        hero=mains[0];mapping[min(range(n),key=lambda i:abs(mapping[i]-hero))]=hero
    exact=normalize(' '.join(words))==normalize(recipe['text'])
    runs=[]
    for i,j in enumerate(mapping):
        r=dict(slots[j],text=words[i],index=i,source_index=j)
        if not exact:
            ow,oh=ink(old[j],r['font'],r['size']);nw,nh=ink(words[i],r['font'],r['size'])
            r['width']*=nw/max(1,ow);r['height']*=nh/max(1,oh)
        runs.append(r)
    if not exact:
        for row in sorted(set(r['row'] for r in runs)):
            band=[r for r in runs if r['row']==row]
            source=[r for r in slots if r['row']==row]
            box=bounds(source);center=(box[0]+box[2])/2
            source_ids=[j for j,r in enumerate(slots) if r['row']==row]
            source_gaps=[max(8,b['x']-b['width']/2-a['x']-a['width']/2) for a,b in zip(source,source[1:])]
            from statistics import median
            typical_gap=median(source_gaps) if source_gaps else 8
            gaps=[]
            for left,right in zip(band,band[1:]):
                # Keep the reference's split footer/header relationships, while
                # giving repeated/rebound slots a real visible-ink word space.
                a=slots[left['source_index']];b=slots[right['source_index']]
                gap=b['x']-b['width']/2-a['x']-a['width']/2
                skipped=source_ids.index(right['source_index'])-source_ids.index(left['source_index'])>1
                gaps.append(typical_gap if skipped else max(8,gap) if left['source_index']!=right['source_index'] else 8)
            span=sum(r['width'] for r in band)+sum(gaps);fit=min(1,650/max(1,span))
            cursor=center-span*fit/2
            for k,r in enumerate(band):
                r['size']*=fit;r['width']*=fit;r['height']*=fit
                r['x']=cursor+r['width']/2;cursor+=r['width']+(gaps[k]*fit if k<len(gaps) else 0)
        # Preserve staggered baselines. Only move a lower band enough to clear
        # actual horizontal collisions; short support rows never shrink a hero.
        done=[]
        for row in sorted(set(r['row'] for r in runs)):
            band=[r for r in runs if r['row']==row];dy=0
            for r in band:
                for previous in done:
                    if min(r['x']+r['width']/2,previous['x']+previous['width']/2)>max(r['x']-r['width']/2,previous['x']-previous['width']/2):
                        dy=max(dy,previous['y']+previous['height']/2+4-(r['y']-r['height']/2))
            for r in band:r['y']+=dy
            done.extend(band)
    # Balance the COMPLETE visible-ink group at the user's anchor. This shift
    # is identical before and after the next word becomes visible.
    left,top,right,bottom=bounds(runs)
    dx=368-(left+right)/2;dy=207-(top+bottom)/2
    for r in runs:r['x']+=dx;r['y']+=dy
    return runs

def pages(cue,width,height):
    from .core import CaptionCue
    limit=profile().get('max_page_words',9)
    result=[];a=0
    while a<len(cue.words):
        remaining=len(cue.words)-a;n=min(limit,remaining)
        if remaining>limit and remaining-limit==1:n-=1
        b=a+n
        result.append((a,CaptionCue(cue.words[a:b],cue.start if a==0 else cue.words[a].start,cue.words[b].start if b<len(cue.words) else cue.end,cue.template_source or cue.text,cue.template_slot)));a=b
    return result

def render(width,height,cue,seconds,font_id='template',position=.5,size=1,colors=None,visibility='phrase'):
    from PIL import Image,ImageDraw,ImageFont
    from .renderer import _font_path
    from .styles import font_file
    from .scene_capture import tag
    out=Image.new('RGBA',(width,height))
    active=next(((offset,page) for offset,page in pages(cue,width,height) if page.start<=seconds<page.end),None)
    if not active:return out
    offset,page=active;cfg=profile()
    def measure(text,file,size):return ImageFont.truetype(str(_font_path(file)),max(2,round(size*10))).getlength(text)/10
    from .template_patterns import pattern_context
    with pattern_context(cue):
        runs=plan([w.text for w in page.words],measure,height>=width,[w.text for w in cue.words],offset)
        recipe=recipe_for([w.text for w in cue.words])
    main=next((r for r in runs if r['role']=='main'),None)
    if recipe and recipe.get('adapted') and main:recipe=dict(recipe,hero=main['index']+offset)
    ratio=min(width/736,height/414)*size*(1.15 if height>=width else 1)
    if runs:
        extent=max(abs(r['x']-368)+r.get('width',measure(r['text'],r.get('font',cfg['main_font'] if r['role']=='main' else cfg['support_font']),r['size']))/2+(50 if r.get('motion')=='right' else 0) for r in runs)
        ratio=min(ratio,width*.90/max(1,extent*2*(1+cfg['camera_zoom'])))
    camera=1+cfg['camera_zoom']*min(1,max(0,(seconds-page.start)/max(.01,page.end-page.start)))
    for r in runs:
        if _decorations_only.get() and not r.get('echo'):continue
        i=r['index'];word=page.words[i];age=seconds-word.start-r.get('delay',0)
        if age<0 or (visibility=='styled_spoken' and seconds>=word.end):continue
        alpha,dx,dy,scale=motion(r,age)
        word_ratio=ratio
        if r.get('echo'):
            word_ratio,echo_scale,echo_dx,echo_dy,echo_alpha=echo_geometry(r,ratio,width,age)
        font_name=r.get('font',cfg['main_font'] if r['role']=='main' else cfg['support_font'])
        if font_id!='template':font_name=font_file(font_id,'kinetic_gold_draft')
        font=ImageFont.truetype(str(_font_path(font_name)),max(2,round(r['size']*word_ratio)))
        box=font.getbbox(r['text']);ink_width=box[2]-box[0];ink_height=box[3]-box[1]
        sx=r.get('width',ink_width/word_ratio)*word_ratio/max(1,ink_width)*scale;sy=r.get('height',ink_height/word_ratio)*word_ratio/max(1,ink_height)*scale
        x=width/2+(r['x']-368+dx)*ratio;y=height*position+(r['y']-207+dy)*ratio
        color=(colors or [])[offset+i] if offset+i<len(colors or []) else None;color=color or (cfg['accent'] if r['role']=='main' else '#FFFFFF')
        left=x-(box[0]+box[2])/2;top=y-(box[1]+box[3])/2
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        pen.text((left,top),r['text'],font=font,fill=color)
        if r.get('echo'):
            # An untagged transparent decoration stays separate from editable text.
            ex=sx/max(scale,.001)*echo_scale;ey=sy/max(scale,.001)*echo_scale
            echo_source=layer
            if r.get('echo_color'):
                echo_source=Image.new('RGBA',out.size)
                ImageDraw.Draw(echo_source).text((left,top),r['text'],font=font,fill=r['echo_color'])
            if r.get('outline_echo'):
                echo_source=Image.new('RGBA',out.size)
                ImageDraw.Draw(echo_source).text((left,top),r['text'],font=font,fill=(0,0,0,0),stroke_width=max(1,round(word_ratio*1.2)),stroke_fill=color)
            echo=echo_source.transform(out.size,Image.Transform.AFFINE,(1/ex,0,x-(x+echo_dx)/ex,0,1/ey,y-(y+echo_dy)/ey),resample=Image.Resampling.BICUBIC)
            echo.putalpha(echo.getchannel('A').point(lambda a:round(a*echo_alpha*r.get('echo_opacity',.18)/.18)))
            out.alpha_composite(echo)
            if _decorations_only.get():continue
        layer=tag(layer,offset+i,r['text'],font,left,top+font.getmetrics()[0],color=color)
        if r.get('typewriter'):
            reveal=min(1,age/r['typewriter']);clip=int(left+font.getlength(r['text'])*reveal)
            mask=layer.getchannel('A');ImageDraw.Draw(mask).rectangle((max(0,clip),0,width,height),fill=0);layer.putalpha(mask)
        layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
        layer=layer.transform(out.size,Image.Transform.AFFINE,(1/sx,0,x-x/sx,0,1/sy,y-y/sy),resample=Image.Resampling.BICUBIC)
        if not _decorations_only.get():out.alpha_composite(layer)
    if recipe and recipe.get('underline') and offset<=recipe['hero']<offset+len(page.words):
        points=stripe_points(seconds-cue.words[recipe['hero']].start,recipe.get('underline_path'))
        if points:
            if runs:
                left,top,right,bottom=bounds(runs);old_left,old_top,old_right,old_bottom=bounds(recipe['runs'])
                sx=(right-left)/max(1,old_right-old_left);sy=(bottom-top)/max(1,old_bottom-old_top)
                points=[((left+right)/2+(x-(old_left+old_right)/2)*sx,bottom+(y-old_bottom)*sy) for x,y in points]
            xy=[(width/2+(x-368)*ratio,height*position+(y-207)*ratio) for x,y in points]
            ImageDraw.Draw(out).polygon(xy,fill=recipe['underline'])
    return out.transform(out.size,Image.Transform.AFFINE,(1/camera,0,width/2-width/2/camera,0,1/camera,height*position-height*position/camera),resample=Image.Resampling.BICUBIC)

def sample_cues():
    from .core import CaptionCue,CaptionWord
    return [CaptionCue(tuple(CaptionWord(text,start,next((t for t in r['starts'][i+1:] if t>start),r['end'])) for i,(text,start) in enumerate(zip(r['text'].split(),r['starts']))),r['starts'][0],r['end']) for r in profile()['sample_groups']]
