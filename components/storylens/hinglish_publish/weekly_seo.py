"""Durable, opt-in weekly packages. Executes only through the Chrome connector.

No YouTube API client, upload transport, model call or arbitrary browser code.
Chrome's existing claim heartbeat binds approved plans to published receipts.
"""
import json
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager, closing
from pathlib import Path

WEEK = 7 * 24 * 60 * 60


def current_channel(root, profile):
    from . import secrets
    from hinglish_niche.profiles import account_key
    try:return secrets.load(root,account_key('youtube',profile)).get('channel_id')
    except Exception:return None


def snapshot(root, profile, browser):
    path=Path(root)/'cache/publisher/weekly-seo.sqlite3'
    if not path.is_file():return []
    result=Plans(root).list(profile)
    for plan in result:
        steps=[]
        for key in plan.get('browser_jobs',[]):
            try:
                task=browser.get(key)
                steps.append({k:task.get(k) for k in ['week','status','not_before','window_end','finished','message','verification','retry_at']})
            except ValueError:steps.append({'status':'needs_review','message':'The browser receipt is unavailable.'})
        plan['steps']=steps
        plan['estimated_end_at']=max([max(s.get('window_end') or 0,(s.get('finished') or 0)+WEEK) for s in steps] or [0]) or None
    return result


class Plans:
    def __init__(self, root):
        self.root=Path(root)
        self.path=self.root/'cache/publisher/weekly-seo.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, profile TEXT NOT NULL, data TEXT NOT NULL)')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            with db:yield db
        finally:db.close()

    def list(self, profile=None):
        with self.db() as db:
            rows=db.execute('SELECT data FROM plans'+(' WHERE profile=?' if profile else ''),(profile,) if profile else ()).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, key, profile=None):
        with self.db() as db:row=db.execute('SELECT data,profile FROM plans WHERE id=?',(key,)).fetchone()
        if not row or profile is not None and row[1]!=profile:raise ValueError('Choose this channel’s saved weekly SEO plan.')
        return json.loads(row[0])

    def update(self, key, **changes):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT data FROM plans WHERE id=?',(key,)).fetchone()
            if not row:raise ValueError('The weekly plan is unavailable.')
            value=json.loads(row[0]);value.update(changes,updated=time.time())
            if not value.get('enabled') and value.get('status') not in ('complete','cancelled'):value['status']='paused'
            db.execute('UPDATE plans SET data=? WHERE id=?',(json.dumps(value),key))
        return value

    def enable(self, engine, profile, payload):
        if payload.get('authorize') is not True:
            raise ValueError('Review every selected week and choose Enable weekly changes.')
        draft=engine.get(payload.get('id',''),profile)
        if draft['mode']=='shorts' or draft['status']!='prepared' or draft.get('cancel_requested'):
            raise ValueError('Choose a finished YouTube Long video or Highlights preparation.')
        proposal=draft['stages'].get('copy:youtube:1',{}).get('weekly_seo',{})
        if proposal.get('status')!='ready' or proposal.get('revision')!=payload.get('revision'):
            raise ValueError('The weekly plan changed. Reopen it and review the latest packages.')
        from .weekly_seo_plan import validate, V8_MODEL
        if V8_MODEL not in proposal.get('model',''):raise ValueError('Generate this weekly plan with V8 before enabling it.')
        transcript=draft['stages'].get('highlights',draft['stages']['speech'])['transcript']
        variants=validate({'variants':payload.get('variants',proposal['variants'])},proposal['weeks'],transcript,proposal.get('evidence_bank'))
        change_thumbnails=payload.get('change_thumbnails',False)
        if type(change_thumbnails) is not bool:raise ValueError('Choose whether weekly thumbnails should change.')
        paths=payload.get('thumbnails',[])
        if change_thumbnails and (not isinstance(paths,list) or len(paths)!=proposal['weeks'] or any(not isinstance(p,str) or not p.strip() for p in paths)):
            raise ValueError('Select one finished thumbnail image for every week, or turn weekly thumbnail changes off.')
        key=uuid.uuid4().hex
        images=[]
        if change_thumbnails:
            from .prepare_post import file_identity, IMAGE
            for path in paths:
                original=file_identity(path,IMAGE)
                try:prepared=engine.publisher.prepared_thumbnail(original['path'])
                except (OSError,ValueError) as error:
                    raise ValueError('A weekly thumbnail could not be read. Choose a valid image file; the plan has not been enabled.') from error
                normalized=file_identity(prepared,IMAGE)
                frozen=self.root/'cache/publisher/weekly-seo-thumbnails'/key/f'week-{len(images)+1}.jpg'
                frozen.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(prepared,frozen)
                from .prepare_post import verify_identity
                verify_identity(normalized)
                identity=file_identity(frozen,IMAGE)
                if identity['sha256']!=normalized['sha256']:raise ValueError('The thumbnail changed while saving its weekly copy. Choose it again; no plan was enabled.')
                images.append({'original':original,'prepared':identity})
        account=engine.publisher.accounts(profile).get('youtube',{})
        if not account.get('id') or account['id']!=draft['bindings']['youtube']['id']:
            raise ValueError('Reconnect this preparation’s original YouTube channel before enabling its weekly plan.')
        from .description_policy import apply
        for row in variants:row['description']=apply(self.root,profile,row)['description']
        source=draft['stages'].get('highlights',{}).get('video',draft['source'])
        value={'id':key,'profile':profile,'preparation':draft['id'],'account_id':account['id'],
            'channel_name':account.get('name',''),'source_sha256':source['sha256'],
            'weeks':proposal['weeks'],'variants':variants,'change_thumbnails':change_thumbnails,
            'offline_policy':'resume_and_shift','manual_edit_policy':'replace_saved_text_next_week',
            'thumbnails':images,'baseline':{k:draft['stages']['copy:youtube:1']['metadata'][k] for k in ['title','description']},
            'proposal_revision':proposal['revision'],'model':proposal['model'],'enabled':True,
            'status':'awaiting_publication','created':time.time(),'updated':time.time(),'browser_jobs':[],
            'message':'Approved. Waiting for this exact Long video’s verified public receipt. Chrome and Storylens must stay open.'}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=[json.loads(row[0]) for row in db.execute('SELECT data FROM plans WHERE profile=?',(profile,))]
            if any(p.get('enabled') and p.get('status')!='complete' and p['preparation']==draft['id'] for p in existing):
                raise ValueError('This video already has an enabled weekly plan. Pause it before approving a replacement.')
            db.execute('INSERT INTO plans VALUES(?,?,?)',(key,profile,json.dumps(value)))
        return value

    def pause(self, key, profile, browser):
        plan=self.get(key,profile)
        value=self.update(key,enabled=False,status='paused',message='Paused. Future changes are stopped; a save already in progress may finish.')
        if browser:
            for task in plan.get('browser_jobs',[]):
                if browser.get(task)['status'] not in ('complete','cancelled'):browser.cancel(task)
        return value


