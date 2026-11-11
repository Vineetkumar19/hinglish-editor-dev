"""Explicit release intent and receipt-only YouTube Studio handoff."""
import hashlib
import time
from datetime import datetime, timedelta

from .store import IST


def evening_slots(key, count, now, after=None):
    day = datetime.fromtimestamp(now, IST).date()
    if after:
        day = max(day, datetime.fromtimestamp(after, IST).date() + timedelta(days=1))
    result = []
    for n in range(count):
        while True:
            minute = 18 * 60 + int(hashlib.sha256(f'{key}:{n}:{day}'.encode()).hexdigest()[:8], 16) % 121
            due = datetime(day.year, day.month, day.day, minute // 60, minute % 60, tzinfo=IST).timestamp()
            if due > now + 300:
                break
            day += timedelta(days=1)
        result.append(due)
        day += timedelta(days=1)
    return result


def set_action(engine, key, profile, platform, action):
    if action not in ('post_now', 'schedule'):
        raise ValueError('Choose Post now or Schedule.')
    draft = engine.get(key, profile)
    if platform not in draft['platforms']:
        raise ValueError('Choose a platform supported by this preparation.')
    jobs = [engine.publisher.store.get(i) for i in draft['jobs_by_platform'].get(platform, [])]
    previous = draft.get('release_actions', {}).get(platform)
    if previous and previous != action:
        raise ValueError('This preparation already has a different release choice. Review its existing receipt before changing it.')
    if jobs and any(j.get('prepare_post_id') != key for j in jobs):
        raise ValueError('This upload belongs to another saved preparation. Review its existing receipt.')
    if jobs and any(j['status'] in ('published', 'scheduled', 'needs_review', 'cancelled') for j in jobs):
        # An ordinary second click never changes a remotely submitted result.
        return draft
    draft.setdefault('release_actions', {})[platform] = action
    if action == 'schedule':
        requested=draft.get('requested_release_slots',{}).get(platform)
        if requested is not None:
            if len(requested)!=draft['count'] or any(type(t) not in (int,float) or t<=time.time()+30 for t in requested):
                raise ValueError('The requested release time passed. Saved progress and existing uploads were kept.')
            slots=list(requested)
        # Shared slots pair Shorts and Reels. Legacy slots on this un-released
        # private upload are replaced once; accepted remote schedules are above.
        elif not draft.get('evening_slots_v2'):
            existing = [j['due'] for j in engine.publisher.store.list()
                        if j.get('profile') == profile and j.get('kind') == 'short'
                        and j.get('prepare_post_id') != key and j['status'] != 'cancelled'] if draft['mode'] == 'shorts' else []
            draft['slots'] = evening_slots(key, draft['count'], time.time(), max(existing) if existing else None)
            draft['evening_slots_v2'] = True
        if requested is None:slots = draft['slots']
    else:
        slots = [time.time()] * draft['count']
    draft.setdefault('release_slots', {})[platform] = slots
    engine._save(draft)
    for n, job in enumerate(jobs):
        engine.publisher.store.change(job['id'], release_action=action, release_authorized_at=time.time(), due=slots[n])
    return draft


def advance_youtube(publisher, job):
    """Never upload bytes: operate solely on the saved video ID, then API-read back."""
    from hinglish_app.assistant_schedule import verify
    action = job['release_action']
    if action not in ('schedule', 'post_now') or not job.get('release_authorized_at'):
        raise ValueError('This saved upload has no explicit release authorization.')
    if not job.get('remote', {}).get('id'):
        raise ValueError('Wait for the existing upload receipt before releasing this video.')
    account = publisher.accounts(job['profile']).get('youtube', {})
    if not account.get('connected') or account.get('id') != job['account_id']:
        raise ValueError('The saved YouTube channel changed. Review its connection before release.')
    instant = datetime.fromtimestamp(job['due'], IST).isoformat() if action == 'schedule' else ''
    remote = verify(publisher.root, job, instant)
    if remote:
        if job.get('browser_schedule_id') and publisher.browser is not None:
            publisher.browser.confirm_youtube(job['browser_schedule_id'],remote)
        return {'remote': remote, 'status': 'scheduled' if instant else 'published', 'release_message': 'Verified by YouTube.'}
    browser = publisher.browser
    if browser is None:
        return {'status': 'processing', 'release_message': 'Private upload saved. Waiting for Storylens Local Publisher in Chrome.'}
    task_id = job.get('browser_schedule_id')
    if task_id:
        task = browser.get(task_id)
        if task['video_id'] != job['remote']['id'] or task['channel_id'] != job['account_id']:
            raise ValueError('The saved Studio receipt belongs to a different video or channel.')
        if task['status'] in ('needs_review', 'blocked', 'cancelled'):
            raise ValueError(task['message'])
        if task['status']=='submitted' and task.get('unapplied_retry_count',0)<2 and time.time()-task.get('submitted_at',time.time())>60:
            # A click is uncertain until API readback. Reapply this same setting
            # only when the exact upload is positively observed private/unscheduled.
            private=verify(publisher.root,job,'',private_only=True)
            if private:
                task=browser.retry_unapplied_youtube(task_id,private)
        if time.time() - task.get('updated',task['created']) > 1200:
            raise ValueError('Studio release is not yet verified. Check its saved receipt; no second submission was sent.')
    else:
        if instant and job['due'] <= time.time() + 60:
            raise ValueError('The release time passed while uploading. Choose a new future schedule for the saved video; do not upload it again.')
        if not browser.snapshot().get('youtube_scheduling'):
            return {'status': 'processing', 'release_message': 'Private upload saved. Waiting for Storylens Local Publisher in Chrome.'}
        # Upload completion is not processing completion: Studio can still show
        # Pending with no editable visibility control. Wait for exact-ID/channel/
        # copy readback before handing the saved private upload to Studio.
        private = verify(publisher.root, job, '', private_only=True)
        if not private:
            return {'status': 'processing', 'release_message':
                    'YouTube is still processing the saved private upload. Waiting before scheduling; no upload is repeated.'}
        task = browser.enqueue_youtube(job['account_id'], job['remote']['id'], instant,
            'prepare-post:' + job['prepare_post_id'], authorized=True,
            channel_name=account.get('name', ''), video_kind=job['kind'], publish_now=action == 'post_now')
        task_id = task['id']
    return {'status': 'processing', 'browser_schedule_id': task_id,
            'release_message': task.get('message', 'Waiting for YouTube Studio verification.')}
