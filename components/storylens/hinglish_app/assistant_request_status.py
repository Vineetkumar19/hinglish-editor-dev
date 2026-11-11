"""Display this request's result separately from independently due queue jobs."""
import time


def review_is_current(session,review):
    request_id=session.get('active_request_message_id')
    if request_id and review.get('request_message_id'):
        return review['request_message_id']==request_id
    created=session.get('active_request_created',0)
    return not created or review.get('created',0)>=created


def pipeline_is_current(session):
    """An older workflow must not recover or report as a newer command."""
    pipeline=session.get('pipeline') or {}
    request_id=session.get('active_request_message_id')
    if request_id and pipeline.get('request_message_id'):
        return pipeline['request_message_id']==request_id
    review=session.get('publishing_review') or {}
    if review and review.get('id') in (pipeline.get('authorized_review'),pipeline.get('review_id')):
        return review_is_current(session,review)
    created=session.get('active_request_created',0)
    return not created or pipeline.get('created',0)>=created


def background_instagram(session,jobs,now=None):
    now=time.time() if now is None else now
    review=session.get('publishing_review') or {}
    own={r.get('browser_job_id') for r in review.get('instagram_rows',[])} if review_is_current(session,review) else set()
    request_start=session.get('active_request_created',0)
    rows=[]
    for job in jobs:
        if job.get('action')!='reel' or job['id'] in own:continue
        if (request_start and job.get('session')==session['id'] and job.get('created',0)>=request_start):continue
        pending=job.get('status') in ('queued','running','sharing') and not job.get('stop')
        recent=(job.get('status')=='published' and job.get('publish_at') and (job.get('finished') or 0)>=now-600)
        if not pending and not recent:continue
        rows.append({k:job.get(k) or '' for k in ('id','session','account','status','publish_at','finished')})
    rows.sort(key=lambda r:(r['status'] not in ('running','sharing'),r['status']=='published',r['publish_at']))
    return rows
