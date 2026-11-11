"""Owner-authorized, clearly labelled screenshot previews; never original downloads."""
from PIL import Image
from .core import detect_tiles

def prepare(folder,tiles=None):
    (folder/'previews').mkdir(exist_ok=True);(folder/'crops').mkdir(exist_ok=True)
    with Image.open(folder/'screenshot.png') as opened:image=opened.convert('RGB')
    tiles=tiles or detect_tiles(image);rows=[]
    for tile in tiles:
        x,y,w,h=tile['box'];name=f'preview-{tile["id"]:03d}.png';crop=image.crop((x,y,x+w,y+h))
        crop.save(folder/'previews'/name);crop.save(folder/'crops'/f'{tile["id"]:03d}.png')
        rows.append({**tile,'caption':'','publisher':'','query':'','description':'','status':'preview',
            'origin':'screenshot-preview','preview_file':name,'preview_width':w,'preview_height':h,'width':w,'height':h})
    return rows
