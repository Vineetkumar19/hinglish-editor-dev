"""Owner-facing controls for exact existing deliveries; never creates uploads."""
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import threading
import time
import uuid
from datetime import datetime

from hinglish_publish.store import IST,fingerprint
from hinglish_publish.features import title_hashtags


def revision(job):
    return hashlib.sha256(json.dumps({k:job.get(k) for k in (
        'id','status','account','account_id','caption','metadata','publish_at','due',
        'fingerprint','remote','submission_started','scheduled_action','scheduled_panel_deleted_at')},sort_keys=True).encode()).hexdigest()[:24]


def pending_in_panel(platform,job,now=None):
    """Project current work, without reviving failures or asserting publication."""
    now=time.time() if now is None else now
    if job.get('scheduled_panel_deleted_at'):return False
    if job.get('platform',platform)!=platform:return False
    status=job['status']
    if platform=='instagram':
        if job.get('action')!='reel':return False
        if status in ('running','sharing'):return True
        # Offline catch-up stays visible and authorized until actually posted.
        if status=='queued':return not job.get('stop')
        return False
    else:
        if job.get('private_copy_scope'):return False
        action=job.get('scheduled_action') or {}
        if action.get('action')=='cancel' and action.get('status') in ('failed','needs_review'):return False
        if status in ('uploading','processing') or (job.get('scheduled_action') or {}).get('status')=='working':return True
        if status not in ('scheduled','ready'):return False
        due=(job.get('remote') or {}).get('publish_at') or job.get('due',0)
    try:
        instant=float(due) if isinstance(due,(float,int)) else datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()
        return instant>now
    except (ValueError,TypeError,AttributeError):return False


def failed_in_panel(platform,job,now=None):
    if job.get('scheduled_panel_deleted_at'):return False
    if job.get('platform',platform)!=platform:return False
    if platform=='instagram':return job.get('action')=='reel' and job['status'] in ('needs_review','blocked','failed')
    if job.get('private_copy_scope') or job.get('platform','youtube')!='youtube':return False
    action=job.get('scheduled_action') or {}
    if action.get('action')=='cancel' and action.get('status') in ('failed','needs_review'):return True
    if job['status'] in ('needs_review','blocked','failed'):return True
    return job['status'] in ('scheduled','ready') and not pending_in_panel(platform,job,now)


def edited_metadata(old,fields):
    if not isinstance(fields,dict) or set(fields)-{'title','description','hashtags'}:raise ValueError('Use the title, description and hashtag fields.')
    title=fields.get('title',old.get('title',''))
    description=fields.get('description',old.get('description',''))
    raw=fields.get('hashtags','')
    if not all(isinstance(v,str) for v in (title,description,raw)):raise ValueError('Publishing text must be text.')
    title=title.strip();description=description.strip()
    tags=list(dict.fromkeys(re.findall(r'#?([A-Za-z][A-Za-z0-9_]*)',raw)))
    if not title or len(title)>100 or '<' in title or '>' in title:raise ValueError('Use a title of 1–100 characters.')
    if not 3<=len(tags)<=5:raise ValueError('Use 3–5 relevant hashtags, separated by spaces.')
    prose=re.sub(r'(?<!\w)#[A-Za-z][A-Za-z0-9_]*','',description).rstrip()
    description=prose+'\n\n'+' '.join('#'+tag for tag in tags)
    if len(description)>5000:raise ValueError('The description is too long; use at most 5,000 characters.')
    caption=title+'\n\n'+' '.join('#'+tag for tag in tags)
    if len(caption)>2200:raise ValueError('The Instagram title and hashtags exceed 2,200 characters.')
    return {**old,'title':title,'description':description,'tags':tags,'instagram_caption':caption}


