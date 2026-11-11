"""Direct public website videos, explicitly awaiting the owner's review.

This contract is separate from the vision-approved candidate bank. It never
creates a positive model verdict. Search/download errors belong to one query,
and a completed or interrupted bank remains available with every planned slot.
"""
from dataclasses import asdict, is_dataclass
from fractions import Fraction
from html import escape, unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote
import hashlib
import json
import re
import threading
import time
import uuid

import requests

from .recovery import read_json, write_json
from .choice_policy import choice_limit
from .stock_pages import parse_page
from .website_catalogs import CATALOGUE_VERSION,PAGE_HOSTS,media_allowed,CatalogueSearch,parallel_interleave

_LOCK=threading.RLock()
_ACTIVE=set()
SCHEMA='storylens.broll.website-review.v1'


def search_url(query,orientation=None):
    slug=re.sub(r'[^a-z0-9]+','-',query.casefold()).strip('-')[:100]
    if not slug:raise ValueError('Use a saved English footage query.')
    if orientation not in (None,'vertical','horizontal'):raise ValueError('Choose Vertical or Horizontal.')
    if orientation:return 'https://mixkit.co/free-stock-video/discover/'+slug+'/?orientation='+orientation
    return 'https://mixkit.co/free-stock-video/'+slug+'/'


def matches_orientation(width,height,orientation):
    if orientation is None:return True
    return width>0 and height>0 and (height>width if orientation=='vertical' else width>height)


def expanded_queries(queries,visual):
    result=list(dict.fromkeys(queries))
    if re.search(r'\b(?:wi[ -]?fi|router|wireless network)\b',visual,re.I):
        result+=['wifi router','internet connection','wireless network','wifi']
    return list(dict.fromkeys(result))[:6]


def detail_links(markup):
    found=[]
    for raw in re.findall(r'href=["\']([^"\']+)["\']',markup):
        url=urljoin('https://mixkit.co',unescape(raw));p=urlparse(url)
        if (p.scheme=='https' and p.netloc=='mixkit.co' and
            re.fullmatch(r'/free-stock-video/[a-z0-9-]+-\d+/',p.path)):
            clean='https://mixkit.co'+p.path
            if clean not in found:found.append(clean)
    return found


def _html(session,url):
    # Fixed public-site hosts; no credentials, redirects to private networks,
    # challenge bypass, browser cookies, subscription or paid download gates.
    origin=urlparse(url)
    if origin.scheme!='https' or origin.netloc not in PAGE_HOSTS:
        raise ValueError('Choose a supported public video website.')
    page_limit=12_000_000 if origin.netloc=='coverr.co' else 6_000_000
    for _ in range(4):
        with session.get(url,timeout=(10,20),stream=True,allow_redirects=False) as response:
            response.raise_for_status()
            if response.is_redirect:
                target=urljoin(url,response.headers.get('Location',''));p=urlparse(target)
                if p.scheme!='https' or p.netloc!=origin.netloc:raise ValueError('External website redirect skipped.')
                url=target;continue
            data=bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>page_limit:raise ValueError('Website page is too large; source skipped.')
            return data.decode(response.encoding or 'utf-8',errors='replace')
    raise ValueError('The website redirected too many times; source skipped.')


class PublicWebsiteSearch:
    def __init__(self,folder,orientation=None):
        self.cache=Path(folder)/'website-pages';self.cache.mkdir(exist_ok=True)
        self.session=requests.Session()
        self.orientation=orientation

    def page(self,url):
        file=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        if file.is_file():return file.read_text('utf-8')
        markup=_html(self.session,url);file.write_text(markup,encoding='utf-8');return markup

    def __call__(self,query):
        markup=self.page(search_url(query,self.orientation))
        for url in detail_links(markup)[:12]:
            try:
                detail=self.page(url)
                for item in parse_page(url,detail,query):
                    parsed=urlparse(item.download_url)
                    if parsed.scheme!='https' or parsed.netloc!='assets.mixkit.co' or not parsed.path.endswith('.mp4'):continue
                    item.license=('Mixkit Restricted License — personal use only; check source terms'
                        if 'Mixkit Restricted License' in detail else 'Check the Mixkit source page and video licence')
                    yield item
            except (requests.RequestException,ValueError):continue


