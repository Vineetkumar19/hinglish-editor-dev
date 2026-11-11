"""Small, attributed starter pack from original public download pages. Never mirrors a catalogue."""
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urljoin
import requests

ROOT = Path(__file__).resolve().parents[1]


def save(session, url, path, metadata):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        r = session.get(url, timeout=60); r.raise_for_status()
        if not 1000 < len(r.content) < 35_000_000 or 'text/html' in r.headers.get('Content-Type', ''):
            raise ValueError('Not a bounded audio download')
        tmp = path.with_suffix('.partial'); tmp.write_bytes(r.content)
        from hinglish_sound.library import decode
        if decode(tmp, rate=8000, limit=1).shape[1] == 0:
            tmp.unlink(); raise ValueError('Empty audio')
        tmp.replace(path)
    metadata['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(str(path) + '.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return str(path.relative_to(ROOT))


def run():
    session = requests.Session()
    session.headers['User-Agent'] = 'Storylens personal sound library'
    receipts, errors = [], []
    album = 'https://chriszabriskie.com/cylinders/'
    page = session.get(album, timeout=30); page.raise_for_status()
    use = session.get('https://chriszabriskie.com/use/', timeout=30); use.raise_for_status()
    license_url = next(iter(re.findall(r'https?://creativecommons.org/licenses/by/[0-9.]+/', use.text)), None)
    if not license_url:
        errors.append('Chris Zabriskie licence link not found; no music downloaded')
    else:
        urls = list(dict.fromkeys(re.findall(r'[\"\']([^\"\']+\.mp3(?:\?[^\"\']*)?)[\"\']', page.text)))
        if not urls:
            player = session.get('https://chriszabriskie.com/assets/player.js', timeout=30)
            player.raise_for_status()
            base = re.search(r'AUDIO_BASE\s*=\s*"(https://[^"]+)"', player.text)
            if base and '${slug}-${String(i + 1).padStart(2, "0")}.m4a' in player.text:
                urls = [f'{base[1]}/cylinders/cylinders-{i:02d}.m4a' for i in range(1,5)]
        for raw in urls[:4]:
            url = urljoin(album, html.unescape(raw)); name = Path(url.split('?')[0]).stem
            name = {f'cylinders-{i:02d}': f'Cylinder {word}' for i, word in
                    enumerate(('One', 'Two', 'Three', 'Four'), 1)}.get(name, name)
            try:
                receipts.append(save(session, url, ROOT/'library/music/general'/Path(url).name,
                    dict(name=name, tags=['instrumental', 'ambient', 'documentary', 'Chris Zabriskie'],
                         author='Chris Zabriskie', source_url=album, license=license_url,
                         attribution=f'{name} by Chris Zabriskie ({album}), licensed under {license_url}.',
                         category_note='Unclassified; CLAP and measured energy determine suitability.')))
            except Exception as e: errors.append(f'{name}: {type(e).__name__}')
    for tag, category in [('ambience', 'ambience'), ('footsteps', 'foley'), ('door', 'foley')]:
        url = f'https://mixkit.co/free-sound-effects/{tag}/'
        page = session.get(url, timeout=30); page.raise_for_status()
        # Parse each card independently, avoiding name/id mismatches across cards.
        cards = re.split(r'<h2\b', page.text)[1:]
        added = 0
        for card in cards:
            sid = re.search(r'sfx/(\d+)/\d+-preview\.mp3', card)
            title = re.search(r'^[^>]*>(.*?)</h2>', card, re.S)
            if not sid or not title: continue
            name = html.unescape(re.sub('<[^>]+>', '', title[1])).strip()
            sid = sid[1]
            try:
                receipts.append(save(session, f'https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}-preview.mp3',
                    ROOT/'library/sound-online'/category/f'mixkit-{sid}.mp3',
                    dict(name=name, tags=[tag,category], provider='Mixkit', source_url=url,
                         license='https://mixkit.co/license/#sfxFree', category=category,
                         notice='Use in video projects; do not redistribute as a standalone sound library.')))
                added += 1
                if added >= 4: break
            except Exception as e: errors.append(f'Mixkit {sid}: {type(e).__name__}')
    receipt = ROOT/'output/sound-research/library-import.json'
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps({'files':receipts,'errors':errors},indent=2),encoding='utf-8')
    print(json.dumps({'downloaded_or_verified':len(receipts),'files':receipts,'errors':errors}))


if __name__ == '__main__':
    run()
