"""Explicit Long release and saved-source reuse; no live platform actions."""
import time
import unittest
from datetime import datetime
from unittest.mock import patch

from tests.test_prepare_post import PreparePostTests
from hinglish_publish.store import IST


class SimplePostingTests(unittest.TestCase):
    setUp = PreparePostTests.setUp

    def payload(self, **changes):
        return {'profile': 'cricket', 'mode': 'long', 'count': 1, 'minutes': 15,
                'video': str(self.video), 'thumbnail': str(self.thumb), 'visibility': 'private',
                'request_id': 'simple-long', 'authorize': True, 'release_action': 'schedule',
                'made_for_kids': False, 'synthetic_media': False, **changes}

    def authorize(self, request):
        for identity in request['ids']:
            self.publisher.store.change(identity, status='ready', authorized_at=time.time())

    def test_discovery_opt_in_is_saved_without_mutating_old_requests(self):
        plain=self.service.create(self.payload(authorize=False))
        self.assertFalse(plain['discovery_review'])
        self.assertEqual(self.service.create(self.payload(authorize=False))['id'],plain['id'])
        request=self.payload(authorize=False,request_id='seo',discovery_review=True,discovery_research=False)
        reviewed=self.service.create(request)
        self.assertTrue(reviewed['discovery_review'])
        self.assertFalse(reviewed['discovery_research'])
        with self.assertRaisesRegex(ValueError,'another selection'):
            self.service.create({**request,'discovery_research':True})
        self.assertEqual(self.publisher.store.list(),[])

    def test_thumbnail_can_be_changed_after_preparation_but_never_after_submission(self):
        draft=self.service.create(self.payload(authorize=False))
        self.service.run(draft['id'],'cricket')
        image=self.root/'new-cover.png';image.write_bytes(b'new cover')
        updated=self.service.edit_thumbnail(draft['id'],'cricket',str(image))
        self.assertEqual(updated['thumbnail']['path'],str(image.resolve()))
        self.assertEqual(updated['source'],draft['source'])
        self.assertEqual(self.publisher.store.list(),[])
        with self.assertRaisesRegex(ValueError,'PNG, JPEG or WebP'):
            self.service.edit_thumbnail(draft['id'],'cricket',str(self.video))
        updated['jobs_by_platform']['youtube']=['already-submitted'];self.service._save(updated)
        with self.assertRaisesRegex(ValueError,'already submitted'):
            self.service.edit_thumbnail(draft['id'],'cricket','')

    def test_review_refresh_changes_only_suggestions_and_refuses_submitted_batches(self):
        draft=self.service.create(self.payload(authorize=False))
        prepared=self.service.run(draft['id'],'cricket')
        baseline=prepared['stages']['copy:youtube:1']['metadata'].copy()
        with patch.object(self.runtime,'stage',return_value={
                'metadata':{'title':'Must never replace the prepared title'},
                'discovery':{'status':'ready','primary_query':'cricket analysis'}}) as stage:
            result=self.service.review_discovery(draft['id'],'cricket',1,False,lambda _:None)
            self.assertEqual(stage.call_args.args[0],'discovery:youtube:1')
            self.assertFalse(stage.call_args.args[1]['discovery_research'])
            self.assertEqual(result['stages']['copy:youtube:1']['metadata'],baseline)
            self.assertEqual(result['status'],'prepared')
            self.assertEqual(result['source'],prepared['source'])
            result['jobs_by_platform']['youtube']=['existing'];self.service._save(result)
            with self.assertRaisesRegex(ValueError,'already submitted'):
                self.service.review_discovery(draft['id'],'cricket',1)
            self.assertEqual(stage.call_count,1)
        self.assertEqual(self.publisher.store.list(),[])

    def test_review_worker_failure_preserves_prepared_copy(self):
        draft=self.service.create(self.payload(authorize=False));prepared=self.service.run(draft['id'],'cricket')
        with patch.object(self.runtime,'stage',side_effect=RuntimeError('worker stopped')):
            result=self.service.review_discovery(draft['id'],'cricket',1,False,lambda _:None)
        self.assertEqual(result['stages']['copy:youtube:1']['metadata'],prepared['stages']['copy:youtube:1']['metadata'])
        self.assertEqual(result['stages']['copy:youtube:1']['discovery']['status'],'needs_review')
        self.assertEqual(result['status'],'prepared')

    def test_missing_or_invalid_authorization_creates_nothing(self):
        for changes in ({'authorize': False}, {'mode': 'shorts'}, {'made_for_kids': 'no'}, {'release_action': 'private'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.service.authorize_source(self.payload(**changes))
        self.assertEqual(self.service.list('cricket'), [])
        self.assertEqual(self.publisher.store.list(), [])

    def test_schedule_prepares_and_authorizes_only_long_youtube_once(self):
        self.publisher.authorize.side_effect = self.authorize
        draft = self.service.authorize_source(self.payload())
        with patch.object(self.service, 'start_delivery'):
            result = self.service.run(draft['id'], 'cricket')
            replay = self.service.authorize_source(self.payload())
            self.service.run(replay['id'], 'cricket')
        jobs = self.publisher.store.list()
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['platform'], 'youtube')
        self.assertEqual(jobs[0]['kind'], 'long')
        self.assertEqual(jobs[0]['release_action'], 'schedule')
        self.assertEqual(jobs[0]['visibility'], 'private')
        self.assertIn(datetime.fromtimestamp(jobs[0]['due'], IST).hour, (18, 19, 20))
        self.assertEqual(self.runtime.calls.count('speech'), 1)
        self.publisher.authorize.assert_called_once()
        with self.assertRaises(ValueError):
            self.service.authorize_source(self.payload(release_action='post_now'))

    def test_gaming_post_now_uses_saved_gaming_binding(self):
        self.publisher.accounts.return_value['youtube']['id'] = 'yt-gaming'
        self.publisher.authorize.side_effect = self.authorize
        draft = self.service.authorize_source(self.payload(profile='gaming', release_action='post_now'))
        with patch.object(self.service, 'start_delivery'):
            self.service.run(draft['id'], 'gaming')
        job = self.publisher.store.list()[0]
        self.assertEqual((job['profile'], job['account_id'], job['release_action']), ('gaming', 'yt-gaming', 'post_now'))
        self.assertLess(abs(job['due'] - time.time()), 10)

    def test_failed_speech_keeps_source_and_requires_no_second_start_from_zero(self):
        self.publisher.authorize.side_effect = self.authorize
        draft = self.service.authorize_source(self.payload())
        self.runtime.fail = 'speech'
        self.assertEqual(self.service.run(draft['id'], 'cricket')['status'], 'failed')
        self.assertEqual(self.publisher.store.list(), [])
        self.runtime.fail = None
        with patch.object(self.service, 'start_delivery'):
            self.service.run(draft['id'], 'cricket')
        self.assertEqual(self.runtime.calls.count('inspect'), 1)
        self.assertEqual(len(self.publisher.store.list()), 1)

    def test_changed_destination_blocks_automatic_post(self):
        draft = self.service.authorize_source(self.payload())
        self.publisher.accounts.return_value['youtube']['id'] = 'different-channel'
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('posting', result['errors'])
        self.assertEqual(self.publisher.store.list(), [])
        self.publisher.authorize.assert_not_called()

    def test_reload_can_resume_saved_long_without_a_new_request_or_changed_source(self):
        draft = self.service.authorize_source(self.payload())
        self.runtime.fail = 'speech'
        self.service.run(draft['id'], 'cricket')
        restored = self.service.authorize_source(self.payload(id=draft['id'], request_id='different-browser-session'))
        self.assertEqual(restored['id'], draft['id'])
        self.assertIn('inspect', restored['stages'])
        self.assertEqual(len(self.service.list('cricket')), 1)
        self.video.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.service.authorize_source(self.payload(id=draft['id']))
        self.assertEqual(self.publisher.store.list(), [])

    def test_saved_long_reuses_exact_speech_without_reposting_long(self):
        parent = self.service.create(self.payload(request_id='parent'))
        self.service.run(parent['id'], 'cricket')
        before = list(self.runtime.calls)
        value = {'profile': 'cricket', 'mode': 'shorts', 'count': 5, 'minutes': 15,
                 'video': str(self.video), 'thumbnail': '', 'visibility': 'private',
                 'request_id': 'child', 'source_preparation': parent['id']}
        child = self.service.create(value)
        result = self.service.run(child['id'], 'cricket')
        self.assertEqual(child['reused_speech_from'], parent['id'])
        self.assertEqual(result['status'], 'prepared')
        self.assertNotIn('speech', self.runtime.calls[len(before):])
        self.assertIn('copy:youtube:5', result['stages'])
        self.assertIn('copy:instagram:5', result['stages'])
        self.assertEqual(self.publisher.store.list(), [])
        self.publisher.authorize.assert_not_called()
        with self.assertRaises(ValueError):
            self.service.create({**value, 'request_id': 'other-profile', 'profile': 'gaming'})
        other = self.root/'different.mp4'
        other.write_bytes(b'different video')
        with self.assertRaises(ValueError):
            self.service.create({**value, 'request_id': 'other-source', 'video': str(other)})

    def test_gaming_shorts_use_finished_highlights_and_never_stream_word_times(self):
        parent = self.service.create(self.payload(profile='gaming', mode='highlights', request_id='highlight-parent'))
        finished = self.root / 'finished-highlights.mp4'
        finished.write_bytes(b'finished ten minute highlight')
        from hinglish_publish.prepare_post import file_identity
        parent['stages'] = {'speech': {'words': [['stream', 7000, 7001]], 'transcript': 'stream'},
                            'highlights': {'video': file_identity(finished), 'duration': 600, 'width': 1280, 'height': 720}}
        self.service._save(parent)
        payload = dict(profile='gaming', mode='shorts', count=5, video=str(finished), thumbnail='',
                       source_preparation=parent['id'], request_id='highlight-child')
        child = self.service.create(payload)
        self.assertEqual(child['source'], file_identity(finished))
        self.assertEqual(child['source_highlights_from'], parent['id'])
        self.assertEqual(child['stages']['inspect']['duration'], 600)
        self.assertNotIn('speech', child['stages'])
        result = self.service.run(child['id'], 'gaming')
        self.assertEqual(result['status'], 'prepared')
        self.assertIn('copy:youtube:5', result['stages'])
        self.assertIn('copy:instagram:5', result['stages'])
        self.assertEqual(self.publisher.store.list(), [])
        with self.assertRaises(ValueError):
            self.service.create({**payload, 'request_id':'stream-instead', 'video':str(self.video)})
        with self.assertRaises(ValueError):
            self.service.create({**payload, 'request_id':'wrong-profile', 'profile':'cricket'})

    def test_immediate_cancel_stops_even_without_another_worker_message(self):
        parent = self.service.create(self.payload(request_id='cancel-immediate'))
        original = self.runtime.stage
        def stage(name, draft, progress):
            if name == 'speech':
                self.service.cancel(draft['id'], 'cricket', immediate=True)
                progress.check_cancel()
            return original(name, draft, progress)
        self.runtime.stage = stage
        result = self.service.run(parent['id'], 'cricket')
        self.assertEqual(result['status'], 'cancelled')
        self.assertIn('inspect', result['stages'])
        self.assertNotIn('speech', result['stages'])
        self.publisher.authorize.assert_not_called()
        self.assertEqual(self.publisher.store.list(), [])

    def test_cancelled_queued_request_cannot_begin_work_or_post(self):
        draft = self.service.create(self.payload(request_id='cancel-queued'))
        self.service.cancel(draft['id'], 'cricket', immediate=True)
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(self.runtime.calls, [])
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.service.post(draft['id'], 'cricket', 'youtube', {}, 'post_now')
        self.assertEqual(self.publisher.store.list(), [])

