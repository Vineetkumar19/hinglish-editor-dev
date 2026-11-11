"""Second reference: compact clean captions, italic emphasis and drawn annotations."""
import json
import math
from copy import deepcopy
from pathlib import Path
from functools import lru_cache
from contextvars import ContextVar
from contextlib import contextmanager

_decorations_only=ContextVar('serif_circle_decorations_only',default=False)

@contextmanager
def decorations_only():
    token=_decorations_only.set(True)
    try:yield
    finally:_decorations_only.reset(token)

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('serif_circle_reference.json').read_text('utf-8'))

def normalize(text):
    return ' '.join(''.join(c for c in w.casefold() if c.isalnum()) for w in text.split())

def recipe_for(words):
    if not words:return None
    key=normalize(' '.join(words))
    cfg=profile()
    from .template_patterns import source_text,transfer
    original=normalize(source_text.get())
    # A frozen source wins even if the replacement happens to match another demo.
    saved=next((r for r in cfg['recipes'] if normalize(r['text'])==key),None) if not original or original==key else None
    if saved:result=deepcopy(saved)
    else:
        candidates=[r for r in cfg['recipes'] if r.get('reference_pattern') or normalize(r['text'])==original]
        result=transfer(words,candidates or cfg['recipes'])
    return fit_new_words(result,words)


def fit_new_words(plan,words):
    """Fit complete ink rows, preserving same-line relationships and open paths."""
    cfg=profile();original=next(r for r in cfg['recipes'] if r['text']==plan.get('template_pattern',plan['text']))
    old_words=original['text'].split()
    old_rows=original['rows']
    # A very short replacement can miss every serif slot under proportional
    # mapping. Keep a real emphasis slot instead of silently changing fonts.
    emphasis=next((r for r in old_rows if r.get('face')=='serif'),None)
    if emphasis and not any(r.get('face')=='serif' for r in plan['rows']):
        focus=min(len(words)-1,math.floor((emphasis['words'][0]+.5)*len(words)/len(old_words)))
        rows=[]
        for row in plan['rows']:
            row['words']=[i for i in row['words'] if i!=focus]
            if row['words']:rows.append(row)
        rows.append(dict(deepcopy(emphasis),words=[focus]))
        plan['rows']=sorted(rows,key=lambda r:r['source_row'])
    if original.get('replace_words'):
        plan['replace_words']=True
        plan['rows']=[dict(old_rows[min(len(old_rows)-1,math.floor((i+.5)*len(old_rows)/len(words)))],words=[i],reveal='word') for i in range(len(words))]
    row_caps={i:600 for i in range(len(old_rows))}
    for spec in original.get('decorations',[]):
        if spec['kind']!='circle':continue
        ids=spec['target_rows'];old=union([row_bounds(old_rows[i],old_words) for i in ids])
        xy=decoration_points(spec,1);span=max(x for x,y in xy)-min(x for x,y in xy)
        cap=max(160,min(600,590*(old[2]-old[0]+24)/max(1,span)-24))
        for i in ids:row_caps[i]=min(row_caps[i],cap)
    for row in plan['rows']:
        row.setdefault('source_row',next(i for i,r in enumerate(old_rows) if r['y']==row['y'] and r.get('x',360)==row.get('x',360)))
        row.setdefault('band',old_rows[row['source_row']].get('band',row['source_row']))
        box=row_bounds(row,words)
        fit=min(1,row_caps[row['source_row']]/max(1,box[2]-box[0]))
        row['size']=row.get('size',cfg['size'])*fit
    # Pack rows which share a baseline horizontally. Never turn them into a stack.
    bands=sorted(set(r['band'] for r in plan['rows']))
    previous=None;previous_source=None
    for band in bands:
        rows=[r for r in plan['rows'] if r['band']==band]
        source=[r for r in old_rows if r.get('band',r.get('source_row'))==band]
        desired=union([row_bounds(r,words) for r in rows])
        right=None
        for row in sorted(rows,key=lambda r:r.get('x',360)):
            box=row_bounds(row,words)
            if right is not None and not plan.get('replace_words'):row['x']=row.get('x',360)+max(0,right+8-box[0])
            right=row_bounds(row,words)[2]
        packed=union([row_bounds(r,words) for r in rows])
        shift=(desired[0]+desired[2]-packed[0]-packed[2])/2
        for row in rows:row['x']=row.get('x',360)+shift
        # A wide split line is fitted as a line, independently of other bands.
        packed=union([row_bounds(r,words) for r in rows])
        fit=min(1,600/max(1,packed[2]-packed[0]));center=(packed[0]+packed[2])/2
        for row in rows:
            row['x']=center+(row['x']-center)*fit;row['size']*=fit
        box=union([row_bounds(r,words) for r in rows])
        source_box=union([row_bounds(r,old_words) for r in source])
        if previous is not None:
            gap=max(3,min(8,source_box[1]-previous_source[3]))
            dy=previous[3]+gap-box[1]
            for row in rows:row['y']+=dy
        previous=union([row_bounds(r,words) for r in rows]);previous_source=source_box
    for spec,old_spec in zip(plan.get('decorations',[]),original.get('decorations',[])):
        ids=old_spec.get('target_rows',list(range(len(old_rows))))
        targets=[r for r in plan['rows'] if r['source_row'] in ids]
        if not targets:
            targets=[min(plan['rows'],key=lambda r:min(abs(r['source_row']-i) for i in ids))]
        old=union([row_bounds(old_rows[i],old_words) for i in ids]);new=union([row_bounds(r,words) for r in targets])
        sx=(new[2]-new[0]+24)/max(1,old[2]-old[0]+24)
        sy=(new[3]-new[1]+16)/max(1,old[3]-old[1]+16) if spec['kind']=='circle' else 1
        def point(x,y):
            nx=(new[0]+new[2])/2+(x-(old[0]+old[2])/2)*sx
            ny=(new[1]+new[3])/2+(y-(old[1]+old[3])/2)*sy if spec['kind']=='circle' else new[3]+y-old[3]
            return [nx,ny]
        spec['path']=[[point(x,y+old_spec.get('y',0)) for x,y in segment] for segment in old_spec['path']];spec['y']=0
    boxes=[row_bounds(r,words) for r in plan['rows']]
    for spec in plan.get('decorations',[]):
        xy=decoration_points(spec,1);pad=spec.get('stroke',3)/2+(6 if spec.get('glow') else 0)
        boxes.append((min(x for x,y in xy)-pad,min(y for x,y in xy)-pad,max(x for x,y in xy)+pad,max(y for x,y in xy)+pad))
    box=union(boxes);dx=360-(box[0]+box[2])/2;dy=-(box[1]+box[3])/2
    for row in plan['rows']:row['x']=row.get('x',360)+dx;row['y']+=dy
    for spec in plan.get('decorations',[]):spec['path']=[[[x+dx,y+dy] for x,y in seg] for seg in spec['path']]
    plan['bounds']=[box[0]+dx,box[1]+dy,box[2]+dx,box[3]+dy]
    return plan


