"""The web agent's hands: search the whole internet like a person would, then download.

Images: "Zomato logo png", "Mahatma Gandhi photo", "Meenakshi Amman Temple" through web image search
(DuckDuckGo / Bing / Yahoo via the `ddgs` package, no key). Videos: web video search plus YouTube search,
downloaded with yt-dlp (YouTube and 1000+ sites), only the part that is needed. Every file still has to
name the person/brand/place in its title or address, then CLIP and the AI judge pick the best one."""
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

import requests

from .web import Media

CACHE_SECONDS = 3 * 24 * 3600
BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
           'Chrome/128.0 Safari/537.36')
WEB_LICENSE = 'from the web: check you may use it'
# Stock-photo sites put watermarks on search previews; the real file is paid.
WATERMARKED = ('shutterstock', 'alamy', 'gettyimages', 'istockphoto', 'dreamstime', '123rf', 'depositphotos',
               'stock.adobe', 'adobestock', 'bigstockphoto', 'vectorstock', 'freepik', 'agefotostock',
               'pond5', 'storyblocks', 'videoblocks', 'artlist', 'envato', 'canstockphoto')
SECTION = 50.0          # seconds of a long web video to download around the useful part


def domain(url):
    host = urlparse(url or '').netloc.lower()
    return host[4:] if host.startswith('www.') else host


def watermarked(*urls):
    return any(w in (u or '').lower() for u in urls for w in WATERMARKED)


def _words_from_url(url):
    path = urlparse(url or '').path
    return re.sub(r'[\W_]+', ' ', re.sub(r'\.[a-z0-9]{2,4}$', '', path, flags=re.I))


