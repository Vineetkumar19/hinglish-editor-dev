"""Dismiss failed list entries without destroying receipts or platform videos."""
import time


def available(platform, job, bridge):
    from .scheduled_posts import failed_in_panel
    failed = failed_in_panel(platform, job) or (platform == 'instagram' and job.get('prepare_post_id')
              and job['status'] in ('needs_review', 'blocked', 'failed') and not job.get('scheduled_panel_deleted_at'))
    if not failed or job.get('scheduled_action', {}).get('status') == 'working':
        return False
    for identity in job.get('scheduled_action', {}).get('browser_ids', []):
        try:
            if bridge.get(identity)['status'] in ('queued', 'running', 'sharing'):
                return False
        except ValueError:
            continue
    return True


def delete_failed(manager, payload):
    from .scheduled_posts import revision
    state = manager.state
    with manager.lock, state.assistant.lock:
        platform, job = manager._job(payload.get('id'))
        if payload.get('revision') != revision(job):
            raise ValueError('This entry changed. Refresh Failed attempts before deleting it.')
        if not available(platform, job, state.local_browser):
            raise ValueError('Only a failed attempt that is no longer working can be removed from this list.')
        stamp = time.time()
        if platform == 'instagram' and job.get('action') == 'reel':
            bridge = state.local_browser
            with bridge.lock:
                current = next(j for j in bridge.data['jobs'] if j['id'] == job['id'])
                if revision(current) != payload['revision'] or not available(platform, current, bridge):
                    raise ValueError('This Reel changed. Refresh Failed attempts before deleting it.')
                current['scheduled_panel_deleted_at'] = stamp
                bridge._save()
        else:
            state.publisher.store.change(job['id'], expected_status=(job['status'],),
                                         scheduled_panel_deleted_at=stamp)
        return {'message': 'Deleted from Failed attempts. The platform video is unchanged.',
                'deleted_id': payload['id']}