class WebsiteFallback:
    """Public website choices across catalogues, with isolated source failures."""
    def __init__(self,folder,orientation=None,limit=None):
        self.limit=choice_limit(limit,orientation)
        self.folder=Path(folder);self.orientation=orientation
        self.mixkit=PublicWebsiteSearch(folder,orientation)
        self.catalogues=CatalogueSearch(folder,orientation,self.limit)
        self.provider_catalogues={name:CatalogueSearch(folder,orientation,self.limit) for name in ('coverr','videezy','pexels','pixabay')}
        self.browser_serial=threading.Lock()
        self.source_status=self.catalogues.status
        self.source_details=self.catalogues.details

    def __call__(self,query):
        from contextlib import nullcontext
        from .stock_browser_client import BrowserSearch
        try:parallel_chrome=BrowserSearch(self.folder).parallel_supported()
        except (requests.RequestException,ValueError,OSError) as error:
            parallel_chrome=False;self.source_details['stock_chrome']=str(error)[:350]
        def mixkit():
            for item in self.mixkit(query):
                self.source_status['mixkit']='Website accessible'
                yield item
        def catalogue(name):
            source=self.provider_catalogues[name]
            try:
                with self.browser_serial if name in ('pexels','pixabay') and not parallel_chrome else nullcontext():
                    yield from source.stock_site(name,query) if name in ('pexels','pixabay') else getattr(source,name)(query)
            finally:
                self.source_status.update(source.status);self.source_details.update(source.details)
        def probes():
            self.catalogues.probe_other_catalogues()
            return iter(())
        yield from parallel_interleave([('mixkit',mixkit),
            *[(name,lambda name=name:catalogue(name)) for name in ('coverr','videezy','pexels','pixabay')],
            ('other catalogues',probes)],self.source_status,per_source=self.limit)


def acquire_video(candidate,folder):
    """Save the advertised original once and decode actual video before offering it."""
    from .stock import download
    import av
    url=urlparse(candidate.download_url)
    if not media_allowed(candidate.download_url):
        raise ValueError('This source has no supported public video download.')
    target=Path(folder)/'media'/(hashlib.sha256(candidate.download_url.encode()).hexdigest()+'.mp4')
    session=requests.Session();session.max_redirects=0
    download(candidate.download_url,target,session=session,timeout=(10,30),max_bytes=200*1024*1024)
    with av.open(str(target)) as container:
        if not container.streams.video:raise ValueError('This result is not a playable video.')
        stream=container.streams.video[0];stream.thread_count=1
        decoded=0
        for frame in container.decode(stream):
            decoded+=1
            if decoded==1:
                image=frame.to_image();image.thumbnail((320,320));image.save(target.with_suffix('.jpg'),quality=80)
            if decoded==2:break
        if decoded<2:raise ValueError('This source has too few video frames.')
        duration=float(stream.duration*stream.time_base) if stream.duration else float(container.duration or 0)/av.time_base
        if duration<=0:raise ValueError('This source has no readable video duration.')
        return {'path':str(target.resolve()),'duration':duration,'width':stream.width,
                'height':stream.height,'fps':str(stream.average_rate),'codec':stream.codec_context.name,
                'poster':target.with_suffix('.jpg').relative_to(folder).as_posix()}


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    from hinglish_app.timed_choice_delivery import file_digest
    return file_digest(Path(path))


def new_bank(timeline,slots,orientation=None,limit=None):
    limit=choice_limit(limit,orientation,timeline=timeline)
    rows=[]
    for index,raw in enumerate(slots):
        raw=asdict(raw) if is_dataclass(raw) else raw
        moment=raw['moment'];identity={'index':index,'start':raw['start'],'end':raw['end'],'text':raw['text']}
        rows.append({**identity,'id':_digest(identity),'visual':moment['visual'],
            'queries':list(moment.get('queries') or [moment['visual']]),'status':'pending',
            'options':[],'attempts':[],'selected':None})
    return {'schema':SCHEMA,'review_mode':'website_manual','bank_id':uuid.uuid4().hex,
        'timeline':timeline,'review_options':True,'state':'collecting','collecting':True,
        'slots':rows,'orientation':orientation,'option_limit':limit,'catalogue_version':CATALOGUE_VERSION,'created_at':time.time()}


