"""Caption 5: speech-built Inter Black clusters with red/blue emphasis."""
from functools import lru_cache
from .template_patterns import patterned
import json
from pathlib import Path

from .caption_three import font,metrics


@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('caption_five_reference.json').read_text('utf8'))


def normalize(text):
    return ''.join(c for c in text.casefold() if c.isalnum())


def composition(words):
    cfg=profile();key=' '.join(map(normalize,words))
    known=next((r for r in cfg['demo_phrases']+cfg['recipes'] if key==' '.join(map(normalize,r['text'].split()))),None)
    from .template_patterns import rebound
    if rebound(words):known=None
    if not words:return dict(rows=[],mode='stack',tone='red',condensed=False)
    if known is None:
        from .template_patterns import transfer
        known=transfer(words,cfg['demo_phrases']+cfg['recipes'])
    numbers=[i for i,w in enumerate(words) if normalize(w).isdigit()]
    hero=numbers[0] if numbers else known['hero'] if known else max(range(len(words)),key=lambda i:(len(normalize(words[i]))-(100 if normalize(words[i]) in cfg['stop_words'] else 0),-i))
    condensed=known.get('condensed',False) if known else len(normalize(words[hero]))>=8
    tone=known.get('tone','red') if known else 'red'
    mode=known.get('mode','flank') if known else 'flank'
    rows=[]
    if hero:rows.append(dict(role='header',words=list(range(hero))))
    rows.append(dict(role='main',words=[hero]))
    if hero+1<len(words):rows.append(dict(role='footer',words=list(range(hero+1,len(words)))))
    return dict(rows=rows,mode=mode,tone=tone,condensed=condensed,adapted=bool(known and known.get('adapted')),number=bool(numbers and hero in numbers),support_focus=known.get('support_focus',-1) if known else -1)


def smooth(value):
    p=max(0.,min(1.,value));return p*p*(3-2*p)


def motion_state(age,available,main=False,condensed=False):
    cfg=profile()['motion'];duration=min(cfg['main_seconds'] if main else cfg['support_seconds'],max(.06,available*.60))
    p=max(0.,min(1.,age/duration));remaining=(1-p)**3
    fade=min(cfg['condensed_fade'] if condensed and main else cfg['main_fade'] if main else cfg['support_fade'],max(.025,available*.28))
    return (smooth(age/fade),cfg['condensed_slide']*remaining if condensed and main else 0.,
            (cfg['main_rise'] if main and not condensed else cfg['support_rise'] if not main else 0.)*remaining,
            1-(cfg['main_scale'] if main else cfg['support_scale'])*remaining)


def layout(words,width,height,font_id='template'):
    from .template_patterns import source_text,source_slot
    return _layout(tuple(words),width,height,font_id,source_text.get(),source_slot.get())


@lru_cache(maxsize=512)
def _layout(words,width,height,font_id,pattern_source='',pattern_slot=-1):
    from .renderer import _font_path
    from .styles import font_file
    cfg=profile();plan=composition(words);unit=min(width,height*1.75);ratio=unit/720
    regular=str(_font_path(cfg['font'] if font_id=='template' else font_file(font_id,'caption_5')))
    main_path=str(_font_path('impact.ttf')) if plan['condensed'] and font_id=='template' else regular
    lines=[]
    for row in plan['rows']:
        main=row['role']=='main';path=main_path if main else regular
        base=cfg['number_size'] if main and plan['number'] else cfg['condensed_size'] if main and plan['condensed'] else cfg['main_size'] if main else cfg['support_size']
        def runs_for(size):
            runs=[];cursor=0
            for i in row['words']:
                chosen=max(2,round((cfg['support_focus_size'] if not main and i==plan['support_focus'] else size)*ratio))
                text=words[i].upper() if main else words[i];tracking=cfg['tracking'];advance,left,right,top,bottom=metrics(path,chosen,900,text,tracking)
                runs.append(dict(i=i,text=text,size=chosen,path=path,weight=900,tracking=tracking,x=cursor,left=left,right=right,top=top,bottom=bottom))
                cursor+=advance+chosen*cfg['space']
            left=min((r['x']+r['left'] for r in runs),default=0);right=max((r['x']+r['right'] for r in runs),default=0)
            return dict(row=row,runs=runs,left=left,width=right-left,top=min(r['top'] for r in runs),bottom=max(r['bottom'] for r in runs))
        line=runs_for(base)
        if not plan.get('adapted') and main and line['width']>unit*cfg['safe_width']:line=runs_for(base*unit*cfg['safe_width']/line['width'])
        lines.append(line)
    if plan.get('adapted'):
        fit=min([1]+[unit*cfg['safe_width']/max(1,l['width']) for l in lines])
        if plan['mode']=='flank':fit=min(fit,unit*cfg['safe_width']/max(1,sum(l['width'] for l in lines)+max(0,len(lines)-1)*cfg['gap']*ratio))
        if fit<1:
            ratio*=fit
            for line in lines:
                for key in ('left','width','top','bottom'):line[key]*=fit
                for r in line['runs']:
                    for key in ('x','left','right','top','bottom'):r[key]*=fit
                    r['size']=max(2,round(r['size']*fit))
    if not lines:return plan,lines,ratio
    main=next(l for l in lines if l['row']['role']=='main');header=next((l for l in lines if l['row']['role']=='header'),None);footer=next((l for l in lines if l['row']['role']=='footer'),None)
    gap=cfg['gap']*ratio
    combined=sum(l['width'] for l in lines)+max(0,len(lines)-1)*gap
    flank=plan['mode']=='flank' and combined<=unit*cfg['safe_width']+1
    plan=dict(plan,arrangement='flank' if flank else 'stack')
    if flank:
        cursor=(width-combined)/2
        for line in ([header] if header else [])+[main]+([footer] if footer else []):
            line['x']=cursor-line['left'];cursor+=line['width']+gap
            # All words in a horizontal cluster share one alphabetic baseline,
            # including edited support text with punctuation or descenders.
            line['y']=0
    else:
        for line in lines:
            role=line['row']['role'];line['x']=(width-line['width'])/2-line['left']
            if role=='main':line['y']=0
            elif role=='header':line['y']=main['top']-gap-line['bottom']
            else:line['y']=main['bottom']+gap-line['top']
        if header and plan['mode']=='offset':header['x']=max(width*.08,(width-main['width'])/2-header['left'])
        if footer and plan['mode']=='offset':footer['x']=min(width*.92-footer['width'],(width+main['width'])/2-footer['width'])-footer['left']
    if plan.get('adapted'):
        margin=(width-unit*cfg['safe_width'])/2
        for line in lines:line['x']=max(margin-line['left'],min(line['x'],width-margin-line['width']-line['left']))
    # The complete cluster has a fixed anchor; new spoken words never recenter it.
    top=min(l['y']+l['top'] for l in lines);bottom=max(l['y']+l['bottom'] for l in lines);center=(top+bottom)/2
    for line in lines:line['y']-=center
    return plan,lines,ratio


