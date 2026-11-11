"""Contact sheets from actual Storylens browser captures."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

base=Path(__file__).resolve().parents[1]/'output/captions/script-pattern-validation/live-evidence'
rows=json.loads((base/'live-checks.json').read_text('utf-8'))
for script in sorted({r['script'] for r in rows}):
    cases=[r for r in rows if r['script']==script]
    sheet=Image.new('RGB',(840,190*len(cases)), '#242629')
    draw=ImageDraw.Draw(sheet)
    for y,row in enumerate(cases):
        for x,shot in enumerate(row['shots']):
            s=shot['stage'];im=Image.open(shot['path']).convert('RGB')
            im=im.crop((round(s['x']),round(s['y']),round(s['x']+s['width']),round(s['y']+s['height'])))
            # Show the caption zone at useful scale, with frame edges retained.
            im=im.crop((0,round(im.height*.38),im.width,round(im.height*.9)))
            im.thumbnail((270,150))
            sheet.paste(im,(x*280+(280-im.width)//2,y*190+25))
            draw.text((x*280+8,y*190+5),row['style']+' / '+str(round(shot['time'],2)),fill='white')
    sheet.save(base/(script+'-contact.jpg'),quality=90)
    print(script,len(cases))
