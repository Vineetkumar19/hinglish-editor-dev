"""Bounded audio acquisition; downloaded files remain candidates, not approved mixes.

No video uploads, catalog scraping, paid requests or credentials in model context.
Provider policy is runtime data, not a permanent promise about external pricing.
"""
import hashlib
import html
import json
import logging
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urljoin
from html.parser import HTMLParser
import requests

KEYS=('FREESOUND_API_KEY','FREESOUND_ACCESS_TOKEN','JAMENDO_CLIENT_ID','ELEVENLABS_API_KEY')
CATEGORIES={'foley','ambience','impact','whoosh','riser','poke','suspense','cute','glitch','retro','awkward','vanish'}
MAX_BYTES=30_000_000
USER_AGENT='StorylensLocalSound/1.0 (personal audio editing; bounded source search)'

def config(root):
    p=Path(root)/'config.sound-providers.local.json'
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}

def credentials(root):
    result={}
    p=Path(root)/'cache/sound/provider-credentials.dpapi'
    if p.exists():
        from hinglish_publish.secrets import crypt
        result=json.loads(crypt(p.read_bytes(),decrypt=True))
    result.update({k:os.environ[k] for k in KEYS if os.getenv(k)})
    return {k:str(v) for k,v in result.items() if k in KEYS and v}

def save_credentials(root,values):
    if set(values)-set(KEYS):raise ValueError('Unknown sound credential')
    from hinglish_publish.secrets import crypt
    current=credentials(root);current.update({k:str(v).strip() for k,v in values.items() if v})
    path=Path(root)/'cache/sound/provider-credentials.dpapi';path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_bytes(crypt(json.dumps(current).encode()));tmp.replace(path)

def status(root):
    cfg=config(root);keys=credentials(root)
    out={'commons':dict(ready=cfg.get('commons',{}).get('enabled',True) is True,mode='public_api',key_required=False)}
    out['openverse']=dict(ready=cfg.get('openverse',{}).get('enabled',False) is True,
                          mode='public_audio_search',key_required=False)
    for name,key in [('freesound','FREESOUND_API_KEY'),('jamendo','JAMENDO_CLIENT_ID'),('elevenlabs','ELEVENLABS_API_KEY')]:
        row=cfg.get(name,{})
        rights=((row.get('noncommercial_project_confirmed') is True and row.get('title_attribution_confirmed') is True)
                if name=='elevenlabs' else row.get('api_use_confirmed') is True)
        out[name]=dict(ready=row.get('enabled') is True and bool(keys.get(key)) and rights,
                      mode='generation_api' if name=='elevenlabs' else 'audio_api',
                      credential_saved=bool(keys.get(key)),terms_confirmed=rights,
                      reason='Requires credentials and permitted use; no paid fallback.')
    out['pixabay']=dict(ready=False,mode='manual',reason='No supported public audio API verified; download on the official site and add the licensed file locally.')
    out['mixkit']=dict(ready=cfg.get('mixkit',{}).get('enabled',True) is True,mode='website',
                      reason='Targeted public search/download only; no catalog scraping. File-type license applies.')
    out.update({n:dict(ready=False,mode='excluded',reason='Excluded by owner.') for n in ('epidemic','artlist')})
    return out

def allowed_license(url):
    p=urlsplit(str(url));path=re.sub(r'/deed\.[a-zA-Z_-]+/?$','',p.path).rstrip('/')
    return p.scheme in ('http','https') and p.netloc=='creativecommons.org' and bool(
        re.fullmatch(r'/licenses/by/(?:2\.0|2\.5|3\.0|4\.0)|/publicdomain/(?:zero|mark)/1\.0',path))

def clean(value):return html.unescape(re.sub('<[^>]*>',' ',str(value))).strip()[:1000]

def checked_url(url,hosts):
    p=urlsplit(str(url))
    if p.scheme!='https' or p.hostname not in hosts or p.username or p.password or p.port not in (None,443):
        raise ValueError('Audio provider returned an unsupported download location')
    return str(url)

