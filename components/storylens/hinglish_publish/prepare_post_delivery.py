"""Run only explicitly authorized Prepare/Post items through existing transports.

The general Publisher worker stays paused. Legacy queue items are never claimed.
"""
import os
import threading
import time

from hinglish_app.user_messages import failure
from .providers import PreflightError
from .browser_provider import ConnectorOffline
from .store import fingerprint


class Delivery:
    def __init__(self, publisher):
        self.publisher = publisher
        self.thread = None
        self.lock = threading.Lock()
        self.last_verify = 0
        self.last_release = {}
        self.uploads = {}  # At most one transport thread per platform.

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def start(self):
        with self.lock:
            if self.running:
                return
            self.thread = threading.Thread(target=self._work, name='prepare-post-delivery', daemon=True)
            self.thread.start()

    def _work(self):
        while not self.publisher.stop.is_set():
            try:
                self.tick(background=True)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Prepare/Post delivery check failed')
            if self.publisher.stop.wait(5):
                break

    def _verify(self, now):
        if now - self.last_verify < 30:
            return
        self.last_verify = now
        for job in self.publisher.store.list():
            if not job.get('prepare_post_id') or job['status'] not in ('processing', 'scheduled') or job['due'] > now:
                continue
            if job.get('release_action') and job['platform'] == 'youtube' and job['status'] == 'processing':
                continue  # Studio release requires exact intent/metadata readback below.
            config = self.publisher.settings(profile=job['profile'])
            if not config.get('enabled'):
                continue
            try:
                status = self.publisher.provider(job, config).verify(job)
                self.publisher.store.change(job['id'], expected_status=('processing', 'scheduled'), status=status, remote=job['remote'])
            except Exception as error:
                issue = failure(error, feature='Platform verification')
                self.publisher.store.change(job['id'], expected_status=('processing', 'scheduled'), status='needs_review', **issue)

    def tick(self, *, background=False):
        publisher = self.publisher
        now = time.time()
        self._check_upload_owners()
        self._verify(now)
        candidates = sorted(publisher.store.list(), key=lambda j: (0 if j.get('platform') == 'instagram' and j['due'] <= now else 1, j['due']))
        for candidate in candidates:
            if (not candidate.get('prepare_post_id') or candidate['status'] != 'ready'
                    or not candidate.get('authorized_at')
                    or candidate.get('delivery_retry_after', 0) > now
                    or candidate['platform'] == 'instagram' and candidate['due'] > now):
                continue
            active = self.uploads.get(candidate['platform'])
            if background and active and active.is_alive():
                continue
            config = publisher.settings(profile=candidate['profile'])
            if not config.get('enabled'):
                continue
            try:
                # Store.change uses BEGIN IMMEDIATE, shared with the existing
                # worker's claim, so only one transport can own this item.
                publisher.store.change(candidate['id'], expected_status=('ready',), status='uploading', delivery_owner=os.getpid())
            except ValueError:
                continue
            job = publisher.store.get(candidate['id'])
            if not background:
                return self._upload(job, config)
            try:
                worker = threading.Thread(target=self._upload, args=(job, config),
                    name='prepare-post-upload-' + job['platform'], daemon=True)
                self.uploads[job['platform']] = worker
                worker.start()
            except RuntimeError:
                # Thread creation failed before any provider invocation. Keep
                # the same authorized item eligible after a short backoff.
                self.uploads.pop(job['platform'], None)
                publisher.store.change(job['id'], expected_status=('uploading',),
                    status='ready', delivery_retry_after=time.time()+30,
                    release_message='Waiting for the local delivery worker to become available.')
        # Transfer bytes in bounded platform workers. A slow YouTube transfer
        # must not block due Instagram dispatch or verification of saved IDs.
        return self._release(now)

    def _upload(self, job, config):
        publisher = self.publisher
        try:
            account = publisher.accounts(job['profile']).get(job['platform'], {})
            if not account.get('connected') or account.get('id') != job.get('account_id'):
                raise PreflightError('The saved destination account changed. Check this draft before posting.')
            if job['platform'] == 'instagram' and (job.get('transport') != 'browser' or account.get('transport') != 'browser'):
                raise PreflightError('Connect Instagram through the existing Chrome connector before posting.')
            from .channel_queue_service import check_authorization_binding
            check_authorization_binding(job, publisher.accounts(job['profile']))
            if fingerprint(job['video']) != job['fingerprint']:
                raise PreflightError('The prepared video changed. Select and prepare the updated file before posting.')
            if job.get('thumbnail') and fingerprint(job['thumbnail']) != job.get('thumbnail_fingerprint'):
                raise PreflightError('The prepared thumbnail changed. Check the selected thumbnail before posting.')
            def checkpoint(remote):
                publisher.store.change(job['id'], expected_status=('uploading',), remote=remote)
            def upload_progress(measure):
                publisher.store.change(job['id'],expected_status=('uploading',),upload_progress=measure)
            checkpoint.progress=upload_progress
            remote, status = publisher.provider(job, config).publish(job, checkpoint)
            publisher.store.change(job['id'], expected_status=('uploading',), remote=remote, status=status, error='')
            publisher.store.event(job['id'], 'Prepare/Post transport result: ' + status)
        except ConnectorOffline as error:
            # BrowserInstagram raises this only BEFORE enqueue/Share. Waiting
            # for reconnect cannot duplicate a post; uncertain submissions still
            # use needs_review and are never silently replayed.
            publisher.store.change(job['id'], expected_status=('uploading',), status='ready',
                delivery_retry_after=time.time()+30, release_message=str(error), error='')
        except PreflightError as error:
            issue = failure(error, feature='Posting')
            publisher.store.change(job['id'], expected_status=('uploading',), status='blocked', **issue)
        except Exception as error:
            issue = failure(error, feature='Posting')
            issue['error'] = 'The upload result needs review. Check the saved platform receipt before retrying; no second upload was started.'
            publisher.store.change(job['id'], expected_status=('uploading',), status='needs_review', **issue)
        return publisher.store.get(job['id'])

    def _check_upload_owners(self):
        """A dead transport is not an active upload; never replay unknown bytes."""
        import psutil
        for job in self.publisher.store.list():
            owner=job.get('delivery_owner')
            if (not job.get('prepare_post_id') or job['status'] not in ('uploading','needs_review')
                    or not isinstance(owner,int) or owner<=0):
                continue
            live=psutil.pid_exists(owner)
            if job['status']=='uploading' and live:continue
            if job['platform']=='youtube' and not job.get('remote',{}).get('id'):
                from .youtube_upload import Session
                try:
                    session=Session(self.publisher.root,job)
                    if session.ready():
                        self.publisher.store.change(job['id'],expected_status=(job['status'],),status='ready',error='',
                            error_details='',upload_progress={**job.get('upload_progress',{}),'state':'resuming'})
                        self.publisher.store.event(job['id'],'Continuing the encrypted saved YouTube transfer; no new upload session.')
                        continue
                except (ValueError,RuntimeError,OSError):
                    pass  # No usable positively bound checkpoint: never insert again.
            if job['status']!='uploading' or live:continue
            try:
                self.publisher.store.change(job['id'],expected_status=('uploading',),status='needs_review',
                    error='The upload worker stopped. The platform outcome must be checked before retrying; the saved file and any receipt are kept.',
                    error_code='upload_interrupted',error_details='The saved upload owner process is no longer running.')
                self.publisher.store.event(job['id'],'Upload owner exited; preserved receipt and blocked duplicate submission.')
            except ValueError:
                continue  # Another live owner may have just committed its result.

    def _release(self, now):
        publisher = self.publisher
        for job in publisher.store.list():
            if job.get('status') == 'needs_review':
                from .scheduling_recovery_agent import recover
                if recover(publisher, job, now):
                    return publisher.store.get(job['id'])
            if (job.get('prepare_post_id') and job.get('release_authorized_at')
                    and job.get('release_action') and job['platform'] == 'youtube'
                    and job['status'] in ('uploaded_private', 'processing')):
                if now - self.last_release.get(job['id'], 0) < 15:
                    continue
                if not publisher.settings(profile=job['profile']).get('enabled'):
                    continue
                self.last_release[job['id']] = now
                try:
                    from .prepare_post_release import advance_youtube
                    changes = advance_youtube(publisher, job)
                    publisher.store.change(job['id'], expected_status=(job['status'],), **changes)
                except Exception as error:
                    issue = failure(error, feature='YouTube release')
                    publisher.store.change(job['id'], expected_status=(job['status'],), status='needs_review', **issue)
                return publisher.store.get(job['id'])
        return None
