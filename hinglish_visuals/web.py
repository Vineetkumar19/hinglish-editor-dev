"""Internet sources that need no account or key: Wikidata (who/what is it + its official logo, portrait,
video, map), Wikipedia (lead image) and Wikimedia Commons (millions of free photos and archival videos).

All answers are cached locally; downloads go through the same cached downloader as B-roll."""
from dataclasses import dataclass, asdict, field
import hashlib
import html
import json
from pathlib import Path
import re
import time
from urllib.parse import quote, urlparse

import requests

WIKIDATA_API = 'https://www.wikidata.org/w/api.php'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
WIKIPEDIA_API = 'https://{lang}.wikipedia.org/w/api.php'
# Wikimedia asks every tool to identify itself (generic library user agents get blocked).
USER_AGENT = 'HinglishEditor/0.2 (local desktop video editor for creators; Smart Visuals) python-requests'
CACHE_SECONDS = 7 * 24 * 3600
IMAGE_WIDTH = 1600          # rendered width we ask Wikimedia for (SVG logos come back as PNG)
EXTMETA = 'Artist|LicenseShortName|LicenseUrl|ImageDescription|Categories|ObjectName|NonFree|Credit'


@dataclass
class Media:
    kind: str                   # image | video
    source: str                 # wikidata | commons | wikipedia | website | pexels | pixabay
    id: str                     # unique, e.g. commons:File:Gandhi_spinning.jpg
    title: str
    url: str                    # what to download (rendered PNG/JPG, or a transcoded video)
    thumb: str = ''             # small preview (remote URL; the report copies it locally)
    page_url: str = ''          # where a person can check the file and its licence
    width: int = 0
    height: int = 0
    duration: float = 0.0
    author: str = ''
    license: str = ''
    license_url: str = ''
    text: str = ''              # title + description + categories (used to prove what it shows)
    role: str = ''              # logo | portrait | video | map | photo | lead
    official: bool = False      # linked from the entity's own Wikidata item / Wikipedia article
    nonfree: bool = False       # Wikipedia "non-free" file (logos shown for identification)
    score: float = 0.0
    path: str = ''              # local file after download
    offset: float = 0.0         # where the useful part of a video starts

    def to_dict(self):
        return asdict(self)


@dataclass
class Entity:
    """A real person / brand / place / event / thing identified on Wikidata."""
    key: str
    name: str
    kind: str
    qid: str = ''
    label: str = ''
    description: str = ''
    aliases: list = field(default_factory=list)
    wiki_title: str = ''
    commons_category: str = ''
    website: str = ''
    files: dict = field(default_factory=dict)      # role -> [Commons file names]

    def names(self):
        """Every way the entity may be written in a file title, description or category."""
        found = [self.name, self.label, self.wiki_title, self.commons_category] + list(self.aliases)
        seen, out = set(), []
        for n in found:
            n = re.sub(r'\s*\(.*?\)\s*', ' ', str(n or '')).strip()
            if len(n) >= 3 and n.casefold() not in seen:
                seen.add(n.casefold()); out.append(n)
        return out

    def to_dict(self):
        return asdict(self)


def plain(text, limit=400):
    """HTML from Commons metadata -> short plain text."""
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))
    return re.sub(r'\s+', ' ', text).strip()[:limit]


def _value(claim):
    snak = (claim or {}).get('mainsnak') or {}
    if snak.get('snaktype') != 'value':
        return None
    return (snak.get('datavalue') or {}).get('value')


def claim_values(entity, prop):
    """Values of a Wikidata property, preferred rank first, deprecated ones dropped."""
    claims = [c for c in (entity.get('claims') or {}).get(prop, []) if c.get('rank') != 'deprecated']
    claims.sort(key=lambda c: c.get('rank') != 'preferred')
    values = [_value(c) for c in claims]
    return [v.get('id') if isinstance(v, dict) and 'id' in v else v for v in values if v]


