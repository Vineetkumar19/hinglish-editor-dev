"""Read public stock-video pages discovered by web search.

Only advertised media URLs (VideoObject, OpenGraph, HTML video/source) are
collected. No browser challenges, accounts or paid-download gates are bypassed.
"""
import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse

from .stock import Candidate
from hinglish_visuals.websearch import parse_duration,watermarked


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.meta={};self.sources=[];self.json=[];self.buffer='';self.in_json=False

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta':self.meta[a.get('property') or a.get('name','')]=a.get('content','')
        if tag in ('video','source') and a.get('src'):self.sources.append(a['src'])
        if tag=='video' and a.get('poster'):self.meta.setdefault('og:image',a['poster'])
        if tag=='script' and a.get('type')=='application/ld+json':self.in_json=True;self.buffer=''

    def handle_data(self,data):
        if self.in_json:self.buffer+=data

    def handle_endtag(self,tag):
        if tag=='script' and self.in_json:
            try:self.json.append(json.loads(self.buffer))
            except ValueError:pass
            self.in_json=False


def _objects(value):
    if isinstance(value,list):
        for item in value:yield from _objects(item)
    elif isinstance(value,dict):
        if value.get('@type')=='VideoObject' or 'VideoObject' in (value.get('@type') or []):yield value
        if '@graph' in value:yield from _objects(value['@graph'])


def parse_page(page_url,markup,query=''):
    parser=Page();parser.feed(markup)
    objects=[v for block in parser.json for v in _objects(block)]
    meta=parser.meta
    if not objects:objects=[{'name':meta.get('og:title',query),'thumbnailUrl':meta.get('og:image',''),
                            'contentUrl':meta.get('og:video:url') or meta.get('og:video') or
                                          (parser.sources[0] if parser.sources else ''),
                            'duration':meta.get('video:duration','')}]
    found=[]
    for obj in objects:
        if obj.get('requiresSubscription') in (True,'true'):continue
        url=urljoin(page_url,str(obj.get('contentUrl') or ''))
        if not obj.get('contentUrl') or not url.startswith(('https://','http://')) or watermarked(url,page_url):continue
        thumb=obj.get('thumbnailUrl') or meta.get('og:image','')
        if isinstance(thumb,list):thumb=thumb[0] if thumb else ''
        author=obj.get('author') or obj.get('creator') or {}
        if isinstance(author,list):author=author[0] if author else {}
        if isinstance(author,dict):author=author.get('name','')
        def integer(v):
            if isinstance(v,dict):v=v.get('value',0)
            try:return int(v or 0)
            except (ValueError,TypeError):return 0
        licence=obj.get('license') or ''
        if not isinstance(licence,str):licence=''
        found.append(Candidate('website','website:'+hashlib.sha1(url.encode()).hexdigest()[:20],
            str(obj.get('name') or meta.get('og:title') or query),parse_duration(obj.get('duration')),
            integer(obj.get('width')),integer(obj.get('height')),thumb=urljoin(page_url,thumb) if thumb else '',
            download_url=url,page_url=page_url,author=str(author),query=query,
            license='Source page terms; check before publishing',license_url=licence))
    return found


def search(web,query,limit=3):
    """Bounded public-page discovery complements the video-search engines."""
    raw=web._cached('broll-stock-pages-v3',[query,limit],lambda:list(web.ddgs().text(
        query+' stock footage -site:pexels.com -site:pixabay.com -site:youtube.com -site:vecteezy.com',
        max_results=limit,safesearch='moderate',region='in-en')))
    found=[]
    for result in raw:
        page=result.get('href') or result.get('url') or ''
        host=(urlparse(page).hostname or '').lower()
        if not page.startswith(('https://','http://')) or not host or host in ('localhost','127.0.0.1') or watermarked(page):continue
        try:
            with web.session.get(page,timeout=15,stream=True) as response:
                response.raise_for_status()
                # Skip non-HTML and excessively large pages; never execute scripts.
                if 'html' not in response.headers.get('Content-Type',''):continue
                content=bytearray()
                for block in response.iter_content(65536):
                    content.extend(block)
                    if len(content)>2_000_000:break
                if len(content)>2_000_000:continue
                markup=content.decode(response.encoding or 'utf-8',errors='replace')
            found+=parse_page(page,markup,result.get('title') or query)[:2]
        except Exception as error:
            web.progress(f'    Stock page skipped ({host}): {error}')
    return found[:6]
