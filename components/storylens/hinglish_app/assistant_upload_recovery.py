"""Read-only batch presentation and narrowly proven pre-transfer retry eligibility."""
import copy
from datetime import datetime


def same_instant(left,right):
    try:
        a=datetime.fromisoformat(left.replace('Z','+00:00'))
        b=datetime.fromisoformat(right.replace('Z','+00:00'))
        return a.tzinfo is not None and b.tzinfo is not None and a==b
    except (AttributeError,TypeError,ValueError):return False


def retryable_rejection(session,review,job):
    if job.get('remote') or job['status'] not in ('blocked','needs_review'):return False
    failure=job.get('upload_failure') or {}
    if failure:return failure.get('phase')=='initializing' and failure.get('safe_retry') is True
    # Legacy SDK errors were reduced to their class name. That SDK class is
    # raised only when session creation is rejected, before transferring bytes.
    # Correlate the exact saved prefix receipts and first unfinished review ID.
    if job.get('error')!='Check YouTube before retrying; the saved remote ID is preserved.':return False
    for message in reversed(session.get('messages',[])):
        if not message.get('error') or not message.get('text','').startswith('Publishing stopped:'):continue
        if not message['text'].startswith('Publishing stopped: ResumableUploadError.'):return False
        results=message.get('publish_results',[]);n=len(results)
        if not n or n>=len(review['ids']) or review['ids'][n]!=job['id']:continue
        rows=review['rows']
        if all(result.get('url') and result['url']==rows[i].get('url') for i,result in enumerate(results)):
            return True
    return False


def present(assistant,session):
    review=copy.deepcopy(session.get('publishing_review'))
    if not review:return None
    for row in review.get('instagram_rows',[]):
        if not row.get('browser_job_id'):
            matches=[j for j in assistant.state.local_browser.snapshot()['jobs'] if
                j.get('action')=='reel' and j.get('reference')==row.get('id') and j.get('account')==row.get('account')]
            if len(matches)==1:row['browser_job_id']=matches[0]['id']
        if row.get('browser_job_id'):
            task=assistant.state.local_browser.get(row['browser_job_id'])
            # Legacy reviews lack a baseline. A receipt that predates this
            # request cannot be counted as a new upload by the retry.
            if 'previously_published' not in row:
                row['previously_published']=bool(task['status']=='published' and (
                    not task.get('finished') or not review.get('created') or task['finished']<=review['created']))
            row.update(status=task['status'],url=task.get('url',''),message=task.get('message',''))
            row['submission_started']=task.get('submission_started',False)
            same_slot=(not task.get('publish_at') and not row.get('publish_at')) or same_instant(task.get('publish_at',''),row.get('publish_at',''))
            row['actual_publish_at']=task.get('publish_at','')
            if not same_slot and task['status']=='queued':
                row.update(status='date_change_pending',message='The requested date change has not been saved yet. The existing Instagram job is retained.')
            if row['status'] in ('needs_review','blocked'):
                from .user_messages import problem
                row['user_message']=problem(row['message'])['message']
    review['instagram_queued_count']=sum(r['status'] in ('queued','running','sharing') for r in review.get('instagram_rows',[]))
    review['instagram_published_count']=sum(r['status']=='published' for r in review.get('instagram_rows',[]))
    jobs={i:assistant.state.publisher.store.get(i) for i in review['ids']}
    for row in review['rows']:
        job=jobs[row['id']];row['status']=job['status'];row['url']=job.get('remote',{}).get('url','')
        remote=job.get('remote') or {}
        row['private_verified']=bool(row.get('private_only') and job['status']=='uploaded_private' and remote.get('privacy')=='private' and not remote.get('publish_at') and remote.get('private_verified_at'))
        row['publication_verified']=bool(row.get('immediate') and job['status']=='published' and remote.get('privacy')=='public' and remote.get('publication_verified_at'))
        row['verified_publish_at']=remote.get('publish_at','') if remote.get('schedule_verified_at') else ''
        row['schedule_verified']=bool(job['status']=='scheduled' and remote.get('privacy')=='private' and
            row['verified_publish_at'] and same_instant(row['verified_publish_at'],row.get('publish_at','')))
        row['schedule_state']='verified' if row['schedule_verified'] else 'not_started'
        row['schedule_message']=''
        task_id=job.get('browser_schedule_id')
        if task_id and not row['schedule_verified']:
            try:task=assistant.state.local_browser.get(task_id)
            except ValueError:task={}
            if task.get('video_id')==remote.get('id') and same_instant(task.get('publish_at',''),row.get('publish_at','')):
                row['schedule_state']=task['status']
                row['schedule_message']=task.get('message','')
    review['uploaded_count']=sum(bool(j.get('remote',{}).get('id')) for j in jobs.values())
    review['scheduled_count']=sum(r['schedule_verified'] for r in review['rows'])
    review['retryable']=all(
        (j.get('remote',{}).get('id') and (j['status'] in ('uploaded_private','scheduled') and j['remote'].get('privacy')=='private' or j['status']=='published' and j['remote'].get('publication_verified_at')))
        or (not j.get('remote') and j['status']=='draft')
        or retryable_rejection(session,review,j) for j in jobs.values())
    if 'made_for_kids' not in review:
        declared=[j for j in jobs.values() if type(j.get('made_for_kids')) is bool and type(j.get('synthetic_media')) is bool]
        if declared and len({(j['made_for_kids'],j['synthetic_media']) for j in declared})==1:
            review.update(made_for_kids=declared[0]['made_for_kids'],synthetic_media=declared[0]['synthetic_media'])
    from .assistant_preferences import apply
    apply(assistant.root,review)
    return review
