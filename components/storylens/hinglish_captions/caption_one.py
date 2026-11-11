"""Caption 1: measured Inter typography from reference video 1."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('caption_one_reference.json').read_text('utf-8'))


def normalize(text):
    return ''.join(c for c in text.casefold() if c.isalnum())


def composition(words):
    config = profile()
    key = ' '.join(map(normalize, words))
    if not words:
        return {'rows': [], 'hero': 0}
    def matches_prefix(recipe):
        tokens=list(map(normalize,recipe['text'].split()))
        return list(map(normalize,words)) == tokens[:len(words)]
    known = next((r for r in config['recipes'] if matches_prefix(r)), None)
    sample = next((r for r in config.get('demo_phrases',[])
                   if matches_prefix(r) and r['hero']<len(words)),None)
    stops = set(config['stop_words'])
    candidates = [i for row in known['rows'] if row.get('blue') for i in row['words']] if known else []
    interior = list(range(1,len(words))) if len(words)>=2 else [0]
    candidates = [i for i in candidates if i in interior]
    hero = sample['hero'] if sample else max(candidates or interior, key=lambda i: (len(normalize(words[i])) - (100 if normalize(words[i]) in stops else 0), -i))
    two_lines = len(normalize(words[hero])) >= config['alignment']['two_line_letters']
    rows = []
    if hero:
        rows.append({'words': list(range(hero)), 'size': 46, 'align': 'left', 'baseline': -.75})
    rows.append({'words': [hero], 'size': 80, 'align': 'left', 'baseline': 0, 'blue': True, 'upper': True})
    footer=list(range(hero+1,len(words)))
    if footer and not two_lines:
        rows.append({'words':footer,'size':46,'align':'right','baseline':.54})
    shown={i for row in rows for i in row['words']}
    return {'rows': rows, 'hero': hero, 'display': known.get('display', {}) if known else {},
            'hidden': [i for i in range(len(words)) if i not in shown], 'two_line':two_lines}


@lru_cache(maxsize=256)
def font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(path), max(2, round(size)))


def motion_state(elapsed, motion):
    """Slow movement with gentle starts and stops, without frame snapping."""
    progress = max(0., min(1., elapsed / motion['duration']))
    eased = progress**3*(progress*(progress*6-15)+10)
    fade = max(0.,min(1.,elapsed/motion['fade']))
    alpha = fade*fade*(3-2*fade)
    return (alpha, motion['x'] * (1-eased), motion['y'] * (1-eased))


def motion_for(plan, row, index):
    config = profile()['smooth_motion']
    main = index == plan['hero']
    return {'duration': config['main_seconds'] if main else config['support_seconds'],
            'fade': config['main_fade_seconds'] if main else config['support_fade_seconds'],
            'x': 0 if main else config['slide_x'],
            'y': config['rise_y'] if main else 0,
            'start_word': index if main else row['words'][0]}


def phase_at(plan, words, seconds, end, visibility='phrase'):
    """Build the three-line stack cumulatively and hold it to the cue boundary."""
    if visibility=='styled_spoken':
        shown={i for row in plan['rows'] for i in row['words']}
        indices=[i for i,w in enumerate(words) if i in shown and w.start<=seconds<w.end]
    else:
        indices=sorted(i for row in plan['rows'] if words[row['words'][0]].start<=seconds for i in row['words'])
    return {'kind':'stack','indices':indices,'onset':words[0].start,'end':end}


@lru_cache(maxsize=128)
def glyph_mask(width, height, path, size, text, tracking, x, baseline):
    """Rasterize at a stable position; fractional motion resamples the mask."""
    from PIL import Image, ImageDraw
    selected = font(path,size)
    mask = Image.new('L',(width,height))
    pen = ImageDraw.Draw(mask)
    for j,c in enumerate(text):
        px = x + selected.getlength(text[:j]) + j*selected.size*tracking
        pen.text((px,baseline-selected.getmetrics()[0]),c,font=selected,fill=255)
    return mask


@lru_cache(maxsize=1024)
def text_metrics(path,size,text,tracking):
    selected=font(path,size)
    left,right=None,None
    for j,c in enumerate(text):
        px=selected.getlength(text[:j])+j*selected.size*tracking
        box=selected.getbbox(c)
        ink=selected.getmask(c).getbbox()
        if ink:
            a,b=px+box[0]+ink[0],px+box[0]+ink[2]
            left=a if left is None else min(left,a)
            right=b if right is None else max(right,b)
    advance=selected.getlength(text)+max(0,len(text)-1)*selected.size*tracking
    return advance,left or 0.,right or 0.


@lru_cache(maxsize=256)
def paginate_cue(cue, font_id='template'):
    """Fit complete, visible word groups; continue every overflow word in time."""
    from .core import CaptionCue
    from .renderer import _font_path
    from .styles import font_file
    config=profile()
    main_path=_font_path('Inter-Bold.otf' if font_id=='template' else font_file(font_id,'caption_1'))
    support_path=_font_path('Inter-Medium.otf' if font_id=='template' else font_file(font_id,'caption_1'))

    def width(words,indices,main=False):
        size=80 if main else 46;path=main_path if main else support_path
        tracking=config['tracking'] if main else config['support_tracking']
        cursor=0;lefts=[];rights=[]
        for i in indices:
            text=words[i].upper() if main else words[i]
            advance,left,right=text_metrics(path,size,text,tracking)
            lefts.append(cursor+left);rights.append(cursor+right)
            cursor+=advance+80*config['word_gap']
        return max(rights,default=0)-min(lefts,default=0)

    remaining=cue.words;groups=[]
    while remaining:
        words=tuple(w.text.strip('.,!?:;') or w.text for w in remaining)
        fits=[]
        for count in range(1,len(words)+1):
            prefix=words[:count];plan=composition(prefix)
            # Two-line layouts end on their hero word. Their remaining words
            # belong to the next slide, never to a hidden renderer row.
            if plan['hidden']:continue
            cap=width(prefix,[plan['hero']],True)-abs(config['smooth_motion']['slide_x'])
            if all(width(prefix,row['words'],row.get('blue',False)) <=
                   (cap if row['align']=='right' else config['native_width']*config['max_width'])
                   for row in plan['rows']):
                fits.append(count)
        split=max(fits,default=1)
        if len(remaining)-split==1:
            alternatives=[n for n in fits if n<split and len(remaining)-n>=2]
            if alternatives:split=max(alternatives)
        groups.append(remaining[:split]);remaining=remaining[split:]
    return tuple(CaptionCue(group,cue.start if i==0 else group[0].start,
                           groups[i+1][0].start if i+1<len(groups) else cue.end)
                 for i,group in enumerate(groups))


def paginate_cues(cues,font_id='template'):
    return [page for cue in cues for page in paginate_cue(cue,font_id)]


def layout(width, height, words, font_id='template'):
    """One source of typography geometry for rendered and editable captions."""
    from .renderer import _font_path
    from .styles import font_file
    config=profile();plan=composition(words)
    words=[plan.get('display',{}).get(str(i),word) for i,word in enumerate(words)]
    unit=min(width,height*.75);scale=unit/config['native_width'];H=round(unit*config['region_ratio'])
    main_path=_font_path('Inter-Bold.otf' if font_id=='template' else font_file(font_id,'caption_1'))
    small_path=_font_path('Inter-Medium.otf' if font_id=='template' else font_file(font_id,'caption_1'))

    def make_line(row,ratio):
            runs = []
            for j,i in enumerate(row['words']):
                native_size = row.get('sizes', [row.get('size', 80)]*len(row['words']))[j]
                selected = font(main_path if native_size > 46 else small_path, native_size*ratio)
                text = words[i].upper() if row.get('upper') else words[i]
                tracking=config['support_tracking'] if native_size<=46 else config['tracking']
                advance,ink_left,ink_right=text_metrics(selected.path,selected.size,text,tracking)
                runs.append((i,text,selected,advance,tracking,ink_left,ink_right))
            mixed=len(set(row.get('sizes',[])))>1
            gap=80*ratio*(.1 if mixed else 0 if row.get('blue') else config['word_gap'])
            cursor=0;lefts=[];rights=[]
            for run in runs:
                lefts.append(cursor+run[5]);rights.append(cursor+run[6]);cursor+=run[3]+gap
            ink_left=min(lefts,default=0);line_width=max(rights,default=0)-ink_left
            return (row,runs,line_width,gap,ink_left)

    def arrange(ratio):
        return [make_line(row,ratio) for row in plan['rows']]

    lines = arrange(scale)
    widest = max((r[2] for r in lines), default=1)
    if widest > width*config['max_width']:
        scale *= width*config['max_width']/widest
        lines = arrange(scale)
    group_width = max((r[2] for r in lines), default=0)
    left = (width-group_width)/2
    main_width=next(line[2] for line in lines if plan['hero'] in line[0]['words'])
    main_line=next(line for line in lines if plan['hero'] in line[0]['words'])
    main_bottom=H/2+plan.get('offset',0)*scale+max(
        selected.getbbox(text)[3]-selected.getmetrics()[0]
        for _,text,selected,*_ in main_line[1])
    main_top=H/2+plan.get('offset',0)*scale+min(
        selected.getbbox(text)[1]-selected.getmetrics()[0]
        for _,text,selected,*_ in main_line[1])
    line_gap=config['alignment'].get('ink_gap',9)*scale
    positioned=[]
    for row,runs,line_width,gap,ink_left in lines:
        visible_left=(width-line_width)/2 if plan['two_line'] else left+main_width-line_width if row['align']=='right' else left
        x=visible_left-ink_left
        x += row.get('x',0)*80*scale
        baseline = H/2 + row['baseline']*80*scale + plan.get('offset',0)*scale
        if row['align']=='right':
            # Match visible ink, including endings without tall ascenders.
            ascent=max(selected.getmetrics()[0]-selected.getbbox(text)[1]
                       for _,text,selected,*_ in runs)
            baseline=main_bottom+line_gap+ascent
        elif not row.get('blue') and row['baseline']<0:
            descent=max(selected.getbbox(text)[3]-selected.getmetrics()[0]
                        for _,text,selected,*_ in runs)
            baseline=main_top-line_gap-descent
        for i,text,selected,advance,tracking,_,_ in runs:
            positioned.append({'index':i,'text':text,'font':selected,'tracking':tracking,'x':x,'baseline':baseline,'row':row})
            x += advance + gap
    return {'plan':plan,'scale':scale,'height':H,'words':positioned}


def render(width, height, cue, seconds, font_id='template', position=.6234375,
           word_colors=None, visibility='phrase'):
    from PIL import Image, ImageDraw, ImageFilter
    from .renderer import _font_path, _safe_word_colors, _color
    from .styles import font_file
    import numpy as np
    out = Image.new('RGBA', (width, height))
    if not cue.start <= seconds < cue.end or not cue.words:
        return out
    pages=paginate_cue(cue,font_id)
    selected_page=next(i for i,page in enumerate(pages) if page.start<=seconds<page.end)
    offset=sum(len(page.words) for page in pages[:selected_page])
    cue=pages[selected_page]
    if word_colors is not None:word_colors=word_colors[offset:offset+len(cue.words)]
    config = profile()
    words = [w.text.strip('.,!?:;') or w.text for w in cue.words]
    plan = composition(words)
    phase = phase_at(plan,cue.words,seconds,cue.end,visibility)
    words = [plan.get('display', {}).get(str(i), word) for i, word in enumerate(words)]
    unit = min(width, height*.75)
    scale = unit / config['native_width']
    H = round(unit * config['region_ratio'])
    region = Image.new('RGBA', (width, H))
    colors = _safe_word_colors(cue, word_colors)
    geometry=layout(width,height,[w.text.strip('.,!?:;') or w.text for w in cue.words],font_id)
    scale=geometry['scale']
    for run in geometry['words']:
            i,text,selected,tracking,x,baseline,row=(run[k] for k in ('index','text','font','tracking','x','baseline','row'))
            word = cue.words[i]
            motion = motion_for(plan, row, i)
            onset=word.start if visibility=='styled_spoken' else cue.words[motion['start_word']].start
            alpha, dx, dy = motion_state(seconds-onset, motion)
            alpha = alpha if i in phase['indices'] else 0
            if alpha:
                mask = glyph_mask(width,H,selected.path,selected.size,text,tracking,x,baseline)
                if dx or dy:
                    mask = mask.transform(mask.size,Image.Transform.AFFINE,
                        (1,0,-dx*scale,0,1,-dy*scale),resample=Image.Resampling.BICUBIC)
                if alpha < 1:
                    mask = mask.point(lambda a:round(a*alpha))
                shadow = mask.filter(ImageFilter.GaussianBlur(max(.3,scale)))
                shade = Image.new('RGBA',region.size,(0,0,0,0))
                shade.putalpha(shadow.point(lambda a: round(a*.5)))
                region.alpha_composite(shade,(0,round(2*scale)))
                custom = colors[i]
                if row.get('blue') and not custom:
                    box = selected.getbbox(text)
                    y0 = baseline+dy*scale-selected.getmetrics()[0]+box[1]
                    y1 = baseline+dy*scale-selected.getmetrics()[0]+box[3]
                    stops = config['gradient']
                    ys = np.clip((np.arange(H)-y0)/max(1,y1-y0),0,1)
                    rgb = np.array([_color(color)[:3] for _,color in stops])
                    ramps = np.stack([np.interp(ys,[s[0] for s in stops],rgb[:,c]) for c in range(3)],axis=1)
                    ink = Image.fromarray(np.repeat(ramps.astype('uint8')[:,None,:],width,axis=1),'RGB').convert('RGBA')
                else:
                    ink = Image.new('RGBA',region.size,_color(custom or '#FFFFFF'))
                ink.putalpha(mask)
                region.alpha_composite(ink)
    out.alpha_composite(region,(0,round(height*position-H/2)))
    return out
