"""Caption 4: italic editorial type and continuous soft-focus camera motion."""
from functools import lru_cache
from .template_patterns import patterned
import json
from pathlib import Path

from .caption_one import font, glyph_mask, text_metrics

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('caption_four_reference.json').read_text('utf8'))


def normalize(text):
    return ''.join(c for c in text.casefold() if c.isalnum())


def composition(words):
    cfg=profile();key=' '.join(map(normalize,words))
    known=next((r for r in cfg['demo_phrases']+cfg['recipes'] if key==' '.join(map(normalize,r['text'].split()))),None)
    from .template_patterns import rebound
    if rebound(words):known=None
    if not words:return {'rows':[], 'motion':'in'}
    if known is None:
        from .template_patterns import transfer
        known=transfer(words,cfg['recipes'])
    fields=('header_alignment','footer_alignment','header_inset','footer_outset','footer_bold','footer_size','main_size','main_words')
    design={k:known[k] for k in fields if known and k in known}
    stops=set(cfg['stop_words'])|set('your our their his her my its this that these those i me us them be been being am are was were have has had will would can could should do does did for from by as if then now hai hain ho tha thi'.split())
    eligible=[i for i,w in enumerate(words) if normalize(w) and normalize(w) not in stops]
    preferred=known.get('hero') if known else None
    hero=preferred if preferred in eligible else max(eligible,key=lambda i:(len(normalize(words[i])),-i)) if eligible else None
    if hero is None:return {'rows':[{'role':'header','words':list(range(len(words)))}],'motion':known.get('motion','in') if known else 'in','adapted':bool(known and known.get('adapted')),'design':design}
    count=max(1,min(design.get('main_words',1),len(words)-hero))
    while count>1 and any(i not in eligible for i in range(hero,hero+count)):count-=1
    rows=[]
    if hero:rows.append({'role':'header','words':list(range(hero))})
    rows.append({'role':'main','words':list(range(hero,hero+count))})
    footer=list(range(hero+count,len(words)))
    if footer:rows.append({'role':'footer','words':footer})
    return {'rows':rows,'motion':known.get('motion','in') if known else 'in','adapted':bool(known and known.get('adapted')),'design':design}


def smooth(value):
    p=max(0.,min(1.,value));return p*p*p*(p*(p*6-15)+10)


def motion_state(age,remaining,available,main=False,exit_seconds=.1):
    cfg=profile()['motion'];duration=min(cfg['focus_seconds'],max(.06,available*.60))
    p=smooth(age/duration);fade=smooth(age/min(cfg['fade_seconds'],max(.045,available*.28)))
    leave=smooth(remaining/max(.015,exit_seconds))
    return fade*leave,cfg['blur']*(1-p)+cfg['exit_blur']*(1-leave),(cfg['main_rise'] if main else cfg['support_rise'])*(1-p),1-(.10 if main else .025)*(1-p)


def camera_state(age,mode='in'):
    cfg=profile()['motion'];p=smooth(age/cfg['camera_seconds'])
    return (1+cfg['camera_zoom']*p if mode=='in' else 1+cfg['camera_zoom']*(1-p),cfg['camera_drift']*p)


@lru_cache(maxsize=512)
def ink_profile(runs):
    """Column silhouettes, relative to the baseline, for optical line spacing."""
    from PIL import Image
    import numpy as np
    left=min((x+text_metrics(path,size,text,tracking)[1] for path,size,text,tracking,x in runs),default=0)
    right=max((x+text_metrics(path,size,text,tracking)[2] for path,size,text,tracking,x in runs),default=0)
    extent=max((size for path,size,text,tracking,x in runs),default=2)*2
    width=max(1,int(right-left+8));height=max(1,extent*2);baseline=extent
    mask=Image.new('L',(width,height))
    for path,size,text,tracking,x in runs:
        from PIL import ImageChops
        mask=ImageChops.lighter(mask,glyph_mask(width,height,path,size,text,tracking,x-left+3,baseline))
    pixels=np.asarray(mask)>48
    columns=pixels.any(axis=0)
    top=np.where(columns,pixels.argmax(axis=0)-baseline,np.inf)
    bottom=np.where(columns,height-1-pixels[::-1].argmax(axis=0)-baseline,-np.inf)
    return left-3,top,bottom


