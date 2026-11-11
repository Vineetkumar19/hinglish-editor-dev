"""Public browser discovery for the two desks. No account cookies or publishing.

This is application code: an isolated short-lived browser, not the owner's
Chrome profile. Search candidates and source-page verification stay distinct.
"""
from pathlib import Path
import datetime as dt
import re
import urllib.parse as U
import json
import time
import threading
from contextlib import contextmanager

BROWSER_ROOT=Path(__file__).resolve().parent.parent/'social-browser'
SETUP_RUNNING=threading.Event()
SETUP_FINISH=threading.Event()

def browser_state():
    try:return json.loads((BROWSER_ROOT/'state.json').read_text(encoding='utf8'))
    except (OSError,ValueError):return {}

def save_browser_state(value):
    BROWSER_ROOT.mkdir(parents=True,exist_ok=True)
    path=BROWSER_ROOT/'state.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value),encoding='utf8');tmp.replace(path)

@contextmanager
def browser_lock():
    import msvcrt
    BROWSER_ROOT.mkdir(parents=True,exist_ok=True)
    with (BROWSER_ROOT/'session.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('Collection browser busy in the other desk or setup window; next scan can retry')
        try:yield
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def connect_browser():
    if SETUP_RUNNING.is_set():return
    SETUP_RUNNING.set();SETUP_FINISH.clear()
    try:
        from playwright.sync_api import sync_playwright
        with browser_lock(),sync_playwright() as pw:
            context=pw.chromium.launch_persistent_context(str(BROWSER_ROOT/'profile'),channel='chrome',chromium_sandbox=True,headless=False,locale='en-US')
            try:
                page=context.pages[0] if context.pages else context.new_page()
                save_browser_state({'state':'setup_open','message':'Complete the Google check in the Collection browser, then click Finish browser setup in the desk.'})
                page.goto('https://www.google.com/search?q=site%3Ainstagram.com%2Freel%2F+gaming',timeout=30000)
                deadline=time.monotonic()+300
                while time.monotonic()<deadline:
                    if not context.pages:break
                    if SETUP_FINISH.is_set():
                        if '/sorry/' not in page.url and page.locator('h3').count()>0:
                            save_browser_state({'state':'ready','checked':dt.datetime.now(UTC).isoformat(),'message':'Browser setup checked. Run Refresh Instagram + X.'});return
                        SETUP_FINISH.clear()
                        save_browser_state({'state':'setup_open','message':'Search results are not visible yet. Complete the check, then click Finish browser setup.'})
                    page.wait_for_timeout(500)
                save_browser_state({'state':'needs_connection','message':'Browser setup closed or timed out before a usable search page was verified.'})
            finally:context.close()
    except Exception as exc:save_browser_state({'state':'needs_connection','message':str(exc)[:300]})
    finally:SETUP_RUNNING.clear()

UTC = dt.timezone.utc

def direct_url(raw):
    try:
        p = U.urlsplit(raw)
        if p.scheme != 'https' or p.username or p.password:
            return None
        host = (p.hostname or '').lower().removeprefix('www.').removeprefix('mobile.')
        if host in ('x.com', 'twitter.com'):
            m = re.fullmatch(r'/([\w]+)/status/(\d+)(?:/(?:photo|video)/\d+)?/?', p.path)
            if m:
                return 'X', f'https://x.com/{m[1]}/status/{m[2]}'
        if host == 'instagram.com':
            m = re.fullmatch(r'/(?:[\w.]+/)?(p|reel|reels)/([\w-]+)/?', p.path)
            if m:
                return 'Instagram', f'https://www.instagram.com/{"reel" if m[1]=="reels" else m[1]}/{m[2]}/'
    except ValueError:
        pass
    return None

def is_search_redirect(raw):
    try:
        p=U.urlsplit(raw)
        return p.scheme=='https' and p.hostname in ['www.google.com','google.com'] and p.path in ['/url','/goto'] and not p.username and not p.password
    except ValueError:return False

def resolve_result(page, row):
    direct=direct_url(row['url'])
    if direct:return direct
    if not is_search_redirect(row['url']):return None
    row['search_redirect']=row['url']
    # Resolve only observed Google result redirects. Stop at the public post
    # address, before Instagram/X can replace it with a login URL.
    import requests
    current=row['url']
    try:
        for _ in range(3):
            if not is_search_redirect(current):return None
            response=requests.get(current,allow_redirects=False,timeout=8)
            if response.status_code not in (301,302,303,307,308):return None
            target=U.urljoin(current,response.headers.get('Location',''))
            direct=direct_url(target)
            if direct:return direct
            current=target
    except requests.RequestException as exc:row['redirect_error']=str(exc)[:180]
    return None

def publication(text, current=None):
    """Search-result age is approximate evidence, never a precise post timestamp."""
    current = current or dt.datetime.now(UTC)
    m = re.search(r'\b(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago\b', text, re.I)
    if m:
        hours = int(m[1]) * {'minute':1/60,'hour':1,'day':24,'week':168,'month':720,'year':8760}[m[2].lower()]
        return '', hours, m[0]
    for pattern, fmt in [(r'\b\d{4}-\d{2}-\d{2}\b','%Y-%m-%d'),(r'\b[A-Z][a-z]{2} \d{1,2}, \d{4}\b','%b %d, %Y')]:
        m = re.search(pattern,text)
        if m:
            try:
                date = dt.datetime.strptime(m[0],fmt).replace(tzinfo=UTC)
                return date.date().isoformat(), (current-date).total_seconds()/3600, m[0]
            except ValueError:
                pass
    return '', None, ''

RESULT_JS = r'''() => [...document.querySelectorAll('a[href]')]
 .filter(a=>a.querySelector('h3')).map(a=>{
   let block=a;
   for(let n=0;n<6 && block.parentElement;n++){
     const p=block.parentElement;
     if(p.querySelectorAll('h3').length>1)break;
     block=p;
   }
   return {url:a.href,title:a.querySelector('h3').innerText,
     evidence:block.innerText.slice(0,1800)};
 })'''

def collect(cfg, niche, root, media_allowed):
    domains=cfg.get('domains',[])
    enabled=[p for p,d in [('Instagram','instagram.com'),('X','x.com')] if d in domains or (p=='X' and 'twitter.com' in domains)]
    if not enabled:
        return [],[{'source':p,'ok':True,'found':0,'state':'disabled'} for p in ['Instagram','X']]
    setup=browser_state()
    if setup.get('state') in ['needs_connection','setup_open']:
        return [],[{'source':p,'ok':False,'found':0,'state':'needs_connection','error':setup.get('message','Use Connect collection browser in Settings.')}for p in enabled]
    event=cfg.get('event','').strip() if cfg.get('mode')=='manual' else ''
    focus=event or ('gaming games' if niche=='gaming' else 'cricket')
    hours=int(cfg.get('lookback_hours',48))
    start=time.monotonic(); found={};statuses=[]
    folder=Path(root)/'data/social-runs'/dt.datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True,exist_ok=True)
    receipt={'started':dt.datetime.now(UTC).isoformat(),'niche':niche,'event':event,'queries':[]}
    try:
        from playwright.sync_api import sync_playwright
        with browser_lock(),sync_playwright() as pw:
            browser=pw.chromium.launch_persistent_context(str(BROWSER_ROOT/'profile'),channel='chrome',chromium_sandbox=True,headless=True,locale='en-US',viewport={'width':1280,'height':900})
            try:
                page=browser.new_page();page.set_default_timeout(8000)
                resolver=browser.new_page();resolver.set_default_timeout(5000)
                for platform in enabled:
                    queries=([f'site:instagram.com/reel/ {focus}',f'site:instagram.com/p/ {focus}'] if platform=='Instagram'
                             else [f'site:x.com {focus} memes',f'site:x.com {focus} news'])
                    errors=[];candidate_urls=set();stale=0
                    for query in queries:
                        if time.monotonic()-start>140:
                            errors.append('Collection time budget reached');break
                        url='https://www.google.com/search?'+U.urlencode({'q':query,'tbs':f'qdr:h{hours}','num':10})
                        try:
                            response=page.goto(url,wait_until='domcontentloaded',timeout=25000)
                            if response and response.status in (403,429):
                                raise RuntimeError('Search access limited; no challenge bypass attempted')
                            page.wait_for_selector('h3, form[action*="sorry"], #captcha-form',timeout=10000)
                            body=page.locator('body').inner_text(timeout=4000)
                            if '/sorry/' in page.url or 'unusual traffic' in body.lower():
                                save_browser_state({'state':'needs_connection','message':'Google requires human verification in the dedicated collection browser. Use Connect collection browser in Settings.'})
                                raise RuntimeError('Search requires human verification; no automatic retry')
                            results=page.evaluate(RESULT_JS)
                            receipt['queries'].append({'query':query,'url':page.url,'results':results})
                            for row in results[:8]:
                                if time.monotonic()-start>140:break
                                published,age,evidence=publication(row['evidence'])
                                if age is not None and (age>hours or age < -24):
                                    stale+=1;continue
                                direct=resolve_result(resolver,row)
                                if not direct or direct[0]!=platform:continue
                                row.update(url=direct[1],published=published,date_evidence=evidence,
                                  event=event,kind='social candidate',verification='search_only',
                                  summary='Public search candidate; original post and claims need review. '+('Search age: '+evidence+'.' if evidence else 'Publication date unavailable.'),
                                  author='',thumbnail='',media_url='',search_url=page.url)
                                if platform=='X':row['author']=U.urlsplit(row['url']).path.split('/')[1]
                                else:
                                    m=re.search(r'Instagram\s*[·•]\s*([\w.]+)',row['evidence'])
                                    if m:row['author']=m[1]
                                found.setdefault(row['url'],row);candidate_urls.add(row['url'])
                        except Exception as exc:
                            errors.append(str(exc)[:280])
                            # CAPTCHA/rate-limit is a stop, not an invitation to rotate engines/proxies.
                            if 'verification' in str(exc) or 'access limited' in str(exc):break
                    verified=0;blocked=0
                    # Inspect a bounded source sample. Remaining cards explicitly remain search-only.
                    for url in sorted(candidate_urls)[:2]:
                        if time.monotonic()-start>175:break
                        row=found[url]
                        try:
                            page.goto(url,wait_until='domcontentloaded',timeout=18000)
                            page.wait_for_selector('meta[property="og:description"], article, input[name="username"], input[name="text"]',state='attached',timeout=6000)
                            detail=page.evaluate('''() => ({url:location.href,title:document.title,
                              description:document.querySelector('meta[property="og:description"]')?.content||'',
                              image:document.querySelector('meta[property="og:image"]')?.content||'',
                              published:document.querySelector('time[datetime]')?.getAttribute('datetime')||'',
                              text:document.querySelector('article')?.innerText?.slice(0,1500)||''})''')
                            row['source_check']=detail
                            description=detail['description'] or detail['text']
                            generic=any(t in (detail['title']+' '+description).lower() for t in ['login • instagram','log in to instagram','sign in to x','see instagram photos','join instagram'])
                            if not direct_url(detail['url']) or not description or generic:
                                blocked+=1;row['source_access']='login_or_unavailable';continue
                            row['verification']='source_metadata';row['source_access']='public';verified+=1
                            row['summary']=description[:1300]+' [Source metadata observed; claims not fact-checked.]'
                            if media_allowed(detail['image']):row['thumbnail']=row['media_url']=detail['image']
                            if detail['published']:
                                try:
                                    date=dt.datetime.fromisoformat(detail['published'].replace('Z','+00:00'))
                                    if date.tzinfo is None:date=date.replace(tzinfo=UTC)
                                    age=(dt.datetime.now(UTC)-date).total_seconds()/3600
                                    if age>hours or age < -1:
                                        found.pop(url,None);candidate_urls.discard(url);stale+=1;verified-=1;continue
                                    row['published']=date.isoformat();row['date_evidence']='source time element'
                                except ValueError:pass
                        except Exception as exc:
                            blocked+=1;row['source_access']='unavailable';row['source_error']=str(exc)[:180]
                    statuses.append({'source':platform,'ok':bool(candidate_urls),'found':len(candidate_urls),
                      'state':'candidates' if candidate_urls else ('blocked' if errors else 'no_results'),
                      'source_metadata_checked':verified,'source_access_blocked':blocked,'excluded_old':stale,
                      'errors':errors,'coverage':'Browser search candidates; only source_metadata items checked on the original page. Not complete platform coverage.'})
                    if browser_state().get('state')=='needs_connection':
                        for other in enabled:
                            if other!=platform and not any(s['source']==other for s in statuses):
                                statuses.append({'source':other,'ok':False,'found':0,'state':'needs_connection','error':'Waiting for collection browser verification; no repeated request.'})
                        break
            finally:
                browser.close()
    except Exception as exc:
        statuses=[{'source':p,'ok':False,'found':0,'state':'blocked','error':str(exc)[:400]} for p in enabled]
    receipt.update(finished=dt.datetime.now(UTC).isoformat(),items=list(found.values()),sources=statuses)
    (folder/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    for s in statuses:s['receipt']=str(folder/'receipt.json')
    return list(found.values()),statuses
