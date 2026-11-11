"""Bounded Chrome recovery of existing, authorized, pre-submission schedules.

No model inference, YouTube API call, media upload or new publishing intent.
The Chrome executor checks the exact signed-in channel, video and release fields;
normal delivery still independently verifies the resulting schedule.
"""
import json
import re
import time
from datetime import datetime


def active_owner(root, job):
    for path in (root / 'output/publisher-prepare-post/workflows').glob('*.json'):
        try:
            flow = json.loads(path.read_text('utf-8'))
            if flow.get('status') != 'working' or flow.get('profile') != job['profile']:
                continue
            if job['id'] not in [key for role in ('long', 'youtube') for key in flow.get('jobs', {}).get(role, [])]:
                continue
            if (flow.get('intent', {}).get('accounts', {}).get('youtube') != job['account_id'] or
                    job['prepare_post_id'] not in flow.get('preparations', {}).values()):
                continue
            match = re.fullmatch(r'ask-full-([a-f0-9]{16})-[a-f0-9]+', flow.get('request_id', ''))
            if not match:
                continue
            session = json.loads((root / 'cache/assistant' / (match[1] + '.json')).read_text('utf-8'))
            if session.get('stop') or session.get('status') in ('stopped', 'cancelled'):
                continue
            return flow['id']
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def recover(publisher, job, now=None):
    now = time.time() if now is None else now
    if (job.get('status') != 'needs_review' or job.get('platform') != 'youtube' or
            job.get('release_action') != 'schedule' or not job.get('release_authorized_at') or
            not job.get('authorized_at') or not job.get('remote', {}).get('id') or
            not job.get('browser_schedule_id') or job.get('due', 0) <= now + 60):
        return False
    owner = active_owner(publisher.root, job)
    browser = publisher.browser
    if not owner or browser is None or not browser.snapshot().get('youtube_scheduling'):
        return False
    account = publisher.accounts(job['profile']).get('youtube', {})
    if not account.get('connected') or account.get('id') != job['account_id']:
        return False
    # Use the live bridge's lock, never construct another LocalBrowser owner.
    with browser.lock:
        task = browser.get(job['browser_schedule_id'])
        count = task.get('schedule_recovery_count', 0)
        if (task.get('action') != 'youtube_schedule' or task.get('publish_now') or task.get('stop') or
                task.get('status') not in ('needs_review', 'blocked') or
                task.get('submission_started') is not False or
                task.get('video_id') != job['remote']['id'] or task.get('channel_id') != job['account_id'] or
                task.get('session') != 'prepare-post:' + job['prepare_post_id'] or
                datetime.fromisoformat(task['publish_at'].replace('Z', '+00:00')).timestamp() != job['due'] or
                count >= 3 or now < task.get('finished', now) + (15, 60, 180)[count]):
            return False
        # Do not retry identity, permission, changed visibility or uncertain-submit errors.
        if not any(text in task.get('message', '') for text in (
                'Studio did not finish loading', 'Receiving end does not exist',
                'The message port closed', 'The reviewed Studio visibility control disappeared')):
            return False
        recovered = browser.enqueue_youtube(task['channel_id'], task['video_id'], task['publish_at'],
            task['session'], authorized=True, channel_name=account.get('name', ''),
            video_kind=job['kind'])
        if recovered['id'] != task['id']:
            raise ValueError('Recovery changed schedule task identity.')
        saved = next(row for row in browser.data['jobs'] if row['id'] == task['id'])
        saved.update(schedule_recovery_count=count + 1, recovery_agent='chrome-scheduling',
            recovery_workflow=owner, message='Browser recovery agent is reopening this existing video schedule.')
        browser._save()
    publisher.store.change(job['id'], expected_status=('needs_review',), status='processing',
        error='', error_details='', release_message=saved['message'])
    publisher.store.event(job['id'], 'Browser scheduling recovery attempt ' + str(count + 1) +
        ': preserved video, channel, date and pre-submission receipt. Cause: ' + task.get('message', ''))
    return True