def optical_baseline(main,line,gap,above=False):
    """Bring adjacent ink close without letting italic tails touch the next row."""
    import numpy as np
    def outline(item):
        return ink_profile(tuple((str(r['path']),r['size'],r['text'],r['tracking'],r['x']) for r in item['runs']))
    main_offset,main_top,main_bottom=outline(main);offset,top,bottom=outline(line)
    shift=line['x']+offset-main['x']-main_offset
    indices=np.arange(len(top));mapped=np.rint(indices+shift).astype(int)
    valid=(mapped>=0)&(mapped<len(main_top))
    if above:
        differences=main_top[mapped[valid]]-bottom[valid]
        finite=differences[np.isfinite(differences)]
        # A capital's slanted edge can leave a deep empty triangle. Keep the
        # header above the letter body rather than dropping it alongside it.
        cap=main['top']+max(r['size'] for r in main['runs'])*.22-line['bottom']
        return min(float(finite.min()) if len(finite) else main['top']-line['bottom'],cap)-gap
    differences=main_bottom[mapped[valid]]-top[valid]
    finite=differences[np.isfinite(differences)]
    return max(min(0,main['bottom'])-line['top'],float(finite.max()) if len(finite) else 0)+gap


def layout(words,width,height,font_id='template'):
    from .template_patterns import source_text,source_slot
    return _layout(tuple(words),width,height,font_id,source_text.get(),source_slot.get())


@lru_cache(maxsize=512)
def _layout(words,width,height,font_id='template',pattern_source='',pattern_slot=-1):
    from .renderer import _font_path
    from .styles import font_file
    cfg=profile();plan=composition(words);design=plan.get('design',{});unit=min(width,height*.75);ratio=unit/720
    main_path=_font_path(cfg['main_font'] if font_id=='template' else font_file(font_id,'caption_4'))
    support_path=_font_path(cfg['support_font'] if font_id=='template' else font_file(font_id,'caption_4'))
    lines=[]
    for row in plan['rows']:
        main=row['role'] in ('main','accent') or row['role']=='footer' and design.get('footer_bold');size=design.get(row['role']+'_size',cfg.get(row['role']+'_size',cfg['main_size']));path=main_path if main else support_path;tracking=cfg['tracking'] if main else cfg['support_tracking']
        def runs_for(size):
            f=font(path,max(2,round(size*ratio)));runs=[];cursor=0
            for i in row['words']:
                text=words[i];advance,left,right=text_metrics(path,f.size,text,tracking);box=f.getbbox(text);ascent=f.getmetrics()[0]
                runs.append(dict(i=i,text=text,path=path,size=f.size,tracking=tracking,x=cursor,left=left,right=right,top=box[1]-ascent,bottom=box[3]-ascent))
                cursor+=advance+f.size*cfg['space']
            left=min((r['x']+r['left'] for r in runs),default=0);right=max((r['x']+r['right'] for r in runs),default=0)
            return runs,left,right-left
        runs,left,line_width=runs_for(size)
        # Fit each complete row independently. A long main word must not make
        # its support text tiny, and a wide header must not hang off one side.
        if line_width>unit*cfg['safe_width']:runs,left,line_width=runs_for(size*unit*cfg['safe_width']/line_width)
        lines.append(dict(row=row,runs=runs,left=left,width=line_width,top=min(r['top'] for r in runs),bottom=max(r['bottom'] for r in runs)))
    main=next((line for line in lines if line['row']['role']=='main'),None)
    # Restore the reference's left header/right footer relationship. Limit the
    # offset before centering the complete silhouette, not each row separately.
    safe_width=unit*cfg['safe_width'];max_offset=unit*cfg.get('max_support_offset',.12)
    for line in lines:
        role=line['row']['role']
        offset=0
        if main is not None and role=='header' and design.get('header_alignment')!='center':offset=(line['width']-main['width'])/2+design.get('header_inset',0)*ratio
        elif main is not None and role=='footer' and design.get('footer_alignment')!='center':offset=(main['width']-line['width'])/2+design.get('footer_outset',0)*ratio
        room=max(0,min(max_offset,(safe_width-line['width'])/2))
        offset=max(-room,min(room,offset))
        x=offset-line['width']/2-line['left']
        if role=='main' or main is None:baseline=0
        elif role=='header':
            baseline=main['top']-cfg['header_gap']*ratio-line['bottom']
        else:
            baseline=main['bottom']+cfg['footer_gap']*ratio-line['top']
        line.update(x=x,y=baseline)
    left=min((l['x']+l['left'] for l in lines),default=0);right=max((l['x']+l['left']+l['width'] for l in lines),default=0)
    shift=width/2-(left+right)/2
    for line in lines:line['x']+=shift
    for line in lines:
        role=line['row']['role']
        if main is not None and role=='header':line['y']=optical_baseline(main,line,cfg['header_gap']*ratio,True)
        elif main is not None and role=='footer':line['y']=optical_baseline(main,line,cfg['footer_gap']*ratio)
    return plan,lines,ratio


