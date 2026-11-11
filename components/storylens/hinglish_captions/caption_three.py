"""Caption 3: owner-selected serif reference with fixed slots and focus motion.

The Inter helpers remain unchanged because Caption 5 imports them too.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
import json
from .template_patterns import patterned

LAYOUT_REVISION = 5
_decorations_only = ContextVar('caption_three_decorations_only', default=False)

@contextmanager
def decorations_only():
    token = _decorations_only.set(True)
    try: yield
    finally: _decorations_only.reset(token)

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('caption_three_reference.json').read_text('utf8'))

@lru_cache(maxsize=1)
def font_css():
    """Upgrade old saved reports with these exact faces, without OS fallback."""
    import base64
    rules=[]
    for key,weight in [('support_font',400),('main_font',700),('playful_font',400)]:
        path=Path(__file__).with_name('fonts')/profile()[key]
        data=base64.b64encode(path.read_bytes()).decode('ascii')
        family='Caption Three Playful' if key=='playful_font' else 'Caption Three Serif'
        rules.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};font-display:block;src:url(data:font/ttf;base64,{data}) format('truetype')}}")
    return '\n'.join(rules)

def normalize(text):
    return ''.join(c for c in text.casefold() if c.isalnum())

def phrase_key(text):
    return ' '.join(map(normalize,text.split()))

def composition(words):
    from .template_patterns import transfer, rebound, source_text
    if not words: return {'rows': [], 'motion': 'in'}
    cfg = profile(); key = ' '.join(map(normalize, words))
    recipes=cfg['recipes']+cfg.get('continuations',[])
    known = next((r for r in recipes if key == phrase_key(r['text'])), None)
    if rebound(words): known = None
    saved=next((r for r in recipes if phrase_key(r['text'])==phrase_key(source_text.get())),None)
    return known or transfer(words, [saved] if saved else cfg['recipes'])

def smooth(value):
    p=max(0.,min(1.,value)); return p*p*p*(p*(p*6-15)+10)

def motion_state(age,remaining,available=1.,main=False,exit_seconds=.12):
    cfg=profile()['motion']; duration=min(cfg['focus_seconds'],max(.06,available*.60))
    p=smooth(age/duration);fade=smooth(age/min(cfg['fade_seconds'],max(.045,available*.28)));leave=smooth(remaining/max(.015,exit_seconds))
    return fade*leave,cfg['blur']*(1-p)+cfg['exit_blur']*(1-leave),(cfg['main_rise'] if main else cfg['support_rise'])*(1-p)

def camera_state(age,mode='in'):
    cfg=profile()['motion'];p=smooth(age/cfg['camera_seconds'])
    return 1+cfg['camera_zoom']*(p if mode=='in' else 1-p),cfg['camera_drift']*p

def transition_state(remaining,mode='focus'):
    p=smooth(1-remaining/profile()['motion']['transition_seconds'])
    return (-500*p if mode=='slide_left' else 0),(-380*p if mode=='slide_up' else 0)

def font_spec(row,font_id='template'):
    from .renderer import _font_path
    from .styles import font_file
    kind=row.get('font_override',row.get('font','support'))
    return _font_path(profile()[kind+'_font'] if font_id=='template' else font_file(font_id,'caption_3'))

@lru_cache(maxsize=128)
def font(path,size,weight=900):
    from PIL import ImageFont
    selected=ImageFont.truetype(str(path),max(2,round(size)))
    if Path(path).name=='Inter-Variable.ttf':selected.set_variation_by_name({400:'Regular',700:'Bold',900:'Black'}[weight])
    return selected


@lru_cache(maxsize=1024)
def metrics(path,size,weight,text,tracking):
    selected=font(path,size,weight);ascent=selected.getmetrics()[0]
    boxes=[]
    for j,c in enumerate(text):
        if c.isspace():continue
        b=selected.getbbox(c);offset=selected.getlength(text[:j])+j*selected.size*tracking
        boxes.append((b[0]+offset,b[1]-ascent,b[2]+offset,b[3]-ascent))
    return (selected.getlength(text)+max(0,len(text)-1)*selected.size*tracking,
            min((b[0] for b in boxes),default=0),max((b[2] for b in boxes),default=0),
            min((b[1] for b in boxes),default=0),max((b[3] for b in boxes),default=0))




def layout(words,width,height,font_id='template'):
    from .template_patterns import source_text,source_slot
    return _layout(tuple(words),width,height,font_id,source_text.get(),source_slot.get())

@lru_cache(maxsize=512)
def ink_outline(runs):
    from PIL import Image,ImageDraw
    import numpy as np
    left=min(x+metrics(path,size,weight,text,tracking)[1] for path,size,weight,text,tracking,x in runs)
    right=max(x+metrics(path,size,weight,text,tracking)[2] for path,size,weight,text,tracking,x in runs)
    extent=max(size for _,size,_,_,_,_ in runs)*2
    mask=Image.new('L',(max(1,int(right-left+8)),extent*2));pen=ImageDraw.Draw(mask)
    for path,size,weight,text,tracking,x in runs:
        f=font(path,size,weight)
        for j,c in enumerate(text):pen.text((x-left+3+f.getlength(text[:j])+j*size*tracking,extent-f.getmetrics()[0]),c,font=f,fill=255)
    pixels=np.asarray(mask)>48;used=pixels.any(axis=0)
    return left-3,np.where(used,pixels.argmax(axis=0)-extent,np.inf),np.where(used,len(pixels)-1-pixels[::-1].argmax(axis=0)-extent,-np.inf)

def baseline_distance(above,below,gap):
    import numpy as np
    def outline(line):return ink_outline(tuple((r['path'],r['size'],r['weight'],r['text'],r['tracking'],r['x']) for r in line['runs']))
    ao,_,bottom=outline(above);bo,top,_=outline(below)
    shift=below['x']+bo-above['x']-ao;indices=np.arange(len(top));mapped=np.floor(indices+shift+.5).astype(int);valid=(mapped>=0)&(mapped<len(bottom))
    distances=bottom[mapped[valid]]-top[valid];finite=distances[np.isfinite(distances)]
    optical=float(finite.max()) if len(finite) else above['bottom']-below['top']
    # Keep a header above the main letter body, even under a slanted capital.
    cap=above['bottom']-below['top']-max(r['size'] for r in below['runs'])*.18
    return max(optical,cap)+gap

@lru_cache(maxsize=512)
def _layout(words,width,height,font_id,pattern_source,pattern_slot):
    cfg=profile();plan=composition(words);unit=min(width,height*.75);ratio=unit/720
    # Fit complete rows, including camera magnification, then remeasure at the
    # fitted font size. Never scale metrics without remeasuring the glyphs.
    limit=unit*cfg['safe_width']/(1+cfg['motion']['camera_zoom']);lines=[]
    for row in plan['rows']:
        path=str(font_spec(row,font_id));weight=row.get('weight',400)
        tracking=cfg['tracking'] if row.get('font')=='main' else cfg['support_tracking']
        def measure(size):
            runs=[];cursor=0.
            for i in row['words']:
                text=words[i]
                advance,left,right,top,bottom=metrics(path,size,weight,text,tracking)
                runs.append(dict(i=i,text=text,path=path,size=size,weight=weight,tracking=tracking,x=cursor,left=left,right=right,top=top,bottom=bottom))
                cursor+=advance+size*cfg['space']
            left=min(r['x']+r['left'] for r in runs);right=max(r['x']+r['right'] for r in runs)
            return runs,left,right-left
        size=max(2,round(row['size']*ratio));runs,left,ink_width=measure(size)
        while ink_width>limit and size>2:
            size=max(2,min(size-1,int(size*limit/ink_width)));runs,left,ink_width=measure(size)
        room=max(0.,(limit-ink_width)/2);offset=max(-room,min(room,row.get('offset',0)*ratio))
        lines.append(dict(row=row,runs=runs,left=left,width=ink_width,top=min(r['top'] for r in runs),bottom=max(r['bottom'] for r in runs),x=offset-ink_width/2-left))
    cursor=0.
    for n,line in enumerate(lines):
        if not n:line['y']=-line['top']
        elif line['row'].get('gap_before'):
            line['y']=lines[n-1]['y']+lines[n-1]['bottom']+max(cfg['readable_line_gap'],line['row']['gap_before'])*ratio-line['top']
        else:line['y']=lines[n-1]['y']+baseline_distance(lines[n-1],line,cfg['readable_line_gap']*ratio)
        cursor=max(cursor,line['y']+line['bottom'])
    left=min((l['x']+l['left'] for l in lines),default=0);right=max((l['x']+l['left']+l['width'] for l in lines),default=0)
    H=max(round(unit*1.3),round(cursor+unit*.24))
    for line in lines:
        line['x']+=width/2-(left+right)/2;line['y']+=(H-cursor)/2
    return plan,lines,ratio,H

@lru_cache(maxsize=256)
@patterned
def paginate_cue(cue,font_id='template'):
    from .core import CaptionCue
    if not cue.words:return ()
    cfg=profile();origin=phrase_key(cue.template_source or cue.text)
    spread=next((s for s in cfg.get('legacy_spreads',[]) if origin==phrase_key(s['text'])),None)
    if spread is None and not any(origin==phrase_key(r['text']) for r in cfg['recipes']+cfg.get('continuations',[])):
        selected=composition([w.text for w in cue.words])
        spread=next((s for s in cfg.get('legacy_spreads',[]) if selected.get('template_pattern')==s['page_sources'][0]),None)
    if spread:
        # Migrate the old four-row cue at its semantic boundary. Each returned
        # page freezes its own source design, so saving/reopening or editing
        # the wording cannot turn the blue page into the handwritten page.
        n=len(cue.words);weights=spread['page_word_weights']
        split=max(1,min(n-1,int(n*weights[0]/sum(weights)+.5))) if n>1 else n
        groups=[cue.words[:split],cue.words[split:]];pages=[]
        for index,group in enumerate(groups):
            if not group:continue
            page=CaptionCue(group,cue.start if index==0 else group[0].start,
                            groups[1][0].start if index==0 and groups[1] else cue.end,
                            spread['page_sources'][index],cue.template_slot)
            pages.extend(paginate_cue(page,font_id))
        return tuple(pages)
    plan=composition([w.text for w in cue.words]);maximum=len(cue.words) if not plan.get('adapted') else plan.get('page_words',cfg['max_words'])
    groups=[];remaining=cue.words
    while remaining:
        count=min(maximum,len(remaining))
        if len(remaining)-count==1 and count>2:count-=1
        groups.append(remaining[:count]);remaining=remaining[count:]
    return tuple(CaptionCue(g,cue.start if i==0 else g[0].start,groups[i+1][0].start if i+1<len(groups) else cue.end,cue.template_source or cue.text,cue.template_slot) for i,g in enumerate(groups))

def paginate_cues(cues,font_id='template'):
    return [page for cue in cues for page in paginate_cue(cue,font_id)]

@lru_cache(maxsize=256)
def text_asset(width,height,path,size,weight,text,tracking,x,baseline,color):
    from PIL import Image,ImageDraw
    from .renderer import _color
    selected=font(path,size,weight);mask=Image.new('L',(width,height));pen=ImageDraw.Draw(mask)
    for j,char in enumerate(text):pen.text((x+selected.getlength(text[:j])+j*size*tracking,baseline-selected.getmetrics()[0]),char,font=selected,fill=255)
    layer=Image.new('RGBA',(width,height),_color(color));layer.putalpha(mask);return layer

def arrow_points():
    points=[]
    for a,b,c,d in [((0,0),(10,35),(31,39),(28,12)),((28,12),(24,-11),(-27,0),(-12,19)),((-12,19),(9,36),(49,11),(21,52)),((21,52),(13,62),(4,69),(-4,76))]:
        for i in range(40):
            t=i/40;u=1-t
            points.append((u*u*u*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t*t*t*d[0],u*u*u*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t*t*t*d[1]))
    return points+[(-4,76),(2,59),(-4,76),(13,70)]

def render(width,height,cue,seconds,font_id='template',position=.65,word_colors=None,visibility='phrase'):
    from PIL import Image,ImageDraw,ImageFilter
    from .renderer import _safe_word_colors
    from .template_patterns import pattern_context
    result=Image.new('RGBA',(width,height))
    if not cue.words or not cue.start<=seconds<cue.end:return result
    pages=paginate_cue(cue,font_id);index=next(i for i,p in enumerate(pages) if p.start<=seconds<p.end)
    offset=sum(len(p.words) for p in pages[:index]);cue=pages[index]
    if word_colors is not None:word_colors=word_colors[offset:offset+len(cue.words)]
    with pattern_context(cue):plan,lines,ratio,H=layout([w.text for w in cue.words],width,height,font_id)
    cfg=profile();colors=_safe_word_colors(cue,word_colors);region=Image.new('RGBA',(width,H))
    exit_seconds=min(cfg['motion']['exit_seconds'],max(.015,(cue.end-cue.words[-1].start)*.25))
    for line in lines:
        row=line['row'];first=cue.words[row['words'][0]].start
        # All words share the row's entrance clock; revealing another word
        # never changes a previous word's layout or restarts its movement.
        _,_,dy=motion_state(seconds-first,cue.end-seconds,cue.end-first,row['role'] in ('main','accent'),exit_seconds)
        for run in line['runs']:
            i=run['i'];word=cue.words[i]
            if seconds<word.start or visibility=='styled_spoken' and seconds>=word.end:continue
            alpha,blur,_=motion_state(seconds-word.start,cue.end-seconds,cue.end-word.start,row['role'] in ('main','accent'),exit_seconds)
            x=line['x']+run['x'];baseline=line['y'];color=colors[i] or cfg.get(row.get('tone_override',row.get('tone','ink')),cfg['ink'])
            if not _decorations_only.get():
                layer=text_asset(width,H,run['path'],run['size'],run['weight'],run['text'],run['tracking'],x,baseline,color)
                from .scene_capture import tag
                layer=tag(layer,offset+i,run['text'],font(run['path'],run['size'],run['weight']),x,baseline,run['tracking'],color,weight=run['weight'])
                if dy:layer=layer.transform(region.size,Image.Transform.AFFINE,(1,0,0,0,1,-dy*ratio),resample=Image.Resampling.BICUBIC)
                if blur>.08:layer=layer.filter(ImageFilter.GaussianBlur(blur*ratio))
                if alpha<1:
                    layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
                region.alpha_composite(layer)
        if plan.get('dash') and row['role']=='main' and seconds>=first:
            opacity,_,_=motion_state(seconds-first,cue.end-seconds,cue.end-first,True,exit_seconds)
            x=line['x']+line['left']+line['width']+12*ratio;y=line['y']+(line['top']+line['bottom'])/2+dy*ratio
            ImageDraw.Draw(region).line((x,y,x+42*ratio,y),fill=(36,36,34,round(255*opacity)),width=max(1,round(2*ratio)))
    if plan.get('arrow') and len(lines)>1:
        last=lines[-1];trigger=cue.words[last['runs'][0]['i']].start-.24;progress=smooth((seconds-trigger)/.65)
        points=arrow_points();count=min(len(points),int(progress*len(points)))
        if count>1:
            y=max(last['y']+last['top']-78*ratio,lines[-2]['y']+lines[-2]['bottom']+10*ratio)
            opacity=smooth((cue.end-seconds)/exit_seconds)
            ImageDraw.Draw(region).line([(width/2+x*ratio,y+v*ratio) for x,v in points[:count]],fill=(36,36,34,round(255*opacity)),width=max(1,round(1.6*ratio)))
    scale,drift=camera_state(seconds-cue.start,plan.get('motion','in'));dx,dy=transition_state(cue.end-seconds,plan.get('transition','focus'))
    ax=width/2;ay=H/2
    region=region.transform(region.size,Image.Transform.AFFINE,(1/scale,0,ax-ax/scale-dx*ratio/scale,0,1/scale,ay-ay/scale-(drift+dy)*ratio/scale),resample=Image.Resampling.BICUBIC)
    result.alpha_composite(region,(0,round(height*position-H/2)));return result

def reference_cues():
    from .core import CaptionCue,CaptionWord
    cues=[]
    recipes=[(slot,r) for slot,r in enumerate(profile()['recipes'])]
    recipes += [(r['source_slot'],r) for r in profile().get('continuations',[])]
    for slot,recipe in sorted(recipes,key=lambda item:item[1]['start']):
        texts=recipe['text'].split();starts=[recipe['start']/30]*len(texts)
        for row in recipe['rows']:
            for i in row['words']:starts[i]=row.get('frame',recipe['start'])/30
        words=tuple(CaptionWord(t,starts[i],next((s for s in starts[i+1:] if s>starts[i]),recipe['end']/30)) for i,t in enumerate(texts))
        cues.append(CaptionCue(words,recipe['start']/30,recipe['end']/30,recipe['text'],slot))
    return cues

def sample_cues():
    from .core import CaptionCue,CaptionWord
    cfg=profile();timing=json.loads(Path(__file__).with_name('caption_one_taj_words.json').read_text('utf8'))['words']
    words=[CaptionWord(w['text'],w['start'],w['end']) for w in timing];groups=[];cursor=0
    for recipe in cfg['demo_phrases']:
        count=len(recipe['text'].split());group=tuple(words[cursor:cursor+count]);cursor+=count
        if ' '.join(w.text for w in group)!=recipe['text']:raise ValueError('Caption 3 must keep the original narration')
        groups.append(group)
    if cursor!=len(words):raise ValueError('Caption 3 must keep every word')
    def origin(index):
        text=cfg['recipes'][index%len(cfg['recipes'])]['text']
        return next((s['text'] for s in cfg.get('legacy_spreads',[]) if s['page_sources'][0]==text),text)
    return [CaptionCue(g,g[0].start,groups[i+1][0].start if i+1<len(groups) else 30.,origin(i),i) for i,g in enumerate(groups)]

@lru_cache(maxsize=4)
def background_image(width,height):
    from PIL import Image
    return Image.new('RGB',(width,height),'#F5F5F3')