def union(boxes):
    return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)


@lru_cache(maxsize=4096)
def ink_metrics(text,face,size,tracking):
    from PIL import ImageFont
    from .renderer import _font_path
    font=ImageFont.truetype(str(_font_path(profile()['fonts'][face])),max(2,round(size*10)))
    boxes=[]
    for j,char in enumerate(text):
        box=font.getbbox(char,anchor='ls');x=font.getlength(text[:j])/10+j*size*tracking
        boxes.append((x+box[0]/10,box[1]/10,x+box[2]/10,box[3]/10))
    return union(boxes) if boxes else (0,0,0,0)


def row_geometry(row,words,measure=None):
    cfg=profile();size=row.get('size',cfg['size']);face=row.get('face','sans');tracking=row.get('tracking',cfg['tracking'])
    if measure is None:
        from PIL import ImageFont
        from .renderer import _font_path
        font=ImageFont.truetype(str(_font_path(cfg['fonts'][face])),max(2,round(size*10)))
        measure=lambda text,file,sz,tr:font.getlength(text)/10+max(0,len(text)-1)*sz*tr
    cursor=0;items=[]
    for i in row['words']:
        text=words[i].upper() if row.get('case')=='upper' else words[i]
        box=ink_metrics(text,face,size,tracking)
        items.append((i,cursor,box));cursor+=measure(text,cfg['fonts'][face],size,tracking)+size*.2
    box=union([(x+b[0],b[1],x+b[2],b[3]) for i,x,b in items])
    return items,box


