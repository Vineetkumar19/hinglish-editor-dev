"""Shared settings and deterministic typography for Thumbnail's image categories."""
import html
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

CATEGORIES = {
    'youtube': ('YouTube thumbnail', '16:9'),
    'instagram': ('Instagram cover', '9:16'),
    'post': ('Social post', '4:5'),
    'poster': ('Poster', '2:3'),
    'general': ('General image', '1:1'),
}
SIZES = {'16:9': (1280, 720), '9:16': (1080, 1920), '4:5': (1080, 1350),
         '1:1': (1080, 1080), '2:3': (1080, 1620), 'profile': (1080, 1080)}


def settings(values=None):
    data = dict(values or {})
    category = data.get('category', 'youtube')
    if category not in CATEGORIES:
        raise ValueError('Choose YouTube thumbnail, Instagram cover, Social post, Poster or General image.')
    aspect = data.get('aspect', 'auto')
    if aspect == 'auto': aspect = CATEGORIES[category][1]
    if aspect not in SIZES: raise ValueError('Choose one of the available image sizes.')
    count = data.get('count', 3)
    if type(count) is not int or not 1 <= count <= 4: raise ValueError('Choose between 1 and 4 image options.')
    text_mode = data.get('text_mode', 'none' if category == 'general' else 'auto')
    if text_mode not in ('auto', 'exact', 'none'): raise ValueError('Choose automatic, exact or no headline.')
    title = str(data.get('title', '')).strip()
    subtitle = str(data.get('subtitle', '')).strip()
    if len(title) > 160 or len(subtitle) > 260: raise ValueError('Keep the headline under 160 characters and supporting text under 260.')
    if text_mode == 'exact' and not title: raise ValueError('Enter your exact headline, or choose automatic / no headline.')
    accent = str(data.get('accent', '#ffd04a'))
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent): raise ValueError('Choose a valid accent colour.')
    seed = data.get('seed', 1700)
    if type(seed) is not int or not 0 <= seed <= 2147483643: raise ValueError('Use a whole-number seed from 0 to 2147483643.')
    layout=data.get('layout','auto')
    if layout not in ('auto','match','editorial','clean'):raise ValueError('Choose automatic, match poster, editorial or clean layout.')
    text_renderer=data.get('text_renderer','model')
    workflow=data.get('workflow','auto')
    if workflow not in ('auto','photo'):raise ValueError('Choose automatic or real-photo image creation.')
    if text_renderer not in ('model','typeset'):raise ValueError('Choose local model lettering or clean typesetting.')
    return dict(category=category, aspect=aspect, count=count, text_mode=text_mode, title=title, subtitle=subtitle,layout=layout,text_renderer=text_renderer,
                workflow=workflow, accent=accent, seed=seed, style=str(data.get('style', 'cinematic')),
                custom_style=str(data.get('custom_style', ''))[:2000], width=SIZES[aspect][0], height=SIZES[aspect][1])


def _font(text, size):
    paths = ('C:/Windows/Fonts/NirmalaB.ttf', 'C:/Windows/Fonts/Nirmala.ttf') if re.search(r'[\u0900-\u097f]', text) else ('C:/Windows/Fonts/impact.ttf','C:/Windows/Fonts/arialbd.ttf')
    for path in paths:
        if Path(path).is_file(): return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _lines(draw, text, font, width):
    lines = []
    for paragraph in text.splitlines():
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if line and draw.textlength(candidate, font=font) > width:
                lines.append(line); line = word
            else: line = candidate
        if line: lines.append(line)
    return lines


def text_block(canvas, text, top, width, max_height, size, color='white', center=False):
    draw = ImageDraw.Draw(canvas)
    for size in range(size, 11, -2):
        font = _font(text, size); lines = _lines(draw, text, font, width)
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=1) for line in lines]
        heights = [b[3] - b[1] for b in boxes]
        gap = max(5, int(size * .14))
        if all(b[2] - b[0] <= width for b in boxes) and sum(heights) + gap * max(0, len(lines)-1) <= max_height: break
    else: raise ValueError('The headline is too long for this size. Shorten it and try again.')
    left, y = top
    for line, box, height in zip(lines, boxes, heights):
        x = left + (width - (box[2] - box[0])) / 2 if center else left
        draw.text((x-box[0]+2, y-box[1]+4), line, font=font, fill='#03060a', stroke_width=2, stroke_fill='#03060a')
        draw.text((x-box[0], y-box[1]), line, font=font, fill=color, stroke_width=1, stroke_fill='#10151b')
        y += height + gap
    return y


