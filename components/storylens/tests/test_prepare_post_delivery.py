"""Dry transport checks for the explicit Prepare/Post delivery queue."""
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_delivery import Delivery
from hinglish_publish.providers import PreflightError
from hinglish_publish.store import Store, fingerprint


class DeliveryTests(unittest.TestCase):
    def test_disconnected_due_reel_waits_and_retries_only_after_backoff(self):
        from hinglish_publish.browser_provider import ConnectorOffline
        key=self.job(platform='instagram',due=time.time()-5)
        self.transport.publish.side_effect=ConnectorOffline('Waiting for Chrome')
        result=self.delivery.tick()
        self.assertEqual(result['status'],'ready')
        self.assertGreater(result['delivery_retry_after'],time.time())
        self.delivery.tick()
        self.transport.publish.assert_called_once()
        self.pub.store.change(key,delivery_retry_after=0)
        self.transport.publish.side_effect=None
        self.delivery.tick()
        self.assertEqual(self.pub.store.get(key)['status'],'uploaded_private')

    def test_network_upload_does_not_block_due_reel_or_existing_release(self):
        youtube = self.job()
        started, unblock, reel = threading.Event(), threading.Event(), threading.Event()
        def publish(job, checkpoint):
            if job['platform']=='youtube':
                started.set()
                if not unblock.wait(5): raise RuntimeError('test upload gate timeout')
            else:
                reel.set()
            return {'id':'fixture-'+job['platform']}, 'uploaded_private'
        self.transport.publish.side_effect=publish
        self.delivery.tick(background=True)
        self.assertTrue(started.wait(2))
        try:
            instagram=self.job(platform='instagram',due=time.time()-5)
            self.delivery.tick(background=True)
            self.assertTrue(reel.wait(2),'Due Instagram dispatch was blocked behind YouTube bytes')
            self.delivery.tick(background=True)
            self.assertEqual(self.pub.store.get(youtube)['status'],'uploading')
            self.assertEqual(sum(c.args[0]['platform']=='youtube' for c in self.transport.publish.call_args_list),1)
        finally:
            unblock.set()
            for worker in self.delivery.uploads.values():worker.join(3)
        self.assertEqual(self.pub.store.get(instagram)['remote']['id'],'fixture-instagram')

    def test_thread_start_failure_keeps_same_job_ready_without_submission(self):
        key=self.job()
        with patch('hinglish_publish.prepare_post_delivery.threading.Thread') as worker:
            worker.return_value.start.side_effect=RuntimeError('cannot start thread')
            self.delivery.tick(background=True)
        result=self.pub.store.get(key)
        self.assertEqual(result['status'],'ready')
        self.assertGreater(result['delivery_retry_after'],time.time())
        self.transport.publish.assert_not_called()
        self.assertEqual(self.delivery.uploads,{})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / 'finished.mp4'
        self.video.write_bytes(b'fixture video')
        self.pub = Mock(root=self.root)
        self.pub.store = Store(self.root)
        self.pub.settings.return_value = {'enabled': True}
        self.pub.accounts.return_value = {'youtube': {'connected': True, 'id': 'yt'}, 'instagram': {'connected': True, 'id': 'ig', 'transport': 'browser'}}
        self.transport = Mock()
        self.transport.publish.return_value = ({'id': 'fixture-remote'}, 'uploaded_private')
        self.pub.provider.return_value = self.transport
        self.delivery = Delivery(self.pub)

    def job(self, own=True, platform='youtube', due=None):
        item = {'video': str(self.video), 'fingerprint': fingerprint(self.video), 'kind': 'long', 'profile': 'cricket',
                'platform': platform, 'metadata': {'title': 'Fixture', 'description': 'Fixture', 'instagram_caption': 'Fixture', 'tags': []},
                'visibility': 'private', 'account_id': 'yt' if platform == 'youtube' else 'ig', 'thumbnail': '',
                'authorized_at': time.time(), **({'prepare_post_id': 'owned'} if own else {})}
        if platform == 'instagram': item['transport'] = 'browser'
        key = self.pub.store.add_batch([item])[0]
        self.pub.store.change(key, status='ready', due=due or time.time())
        return key

    def test_legacy_ready_jobs_are_never_claimed(self):
        key = self.job(own=False)
        self.assertIsNone(self.delivery.tick())
        self.assertEqual(self.pub.store.get(key)['status'], 'ready')
        self.transport.publish.assert_not_called()

    def test_explicit_owned_post_calls_existing_transport_once(self):
        key = self.job()
        self.assertEqual(self.delivery.tick()['status'], 'uploaded_private')
        self.delivery.tick()
        self.assertEqual(self.transport.publish.call_count, 1)
        self.assertEqual(self.pub.store.get(key)['remote']['id'], 'fixture-remote')

    def test_future_instagram_waits_for_its_saved_local_time(self):
        key = self.job(platform='instagram', due=time.time() + 86400)
        self.assertIsNone(self.delivery.tick())
        self.assertEqual(self.pub.store.get(key)['status'], 'ready')
        self.transport.publish.assert_not_called()

    def test_unknown_upload_outcome_requires_review_without_retry(self):
        key = self.job()
        self.transport.publish.side_effect = RuntimeError('uncertain network result')
        self.assertEqual(self.delivery.tick()['status'], 'needs_review')
        self.delivery.tick()
        self.assertEqual(self.transport.publish.call_count, 1)

    def test_dead_upload_owner_is_not_left_uploading_or_reuploaded(self):
        key=self.job();self.pub.store.change(key,status='uploading',delivery_owner=987654,
            remote={'id':'saved-remote'})
        with patch('psutil.pid_exists',return_value=False):self.delivery.tick()
        job=self.pub.store.get(key)
        self.assertEqual(job['status'],'needs_review');self.assertEqual(job['remote']['id'],'saved-remote')
        self.assertEqual(job['error_code'],'upload_interrupted');self.transport.publish.assert_not_called()

    def test_slow_live_upload_owner_is_not_interrupted(self):
        key=self.job();self.pub.store.change(key,status='uploading',delivery_owner=987654)
        with patch('psutil.pid_exists',return_value=True):self.delivery.tick()
        self.assertEqual(self.pub.store.get(key)['status'],'uploading');self.transport.publish.assert_not_called()

    def test_saved_transfer_recovers_after_error_without_waiting_for_process_exit(self):
        key=self.job();self.pub.store.change(key,status='needs_review',delivery_owner=987654,error='transfer interrupted')
        with patch('psutil.pid_exists',return_value=True),patch('hinglish_publish.youtube_upload.Session') as saved:
            saved.return_value.ready.return_value=True
            result=self.delivery.tick()
        self.assertEqual(result['status'],'uploaded_private');self.transport.publish.assert_called_once()

    def test_session_retry_backoff_does_not_reclaim_before_ready(self):
        key=self.job();self.pub.store.change(key,status='needs_review',delivery_owner=987654)
        with patch('psutil.pid_exists',return_value=True),patch('hinglish_publish.youtube_upload.Session') as saved:
            saved.return_value.ready.return_value=False
            self.delivery.tick()
        self.assertEqual(self.pub.store.get(key)['status'],'needs_review');self.transport.publish.assert_not_called()

    def test_partial_remote_receipt_survives_a_later_transport_error(self):
        key = self.job()
        def publish(job, checkpoint):
            checkpoint({'id': 'saved-before-error'})
            raise RuntimeError('verification response lost')
        self.transport.publish.side_effect = publish
        result = self.delivery.tick()
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(self.pub.store.get(key)['remote']['id'], 'saved-before-error')
        self.delivery.tick()
        self.assertEqual(self.transport.publish.call_count, 1)

    def test_disabled_profile_and_changed_account_do_not_upload(self):
        key = self.job()
        self.pub.settings.return_value = {'enabled': False}
        self.assertIsNone(self.delivery.tick())
        self.pub.settings.return_value = {'enabled': True}
        self.pub.accounts.return_value['youtube']['id'] = 'other'
        self.assertEqual(self.delivery.tick()['status'], 'blocked')
        self.transport.publish.assert_not_called()

    def test_saved_private_release_uses_receipt_path_without_uploading_bytes(self):
        key=self.job()
        self.pub.store.change(key,status='uploaded_private',remote={'id':'existing'},
            release_action='schedule',release_authorized_at=time.time())
        with patch('hinglish_publish.prepare_post_release.advance_youtube',return_value={
                'status':'processing','browser_schedule_id':'studio'}) as release:
            result=self.delivery.tick()
        self.assertEqual(result['status'],'processing')
        self.assertEqual(result['remote']['id'],'existing')
        release.assert_called_once()
        self.transport.publish.assert_not_called()

    def test_uncertain_release_failure_never_reuploads_or_resubmits(self):
        key=self.job()
        self.pub.store.change(key,status='uploaded_private',remote={'id':'existing'},
            release_action='schedule',release_authorized_at=time.time())
        with patch('hinglish_publish.prepare_post_release.advance_youtube',side_effect=ValueError('Check receipt')) as release:
            self.assertEqual(self.delivery.tick()['status'],'needs_review')
            self.delivery.tick()
        release.assert_called_once()
        self.transport.publish.assert_not_called()

    def test_due_instagram_is_not_starved_by_waiting_youtube_release_checks(self):
        youtube=self.job()
        self.pub.store.change(youtube,status='uploaded_private',remote={'id':'existing'},
            release_action='schedule',release_authorized_at=time.time())
        instagram=self.job(platform='instagram',due=time.time()-5)
        with patch('hinglish_publish.prepare_post_release.advance_youtube') as release:
            result=self.delivery.tick()
        self.assertEqual(result['id'],instagram)
        self.transport.publish.assert_called_once()
        release.assert_not_called()


if __name__ == '__main__': unittest.main()