def row_bounds(row,words):
    _,b=row_geometry(row,words);x=row.get('x',360);y=row['y']
    return x-(b[2]-b[0])/2,y-(b[3]-b[1])/2,x+(b[2]-b[0])/2,y+(b[3]-b[1])/2

def pages(cue,width,height):
    from .kinetic_gold import pages as paginate
    if height>=width and len(cue.words)==7 and recipe_for([w.text for w in cue.words]):
        from .core import CaptionCue
        split=3;boundary=cue.words[split].start
        return [(0,CaptionCue(cue.words[:split],cue.start,boundary,cue.template_source or cue.text,cue.template_slot)),(split,CaptionCue(cue.words[split:],boundary,cue.end,cue.template_source or cue.text,cue.template_slot))]
    return paginate(cue,width,height)

def plan(words,measure,recipe=None):
    cfg=profile();recipe=recipe or recipe_for(words)
    rows=recipe['rows'] if recipe else [{'words':list(range(len(words))),'y':0}]
    runs=[]
    for row in rows:
        face=row.get('face','sans');size=row.get('size',cfg['size']);tracking=row.get('tracking',cfg['tracking'])
        ids=row['words'];items,box=row_geometry(row,words,measure)
        left=row.get('x',360)-(box[0]+box[2])/2;baseline=row['y']-(box[1]+box[3])/2
        for i,x,b in items:
            runs.append(dict(index=i,text=words[i].upper() if row.get('case')=='upper' else words[i],row_text=' '.join(words[j] for j in ids),x=left+x+(b[0]+b[2])/2,y=baseline+(b[1]+b[3])/2,
                             origin_x=left+x,baseline=baseline,size=size,face=face,tracking=tracking,
                             color=row.get('color','#FFFFFF'),reveal_with=ids[0] if row.get('reveal')=='row' else i,motion=recipe.get('motion','rise') if recipe else 'cut'))
    return sorted(runs,key=lambda r:r['index'])

def motion(age,kind):
    if kind=='cut':return 1,0,0
    p=max(0,min(1,age/.23));ease=1-(1-p)**3
    fade=max(0,min(1,age/.14));fade=fade*fade*(3-2*fade)
    return fade,46*(1-ease),7.5*(1-p)**2

def decoration_points(spec,progress):
    progress=max(0,min(1,progress));points=[]
    if 'path' in spec:
        path=[]
        for segment in spec['path']:
            for i in range(61):
                t=i/60
                path.append(tuple((1-t)**3*segment[0][d]+3*(1-t)**2*t*segment[1][d]+3*(1-t)*t*t*segment[2][d]+t**3*segment[3][d]+(spec.get('y',0) if d==1 else 0) for d in (0,1)))
        lengths=[0]
        for a,b in zip(path,path[1:]):lengths.append(lengths[-1]+math.dist(a,b))
        cutoff=lengths[-1]*progress;points=[path[0]]
        for i in range(1,len(path)):
            if lengths[i]<=cutoff:points.append(path[i]);continue
            f=(cutoff-lengths[i-1])/max(.00001,lengths[i]-lengths[i-1])
            points.append(tuple(path[i-1][d]+f*(path[i][d]-path[i-1][d]) for d in (0,1)));break
        return points
    # Old callers receive the open source contour, never a generated ellipse.
    source=next(d for r in profile()['recipes'] for d in r.get('decorations',[]) if d['kind']==spec['kind'] and 'path' in d)
    return decoration_points(source,progress)

def stroke_outline(points,stroke,progress):
    left=[];right=[]
    for i,(x,y) in enumerate(points):
        a=points[max(0,i-1)];b=points[min(len(points)-1,i+1)];dx=b[0]-a[0];dy=b[1]-a[1];length=max(.001,math.hypot(dx,dy))
        t=progress*i/max(1,len(points)-1);half=stroke*(.12+.88*math.sin(math.pi*t)**.6)/2
        left.append((x-dy/length*half,y+dx/length*half));right.append((x+dy/length*half,y-dx/length*half))
    return left+right[::-1]

