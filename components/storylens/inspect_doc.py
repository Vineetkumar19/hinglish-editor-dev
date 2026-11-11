from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from PIL import Image
from PIL import ImageDraw

src = Path(r'E:\thisis.vineet\CC MANUAL PART 1.docx')
with ZipFile(src) as z:
    media = [n for n in z.namelist() if n.startswith('word/media/') and not n.endswith('/')]
    print('Media count:', len(media))
    for n in media:
        b = z.read(n)
        try:
            im = Image.open(BytesIO(b))
            dims = f'{im.width}x{im.height} {im.format}'
        except Exception as e:
            dims = f'unknown {e}'
        print(n, len(b), dims)
    for n in z.namelist():
        if n.endswith('.xml') and (b'Om Shinde' in z.read(n) or b'Rohit' in z.read(n)):
            print('XML mention:', n)
    out = Path('work/media')
    out.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for n in sorted(media, key=lambda x: int(Path(x).stem.replace('image', ''))):
        p = out / Path(n).name
        p.write_bytes(z.read(n))
        im = Image.open(p).convert('RGB')
        im.thumbnail((490, 300))
        tile = Image.new('RGB', (510, 330), 'white')
        tile.paste(im, ((510-im.width)//2, 20))
        ImageDraw.Draw(tile).text((8, 5), p.name, fill='black')
        thumbs.append(tile)
    sheet = Image.new('RGB', (510*4, 330*8), '#ddd')
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i%4)*510, (i//4)*330))
    sheet.save('work/contact.jpg', quality=85)
