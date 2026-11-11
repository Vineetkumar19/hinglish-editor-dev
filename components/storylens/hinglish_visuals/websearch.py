"""The web agent's hands: search the whole internet like a person would, then download.

Images: "Zomato logo png", "Mahatma Gandhi photo", "Meenakshi Amman Temple" through web image search
(DuckDuckGo / Bing / Yahoo via the `ddgs` package, no key). Videos: web video search plus YouTube search,
downloaded with yt-dlp (YouTube and 1000+ sites), only the part that is needed. Every file still has to
name the person/brand/place in its title or address, then CLIP and the AI judge pick the best one."""
import hashlib
import ipaddress
import json
from pathlib import Path
from dataclasses import replace
import re
import time
from urllib.parse import urlparse, urljoin

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
MAX_IMAGE_BYTES = 25 * 1024 * 1024    # a picture bigger than this is not a normal photo/logo
MAX_VIDEO_BYTES = 400 * 1024 * 1024   # one downloaded web-video part


def _not_live(info, *, incomplete=False):
    """yt-dlp filter: never record a live stream (it would never end)."""
    return 'live stream' if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming') else None


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
    def begin_subject(self, seconds=60):
        self.subject_deadline=time.monotonic()+seconds
        self.subject_calls=0
        self.source_evidence_pages=set()
        self.source_evidence_bodies={}
        self.source_evidence_errors=[]

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
            saved=json.loads(file.read_text(encoding='utf-8'))
            if saved or time.time()-file.stat().st_mtime<300:return saved
        if time.monotonic()>getattr(self,'subject_deadline',float('inf')) or getattr(self,'subject_calls',0)>=8:
            raise TimeoutError('This keyword reached its source-search limit; continuing with saved sources.')
        self.subject_calls=getattr(self,'subject_calls',0)+1
        data = call()
        file.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return data

    def ddgs(self):
        if self._ddgs is None:
            from ddgs import DDGS
            self._ddgs = DDGS(timeout=20)
        return self._ddgs

    def pages(self, query, limit=5):
        """Independent text-search leads when one research provider misses a name."""
        try:
            rows=self._cached('web-pages',[query,limit],lambda:list(self.ddgs().text(query,
                max_results=limit,backend='google,bing,brave',safesearch='moderate')))
            return [{'title':r.get('title',''),'url':r.get('href') or r.get('url',''),
                'text':r.get('body') or r.get('description','')} for r in rows]
        except Exception as error:
            self.progress('Web page search unavailable: '+str(error))
            return []

    def images(self, query, limit=30, transparent=False):
        """Web image search -> Media (largest real image; the address and title are its evidence)."""
        options = {'max_results': limit, 'safesearch': 'moderate', 'region': 'in-en'}
        if transparent:
            options['type_image'] = 'transparent'
        try:
            raw = self._cached('images', [query, options], lambda: list(self.ddgs().images(query, **options)))
        except Exception as error:
            self.progress(f'Web image search unavailable: {error}; trying Agent Reach source pages')
            raw = []
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
        if len(found) < 10:
            try:
                from .reach import search, read
                pages = self._cached('reach-search', [query, 5], lambda: search(self.root, query, 5))
                pages=list({p.get('url'):p for p in self.pages(query,3)+pages}.values())
                for page in pages[:5]:
                    page_url = page.get('url') or ''
                    if not page_url.startswith('http') or watermarked(page_url):
                        continue
                    body = self._cached('reach-read', page_url, lambda: read(self.root, page_url))
                    for title, url in re.findall(r'!\[([^\]]*)\]\((https?://[^\s)]+)\)', body)[:12]:
                        if watermarked(url): continue
                        found.append(Media('image', 'web', 'web:'+hashlib.sha1(url.encode()).hexdigest()[:16],
                            title or page.get('title',''), url, url, page_url,
                            author=domain(page_url), license=WEB_LICENSE,
                            text=(title+' '+page.get('title','')+' '+page.get('text',''))[:1000], role='agent-reach'))
            except Exception as error:
                self.progress(f'Agent Reach search/read unavailable: {error}; keeping available image-search results')
        return found

    def source_evidence(self, media, method):
        """Read bounded image-bound source prose before the generic location gate.

        No query-derived location, guessed city expansion or image-identity approval.
        The existing shared source cache/time/call limits continue to apply.
        """
        from .web import generic_reference_allowed, generic_source_matches
        if not isinstance(method,dict) or not generic_reference_allowed(method, method.get('kind'), method.get('show'), method.get('name')):
            return media
        if generic_source_matches(method, f'{media.title} {media.text}'):
            return media
        page=media.page_url
        parsed=urlparse(page)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
            return media
        host=parsed.hostname.casefold().rstrip('.')
        if host=='localhost' or host.endswith(('.localhost','.local')):
            return media
        try:
            if not ipaddress.ip_address(host).is_global:
                return media
        except ValueError:
            pass  # Existing public read channel owns DNS/redirect policy.
        pages=getattr(self,'source_evidence_pages',set())
        bodies=getattr(self,'source_evidence_bodies',{})
        if page not in pages and len(pages)>=4:
            return media
        if page in pages and page not in bodies:
            return media  # A prior failure is not retried for every image.
        pages.add(page);self.source_evidence_pages=pages
        try:
            from .reach import read
            if page not in bodies:
                bodies[page]=self._cached('reach-read',page,lambda:read(self.root,page))
                self.source_evidence_bodies=bodies
            body=bodies[page]
            if not isinstance(body,str) or not body.strip():
                raise ValueError('The source page returned no readable evidence.')
            # Bind the page to the exact offered image, not an unrelated article.
            links=list(re.finditer(r'!\[[^\]]*\]\(([^\s)]+)\)',body))
            match=next((m for m in links if urljoin(page,m.group(1)).split('#')[0]==media.url.split('#')[0]),None)
            if match is None:
                return media
            before=body.rfind('\n#',0,match.start())
            after=body.find('\n#',match.end())
            section=body[max(before,match.start()-2400,0):min(after if after>=0 else len(body),match.end()+2400)]
            # Only this source's actual prose is added; instructions remain data.
            prose=re.sub(r'!\[([^\]]*)\]\([^)]*\)',r'\1',section)
            prose=re.sub(r'\[([^\]]*)\]\([^)]*\)',r'\1',prose)
            prose=re.sub(r'<[^>]+>',' ',prose)
            prose=re.sub(r'\s+',' ',prose).strip()
            return replace(media,text=f'{media.text}\n{prose}')
        except Exception as error:
            errors=getattr(self,'source_evidence_errors',[])
            errors.append({'page_url':page,'error':str(error)})
            self.source_evidence_errors=errors
            self.progress('Source page verification could not finish; this image stays unverified.')
            return media

    def evidence_candidates(self, moment, entity, candidates):
        """Read source pages; capture actual documents/scorecards, never invent a stats graphic."""
        from .reach import search, read
        terms = [t.casefold().strip() for t in moment.evidence_terms if str(t).strip()]
        if not terms:
            return []
        pages = self._cached('reach-evidence', moment.queries[0],
            lambda: search(self.root, moment.queries[0], 8))
        pages=list({p.get('url'):p for p in self.pages(moment.queries[0],3)+pages}.values())
        evidence = []
        for page in pages[:8]:
            url = page.get('url') or ''
            if not url.startswith('http') or watermarked(url): continue
            try:
                body = self._cached('reach-read', url, lambda: read(self.root, url))
                if not all(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)', body.casefold()) for t in terms):
                    continue
                # Source text and a local vision check of the capture are both required.
                from playwright.sync_api import sync_playwright
                key = hashlib.sha256(('table-v2|'+url+'|'+json.dumps(terms)).encode()).hexdigest()[:20]
                target = self.root/'cache/visuals/evidence'/(key+'.png')
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(headless=True)
                        try:
                            tab = browser.new_page(viewport={'width':1280,'height':1600})
                            tab.route('**/*', lambda route: route.abort() if route.request.resource_type in ('media','font') else route.continue_())
                            tab.goto(url, wait_until='domcontentloaded', timeout=25000)
                            tables=tab.locator('table').all()
                            best=None;best_score=0
                            for table in tables[:20]:
                                text=table.inner_text(timeout=2000).casefold()
                                score=sum(t in text for t in terms)
                                if score>best_score:best,best_score=table,score
                            if best is not None:
                                best.screenshot(path=str(target),timeout=8000)
                            else:
                                tab.screenshot(path=str(target), full_page=False)
                        finally: browser.close()
                media = Media('image','web','evidence:'+key,page.get('title') or entity.name,
                    url, str(target), url,1280,1600,author=domain(url),license=WEB_LICENSE,
                    text=(page.get('title','')+' '+body)[:4000],role='source-capture',path=str(target))
                evidence.append(media)
            except Exception as error:
                self.progress(f'Could not inspect evidence source {domain(url)}: {error}')
        return evidence

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
        with YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': True, 'skip_download': True,
                        'socket_timeout':15, 'retries':1, 'extractor_retries':1}) as ydl:
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
        # streamed with a size cap: a bad search result must never pull a huge file into memory
        with self.session.get(media.url, headers=headers, timeout=40, stream=True) as response:
            response.raise_for_status()
            kind = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
            if kind and not kind.startswith('image/') and kind != 'application/octet-stream':
                raise ValueError(f'the site sent {kind}, not a picture')
            if int(response.headers.get('Content-Length') or 0) > MAX_IMAGE_BYTES:
                raise ValueError('the picture is too large')
            content = bytearray()
            for chunk in response.iter_content(256 * 1024):
                content += chunk
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError('the picture is too large')
        if len(content) < 1500:
            raise ValueError('the site did not send a real image')
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > 60_000_000:        # decompression-bomb guard (~ 8K x 7K)
                raise ValueError('the picture is too large')
            image.verify()
        partial = target.with_suffix(target.suffix + '.partial')
        partial.write_bytes(bytes(content))
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
        elif duration <= 0:                     # length unknown (live streams, some sites): never the whole thing
            end = max(SECTION, need + 10)
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
                   'noplaylist': True, 'retries': 3, 'socket_timeout': 30, 'overwrites': True, 'noprogress': True,
                   'max_filesize': MAX_VIDEO_BYTES, 'match_filter': _not_live}
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