def render(width,height,cue,seconds,font_id='template',position=.65,size=1,colors=None,visibility='phrase'):
    from PIL import Image,ImageDraw,ImageFont,ImageFilter
    from .renderer import _font_path
    from .styles import font_file
    from .scene_capture import tag
    cfg=profile();out=Image.new('RGBA',(width,height));active=next(((o,p) for o,p in pages(cue,width,height) if p.start<=seconds<p.end),None)
    if not active:return out
    offset,page=active
    from .template_patterns import pattern_context
    def measure(text,file,sz,tracking):
        f=ImageFont.truetype(str(_font_path(file)),max(2,round(sz*10)))
        return f.getlength(text)/10+max(0,len(text)-1)*sz*tracking
    with pattern_context(cue):
        local_words=[w.text for w in page.words];recipe=recipe_for(local_words)
        runs=[dict(r,index=r['index']+offset,reveal_with=r['reveal_with']+offset) for r in plan(local_words,measure,recipe)]
    recipe=dict(recipe,decorations=[dict(d,trigger=d['trigger']+offset) for d in recipe.get('decorations',[])])
    yshift=0
    ratio=min(width/720,height/720)*size
    box=recipe['bounds']
    ratio=min(ratio,width*.84/max(1,box[2]-box[0]),
              height*max(.01,position-.04)/max(1,-box[1]+24),
              height*max(.01,.96-position)/max(1,box[3]+56))
    for r in runs:
        if _decorations_only.get():continue
        i=r['index'];reveal=max(offset,r['reveal_with']);age=seconds-cue.words[reveal].start
        if age<0 or (visibility=='styled_spoken' and not cue.words[i].start<=seconds<cue.words[i].end):continue
        if recipe and recipe.get('replace_words') and not cue.words[i].start<=seconds<cue.words[i].end:continue
        alpha,rise,blur=motion(age,r['motion'])
        file=cfg['fonts'][r['face']] if font_id=='template' else font_file(font_id,'serif_circle_draft')
        font=ImageFont.truetype(str(_font_path(file)),max(2,round(r['size']*ratio)))
        tracking=r['tracking'];text=r['text']
        actual=[]
        for j,char in enumerate(text):
            b=font.getbbox(char);start=font.getlength(text[:j])+j*font.size*tracking
            actual.append((start+b[0],b[1],start+b[2],b[3]))
        ink=union(actual)
        x=width/2+(r['x']-360)*ratio-(ink[0]+ink[2])/2;baseline=height*position+(r['baseline']+rise)*ratio
        color=colors[i] if colors and i<len(colors) and colors[i] else r['color']
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for j,char in enumerate(text):pen.text((x+font.getlength(text[:j])+j*font.size*tracking,baseline),char,font=font,fill=color,anchor='ls')
        layer=tag(layer,i,text,font,x,baseline,tracking=tracking,color=color)
        if blur:layer=layer.filter(ImageFilter.GaussianBlur(blur*ratio))
        layer.putalpha(layer.getchannel('A').point(lambda a:round(a*alpha)))
        out.alpha_composite(layer)
    if recipe:
        for source in recipe.get('decorations',[]):
            if not offset<=source['trigger']<offset+len(page.words):continue
            age=seconds-cue.words[source['trigger']].start-source.get('delay',0)
            if age<=0:continue
            p=min(1,age/source.get('duration',.65));p=p if source.get('linear') else 1-(1-p)**2
            spec=dict(source);spec['y']-=yshift
            xy=[(width/2+(x-360)*ratio,height*position+y*ratio) for x,y in decoration_points(spec,p)]
            layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
            stroke=spec.get('stroke',3)*ratio
            if spec.get('taper'):pen.polygon(stroke_outline(xy,stroke,p),fill=spec['color'])
            else:
                pen.line(xy,fill=spec['color'],width=max(1,round(stroke)),joint='curve')
                for x,y in (xy[0],xy[-1]):pen.ellipse((x-stroke/2,y-stroke/2,x+stroke/2,y+stroke/2),fill=spec['color'])
            if spec.get('glow'):
                glow=layer.filter(ImageFilter.GaussianBlur(6*ratio));glow.putalpha(glow.getchannel('A').point(lambda a:round(a*.55)));out.alpha_composite(glow)
            out.alpha_composite(layer)
    return out

def sample_cues():
    from .core import CaptionCue,CaptionWord
    result=[]
    for row in profile()['sample_groups']:
        words=row['text'].split();starts=row['starts']
        result.append(CaptionCue(tuple(CaptionWord(text,starts[i],starts[i+1] if i+1<len(starts) else row['end']) for i,text in enumerate(words)),starts[0],row['end']))
    return result
