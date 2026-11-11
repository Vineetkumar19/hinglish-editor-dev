"""Safe continuation of an authorized release; never uploads media bytes."""
import time
from .store import IST
from datetime import datetime


class ReleaseNotReady(RuntimeError):
    """Exact private upload is still processing; no Studio action was replayed."""


def release(publisher, job):
    from hinglish_app.assistant_schedule import verify
    if job.get('platform')!='youtube' or not job.get('remote',{}).get('id') or not job.get('release_authorized_at'):
        return False
    action=job.get('release_action')
    if action not in ('schedule','post_now'):
        return False
    instant=datetime.fromtimestamp(job['due'],IST).isoformat() if action=='schedule' else ''
    done=verify(publisher.root,job,instant)
    if done:
        publisher.store.change(job['id'],expected_status=(job['status'],),status='scheduled' if instant else 'published',remote=done,error='')
        return True
    private=verify(publisher.root,job,'',private_only=True)
    if not private:
        # verify(private_only=True) returns None only for the exact matching,
        # private/unscheduled video while YouTube is still processing it.
        # A missing video, changed copy/account or unsafe visibility raises.
        raise ReleaseNotReady('YouTube is still processing the saved private upload. Waiting before retrying its schedule; no upload is repeated.')
    if publisher.browser is None:
        return False
    if instant and job['due']<=time.time()+60:
        return False
    task_id=job.get('browser_schedule_id')
    if task_id:
        task=publisher.browser.get(task_id)
        if (task['video_id']!=job['remote']['id'] or task['channel_id']!=job['account_id'] or task.get('stop')
                or task.get('action')!='youtube_schedule' or bool(task.get('publish_now'))!=(action=='post_now')
                or (instant and datetime.fromisoformat(task['publish_at'].replace('Z','+00:00'))!=datetime.fromisoformat(instant))):
            return False
        if task['status'] in ('blocked','needs_review') and task.get('submission_started') is False:
            # enqueue_youtube requeues only the exact same pre-submission task.
            task=publisher.browser.enqueue_youtube(job['account_id'],job['remote']['id'],instant,
                'prepare-post:'+job['prepare_post_id'],authorized=True,
                channel_name=publisher.accounts(job['profile'])['youtube'].get('name',''),
                video_kind=job['kind'],publish_now=action=='post_now')
            if task['id']!=task_id:
                raise ValueError('The saved Studio recovery task changed identity; no upload was repeated.')
        elif task['status']=='submitted' and action=='schedule':
            publisher.browser.retry_unapplied_youtube(task_id,private)
        elif task['status'] not in ('queued','running','sharing'):
            return False
    publisher.store.change(job['id'],expected_status=(job['status'],),status='uploaded_private',
        remote=private,error='',error_details='',release_message='Existing private upload verified; continuing the saved release.')
    return True


def recover(workflow, value):
    """Only replay stages with known saved outcomes; never retry uncertain upload."""
    step=value.get('current_step','')
    groups=value.get('jobs',{})
    roles={'long_verify':['long'],'youtube_verify':['youtube'],'instagram_verify':['instagram'],
           'shorts_prepare':[],'long_prepare':[],'shorts_delivery':['youtube','instagram']}.get(step,list(groups))
    # An independent Long failure must not suppress safe recovery of Shorts,
    # captions or their saved releases.
    jobs=[workflow.engine.publisher.store.get(key) for role in roles for key in groups.get(role,[])]
    failed=[j for j in jobs if j['status'] in ('blocked','needs_review')]
    if failed:
        for job in failed:
            if job.get('platform')=='youtube' and job.get('prepare_post_id') and not job.get('remote',{}).get('id'):
                from .youtube_upload import Session
                try:pending=Session(workflow.root,job).resumable()
                except (ValueError,RuntimeError,OSError,KeyError):pending=False
                if pending:
                    raise ReleaseNotReady('Waiting for the saved YouTube transfer to resume automatically. No replacement upload is being created.')
        return all(release(workflow.engine.publisher,j) for j in failed)
    if value.get('current_step') in ('long_prepare', 'shorts_prepare'):
        kind = 'long' if value['current_step']=='long_prepare' else 'shorts'
        key = value.get('preparations', {}).get(kind)
        if key:
            draft = workflow.engine.get(key, value['profile'])
            # run() resumes checkpoints; it never repeats completed stages.
            return draft['status']=='failed' and not draft.get('cancel_requested') and not any(draft.get('jobs_by_platform', {}).values())
    return False
