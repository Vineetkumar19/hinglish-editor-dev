"""Public catalogue adapters. No keys, inference, cookies, or gated downloads.

Availability is recorded per website; one broken catalogue does not veto the
others. Only public advertised videos with an identified free record are used.
"""
from collections import deque
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse,urljoin,quote
from pathlib import Path
import hashlib,json,re
import requests

from .stock import Candidate
from .stock_pages import parse_page

CATALOGUE_VERSION=4
PAGE_HOSTS=frozenset(('mixkit.co','www.pexels.com','pixabay.com','coverr.co',
    'www.videezy.com','www.vidsplay.com','dareful.com','mazwai.com'))
MEDIA_HOSTS=frozenset(('assets.mixkit.co','cdn.pixabay.com','videos.pexels.com',
    'cdn.coverr.co','static.videezy.com'))


def media_allowed(url):
    p=urlparse(url)
    return p.scheme=='https' and p.netloc in MEDIA_HOSTS and p.path.lower().endswith('.mp4')


class EmbeddedJSON(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.buffer='';self.blocks=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('type')=='application/json':self.active=True;self.buffer=''
    def handle_data(self,text):
        if self.active:self.buffer+=text
    def handle_endtag(self,tag):
        if tag=='script' and self.active:
            try:self.blocks.append(json.loads(self.buffer))
            except ValueError:pass
            self.active=False


def records(value):
    if isinstance(value,dict):
        if 'slug' in value and 'isPremium' in value:yield value
        for child in value.values():yield from records(child)
    elif isinstance(value,list):
        for child in value:yield from records(child)


def coverr_candidates(markup,query,orientation):
    links=[]
    for raw in re.findall(r'href=["\']([^"\']+)["\']',markup):
        p=urlparse(urljoin('https://coverr.co',unescape(raw)))
        if p.netloc=='coverr.co' and re.fullmatch(r'/videos/[a-z0-9-]+',p.path):
            slug=p.path.rsplit('/',1)[-1]
            if slug not in links:links.append(slug)
    parser=EmbeddedJSON();parser.feed(markup)
    by_slug={r['slug']:r for block in parser.blocks for r in records(block)}
    found=[]
    for slug in links[:30]:
        row=by_slug.get(slug,{})
        if row.get('isPremium') is not False or row.get('isAiGenerated') is not False:continue
        if orientation=='vertical' and row.get('isVertical') is False:continue
        if orientation=='horizontal' and row.get('isVertical') is True:continue
        url=(row.get('urls') or {}).get('mp4') or ''
        if not media_allowed(url):continue
        width=int(row.get('maxWidth') or 0);height=int(row.get('maxHeight') or 0)
        found.append(Candidate('coverr','coverr:'+slug,str(row.get('title') or query),
            float(row.get('duration') or 0),width,height,
            thumb=str(row.get('poster') or row.get('thumbnail') or ''),download_url=url,
            page_url='https://coverr.co/videos/'+slug,query=query,
            license='Coverr free video · check source licence and third-party rights',
            license_url='https://coverr.co/license'))
    return found[:12]


def videezy_links(markup):
    found=[]
    for raw in re.findall(r'href=["\']([^"\']+)["\']',markup):
        p=urlparse(urljoin('https://www.videezy.com',unescape(raw)))
        if (p.scheme=='https' and p.netloc=='www.videezy.com' and
            re.fullmatch(r'/[a-z-]+/\d+-[a-z0-9-]+',p.path) and
            not p.path.startswith('/after-effects-templates/')):
            url='https://www.videezy.com'+p.path
            if url not in found:found.append(url)
    return found


def videezy_candidates(page,markup,query):
    if not re.search(r'\bresource_is_premium\s*=\s*false\b',markup):return []
    found=[]
    for item in parse_page(page,markup,query):
        if not media_allowed(item.download_url):continue
        item.source='videezy';item.id='videezy:'+hashlib.sha256(item.download_url.encode()).hexdigest()[:24]
        item.license='Videezy free resource · check attribution and source licence'
        found.append(item)
    return found[:1]


def interleave(sources,status):
    """Round-robin choices so a single site's first six cannot hide other sites."""
    queue=deque((name,iter(values)) for name,values in sources)
    while queue:
        name,values=queue.popleft()
        try:item=next(values)
        except StopIteration:continue
        except Exception:
            status.setdefault(name,'Website could not finish this search; other sources continue')
            continue
        queue.append((name,values));yield item


def parallel_interleave(sources,status,per_source=6):
    """Five bounded metadata searches; decoding/downloads remain in caller.

    Each provider has its own iterator/session. Finish this metadata batch
    before returning so no abandoned worker leaks into the next keyword.
    Round-robin the small batches so one fast website cannot hide the others.
    """
    from concurrent.futures import ThreadPoolExecutor
    if type(per_source) is not int or not 1<=per_source<=6:raise ValueError('Choose up to six source candidates.')
    def take(name,factory):
        batch=[];values=None
        try:
            values=iter(factory())
            for _ in range(per_source):
                try:batch.append(next(values))
                except StopIteration:break
        except Exception:status[name]='Website could not finish this search; other sources continue'
        finally:
            if values is not None and hasattr(values,'close'):values.close()
        return batch
    sources=list(sources)
    if not sources:return
    with ThreadPoolExecutor(max_workers=min(5,len(sources)),thread_name_prefix='broll-source') as pool:
        tasks=[(name,pool.submit(take,name,factory)) for name,factory in sources]
        batches=[(name,iter(task.result())) for name,task in tasks]
    yield from interleave(batches,status)


class CatalogueSearch:
    def __init__(self,folder,orientation,limit=None):
        from .choice_policy import choice_limit
        self.limit=choice_limit(limit,orientation)
        self.folder=Path(folder);self.orientation=orientation;self.session=requests.Session()
        self.cache=self.folder/'website-pages';self.cache.mkdir(exist_ok=True)
        self.status={};self.details={};self.blocked=set();self.probed=set();self.failed_queries={}

    def page(self,name,url):
        from .website_review import _html
        if name in self.blocked:raise ValueError('This website is unavailable for this run.')
        if url in self.failed_queries:raise ValueError(self.failed_queries[url])
        file=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        if file.is_file():
            self.status[name]='Using saved public website pages'
            return file.read_text('utf-8')
        try:
            text=_html(self.session,url);file.write_text(text,encoding='utf-8')
            self.status[name]='Website accessible';return text
        except requests.HTTPError as error:
            code=error.response.status_code if error.response is not None else None
            self.status[name]=f'Website access blocked ({code}); other sources continue' if code in (401,403,429) else f'Website request failed ({code}); other sources continue'
            if code in (401,403,429):self.blocked.add(name)
            raise
        except requests.RequestException:
            self.status[name]='Website connection failed; other sources continue';raise
        except ValueError as error:
            message=str(error)[:350];self.details[name]=message
            if 'redirect' in message.lower():
                self.status[name]='Website redirected to an unsupported destination; other sources continue'
                self.blocked.add(name)
            else:
                self.status[name]='This website search could not be read; other queries and sources continue'
                self.failed_queries[url]=message
            raise

    def coverr(self,query):
        page=self.page('coverr','https://coverr.co/s?q='+quote(query,safe=''))
        found=coverr_candidates(page,query,self.orientation)
        del page
        yield from found

    def videezy(self,query):
        page=self.page('videezy','https://www.videezy.com/free-video/'+quote(query.replace(' ','-'),safe='-'))
        for url in videezy_links(page)[:10]:
            try:yield from videezy_candidates(url,self.page('videezy',url),query)
            except (requests.RequestException,ValueError):continue

    def stock_site(self,name,query):
        from .stock_browser_client import BrowserSearch
        try:
            browser=BrowserSearch(self.folder)
            found=browser.search(name,query,self.orientation,limit=self.limit)
            if found is not None:
                self.status[name]='Chrome · '+(browser.message or 'Public video search finished')
                yield from found
                return
        except (requests.RequestException,ValueError,OSError) as error:
            self.details[name]=str(error)[:350]
            self.status[name]='Chrome search unavailable; public website fallback continues'
        url=('https://www.pexels.com/search/videos/'+quote(query,safe='')+'/' if name=='pexels' else
             'https://pixabay.com/videos/search/'+quote(query,safe='')+'/')
        host=urlparse(url).netloc;markup=self.page(name,url)
        pattern=r'/video/[a-z0-9-]+-\d+/?' if name=='pexels' else r'/videos/[a-z0-9-]+-\d+/?'
        links=[]
        for raw in re.findall(r'href=["\']([^"\']+)["\']',markup):
            detail=urljoin(url,unescape(raw));p=urlparse(detail)
            if p.scheme=='https' and p.netloc==host and re.fullmatch(pattern,p.path) and detail not in links:links.append(detail)
        for detail in links[:6]:
            try:yield from parse_page(detail,self.page(name,detail),query)
            except (requests.RequestException,ValueError):continue

    def probe_other_catalogues(self):
        # These sites currently block public access or redirect to another
        # product. Check once, report accurately, and never bypass a challenge.
        for name,url in [('vidsplay','https://www.vidsplay.com/'),('dareful','https://dareful.com/'),('mazwai','https://mazwai.com/')]:
            if name in self.probed:continue
            self.probed.add(name)
            try:
                self.page(name,url)
                self.status[name]='Website reachable; automated playable-video extraction is not supported yet'
            except (requests.RequestException,ValueError):pass