def sync(browser, now=None):
    """Called by the existing local Chrome heartbeat, never by a cloud timer."""
    root=browser.folder.parents[1]
    path=root/'cache/publisher/weekly-seo.sqlite3'
    if not path.is_file():return
    now=time.time() if now is None else now
    plans=Plans(root)
    from .store import Store
    for plan in plans.list():
        try:
            if not plan.get('enabled') or plan.get('status') in ('complete','needs_review'):continue
            if current_channel(root,plan['profile'])!=plan['account_id']:
                plans.update(plan['id'],status='needs_review',message='This profile’s saved YouTube channel changed or is unavailable. Weekly changes are paused.');continue
            if 'youtube_weekly_metadata' not in browser.worker_supports:
                message='Reload Storylens Local Publisher 0.4.38 in Chrome to enable weekly changes. No package has been applied by this check.'
                if plan.get('message')!=message:plans.update(plan['id'],status='waiting_extension',message=message)
                continue
            if plan.get('status')=='waiting_extension':
                plan=plans.update(plan['id'],status='active' if plan['browser_jobs'] else 'awaiting_publication',message='Chrome is ready. Waiting for this video’s weekly window or verified public release.')
            if not plan['browser_jobs']:
                # Read saved job/preparation identities only. Never upload, retry a
                # failed workflow or edit the original publishing receipt.
                db_path=root/'output/publisher-prepare-post/preparations/preparations.sqlite3'
                with closing(sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True)) as db:
                    found=db.execute('SELECT data FROM preparations WHERE id=?',(plan['preparation'],)).fetchone()
                if not found:continue
                draft=json.loads(found[0]);keys=draft.get('jobs_by_platform',{}).get('youtube',[])
                if draft.get('cancel_requested') or draft['status']=='cancelled':
                    plans.update(plan['id'],enabled=False,status='cancelled',message='The source preparation was cancelled. No weekly changes will run.');continue
                if len(keys)!=1:continue
                job=Store(root).get(keys[0])
                if job['status']=='cancelled':
                    plans.update(plan['id'],enabled=False,status='cancelled',message='The original video was cancelled. No weekly changes will run.');continue
                if job['status']!='published' or not job.get('remote',{}).get('publication_verified_at'):continue
                if (job.get('platform')!='youtube' or job.get('kind')!='long' or job.get('profile')!=plan['profile'] or
                    job.get('account_id')!=plan['account_id'] or job.get('fingerprint')!=plan['source_sha256']):
                    plans.update(plan['id'],status='needs_review',message='The saved video or channel no longer matches this weekly plan.');continue
                video_id=job['remote']['id']
                if any(p['id']!=plan['id'] and p.get('enabled') and p.get('video_id')==video_id and p['account_id']==plan['account_id'] and p.get('status')!='complete' for p in plans.list()):
                    plans.update(plan['id'],status='needs_review',message='Another enabled plan already owns this video.');continue
                from .weekly_seo_browser import enqueue
                start=plan.get('start_at',now)
                # Persist the anchor before enqueue; retries reuse exact task IDs.
                plans.update(plan['id'],start_at=start,video_id=video_id)
                previous=[t for t in browser.data['jobs'] if t.get('action')=='youtube_weekly_metadata' and
                    t.get('video_id')==video_id and t.get('channel_id')==plan['account_id'] and
                    t['status']=='complete' and t.get('verification',{}).get('method')=='studio_dom_after_reload']
                baseline=max(previous,key=lambda t:t['finished'])['metadata'] if previous else job['metadata']
                tasks=[enqueue(browser,plan,video_id,row,start,baseline)['id'] for row in plan['variants']]
                plan=plans.update(plan['id'],browser_jobs=tasks,status='active',
                    message='Weekly packages queued for this existing video. No new video will be uploaded.')
            tasks=[browser.get(key) for key in plan['browser_jobs']]
            # Offline time never expires an approved set. Keep later sets at
            # least seven days apart, anchored to actual verified completion.
            anchor=None;changed=False
            with browser.lock:
                for saved in sorted(tasks,key=lambda t:t['week']):
                    task=next(t for t in browser.data['jobs'] if t['id']==saved['id'])
                    if task['status']=='complete':anchor=task['finished'];continue
                    if task['status']!='queued':continue
                    due=max(task['not_before'],anchor+WEEK if anchor is not None else task['not_before'])
                    end=max(due,now)+WEEK
                    if due!=task['not_before'] or end!=task['window_end']:
                        task.update(not_before=due,window_end=end);changed=True
                    anchor=max(due,now)
                if changed:browser._save()
            tasks=[browser.get(key) for key in plan['browser_jobs']]
            failed=next((t for t in tasks if t['status'] in ('needs_review','blocked')),None)
            if failed:
                plans.update(plan['id'],status='needs_review',message=failed.get('message','The weekly browser change needs review.'))
                for task in tasks:
                    if task['status']=='queued':browser.cancel(task['id'])
            elif all(t['status'] in ('complete','cancelled') for t in tasks) and now>=max(
                    [t['finished']+WEEK for t in tasks if t['status']=='complete'] or [plan['start_at']+plan['weeks']*WEEK]):
                plans.update(plan['id'],status='complete',message='Weekly plan finished. The last applied package is retained.',
                    receipts=[{k:t.get(k) for k in ['id','week','status','finished','message','verification']} for t in tasks])
        except Exception as error:
            from hinglish_app.user_messages import failure
            issue=failure(error,feature='Weekly SEO plan')
            plans.update(plan['id'],status='needs_review',message=issue['error'],technical_details=issue.get('error_details',''))