def save_bank(folder,bank):
    write_json(Path(folder)/'website-review.json',bank)
    # Main Storylens result summaries discover this familiar filename. Strict
    # candidate controllers do not accept this different schema as model approval.
    write_json(Path(folder)/'broll-project.json',bank)
    write_page(folder,bank)


def collect(folder,timeline,slots,limit=None,search=None,acquire=acquire_video,progress=print,api_search=None,orientation=None):
    if api_search is not None:raise ValueError('B-roll uses website search and human review. API search is disabled.')
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    limit=choice_limit(limit,orientation,timeline=timeline)
    if orientation not in (None,'vertical','horizontal'):raise ValueError('Choose Vertical or Horizontal.')
    expected=new_bank(timeline,slots,orientation,limit)
    bank=read_json(folder/'website-review.json') or expected
    if bank.get('schema')!=SCHEMA or _digest(bank['timeline'])!=_digest(timeline) or [s['id'] for s in bank['slots']]!=[s['id'] for s in expected['slots']]:
        raise ValueError('This saved website review belongs to another plan. Keep it and start a new review.')
    if bank.get('orientation')!=orientation:raise ValueError('Keep this review and start a separate result for another orientation.')
    method='api_first' if api_search is not None else 'websites'
    if bank.get('retrieval_method',method)!=method:raise ValueError('Keep the existing review and start a separate run for the new search method.')
    if bank.get('state') in ('collecting','stopped'):
        # A source that timed out before shutdown is not a permanent "no
        # footage" verdict. Revisit only empty groups on the next bounded
        # continuation; keep every prior attempt and all real saved choices.
        for row in bank['slots']:
            if row['status']=='no_results' and not row['options']:
                row.setdefault('previous_attempts',[]).extend(row['attempts'])
                row.update(status='pending',attempts=[])
    bank.update(state='collecting',collecting=True,retrieval_method=method,option_limit=limit);save_bank(folder,bank)
    search=search or WebsiteFallback(folder,orientation,limit)
    try:
        for row in bank['slots']:
            if row['status'] in ('ready','no_results'):continue
            row['status']='searching';save_bank(folder,bank)
            progress(f'Search {row["index"]+1}/{len(bank["slots"])}: {row["visual"]}')
            seen={c['id'] for c in row['options']}
            attempted={(a.get('stage','website'),a['query']) for a in row['attempts'] if a.get('complete')}
            stages=([('api',api_search)] if api_search is not None else [])+[('website',search)]
            for stage,finder in stages:
                if stage=='website' and api_search is not None and row['options']:break
                row['search_queries']=expanded_queries(row['queries'],row['visual'])
                for query in row['search_queries']:
                    if (stage,query) in attempted or len(row['options'])>=limit:continue
                    attempt={'stage':stage,'query':query,'complete':False,'errors':[]};row['attempts'].append(attempt)
                    try:
                        for item in finder(query):
                            if len(row['options'])>=limit:break
                            if item.id in seen or item.kind!='video':continue
                            seen.add(item.id)
                            if item.width and item.height and not matches_orientation(item.width,item.height,orientation):continue
                            try:
                                media=acquire(item,folder);path=Path(media['path']).resolve()
                                if not path.is_relative_to(folder) or not path.is_file():raise ValueError('The collected video is outside this saved review.')
                                if media['duration']<(row['end']-row['start']):raise ValueError('Video shorter than this spoken phrase.')
                                if not matches_orientation(media['width'],media['height'],orientation):
                                    attempt['errors'].append('Skipped a video with the other orientation; no crop was substituted.')
                                    continue
                                row['options'].append({**item.to_dict(),**media,'clip':path.relative_to(folder).as_posix(),
                                    'sha256':file_hash(path),'retrieval_stage':stage,'review_status':'needs_human_review'})
                                save_bank(folder,bank)
                            except Exception as error:attempt['errors'].append(str(error)[:350])
                        attempt['complete']=True
                    except Exception as error:
                        attempt.update(complete=True,error=str(error)[:350])
                    bank.setdefault('source_status',{}).update({stage+':'+k:v for k,v in getattr(finder,'source_status',{}).items()})
                    bank.setdefault('source_details',{}).update(getattr(finder,'source_details',{}))
                    save_bank(folder,bank)
            row['status']='ready' if row['options'] else 'no_results';save_bank(folder,bank)
            progress(f'  {len(row["options"])} playable choices; awaiting your review')
        bank.update(state='complete',collecting=False,finished_at=time.time());save_bank(folder,bank)
    except BaseException:
        bank.update(state='stopped',collecting=False);save_bank(folder,bank);raise
    return bank


