"""Release contracts; platform acceptance requires real receipts separately."""
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_release import evening_slots, advance_youtube
from hinglish_publish.store import IST
from tests import test_prepare_post as preparation_fixtures


class ReleaseTests(unittest.TestCase):
    setUp = preparation_fixtures.PreparePostTests.setUp
    draft = preparation_fixtures.PreparePostTests.draft
    def test_evening_slots_are_future_daily_and_stable_across_midnight(self):
        now = datetime(2026, 10, 29, 20, 5, tzinfo=IST).timestamp()
        slots = evening_slots('saved', 5, now)
        self.assertEqual(slots, evening_slots('saved', 5, now))
        self.assertEqual(len({datetime.fromtimestamp(x, IST).date() for x in slots}), 5)
        self.assertTrue(all(18*60 <= datetime.fromtimestamp(x, IST).hour*60+datetime.fromtimestamp(x, IST).minute <= 20*60 for x in slots))
        self.assertTrue(all(x > now for x in slots))

    def authorize_real(self, payload):
        for key in payload['ids']:
            self.publisher.store.change(key, expected_status=('draft','blocked'), status='ready', authorized_at=time.time())

    def test_two_concurrent_post_clicks_authorize_and_queue_once(self):
        draft = self.draft('long'); self.service.run(draft['id'], 'cricket')
        self.publisher.authorize.side_effect = self.authorize_real
        self.service.start_delivery = Mock()
        errors = []
        def click():
            try:self.service.post(draft['id'], 'cricket', 'youtube', {}, 'schedule')
            except Exception as e:errors.append(str(e))
        threads = [threading.Thread(target=click) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(self.publisher.store.list()), 1)
        self.assertEqual(self.publisher.authorize.call_count, 1)
        job = self.publisher.store.list()[0]
        self.assertEqual(job['release_action'], 'schedule')
        self.assertEqual(job['visibility'], 'private')
        self.assertGreater(job['due'], time.time())

    def test_private_upload_can_schedule_same_id_without_authorizing_upload_again(self):
        draft = self.draft('long');self.service.run(draft['id'], 'cricket')
        original = self.service.queue(draft['id'], 'cricket', 'youtube')[0]
        self.publisher.store.change(original['id'], status='uploaded_private', authorized_at=time.time(), remote={'id':'saved-video'})
        self.service.start_delivery = Mock()
        result=self.service.post(draft['id'], 'cricket', 'youtube', {}, 'schedule')
        self.assertEqual(result['jobs'][0]['id'], original['id'])
        self.assertEqual(result['jobs'][0]['remote']['id'], 'saved-video')
        self.assertEqual(len(self.publisher.store.list()), 1)
        self.publisher.authorize.assert_not_called()
        self.service.start_delivery.assert_called_once()

    def test_short_schedule_pairs_youtube_instagram_and_now_is_not_future(self):
        draft=self.draft();self.service.run(draft['id'],'cricket')
        self.publisher.authorize.side_effect=self.authorize_real;self.service.start_delivery=Mock()
        yt=self.service.post(draft['id'],'cricket','youtube',{},'schedule')['jobs']
        ig=self.service.post(draft['id'],'cricket','instagram',{},'schedule')['jobs']
        self.assertEqual([j['due'] for j in yt],[j['due'] for j in ig])
        with self.assertRaisesRegex(ValueError,'different release'):
            self.service.post(draft['id'],'cricket','youtube',{},'post_now')

    def test_post_now_is_public_intent_with_private_transport_and_immediate_due(self):
        draft=self.draft('long');self.service.run(draft['id'],'cricket')
        self.publisher.authorize.side_effect=self.authorize_real;self.service.start_delivery=Mock()
        job=self.service.post(draft['id'],'cricket','youtube',{},'post_now')['jobs'][0]
        self.assertEqual(job['release_action'],'post_now')
        self.assertEqual(job['visibility'],'private')
        self.assertLess(abs(job['due']-time.time()),5)


