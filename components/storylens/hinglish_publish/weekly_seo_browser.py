"""Fixed Chrome queue contracts for weekly metadata, never a YouTube API call."""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

ACTION='youtube_weekly_metadata'


def enqueue(browser, plan, video_id, row, start, baseline):
    from .weekly_seo import WEEK
    from .prepare_post import verify_identity
    if not re.fullmatch(r'UC[\w-]{22}',plan['account_id']) or not re.fullmatch(r'[\w-]{11}',video_id):
        raise ValueError('Weekly changes require the exact saved YouTube video and channel.')
    metadata={k:row[k] for k in ['title','description']}
    image=plan['thumbnails'][row['week']-1]['prepared'] if plan['change_thumbnails'] else None
    if image:verify_identity(image)
    signature=hashlib.sha256(json.dumps([plan['id'],row['week'],video_id,metadata,image],sort_keys=True).encode()).hexdigest()
    with browser.lock:
        prior=next((j for j in browser.data['jobs'] if j.get('fingerprint')==signature and j['action']==ACTION),None)
        if prior:return dict(prior)
        job={'id':uuid.uuid4().hex[:16],'action':ACTION,'plan_id':plan['id'],'week':row['week'],
            'channel_id':plan['account_id'],'channel_name':plan['channel_name'],'video_id':video_id,
            'video_kind':'long','publish_at':'','publish_now':False,'allow_reschedule':False,
            'session':'weekly-seo:'+plan['id'],'account':'','video':'','caption':'',
            'metadata':metadata,'expected_metadata':{k:baseline[k] for k in ['title','description']},
            'thumbnail':image,'not_before':start+(row['week']-1)*WEEK,'window_end':start+row['week']*WEEK,
            'status':'queued','created':time.time(),'message':'Waiting for this approved weekly package’s date.',
            'fingerprint':signature,'stop':False,'submission_started':False,'last_phase':'queued'}
        browser.data['jobs'].append(job);browser._save();return dict(job)


def eligible(browser, job, now):
    from .weekly_seo import Plans
    plan=Plans(browser.folder.parents[1]).get(job['plan_id'])
    if not plan.get('enabled') or plan.get('status') in ('paused','needs_review','cancelled'):
        job.update(status='cancelled',message='The weekly plan is paused or needs review.');browser._save();return False
    prior=[j for j in browser.data['jobs'] if j.get('plan_id')==job['plan_id'] and j.get('week',0)<job['week']]
    if any(j['status'] not in ('complete','cancelled') for j in prior):return False
    applied=sorted([j for j in prior if j['status']=='complete'],key=lambda j:j['week'])
    if applied:
        from .weekly_seo import WEEK
        previous=applied[-1]
        due=max(job['not_before'],previous['finished']+WEEK)
        if due!=job['not_before']:
            job.update(not_before=due,window_end=due+WEEK);browser._save()
        job['expected_metadata']=dict(previous['metadata'])
    return True


def finish(browser, job, result):
    status=result.get('status')
    if status not in ('complete','needs_review','blocked','cancelled','queued'):
        raise ValueError('Weekly changes need a saved Studio readback, not an upload receipt.')
    if status=='queued':
        if job.get('submission_started'):
            raise ValueError('A submitted weekly Save must be checked before retrying.')
        job.update(status='queued',retry_at=time.time()+60,message=str(result.get('message','Waiting for Studio and the connection to be ready.'))[:500])
        job.pop('lease',None);browser._save();return browser.get(job['id'])
    if status=='complete':
        if (job['status']!='sharing' or result.get('reloaded') is not True or result.get('save_disabled') is not True or
            result.get('visibility')!='Public' or result.get('metadata')!=job['metadata'] or
            any(result.get(k)!=job[k] for k in ['channel_id','video_id']) or
            job.get('thumbnail') and result.get('thumbnail_saved') is not True):
            raise ValueError('Studio has not verified this exact weekly package after reload.')
        job['verification']={'method':'studio_dom_after_reload','time':time.time(),
            'channel_id':job['channel_id'],'video_id':job['video_id'],'metadata':job['metadata'],
            'visibility':'Public','thumbnail_save_confirmed':bool(job.get('thumbnail')),
            'thumbnail_pixel_match_verified':False}
    job.update(status=status,finished=time.time(),message=str(result.get('message',''))[:500])
    browser._save();return browser.get(job['id'])
