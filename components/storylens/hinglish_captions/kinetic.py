"""Reference typography measured from Shorts 16, isolated from other presets."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name('kinetic_reference.json').read_text(encoding='utf-8'))


def normalized(word):
    return ''.join(c for c in str(word).casefold() if c.isalnum())


def composition(words, effect=None):
    """Use measured reference phrases or the same grammar with new wording.

    Timings never select a random composition: moving a cue keeps its design.
    All indices refer to the source words, including repeated words and echoes.
    """
    config = profile()
    tokens = [normalized(w) for w in words]
    key = ' '.join(tokens)
    known = next((row for row in config['phrases']
                  if key == ' '.join(normalized(w) for w in row['text'].split())), None)
    from .template_patterns import rebound
    if rebound(words):known=None
    candidates = [i for row in known['hero'] for i in row] if known else list(range(len(tokens)))
    if not tokens:
        return {'top': [], 'hero': [], 'bottom': [], 'effect': 'plain', 'color': 0}
    if known is None and len(words)==1:return dict(top=[],hero=[[0]],bottom=[],effect=effect or 'plain',color=0)
    if known is None:
        from .template_patterns import transfer
        recipes=[dict(r,rows=[{'words':r['top'],'role':'support'},
                 *[{'words':ids,'role':'main'} for ids in r['hero']],
                 {'words':r['bottom'],'role':'footer'}]) for r in config['phrases']]
        saved=transfer(words,recipes)
        result={k:v for k,v in saved.items() if k not in ('rows','top','hero','bottom')}
        result.update(top=[i for r in saved['rows'] if r['role']=='support' for i in r['words']],
                      hero=[r['words'] for r in saved['rows'] if r['role']=='main'],
                      bottom=[i for r in saved['rows'] if r['role']=='footer' for i in r['words']],
                      effect=effect or saved['effect'])
        focus=next((ids[0] for ids in result['hero'] if ids),0)
        result.update(top=list(range(focus)),hero=[[focus]],bottom=list(range(focus+1,len(words))))
        if result['effect'] in ('stack','bar'):result['effect']='plain'
        return result
    stops = set(config['stop_words'])
    hero = max(candidates, key=lambda i: (len(tokens[i]) * 3 - (100 if tokens[i] in stops else 0), -i))
    seed = sum(ord(c) for c in key)
    effect = effect or (known['effect'] if known else ('plain', 'plain', 'echo', 'plain', 'plain', 'plain')[seed % 6])
    if effect in ('stack', 'bar'): effect = 'plain'
    result = {'top': list(range(hero)), 'hero': [[hero]], 'bottom': list(range(hero + 1, len(words))),
              'effect': effect, 'color': known['color'] if known else seed % 3}
    for field in ('handwriting','handwriting_ratio','handwriting_gap_ratio','hero_offset_ratio','support_ratio','top_gap_ratio'):
        if known and field in known: result[field] = known[field]
    return result


def highlight_color(words):
    return '#FFFFFF'


def smooth(value):
    p = max(0.0, min(1.0, value))
    return p * p * (3 - 2 * p)


def echo_scale(age):
    """The approved Caption 3 entrance: close framing settling to normal."""
    keys = profile()['echo_zoom']
    if age <= keys[0][0]: return keys[0][1]
    for left, right in zip(keys, keys[1:]):
        if age <= right[0]:
            return left[1] + (right[1]-left[1])*(age-left[0])/(right[0]-left[0])
    return keys[-1][1]


def zoom_group(image, age, anchor):
    """Move a caption composition uniformly, including editable word geometry."""
    from PIL import Image
    scale = echo_scale(age)
    if abs(scale-1) <= .0001: return image
    ax, ay = anchor
    return image.transform(image.size, Image.Transform.AFFINE,
        (1/scale,0,ax-ax/scale,0,1/scale,ay-ay/scale),
        resample=Image.Resampling.BICUBIC)


@lru_cache(maxsize=256)
def _font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, max(2, round(size)))


def render(width, height, cue, seconds, font_id='template', position=.86015625, word_colors=None, visibility='phrase', style_name='kinetic_documentary'):
    """Reference lettering and quick word reveals, without background stripes."""
    from PIL import Image, ImageDraw, ImageFilter
    from .renderer import _font_path, _safe_word_colors, _color
    from .styles import font_file, template
    config = profile()
    output = Image.new('RGBA', (width, height))
    if not cue.start <= seconds < cue.end: return output
    words = [w.text.strip('.,!?:;"'+chr(39)) or w.text for w in cue.words]
    if not words: return output
    plan = composition(words, template(style_name).get('reference_effect'))
    hero_index = plan['hero'][0][0]
    unit = min(width, height * config['landscape_unit_ratio']) * config['default_scale']
    region_height = round(unit * config['region_ratio'])
    region = Image.new('RGBA', (width, region_height))
    draw = ImageDraw.Draw(region)
    main_path = str(_font_path(font_file(font_id, style_name)))
    small_path = str(_font_path('arialbd.ttf'))
    script_path = str(_font_path('Inkfree.ttf'))
    colors = _safe_word_colors(cue, word_colors)
    enter = config['enter_frames'] / config['reference_fps']
    leave = smooth((cue.end-seconds) / (config['exit_frames'] / config['reference_fps']))
    gap = unit * config['gap_ratio']
    safe = width * config['safe_width'] * config['default_scale']

    def chosen_font(indices, ratio, path, script=False):
        text = ' '.join(words[i] if script else words[i].upper() for i in indices) or 'H'
        size = max(2, round(unit * ratio))
        selected = _font(path, size)
        measured = draw.textlength(text, font=selected)
        if measured > safe:
            selected = _font(path, max(2, int(size * safe / measured)))
        box = selected.getbbox('H')
        return selected, box[3] - box[1]

    is_script = plan['effect'] == 'script'
    main, cap = chosen_font([hero_index], config['script_ratio'] if is_script else config['hero_ratio'],
                            script_path if is_script else main_path, is_script)
    hero_text = words[hero_index] if is_script else words[hero_index].upper()
    hero_box = main.getbbox(hero_text)
    cap = hero_box[3] - hero_box[1]
    hero_top = region_height / 2 - cap / 2 + unit*plan.get('hero_offset_ratio',0)
    handwriting = plan.get('handwriting',[])
    small_top = [i for i in plan['top'] if i not in handwriting]
    small, small_cap = chosen_font(small_top + plan['bottom'], plan.get('support_ratio',config['small_ratio']), small_path)
    top_gap = unit*plan.get('top_gap_ratio',config['gap_ratio'])

    def visible(i):
        word = cue.words[i]
        return word.start <= seconds and (visibility != 'styled_spoken' or seconds < word.end)

    def alpha(i):
        return smooth((seconds-cue.words[i].start)/enter)*leave if visible(i) else 0

    def row(indices, selected, y, script=False, outline=False, opacity=1):
        texts = [words[i] if script else words[i].upper() for i in indices]
        x = (width - draw.textlength(' '.join(texts), font=selected)) / 2
        space = draw.textlength(' ', font=selected)
        baseline = y-selected.getbbox(' '.join(texts) or 'H')[1]
        for i, text in zip(indices, texts):
            fade = alpha(i)
            if fade:
                color = colors[i] or (highlight_color(words) if i == hero_index else '#FFFFFF')
                xy = (x, baseline)
                ink = Image.new('RGBA', region.size); pen = ImageDraw.Draw(ink)
                if outline:
                    pen.text(xy, text, font=selected, fill=(0,0,0,0),
                             stroke_width=max(1, round(unit/540)), stroke_fill=_color(color, round(255*fade*opacity)))
                else:
                    # Keep the reference silhouette during the word reveal.
                    pen.text(xy, text, font=selected, fill=(0,0,0,round(255*leave)))
                    color_layer=Image.new('RGBA',region.size)
                    ImageDraw.Draw(color_layer).text(xy,text,font=selected,fill=_color(color,round(255*fade)))
                    ink.alpha_composite(color_layer)
                from .scene_capture import tag_draw
                tag_draw(ImageDraw.Draw(ink),i,text,selected,xy,color,fade*opacity,outline,max(1,round(unit/540)) if outline else 0)
                blur = (1-fade)*unit*.005
                if blur>.15: ink=ink.filter(ImageFilter.GaussianBlur(blur))
                region.alpha_composite(ink)
            x += draw.textlength(text, font=selected) + space

    if plan['effect']=='echo':
        echo=_font(main_path,main.size*config['echo_ratio'])
        measured=draw.textlength(words[hero_index].upper(),font=echo)
        camera_peak=max(v for _,v in config['echo_zoom']) if style_name in config['zoom_styles'] else 1
        echo_safe=width*.90/camera_peak
        if measured>echo_safe:echo=_font(main_path,echo.size*echo_safe/measured)
        row([hero_index],echo,hero_top+cap*config['echo_offset'],outline=True,opacity=config['echo_opacity'])
    if handwriting:
        script, _=chosen_font(handwriting,plan['handwriting_ratio'],script_path,True)
        script_text=' '.join(words[i] for i in handwriting)
        box=script.getbbox(script_text);script_cap=box[3]-box[1]
        row(handwriting,script,hero_top-small_cap-top_gap-unit*plan['handwriting_gap_ratio']-script_cap,True)
    row(small_top, small, hero_top-small_cap-top_gap)
    row([hero_index], main, hero_top, is_script, outline=plan['effect']=='outline')
    row(plan['bottom'], small, hero_top+cap+gap)
    if style_name in config['zoom_styles']:
        region = zoom_group(region, seconds-cue.words[hero_index].start,
                            (width/2, hero_top+cap/2))
    output.alpha_composite(region, (0, round(height * position-region_height/2)))
    return output
