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
    kind: str = 'video'
    license: str = ''
    license_url: str = ''
    extraction: bool = False  # page URL requires the bounded web-video downloader
    specific: float | None = None
    verified_description: str = ''

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
        from .recovery import read_json, retry, write_json
        rejected=self.cache/('rejected-'+self.name+'-'+hashlib.sha256(self.key.encode()).hexdigest()[:20]+'.json')
        if rejected.is_file():
            raise PermissionError(f'{self.name.title()} rejected the saved API key. Update it in B-roll settings; other sources can still run.')
        spec = json.dumps({'source': self.name, 'url': url, 'params': params}, sort_keys=True)
        file = self.cache / (hashlib.sha256(spec.encode()).hexdigest() + '.json')
        if file.exists() and time.time() - file.stat().st_mtime < SEARCH_CACHE_SECONDS:
            cached=read_json(file)
            if cached is not None:return cached
        def request():
            response = self.session.get(url, params=params, headers=headers or {}, timeout=30)
            if response.status_code in (401, 403):
                write_json(rejected,{'source':self.name,'rejected_at':time.time()})
                raise PermissionError(f'{self.name.title()} rejected the API key. Re-copy it into B-roll settings.')
            response.raise_for_status()
            data = response.json()
            write_json(file,data)
            return data
        return retry(request,lambda message:None,self.name.title()+' search')


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
        from .internet import stock_keyword
        broad=stock_keyword(query)
        queries=[query,broad] if broad and broad.casefold()!=query.casefold() else [query]
        if broad=='cafe' and 'coffee shop' not in queries:
            queries.append('coffee shop')
        groups=[];seen=set()
        for term in queries:
            params={'key':self.key,'q':term[:100],'per_page':max(3,per_page*2),
                    'safesearch':'true','video_type':'film'}
            # A cafe request needs venue/customer footage as well as isolated
            # coffee cups. Pixabay's people category is a useful broad backup.
            if term==broad and broad=='cafe':params['category']='people'
            data=self._get('https://pixabay.com/api/videos/',params)
            limit=per_page
            batch=[]
            for hit in data.get('hits',[]):
                if hit.get('id') in seen or hit.get('type','film')!='film':continue
                batch.append(hit);seen.add(hit.get('id'))
                if len(batch)>=limit:break
            groups.append(batch)
        hits=[group[i] for i in range(per_page) for group in groups if i<len(group)]
        results = []
        for v in hits:
            if v.get('type','film')!='film':
                continue
            sizes = v.get('videos') or {}
            files = [(s.get('width'), s.get('height'), s.get('url')) for s in sizes.values() if isinstance(s, dict)]
            chosen = pick_file(files, target_w, target_h)
            # Pixabay has few vertical videos and no orientation filter: keep wide clips too; they are
            # centre-cropped for 9:16 and ranked slightly lower than true vertical footage.
            if not chosen:
                continue
            thumb = (sizes.get('medium') or {}).get('thumbnail') or (sizes.get('small') or {}).get('thumbnail', '')
            results.append(Candidate('pixabay', f"pixabay:{v['id']}", v.get('tags', query), float(v.get('duration') or 0),
                                     chosen[0], chosen[1], thumb, chosen[2], v.get('pageURL', ''),
                                     v.get('user', ''), query=query))
            if len(results) >= per_page:
                break
        return results


def download(url, target, session=None, timeout=120, max_bytes=1_500_000_000):
    """Download once into the local cache; partial files are never left behind as complete.
    Stops at `max_bytes` so a wrong link can never fill the disk."""
    target = Path(target)
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.partial')
    getter = session or requests
    try:
        with getter.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            if int(response.headers.get('Content-Length') or 0) > max_bytes:
                raise ValueError('the file is too large to download')
            written = 0
            with partial.open('wb') as out:
                for block in response.iter_content(1024 * 1024):
                    written += len(block)
                    if written > max_bytes:
                        raise ValueError('the file is too large to download')
                    out.write(block)
            expected=int(response.headers.get('Content-Length') or 0)
            if not written or expected and written!=expected:
                raise requests.ConnectionError('The video transfer stopped early')
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
    if candidate.kind == 'image':
        return f'{safe}.jpg'
    return f'{safe}-{candidate.width}x{candidate.height}.mp4'
