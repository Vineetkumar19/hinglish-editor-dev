"""One authorized, durable Long -> Shorts -> paired delivery workflow."""
import copy
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from hinglish_app.durable_json import write
from hinglish_app.user_messages import failure
from .prepare_post import file_identity, VIDEO


class PreparationStopped(ValueError):
    def __init__(self, draft):
        issues=draft.get('errors',{})
        key=next(iter(issues),draft.get('current_stage','preparation'))
        label=key
        if key.startswith('copy:'):
            _,platform,index=key.split(':')
            label=('YouTube text' if platform=='youtube' else 'Instagram caption')+' for clip '+index
        super().__init__('Could not finish '+label+'. Finished videos and completed steps are saved.')
        self.stderr='\n'.join(v.get('error_details') or v.get('error','') for v in issues.values())


def reconcile_existing_long(publisher, value):
    """Refresh this exact reused upload; never submit or invent a remote result."""
    if not value['steps'].get('long_reused'):return
    from .providers import youtube_client
    client,account=youtube_client(publisher.root,value['profile'])
    for key in value['jobs']['long']:
        job=publisher.store.get(key)
        if job['fingerprint']!=value['source']['sha256'] or job['account_id']!=value['intent']['accounts']['youtube']:
            raise ValueError('The reused long receipt does not match this source and channel.')
        rows=client.videos().list(part='snippet,status',id=job['remote']['id']).execute().get('items',[])
        if len(rows)!=1 or rows[0]['snippet']['channelId']!=job['account_id'] or account['channel_id']!=job['account_id']:
            raise ValueError('YouTube cannot verify the exact reused long upload on this channel.')
        item=rows[0]
        if any(item['snippet'].get(k)!=job['metadata'][k] for k in ('title','description')):
            raise ValueError('The existing YouTube copy changed. Review it before reusing this upload.')
        status=item['status']
        if status.get('uploadStatus') in ('failed','rejected','deleted'):raise ValueError('YouTube did not retain this saved upload.')
        if status.get('privacyStatus')=='private' and not status.get('publishAt'):
            remote={**job['remote'],'privacy':'private','publish_at':'','private_verified_at':time.time()}
            remote.pop('schedule_verified_at',None)
            publisher.store.change(key,status='uploaded_private',remote=remote,release_action=None,release_authorized_at=None)
            publisher.store.event(key,'Reconciled exact processed/private YouTube receipt; no upload repeated.')


def completed_long_cancelled(publisher, value):
    """A later verified cancellation does not undo a completed preparation stage."""
    receipts=value.get('receipts',{}).get('long',[])
    keys=value.get('jobs',{}).get('long',[])
    if not keys or {r['job'] for r in receipts}!=set(keys):return False
    for receipt in receipts:
        job=publisher.store.get(receipt['job']);remote=job.get('remote',{})
        if (job['status']!='cancelled' or not remote.get('cancellation_verified_at')
                or remote.get('privacy')!='private' or remote.get('publish_at')
                or remote.get('id')!=receipt.get('remote',{}).get('id')
                or job.get('account_id')!=value['intent']['accounts']['youtube']
                or job.get('fingerprint')!=value['source']['sha256']):return False
    return True


def completed_long_checkpoint(publisher, value):
    """A verified earlier step is a boundary, not a dependency on a remote file."""
    receipts=value.get('receipts',{}).get('long',[]);keys=value.get('jobs',{}).get('long',[])
    if not keys or len(receipts)!=len(keys) or {r.get('job') for r in receipts}!=set(keys):return False
    for receipt in receipts:
        remote=receipt.get('remote') or {};status=receipt.get('status')
        proof={'scheduled':'schedule_verified_at','published':'publication_verified_at','uploaded_private':'private_verified_at'}.get(status)
        if not proof or not remote.get(proof) or not remote.get('id'):return False
        job=publisher.store.get(receipt['job'])
        if (job.get('profile')!=value['profile'] or job.get('platform')!='youtube' or job.get('kind')!='long'
                or job.get('account_id')!=value['intent']['accounts']['youtube']
                or job.get('fingerprint')!=value['source']['sha256']
                or job.get('remote',{}).get('id')!=remote['id']):
            raise ValueError('The saved completed Long step does not match this source, channel and upload. No upload was repeated.')
    return True