@lru_cache(maxsize=256)
@patterned
def paginate_cue(cue,font_id='template'):
    from .core import CaptionCue
    remaining=cue.words;groups=[];cfg=profile()
    while remaining:
        fits=[]
        for count in range(1,min(len(remaining),cfg['max_words'])+1):
            _,lines,_=layout([w.text for w in remaining[:count]],720,1280,font_id)
            if all(line['width']<=720*cfg['safe_width']+1 for line in lines):fits.append(count)
        split=max(fits,default=1)
        if len(remaining)-split==1:
            alternatives=[n for n in fits if n<split and len(remaining)-n>=2]
            if alternatives:split=max(alternatives)
        groups.append(remaining[:split]);remaining=remaining[split:]
    return tuple(CaptionCue(group,cue.start if i==0 else group[0].start,groups[i+1][0].start if i+1<len(groups) else cue.end,cue.template_source or cue.text,cue.template_slot) for i,group in enumerate(groups))


def paginate_cues(cues,font_id='template'):
    return [page for cue in cues for page in paginate_cue(cue,font_id)]


def sample_cues():
    from .core import CaptionCue,CaptionWord
    words=[CaptionWord(w['text'],w['start'],w['end']) for w in json.loads(Path(__file__).with_name('caption_one_taj_words.json').read_text('utf8'))['words']]
    groups=[];cursor=0
    for recipe in profile()['demo_phrases']:
        count=len(recipe['text'].split());group=tuple(words[cursor:cursor+count]);cursor+=count
        if ' '.join(w.text for w in group)!=recipe['text']:raise ValueError('Caption 4 narration and sample must keep identical words')
        groups.append(group)
    if cursor!=len(words):raise ValueError('Caption 4 must preserve every narration word')
    return paginate_cues([CaptionCue(g,g[0].start,groups[i+1][0].start if i+1<len(groups) else 30.) for i,g in enumerate(groups)])


@lru_cache(maxsize=128)
def text_asset(width,height,path,size,text,tracking,x,baseline,color):
    from PIL import Image
    from .renderer import _color
    mask=glyph_mask(width,height,path,size,text,tracking,x,baseline)
    layer=Image.new('RGBA',(width,height),_color(color));layer.putalpha(mask);return layer


def render(width,height,cue,seconds,font_id='template',position=.42,word_colors=None,visibility='phrase'):
    from PIL import Image,ImageFilter
    from .renderer import _safe_word_colors
    result=Image.new('RGBA',(width,height))
    if not cue.words or not cue.start<=seconds<cue.end:return result
    pages=paginate_cue(cue,font_id);page_index=next(i for i,p in enumerate(pages) if p.start<=seconds<p.end);offset=sum(len(p.words) for p in pages[:page_index]);cue=pages[page_index]
    if word_colors is not None:word_colors=word_colors[offset:offset+len(cue.words)]
    colors=_safe_word_colors(cue,word_colors);cfg=profile();plan,lines,ratio=layout([w.text for w in cue.words],width,height,font_id)
    H=round(min(width,height*.75)*.85);region=Image.new('RGBA',(width,H));center=H*.5
    exit_seconds=min(cfg['motion']['exit_seconds'],max(.015,(cue.end-cue.words[-1].start)*.20))
    for line in lines:
        main=line['row']['role'] in ('main','accent') or line['row']['role']=='footer' and plan.get('design',{}).get('footer_bold')
        for run in line['runs']:
            i=run['i'];word=cue.words[i]
            if word.start>seconds or visibility=='styled_spoken' and seconds>=word.end:continue
            alpha,blur,dy,scale=motion_state(seconds-word.start,cue.end-seconds,cue.end-word.start,main,exit_seconds)
            x=line['x']+run['x'];baseline=center+line['y'];layer=text_asset(width,H,run['path'],run['size'],run['text'],run['tracking'],x,baseline,colors[i] or cfg['ink'])
            from .scene_capture import tag
            layer=tag(layer,offset+i,run['text'],font(run['path'],run['size']),x,baseline,run['tracking'],colors[i] or cfg['ink'])
            if scale!=1 or dy:
                ax=x+(run['left']+run['right'])/2;ay=baseline+(run['top']+run['bottom'])/2
                layer=layer.transform(layer.size,Image.Transform.AFFINE,(1/scale,0,ax-ax/scale,0,1/scale,ay-ay/scale-dy*ratio/scale),resample=Image.Resampling.BICUBIC)
            if blur>.08:layer=layer.filter(ImageFilter.GaussianBlur(blur*ratio))
            if alpha<1:
                layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
            region.alpha_composite(layer)
    scale,drift=camera_state(seconds-cue.start,plan['motion']);ax=width/2;ay=center-25*ratio
    region=region.transform(region.size,Image.Transform.AFFINE,(1/scale,0,ax-ax/scale,0,1/scale,ay-ay/scale-drift*ratio/scale),resample=Image.Resampling.BICUBIC)
    result.alpha_composite(region,(0,round(height*position-center)));return result


@lru_cache(maxsize=8)
def background_image(width,height):
    from PIL import Image
    return Image.new('RGB',(width,height),'black')
