"""Review-only cinematic references. Shared geometry for local video/editor exports."""
import json
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('cinematic_reference.json').read_text('utf-8'))

def pages(cue,width,height):
    from .core import CaptionCue
    limit=4 if height>=width else 7
    return [CaptionCue(cue.words[a:a+limit],cue.start if not a else cue.words[a].start,
        cue.words[a+limit].start if a+limit<len(cue.words) else cue.end,cue.template_source or cue.text,cue.template_slot) for a in range(0,len(cue.words),limit)]

def face(style,index,text):
    cfg=profile()[style]
    from .template_patterns import source_text
    original=source_text.get().split()
    if original:text=original[min(index,len(original)-1)]
    if style=='cinematic_mixed_draft':
        if index==0:return 'GreatVibes-Regular.ttf',cfg['script_size']
        if text.strip(',.!?').lower() in cfg['bold_words']:return 'Inter-Bold.otf',cfg['size']
    return 'Roboto-Regular.ttf',cfg['size']

def render(width,height,cue,seconds,style,font_id='template',position=.456,size=1,colors=None,visibility='phrase',_fit_pass=0):
    from PIL import Image,ImageDraw,ImageFilter,ImageFont
    from .renderer import _font_path,_color
    from .styles import font_file
    output=Image.new('RGBA',(width,height))
    page=next((p for p in pages(cue,width,height) if p.start<=seconds<p.end),None)
    if page is None:return output
    cfg=profile()[style];ratio=(width/720*1.3 if height>=width else min(width/1280,height/720))*size
    offset=next(i for i,w in enumerate(cue.words) if w is page.words[0])
    runs=[];cursor=0
    for i,w in enumerate(page.words):
        filename,points=face(style,i,w.text)
        if font_id!='template':filename=font_file(font_id,style)
        f=ImageFont.truetype(str(_font_path(filename)),max(2,round(points*ratio)))
        advance=f.getlength(w.text);runs.append((w,f,cursor,i));cursor+=advance+cfg['space']*ratio
    span=cursor-cfg['space']*ratio
    if span>width*.88:
        if _fit_pass>=16:raise ValueError('This caption contains a word too wide for the frame. Shorten that word or choose a wider format; your script is kept.')
        return render(width,height,cue,seconds,style,font_id,position,size*width*.88/span*.98,colors,visibility,_fit_pass+1)
    baseline=height*position+cfg['size']*ratio*.32
    for w,f,x,i in runs:
        if seconds<w.start or (visibility=='styled_spoken' and seconds>=w.end):continue
        p=max(0,min(1,(seconds-w.start)/cfg['fade']));alpha=p*p*(3-2*p)
        layer=Image.new('RGBA',output.size);pen=ImageDraw.Draw(layer)
        color=(colors or [])[offset+i] if offset+i<len(colors or []) else None
        xy=((width-span)/2+x,baseline-f.getmetrics()[0]+cfg['rise']*ratio*(1-p)**3)
        pen.text(xy,w.text,font=f,fill=_color(color or '#FFFFFF'),stroke_width=0)
        from .scene_capture import tag
        layer=tag(layer,offset+i,w.text,f,xy[0],xy[1]+f.getmetrics()[0],0,color or '#FFFFFF')
        if p<1:layer=layer.filter(ImageFilter.GaussianBlur(cfg['blur']*ratio*(1-p)))
        layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
        output.alpha_composite(layer)
    return output
