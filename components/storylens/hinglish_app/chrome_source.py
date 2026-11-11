"""Browser-only Instagram snapshots using StoryLens's existing paired worker."""
import time

from .analytics_sources import ACCOUNTS, SourceError


def collect(browser, account, today, emit):
    _, profile, _, handle = ACCOUNTS[account]
    try:
        job_id = browser.enqueue_instagram_analytics(profile, handle)
    except ValueError as error:
        return 'needs_connection', [str(error)]
    try:
        deadline = time.monotonic() + 250
        while time.monotonic() < deadline:
            job = browser.get(job_id)
            if job['status'] == 'complete':
                record = job['analytics']
                emit('snapshot', today, '', record['snapshot'])
                if record['rolling']:
                    emit('browser_30d', today, '', record['rolling'])
                for item in record['content']:
                    emit('content', today, item['id'], {key: value for key, value in item.items() if key != 'id'})
                return ('analytics' if record['rolling'] else 'counters'), record['notes']
            if job['status'] not in ('queued', 'running'):
                raise SourceError(job.get('message') or 'Chrome could not read this Instagram profile.')
            time.sleep(.5)
        raise SourceError('Chrome did not finish this read. Keep the paired profile open and refresh again.')
    finally:
        browser.finish_instagram_analytics_wait(job_id)
