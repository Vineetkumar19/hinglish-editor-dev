"""Free stock footage search (Pexels, Pixabay) with local caching of searches and downloads."""
from dataclasses import dataclass, field, asdict
import hashlib
import json
from pathlib import Path
import re
import time

import requests

SEARCH_CACHE_SECONDS = 24 * 3600   # Pixabay asks for search results to be cached for 24 h


@dataclass
class Candidate:
    source: str                 # library | pexels | pixabay
    id: str                     # unique across sources, e.g. pexels:12345
    title: str
    duration: float
    width: int
    height: int
    thumb: str = ''             # remote URL (stock) or local jpg (library)
    download_url: str = ''
    page_url: str = ''
    author: str = ''
    path: str = ''              # local file (library, or stock after download)
    offset: float = 0.0         # where the useful part starts inside the file
    query: str = ''
    score: float = 0.0

    def to_dict(self):
        return asdict(self)


def _orientation_ok(width, height, orientation):
    if orientation == 'portrait': return height > width
    if orientation == 'landscape': return width > height
    return True


def pick_file(files, target_w, target_h):
    """files: [(width, height, url)]. Smallest file that still covers the canvas, else the largest."""
    usable = [f for f in files if f[0] and f[1] and f[2]]
    if not usable:
        return None
    scale = lambda f: max(target_w / f[0], target_h / f[1])     # crop-to-fill scale factor
    covering = [f for f in usable if scale(f) <= 1.0]
    return min(covering, key=lambda f: f[0] * f[1]) if covering else max(usable, key=lambda f: f[0] * f[1])


class StockClient:
    name = ''

    def __init__(self, key, root, session=None):
        self.key = key
        self.cache = Path(root) / 'cache' / 'broll' / 'search'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()

    def _get(self, url, params, headers=None):
        spec = json.dumps({'source': self.name, 'url': url, 'params': params}, sort_keys=True)
        file = self.cache / (hashlib.sha256(spec.encode()).hexdigest() + '.json')
        if file.exists() and time.time() - file.stat().st_mtime < SEARCH_CACHE_SECONDS:
            return json.loads(file.read_text(encoding='utf-8'))
        for attempt in range(4):
            response = self.session.get(url, params=params, headers=headers or {}, timeout=30)
            if response.status_code == 429:
                time.sleep(float(response.headers.get('Retry-After', 0) or 0) or 5 * (attempt + 1))
                continue
            if response.status_code in (401, 403):
                raise PermissionError(f'{self.name.title()} rejected the API key. Check Settings → B-roll.')
            response.raise_for_status()
            data = response.json()
            file.write_text(json.dumps(data), encoding='utf-8')
            return data
        raise RuntimeError(f'{self.name.title()} is rate limiting searches; try again in a few minutes')


class PexelsClient(StockClient):
    name = 'pexels'

    def search(self, query, orientation, target_w, target_h, per_page=8):
        data = self._get('https://api.pexels.com/videos/search',
                         {'query': query, 'orientation': orientation, 'size': 'medium', 'per_page': per_page},
                         {'Authorization': self.key})
        results = []
        for v in data.get('videos', []):
            files = [(f.get('width'), f.get('height'), f.get('link')) for f in v.get('video_files', [])
                     if f.get('file_type') == 'video/mp4']
            chosen = pick_file(files, target_w, target_h)
            if not chosen or not _orientation_ok(v.get('width', 0), v.get('height', 0), orientation):
                continue
            results.append(Candidate('pexels', f"pexels:{v['id']}", query, float(v.get('duration') or 0),
                                     chosen[0], chosen[1], v.get('image', ''), chosen[2], v.get('url', ''),
                                     (v.get('user') or {}).get('name', ''), query=query))
        return results


class PixabayClient(StockClient):
    name = 'pixabay'

    def search(self, query, orientation, target_w, target_h, per_page=8):
        data = self._get('https://pixabay.com/api/videos/',
                         {'key': self.key, 'q': query[:100], 'per_page': max(3, per_page * 2),
                          'safesearch': 'true'})
        results = []
        for v in data.get('hits', []):
            sizes = v.get('videos') or {}
            files = [(s.get('width'), s.get('height'), s.get('url')) for s in sizes.values() if isinstance(s, dict)]
            chosen = pick_file(files, target_w, target_h)
            if not chosen or not _orientation_ok(chosen[0], chosen[1], orientation):
                continue
            thumb = (sizes.get('medium') or {}).get('thumbnail') or (sizes.get('small') or {}).get('thumbnail', '')
            results.append(Candidate('pixabay', f"pixabay:{v['id']}", v.get('tags', query), float(v.get('duration') or 0),
                                     chosen[0], chosen[1], thumb, chosen[2], v.get('pageURL', ''),
                                     v.get('user', ''), query=query))
            if len(results) >= per_page:
                break
        return results


def download(url, target, session=None, timeout=120):
    """Download once into the local cache; partial files are never left behind as complete."""
    target = Path(target)
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.partial')
    getter = session or requests
    try:
        with getter.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with partial.open('wb') as out:
                for block in response.iter_content(1024 * 1024):
                    out.write(block)
        partial.replace(target)
        return target
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def cached_name(candidate, kind='video'):
    """Filesystem-safe, unique name (library ids contain full paths)."""
    safe = re.sub(r'[^A-Za-z0-9_-]+', '-', candidate.id).strip('-')
    if len(safe) > 60:
        safe = safe[:24] + '-' + hashlib.sha1(candidate.id.encode()).hexdigest()[:16]
    if kind == 'thumb':
        return f'{safe}.jpg'
    return f'{safe}-{candidate.width}x{candidate.height}.mp4'
