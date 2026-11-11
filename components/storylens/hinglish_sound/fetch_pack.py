"""Extend the sound library with a free professional pack from Mixkit.

Mixkit Sound Effects Free License (https://mixkit.co/license/#sfxFree): free to use in commercial and
personal video projects, no attribution required; the files may not be redistributed as a sound
library of their own. Files are saved per effect family with a .json sidecar (name, tags, source).
"""
import json
from pathlib import Path
import re
import time

import requests

# Mixkit tag page -> our effect family
FAMILIES = {
    'whoosh': ['whoosh', 'woosh', 'swoosh', 'transition', 'swipe', 'slide'],
    'impact': ['cinematic', 'trailer', 'impact', 'hit', 'boom', 'punch', 'bass'],
    'riser': ['riser', 'swell'],
    'poke': ['pop', 'click', 'notification', 'bubble', 'interface', 'ui', 'typing', 'keyboard', 'camera',
             'tick', 'alert', 'message', 'money'],
    'cute': ['chime', 'ding', 'bell', 'magic', 'sparkle'],
    'retro': ['game', 'arcade', 'coin', 'win', 'achievement', 'success'],
    'awkward': ['fail', 'lose', 'wrong', 'error', 'scratch', 'cartoon'],
    'suspense': ['heartbeat', 'clock', 'tension', 'suspense'],
    'glitch': ['glitch'],
}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Hinglish Editor sound pack)'}
LICENSE = 'Mixkit Sound Effects Free License (free for commercial videos, no attribution; do not redistribute as a library)'


def fetch(target, progress=print):
    target = Path(target)
    session = requests.Session()
    seen = {}                                   # sound id -> (family, title, tags)
    for family, tags in FAMILIES.items():
        for tag in tags:
            html = session.get(f'https://mixkit.co/free-sound-effects/{tag}/', headers=HEADERS, timeout=30).text
            ids = re.findall(r'sfx/(\d+)/\d+-preview\.mp3', html)
            titles = [t.strip() for t in re.findall(r'item-grid-card__title">\s*([^<]+?)\s*<', html)]
            for sid, title in zip(dict.fromkeys(ids), titles):
                if sid in seen:
                    seen[sid][2].append(tag)
                else:
                    seen[sid] = [family, title, [tag]]
            time.sleep(.3)
    progress(f'  {len(seen)} professional sounds found')
    saved = 0
    for n, (sid, (family, title, tags)) in enumerate(seen.items(), 1):
        slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')[:50] or 'sound'
        file = target / family / f'{slug}_mixkit{sid}.mp3'
        meta = {'name': title, 'tags': tags + title.lower().split(), 'category': family, 'source': 'mixkit',
                'source_url': f'https://mixkit.co/free-sound-effects/{tags[0]}/', 'licence': LICENSE}
        if not file.exists():
            file.parent.mkdir(parents=True, exist_ok=True)
            audio = session.get(f'https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}-preview.mp3',
                                headers=HEADERS, timeout=60)
            if audio.status_code != 200 or len(audio.content) < 1000:
                continue
            file.write_bytes(audio.content)
            time.sleep(.1)
        Path(str(file) + '.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
        saved += 1
        if n % 100 == 0:
            progress(f'  Downloaded {n}/{len(seen)}')
    return saved


if __name__ == '__main__':
    import sys
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    print(fetch(root / 'library' / 'sfx-pro'), 'sounds ready in', root / 'library' / 'sfx-pro')