class StudioHandoffTests(unittest.TestCase):
    def setUp(self):
        self.publisher=Mock(root=Path('.'))
        self.publisher.accounts.return_value={'youtube':{'connected':True,'id':'channel','name':'Cricket'}}
        self.publisher.browser.snapshot.return_value={'youtube_scheduling':True}
        self.publisher.browser.enqueue_youtube.return_value={'id':'studio','status':'queued','message':'Waiting'}
        self.job={'id':'queue','prepare_post_id':'owned','profile':'cricket','account_id':'channel','kind':'long',
            'release_action':'schedule','release_authorized_at':time.time(),'due':time.time()+3600,'remote':{'id':'saved-video'}}

    @patch('hinglish_app.assistant_schedule.verify',side_effect=[None,{'id':'saved-video','privacy':'private','private_verified_at':123}])
    def test_release_only_enqueues_saved_id_and_does_not_assert_remote_success(self,verify):
        result=advance_youtube(self.publisher,self.job)
        self.assertEqual(result['status'],'processing')
        self.assertEqual(result['browser_schedule_id'],'studio')
        self.assertEqual(self.publisher.browser.enqueue_youtube.call_args.args[:2],('channel','saved-video'))
        self.publisher.provider.assert_not_called()
        self.assertEqual(verify.call_args.kwargs,{'private_only':True})

    @patch('hinglish_app.assistant_schedule.verify',return_value=None)
    def test_processing_private_upload_waits_without_starting_studio(self,verify):
        result=advance_youtube(self.publisher,self.job)
        self.assertEqual(result['status'],'processing')
        self.assertIn('still processing',result['release_message'])
        self.assertNotIn('browser_schedule_id',result)
        self.publisher.browser.enqueue_youtube.assert_not_called()
        self.publisher.provider.assert_not_called()

    @patch('hinglish_app.assistant_schedule.verify',side_effect=[None,ValueError('The reviewed YouTube channel changed.')])
    def test_initial_processing_gate_preserves_exact_identity_failure(self,verify):
        with self.assertRaisesRegex(ValueError,'channel changed'):
            advance_youtube(self.publisher,self.job)
        self.publisher.browser.enqueue_youtube.assert_not_called()

    @patch('hinglish_app.assistant_schedule.verify',return_value={'id':'saved-video','schedule_verified_at':123})
    def test_exact_api_receipt_completes_without_another_studio_submission(self,verify):
        self.assertEqual(advance_youtube(self.publisher,self.job)['status'],'scheduled')
        self.publisher.browser.enqueue_youtube.assert_not_called()

    @patch('hinglish_app.assistant_schedule.verify',return_value=None)
    def test_uncertain_studio_result_is_never_submitted_twice(self,verify):
        self.job['browser_schedule_id']='studio'
        self.publisher.browser.get.return_value={'video_id':'saved-video','channel_id':'channel','status':'needs_review','message':'Check receipt'}
        with self.assertRaisesRegex(ValueError,'Check receipt'):advance_youtube(self.publisher,self.job)
        self.publisher.browser.enqueue_youtube.assert_not_called()

    @patch('hinglish_app.assistant_schedule.verify',return_value=None)
    def test_passed_time_keeps_existing_upload_and_never_schedules_past(self,verify):
        self.job['due']=time.time()-10
        with self.assertRaisesRegex(ValueError,'time passed'):advance_youtube(self.publisher,self.job)
        self.publisher.browser.enqueue_youtube.assert_not_called()

    @patch('hinglish_app.assistant_schedule.verify',return_value=None)
    def test_connector_reconnect_waits_without_failed_or_duplicate_submission(self,verify):
        self.publisher.browser.snapshot.return_value={'youtube_scheduling':False}
        value=advance_youtube(self.publisher,self.job)
        self.assertEqual(value['status'],'processing')
        self.assertIn('Waiting',value['release_message'])
        self.publisher.browser.enqueue_youtube.assert_not_called()

    @patch('hinglish_app.assistant_schedule.verify')
    def test_unapplied_schedule_retries_same_task_only_after_positive_private_readback(self,verify):
        self.job['browser_schedule_id']='studio'
        self.publisher.browser.get.return_value={'video_id':'saved-video','channel_id':'channel',
            'status':'submitted','created':time.time()-90,'submitted_at':time.time()-80,'updated':time.time()-70}
        proof={'id':'saved-video','privacy':'private','publish_at':'','private_verified_at':time.time()}
        verify.side_effect=[None,proof]
        self.publisher.browser.retry_unapplied_youtube.return_value={'status':'queued','created':time.time()-90,'updated':time.time()}
        result=advance_youtube(self.publisher,self.job)
        self.assertEqual(result['browser_schedule_id'],'studio')
        self.publisher.browser.retry_unapplied_youtube.assert_called_once_with('studio',proof)
        self.publisher.browser.enqueue_youtube.assert_not_called()
