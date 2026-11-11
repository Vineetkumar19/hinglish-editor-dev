"""Cancel one pending delivery; retain files, upload IDs and duplicate guards."""
import copy
import threading
import time
import uuid


def verified_private(store, job, operation):
    """Called only after exact-channel private/no-release-date API readback."""
    stamp = time.time()
    remote = {**job['remote'], 'privacy': 'private', 'publish_at': '', 'cancellation_verified_at': stamp}
    remote.pop('schedule_verified_at', None)
    operation.update(status='complete', message='Schedule cancelled and verified. The YouTube video remains private.')
    store.change(job['id'], expected_status=('scheduled',), status='cancelled', cancelled_at=stamp,
                 remote=remote, scheduled_action=operation)


def available(platform, job, bridge):
    if platform == 'instagram':
        if job.get('action') == 'reel':
            return job['status'] == 'queued' and job.get('submission_started') is False and not job.get('stop')
        return job['status'] == 'ready' and not job.get('remote')
    return (job['status'] == 'scheduled' and bool(job.get('remote', {}).get('id'))
            and job.get('scheduled_action', {}).get('status') not in ('working', 'needs_review')
            and bool(bridge.snapshot().get('youtube_private_cleanup')))


def cancel(manager, payload):
    from .scheduled_posts import revision
    state = manager.state
    with manager.lock, state.assistant.lock:
        platform, job = manager._job(payload.get('id'))
        if payload.get('revision') != revision(job):
            raise ValueError('This post changed. Refresh the list before cancelling it.')
        if not available(platform, job, state.local_browser):
            raise ValueError('This post has started or cannot be cancelled here. Check its platform result; no post was deleted.')
        if platform == 'instagram':
            if job.get('action') != 'reel':
                # CAS shares the delivery claim transaction: cancellation cannot
                # overtake an item already claimed for upload.
                state.publisher.store.change(job['id'], expected_status=('ready',), status='cancelled',
                                             cancelled_at=time.time(), error='')
            else:
                bridge = state.local_browser
                with bridge.lock:
                    current = next(j for j in bridge.data['jobs'] if j['id'] == job['id'])
                    if revision(current) != payload['revision'] or not available(platform, current, bridge):
                        raise ValueError('This Reel has started. Check Instagram before making another change.')
                    current.update(status='cancelled', stop=True, cancelled_at=time.time(), message='Schedule cancelled by you; no upload was started.')
                    check = next((j for j in bridge.data['jobs'] if j['id'] == current.get('preflight_id')), None)
                    if check and check['status'] == 'queued':
                        check.update(status='cancelled', stop=True, message='The related Reel schedule was cancelled.')
                    bridge._save()
                # Retire the corresponding handed-off publisher row as well.
                for linked in state.publisher.store.list():
                    if linked.get('platform') == 'instagram' and linked.get('remote', {}).get('browser_job_id') == job['id']:
                        if linked['status'] in ('processing', 'ready', 'blocked', 'needs_review'):
                            state.publisher.store.change(linked['id'], expected_status=(linked['status'],),
                                                         status='cancelled', cancelled_at=time.time())
            return {'message':'Instagram schedule cancelled. The saved video is kept.'}
        operation = {'id':uuid.uuid4().hex, 'status':'working', 'action':'cancel', 'created':time.time(),
                     'message':'Cancelling the scheduled release; keeping the YouTube video private.', 'browser_ids':[]}
        state.publisher.store.change(job['id'], expected_status=('scheduled',), scheduled_action=operation)
        threading.Thread(target=manager._youtube, args=(job, copy.deepcopy(job['metadata']), False, operation), daemon=True).start()
        return {'message':'Cancelling this YouTube schedule. It is complete only after private visibility and no release date are verified.'}