def commons_candidate(row):
    infos=row.get('imageinfo') or []
    if not infos:return None
    info=infos[0];meta=info.get('extmetadata',{})
    val=lambda k:clean(meta.get(k,{}).get('value',''))
    licence=val('LicenseUrl')
    audio=str(info.get('mime','')).startswith('audio/') or (info.get('mime')=='application/ogg' and info.get('mediatype')=='AUDIO')
    if not audio or not allowed_license(licence):return None
    if info.get('size',MAX_BYTES+1)>MAX_BYTES or info.get('badfile'):return None
    return dict(provider='commons',id=str(row['pageid']),name=clean(row.get('title','')).removeprefix('File:'),
                url=info['url'],source_url=info.get('descriptionurl',''),license=licence,
                author=val('Artist'),attribution=val('Attribution'),description=val('ImageDescription'),
                suffix=Path(urlsplit(info['url']).path).suffix.lower(),hosts={'upload.wikimedia.org'},original_quality=True)

def openverse_candidate(row):
    """Only import a directly hosted, attributable recording from a known media host."""
    if not isinstance(row,dict) or not allowed_license(row.get('license_url','')):return None
    try:size=int(row.get('filesize') or 0)
    except (ValueError,TypeError):return None
    if row.get('mature') is True or size>MAX_BYTES:return None
    url=str(row.get('url',''));host=urlsplit(url).hostname
    hosts={'upload.wikimedia.org','cdn.freesound.org'}
    suffix=Path(urlsplit(url).path).suffix.lower()
    if host not in hosts or suffix not in ('.wav','.mp3','.ogg','.flac','.aiff','.aif','.m4a'):return None
    if not row.get('id') or not row.get('foreign_landing_url'):return None
    return dict(provider='openverse',id=str(row['id']),name=clean(row.get('title','')),
        url=url,source_url=row['foreign_landing_url'],license=row['license_url'],
        author=clean(row.get('creator','')),attribution=clean(row.get('attribution','')),
        description=clean(' '.join(str(t.get('name','')) for t in row.get('tags',[]) if isinstance(t,dict))),
        suffix=suffix,hosts=hosts,original_quality=True,
        retrieval_method='Openverse public audio search; direct approved host')

def jamendo_candidate(row):
    if row.get('audiodownload_allowed') is not True or not allowed_license(row.get('license_ccurl','')):return None
    url=row.get('audiodownload','')
    if not url:return None
    return dict(provider='jamendo',id=str(row['id']),name=clean(row.get('name','')),
                url=url,source_url=row.get('shareurl') or 'https://www.jamendo.com/track/'+str(row['id']),
                license=row['license_ccurl'],author=clean(row.get('artist_name','')),attribution='',
                suffix='.mp3',hosts={'api.jamendo.com','storage.jamendo.com','prod-1.storage.jamendo.com',
                                    'prod-2.storage.jamendo.com','usercontent.jamendo.com'},original_quality=False)

def free_generation_allowed(account,required):
    nums=[account.get('character_count'),account.get('character_limit'),required]
    return account.get('tier')=='free' and account.get('allowed_to_extend_character_limit') is False and all(
        type(n) in (int,float) and math.isfinite(n) and n>=0 for n in nums) and nums[1]-nums[0]>=required

def _json(session,url,timeout=(8,20),**kwargs):
    r=session.get(url,timeout=timeout,allow_redirects=False,**kwargs)
    try:
        r.raise_for_status()
        if r.is_redirect:raise ValueError('Provider API redirected; reconnect the official endpoint')
        return r.json()
    finally:r.close()