@lru_cache(maxsize=256)
@patterned
def paginate_cue(cue,font_id='template'):
    from .core import CaptionCue
    groups=[];remaining=cue.words
    while remaining:
        fits=[]
        for count in range(1,min(len(remaining),profile()['max_words'])+1):
            _,lines,_=layout([w.text for w in remaining[:count]],720,1280,font_id)
            if all(l['width']<=720*profile()['safe_width']+1 for l in lines):fits.append(count)
        split=max(fits,default=1)
        if len(remaining)-split==1:split=max((n for n in fits if n<split and len(remaining)-n>=2),default=split)
        groups.append(remaining[:split]);remaining=remaining[split:]
    return tuple(CaptionCue(g,cue.start if i==0 else g[0].start,groups[i+1][0].start if i+1<len(groups) else cue.end,cue.template_source or cue.text,cue.template_slot) for i,g in enumerate(groups))


def paginate_cues(cues,font_id='template'):
    return [page for cue in cues for page in paginate_cue(cue,font_id)]


def sample_cues():
    from .core import CaptionCue,CaptionWord
    words=[CaptionWord(w['text'],w['start'],w['end']) for w in json.loads(Path(__file__).with_name('caption_one_taj_words.json').read_text('utf8'))['words']]
    groups=[];cursor=0
    for recipe in profile()['demo_phrases']:
        count=len(recipe['text'].split());g=tuple(words[cursor:cursor+count]);cursor+=count
        if ' '.join(w.text for w in g)!=recipe['text']:raise ValueError('Caption 5 narration and sample words differ')
        groups.append(g)
    if cursor!=len(words):raise ValueError('Caption 5 must preserve all narration words')
    return paginate_cues([CaptionCue(g,g[0].start,groups[i+1][0].start if i+1<len(groups) else 30.) for i,g in enumerate(groups)])


@lru_cache(maxsize=160)
def text_asset(width,height,path,size,text,tracking,x,baseline,color):
    from PIL import Image,ImageDraw
    from .renderer import _color
    selected=font(path,size,900);mask=Image.new('L',(width,height));pen=ImageDraw.Draw(mask)
    for j,c in enumerate(text):pen.text((x+selected.getlength(text[:j])+j*size*tracking,baseline-selected.getmetrics()[0]),c,font=selected,fill=255)
    result=Image.new('RGBA',(width,height),_color(color));result.putalpha(mask);return result


def render(width,height,cue,seconds,font_id='template',position=.45,word_colors=None,visibility='phrase'):
    from PIL import Image
    from .renderer import _safe_word_colors
    result=Image.new('RGBA',(width,height))
    if not cue.words or not cue.start<=seconds<cue.end:return result
    pages=paginate_cue(cue,font_id);page_index=next(i for i,p in enumerate(pages) if p.start<=seconds<p.end);offset=sum(len(p.words) for p in pages[:page_index]);cue=pages[page_index]
    if word_colors is not None:word_colors=word_colors[offset:offset+len(cue.words)]
    colors=_safe_word_colors(cue,word_colors);cfg=profile();plan,lines,ratio=layout([w.text for w in cue.words],width,height,font_id)
    H=round(min(width,height*1.75)*1.05);center=H/2;region=Image.new('RGBA',(width,H))
    for line in lines:
        main=line['row']['role']=='main'
        for run in line['runs']:
            i=run['i'];w=cue.words[i]
            if seconds<w.start or visibility=='styled_spoken' and seconds>=w.end:continue
            alpha,dx,dy,scale=motion_state(seconds-w.start,cue.end-w.start,main,plan['condensed'])
            x=line['x']+run['x'];y=center+line['y'];color=colors[i] or cfg[plan['tone'] if main else 'black']
            layer=text_asset(width,H,run['path'],run['size'],run['text'],run['tracking'],x,y,color)
            from .scene_capture import tag
            layer=tag(layer,offset+i,run['text'],font(run['path'],run['size'],900),x,y,run['tracking'],color,weight=900)
            if scale!=1 or dx or dy:
                ax=x+(run['left']+run['right'])/2;ay=y+(run['top']+run['bottom'])/2
                layer=layer.transform(layer.size,Image.Transform.AFFINE,(1/scale,0,ax-ax/scale-dx*ratio/scale,0,1/scale,ay-ay/scale-dy*ratio/scale),resample=Image.Resampling.BICUBIC)
            if alpha<1:
                layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
            region.alpha_composite(layer)
    result.alpha_composite(region,(0,round(height*position-center)));return result
