"""Saved reference guidance and readable, image-led thumbnail compositions."""
import json
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageChops,ImageEnhance


def style_for(root,topic):
    candidates=[]
    for file in sorted((Path(root)/'library/thumbnail-styles').glob('*/style.json')):
        card=json.loads(file.read_text(encoding='utf-8'))
        if not card.get('match_all') or not all(word.casefold() in topic.casefold() for word in card['match_all']):
            continue
        candidates.append((file,card))
    # A target-team/title recipe must win over a shorter reference-team mention
    # such as "Mumbai UNDER RATED in the KKR look".
    candidates.sort(key=lambda row:(len(row[1]['match_all']),sum(len(word) for word in row[1]['match_all'])),reverse=True)
    for file,card in candidates:
        card['_folder']=file.parent
        for key in ('portrait','subjects'):
            if card.get(key):
                image=(file.parent/card[key]).resolve()
                if not image.is_relative_to(file.parent.resolve()) or not image.is_file():
                    raise ValueError('The saved thumbnail reference picture is unavailable.')
                card[key]=str(image)
        for source in card.get('photography',{}).values():
            image=(file.parent/source['path']).resolve()
            if not image.is_relative_to(file.parent.resolve()) or not image.is_file():
                raise ValueError('The saved source photo is unavailable. Restore the reference photograph and retry.')
            source['path']=str(image)
        return card
    return {}


def _font(size):
    for path in ('C:/Windows/Fonts/impact.ttf','C:/Windows/Fonts/arialbd.ttf'):
        if Path(path).is_file():return ImageFont.truetype(path,size)
    return ImageFont.load_default(size=size)


def _text(canvas,lines,xy,width,size=105,accent='#ffd04a',center=False):
    draw=ImageDraw.Draw(canvas)
    font=_font(size)
    while max(draw.textbbox((0,0),line,font=font)[2] for line in lines)>width and font.size>24:
        font=_font(font.size-2)
    x,y=xy
    for i,line in enumerate(lines):
        left=x+(width-draw.textlength(line,font=font))/2 if center else x
        draw.text((left,y),line,font=font,fill='white' if i==0 else accent,
                  stroke_width=3,stroke_fill='#06152c')
        y+=font.size+10


def _subject(canvas,path,box,glow='#3fbbff'):
    with Image.open(path) as image:person=image.convert('RGBA')
    person.thumbnail(box[2:],Image.Resampling.LANCZOS)
    fade=Image.new('L',person.size,255);draw=ImageDraw.Draw(fade)
    span=max(2,round(person.height*.075))
    for y in range(person.height-span,person.height):
        draw.line((0,y,person.width,y),fill=round(255*(person.height-1-y)/span))
    person.putalpha(ImageChops.multiply(person.getchannel('A'),fade))
    x=box[0]+(box[2]-person.width)//2;y=box[1]+box[3]-person.height
    light=Image.new('RGBA',canvas.size)
    color=Image.new('RGBA',person.size,glow);color.putalpha(person.getchannel('A'))
    light.alpha_composite(color,(x,y));light=light.filter(ImageFilter.GaussianBlur(13))
    canvas.alpha_composite(light);canvas.alpha_composite(person,(x,y))


def compose(canvas,hook,index,niche,portrait=None,style=None):
    style=style or {};canvas=ImageEnhance.Color(canvas.convert('RGB')).enhance(1.18).convert('RGBA')
    accent=style.get('accent','#ffcf4a' if niche=='cricket' else '#64e8ff')
    # Keep photographic detail visible; shade only the text areas.
    shade=Image.new('RGBA',canvas.size);draw=ImageDraw.Draw(shade)
    for y in range(720):
        alpha=round(225*max(0,(y-440)/280))
        draw.line((0,y,1280,y),fill=(3,11,28,alpha))
    canvas.alpha_composite(shade)
    portrait=portrait or style.get('portrait')
    subjects=style.get('subjects')
    if style and index==0 and subjects:
        _subject(canvas,subjects,(20,40,1240,545))
        shade=Image.new('RGBA',canvas.size);ImageDraw.Draw(shade).rectangle((0,565,1280,720),fill=(3,12,28,225))
        canvas.alpha_composite(shade)
        _text(canvas,[hook],(45,560),1190,140,accent,center=True)
    else:
        # Side lighting and a dark reading panel for the split layouts.
        panel=Image.new('RGBA',canvas.size);draw=ImageDraw.Draw(panel)
        for x in range(950):
            draw.line((x,0,x,720),fill=(3,12,28,round(210*max(0,1-x/950))))
        canvas.alpha_composite(panel)
        if portrait:_subject(canvas,portrait,(610 if index==1 else 640,30,670 if index==1 else 640,690))
        words=hook.split();split=(len(words)+1)//2
        lines=[' '.join(words[:split]),' '.join(words[split:])]
        if style and index==2:
            ghost=Image.new('RGBA',canvas.size)
            ImageDraw.Draw(ghost).text((20,70),'2020',font=_font(260),fill=(255,208,74,65))
            canvas.alpha_composite(ghost)
        _text(canvas,[line for line in lines if line],(45,245 if index==1 else 360),660,120,accent)
    label=style.get('label',niche.upper()+' / THE STORY')
    draw=ImageDraw.Draw(canvas)
    label_font=_font(27);bounds=draw.textbbox((0,0),label,font=label_font)
    draw.rounded_rectangle((38,25,58+bounds[2],75),radius=8,fill=(4,20,42,225),outline=accent,width=2)
    draw.text((48,30),label,font=label_font,fill=accent)
    return canvas.convert('RGB')