class _MixkitCards(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'item-grid-card' in a.get('class','').split():
            self.row={'name':''};self.rows.append(self.row)
        if self.row is None:return
        if a.get('data-audio-player-item-id-value'):self.row['id']=a['data-audio-player-item-id-value']
        if a.get('data-download--button-modal-url-value'):self.row['modal']=a['data-download--button-modal-url-value']
        if tag=='h2' and 'item-grid-card__title' in a.get('class','').split():self.title=True
    def handle_endtag(self,tag):
        if tag=='h2':self.title=False
    def handle_data(self,text):
        if self.title and self.row is not None:self.row['name']+=text

def mixkit_cards(markup,page):
    parser=_MixkitCards();parser.feed(markup);rows=[]
    for row in parser.rows:
        modal=urljoin(page,row.get('modal',''))
        if not row.get('id','').isdigit() or not row.get('name','').strip():continue
        try:checked_url(modal,{'mixkit.co'})
        except ValueError:continue
        if not re.fullmatch(r'/free-(?:sound-effects|stock-music)/download/\d+/',urlsplit(modal).path):continue
        rows.append(dict(row,name=clean(row['name']),modal=modal))
    return rows

def _text(session,url):
    for _ in range(3):
        checked_url(url,{'mixkit.co'})
        response=session.get(url,timeout=(8,12),stream=True,allow_redirects=False)
        if response.is_redirect:
            url=urljoin(url,response.headers.get('Location',''));response.close();continue
        try:
            response.raise_for_status();data=bytearray();started=time.monotonic()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>2_000_000 or time.monotonic()-started>20:raise ValueError('Website response exceeds search limit')
            return data.decode('utf-8')
        finally:response.close()
    raise ValueError('Website redirect limit reached')

def _mixkit(session,query,kind):
    slug=re.sub('[^a-z0-9 -]','',query.lower());slug=re.sub(r'\s+','-',slug).strip('-')[:110]
    if not slug:return []
    family='free-stock-music' if kind=='music' else 'free-sound-effects'
    page=f'https://mixkit.co/{family}/discover/{slug}/'
    cards=mixkit_cards(_text(session,page),page);out=[]
    words=set(re.findall(r'[a-z]{3,}',query.lower()))
    cards.sort(key=lambda c:len(words & set(re.findall(r'[a-z]{3,}',c['name'].lower()))),reverse=True)
    for card in cards[:2]:
        modal=_text(session,card['modal'])
        urls=re.findall(r'data-download--modal-url-value="([^"]+)"',modal)
        if not urls:continue
        url=html.unescape(urls[0])
        try:checked_url(url,{'assets.mixkit.co'})
        except ValueError:continue
        expected='/active_storage/music/' if kind=='music' else '/active_storage/sfx/'
        if not urlsplit(url).path.startswith(expected):continue
        out.append(dict(provider='mixkit',id=card['id'],name=card['name'],url=url,source_url=page,
            license='https://mixkit.co/license/#'+('musicFree' if kind=='music' else 'sfxFree'),
            author='Mixkit contributor; see source page',attribution='',
            suffix=Path(urlsplit(url).path).suffix.lower(),hosts={'assets.mixkit.co'},original_quality=True,
            retrieval_method='observed public download dialog; targeted search'))
    return out

def relevant_candidate(row,query,category):
    if category not in ('foley','ambience'):return True
    from .relevance import _subjects
    metadata=' '.join([row.get('name',''),row.get('description',''),' '.join(row.get('tags',[]))])
    wanted=_subjects(query);source=_subjects(metadata)
    if wanted:return bool(wanted & source)
    stop={'sound','sounds','effect','effects','ambience','foley','physical','with','the','and','for','from','under','scene'}
    words=lambda text:set(re.findall(r'[a-z]{3,}',text.lower()))-stop
    return bool(words(query)&words(metadata))

def _candidates(session,name,query,keys,kind):
    if name=='mixkit':return _mixkit(session,query,kind)
    if name=='openverse':
        data=_json(session,'https://api.openverse.org/v1/audio/',timeout=(4,8),params=dict(q=query,page_size=8,
            license='cc0,by',filter_dead='true'))
        return [c for row in data.get('results',[]) if (c:=openverse_candidate(row))]
    if name=='commons':
        data=_json(session,'https://commons.wikimedia.org/w/api.php',params=dict(action='query',format='json',
             generator='search',gsrsearch=query+' filetype:audio',gsrnamespace=6,gsrlimit=6,
             prop='imageinfo',iiprop='url|mime|mediatype|size|extmetadata|badfile',iiextmetadatafilter='LicenseUrl|Artist|Attribution|ImageDescription'))
        return [c for row in data.get('query',{}).get('pages',{}).values() if (c:=commons_candidate(row))]
    if name=='jamendo':
        if kind!='music':return []
        data=_json(session,'https://api.jamendo.com/v3.0/tracks/',params=dict(client_id=keys['JAMENDO_CLIENT_ID'],
            format='json',limit=6,search=query,include='licenses+musicinfo',ccnc='false',ccnd='false',ccsa='false',
            vocalinstrumental='instrumental',audiodlformat='mp32'))
        if data.get('headers',{}).get('status')!='success':raise ValueError('Jamendo did not complete the search')
        return [c for row in data.get('results',[]) if (c:=jamendo_candidate(row))]
    if name=='freesound':
        if kind!='sfx':return []
        data=_json(session,'https://freesound.org/apiv2/search/',params=dict(query=query,page_size=6,
            filter='license:"Creative Commons 0" duration:[0.1 TO 90]',
            fields='id,name,username,url,license,duration,tags,type,filesize,previews'),
            headers={'Authorization':'Token '+keys['FREESOUND_API_KEY']})
        out=[]
        for row in data.get('results',[]):
            if not allowed_license(row.get('license','')):continue
            original=bool(keys.get('FREESOUND_ACCESS_TOKEN'))
            url=f'https://freesound.org/apiv2/sounds/{int(row["id"])}/download/' if original else row.get('previews',{}).get('preview-hq-mp3')
            if not url:continue
            out.append(dict(provider=name,id=str(row['id']),name=clean(row['name']),url=url,source_url=row['url'],
                license=row['license'],author=clean(row['username']),tags=row.get('tags',[]),attribution='',
                suffix='.'+row['type'] if original else '.mp3',original_quality=original,
                headers={'Authorization':'Bearer '+keys['FREESOUND_ACCESS_TOKEN']} if original else {},
                hosts={'freesound.org','cdn.freesound.org','cdn.freesound.org.s3.amazonaws.com'}))
        return out
    return []

def _download(session,row,target):
    url=row['url'];headers=row.get('headers',{});started=time.monotonic()
    for _ in range(4):
        checked_url(url,row['hosts'])
        response=session.get(url,headers=headers,timeout=(8,12),stream=True,allow_redirects=False)
        if response.is_redirect:
            url=urljoin(url,response.headers.get('Location',''));headers={};response.close();continue
        break
    else:raise ValueError('Too many audio download redirects')
    tmp=target.with_suffix(target.suffix+'.partial')
    try:
        response.raise_for_status()
        if int(response.headers.get('Content-Length','0'))>MAX_BYTES:raise ValueError('Audio exceeds download limit')
        size=0
        with tmp.open('wb') as f:
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>MAX_BYTES or time.monotonic()-started>35:raise ValueError('Audio exceeds bounded download limit')
                f.write(chunk)
        from .library import decode
        if not size or decode(tmp,rate=8000,limit=1).shape[1]==0:raise ValueError('Provider returned invalid audio')
        tmp.replace(target)
    finally:response.close();tmp.unlink(missing_ok=True)

def _store(session,root,row,query,category,kind):
    suffix=row['suffix']
    if suffix=='.oga':suffix='.ogg'
    if suffix not in ('.wav','.mp3','.ogg','.flac','.aiff','.aif','.m4a'):raise ValueError('Unsupported audio format')
    folder=Path(root)/'library'/('music-online' if kind=='music' else 'sound-online')/category
    folder.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256((row['provider']+':'+row['id']).encode()).hexdigest()[:20]
    target=folder/(row['provider']+'-'+identity+suffix)
    if not target.exists():_download(session,row,target)
    meta={k:v for k,v in row.items() if k not in ('headers','hosts','url','suffix')}
    meta.update(kind=kind,category=category,tags=row.get('tags',[]),search_query=query,
                downloaded_unix=time.time(),audio_quality_verified=False)
    Path(str(target)+'.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    return str(target)

def _generate(session,root,query,category,keys,duration):
    if type(duration) not in (int,float) or not math.isfinite(duration) or not .5<=duration<=10:
        raise ValueError('Free custom effects are bounded to 0.5–10 seconds')
    headers={'xi-api-key':keys['ELEVENLABS_API_KEY']}
    account=_json(session,'https://api.elevenlabs.io/v1/user/subscription',headers=headers)
    # Conservative reserve. Account data, not the model, decides eligibility.
    if not free_generation_allowed(account,max(600,math.ceil(duration*40)+200)):
        raise ValueError('Free allowance could not be confirmed; no generation was sent')
    identity=hashlib.sha256(json.dumps([query,duration,'sound-effects-v2']).encode()).hexdigest()[:20]
    folder=Path(root)/'library/sound-online'/category;folder.mkdir(parents=True,exist_ok=True)
    target=folder/('elevenlabs-'+identity+'.mp3');temp=target.with_suffix('.mp3.partial')
    if not target.exists():
        # Never retry a possibly consumed generation request automatically.
        response=session.post('https://api.elevenlabs.io/v1/sound-generation',headers=headers,
            params={'output_format':'mp3_44100_128'},json={'text':query,'duration_seconds':duration,
            'model_id':'eleven_text_to_sound_v2'},timeout=(8,60),stream=True,allow_redirects=False)
        try:
            response.raise_for_status()
            if response.is_redirect:raise ValueError('Generation endpoint redirected')
            size=0
            with temp.open('wb') as f:
                for chunk in response.iter_content(65536):
                    size+=len(chunk)
                    if size>MAX_BYTES:raise ValueError('Generated effect exceeds size limit')
                    f.write(chunk)
            from .library import decode
            if not size or decode(temp,rate=8000,limit=1).shape[1]==0:raise ValueError('Generated effect is not readable')
            temp.replace(target)
        finally:response.close();temp.unlink(missing_ok=True)
    Path(str(target)+'.json').write_text(json.dumps(dict(provider='elevenlabs',name=query,tags=query.split(),
        source_url='https://elevenlabs.io/sound-effects',license='ElevenLabs Free: non-commercial only',
        attribution='Include elevenlabs.io or 11.ai in the published title, as required by the Free plan.',
        kind='sfx',category=category,original_quality=False,audio_quality_verified=False,
        generation_account_tier='free',duration_requested=duration),indent=2),encoding='utf-8')
    return str(target)

def acquire(root,query,category,limit=2,kind='sfx',duration=3.0):
    if kind=='music' and re.fullmatch('[A-Za-z][A-Za-z0-9 _-]{0,39}',str(category)):
        category=re.sub(r'\s+','-',str(category).strip().lower())
    if kind not in ('music','sfx') or not re.fullmatch('[a-z][a-z0-9_-]{0,39}',str(category)):
        raise ValueError('Invalid sound category or kind')
    if kind=='sfx' and category not in CATEGORIES:raise ValueError('Unsupported sound family')
    if type(limit) is not int or not 1<=limit<=3:raise ValueError('Choose one to three candidates')
    query=' '.join(str(query).split())[:160]
    if not query:return dict(paths=[],notices=['The missing sound needs a search description.'])
    keys=credentials(root);ready=status(root);paths=[];notices=[]
    with requests.Session() as session:
        session.headers.update({'User-Agent':USER_AGENT})
        names=['freesound','openverse','mixkit','commons'] if kind=='sfx' else ['jamendo','openverse','mixkit','commons']
        for name in names:
            if not ready[name]['ready']:continue
            try:
                for row in _candidates(session,name,query,keys,kind)[:limit]:
                    if kind=='sfx' and not relevant_candidate(row,query,category):continue
                    try:paths.append(_store(session,root,row,query,category,kind))
                    except (ValueError,requests.RequestException,OSError):continue
                    if len(paths)>=limit:break
            except (ValueError,requests.RequestException,OSError):
                notices.append(name+': search unavailable; existing local sounds were kept.')
            if len(paths)>=limit:break
        if not paths and kind=='sfx' and ready['elevenlabs']['ready']:
            try:paths.append(_generate(session,root,query,category,keys,duration))
            except (ValueError,requests.RequestException,OSError):
                notices.append('ElevenLabs: free generation unavailable or unconfirmed; no paid retry was made.')
    if not paths:notices.append('No eligible online sound was downloaded for this query.')
    return dict(paths=paths,notices=notices)

class Fallback:
    """One job gets at most three missing-source searches, only after local rejection."""
    def __init__(self,root,enabled=True):
        self.root=Path(root);self.enabled=enabled;self.remaining=3;self.notes=[];self.queries=set()
    def extend(self,index,query,category,kind,brain,listener,progress,duration):
        identity=(kind,category,query)
        if not self.enabled or self.remaining<=0 or identity in self.queries:return index
        self.remaining-=1;self.queries.add(identity)
        progress('Searching online for a missing '+('music track' if kind=='music' else 'sound effect'))
        try:
            found=acquire(self.root,query,category,kind=kind,limit=2,duration=min(10.,max(.5,float(duration))))
        except (ValueError,OSError,requests.RequestException) as exc:
            # Provider messages may contain credential-bearing URLs. Keep only
            # the exception class in ordinary diagnostics.
            logging.getLogger(__name__).warning('Optional online audio lookup failed (%s)',type(exc).__name__)
            self.notes.append('Online sound search is unavailable; existing local sounds were kept. Check the provider settings before trying again.')
            return index
        self.notes.extend(found['notices'])
        if not found['paths']:return index
        from .library import scan
        from .vectors import SoundIndex
        folder=self.root/'library'/('music-online' if kind=='music' else 'sound-online')
        fresh=scan(folder,kind,self.root/'cache/sound',progress=progress)
        assets=list({a.path:a for a in list(index.assets)+fresh}.values())
        return SoundIndex(assets,brain,listener,progress)