def parse_duration(value):
    """'4:13', '1:02:03', 'PT4M13S' or seconds -> seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or '').strip()
    iso = re.fullmatch(r'P?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', text, re.I)
    if iso and any(iso.groups()):
        h, m, s = (int(g or 0) for g in iso.groups())
        return float(h * 3600 + m * 60 + s)
    parts = [p for p in text.split(':') if p.isdigit()]
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return float(total)


class WebSearch:
    def __init__(self, root, progress=print, ddgs=None, youtube=None):
        self.root = Path(root)
        self.cache = self.root / 'cache' / 'visuals' / 'websearch'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.progress = progress
        self._ddgs, self._youtube = ddgs, youtube
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': BROWSER, 'Accept': 'image/avif,image/webp,image/png,image/*,*/*;q=0.8'})

    # ---- searching ----
    def _cached(self, kind, spec, call):
        file = self.cache / (hashlib.sha256(json.dumps([kind, spec], sort_keys=True).encode()).hexdigest() + '.json')
        if file.exists() and time.time() - file.stat().st_mtime < CACHE_SECONDS:
            return json.loads(file.read_text(encoding='utf-8'))
        data = call()
        file.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return data

    def ddgs(self):
        if self._ddgs is None:
            from ddgs import DDGS
            self._ddgs = DDGS(timeout=20)
        return self._ddgs

    def images(self, query, limit=30, transparent=False):
        """Web image search -> Media (largest real image; the address and title are its evidence)."""
        options = {'max_results': limit, 'safesearch': 'moderate', 'region': 'in-en'}
        if transparent:
            options['type_image'] = 'transparent'
        raw = self._cached('images', [query, options], lambda: list(self.ddgs().images(query, **options)))
        found = []
        for r in raw:
            image, page = r.get('image') or '', r.get('url') or ''
            if not image.startswith('http') or watermarked(image, page):
                continue
            try:
                width, height = int(float(r.get('width') or 0)), int(float(r.get('height') or 0))
            except ValueError:
                width = height = 0
            title = re.sub(r'\s+', ' ', str(r.get('title') or '')).strip()
            text = f'{title} {_words_from_url(image)} {_words_from_url(page)}'
            found.append(Media('image', 'web', 'web:' + hashlib.sha1(image.encode()).hexdigest()[:16],
                               title or domain(page), image, r.get('thumbnail') or image, page, width, height,
                               author=r.get('source') or domain(page), license=WEB_LICENSE, text=text[:800],
                               role='web'))
        return found

    def videos(self, query, limit=12):
        """Web video search + YouTube search -> Media whose url is the video page (yt-dlp downloads it)."""
        found = []
        try:
            raw = self._cached('videos', [query, limit], lambda: list(self.ddgs().videos(
                query, max_results=limit, safesearch='moderate', region='in-en')))
        except Exception as error:
            self.progress(f'    Web video search skipped: {error}')
            raw = []
        for r in raw:
            page = r.get('content') or r.get('embed_url') or ''
            if not page.startswith('http') or watermarked(page):
                continue
            images = r.get('images') or {}
            found.append(self._video(page, r.get('title', ''), r.get('description', ''),
                                     parse_duration(r.get('duration')), r.get('publisher') or r.get('uploader') or '',
                                     images.get('large') or images.get('medium') or images.get('small') or ''))
        try:
            entries = self._cached('youtube', [query, limit], lambda: self.youtube_search(query, limit))
        except Exception as error:
            self.progress(f'    YouTube search skipped: {error}')
            entries = []
        for e in entries:
            found.append(self._video(e['url'], e.get('title', ''), e.get('description', ''),
                                     float(e.get('duration') or 0), e.get('channel', ''), e.get('thumb', '')))
        unique = {}
        for m in found:
            unique.setdefault(m.id, m)
        return list(unique.values())

    def _video(self, page, title, description, duration, author, thumb):
        key = re.sub(r'^https?://(www\.|m\.)?', '', page)
        youtube = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', page)
        if youtube:
            key = 'youtube:' + youtube.group(1)
            page = 'https://www.youtube.com/watch?v=' + youtube.group(1)
            thumb = thumb or f'https://i.ytimg.com/vi/{youtube.group(1)}/hqdefault.jpg'
        text = f'{title} {description[:300]} {_words_from_url(page)}'
        return Media('video', 'web', 'web:' + hashlib.sha1(key.encode()).hexdigest()[:16], title or domain(page), page,
                     thumb, page, 0, 0, duration, author or domain(page), WEB_LICENSE, text[:800], role='web')

    def youtube_search(self, query, limit):
        if self._youtube is not None:
            return self._youtube(query, limit)
        from yt_dlp import YoutubeDL
        with YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(f'ytsearch{limit}:{query}', download=False) or {}
        out = []
        for e in info.get('entries') or []:
            if not e or not e.get('id') or e.get('live_status') in ('is_live', 'is_upcoming'):
                continue
            thumbs = e.get('thumbnails') or []
            out.append({'url': f"https://www.youtube.com/watch?v={e['id']}", 'title': e.get('title') or '',
                        'description': e.get('description') or '', 'duration': e.get('duration') or 0,
                        'channel': e.get('channel') or e.get('uploader') or '',
                        'thumb': thumbs[-1]['url'] if thumbs else ''})
        return out

    # ---- downloading ----
    def download_image(self, media, target):
        """Download like a browser (some sites refuse requests without a referring page); keeps only
        files that really are pictures."""
        target = Path(target)
        if target.exists() and target.stat().st_size > 0:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        headers = {'Referer': media.page_url} if media.page_url else {}
        response = self.session.get(media.url, headers=headers, timeout=40)
        response.raise_for_status()
        if len(response.content) < 1500:
            raise ValueError('the site did not send a real image')
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(response.content)) as image:
            image.verify()
        partial = target.with_suffix(target.suffix + '.partial')
        partial.write_bytes(response.content)
        partial.replace(target)
        return target

    def download_video(self, media, need):
        """Only the useful part of a web video (the whole video when it is short), video only, <= 1080p.
        Returns (file, seconds of the source where the file starts)."""
        duration = media.duration
        start, end = 0.0, None
        if duration > 150:
            start = max(3.0, min(duration * .12, duration - SECTION - 5))
            end = start + max(SECTION, need + 10)
        key = hashlib.sha1(f'{media.url}|{start}|{end}'.encode()).hexdigest()[:20]
        folder = self.root / 'cache' / 'visuals' / 'web-video'
        folder.mkdir(parents=True, exist_ok=True)
        done = [p for p in folder.glob(key + '.*') if not p.name.endswith(('.part', '.ytdl', '.temp'))]
        if done:
            return done[0], start
        from yt_dlp import YoutubeDL
        options = {'format': 'bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080][ext=mp4]/bv*[height<=1080]/'
                             'b[height<=1080]/b',
                   'outtmpl': str(folder / (key + '.%(ext)s')), 'quiet': True, 'no_warnings': True,
                   'noplaylist': True, 'retries': 3, 'socket_timeout': 30, 'overwrites': True}
        try:
            import imageio_ffmpeg
            options['ffmpeg_location'] = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        if end is not None:
            from yt_dlp.utils import download_range_func
            options['download_ranges'] = download_range_func(None, [(start, end)])
        with YoutubeDL(options) as ydl:
            ydl.download([media.url])
        done = [p for p in folder.glob(key + '.*') if not p.name.endswith(('.part', '.ytdl', '.temp'))]
        if not done:
            raise RuntimeError('the video site did not give a downloadable file')
        return done[0], start