class ScheduledPosts:
    def __init__(self,state):
        self.state=state;self.lock=threading.RLock()
        self._refreshing=False;self._refreshed_at=0;self._refresh_warning=''
        # After a restart an interrupted action must be read back, never replayed.
        for job in state.publisher.store.list():
            action=job.get('scheduled_action') or {}
            if action.get('status')=='working':
                state.publisher.store.change(job['id'],scheduled_action={**action,'status':'needs_review',
                    'message':'This action was interrupted. Check its saved YouTube result before retrying.'})

    def _job(self,key):
        if not isinstance(key,str) or not re.fullmatch(r'(instagram|youtube):[a-f0-9]{16}',key):raise ValueError('Choose a saved scheduled post.')
        platform,identity=key.split(':')
        if platform=='instagram':
            try:job=self.state.local_browser.get(identity)
            except ValueError:
                job=self.state.publisher.store.get(identity)
                if job.get('platform')!='instagram' or not job.get('prepare_post_id'):raise ValueError('This is not a scheduled post.')
        else:job=self.state.publisher.store.get(identity)
        if platform=='instagram' and job.get('action')!='reel' and not job.get('prepare_post_id') or platform=='youtube' and job.get('platform')!='youtube':raise ValueError('This is not a scheduled post.')
        return platform,job

    def refresh_published(self):
        """Reconcile existing YouTube IDs with read-only API calls, never upload."""
        with self.lock:
            if self._refreshing or time.time()-self._refreshed_at<60:return
            jobs=[j for j in self.state.publisher.store.list() if j['status']=='scheduled'
                  and not j.get('scheduled_panel_deleted_at')
                  and j.get('remote',{}).get('id') and (j.get('scheduled_action') or {}).get('status')!='working']
            self._refreshed_at=time.time()
            if not jobs:return
            self._refreshing=True
        threading.Thread(target=self._refresh_youtube,args=(jobs,),daemon=True,name='storylens-schedule-readback').start()

    def _refresh_youtube(self,jobs):
        from hinglish_publish.providers import youtube_client
        warning=''
        try:
            for profile in dict.fromkeys(j['profile'] for j in jobs):
                try:
                    client,account=youtube_client(self.state.root,profile)
                    selected=[j for j in jobs if j['profile']==profile and j.get('account_id')==account['channel_id']]
                    for start in range(0,len(selected),50):
                        batch=selected[start:start+50]
                        items=client.videos().list(part='snippet,status',id=','.join(j['remote']['id'] for j in batch)).execute().get('items',[])
                        observed={item['id']:item for item in items}
                        for job in batch:
                            item=observed.get(job['remote']['id'],{})
                            action=job.get('scheduled_action') or {}
                            if action.get('action')=='cancel' and item.get('snippet',{}).get('channelId')==job['account_id'] and item.get('status',{}).get('privacyStatus')=='private' and not item['status'].get('publishAt'):
                                with self.lock:
                                    current=self.state.publisher.store.get(job['id'])
                                    if revision(current)!=revision(job):continue
                                    from .scheduled_posts_cancel import verified_private
                                    verified_private(self.state.publisher.store,current,copy.deepcopy(action))
                                continue
                            if (item.get('snippet',{}).get('channelId')!=job['account_id']
                                or item.get('status',{}).get('privacyStatus')!='public'
                                or item.get('status',{}).get('uploadStatus')!='processed'):continue
                            with self.lock:
                                current=self.state.publisher.store.get(job['id'])
                                if revision(current)!=revision(job):continue
                                remote={**current['remote'],'privacy':'public','publish_at':'','publication_verified_at':time.time()}
                                remote.pop('schedule_verified_at',None)
                                self.state.publisher.store.change(job['id'],expected_status=('scheduled',),status='published',remote=remote)
                except Exception:
                    warning='Some YouTube publication checks are unavailable. Past unverified entries are in Failed attempts.'
        finally:
            with self.lock:self._refresh_warning=warning;self._refreshing=False

    def snapshot(self):
        from .scheduled_posts_cancel import available
        from .scheduled_posts_delete import available as can_delete
        self.refresh_published()
        state=self.state;owners={}
        for path in state.assistant.folder.glob('*.json'):
            try:
                data=json.loads(path.read_text('utf-8'));review=data.get('publishing_review') or {}
                for row in review.get('rows',[]):owners[row['id']]=data['id']
            except (ValueError,OSError,KeyError):continue
        with state.local_browser.lock:
            instagram=copy.deepcopy(state.local_browser.data['jobs'])
            instagram_profiles={handle.casefold():profile for profile,handle in state.local_browser.data['accounts'].items()}
        rows=[]
        publisher_jobs=state.publisher.store.list()
        for platform,jobs in (('instagram',instagram),('youtube',publisher_jobs)):
            for job in jobs:
                failed=failed_in_panel(platform,job)
                if not failed and not pending_in_panel(platform,job):continue
                if platform=='instagram':
                    caption=job.get('caption','');title=re.sub(r'(?<!\w)#[A-Za-z][A-Za-z0-9_]*','',caption.split('\n')[0]).strip() if caption else Path(job['video']).stem
                    meta={'title':title,'description':'','tags':re.findall(r'#([A-Za-z][A-Za-z0-9_]*)',caption)}
                    due=job.get('publish_at','');session=job.get('session','')
                    can_edit=job['status']=='queued' and job.get('submission_started') is False and not job.get('stop')
                    account=job['account'];message=job.get('message','')
                    profile=instagram_profiles.get(account.casefold()) or (account if account in ('cricket','gaming') else '')
                    if not profile:
                        profile=next((p for p in ('cricket','gaming') if ':'+p+':' in job.get('reference','')),'other')
                else:
                    if not job.get('authorized_at') and not (job.get('remote') or {}).get('id'):continue
                    meta=job['metadata'];due=(job.get('remote') or {}).get('publish_at') or datetime.fromtimestamp(job['due'],IST).isoformat()
                    session=owners.get(job['id'],'');account=state.publisher.accounts(job.get('profile','general'))['youtube'].get('name') or job.get('profile','YouTube')
                    op=job.get('scheduled_action') or {};message=op.get('message') or job.get('error','')
                    can_edit=job['status']=='scheduled' and bool(job.get('remote',{}).get('id')) and op.get('status') not in ('working','needs_review')
                    profile=job.get('profile','other')
                    if failed and job['status'] in ('scheduled','ready') and op.get('status') not in ('failed','needs_review'):
                        message='The release time has passed, but publication is not confirmed. Check YouTube before retrying.'
                key=platform+':'+job['id']
                tags=re.findall(r'(?<!\w)#([A-Za-z][A-Za-z0-9_]*)',meta.get('description','')) or meta.get('tags',[])
                rows.append({'id':key,'platform':platform,'profile':profile,'account':account,'status':job['status'],
                    'bucket':'failed' if failed else 'scheduled',
                    'publish_at':due,'title':meta.get('title','Video'),'description':meta.get('description',''),
                    'hashtags':' '.join('#'+tag.lstrip('#') for tag in dict.fromkeys(tags)),
                    'session':session,'can_edit':can_edit and not failed,'can_cancel':available(platform,job,state.local_browser),'can_delete':can_delete(platform,job,state.local_browser),'message':message,'revision':revision(job),
                    'operation':job.get('scheduled_action',{}),'url':job.get('url') or job.get('remote',{}).get('url','')})
        # Future Prepare/Post Reels stay in the durable publisher queue until
        # due. They are not Chrome tasks yet, and must never count as YouTube.
        browser_ids={j['id'] for j in instagram}
        for job in publisher_jobs:
            if job.get('platform')!='instagram' or not job.get('prepare_post_id') or not job.get('authorized_at'):continue
            if job.get('scheduled_panel_deleted_at'):continue
            remote=job.get('remote') or {}
            if remote.get('browser_job_id') in browser_ids:continue
            if job['status'] not in ('ready','uploading','processing','needs_review','blocked','failed'):continue
            meta=job.get('metadata') or {};caption=meta.get('instagram_caption','')
            failed=job['status'] in ('needs_review','blocked','failed')
            rows.append({'id':'instagram:'+job['id'],'platform':'instagram','profile':job['profile'],
                'account':job.get('account_id',''),'status':job['status'],'bucket':'failed' if failed else 'scheduled',
                'publish_at':datetime.fromtimestamp(job['due'],IST).isoformat(),
                'title':re.sub(r'(?<!\w)#[A-Za-z][A-Za-z0-9_]*','',caption).strip(),
                'description':'','hashtags':' '.join(re.findall(r'#[A-Za-z][A-Za-z0-9_]*',caption)),
                'session':'','can_edit':False,'can_cancel':available('instagram',job,state.local_browser),'can_delete':can_delete('instagram',job,state.local_browser),'message':job.get('error','') if failed else 'Queued locally; uploads automatically at release time while Storylens and Chrome are running.',
                'revision':revision(job),'operation':{},'url':remote.get('url',''),
                'prepare_post_id':job['prepare_post_id']})
        def release(row):
            try:return datetime.fromisoformat(row['publish_at'].replace('Z','+00:00')).timestamp()
            except (ValueError,TypeError):return 0
        rows.sort(key=lambda row:(({'cricket':0,'gaming':1}).get(row['profile'],2),row['platform'],release(row),row['id']))
        cancelled_ids=['instagram:'+j['id'] for j in instagram if j['status']=='cancelled' and j.get('cancelled_at')]
        cancelled_ids += [j['platform']+':'+j['id'] for j in publisher_jobs if j['status']=='cancelled' and (j.get('cancelled_at') or j.get('remote',{}).get('cancellation_verified_at'))]
        deleted_ids=['instagram:'+j['id'] for j in instagram if j.get('scheduled_panel_deleted_at')]
        deleted_ids += [j['platform']+':'+j['id'] for j in publisher_jobs if j.get('scheduled_panel_deleted_at')]
        return {'posts':rows,'cancelled_ids':cancelled_ids,'deleted_ids':deleted_ids,'delete_failed_supported':True,'cancel_scheduled_supported':True,'prepare_post_queue_included':True,'busy':sum(row['operation'].get('status')=='working' for row in rows),
                'refreshing':self._refreshing,'refresh_warning':self._refresh_warning}

    def thumbnail(self,key):
        _,job=self._job(key);path=Path(job['video'])
        if not path.is_file():raise ValueError('The saved video is unavailable.')
        stamp=path.stat();digest=hashlib.sha256(('preview-v2:'+str(path.resolve())+str(stamp.st_size)+str(stamp.st_mtime_ns)).encode()).hexdigest()
        cache=self.state.root/'cache/publisher/previews'/f'{digest}.jpg'
        if cache.is_file():return cache.read_bytes()
        import av
        with av.open(str(path)) as video:
            stream=video.streams.video[0]
            if stream.duration and stream.time_base:
                video.seek(int(min(float(stream.duration*stream.time_base)*.1,2)*1_000_000))
            frame=next(video.decode(video=0),None)
            if frame is None:raise ValueError('This video has no preview frame.')
            picture=frame.to_image();picture.thumbnail((360,360));buffer=io.BytesIO();picture.convert('RGB').save(buffer,'JPEG',quality=78)
        cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(buffer.getvalue())
        return buffer.getvalue()

    def _sync(self,job,platform,meta,publish_now=False):
        assistant=self.state.assistant
        for path in assistant.folder.glob('*.json'):
            try:
                raw=json.loads(path.read_text('utf-8'));review=raw.get('publishing_review') or {}
                matches=[r for r in review.get('instagram_rows' if platform=='instagram' else 'rows',[])
                    if r.get('browser_job_id' if platform=='instagram' else 'id')==job['id']]
                if not matches:continue
                session=assistant._get(raw['id'])
                if session['status'] in ('planning','running','transcribing'):continue
                previous=copy.deepcopy(session['publishing_review']);review=copy.deepcopy(previous)
                for row in review.get('instagram_rows' if platform=='instagram' else 'rows',[]):
                    if row.get('browser_job_id' if platform=='instagram' else 'id')!=job['id']:continue
                    row['metadata']=meta
                    if platform=='instagram':row.update(caption=job['caption'],status=job['status'])
                    if publish_now:row.update(immediate=True,publish_at='')
                    if platform=='youtube' and publish_now:row.update(status='published',publication_verified=True,schedule_verified=False,url=job['remote']['url'])
                review.update(id=uuid.uuid4().hex,created=time.time(),state='queued' if platform=='instagram' else previous['state'])
                from .pipeline_ledger import freeze
                freeze(assistant,session['id'],review)
                history=list(session.get('publishing_review_history',[]));history.append(previous)
                pipeline=copy.deepcopy(session.get('pipeline') or {})
                if pipeline:pipeline.update(authorized_review=review['id'],automatic=True,phase='waiting_instagram' if platform=='instagram' else 'waiting_release')
                assistant._update(session['id'],publishing_review=review,publishing_review_history=history[-10:],pipeline=pipeline or None)
                assistant._message(session['id'],'assistant','Posting the selected Instagram Reel now.' if platform=='instagram' and publish_now else
                    'The selected YouTube video is now public and verified.' if publish_now else 'Scheduled post text updated. Its release time is unchanged.')
            except (json.JSONDecodeError,OSError):continue

    def act(self,payload):
        if payload.get('action')=='delete':
            from .scheduled_posts_delete import delete_failed
            return delete_failed(self,payload)
        if payload.get('action')=='cancel':
            from .scheduled_posts_cancel import cancel
            return cancel(self,payload)
        if payload.get('action') not in ('save','publish_now'):raise ValueError('Choose Save changes or Publish now.')
        now=payload['action']=='publish_now'
        with self.lock,self.state.assistant.lock:
            platform,job=self._job(payload.get('id'))
            if platform=='instagram' and job.get('prepare_post_id') and job.get('action')!='reel':
                raise ValueError('Open Prepare & post to change this saved Reel. No upload was started.')
            if failed_in_panel(platform,job):raise ValueError('This is a failed or past unverified attempt. Open its source chat to review it before retrying.')
            if payload.get('revision')!=revision(job):raise ValueError('This post changed. Refresh the scheduled list before editing it.')
            # Reject a busy owning workflow before changing either store.
            for session in self.state.assistant.sessions.values():
                review=session.get('publishing_review') or {}
                if any(r.get('browser_job_id' if platform=='instagram' else 'id')==job['id'] for r in review.get('instagram_rows' if platform=='instagram' else 'rows',[])) and session['status'] in ('planning','running','transcribing'):
                    raise ValueError('This workflow is working. Wait for it to finish before changing its scheduled post.')
            old=job.get('metadata',{}) if platform=='youtube' else {'title':job.get('caption','').split('\n')[0],'description':''}
            meta=edited_metadata(old,payload.get('fields',{}))
            if platform=='youtube' and not re.sub(r'(?<!\w)#[A-Za-z][A-Za-z0-9_]*','',meta['description']).strip():raise ValueError('Add a description about the YouTube video before saving.')
            if platform=='youtube' and fingerprint(job['video'])!=job.get('fingerprint'):raise ValueError('The saved video changed. No publication was requested.')
            if platform=='instagram':
                bridge=self.state.local_browser
                with bridge.lock:
                    current=next(j for j in bridge.data['jobs'] if j['id']==job['id'])
                    if revision(current)!=payload['revision'] or current['status']!='queued' or current.get('submission_started') is not False or current.get('stop'):
                        raise ValueError('This Reel has already started or needs checking. No second post was created.')
                    stat=Path(current['video']).stat()
                    if [stat.st_size,stat.st_mtime_ns]!=current['file_stamp']:raise ValueError('The queued file changed. Restore it before publishing.')
                    current['caption']=meta['instagram_caption']
                    current['fingerprint']=hashlib.sha256(json.dumps(['reel',current['account'],current['video'],current['file_stamp'],current['caption']],ensure_ascii=False).encode()).hexdigest()
                    if now:
                        current.update(publish_at='',not_before=0,message='Publish now requested from Scheduled posts.')
                        check=next((j for j in bridge.data['jobs'] if j['id']==current.get('preflight_id')),None)
                        if check and check['status']=='queued':check.update(status='cancelled',message='The owner chose Publish now.')
                        current.pop('preflight_id',None)
                    bridge._save();self._sync(copy.deepcopy(current),platform,meta,now)
                return {'message':'Queued to post now; publication is not verified yet.' if now else 'Saved. The release time is unchanged.'}
            if job['status']!='scheduled' or not job.get('remote',{}).get('id'):raise ValueError('Only an existing scheduled YouTube upload can be changed here.')
            if (job.get('scheduled_action') or {}).get('status') in ('working','needs_review'):raise ValueError('This saved action is still working or needs platform verification. It will not be replayed.')
            if not self.state.local_browser.snapshot().get('youtube_scheduling'):raise ValueError('Connect YouTube Studio through Local Publisher before changing this scheduled video.')
            operation={'id':uuid.uuid4().hex,'status':'working','action':payload['action'],'created':time.time(),
                'message':'Waiting for YouTube Studio; the existing upload will be reused.','browser_ids':[]}
            self.state.publisher.store.change(job['id'],expected_status=('scheduled',),scheduled_action=operation)
            threading.Thread(target=self._youtube,args=(job,meta,now,operation),daemon=True).start()
            return {'message':'Working on the existing YouTube video. The result will appear here after verification.'}

    def _youtube(self,job,meta,publish_now,operation):
        store=self.state.publisher.store;bridge=self.state.local_browser
        def progress(message):
            operation['message']=message;store.change(job['id'],scheduled_action=copy.deepcopy(operation))
        try:
            from hinglish_publish.providers import youtube_client
            from .assistant_upload_recovery import same_instant
            client,account=youtube_client(self.state.root,job['profile'])
            if account['channel_id']!=job['account_id']:raise ValueError('The connected YouTube channel changed. No action was sent.')
            def read():
                items=client.videos().list(part='snippet,status',id=job['remote']['id']).execute().get('items',[])
                if not items:raise ValueError('YouTube did not return this saved video. Check it in YouTube Studio, or remove this entry from Failed attempts. No platform change was sent.')
                if len(items)!=1 or items[0]['snippet']['channelId']!=job['account_id']:raise ValueError('The exact scheduled YouTube video cannot be verified.')
                return items[0]
            original=read();due=original['status'].get('publishAt','')
            if operation['action']=='cancel' and original['status'].get('privacyStatus')=='private' and not due:
                from .scheduled_posts_cancel import verified_private
                verified_private(store,job,operation)
                return
            if original['status'].get('privacyStatus')!='private' or not due:raise ValueError('YouTube no longer reports this video as scheduled. Check its current platform result.')
            expected=job['remote'].get('publish_at') or datetime.fromtimestamp(job['due'],IST).isoformat()
            if not same_instant(due,expected):raise ValueError('The YouTube release time changed outside this review. No action was sent.')
            if any(original['snippet'].get(k)!=job['metadata'][k] for k in ('title','description')):raise ValueError('The YouTube text changed outside Storylens. Refresh its platform details before overwriting it.')
            def wait(task):
                operation['browser_ids'].append(task['id']);progress('Applying your change to the existing YouTube video.')
                for _ in range(900):
                    state=bridge.get(task['id'])
                    if state['status']=='submitted':return
                    if state['status'] in ('needs_review','blocked','cancelled'):raise ValueError(state.get('message') or 'YouTube action needs checking.')
                    time.sleep(1)
                raise TimeoutError('YouTube Studio has not finished. Check the saved action before retrying.')
            account_name=self.state.publisher.accounts(job['profile'])['youtube'].get('name','')
            session=next((r['session'] for r in self.snapshot()['posts'] if r['id']=='youtube:'+job['id']),'')
            if operation['action']=='cancel':
                wait(bridge.enqueue_youtube(job['account_id'],job['remote']['id'],'',session,authorized=True,
                    channel_name=account_name,video_kind=job['kind'],private_only=True))
                for attempt in range(60):
                    current=read()
                    if current['status'].get('privacyStatus')=='private' and not current['status'].get('publishAt'):break
                    time.sleep(1)
                else:raise ValueError('YouTube has not confirmed cancellation. Check the saved video; no second action was sent.')
                from .scheduled_posts_cancel import verified_private
                verified_private(store,job,operation)
                return
            if any(meta[k]!=job['metadata'][k] for k in ('title','description')):
                wait(bridge.enqueue_youtube(job['account_id'],job['remote']['id'],'',session,authorized=True,
                    channel_name=account_name,video_kind=job['kind'],metadata={k:meta[k] for k in ('title','description')},
                    expected_metadata={k:job['metadata'][k] for k in ('title','description')}))
                for attempt in range(30):
                    current=read()
                    if all(current['snippet'].get(k)==meta[k] for k in ('title','description')):break
                    time.sleep(1)
                else:raise ValueError('YouTube has not verified the saved text. No second save was sent.')
                if not same_instant(current['status'].get('publishAt',''),due):raise ValueError('The release changed while saving. Check YouTube before continuing.')
                store.change(job['id'],metadata=meta)
            if publish_now:
                wait(bridge.enqueue_youtube(job['account_id'],job['remote']['id'],'',session,authorized=True,
                    channel_name=account_name,video_kind=job['kind'],publish_now=True,allow_reschedule=True))
                for attempt in range(60):
                    current=read()
                    if current['status'].get('privacyStatus')=='public' and current['status'].get('uploadStatus')=='processed':break
                    time.sleep(1)
                else:raise ValueError('YouTube has not confirmed public visibility. No second publication was sent.')
                remote={**job['remote'],'privacy':'public','publish_at':'','publication_verified_at':time.time()}
                remote.pop('schedule_verified_at',None)
                store.change(job['id'],status='published',remote=remote,due=time.time(),metadata=meta)
            operation.update(status='complete',message='Published now and verified on YouTube.' if publish_now else 'Text saved and the scheduled release time verified unchanged.')
            store.change(job['id'],scheduled_action=operation)
            with self.state.assistant.lock:self._sync(store.get(job['id']),'youtube',meta,publish_now)
        except Exception as error:
            uncertain=any(bridge.get(key).get('submission_started') for key in operation['browser_ids'])
            from .user_messages import problem
            issue=problem(error)
            operation.update(status='needs_review' if uncertain else 'failed',message=issue['message'],
                error_code=issue['code'],error_details=issue['details'],finished=time.time())
            store.change(job['id'],scheduled_action=operation)