class Workflow:
    def __init__(self, state, engine):
        self.state, self.engine = state, engine
        self.root = Path(state.root)
        self.folder = self.root / 'output/publisher-prepare-post/workflows'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.running = set()

    def get(self, key, profile):
        if not isinstance(key,str) or len(key)!=32 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Select a saved full workflow.')
        value=json.loads((self.folder/(key+'.json')).read_text('utf-8'))
        if value['profile']!=profile:raise ValueError('Select this workflow’s original channel.')
        return value

    def save(self, value):
        value['updated']=time.time()
        write(self.folder/(value['id']+'.json'),value)

    def list(self, profile):
        return sorted([json.loads(p.read_text('utf-8')) for p in self.folder.glob('*.json')
                       if json.loads(p.read_text('utf-8'))['profile']==profile],key=lambda x:x['created'],reverse=True)

    def create(self, payload):
        from hinglish_app.assistant_preferences import declarations
        if payload.get('authorize') is not True:raise ValueError('Press Run full workflow to authorize these exact destinations and steps.')
        profile=payload['profile'];count=payload.get('count',5)
        if profile not in ('cricket','gaming') or type(count) is not int or not 1<=count<=40:
            raise ValueError('Choose a channel and between1 and40 Shorts.')
        test=payload.get('minute_test',False)
        if type(test) is not bool or test and count!=5:raise ValueError('The one-minute validation uses exactly five Shorts.')
        decl={**declarations(self.root),**{k:payload[k] for k in ('made_for_kids','synthetic_media') if k in payload}}
        if any(type(decl.get(k)) is not bool for k in ('made_for_kids','synthetic_media')):
            raise ValueError('Choose audience and altered-content declarations first.')
        source=file_identity(payload.get('video',''),VIDEO)
        accounts=self.engine.publisher.accounts(profile)
        if any(not accounts.get(p,{}).get('connected') for p in ('youtube','instagram')):
            raise ValueError('Connect this channel’s YouTube and Instagram accounts before running both destinations.')
        request=str(payload.get('request_id',''))
        if not request or len(request)>80:raise ValueError('Refresh the page before starting a full workflow.')
        intent={'profile':profile,'source_sha256':source['sha256'],'count':count,'minute_test':test,
                'long_release':payload.get('long_release','schedule'),
                'accounts':{p:accounts[p]['id'] for p in ('youtube','instagram')},
                'declarations':{k:decl[k] for k in ('made_for_kids','synthetic_media')}}
        for flag in ('discovery_review', 'discovery_research'):
            if flag in payload:
                if type(payload[flag]) is not bool:
                    raise ValueError('Choose whether to include the SEO and thumbnail review.')
                intent[flag] = payload[flag]
        if payload.get('delivery_timing'):
            from .workflow_timing import validate
            intent['delivery_timing']=validate(payload['delivery_timing'])
        from .test_mode import enabled as repeat_uploads
        intent['repeat_uploads'] = repeat_uploads(self.root, profile)
        reuse_id = str(payload.get('reuse_long_video_id') or '')
        if reuse_id:intent['reuse_long_video_id'] = reuse_id
        fresh = payload.get('fresh_start', False)
        if type(fresh) is not bool:raise ValueError('Choose a valid fresh-start setting.')
        if fresh and reuse_id:raise ValueError('A fresh test cannot also reuse an earlier upload.')
        if fresh:intent['fresh_start'] = True
        if intent['long_release'] not in ('post_now','schedule'):raise ValueError('Choose Post now or Schedule for the long video.')
        with self.lock:
            for old in self.list(profile):
                if old['request_id']==request:
                    if old['intent']!=intent:raise ValueError('This click already belongs to a different source or release choice.')
                    return old
            key=uuid.uuid4().hex
            value={'id':key,'profile':profile,'request_id':request,'intent':intent,'source':source,
                   'thumbnail':payload.get('thumbnail',''),'created':time.time(),'status':'saved',
                   'message':'Full workflow saved.','steps':{},'preparations':{},'jobs':{},'errors':{},'receipts':{}}
            # New workflows get review suggestions. Existing saved workflows,
            # including their later Shorts steps, retain their old behaviour.
            value['discovery_settings'] = {flag: payload.get(flag, True) is True
                for flag in ('discovery_review', 'discovery_research')}
            # Reuse a receipt only for identical bytes, intended account and profile.
            existing=[] if fresh or intent['repeat_uploads'] and not reuse_id else [j for j in self.engine.publisher.store.list() if j.get('fingerprint')==source['sha256']
                      and j.get('profile')==profile and j.get('platform')=='youtube' and j.get('kind')=='long'
                      and j.get('account_id')==accounts['youtube']['id'] and j.get('remote',{}).get('id')
                      and (not reuse_id or j['remote']['id']==reuse_id and j['status']!='cancelled')]
            if reuse_id and not existing:raise ValueError('The requested long upload does not match this source and channel, or was cancelled. No new upload was started.')
            if len(existing)>1:raise ValueError('Multiple saved uploads match this source. Review their receipts before starting another workflow.')
            if existing:
                value['jobs']['long']=[existing[0]['id']]
                value['steps']['long_reused']={'job':existing[0]['id'],'video_id':existing[0]['remote']['id']}
            self.save(value)
            return value

    def start(self, key, profile):
        with self.lock:
            value=self.get(key,profile)
            if key in self.running:return value
            if value['status'] in ('complete','awaiting_instagram_cleanup'):return value
            for preparation in value['preparations'].values():
                saved = self.engine.get(preparation, profile)
                if saved['status'] == 'stopped' and saved.get('cancel_requested'):
                    self.engine.resume(preparation, profile)
            self.running.add(key);value.update(status='queued',message='Waiting for local preparation.');self.save(value)
            def work(progress=print):
                try:
                    self.supervise(key,profile,progress)
                except Exception as error:
                    value=self.get(key,profile);issue=failure(error,feature='Full publishing workflow')
                    value['errors'][value.get('current_step','workflow')]=issue
                    value.update(status='failed',message=issue['error']);self.save(value)
                finally:
                    with self.lock:self.running.discard(key)
                return self.get(key,profile)
            self.state.publisher.task(work)
            return self.get(key,profile)

    def checkpoint(self, value, step, message):
        value.update(current_step=step,status='working',message=message);self.save(value)

    def supervise(self, key, profile, progress, should_stop=None):
        while True:
            if should_stop and should_stop():
                raise ValueError('Stopped. Completed stages and uploaded videos are saved.')
            try:
                return self.run(key,profile,progress)
            except Exception as error:
                if should_stop and should_stop():raise
                value=self.get(key,profile)
                recovery=value.get('automatic_recovery') or {}
                step=value.get('current_step','workflow')
                step_attempts=recovery.setdefault('step_attempts',{})
                attempt=step_attempts.get(step,sum(1 for h in recovery.get('history',[]) if h.get('step')==step))
                if not recovery.get('enabled') or attempt>=3:
                    if recovery.get('enabled'):
                        recovery['exhausted']=True;value['automatic_recovery']=recovery;self.save(value)
                    raise
                from .prepare_post_recovery import recover, ReleaseNotReady
                try:
                    safe = recover(self,value)
                except ReleaseNotReady as pending:
                    checks=recovery.setdefault('readiness_checks',{})
                    count=checks.get(step,0)
                    if count>=40:
                        recovery.update(exhausted=True,blocked_reason=str(pending))
                        value['automatic_recovery']=recovery;self.save(value)
                        raise
                    delay=min(30,5*(count+1))
                    checks[step]=count+1
                    recovery.update(next_retry=time.time()+delay)
                    value.update(automatic_recovery=recovery,status='waiting_retry',message=str(pending))
                    self.save(value);progress(value['message'])
                    if self.state.publisher.stop.wait(delay):
                        raise ValueError('Storylens stopped while waiting for YouTube processing. The existing upload is saved.')
                    continue
                except Exception as recovery_error:
                    recovery['blocked_reason']=str(recovery_error)
                    recovery['exhausted']=True;value['automatic_recovery']=recovery;self.save(value)
                    raise
                if not safe:
                    recovery['blocked_reason']='The saved release could not be safely replayed from its current receipt.'
                    recovery['exhausted']=True;value['automatic_recovery']=recovery;self.save(value)
                    raise
                delay=(5,30,120)[attempt]
                step_attempts[step]=attempt+1
                recovery.update(attempts=recovery.get('attempts',0)+1,next_retry=time.time()+delay)
                recovery.setdefault('history',[]).append({'attempt':attempt+1,'step':value.get('current_step'),
                    'reason':str(error),'time':time.time(),'method':'saved_stage_resume' if step.endswith('_prepare') else 'independent_private_readback_same_upload'})
                message=('Retrying the unfinished preparation step. Completed source checks and transcripts are saved.'
                         if step.endswith('_prepare') else
                         'Existing upload verified. Automatically continuing the next saved step.')
                value.update(automatic_recovery=recovery,status='waiting_retry',message=message)
                self.save(value);progress(value['message'])
                if self.state.publisher.stop.wait(delay):
                    raise ValueError('Storylens stopped while waiting to resume this saved workflow.')

    def preparation(self, value, kind):
        profile=value['profile']
        if kind not in value['preparations']:
            draft=self.engine.create({'profile':profile,'mode':kind,'count':value['intent']['count'],
                'video':value['source']['path'],'thumbnail':value['thumbnail'] if kind=='long' else '',
                'visibility':'private','request_id':value['id']+'-'+kind,
                **value.get('discovery_settings', {})})
            value['preparations'][kind]=draft['id'];self.save(value)
            # Same source hash permits exact completed ASR reuse after a path move.
            with self.engine.lock:
                if value['intent'].get('fresh_start'):
                    draft['fresh_start'] = True
                    self.engine._save(draft)
                for previous in self.engine.list(profile):
                    if previous['id']==draft['id'] or previous['source']['sha256']!=value['source']['sha256']:continue
                    # Fresh tests cannot inherit old runs. Shorts may use only
                    # the transcript just created by this same workflow.
                    if value['intent'].get('fresh_start') and previous['id']!=value['preparations'].get('long'):continue
                    if 'speech' in previous['stages'] and 'inspect' in previous['stages']:
                        draft['stages']['inspect']=copy.deepcopy(previous['stages']['inspect'])
                        draft['stages']['speech']=copy.deepcopy(previous['stages']['speech'])
                        draft['stages']['speech']['source']=draft['source']
                        draft['reused_speech_from']=previous['id'];self.engine._save(draft)
                        (self.engine.folder/draft['id']).mkdir(parents=True,exist_ok=True)
                        write(self.engine.folder/draft['id']/'speech-reuse.json',{'from':previous['id'],'source_sha256':value['source']['sha256']})
                        break
        return self.engine.get(value['preparations'][kind],profile)

    def run(self, key, profile, progress):
        value=self.get(key,profile);value['errors']={};self.save(value)
        decl=value['intent']['declarations']
        if 'long' not in value['jobs']:
            self.checkpoint(value,'long_prepare','Preparing the long YouTube video.')
            long=self.preparation(value,'long')
            with self.state.work_lock:long=self.engine.run(long['id'],profile,progress)
            if long['status']!='prepared':raise PreparationStopped(long)
            self.checkpoint(value,'long_upload','Uploading the long video to the saved YouTube channel.')
            from .workflow_timing import apply
            apply(self.engine,long,'long','youtube',value['intent'].get('delivery_timing',{}))
            jobs=self.engine.post(long['id'],profile,'youtube',decl,value['intent']['long_release'])['jobs']
            value['jobs']['long']=[j['id'] for j in jobs];self.save(value)
        if completed_long_checkpoint(self.engine.publisher,value):
            value['steps']['long_checkpoint_reused']=True;self.save(value)
        else:
            reconcile_existing_long(self.engine.publisher,value)
            # Delivery owns network waits. Shorts depend on the local source and
            # saved speech, not on the Long's remote schedule being ready.
            self.engine.start_delivery()
        self.checkpoint(value,'shorts_prepare','Extracting Shorts and preparing paired YouTube/Instagram text.')
        short=self.preparation(value,'shorts')
        with self.state.work_lock:short=self.engine.run(short['id'],profile,progress)
        if short['status']!='prepared':raise PreparationStopped(short)
        value['steps']['shorts_prepared']={'count':short['count'],'stages':list(short['stages'])};self.save(value)
        self.checkpoint(value,'shorts_delivery','Scheduling YouTube Shorts and queuing the same clips for Instagram.')
        for platform in ('youtube','instagram'):
            if platform not in value['jobs']:
                # Keep allocation and queue insertion together so another local
                # batch observes these dates before choosing its own first day.
                with self.engine.lock:
                    short=self.engine.get(short['id'],profile)
                    from .workflow_timing import apply
                    apply(self.engine,short,'shorts',platform,value['intent'].get('delivery_timing',{}))
                    jobs=self.engine.post(short['id'],profile,platform,decl,'schedule')['jobs']
                value['jobs'][platform]=[j['id'] for j in jobs];self.save(value)
        if value['intent']['minute_test'] and not value['steps'].get('minute_slots_applied'):
            # Test timing is bound to this explicit workflow, never global settings.
            if not value['steps'].get('minute_slots'):
                value['steps']['minute_slots']={'due':[time.time()+60*(i+1) for i in range(short['count'])]};self.save(value)
            due=value['steps']['minute_slots']['due']
            for key,instant in zip(value['jobs']['instagram'],due):
                job=self.engine.publisher.store.get(key)
                if job['status']=='ready' and not job.get('remote'):
                    self.engine.publisher.store.change(key,expected_status=('ready',),due=instant,validation_workflow=value['id'])
            value['steps']['minute_slots_applied']=True;self.save(value)
        self.engine.start_delivery()
        self.wait(value,'youtube',progress)
        if not completed_long_checkpoint(self.engine.publisher,value):
            self.wait(value,'long',progress)
        if value['intent']['minute_test']:
            self.wait(value,'instagram',progress)
            self.checkpoint(value,'youtube_cleanup','Verified test posts; leaving the YouTube test videos private.')
            self.youtube_private(value)
            value.update(status='awaiting_instagram_cleanup',message='Five Instagram posts verified. YouTube test videos are private. Instagram test cleanup remains.')
        else:
            test_interval=value['intent'].get('delivery_timing',{}).get('instagram_interval')
            if test_interval:self.wait(value,'instagram',progress)
            value['steps']['instagram_buffer']={'jobs':value['jobs']['instagram'],'remote_delivery_verified':bool(test_interval)}
            value.update(status='complete',message='YouTube releases verified. Instagram buffer saved; each Reel is verified when it posts.')
            if test_interval:value['message']='YouTube releases and all Instagram test posts verified.'
        self.save(value)

    def wait(self, value, platform, progress):
        self.engine.start_delivery()
        keys=value['jobs'][platform]
        while True:
            # Persist the exact delivery boundary before reading a failed job,
            # otherwise recovery can mistakenly target the preceding platform.
            self.checkpoint(value,platform+'_verify',f'Checking {platform} platform receipts.')
            jobs=[self.engine.publisher.store.get(k) for k in keys]
            bad=[j for j in jobs if j['status'] in ('blocked','needs_review','cancelled')]
            if bad:raise ValueError('A saved '+platform+' post needs review: '+str(bad[0].get('error') or bad[0]['status'])+' No duplicate upload was started.')
            accepted=('published',) if platform=='instagram' else ('scheduled','published','uploaded_private')
            done=[j for j in jobs if j['status'] in accepted and j.get('remote',{}).get('url')
                  and (j['platform']!='youtube' or not j.get('release_action') or j['status']!='uploaded_private')]
            self.checkpoint(value,platform+'_verify',f'Checking {platform} platform receipts: {len(done)}/{len(jobs)} saved results available.')
            progress(value['message'])
            if len(done)==len(jobs):
                if platform!='instagram':
                    from hinglish_app.assistant_schedule import verify
                    from datetime import datetime,timezone
                    for job in done:
                        instant=datetime.fromtimestamp(job['due'],timezone.utc).isoformat() if job['status']=='scheduled' else ''
                        checked=verify(self.root,job,instant,private_only=job['status']=='uploaded_private')
                        if not checked:break
                        job['remote']=checked
                    else:
                        value['receipts'][platform]=[{'job':j['id'],'status':j['status'],'due':j['due'],'remote':j['remote']} for j in done]
                        self.save(value);return
                    if self.state.publisher.stop.wait(5):raise ValueError('Resume the saved workflow to verify the existing upload.')
                    continue
                value['receipts'][platform]=[{'job':j['id'],'status':j['status'],'due':j['due'],'remote':j['remote']} for j in done]
                self.save(value);return
            # No diagnostic deadline aborts healthy uploads or future buffers.
            if self.state.publisher.stop.wait(5):raise ValueError('Storylens stopped. Resume the saved full workflow; existing uploads will be reused.')

    def youtube_private(self, value):
        from .providers import youtube_client
        client,account=youtube_client(self.root,value['profile'])
        browser=self.engine.publisher.browser
        keys=value['jobs']['long']+value['jobs']['youtube']
        for number,key in enumerate(keys,1):
            job=self.engine.publisher.store.get(key)
            if account['channel_id']!=job['account_id']:raise ValueError('The YouTube channel changed before test cleanup.')
            video_id=job['remote']['id']
            def readback():
                rows=client.videos().list(part='snippet,status',id=video_id).execute().get('items',[])
                if len(rows)!=1 or rows[0]['snippet']['channelId']!=job['account_id']:
                    raise ValueError('The cleanup receipt belongs to another channel or missing upload.')
                if any(rows[0]['snippet'].get(k)!=job['metadata'][k] for k in ('title','description')):
                    raise ValueError('The test upload copy changed before cleanup. Review the existing receipt.')
                return rows[0]['status']
            status=readback()
            private=lambda state:state.get('privacyStatus')=='private' and not state.get('publishAt') and state.get('uploadStatus')=='processed'
            if not private(status):
                if browser is None or not browser.snapshot().get('youtube_private_cleanup'):
                    raise ValueError('Reload Storylens Local Publisher0.4.36 in Chrome to finish private-only test cleanup. Existing uploads and schedules are saved; no new Google permissions are needed.')
                task=browser.enqueue_youtube(job['account_id'],video_id,'','prepare-post:'+job['prepare_post_id']+'-test-cleanup',
                    authorized=True,private_only=True,channel_name=self.engine.publisher.accounts(value['profile'])['youtube'].get('name',''),
                    video_kind=job['kind'])
                value['steps'].setdefault('youtube_private_tasks',{})[key]=task['id'];self.save(value)
                while not private(status):
                    self.checkpoint(value,'youtube_cleanup',f'Keeping YouTube test uploads private: {number-1}/{len(keys)} verified.')
                    task=browser.get(task['id'])
                    if task['status'] in ('needs_review','blocked','cancelled'):
                        raise ValueError(task['message']+' The existing upload is kept.')
                    if self.state.publisher.stop.wait(2):raise ValueError('Resume this saved workflow to finish private-only cleanup.')
                    status=readback()
            remote={**job['remote'],'privacy':'private','publish_at':'','cleanup_private_verified_at':time.time()}
            self.engine.publisher.store.change(key,status='uploaded_private',remote=remote,release_action=None,release_authorized_at=None)
            value['steps'].setdefault('youtube_private',{})[key]={'video_id':video_id,'verified':True,'method':'independent_youtube_api_readback'};self.save(value)
