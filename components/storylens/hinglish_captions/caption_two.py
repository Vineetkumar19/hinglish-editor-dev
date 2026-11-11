"""Caption 2: timed lime typography with a settling zoom on every slide."""
from functools import lru_cache
from .template_patterns import patterned
import json
import math
from pathlib import Path
from contextvars import ContextVar
from contextlib import contextmanager

from .caption_one import font as regular_font, glyph_mask, text_metrics

_decorations_only=ContextVar('caption_two_decorations_only',default=False)

@contextmanager
def decorations_only():
    token=_decorations_only.set(True)
    try:yield
    finally:_decorations_only.reset(token)


@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('caption_two_reference.json').read_text('utf-8'))


def normalize(text):
    return ''.join(c for c in text.casefold() if c.isalnum())


def _composition(words):
    key=' '.join(map(normalize,words))
    known=next((r for r in profile()['recipes']+profile()['demo_phrases']
                if key==' '.join(map(normalize,r['text'].split()))),None)
    from .template_patterns import rebound
    if rebound(words):known=None
    if known:return known
    if not words:return {'rows':[],'motion':'out'}
    if profile().get('reference_grouping'):
        from .template_patterns import transfer
        return transfer(words,profile()['recipes'])
    stops={'the','a','an','and','to','of','in','at','on','is','it','with','you','we','hai','ka','ki','ke','ko','se','aur'}
    hero=max(range(len(words)),key=lambda i:(len(normalize(words[i]))-(100 if normalize(words[i]) in stops else 0),-i))
    rows=[]
    if hero:rows.append({'words':list(range(hero)),'role':'support','align':'top_left'})
    rows.append({'words':[hero],'role':'main'})
    if hero+1<len(words):rows.append({'words':list(range(hero+1,len(words))),'role':'support','align':'bottom'})
    return {'rows':rows,'motion':'out'}