def _load(root,folder):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root/'output/broll'):raise ValueError('Open a saved B-roll website review.')
    bank=read_json(folder/'website-review.json',{})
    if bank.get('schema')!=SCHEMA:raise ValueError('Open a saved website review before choosing a video.')
    return folder,bank


def choose(root,folder,index,source_id):
    """Save an explicit decision without requiring an editor or model approval."""
    if type(index) is not int:raise ValueError('Choose an offered keyword moment.')
    with _LOCK:
        folder,bank=_load(root,folder)
        if bank.get('collecting'):raise ValueError('Let the current website search finish; collected choices are kept.')
        row=next((r for r in bank['slots'] if r['index']==index),None)
        if not row:raise ValueError('Choose an offered keyword moment.')
        option=next((c for c in row['options'] if c['id']==source_id),None)
        if source_id is not None and not option:raise ValueError('Choose an offered website video for this moment.')
        if option:
            path=Path(option['path']).resolve()
            if not path.is_relative_to(folder) or not path.is_file() or file_hash(path)!=option['sha256']:
                raise ValueError('The video changed. Collect this exact source again before importing.')
        row.update(selected=source_id,approval={'method':'explicit_user_choice','at':time.time(),
            'sha256':option['sha256'] if option else None})
        save_bank(folder,bank)
        return bank


def prepare_native(folder,option,timeline):
    """Only a selected clip is conformed; keep the original and its full handles."""
    from .conform import make_clip
    path=Path(option['path']).resolve()
    destination=Path(folder)/'native'/(_digest({'sha':option['sha256'],'timeline':timeline})+'.mp4')
    fps=Fraction(str(timeline['fps']))
    duration=int(option['duration']*fps)/float(fps)
    if not destination.is_file():
        make_clip(path,0,duration,timeline['width'],timeline['height'],fps,destination,device='cpu')
    return {'path':str(destination.resolve()),'sha256':file_hash(destination),'duration':duration}


def prepare_choice(root,folder,index,source_id,context):
    from hinglish_app.timed_choice_delivery import TimedChoiceDelivery
    if context.get('host')!='aftereffects':raise ValueError('Connect After Effects for this website review.')
    if type(index) is not int:raise ValueError('Choose an offered keyword moment.')
    with _LOCK:
        bank=choose(root,folder,index,source_id);folder=Path(folder).resolve()
        row=next((r for r in bank['slots'] if r['index']==index),None)
        option=next((c for c in row['options'] if c['id']==source_id),None) if row else None
        if not option:raise ValueError('Choose an offered website video for this moment.')
        path=Path(option['path']).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or file_hash(path)!=option['sha256']:
            raise ValueError('The video changed. Collect this exact source again before importing.')
        timeline=bank['timeline'];fps=Fraction(str(timeline['fps']))
        native=prepare_native(folder,option,timeline)
        manifest=TimedChoiceDelivery(root).prepare({'feature':'broll','bank_id':bank['bank_id'],
            'slot_id':row['id'],'slot_fingerprint':_digest({k:row[k] for k in ('start','end','text')}),
            'asset_id':source_id,'asset_path':native['path'],'asset_sha256':native['sha256'],
            'source_in':0,'source_duration':native['duration'],'start_frame':round(row['start']*fps),
            'end_frame':round(row['end']*fps),'fps':str(fps),'width':timeline['width'],'height':timeline['height']},context)
        return manifest