def compose(canvas, hook, subtitle, portrait, config, index=0, group=False):
    canvas = canvas.convert('RGBA'); width, height = canvas.size
    margin = round(min(width, height) * .065)
    if portrait:
        with Image.open(portrait) as image: subject = image.convert('RGBA')
        if config['aspect'] == 'profile':
            subject = ImageOps.fit(subject, (width-2*margin, height-2*margin), centering=(.5, .4))
            canvas.alpha_composite(subject, (margin, margin))
        else:
            box = (round(width*(.90 if group else .52)), round(height*.66))
            subject.thumbnail(box, Image.Resampling.LANCZOS)
            canvas.alpha_composite(subject, ((width-subject.width)//2 if group else width-margin-subject.width, margin))
    if not hook and not subtitle: return canvas.convert('RGB')
    # Text is typeset after generation, preserving exact spelling and safe margins.
    shade = Image.new('RGBA', canvas.size)
    d = ImageDraw.Draw(shade)
    for y in range(height):
        opacity = round(225 * min(1, max(0, (y/height-.30)/.50)))
        d.line((0,y,width,y), fill=(5,10,18,opacity))
    canvas.alpha_composite(shade)
    match=config.get('layout')=='match'
    top = round(height * (.66 if match else .60 if width > height else .62))
    text_width = width-2*margin
    if width>height and not match and len(hook.split())>=3:
        words=hook.split();split=(len(words)+1)//2
        hook=' '.join(words[:split])+'\n'+' '.join(words[split:])
    title_height = height-margin-top-(round(height*.10) if subtitle else 0)
    end = text_block(canvas, hook, (margin,top), text_width, title_height, round(min(width,height)*(.21 if match else .18)), 'white',center=match or index%3==1) if hook else top
    if subtitle:
        badge=ImageDraw.Draw(canvas);badge_font=_font(subtitle,round(min(width,height)*.045));bounds=badge.textbbox((0,0),subtitle,font=badge_font)
        badge_width=bounds[2]-bounds[0]+30
        if badge_width<=text_width:
            left=(width-badge_width)//2 if match else margin;y=min(height-margin-(bounds[3]-bounds[1])-15,end+round(height*.025))
            badge.rounded_rectangle((left,y,left+badge_width,y+bounds[3]-bounds[1]+14),radius=4,fill=config['accent'])
            badge.text((left+15-bounds[0],y+7-bounds[1]),subtitle,font=badge_font,fill='#10151b')
        else:text_block(canvas,subtitle,(margin,end+round(height*.025)),text_width,height-margin-end-round(height*.025),round(min(width,height)*.045))
    return canvas.convert('RGB')


def report(folder, project):
    folder = Path(folder)
    with zipfile.ZipFile(folder/'all-images.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in project['files']:
            for file in (folder/name, (folder/name).with_suffix('.jpg')): bundle.write(file, file.name)
        bundle.write(folder/'thumbnail-project.json', 'thumbnail-project.json')
        for file in folder.glob('design-*/*'):
            if file.is_file() and file.suffix in ('.html','.png','.ttf'):bundle.write(file,file.relative_to(folder))
        if project.get('include_original_sources'):
            for key,source in project.get('sources',{}).items():
                file=Path(source['path'])
                if file.is_file() and file.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
                    bundle.write(file,'source-originals/'+re.sub(r'[^a-zA-Z0-9_-]','_',key)+file.suffix.lower())
    cards = []
    for i, name in enumerate(project['files'],1):
        title = html.escape(project['concepts'][i-1].get('hook','') or f'Image {i}')
        cards.append(f'<article><img src="{name}" alt="{title}"><div><b>Option {i}</b><span><a href="{name}" download>PNG</a><a href="{Path(name).with_suffix(".jpg")}" download>JPEG</a></span></div></article>')
    config = project['settings']; label = CATEGORIES[config['category']][0]
    source_lines=[]
    for key,source in project.get('sources',{}).items():
        name=html.escape(source.get('name',key));url=source.get('page','')
        detail=(f'<a href="{html.escape(url,quote=True)}">Source photograph</a>' if url.startswith(('https://','http://'))
                else html.escape(source.get('source','Saved local source')))
        source_lines.append(f'<p>{name}: {detail}</p>')
    page = folder/'report.html'
    page.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Thumbnail · Your images</title><style>body{margin:0;background:#101316;color:#edf1f4;font:15px system-ui}main{max-width:1100px;margin:40px auto;padding:0 24px}header{display:flex;align-items:center;justify-content:space-between;gap:20px}h1{font-size:26px;margin:0}p{color:#aeb8c0}a{color:#ffb47b;text-decoration:none}header a{border:1px solid #414a52;padding:10px 14px;border-radius:7px}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:24px;margin-top:24px}article{min-width:0}img{width:100%;max-height:680px;object-fit:contain;background:#080a0c;border:1px solid #30373e;border-radius:8px}article div{display:flex;justify-content:space-between;padding:12px 0}span a{margin-left:18px}details{margin-top:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#aeb8c0}</style><main>'
        f'<header><h1>{html.escape(label)}</h1><a href="all-images.zip" download>Download all</a></header><p>{len(project["files"])} image options · {config["width"]} × {config["height"]} · PNG + JPEG</p>'
        '<div class="images">'+''.join(cards)+'</div><p>Review names, facts and cropping before posting.</p><details><summary>Creation details & sources</summary><pre>'+html.escape(project.get('identity_note',''))+'</pre>'+''.join(source_lines)+'</details></main></html>', 'utf-8')
    return page