def composition(words):
    """Retain reference row roles while balancing the complete caption group."""
    plan = _composition(words)
    if profile().get('reference_style'):
        if not words:return dict(plan,rows=[],strike=False,record=False,plane=False)
        stops=set(profile()['keyword_stop_words'])
        eligible=[i for i,w in enumerate(words) if normalize(w) and normalize(w) not in stops]
        original=next((r for r in plan['rows'] if r['role']=='main'),{})
        rows=[dict(r,words=list(r['words']),green=[i for i in r.get('green',[]) if i in eligible]) for r in plan['rows']]
        if not eligible:
            rows=[{'words':list(range(len(words))),'role':'support','align':'center'}]
        elif not any(i in eligible for i in original.get('words',[])):
            # Stay near the reference emphasis slot. Picking the longest word
            # anywhere could move the hero to an edge and erase the design.
            anchors=original.get('words') or [len(words)//2]
            hero=min(eligible,key=lambda i:(min(abs(i-j) for j in anchors),-i))
            pivot=next((i for i,r in enumerate(rows) if r['role']=='main'),0)
            before=[r for r in rows[:pivot] if r['role']!='main']
            after=[r for r in rows[pivot+1:] if r['role']!='main']
            def rebind_support(ids,prototypes,align):
                if not ids:return []
                prototypes=prototypes or [{'role':'support','align':align,'words':[0]}]
                weights=[max(1,len(r['words'])) for r in prototypes];total=sum(weights)
                assigned=[[] for _ in prototypes]
                for k,i in enumerate(ids):
                    target=(k+.5)*total/len(ids);edge=0
                    for j,weight in enumerate(weights):
                        edge+=weight
                        if target<edge:
                            assigned[j].append(i);break
                return [dict(row,words=group,green=[i for i in row.get('green',[]) if i in group and i in eligible])
                        for row,group in zip(prototypes,assigned) if group]
            rows=[]
            rows.extend(rebind_support(list(range(hero)),before,'top_left'))
            rows.append(dict(original,role='main',words=[hero],green=[]))
            rows.extend(rebind_support(list(range(hero+1,len(words))),after,'bottom'))
        for row in rows:
            if row['role']=='card':row.update(role='support',align='bottom')
        return dict(plan,rows=rows,centered=True,reference_layout=False,balanced_reference=True,strike=False,record=False,plane=False)
    if profile().get('centered_rows'):
        if not words:return plan
        stops=set(profile()['keyword_stop_words'])
        eligible=[i for i,w in enumerate(words) if normalize(w) and normalize(w) not in stops]
        preferred=[i for row in plan['rows'] if row['role']=='main' for i in row['words'] if i in eligible]
        hero=max(preferred or eligible,key=lambda i:(len(normalize(words[i])),-i)) if eligible else None
        rows=[]
        if hero is None:
            rows=[{'words':list(range(len(words))),'role':'support','align':'center'}]
        else:
            if hero:rows.append({'words':list(range(hero)),'role':'support','align':'center'})
            rows.append({'words':[hero],'role':'main','align':'center'})
            if hero+1<len(words):rows.append({'words':list(range(hero+1,len(words))),'role':'support','align':'center'})
        return dict(plan,rows=rows,centered=True,reference_layout=False,strike=False,record=False,plane=False,
                    main_size=profile()['main_size'],support_size=profile()['support_size'],tracking=profile()['tracking'])
    if profile().get('reference_grouping'):return plan
    if not words:return plan
    original=next(row for row in plan['rows'] if row['role']=='main')
    candidates=original['words']
    stops={'the','a','an','and','to','of','in','at','on','is','it','with','you','we','hai','ka','ki','ke','ko','se','aur'}
    eligible=list(range(2,len(words))) if len(words)>=3 else list(range(len(words)))
    hero=candidates[0] if len(candidates)==1 and candidates[0] in eligible else max(eligible,key=lambda i:(len(normalize(words[i]))-(100 if normalize(words[i]) in stops else 0),-i))
    header=next((r for r in plan['rows'] if r['role']=='support' and r.get('align')!='bottom'),{})
    footer=next((r for r in plan['rows'] if r.get('align')=='bottom'),{})
    rows=[]
    if hero:rows.append(dict(header,words=list(range(hero)),role='support',align='top_left'))
    rows.append(dict(original,words=[hero]))
    if hero+1<len(words):rows.append(dict(footer,words=list(range(hero+1,len(words))),role='support',align='bottom'))
    return dict(plan, rows=rows)


def reference_lines(plan,make_runs,safe_width,unit,ratio,width,H,cfg):
    """Lay out full text once; preserve stagger without collisions or reflow."""
    entries=[]
    for row in plan['rows']:
        size=row.get('size',plan.get('main_size',cfg['main_size']) if row['role']=='main' else plan.get('support_size',cfg['support_size']))
        runs,w,ink=make_runs(row,size)
        if w>safe_width:
            size*=safe_width/w;runs,w,ink=make_runs(row,size)
        entries.append(dict(row=row,size=size,runs=runs,width=w,ink=ink,extents=ink_extents(runs),x=-w/2-ink,y=0))
    main=next((e for e in entries if e['row']['role']=='main'),None)
    gap=cfg.get('visible_ink_gap',(cfg['line_gap']+max(k[1] for k in cfg['motion']['word_y'])-min(k[1] for k in cfg['motion']['word_y'])+2)*cfg.get('centered_gap_scale',.3))*ratio
    upper=[e for e in entries if e is not main and e['row'].get('align')!='bottom']
    lower=[e for e in entries if e['row'].get('align')=='bottom']
    if main is not None:
        if len(upper)==2:
            a,b=upper
            header_gap=max(gap,cfg.get('split_header_gap',20)*ratio)
            fit=min(1,max(1,safe_width-header_gap)/max(1,a['width']+b['width']))
            if fit<1:
                for e in upper:
                    e['size']*=fit;runs,w,ink=make_runs(e['row'],e['size']);e.update(runs=runs,width=w,ink=ink,extents=ink_extents(runs))
            span=min(safe_width,max(main['width']*(1-plan.get('header_fraction',.16)-plan.get('right_fraction',0)),a['width']+b['width']+header_gap))
            center=(plan.get('header_fraction',.16)-plan.get('right_fraction',0))*main['width']/2
            room=max(0,(safe_width-span)/2);center=max(-room,min(room,center))
            a['x']=center-span/2-a['ink'];b['x']=center+span/2-b['width']-b['ink']
        else:
            for e in upper:
                align=e['row'].get('align')
                center=0 if align=='center' else (main['width']-e['width'])/2-main['width']*plan.get('right_fraction',0) if align=='top_right' else (e['width']-main['width'])/2+main['width']*plan.get('header_fraction',.16)
                room=max(0,(safe_width-e['width'])/2);center=max(-room,min(room,center));e['x']=center-e['width']/2-e['ink']
        if upper:
            y=main['extents'][0]-gap-max(e['extents'][1] for e in upper)
            for e in upper:e['y']=y
        bottom=main['extents'][1]
        for e in lower:
            center=(main['width']-e['width'])/2+e['row'].get('dx',0)*ratio
            room=max(0,(safe_width-e['width'])/2);center=max(-room,min(room,center))
            e['x']=center-e['width']/2-e['ink'];e['y']=bottom+gap-e['extents'][0];bottom=e['y']+e['extents'][1]
    left=min((e['x']+e['ink'] for e in entries),default=0);right=max((e['x']+e['ink']+e['width'] for e in entries),default=0)
    top=min((e['y']+e['extents'][0] for e in entries),default=0);bottom=max((e['y']+e['extents'][1] for e in entries),default=0)
    for e in entries:e['row']['_x']=e['x']+width/2-(left+right)/2
    return [(e['row'],e['runs'],e['extents'],e['y']+H/2-(top+bottom)/2) for e in entries]


def page_ranges(words):
    """Split at word boundaries without dropping, reordering or retiming words."""
    limit=profile().get('max_words_per_frame',7)
    if profile().get('reference_style'):
        # Balance the overflow instead of making a five-word page followed by
        # a stranded one-word page. Saved long cues use this same hard limit.
        limit=max(1,min(5,limit));count=math.ceil(len(words)/limit)
        if not count:return []
        size,extra=divmod(len(words),count);result=[];start=0
        for i in range(count):
            end=start+size+(i<extra);result.append((start,end));start=end
        return result
    if profile().get('reference_grouping') and len(words)<=7 and _composition(words).get('reference_layout'):
        return [(0,len(words))]
    if profile().get('reference_grouping'):
        return [(a,min(a+7,len(words))) for a in range(0,len(words),7)]
    result=[];start=0
    while start<len(words):
        remaining=words[start:]
        plan=composition(remaining)
        main=next(row for row in plan['rows'] if row['role']=='main')
        stop=main['words'][-1]+1
        long_main=any(len(normalize(remaining[i]))>8 for i in main['words'])
        count=min(7,len(remaining))
        # Break after the focus word, rather than leave a long footer or cut a
        # sentence at an arbitrary seventh word. Overflow starts a fresh frame.
        if (long_main or len(remaining)>7) and stop<=7:
            count=stop
        # Re-evaluate a shortened page: its focus word may differ from the
        # original recipe's focus (especially after the seven-word boundary).
        while True:
            candidate=remaining[:count]
            hero=next(row for row in composition(candidate)['rows'] if row['role']=='main')
            end=hero['words'][-1]+1
            if any(len(normalize(candidate[i]))>8 for i in hero['words']) and end<count:
                count=end
            else:break
        result.append((start,start+count));start+=count
    return result


@patterned
def paginate_cue(cue, font_id='template'):
    from .core import CaptionCue
    ranges=page_ranges([w.text for w in cue.words])
    return [CaptionCue(cue.words[a:b],cue.start if a==0 else cue.words[a].start,
                       cue.words[b].start if b<len(cue.words) else cue.end,cue.template_source or cue.text,cue.template_slot) for a,b in ranges]


def interpolate(keys,seconds,column=1):
    if seconds<=keys[0][0]:return keys[0][column]
    for a,b in zip(keys,keys[1:]):
        if seconds<=b[0]:
            p=(seconds-a[0])/(b[0]-a[0])
            return a[column]+(b[column]-a[column])*p
    return keys[-1][column]


def motion_state(elapsed,main=False,slide=False):
    cfg=profile()['motion']
    p=max(0.,min(1.,elapsed/cfg['text_seconds']))
    eased=1-(1-p)**3
    fade=max(0.,min(1.,elapsed/cfg['fade_seconds']))
    # Each word rises, passes its resting position slightly, then settles down.
    return (fade*fade*(3-2*fade),0.,
            smooth_track(cfg['word_y'],elapsed),cfg['blur']*(1-eased))


def smooth_track(keys,seconds):
    if seconds<=keys[0][0]:return keys[0][1]
    for a,b in zip(keys,keys[1:]):
        if seconds<=b[0]:
            p=(seconds-a[0])/(b[0]-a[0]);p=p*p*p*(p*(p*6-15)+10)
            return a[1]+(b[1]-a[1])*p
    return keys[-1][1]


def word_scale(elapsed):
    return smooth_track(profile()['motion']['word_scale'],elapsed)


def group_scale(plan,elapsed):
    if plan.get('camera_keys'):return interpolate(plan['camera_keys'],elapsed)
    mode=plan.get('motion','focus')
    return interpolate(profile()['motion']['scale_'+('out' if mode=='out' else 'in')],elapsed) if mode in ('out','in') else 1.


def ink_extents(runs):
    """Visible glyph extents relative to their shared baseline."""
    boxes=[r['font'].getbbox(c) for r in runs for c in r['text'] if not c.isspace()]
    ascents=[r['font'].getmetrics()[0] for r in runs for c in r['text'] if not c.isspace()]
    return (min((b[1]-a for b,a in zip(boxes,ascents)),default=0),
            max((b[3]-a for b,a in zip(boxes,ascents)),default=0))


def footer_baseline(baseline,main_extents,footer_extents,gap=None):
    top,bottom=main_extents
    # Measure both rows' visible ink so neither capitals nor descenders touch.
    bottom=min(0,bottom)
    return baseline+main_extents[1]-footer_extents[0]+(profile()['line_gap'] if gap is None else gap)


def sample_cues():
    from .core import CaptionCue,CaptionWord
    timing=json.loads(Path(__file__).with_name('caption_one_taj_words.json').read_text('utf-8'))
    words=[CaptionWord(w['text'],w['start'],w['end']) for w in timing['words']]
    groups=[];cursor=0
    for recipe in profile()['demo_phrases']:
        count=len(recipe['text'].split());group=tuple(words[cursor:cursor+count]);cursor+=count
        if ' '.join(w.text for w in group)!=recipe['text']:raise ValueError('Caption 2 sample and narration words differ')
        groups.append(group)
    if cursor!=len(words):raise ValueError('Caption 2 must keep every narration word')
    return [page for i,g in enumerate(groups) for page in paginate_cue(CaptionCue(g,g[0].start,groups[i+1][0].start if i+1<len(groups) else 30.))]


def reference_cues():
    """Native 30 fps on-screen reference events, including its intentional gaps."""
    from .core import CaptionCue,CaptionWord
    cues=[]
    for recipe in profile()['recipes']:
        starts=recipe['starts'];texts=recipe['text'].split();end=recipe['end']/30
        words=tuple(CaptionWord(texts[i],start/30,starts[i+1]/30 if i+1<len(starts) else end) for i,start in enumerate(starts))
        cues.append(CaptionCue(words,recipe['start']/30,end))
    return cues


@lru_cache(maxsize=64)
def card_font(path,size):
    from PIL import ImageFont
    chosen=ImageFont.truetype(str(path),max(2,round(size)))
    if Path(path).name=='Inter-Variable.ttf':chosen.set_variation_by_name('Light')
    return chosen


@lru_cache(maxsize=96)
def text_asset(width,height,path,size,text,tracking,x,baseline,color,glow=False,ink_enabled=True):
    from PIL import Image,ImageFilter,ImageChops
    from .renderer import _color
    mask=glyph_mask(width,height,path,size,text,tracking,x,baseline)
    result=Image.new('RGBA',(width,height))
    appearance=profile().get('appearance')
    if appearance:
        unit=size/104
        shade=ImageChops.offset(mask,0,round(appearance['shadow_y']*unit)).filter(ImageFilter.GaussianBlur(appearance['shadow_blur']*unit))
        shadow=Image.new('RGBA',result.size,'black');shadow.putalpha(shade.point(lambda v:round(v*appearance['shadow_opacity'])))
        result.alpha_composite(shadow)
        for radius,alpha in appearance['lime_glow' if glow else 'white_glow']:
            bloom=Image.new('RGBA',result.size,_color(color));bloom.putalpha(mask.filter(ImageFilter.GaussianBlur(radius*unit)).point(lambda v:round(v*alpha)))
            result.alpha_composite(bloom)
    elif glow:
        for radius,alpha in [(16,.12),(5,.16)]:
            bloom=Image.new('RGBA',result.size,_color(color))
            bloom.putalpha(mask.filter(ImageFilter.GaussianBlur(radius*width/720)).point(lambda v:round(v*alpha)))
            result.alpha_composite(bloom)
    if ink_enabled:
        ink=Image.new('RGBA',result.size,_color(color));ink.putalpha(mask)
        result.alpha_composite(ink)
    return result


@lru_cache(maxsize=16)
def card_background(width,height):
    from PIL import Image,ImageDraw
    import numpy as np
    y,x=np.mgrid[0:height,0:width]
    strength=np.exp(-(((x-width*.48)/(width*.42))**2+((y-height*1.03)/(height*.8))**2)*2)
    rgb=np.stack([14+strength*92,6+strength*0,11+strength*8],axis=2).astype('uint8')
    tile=Image.fromarray(rgb,'RGB').convert('RGBA')
    mask=Image.new('L',tile.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=height*.30,fill=242)
    tile.putalpha(mask)
    ImageDraw.Draw(tile).rounded_rectangle((0,0,width-1,height-1),radius=height*.30,outline=(121,105,99,150),width=1)
    return tile


def render(width,height,cue,seconds,font_id='template',position=732/1280,word_colors=None,visibility='phrase'):
    from PIL import Image,ImageDraw,ImageFilter
    from .renderer import _font_path,_safe_word_colors,_color
    from .styles import font_file
    output=Image.new('RGBA',(width,height))
    if not cue.words or not cue.start<=seconds<cue.end:return output
    cfg=profile();words=[w.text for w in cue.words];requested_position=position
    a,b=next(((a,b) for a,b in page_ranges(words) if (cue.start if a==0 else cue.words[a].start)<=seconds<(cue.words[b].start if b<len(words) else cue.end)),(0,0))
    if a==b:return output
    plan=composition(words[a:b])
    plan=dict(plan,rows=[dict(row,words=[i+a for i in row['words']],green=[i+a for i in row.get('green',[])]) for row in plan['rows']])
    colors=_safe_word_colors(cue,word_colors)
    unit=min(width,height*.75);ratio=unit/720;H=round(unit*1.25)
    region=Image.new('RGBA',(width,H));baseline=H/2+plan.get('main_offset',0)*ratio
    main_path=_font_path('Inter-Bold.otf' if font_id=='template' else font_file(font_id,'caption_2'))
    support_path=main_path
    light_path=_font_path('Inter-Variable.ttf' if font_id=='template' else font_file(font_id,'caption_2'))
    main_row=next((r for r in plan['rows'] if r['role']=='main'),None)
    # Measured reference cameras settle from the emphasis word's onset.
    main_onset=min(cue.words[i].start for i in main_row['words']) if main_row and plan.get('camera_anchor')=='main' else cue.words[a].start

    def shown(i):return cue.words[i].start<=seconds and (visibility!='styled_spoken' or seconds<cue.words[i].end)
    def make_runs(row,size,card=False):
        row_path=_font_path('StorylensInterCaption-Regular.ttf') if row.get('regular') and font_id=='template' else main_path
        selected=(card_font if card else regular_font)(light_path if card else row_path,max(2,round(size*ratio)))
        tracking=(-.045 if card else row.get('tracking',plan.get('tracking',cfg['tracking']) if row['role']=='main' else cfg['support_tracking']))
        runs=[];cursor=0
        for i in row['words']:
            text=words[i]
            if not plan.get('reference_layout') and row['role']=='main' and i==row['words'][0] and text:text=text[0].upper()+text[1:]
            advance,left,right=text_metrics(selected.path,selected.size,text,tracking) if not card else (selected.getlength(text)+(len(text)-1)*selected.size*tracking,0,selected.getlength(text)+(len(text)-1)*selected.size*tracking)
            runs.append(dict(i=i,text=text,font=selected,tracking=tracking,x=cursor,left=left,right=right,enter_y=row.get('enter_y')))
            cursor+=advance+selected.size*(.17 if row['role']=='main' else .21)
        left=min((r['x']+r['left'] for r in runs),default=0);right=max((r['x']+r['right'] for r in runs),default=0)
        return runs,right-left,left

    if plan.get('adapted') and not plan.get('centered'):
        widest=max((make_runs(row,row.get('size',plan.get('main_size',cfg['main_size']) if row['role']=='main' else plan.get('support_size',cfg['support_size'])))[1] for row in plan['rows']),default=1)
        camera_peak=max(1.,max(k[1] for k in cfg['motion']['scale_out']))
        ratio*=min(1,unit*.88/camera_peak/max(1,widest))
        baseline=H/2+plan.get('main_offset',0)*ratio
    main_size=plan.get('main_size',cfg['main_size'])
    main_runs,main_width,main_ink=([],0,0) if not main_row else make_runs(main_row,main_row.get('size',main_size))
    peak=max(1.,max(key[1] for key in cfg['motion']['scale_out']))
    safe_width=unit*cfg.get('settled_width_fraction',.88) if plan.get('balanced_reference') else unit*.98 if plan.get('reference_layout') else unit*.88/peak
    if main_row and main_width>safe_width:
        main_size=main_row.get('size',main_size)*safe_width/main_width
        main_runs,main_width,main_ink=make_runs(main_row,main_size)
    main_left=(width-main_width)/2
    main_extents=ink_extents(main_runs)
    centered_lines=[]
    if plan.get('balanced_reference'):
        centered_lines=reference_lines(plan,make_runs,safe_width,unit,ratio,width,H,cfg)
    elif plan.get('centered'):
        # One centered header/footer replaces the old colliding split headers.
        # Keep the owner's compact spacing while retaining the entrance motion.
        for row in plan['rows']:
            size=main_size if row['role']=='main' else cfg['support_size']
            runs,line_width,ink=make_runs(row,size)
            if line_width>safe_width:
                size*=safe_width/line_width
                runs,line_width,ink=make_runs(row,size)
            extents=ink_extents(runs)
            centered_lines.append((row,runs,extents))
        travel=max(k[1] for k in cfg['motion']['word_y'])-min(k[1] for k in cfg['motion']['word_y'])
        gap=(cfg['line_gap']+travel+2)*cfg.get('centered_gap_scale',.3)*ratio
        block_height=sum(ex[1]-ex[0] for _,_,ex in centered_lines)+gap*max(0,len(centered_lines)-1)
        top=H/2-block_height/2
        centered_lines=[(row,runs,ex,top+sum(old[2][1]-old[2][0]+gap for old in centered_lines[:i])-ex[0]) for i,(row,runs,ex) in enumerate(centered_lines)]

    def paint_word(run,x,y,color,main=False,card=False):
        i=run['i']
        if not shown(i):return
        alpha,dx,dy,blur=motion_state(seconds-cue.words[i].start,main,plan.get('motion')=='out')
        if run.get('enter_y') is not None:
            dy=smooth_track([[0,run['enter_y']],[cfg['motion']['text_seconds'],0]],seconds-cue.words[i].start)
        selected=run['font'];path=selected.path
        if card:
            # The light variable face keeps the warning-card typography thin.
            layer=Image.new('RGBA',region.size);pen=ImageDraw.Draw(layer)
            for j,c in enumerate(run['text']):
                pen.text((x+selected.getlength(run['text'][:j])+j*selected.size*run['tracking'],y-selected.getmetrics()[0]),c,font=selected,fill=_color(colors[i] or color))
        else:
            layer=text_asset(width,H,path,selected.size,run['text'],run['tracking'],x,y,colors[i] or color,main or color==cfg['green'],not _decorations_only.get())
        from .scene_capture import tag
        if not _decorations_only.get():layer=tag(layer,i,run['text'],selected,x,y,run['tracking'],colors[i] or color,weight=300 if card else None)
        scale=word_scale(seconds-cue.words[i].start)
        if abs(scale-1)>.0001:
            ax=x+(run['left']+run['right'])/2
            top,bottom=ink_extents([run]);ay=y+(top+bottom)/2
            layer=layer.transform(layer.size,Image.Transform.AFFINE,
                (1/scale,0,ax-ax/scale,0,1/scale,ay-ay/scale),resample=Image.Resampling.BICUBIC)
        if blur>.12:layer=layer.filter(ImageFilter.GaussianBlur(blur*ratio))
        if dx or dy:layer=layer.transform(layer.size,Image.Transform.AFFINE,(1,0,-dx*ratio,0,1,-dy*ratio),resample=Image.Resampling.BICUBIC)
        if alpha<1:
            layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
        region.alpha_composite(layer)

    card_index=0
    if plan.get('centered'):
        for row,runs,extents,y in centered_lines:
            visible=[r for r in runs if shown(r['i']) and motion_state(seconds-cue.words[r['i']].start)[0]>.01]
            if not visible:continue
            # Reserve the entire row before revealing words. Never recenter a
            # growing prefix: previously visible words must keep their slots.
            left=min(r['x']+r['left'] for r in runs);right=max(r['x']+r['right'] for r in runs)
            x=row.get('_x',width/2-(left+right)/2)
            for run in visible:
                content=bool(normalize(words[run['i']])) and normalize(words[run['i']]) not in cfg.get('keyword_stop_words',[])
                highlight=content and (row['role']=='main' or run['i'] in row.get('green',[]))
                paint_word(run,x+run['x'],y,cfg['green'] if highlight else cfg['white'],highlight)
    for row in plan['rows']:
        if plan.get('centered'):continue
        if row['role']=='card':
            onset=cue.words[row['words'][0]].start;elapsed=seconds-onset
            if elapsed<0:card_index+=1;continue
            bw,bh=round(448*ratio),round(82*ratio);x=(width-bw)/2
            center=baseline+(-7+card_index*116+interpolate(cfg['motion']['card_y'],elapsed))*ratio
            bg=card_background(bw,bh)
            if elapsed<.15:
                bg=bg.copy();bg.putalpha(bg.getchannel('A').point(lambda v:round(v*max(0,elapsed/.15))))
            region.alpha_composite(bg,(round(x),round(center-bh/2)))
            pen=ImageDraw.Draw(region);cx=x+50*ratio;cy=center
            if card_index==0:
                pen.polygon([(cx,cy-17*ratio),(cx-17*ratio,cy+14*ratio),(cx+17*ratio,cy+14*ratio)],fill=_color(cfg['red']))
                pen.line([(cx,cy-7*ratio),(cx,cy+3*ratio)],fill=(35,0,0,255),width=max(1,round(3*ratio)))
                pen.ellipse((cx-ratio,cy+8*ratio,cx+ratio,cy+10*ratio),fill=(35,0,0,255))
            else:
                from PIL import ImageFont
                emoji_font=ImageFont.truetype(str(_font_path('seguiemj.ttf')),max(2,round(36*ratio)))
                pen.text((cx,cy),'💸',font=emoji_font,anchor='mm',fill=(250,236,205,255),embedded_color=True)
            runs,line_width,ink=make_runs(row,36 if card_index==0 else 30,True)
            start=max(x+90*ratio,width/2-line_width/2)
            for run in runs:paint_word(run,start+run['x']-ink,center+12*ratio,cfg['white'],card=True)
            card_index+=1;continue
        main=row['role']=='main';size=row.get('size',main_size if main else plan.get('support_size',cfg['support_size']))
        runs,line_width,ink=(main_runs,main_width,main_ink) if main else make_runs(row,size)
        available=main_left+main_width-(width-safe_width)/2
        if not main and line_width>available:
            size*=available/line_width
            runs,line_width,ink=make_runs(row,size)
        align=row.get('align','main')
        if main:x=main_left-ink;y=baseline
        elif align=='top_left':
            x=main_left+main_width*plan.get('header_fraction',.16)-ink if plan.get('reference_layout') else main_left-ink
            y=baseline-plan.get('top_lift',70)*ratio if plan.get('reference_layout') else baseline+main_extents[0]-ink_extents(runs)[1]-cfg['line_gap']*ratio
        elif align=='top_right':
            x=main_left+main_width-line_width-ink-main_width*plan.get('right_fraction',0)
            y=baseline-plan.get('top_lift',70)*ratio if plan.get('reference_layout') else baseline+main_extents[0]-ink_extents(runs)[1]-cfg['line_gap']*ratio
        elif align=='bottom':x=main_left+main_width-line_width-ink;y=baseline+size*.85*ratio if plan.get('reference_layout') else footer_baseline(baseline,main_extents,ink_extents(runs),cfg['line_gap']*ratio)
        else:x=main_left+main_width*plan.get('header_fraction',.12)-ink;y=baseline-plan.get('top_lift',78 if size>=75 else 85 if size>=65 else 66 if size>=58 else 70)*ratio
        if not (main and plan.get('reference_layout')):x=max(width*.055,min(x,width*.945-line_width))
        x+=row.get('dx',0)*ratio
        if plan.get('adapted'):
            margin=(width-unit*.88/peak)/2
            x=max(margin-ink,min(x,width-margin-line_width-ink))
        for run in runs:
            color=cfg['green'] if main or run['i'] in row.get('green',[]) else cfg['white']
            paint_word(run,x+run['x'],y,color,main)

    elapsed=seconds-main_onset
    cursor_layer=Image.new('RGBA',region.size)
    cursor=cfg.get('cursor');event=next((start for start in cursor['times'] if start<=seconds<start+cursor['duration']),None) if cursor else None
    if not cfg.get('text_only') and ((event is not None) or (not cursor and plan.get('plane') and elapsed>=.12)):
        t=seconds-event if event is not None else elapsed-.12
        cursor_plan=cfg['recipes'][1] if cursor else plan
        anchor=H/2+(requested_position-position)*height if cursor else baseline
        keys=cfg['motion']['plane'];cx=(interpolate(keys,t,1)+cursor_plan.get('plane_dx',0))*ratio+(width-unit)/2;cy=anchor+(interpolate(keys,t,2)+cursor_plan.get('plane_dy',0))*ratio
        angle=math.radians(interpolate(keys,t,3)+cursor_plan.get('plane_angle',0));size=cursor_plan.get('plane_size',46)*ratio
        click=(t-cursor['click_at'])/cursor['click_seconds'] if cursor else -1
        if 0<=click<=1:size*=1-.12*math.sin(math.pi*click)
        points=[(-.55,.1),(.55,-.5),(.15,.65),(-.05,.15),(-.55,.1),(-.05,.15),(.55,-.5)]
        vertices=[(cx+(a*math.cos(angle)-b*math.sin(angle))*size,cy+(a*math.sin(angle)+b*math.cos(angle))*size) for a,b in points]
        icon=Image.new('RGBA',region.size);ip=ImageDraw.Draw(icon);ip.line(vertices,fill=_color(cfg['green']),width=max(1,round(4*ratio)),joint='curve')
        if cursor and 0<=t-cursor['click_at']<.38:
            pulse=(t-cursor['click_at'])/.38;r=(5+24*pulse)*ratio;tx,ty=vertices[1]
            ip.ellipse((tx-r,ty-r,tx+r,ty+r),outline=_color(cfg['green'],round(180*(1-pulse))),width=max(1,round(2*ratio)))
        if cursor:
            alpha=max(0,min(1,(cursor['duration']-t)/(cursor['duration']-cursor['fade_at'])))
            icon.putalpha(icon.getchannel('A').point(lambda value:round(value*alpha)))
        cursor_layer.alpha_composite(icon.filter(ImageFilter.GaussianBlur(8*ratio)));cursor_layer.alpha_composite(icon)
    if not cfg.get('text_only') and plan.get('strike') and elapsed>.17:
        p=min(1,(elapsed-.17)/.55);x0=main_left-10*ratio;y0=baseline-90*ratio;x1=main_left+main_width*p;y1=y0+76*ratio*p
        if cfg.get('appearance'):
            dx=main_width+20*ratio;dy=main_size*.8*ratio;length=math.hypot(dx,dy);left=[];right=[]
            for k in range(61):
                t=p*k/60;x=x0+dx*t;y=y0+dy*t;half=7*ratio*math.sin(math.pi*t)**.65
                left.append((x-dy/length*half,y+dx/length*half));right.append((x+dy/length*half,y-dx/length*half))
            ImageDraw.Draw(region).polygon(left+right[::-1],fill=_color(cfg['red']))
        else:ImageDraw.Draw(region).line([(x0,y0),(x1,y1)],fill=_color(cfg['red']),width=max(1,round(6*ratio)))
    if not cfg.get('text_only') and plan.get('record') and elapsed>.5:
        x=main_left+main_width+16*ratio;y=baseline-67*ratio
        ImageDraw.Draw(region).ellipse((x-5*ratio,y-5*ratio,x+5*ratio,y+5*ratio),fill=_color(cfg['red']))
    scale=group_scale(plan,elapsed)
    if plan.get('balanced_reference') and centered_lines:
        left=min(row['_x']+r['x']+r['left'] for row,runs,_,_ in centered_lines for r in runs)
        right=max(row['_x']+r['x']+r['right'] for row,runs,_,_ in centered_lines for r in runs)
        scale=min(scale,unit*cfg.get('camera_width_fraction',.94)/max(1,right-left))
    if abs(scale-1)>.0001:
        ax=width/2;ay=H/2 if plan.get('centered') else baseline-32*ratio
        region=region.transform(region.size,Image.Transform.AFFINE,(1/scale,0,ax-ax/scale,0,1/scale,ay-ay/scale),resample=Image.Resampling.BICUBIC)
    region.alpha_composite(cursor_layer)
    output.alpha_composite(region,(0,round(height*position-H/2)))
    return output