class Web:
    def __init__(self, root, language='en', session=None):
        self.language = language
        self.cache = Path(root) / 'cache' / 'visuals' / 'web'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT

    # ---- plumbing ----
    def get(self, url, params):
        params = {**params, 'format': 'json'}
        spec = json.dumps({'url': url, 'params': params}, sort_keys=True)
        file = self.cache / (hashlib.sha256(spec.encode()).hexdigest() + '.json')
        if file.exists() and time.time() - file.stat().st_mtime < CACHE_SECONDS:
            return json.loads(file.read_text(encoding='utf-8'))
        for attempt in range(4):
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code in (429, 503):
                time.sleep(float(response.headers.get('Retry-After', 0) or 0) or 3 * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            if 'error' in data:
                raise RuntimeError(f"{urlparse(url).netloc}: {data['error'].get('info', 'error')}")
            file.write_text(json.dumps(data), encoding='utf-8')
            return data
        raise RuntimeError(f'{urlparse(url).netloc} is busy; try again in a few minutes')

    @property
    def wikipedia(self):
        return WIKIPEDIA_API.format(lang=self.language)

    # ---- Wikidata ----
    def search_entities(self, name, limit=6):
        data = self.get(WIKIDATA_API, {'action': 'wbsearchentities', 'search': name[:100], 'language': self.language,
                                       'uselang': self.language, 'type': 'item', 'limit': limit})
        return [{'id': r['id'], 'label': r.get('label', ''), 'description': r.get('description', '')}
                for r in data.get('search', []) if r.get('id')]

    def entity(self, key, name, kind, qid):
        """Everything useful about one Wikidata item: names, article, and its own media files."""
        data = self.get(WIKIDATA_API, {'action': 'wbgetentities', 'ids': qid, 'languages': self.language,
                                       'props': 'labels|descriptions|aliases|claims|sitelinks',
                                       'sitefilter': f'{self.language}wiki'})
        item = (data.get('entities') or {}).get(qid) or {}
        lang = self.language
        files = {}
        for role, prop in (('logo', 'P154'), ('portrait', 'P18'), ('video', 'P10'), ('map', 'P242')):
            names = [v for v in claim_values(item, prop) if isinstance(v, str)]
            if names:
                files[role] = names[:4]
        websites = [v for v in claim_values(item, 'P856') if isinstance(v, str)]
        categories = [v for v in claim_values(item, 'P373') if isinstance(v, str)]
        return Entity(key, name, kind, qid,
                      ((item.get('labels') or {}).get(lang) or {}).get('value', name),
                      ((item.get('descriptions') or {}).get(lang) or {}).get('value', ''),
                      [a.get('value', '') for a in (item.get('aliases') or {}).get(lang, [])][:12],
                      ((item.get('sitelinks') or {}).get(f'{lang}wiki') or {}).get('title', ''),
                      categories[0] if categories else '', websites[0] if websites else '', files)

    # ---- Commons / Wikipedia files ----
    def _media(self, page, source, api_host):
        infos = page.get('videoinfo') or page.get('imageinfo') or []
        if page.get('missing') or not infos:
            return None
        info = infos[0]
        meta = {k: (v or {}).get('value', '') for k, v in (info.get('extmetadata') or {}).items()}
        mediatype = (info.get('mediatype') or '').upper()
        mime = info.get('mime') or ''
        kind = 'video' if mediatype == 'VIDEO' or mime.startswith('video/') or mime == 'application/ogg' else \
            'image' if mediatype in ('BITMAP', 'DRAWING') or mime.startswith('image/') else None
        if kind is None:
            return None
        title = page.get('title', '')
        name = title.split(':', 1)[-1]
        width, height = int(info.get('width') or 0), int(info.get('height') or 0)
        if kind == 'image':
            url = info.get('thumburl') or info.get('url', '')
            thumb = url
        else:
            url, width, height = pick_derivative(info.get('derivatives') or [], info.get('url', ''), width, height,
                                                 int(info.get('size') or 0))
            thumb = video_poster(info.get('url', ''), api_host)
        if not url:
            return None
        text = ' '.join([re.sub(r'\.[A-Za-z0-9]{2,5}$', '', name).replace('_', ' '), plain(meta.get('ObjectName')),
                         plain(meta.get('ImageDescription')), meta.get('Categories', '').replace('|', ' | ')])
        return Media(kind, source, f'{source}:{title}', re.sub(r'\.[A-Za-z0-9]{2,5}$', '', name).replace('_', ' '),
                     url, thumb, info.get('descriptionurl', ''), width, height, float(info.get('duration') or 0),
                     plain(meta.get('Artist'), 120), plain(meta.get('LicenseShortName'), 60),
                     meta.get('LicenseUrl', ''), text[:1500], nonfree=str(meta.get('NonFree', '')).lower() == 'true')

    def files(self, names, api=COMMONS_API, source='commons'):
        """Media for Commons/Wikipedia file names (with or without the File: prefix), in the given order."""
        titles = [n if n.lower().startswith(('file:', 'image:')) else 'File:' + n for n in names]
        found = {}
        for i in range(0, len(titles), 40):
            chunk = titles[i:i + 40]
            params = {'action': 'query', 'formatversion': 2, 'titles': '|'.join(chunk), 'redirects': 1,
                      'prop': 'imageinfo', 'iiprop': 'url|size|mime|mediatype|extmetadata',
                      'iiurlwidth': IMAGE_WIDTH, 'iiextmetadatafilter': EXTMETA,
                      'iiextmetadatalanguage': self.language}
            if api == COMMONS_API:   # TimedMediaHandler: transcoded, smaller copies of videos
                params = {k.replace('ii', 'vi', 1) if k.startswith('ii') else k: v for k, v in params.items()}
                params.update(prop='videoinfo', viprop='url|size|mime|mediatype|extmetadata|derivatives')
            data = self.get(api, params)
            query = data.get('query') or {}
            rename = {n.get('to'): n.get('from') for n in query.get('normalized', []) + query.get('redirects', [])}
            for page in query.get('pages', []):
                media = self._media(page, source, urlparse(api).netloc)
                if media:
                    found[rename.get(page.get('title'), page.get('title'))] = media
                    found[page.get('title')] = media
        return [found[t] for t in titles if t in found]

    def commons_search(self, query, filetype='bitmap', limit=20):
        """Commons full-text search (titles, descriptions and categories) for one kind of file."""
        search = f'{query} filetype:{filetype}' if filetype else query
        data = self.get(COMMONS_API, {'action': 'query', 'formatversion': 2, 'generator': 'search',
                                      'gsrsearch': search[:250], 'gsrnamespace': 6, 'gsrlimit': limit,
                                      'prop': 'videoinfo', 'viprop': 'url|size|mime|mediatype|extmetadata|derivatives',
                                      'viurlwidth': IMAGE_WIDTH, 'viextmetadatafilter': EXTMETA,
                                      'viextmetadatalanguage': self.language})
        pages = sorted((data.get('query') or {}).get('pages', []), key=lambda p: p.get('index', 0))
        return [m for m in (self._media(p, 'commons', 'commons.wikimedia.org') for p in pages) if m]

    def lead_image(self, title):
        """The main image of a Wikipedia article (for brands usually the logo, even when it is non-free)."""
        if not title:
            return None
        data = self.get(self.wikipedia, {'action': 'query', 'formatversion': 2, 'titles': title, 'redirects': 1,
                                         'prop': 'pageimages', 'piprop': 'name'})
        pages = (data.get('query') or {}).get('pages', [])
        name = pages[0].get('pageimage') if pages else None
        if not name:
            return None
        found = self.files([name], api=self.wikipedia, source='wikipedia')
        return found[0] if found else None

    def site_icon(self, website):
        """Last resort for an app/company logo: the high-resolution icon its own website publishes."""
        host = urlparse(website if '://' in website else 'https://' + website).netloc
        if not host:
            return None
        url = f'https://www.google.com/s2/favicons?domain={quote(host)}&sz=256'
        return Media('image', 'website', f'website:{host}', host, url, url, f'https://{host}', 256, 256,
                     text=host, role='logo', official=True)


def pick_derivative(derivatives, original, width, height, size, want=720, max_original=400_000_000):
    """Smallest transcoded copy at least `want` pixels tall (or the biggest below that). Original only
    when Commons has no transcode and the file is not huge."""
    usable = []
    for d in derivatives:
        kind = (d.get('type') or '').lower()
        if not d.get('src') or not d.get('height') or 'audio' in kind or not kind.startswith(('video/', 'application/ogg')):
            continue
        usable.append((int(d.get('width') or 0), int(d['height']), d['src'], 'webm' in kind))
    if usable:
        tall = [u for u in usable if u[1] >= min(want, height or want)]
        if tall:
            best = min(tall, key=lambda u: (u[1], not u[3]))
        else:
            best = max(usable, key=lambda u: (u[1], u[3]))
        return best[2], best[0], best[1]
    if original and (not size or size <= max_original):
        return original, width, height
    return '', width, height


def video_poster(url, host):
    """Commons serves a still of any video at .../thumb/<path>/<width>px--<name>.jpg."""
    match = re.match(r'(https://upload\.wikimedia\.org/wikipedia/[^/]+)/(\w/\w\w)/([^/]+)$', url or '')
    if not match:
        return ''
    return f'{match.group(1)}/thumb/{match.group(2)}/{match.group(3)}/480px--{match.group(3)}.jpg'