def write_page(folder,bank):
    from .report import STYLE,_clock
    from hinglish_app import BRIDGE_URL,app_token,embed_token
    cards=[];count=sum(len(s['options']) for s in bank['slots'])
    orientation=bank.get('orientation');limit=bank.get('option_limit',5)
    format_buttons=''.join('<button type="button" class="format-choice" data-orientation="'+value+'" aria-pressed="'+str(orientation==value).lower()+'"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 20 20"><rect x="'+('5' if value=='vertical' else '2')+'" y="'+('2' if value=='vertical' else '5')+'" width="'+('10' if value=='vertical' else '16')+'" height="'+('16' if value=='vertical' else '10')+'" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'+label+'</button>' for value,label in [('vertical','Vertical'),('horizontal','Horizontal')])
    for row in bank['slots']:
        options=''.join('<div class="choice-card'+(' selected' if row.get('selected')==o['id'] else '')+'"><video controls muted playsinline preload="none" '+('poster="'+escape(o['poster'],quote=True)+'" ' if o.get('poster') else '')+'src="'+escape(o['clip'],quote=True)+'"></video>'
            '<div class="choice-actions"><button class="choose" '+('disabled ' if bank['collecting'] else '')+'data-slot="'+str(row['index'])+'" data-id="'+escape(o['id'],quote=True)+'">Option '+str(n)+'</button>'
            '<a class="source" target="_blank" rel="noopener noreferrer" href="'+escape(o['page_url'],quote=True)+'">Source</a></div>'
            '<small class="source">'+escape(o.get('license') or 'Check source terms')+'</small></div>' for n,o in enumerate(row['options'],1))
        status={'pending':'Waiting to search','searching':'Searching website…','ready':f'{len(row["options"])} playable choices',
                'no_results':'No playable result collected from this website'}.get(row['status'],row['status'])
        cards.append('<section class="moment review-bank" data-slot="'+str(row['index'])+'"><div><div class="time">'+_clock(row['start'])+' – '+_clock(row['end'])+'</div>'
            '<p class="said">“'+escape(row['text'])+'”</p><div class="moment-meta"><span class="idea">'+escape(row['visual'])+'</span>'
            '<span class="idea">Search: '+escape(', '.join(row['queries']))+'</span><span class="idea">'+escape(status)+'</span></div>'
            '</div><button class="none" data-slot="'+str(row['index'])+'" '+('disabled' if bank['collecting'] else '')+'>No B-roll</button><div class="choice-bank">'+(options or '<p class="empty">'+escape(status)+'. Other websites may have footage.</p>')+'</div></section>')
    sources=''.join('<p>'+escape(k)+' · '+escape(v)+'</p>' for k,v in bank.get('source_status',{}).items())
    errors=''.join('<p>'+escape(row['visual'])+': '+escape(str(a.get('error') or '; '.join(a.get('errors',[]))))+'</p>' for row in bank['slots'] for a in row['attempts'] if a.get('error') or a.get('errors'))
    errors+=''.join('<p>'+escape(k)+': '+escape(v)+'</p>' for k,v in bank.get('source_details',{}).items())
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>B-roll website review</title><style>'''+STYLE+'''
.moment{display:block}.choice-bank{margin-top:10px}.choose{font-size:12px;padding:3px 9px;height:28px}.choice-card small{display:block;font-size:11px;margin-top:5px}.editor-exports{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.choice-card.selected{border-color:var(--good)}.choice-card video{height:'''+('250px' if orientation=='vertical' else '160px')+'''}details{color:var(--muted);font-size:12px}.formats{display:flex;gap:6px;margin-bottom:14px}.format-choice{display:flex;align-items:center;gap:7px;height:34px;padding:4px 11px;font-size:13px}.format-choice[aria-pressed="true"]{background:#30363f;border-color:#76818d}</style>
<script src="'''+BRIDGE_URL+'''/feedback.js"></script><script src="'''+BRIDGE_URL+'''/broll-editor-choices.js?v=website-1"></script></head><body>
<header><div><h1>B-roll review · '''+escape(bank['timeline']['name'])+'''</h1><small>'''+str(count)+' playable videos · '+str(len(bank['slots']))+''' keyword moments</small></div><span id="status" role="status"></span></header>
<main><div class="formats" role="group" aria-label="B-roll format">'''+format_buttons+'''</div><div class="editor-exports"><div id="editors"></div><span class="idea">You review and choose · Website results are not vision-checked</span></div>
<p class="summary">'''+('Website search is running. Completed choices are kept.' if bank['collecting'] else 'Search finished.' if bank['state']=='complete' else 'Search stopped. Collected videos and all keyword moments are kept.')+'''</p>
'''+('<button id="continueSearch">Search missing keywords again</button>' if not bank['collecting'] and any(not s['options'] for s in bank['slots']) else '')+''.join(cards)+'''<footer>Up to '''+('six' if limit==6 else str(limit))+''' videos per keyword. Source originals and original speech timestamps are kept. Review the clip and its source terms before choosing it.</footer>
'''+('<details><summary>Technical details · source availability</summary>'+sources+errors+'</details>' if sources or errors else '')+'''</main><script>
const folder=__FOLDER__,token=__TOKEN__,selected=__SELECTED__;let busy=false;
const status=document.querySelector('#status');document.documentElement.dataset.token=token;
const api=async value=>{const r=await window.storylensFetch('__BRIDGE__/api/panel/broll-website',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},body:JSON.stringify({...value,folder})});return window.storylensResponse(r)};
const editor=window.storylensBrollEditors.render(document.querySelector('#editors'),{api,hosts:['aftereffects'],onStatus:message=>status.textContent=message,
onConnect:async()=>{for(const [slot,id] of Object.entries(selected)){const result=await editor.select({slot_index:Number(slot),source_id:id});status.textContent=result.message;}}});
document.querySelectorAll('.choose,.none').forEach(button=>button.onclick=async()=>{if(busy)return;busy=true;button.disabled=true;status.textContent='Saving your choice…';
try{const slot=Number(button.dataset.slot),id=button.dataset.id||null;
await api({action:'choose',slot_index:slot,source_id:id});if(id)selected[slot]=id;else delete selected[slot];
button.closest('.moment').querySelectorAll('.choice-card').forEach(c=>c.classList.toggle('selected',id&&c===button.closest('.choice-card')));
status.textContent=id?'Choice saved. Connect After Effects when ready.':'No B-roll chosen. Existing editor layers are kept.';
if(editor.active&&id){const result=await editor.select({slot_index:slot,source_id:id});status.textContent=result.message;}
}catch(error){status.textContent=window.storylensError(error);}finally{busy=false;button.disabled=false;}});
const retry=document.querySelector('#continueSearch');if(retry)retry.onclick=async()=>{retry.disabled=true;try{await api({action:'continue'});location.reload()}catch(error){status.textContent=window.storylensError(error);retry.disabled=false;}};
document.querySelectorAll('.format-choice').forEach(button=>button.onclick=async()=>{if(busy)return;busy=true;button.disabled=true;try{const result=await api({action:'start',orientation:button.dataset.orientation,limit:button.dataset.orientation==='horizontal'?2:5});location.href=result.page}catch(error){status.textContent=window.storylensError(error);button.disabled=false;busy=false;}});
if(__COLLECTING__)setTimeout(()=>{if(!busy&&![...document.querySelectorAll('video')].some(v=>!v.paused))location.reload()},15000);
</script></body></html>'''
    safe=lambda v:json.dumps(v,ensure_ascii=False).replace('<','\\u003c')
    page=page.replace('__FOLDER__',safe(str(Path(folder).resolve()))).replace('__TOKEN__',safe(app_token())).replace('__BRIDGE__',BRIDGE_URL).replace('__COLLECTING__',str(bank['collecting']).lower()).replace('__SELECTED__',safe({str(s['index']):s['selected'] for s in bank['slots'] if s.get('selected')}))
    destination=Path(folder)/'report.html';temporary=destination.with_name('report.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(embed_token(page),encoding='utf-8')
        for attempt in range(6):
            try:temporary.replace(destination);break
            except PermissionError:
                if attempt==5:raise
                time.sleep(.05*2**attempt)
    finally:temporary.unlink(missing_ok=True)


def finish_plans(root,plans,output,store,limit=None,progress=print,orientation=None):
    """Normal Storylens planning feeds the website collector before Vision loads."""
    from .pipeline import timeline_to_dict
    from .report import write_index
    results=[]
    for timeline,folder,summary,profile,slots,phrases in plans:
        bank=collect(folder,timeline_to_dict(timeline),slots,
            limit=limit,progress=progress,orientation=orientation)
        found=sum(bool(s['options']) for s in bank['slots'])
        results.append({'name':timeline.name,'folder':folder.name,'filled':found,
                        'moments':len(slots),'xml':timeline.xml_path})
    write_index(Path(output)/'index.html',results,[])
    write_json(Path(output)/'result.json',{'results':results,'notes':[],
        'review_mode':'website_manual','human_review_required':True})
    result=Path(output)/(results[0]['folder']+'/report.html' if len(results)==1 else 'index.html')
    store.data.update(state='complete',result=str(result));store.save()
    return result


def start_saved_review(root,folder,orientation=None,limit=None):
    """Start a CPU-only review from a real previously saved local-model plan."""
    from datetime import datetime
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root/'output/broll') or not folder.is_dir():
        raise ValueError('Open the existing B-roll result before searching websites.')
    if orientation not in (None,'vertical','horizontal'):raise ValueError('Choose Vertical or Horizontal.')
    if (folder/'plan-provenance.json').is_file():
        provenance=read_json(folder/'plan-provenance.json',{})
        journal_path=Path(provenance.get('source_journal','')).resolve()
        if not journal_path.is_relative_to(root/'output/broll') or journal_path.name!='recovery.json':
            raise ValueError('Reopen the original keyword review.')
        folder=journal_path.parent/folder.name
    journal=read_json(folder.parent/'recovery.json',{})
    plan=next((p for p in journal.get('plans',[]) if p.get('folder')==folder.name),None)
    job=next((j for j in journal.get('jobs',[]) if j.get('folder')==folder.name),None)
    if not plan or not job:raise ValueError('This result has no saved keyword plan. Run Add B-roll with your video first.')
    limit=choice_limit(limit,orientation,timeline=job['timeline'])
    with _LOCK:
        link_file=folder/('website-review-'+str(orientation or 'any')+'-'+str(limit)+'-catalogues'+str(CATALOGUE_VERSION)+'-link.json')
        link=read_json(link_file,{})
        destination=Path(link.get('folder','')).resolve()
        if destination.is_relative_to(root/'output/broll') and (destination/'website-review.json').is_file():
            return {'page':'/broll-output/'+destination.relative_to(root/'output/broll').as_posix()+'/report.html'}
        destination=root/'output/broll'/(datetime.now().strftime('%Y%m%d-%H%M%S-website-')+str(orientation or 'any')+'-'+uuid.uuid4().hex[:6])/folder.name
        destination.mkdir(parents=True)
        bank=new_bank(job['timeline'],plan['slots'],orientation,limit);save_bank(destination,bank)
        write_json(destination/'plan-provenance.json',{'source_journal':str(folder.parent/'recovery.json'),
            'source_journal_sha256':file_hash(folder.parent/'recovery.json'),
            'planning':'Saved local-model plan; no fresh transcription or inference',
            'slots':plan['slots']})
        write_json(link_file,{'folder':str(destination)})
        _ACTIVE.add(str(destination))
        def run():
            def progress(message):
                with (destination/'collection.log').open('a',encoding='utf-8') as log:log.write(message+'\n')
            try:collect(destination,job['timeline'],plan['slots'],progress=progress,limit=limit,orientation=orientation)
            except Exception as error:progress('Collection stopped: '+str(error))
            finally:
                with _LOCK:_ACTIVE.discard(str(destination))
        threading.Thread(target=run,name='B-roll public website search',daemon=True).start()
        return {'page':'/broll-output/'+destination.relative_to(root/'output/broll').as_posix()+'/report.html'}


def continue_review(root,folder):
    """Retry only empty keyword groups; retain all actual media and choices."""
    with _LOCK:
        folder,bank=_load(root,folder)
        if str(folder) in _ACTIVE:return {'started':False,'state':'collecting'}
        provenance=read_json(folder/'plan-provenance.json',{})
        slots=provenance.get('slots')
        if not slots:raise ValueError('This review has no original saved keyword plan. Start a new review from the saved video.')
        for row in bank['slots']:
            if row['options']:continue
            row.setdefault('previous_attempts',[]).extend(row['attempts'])
            row.update(attempts=[],status='pending')
        bank.update(state='collecting',collecting=True);save_bank(folder,bank)
        _ACTIVE.add(str(folder))
        def run():
            try:
                def progress(message):
                    with (folder/'collection.log').open('a',encoding='utf-8') as log:log.write(message+'\n')
                collect(folder,bank['timeline'],slots,limit=bank.get('option_limit',6),search=WebsiteFallback(folder,bank.get('orientation')),progress=progress,orientation=bank.get('orientation'))
            finally:
                with _LOCK:_ACTIVE.discard(str(folder))
        threading.Thread(target=run,name='B-roll missing website keywords',daemon=True).start()
        return {'started':True,'state':'collecting'}
