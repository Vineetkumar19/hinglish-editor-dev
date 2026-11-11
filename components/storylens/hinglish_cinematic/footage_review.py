"""Portable, offline visual review of the committed footage bank."""
from collections import defaultdict
from fractions import Fraction
from html import escape
from pathlib import Path
from urllib.parse import quote
import json

from PIL import Image, ImageDraw, ImageFont


def source_range(asset):
    start = asset['start']
    duration = asset['duration']
    if {'in_pts', 'out_pts', 'timebase'} <= asset.keys():
        duration = float((asset['out_pts'] - asset['in_pts']) * Fraction(asset['timebase']))
    return f'{start:.3f}–{start + duration:.3f} s'


def write_review(output, manifest, stop=None):
    from hinglish_app.workbench_jobs import atomic_json, replace_retry

    folder = Path(output) / 'Best Clip' / 'Review'
    folder.mkdir(parents=True, exist_ok=True)
    by_orientation = defaultdict(list)
    for asset in manifest['assets']:
        by_orientation[asset.get('orientation', 'Unclassified')].append(asset)

    sheets = []
    cards = []
    font = ImageFont.load_default(size=15)
    for orientation, assets in sorted(by_orientation.items()):
        for offset in range(0, len(assets), 12):
            if stop is not None and stop.is_set():
                raise InterruptedError('Footage review stopped. Completed clips are kept.')
            page = offset // 12 + 1
            rows = assets[offset:offset + 12]
            canvas = Image.new('RGB', (1040, 48 + 198 * ((len(rows) + 3) // 4)), '#182032')
            draw = ImageDraw.Draw(canvas)
            draw.text((14, 15), f'{orientation} candidates   /   Page {page}', font=font, fill='white')
            for index, asset in enumerate(rows):
                x = 12 + 258 * (index % 4)
                y = 47 + 198 * (index // 4)
                draw.rectangle((x, y, x + 241, y + 183), fill='#101624')
                with Image.open(asset['poster']) as image:
                    image.thumbnail((240, 124))
                    canvas.paste(image, (x + (242 - image.width) // 2, y + (124 - image.height) // 2))
                draw.text((x + 6, y + 128), asset['id'], font=font, fill='white')
                draw.text((x + 6, y + 151), f"{source_range(asset)}   ·   {asset['score']:.3f}", font=font, fill='#d5dfed')
                clip = Path(asset['best_clip_path']).relative_to(folder.parent)
                link = '../' + quote(clip.as_posix(), safe='/')
                duplicate = asset.get('duplicate_group') or 'Unavailable for this scan'
                cards.append(
                    f'<article id="{escape(asset["id"], quote=True)}">'
                    f'<video controls preload="none" width="256" src="{link}"></video>'
                    f'<p>{escape(asset["id"])} · {escape(orientation)} · {source_range(asset)}'
                    f' · measured quality {asset["score"]:.3f}</p>'
                    f'<p>{escape(asset["source"])}<br>Duplicate group {escape(duplicate)}'
                    f' · {escape(asset["group"])} · {escape(asset.get("review_state", "unreviewed"))}</p></article>'
                )
            name = f'contact-{orientation.lower()}-{page:02d}.jpg'
            temporary = folder / f'.{name}.part'
            canvas.save(temporary, format='JPEG', quality=88)
            replace_retry(temporary, folder / name)
            sheets.append({'file':name, 'orientation':orientation, 'ids':[asset['id'] for asset in rows]})

    atomic_json(folder / 'candidate_manifest.json', {**manifest, 'contact_sheets':sheets})
    links = ''.join(
        f'<li><a href="{quote(sheet["file"])}">{escape(sheet["file"])}</a></li>'
        for sheet in sheets
    )
    html = folder / 'index.html'
    temporary = folder / '.index.html.part'
    temporary.write_text(
        '<!doctype html><meta charset="utf-8"><title>Best Clip review</title>'
        '<style>body{font:16px system-ui;margin:2rem;color:#172033}article{border-top:1px solid #aaa;'
        'margin-top:1.5rem;padding-top:1.5rem;overflow-wrap:anywhere}</style>'
        '<h1>Candidate review</h1><h2>Contact sheets</h2><ul>' + links + '</ul>'
        '<p><a href="candidate_manifest.json">Candidate manifest</a></p>'
        '<h2>Clips and source ranges</h2>' + ''.join(cards),
        encoding='utf-8',
    )
    replace_retry(temporary, html)
    return {'index':str(html), 'manifest':str(folder / 'candidate_manifest.json'), 'sheets':sheets}
