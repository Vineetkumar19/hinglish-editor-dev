"""Durable, resumable screenshot collections. Only verified source bytes are exported."""
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import zipfile

from PIL import Image,ImageOps

from .analysis import analyse
from .core import MAX_UPLOAD,validate_screenshot,similarity,photo_filename,pixel_hash
from .network import Fetcher
from .sources import Sources
from .search_agents import heading_query,search_candidates
from .quality import meets_quality

TERMINAL={'done','failed','cancelled','interrupted','archived'}

def write_json(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');temp.replace(path)

def identifier(value,length=12):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}',value):
        raise ValueError('Photo collection invalid: reopen a saved collection from this tool.')
    return value

def decode(data):
    with Image.open(io.BytesIO(data)) as opened:
        if opened.width*opened.height>60_000_000 or opened.format not in ('JPEG','PNG','WEBP','AVIF','GIF'):
            raise ValueError('Photo source invalid: unsupported image dimensions or format.')
        fmt=opened.format;image=ImageOps.exif_transpose(opened).convert('RGB');image.load()
        return image,fmt

class PhotoService:
    def __init__(self,root,*,analyser=analyse,finder=None,fetcher_factory=None):
        self.root=Path(root).resolve();self.base=self.root/'output/photo-collector'
        self.cache=self.root/'cache/photo-collector';self.trash=self.base/'.trash'
        for path in (self.base,self.cache/'jobs',self.cache/'uploads',self.cache/'images',self.trash):path.mkdir(parents=True,exist_ok=True)
        self.analyser=analyser;self.finder=finder;self.fetcher_factory=fetcher_factory or (lambda cancel:Fetcher(cancel=cancel))
        from .aftereffects import import_photos
        self.importer=import_photos;self.ae_lock=threading.Lock()
        self.lock=threading.RLock();self.jobs={};self.events={};self.threads={}
        for path in (self.cache/'jobs').glob('*.json'):
            try:
                job=json.loads(path.read_text('utf8'));identifier(job['id'])
                if job.get('status') not in TERMINAL:job.update(status='interrupted',stage='Interrupted. Saved photos are kept; continue this collection.')
                self.jobs[job['id']]=job
            except (OSError,ValueError,KeyError):continue

    def _save(self,job):write_json(self.cache/'jobs'/(job['id']+'.json'),job)
    def _get(self,id):
        identifier(id)
        if id not in self.jobs:raise ValueError('Photo collection missing: choose an existing saved collection.')
        return self.jobs[id]
    def _folder(self,job):
        target=(self.base/job['folder']).resolve()
        if target==self.base.resolve() or not target.is_relative_to(self.base.resolve()):
            raise ValueError('Photo collection invalid: this folder is outside the collection library.')
        return target
    def update(self,id,**values):
        with self.lock:
            job=self._get(id);job.update(values);job['updated']=time.time();self._save(job)
    def progress(self,id,message):self.update(id,stage=str(message))
    def upload(self,data):
        info=validate_screenshot(data);id=uuid.uuid4().hex
        path=self.cache/'uploads'/(id+info['extension']);path.write_bytes(data)
        return {'upload_id':id,**info}
    def _upload_path(self,id):
        identifier(id,32)
        found=list((self.cache/'uploads').glob(id+'.*'))
        if len(found)!=1 or not found[0].resolve().is_relative_to((self.cache/'uploads').resolve()):
            raise ValueError('Photo screenshot missing: add your screenshot again.')
        return found[0]
    def start(self,payload):
        if not isinstance(payload,dict):raise ValueError('Photo settings invalid: add one screenshot to start.')
        source=self._upload_path(payload.get('upload_id'))
        from hinglish_niche.profiles import valid_profile
        profile=valid_profile(payload.get('profile','general'))
        name=' '.join(str(payload.get('name') or '').split())[:100]
        min_edge=payload.get('min_edge',0)
        if type(min_edge) is not int or min_edge not in (0,1280,1920,3840):raise ValueError('Photo settings invalid: choose an available original-photo size.')
        destination=payload.get('destination','folder')
        if destination not in ('folder','aftereffects'):raise ValueError('Photo settings invalid: Premiere Pro and CapCut are not connected for photo import yet. Choose Folder or After Effects.')
        with self.lock:
            if any(job['status'] not in TERMINAL for job in self.jobs.values()):
                raise ValueError('Photo collection busy: let the current collection finish, or cancel it first.')
            id=uuid.uuid4().hex[:12];folder=datetime.now().strftime('%Y%m%d-%H%M%S-')+id
            target=self.base/folder;target.mkdir()
            for sub in ('photos','originals','crops','candidates'): (target/sub).mkdir()
            with Image.open(source) as image:ImageOps.exif_transpose(image).convert('RGB').save(target/'screenshot.png')
            job={'id':id,'folder':folder,'title':name or 'Photo collection','profile':profile,'status':'queued',
                'created':time.time(),'updated':time.time(),'stage':'Preparing the screenshot…','photos':[],
                'error':None,'destination':destination,'min_edge':min_edge,'named':bool(name),'source_hash':hashlib.sha256(source.read_bytes()).hexdigest()}
            job['selective_downloads']=payload.get('workflow')=='selective'
            job['previews']=bool(payload.get('previews',False))
            if job['previews']:
                from .previews import prepare
                job['photos']=prepare(target)
            self.jobs[id]=job;self._save(job);self._launch(id)
            return self.snapshot(id)
    def _launch(self,id):
        event=threading.Event();self.events[id]=event
        thread=threading.Thread(target=self._run,args=(id,event),daemon=True,name='photo-collector-'+id)
        self.threads[id]=thread;thread.start()
    def wait(self,id,timeout=10):
        if id in self.threads:self.threads[id].join(timeout)
    def snapshot(self,id):
        with self.lock:
            job=json.loads(json.dumps(self._get(id)))
        states=[row.get('status') for row in job['photos']]
        job['counts']={'total':len(states),'saved':states.count('saved'),'duplicates':states.count('duplicate'),
            'found':states.count('ready')+states.count('saved')+states.count('duplicate'),
            'low_quality':states.count('low_quality'),'review':states.count('review'),'missing':states.count('missing'),
            'previews':sum(bool(row.get('preview_file')) and row['status'] not in ('ready','saved','duplicate') for row in job['photos'])}
        if job['status']=='done' and job['counts']['total'] and not job['counts']['found']:
            size=job.get('min_edge',0)
            job['stage']=(f'No clean originals meet the selected {size}px size. ' if size else 'No source photos could be confirmed. ')+ 'Smaller or uncertain results are held. Continue the saved search for originals; existing files are kept.'
        job['output_folder']=str(self._folder(job))
        return job
    def history(self):return [self.snapshot(id) for id in sorted(self.jobs,key=lambda value:self.jobs[value]['created'],reverse=True)]
    def cancel(self,id):
        with self.lock:
            job=self._get(id)
            if id in self.events and job['status'] not in TERMINAL:
                self.events[id].set();self.update(id,stage='Stopping after the current operation; saved photos are kept.')
        return self.snapshot(id)
    def retry(self,id,min_edge=None,previews=None):
        with self.lock:
            job=self._get(id)
            if job['status'] not in TERMINAL or job['status']=='archived':raise ValueError('Photo collection busy: wait for it to stop before continuing.')
            if any(row['status'] not in TERMINAL for row in self.jobs.values()):raise ValueError('Photo collection busy: another collection is still active.')
            self.apply_quality(id,min_edge)
            if previews and not job.get('previews'):
                from .previews import prepare
                old={row['id']:row for row in job['photos']};generated=prepare(self._folder(job))
                self.update(id,previews=True,photos=[{**row,**old.get(row['id'],{}),'preview_file':row['preview_file'],'preview_width':row['preview_width'],'preview_height':row['preview_height']} for row in generated])
            self.update(id,status='queued',error=None,stage='Continuing saved photo matches…');self._launch(id)
        return self.snapshot(id)

    def _cached_image(self,url,fetcher):
        key=hashlib.sha256(url.encode()).hexdigest();target=self.cache/'images'/(key+'.bin')
        if target.is_file():
            try:return decode(target.read_bytes())[0]
            except (OSError,ValueError):pass
        result=fetcher.get(url,limit=3*1024*1024)
        image,_=decode(result['data']);target.write_bytes(result['data']);return image

    def _original(self,url,fetcher):
        key=hashlib.sha256(url.encode()).hexdigest();target=self.cache/'images'/('original-'+key+'.bin');meta=target.with_suffix('.json')
        if target.is_file() and meta.is_file() and target.stat().st_size<=25*1024*1024:
            try:
                data=target.read_bytes();decode(data);return {**json.loads(meta.read_text('utf8')),'data':data}
            except (OSError,ValueError):pass
        result=fetcher.get(url);decode(result['data']);target.write_bytes(result['data'])
        write_json(meta,{key:value for key,value in result.items() if key!='data'})
        return result

    def _run(self,id,cancel):
        try:
            self.update(id,status='running',error=None)
            job=self._get(id);folder=self._folder(job);plan_path=folder/'plan.json'
            if job.get('destination')=='aftereffects' and not job.get('ae_expected'):
                self.progress(id,'Connecting to your open After Effects project…')
                try:
                    with self.ae_lock:probe=self.importer(folder,job,[])
                    self.update(id,ae_expected=probe['project'],ae_status='connected',ae_error=None)
                except Exception as error:
                    from hinglish_app.user_messages import failure
                    self.update(id,ae_status='failed',ae_error=failure(error))
            if plan_path.is_file():plan=json.loads(plan_path.read_text('utf8'))
            else:
                plan=self.analyser(self.root,folder,folder/'screenshot.png',job['profile'],lambda m:self.progress(id,m),cancel)
                write_json(plan_path,plan)
                old={row['id']:row for row in job['photos']}
                self.update(id,title=job['title'] if job.get('named') else plan.get('title') or job['title'],photos=[{**old.get(row['id'],{}),**row,'status':old.get(row['id'],{}).get('status','pending')} for row in plan['photos']])
            rows=self._get(id)['photos']
            if not rows:raise ValueError('Photo tiles missing: no main result images were found.')
            with Image.open(folder/'screenshot.png') as image:screenshot=image.convert('RGB')
            for row in rows:
                x,y,w,h=row['box'];screenshot.crop((x,y,x+w,y+h)).save(folder/'crops'/f'{row["id"]:03d}.png')
            finder=self.finder or Sources(self.root,lambda m:self.progress(id,m))
            fetcher=self.fetcher_factory(cancel);pool=[];seen_urls=set()
            def extend(values):
                for item in values:
                    if item.get('url') and item['url'] not in seen_urls:seen_urls.add(item['url']);pool.append(item)
            if any(row['status'] not in ('ready','saved','duplicate') for row in rows):
                self.progress(id,'Searching public sources for the screenshot’s photos…')
                try:extend(finder.images(plan.get('query') or rows[0]['query'],limit=50))
                except Exception as error:self.progress(id,'The first image search was unavailable; trying individual photo captions…')
            global_pool=list(pool)
            for number,row in enumerate(rows,1):
                if cancel.is_set():raise InterruptedError('Photo collection cancelled; saved photos are kept.')
                if row['status'] in ('ready','saved','duplicate'):continue
                pool=list(global_pool);seen_urls={item['url'] for item in pool}
                self.progress(id,f'Finding photo {number} of {len(rows)}…')
                crop=Image.open(folder/'crops'/f'{row["id"]:03d}.png').convert('RGB')
                best=None;low=None;winner=None;checked=set();errors=[]
                row['search_agents']=[]
                for step in range(4):
                    if step==0:
                        self.progress(id,f'Finding photo {number} of {len(rows)} by image details and heading…')
                        for batch in search_candidates(finder,row,cancel):
                            extend(batch['candidates'])
                            row['search_agents'].append({key:batch[key] for key in ('agent','query','error')}|
                                                        {'candidates':len(batch['candidates'])})
                            if batch['error']:errors.append(batch['error'])
                            self.update(id,photos=rows)
                    if step==1:
                        try:extend(finder.images(row['query']+' '+row.get('publisher','')+' high resolution original photo',limit=30))
                        except Exception as error:errors.append(str(error))
                    if step==2 and hasattr(finder,'page_images'):
                        query=heading_query(row) or row['query']
                        try:extend(finder.page_images(query,fetcher,limit=5))
                        except Exception as error:errors.append(str(error))
                    if step==3 and hasattr(finder,'google_images'):
                        # Use the unquoted visible heading as a second index
                        # query too: truncated titles may fail exact phrases.
                        queries=list(dict.fromkeys(filter(None,[heading_query(row,quoted=False),row['query']+' '+row.get('publisher','')])) )
                        for query in queries:
                            try:extend(finder.google_images(query,fetcher,limit=25))
                            except Exception as error:errors.append(str(error))
                    for candidate in pool:
                        if candidate['url'] in checked:continue
                        if cancel.is_set():raise InterruptedError('Photo collection cancelled; saved photos are kept.')
                        checked.add(candidate['url'])
                        if len(checked)>180:break
                        try:
                            if candidate.get('thumbnail') and candidate['thumbnail']!=candidate['url']:
                                thumb=self._cached_image(candidate['thumbnail'],fetcher)
                            else:thumb=decode(self._original(candidate['url'],fetcher)['data'])[0]
                            match=similarity(crop,thumb)
                            if best is None or match['score']>best[0]['score']:best=(match,candidate,thumb)
                            plausible=match['matched'] or (match.get('inliers',0)>=8 and match.get('coverage',0)>=.12 and match.get('agreement',0)>=.45)
                            if not plausible:continue
                            result=self._original(candidate['url'],fetcher);original,fmt=decode(result['data'])
                            verified=similarity(crop,original)
                            if not verified['matched']:continue
                            digest=pixel_hash(original)
                            content_edge=max(verified.get('effective_width',0),verified.get('effective_height',0))
                            if not meets_quality({**row,'width':original.width,'height':original.height,'effective_width':verified.get('effective_width'),'effective_height':verified.get('effective_height'),'match':verified},job.get('min_edge',0)):
                                if low is None or content_edge>max(low[4].get('effective_width',0),low[4].get('effective_height',0)):low=(candidate,result,original,fmt,verified)
                                continue
                            quality=min(original.width,verified.get('effective_width',0))*min(original.height,verified.get('effective_height',0))
                            if winner is None or quality>winner[0]:winner=(quality,candidate,result,original,fmt,verified)
                        except InterruptedError:raise
                        except Exception as error:errors.append(str(error))
                if winner:
                    _,candidate,result,original,fmt,verified=winner;digest=pixel_hash(original)
                    duplicate=next((old for old in rows if old.get('pixel_hash')==digest and old.get('status') in ('saved','ready')),None)
                    filename=duplicate['file'] if duplicate else photo_filename(row['id'],candidate.get('title') or row.get('caption') or plan['title'],digest,fmt)
                    (folder/'originals').mkdir(exist_ok=True)
                    if not duplicate:(folder/'originals'/filename).write_bytes(result['data'])
                    row.update(status='duplicate' if duplicate else 'ready',origin='original',file=filename,pixel_hash=digest,
                        width=original.width,height=original.height,source_url=result['url'],source_page=candidate.get('page',''),
                        effective_width=verified.get('effective_width'),effective_height=verified.get('effective_height'),
                        source_title=candidate.get('title',''),license=candidate.get('license','Usage rights unverified.'),
                        match=verified,search_agent=candidate.get('search_agent','source-page-or-shared-search'),duplicate_of=duplicate['id'] if duplicate else None)
                    self.update(id,photos=rows)
                else:
                    if low:
                        candidate,result,original,fmt,verified=low
                        original.thumbnail((400,400));original.save(folder/'candidates'/f'{row["id"]:03d}.png')
                        with Image.open(io.BytesIO(result['data'])) as source:width,height=source.size
                        row.update(status='low_quality',width=width,height=height,source_url=result['url'],source_page=candidate.get('page',''),match=verified)
                    elif best and best[0]['score']>=.58:
                        best[2].save(folder/'candidates'/f'{row["id"]:03d}.png')
                        row.update(status='review',suggestion={**best[1],'match':best[0]})
                    else:row.update(status='missing')
                    row['technical_details']=errors[-4:]
                    self.update(id,photos=rows)
            self._bundle(id)
            count=self.snapshot(id)['counts']
            self.update(id,stage=f'{count["found"]} source photos ready · {count["low_quality"]} below your size limit · {count["review"]+count["missing"]} unresolved. Choose Download all or individual photos.')
            if (job.get('destination')=='aftereffects' or job.get('ae_requested')) and (count['found'] or count.get('previews')):
                if job.get('ae_expected') or job.get('ae_requested'):
                    try:self.send_ae(id)
                    except Exception:pass
            elif job.get('destination')=='aftereffects' and not count['found']:
                self.update(id,ae_status='no_photos',stage='No confirmed photos meet your size limit. Nothing was imported into After Effects; the source-size results are shown below.')
            self.update(id,status='done')
        except InterruptedError as error:self.update(id,status='cancelled',stage=str(error))
        except Exception as error:
            from hinglish_app.user_messages import failure
            self.update(id,status='failed',stage='The collection stopped; saved photos and your screenshot are kept.',error=failure(error))

    def _bundle(self,id):
        job=self._get(id);folder=self._folder(job)
        def safe(value):
            value=str(value or '')
            return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
        with (folder/'sources.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['Photo','Caption','Status','File','Width','Height','Source page','Image URL','Usage rights'])
            for row in job['photos']:writer.writerow([safe(row.get(key,'')) for key in ('id','caption','status','file','width','height','source_page','source_url','license')])
        write_json(folder/'collection.json',{'title':job['title'],'photos':job['photos'],'source_hash':job['source_hash']})
        with zipfile.ZipFile(folder/'photos.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
            allowed={row.get('file') for row in job['photos'] if row['status'] in ('saved','duplicate')}
            for file in (folder/'photos').iterdir():
                if file.is_file() and file.name in allowed:archive.write(file,'photos/'+file.name)
            archive.write(folder/'sources.csv','sources.csv');archive.write(folder/'collection.json','collection.json')

    def _recover_smaller_originals(self,job):
        """Restore verified small originals from their existing download cache, without a web search."""
        folder=self._folder(job);rows=job['photos'];index=None
        for row in rows:
            if row.get('status')!='low_quality' or not (row.get('match') or {}).get('matched') or not row.get('source_url'):continue
            url=row['source_url'];cached=self.cache/'images'/('original-'+hashlib.sha256(url.encode()).hexdigest()+'.bin')
            if not cached.is_file():
                if index is None:
                    index={}
                    for meta in (self.cache/'images').glob('original-*.json'):
                        try:index[json.loads(meta.read_text('utf8')).get('url')]=meta.with_suffix('.bin')
                        except (OSError,ValueError):pass
                cached=index.get(url)
            if not cached or not cached.is_file() or not cached.resolve().is_relative_to((self.cache/'images').resolve()):continue
            try:
                data=cached.read_bytes();image,fmt=decode(data);digest=pixel_hash(image)
                filename=photo_filename(row['id'],row.get('caption') or 'Photo',digest,fmt)
                target=folder/'originals'/filename;target.parent.mkdir(exist_ok=True)
                if not target.exists():target.write_bytes(data)
                row.update(status='ready',origin='original',file=filename,pixel_hash=digest,width=image.width,height=image.height)
            except (OSError,ValueError):continue

    def apply_quality(self,id,min_edge):
        if min_edge is None:return
        if type(min_edge) is not int or min_edge not in (0,1280,1920,3840):raise ValueError('Photo settings invalid: choose an available original-photo size.')
        job=self._get(id)
        if min_edge==0:self._recover_smaller_originals(job)
        for row in job['photos']:
            if row['status'] in ('ready','saved','duplicate'):
                if not meets_quality(row,min_edge):row['status']='low_quality'
        self.update(id,min_edge=min_edge,photos=job['photos'])

    def save(self,id,item=None,min_edge=None):
        with self.lock:
            job=self._get(id);folder=self._folder(job)
            if job['status']=='archived':raise ValueError('Photo collection archived: restore it before saving photos.')
            self.apply_quality(id,min_edge)
            rows=job['photos'] if item is None else [row for row in job['photos'] if str(row['id'])==str(item)]
            available=[row for row in rows if row['status'] in ('ready','saved','duplicate')]
            if not available:raise ValueError('Photo file missing: no confirmed photos meet your size limit yet. Wait for more results or choose another collection.')
            for row in available:
                target=(folder/'photos'/row['file']).resolve();source=(folder/'originals'/row['file']).resolve()
                if not target.is_relative_to((folder/'photos').resolve()) or not source.is_relative_to((folder/'originals').resolve()):raise ValueError('Photo file invalid: reopen the collection.')
                if not target.is_file():
                    if not source.is_file():raise ValueError('Photo file missing: continue this collection to recover its original.')
                    shutil.copyfile(source,target)
                row['downloaded']=True
                if row['status']!='duplicate':row['status']='saved'
            self.update(id,photos=job['photos']);self._bundle(id)
        return self.snapshot(id)

    def send_ae(self,id,min_edge=None):
        try:return self._send_ae(id,min_edge)
        except Exception as error:
            if isinstance(id,str) and id in self.jobs:
                from hinglish_app.user_messages import failure
                self.update(id,ae_status='failed',ae_error=failure(error))
            raise

    def _send_ae(self,id,min_edge=None):
        with self.ae_lock:
            job=self._get(id)
            if job['status']=='archived':raise ValueError('Photo collection archived: restore it before importing photos.')
            if job.get('ae_status')=='importing':raise ValueError('Photo collection busy: wait for After Effects to confirm the current import.')
            self.apply_quality(id,min_edge)
            folder=self._folder(job);rejected=set()
            for row in job['photos']:
                if row['status'] not in ('ready','saved','duplicate'):continue
                try:
                    source=self.file(id,'photo',row['id']);original,_=decode(source.read_bytes())
                    with Image.open(folder/'crops'/f'{row["id"]:03d}.png') as crop:check=similarity(crop,original)
                    row['match']=check
                    if not check['matched']:raise ValueError('The saved variant does not preserve the screenshot photo.')
                    if not meets_quality({**row,'width':original.width,'height':original.height,'effective_width':check.get('effective_width'),'effective_height':check.get('effective_height'),'match':check},job.get('min_edge',0)):
                        row['status']='low_quality';rejected.add(row['file']);continue
                except (ValueError,OSError) as error:
                    row['status']='review';row['rejected_reason']=str(error);rejected.add(row.get('file',''))
            valid={row.get('file') for row in job['photos'] if row['status'] in ('ready','saved','duplicate')}
            for name in rejected-valid:
                path=(folder/'photos'/name).resolve();target=(folder/'unconfirmed-originals'/name).resolve()
                if not job.get('ae_receipt') and name and path.is_relative_to((folder/'photos').resolve()) and target.is_relative_to((folder/'unconfirmed-originals').resolve()) and path.is_file():
                    target.parent.mkdir(exist_ok=True)
                    if not target.exists():shutil.move(str(path),str(target))
            self.update(id,photos=job['photos']);self._bundle(id)
            if any(row['status'] in ('ready','saved','duplicate') for row in job['photos']):self.save(id)
            records=[]
            for row in job['photos']:
                if row['status'] in ('saved','duplicate') and row.get('file'):
                    records.append({'id':row['id'],'path':str(self.file(id,'photo',row['id'])),'origin':'original'})
                elif job.get('previews') and row.get('preview_file'):
                    path=(folder/'previews'/row['preview_file']).resolve()
                    if path.is_relative_to((folder/'previews').resolve()) and path.is_file():records.append({'id':row['id'],'path':str(path),'origin':'screenshot-preview'})
            if not records:raise ValueError('Photo quality unavailable: no confirmed originals meet the selected size. Continue the search or enable labelled screenshot previews.')
            paths=list(dict.fromkeys(row['path'] for row in records))
            self.update(id,ae_status='importing',ae_error=None)
            try:
                result=self.importer(folder,job,paths,expected=job.get('ae_expected'),photos=records)
                self.update(id,ae_requested=True,ae_status='done',ae_receipt=result,ae_expected=result['project'],stage=f'{len(result.get("imported",[]))} photos imported · {len(result.get("upgraded",[]))} upgraded · {len(result.get("already_present",[]))} already present. Screenshot previews are labelled in After Effects.')
            except Exception as error:
                from hinglish_app.user_messages import failure
                self.update(id,ae_status='failed',ae_error=failure(error));raise
        return self.snapshot(id)

    def file(self,id,kind,item=None):
        job=self._get(id)
        if job['status']=='archived':raise ValueError('Photo collection archived: restore it before opening its photos.')
        folder=self._folder(job)
        if kind=='screenshot':path=folder/'screenshot.png'
        elif kind=='zip':path=folder/'photos.zip'
        elif kind in ('crop','candidate','photo'):
            try:item=int(item)
            except (TypeError,ValueError):raise ValueError('Photo missing: choose a photo from this collection.')
            row=next((entry for entry in job['photos'] if entry['id']==item),None)
            if row is None:raise ValueError('Photo missing: choose a photo from this collection.')
            if kind=='photo':
                path=folder/'photos'/row.get('file','')
                if not path.is_file():path=folder/'originals'/row.get('file','')
                if not path.is_file() and row.get('preview_file'):path=folder/'previews'/row['preview_file']
            else:path=folder/('crops' if kind=='crop' else 'candidates')/f'{item:03d}.png'
        else:raise ValueError('Photo file invalid: choose a collection photo or ZIP.')
        path=path.resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():raise ValueError('Photo file missing: this result has no saved file yet.')
        return path
    def archive(self,id):
        with self.lock:
            job=self._get(id)
            if job['status'] not in TERMINAL or job['status']=='archived':raise ValueError('Photo collection busy: let it finish before moving it to Trash.')
            self._folder(job)
            self.update(id,status='archived',previous_status=job['status'],previous_folder=job['folder'],archive_mode='metadata')
        return self.snapshot(id)
    def restore(self,id):
        with self.lock:
            job=self._get(id)
            if job['status']!='archived':raise ValueError('Photo collection invalid: choose an archived collection to restore.')
            if job.get('archive_mode')=='metadata':
                self.update(id,status=job['previous_status']);return self.snapshot(id)
            source=self._folder(job);target=(self.base/job['previous_folder']).resolve()
            if not source.is_relative_to(self.trash.resolve()) or not target.is_relative_to(self.base.resolve()) or target==self.base.resolve() or target.exists():
                raise ValueError('Photo collection invalid: its restore destination is unavailable.')
            shutil.move(str(source),str(target));self.update(id,status=job['previous_status'],folder=job['previous_folder'])
        return self.snapshot(id)

_services={};_lock=threading.Lock()
def service(root):
    key=str(Path(root).resolve())
    with _lock:
        if key not in _services:_services[key]=PhotoService(root)
        return _services[key]
