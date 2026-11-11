"""Additional B-roll sources using the existing bounded Commons/web clients.

Search results are candidates, never proof of a match. The local visual ranker
still filters them. Source pages and licence labels travel with every choice.
"""
from .stock import Candidate


def venue_query(query):
    """Search libraries by physical venue names, not abstract absence phrases.

    The actual-frame checker still enforces the requested literal/illustrative
    use. Broadening retrieval never by itself approves an active venue.
    """
    import re
    text=query.casefold()
    region=' India' if re.search(r'\bindia\b',text) else ''
    if re.search(r'\bcaf[eé]s?\b|\bcoffee shop',text):return 'cafe interior'+region
    if re.search(r'\b(?:cricket|football|golf|tennis|rugby)\b',text):return ''
    if 'nightclub' in text or re.search(r'\bclub\b',text) and re.search(r'\b(?:night|empty|closed|nightlife)\b',text):
        return 'nightclub interior'+region
    if re.search(r'\bnightlife\b',text):return 'nightclub interior'+region
    if re.search(r'\b(?:bar|lounge)\b',text):
        return 'bar interior'+region
    return ''


def stock_keyword(query):
    """Stock APIs often AND every word; retain a broad physical-subject fallback."""
    import re
    venue=venue_query(query)
    if venue:return venue.split()[0]
    text=query.casefold()
    if re.search(r'\b(?:cricket|ipl|rcb|wickets?)\b',text):return 'cricket'
    if re.search(r'\b(?:shutter|shutters|shop|shops|storefront)\b',text):return 'shop'
    if re.search(r'\b(?:night|nighttime)\b',text):
        if re.search(r'\b(?:highway|drive|driving|motorway)\b',text):return 'night drive'
        if re.search(r'\b(?:street|streets|city|cityscape|road)\b',text):return 'night street'
    if re.search(r'\b(?:phone|smartphone)\b',text):return 'phone'
    if re.search(r'\b(?:wardrobes?|closets?)\b|\bclothes cupboard\b',text):return 'closet'
    return ''


def candidate(media, *, extraction=False):
    # Older web-video records put their evidence prose in license_url.
    licence_url=media.license_url if media.license_url.startswith(('https://','http://')) else ''
    return Candidate(media.source, media.id, media.title, media.duration, media.width, media.height,
                     thumb=media.thumb, download_url=media.url, page_url=media.page_url,
                     author=media.author, query=media.text or (media.license_url if not licence_url else ''), kind=media.kind,
                     license=media.license, license_url=licence_url, extraction=extraction)


class CommonsClient:
    name = 'commons'

    def __init__(self, root):
        from hinglish_visuals.web import Web
        self.web = Web(root)

    def search(self, query, orientation, width, height, per_page=6):
        return [candidate(m) for m in self.web.commons_search(query, 'video', min(per_page, 6))
                if m.kind == 'video' and not m.nonfree]

    def images(self, query, limit=5):
        return [candidate(m) for m in self.web.commons_search(query, 'bitmap', min(limit, 5))
                if m.kind == 'image' and not m.nonfree]


class WebClient:
    name = 'web'

    def __init__(self, root, progress=print):
        from hinglish_visuals.websearch import WebSearch
        self.web = WebSearch(root, progress)

    def search(self, query, orientation, width, height, per_page=6):
        from .stock_pages import search
        try:pages=search(self.web,query)
        except Exception as error:
            self.web.progress(f'    Public stock-page search skipped: {error}');pages=[]
        broad=venue_query(query)
        videos=self.web.videos(broad or query,min(per_page,5))
        if broad and broad.casefold()!=query.casefold():
            videos+=self.web.videos(query,min(per_page,3))
        return [p for p in pages if p.duration<=1800]+[candidate(m, extraction=True)
                for m in videos if m.duration<=1800]

    def images(self, query, limit=5):
        return [candidate(m) for m in self.web.images(query, min(limit, 5))]


def exact_subject_match(item, subject):
    """Specific stills must name the actual subject, not just pass a generic visual score."""
    import re
    words = lambda s: set(re.findall(r'[a-z0-9]+', s.casefold())) - {'the', 'a', 'of', 'in', 'and'}
    wanted = words(subject)
    evidence = words(' '.join((item.title, item.query, item.page_url)))
    return bool(wanted) and len(wanted & evidence) / len(wanted) >= .75


def acquire(root, item, need):
    """Get a reusable source; return local path, available duration and source offset."""
    if item.kind != 'video':
        raise ValueError('Add B-roll uses videos only. Choose a video clip instead of an image.')
    from pathlib import Path
    from .library import probe_video
    from .stock import cached_name, download
    from hinglish_visuals.web import Media
    from hinglish_visuals.websearch import WebSearch
    if item.path and Path(item.path).is_file():
        path = Path(item.path)
    else:
        media = Media(item.kind, item.source, item.id, item.title, item.download_url,
                      item.thumb, item.page_url, item.width, item.height, item.duration,
                      item.author, item.license, item.license_url)
        if item.extraction:
            from .web_download import download as download_web
            path = download_web(root,item,need)
        else:
            path = download(item.download_url, Path(root)/'cache/broll/stock'/cached_name(item),
                            max_bytes=400*1024*1024)
        item.path = str(path)
    try:
        info = probe_video(path)
    except Exception:
        # Repair only our derived stock cache. Never delete creator footage or
        # downloaded web originals, and do not repeatedly fetch an invalid URL.
        cache=(Path(root)/'cache/broll/stock').resolve()
        if item.source=='library' or not Path(path).resolve().is_relative_to(cache) or item.extraction:
            raise
        Path(path).unlink(missing_ok=True)
        item.path=''
        path=download(item.download_url,cache/cached_name(item),max_bytes=400*1024*1024)
        info=probe_video(path)
        item.path=str(path)
    if not info or info[0] < need:
        raise ValueError('The downloaded B-roll is shorter than this spoken line. Choose another clip.')
    return path, info[0], min(item.offset if item.source == 'library' else 1.0, max(0., info[0]-need))
