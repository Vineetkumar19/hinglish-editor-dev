"""CPU-only state-machine tests; these are not model or platform acceptance."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from hinglish_publish.prepare_post import PreparePost, candidates, file_identity, buffer_status
from hinglish_publish.store import Store


class Runtime:
    def __init__(self, root):
        self.root = Path(root)
        self.calls = []
        self.fail = None

    def stage(self, stage, draft, progress):
        self.calls.append(stage)
        if stage == self.fail:
            raise ValueError('Check the source and retry this step.')
        if stage == 'speech':
            return {'words': [['Cricket', 0, 1]], 'transcript': 'Cricket analysis', 'model': 'fixture'}
        if stage == 'selection':
            return {'clips': [{'index': n + 1} for n in range(draft['count'])], 'model': 'fixture'}
        if stage.startswith('render:'):
            number = int(stage.split(':')[1])
            path = self.root / f'clip{number}.mp4'
            path.write_bytes(f'clip{number}'.encode())
            return {'video': file_identity(path), 'transcript': 'Cricket analysis', 'duration': 40, 'width': 720, 'height': 1280}
        if stage.startswith('copy:'):
            return {'metadata': {'title': 'Cricket analysis', 'description': 'Cricket analysis #Cricket', 'tags': ['Cricket'], 'instagram_caption': 'Cricket analysis #Cricket'}, 'model': 'fixture'}
        if stage == 'inspect':
            return {'duration': 180, 'width': 1920, 'height': 1080}
        raise AssertionError(stage)


class PreparePostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / 'Mumbai Indians.mp4'
        self.video.write_bytes(b'video')
        self.thumb = self.root / 'chosen.jpg'
        self.thumb.write_bytes(b'thumbnail')
        self.publisher = Mock(root=self.root)
        self.publisher.store = Store(self.root)
        self.publisher.accounts.return_value = {'youtube': {'id': 'yt-cricket', 'connected': True}, 'instagram': {'id': 'ig-cricket', 'connected': True, 'transport': 'browser'}}
        self.publisher.settings.return_value = {'visibility': 'private', 'daily_time': '19:00', 'enabled': True}
        self.publisher.thread = None
        self.publisher.prepared_thumbnail.return_value = str(self.thumb)
        self.runtime = Runtime(self.root)
        self.service = PreparePost(self.publisher, runtime=self.runtime)

    def draft(self, mode='shorts', count=5):
        return self.service.create({'profile': 'cricket', 'mode': mode, 'count': count, 'video': str(self.video), 'thumbnail': str(self.thumb) if mode == 'long' else '', 'request_id': 'first'})

    def test_folder_always_requires_exact_selection(self):
        result = candidates(self.root, 'Mumbai')
        self.assertEqual(result['candidates'][0]['path'], str(self.video.resolve()))
        with self.assertRaisesRegex(ValueError, 'exact'):
            self.service.create({'profile': 'cricket', 'mode': 'long', 'video': str(self.root), 'request_id': 'folder'})

    def test_resume_only_unfinished_stage_and_never_posts(self):
        draft = self.draft()
        self.runtime.fail = 'copy:instagram:2'
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('copy:youtube:5', result['stages'])
        before = list(self.runtime.calls)
        self.runtime.fail = None
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(self.runtime.calls[len(before):], ['copy:instagram:2', 'copy:instagram:3', 'copy:instagram:4', 'copy:instagram:5'])
        self.assertEqual(self.publisher.store.list(), [])
        self.publisher.authorize.assert_not_called()

    def test_long_has_only_youtube_and_exact_thumbnail(self):
        draft = self.draft('long')
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['platforms'], ['youtube'])
        self.assertEqual(result['thumbnail']['path'], str(self.thumb.resolve()))
        self.assertFalse(any('instagram' in key for key in result['stages']))

    def test_request_replay_profile_isolation_and_changed_source(self):
        draft = self.draft()
        self.assertEqual(draft['id'], self.draft()['id'])
        with self.assertRaises(ValueError):
            self.service.get(draft['id'], 'gaming')
        self.video.write_bytes(b'changed source')
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.runtime.calls, [])

    def test_paired_queue_uses_same_files_order_times_and_no_thumbnails(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        yt = self.service.queue(draft['id'], 'cricket', 'youtube')
        ig = self.service.queue(draft['id'], 'cricket', 'instagram')
        self.assertEqual([j['video'] for j in yt], [j['video'] for j in ig])
        self.assertEqual([j['due'] for j in yt], [j['due'] for j in ig])
        self.assertTrue(all(not j['thumbnail'] for j in yt + ig))
        self.assertTrue(all(j['transport'] == 'browser' for j in ig))
        self.assertEqual([j['id'] for j in yt], [j['id'] for j in self.service.queue(draft['id'], 'cricket', 'youtube')])
        self.assertTrue(all(j['status'] == 'draft' for j in yt + ig))

    def test_account_switch_blocks_without_queue(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        self.publisher.accounts.return_value['youtube']['id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'account'):
            self.service.queue(draft['id'], 'cricket', 'youtube')
        self.assertEqual(self.publisher.store.list(), [])

    def test_cancel_keeps_completed_steps(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        self.service.cancel(draft['id'], 'cricket')
        result = self.service.get(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'stopped')
        self.assertIn('speech', result['stages'])

    def test_cancel_during_work_stops_at_saved_boundary_and_resume_continues(self):
        draft = self.draft()
        def progress(message):
            if 'selection' in message:
                self.service.cancel(draft['id'], 'cricket')
        result = self.service.run(draft['id'], 'cricket', progress)
        self.assertEqual(result['status'], 'stopped')
        self.assertIn('selection', result['stages'])
        self.assertNotIn('render:1', result['stages'])
        self.service.resume(draft['id'], 'cricket')
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(self.runtime.calls.count('selection'), 1)

    def test_shortfall_is_saved_without_rendering_or_copy(self):
        draft = self.draft()
        original = self.runtime.stage
        self.runtime.stage = lambda stage, d, p: {'clips': [{'index': 1}], 'model': 'fixture'} if stage == 'selection' else original(stage, d, p)
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('5 were requested', result['message'])
        self.assertFalse(any(s.startswith(('copy:', 'render:')) for s in result['stages']))

    def test_youtube_can_queue_when_instagram_copy_failed(self):
        draft = self.draft()
        self.runtime.fail = 'copy:instagram:1'
        self.service.run(draft['id'], 'cricket')
        self.assertEqual(len(self.service.queue(draft['id'], 'cricket', 'youtube')), 5)
        with self.assertRaisesRegex(ValueError, 'copy'):
            self.service.queue(draft['id'], 'cricket', 'instagram')

    def test_thumbnail_change_blocks_post(self):
        draft = self.draft('long')
        self.service.run(draft['id'], 'cricket')
        self.thumb.write_bytes(b'changed thumbnail')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.service.post(draft['id'], 'cricket', 'youtube', {})
        self.publisher.authorize.assert_not_called()

    def test_copy_edit_persists_without_regeneration(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        self.service.edit(draft['id'], 'cricket', 'youtube', 1, {'title': 'Edited cricket title'})
        calls = list(self.runtime.calls)
        result = self.service.run(draft['id'], 'cricket')
        self.assertEqual(result['stages']['copy:youtube:1']['metadata']['title'], 'Edited cricket title')
        self.assertEqual(self.runtime.calls, calls)

    def test_post_reuses_receipts_and_does_not_authorize_again(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        jobs = self.service.queue(draft['id'], 'cricket', 'youtube')
        for j in jobs:
            self.publisher.store.change(j['id'], status='uploaded_private', remote={'id': 'test-receipt'})
        calls = list(self.runtime.calls)
        result = self.service.post(draft['id'], 'cricket', 'youtube', {})
        self.assertTrue(all(j['remote']['id'] == 'test-receipt' for j in result['jobs']))
        self.publisher.authorize.assert_not_called()
        self.assertEqual(self.runtime.calls, calls)

    def test_uncertain_upload_is_not_reauthorized(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        jobs = self.service.queue(draft['id'], 'cricket', 'youtube')
        self.publisher.store.change(jobs[0]['id'], status='needs_review', remote={'id': 'existing'})
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.service.post(draft['id'], 'cricket', 'youtube', {})
        self.publisher.authorize.assert_not_called()

    def test_schedule_has_one_day_per_clip_in_ist_window_and_is_durable(self):
        from datetime import datetime
        from hinglish_publish.store import IST
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        jobs = self.service.queue(draft['id'], 'cricket', 'youtube')
        times = [datetime.fromtimestamp(j['due'], IST) for j in jobs]
        self.assertEqual(len({t.date() for t in times}), 5)
        self.assertTrue(all(17 * 60 <= t.hour * 60 + t.minute <= 21 * 60 for t in times))
        restored = PreparePost(self.publisher, self.runtime)
        ig = restored.queue(draft['id'], 'cricket', 'instagram')
        self.assertEqual([j['due'] for j in jobs], [j['due'] for j in ig])

    def test_new_request_cannot_rebind_existing_idempotency_key(self):
        draft = self.draft()
        with self.assertRaisesRegex(ValueError, 'selection'):
            self.service.create({**draft['intent'], 'count': 6, 'request_id': 'first'})

    def test_long_queue_uses_chosen_thumbnail_and_private_visibility(self):
        draft = self.draft('long')
        self.service.run(draft['id'], 'cricket')
        jobs = self.service.queue(draft['id'], 'cricket', 'youtube')
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['thumbnail'], str(self.thumb))
        self.assertEqual(jobs[0]['visibility'], 'private')

    def test_model_subrequest_cache_reuses_only_completed_exact_request(self):
        from hinglish_publish.prepare_post_runtime import RecordedBrain
        brain = Mock(name='local')
        brain.name = 'fixture-local'
        brain.json.return_value = {'facts': ['Fixture fact']}
        brain.last_usage = {'cache_hit': False}
        recorder = RecordedBrain(brain, self.root, {'profile': 'cricket'})
        first = recorder.json('system', {'speech': 'one'}, {'type': 'object'})
        self.assertEqual(first, recorder.json('system', {'speech': 'one'}, {'type': 'object'}))
        self.assertEqual(brain.json.call_count, 1)
        recorder.json('system', {'speech': 'two'}, {'type': 'object'})
        self.assertEqual(brain.json.call_count, 2)

    def test_source_chunks_preserve_all_words_in_bounded_requests(self):
        from hinglish_publish.prepare_post import text_chunks
        text = ' '.join('word' + str(i) for i in range(3000))
        chunks = text_chunks(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 6000 for chunk in chunks))
        self.assertEqual(' '.join(chunks), text)

    def test_selection_request_never_starts_model_or_authorizes(self):
        from types import SimpleNamespace
        from hinglish_app.prepare_post_http import dispatch
        state = SimpleNamespace(root=self.root, publisher=self.publisher)
        result = dispatch(state, {'action': 'create', 'profile': 'cricket', 'mode': 'shorts', 'count': 5, 'video': str(self.video), 'request_id': 'http'})
        self.assertEqual(result['status'], 'saved')
        self.publisher.task.assert_not_called()
        self.publisher.authorize.assert_not_called()

    def test_conflicting_existing_post_is_not_silently_reused(self):
        draft = self.draft()
        self.service.run(draft['id'], 'cricket')
        jobs = self.service.queue(draft['id'], 'cricket', 'youtube')
        saved = self.service.get(draft['id'], 'cricket')
        saved['jobs_by_platform'] = {}
        self.service._save(saved)
        self.publisher.store.change(jobs[0]['id'], prepare_post_id='older', visibility='public')
        with self.assertRaisesRegex(ValueError, 'different copy, thumbnail or visibility'):
            self.service.post(draft['id'], 'cricket', 'youtube', {})
        self.publisher.authorize.assert_not_called()

    def test_gaming_highlights_has_three_independent_cut_checkpoints(self):
        self.runtime.stage = Mock(side_effect=lambda stage, d, p: ({'duration': 900, 'width': 1920, 'height': 1080} if stage == 'inspect' else
            {'transcript': 'Gaming commentary', 'words': [['Gaming', 0, 1]]} if stage == 'speech' else
            {'video': file_identity(self.video), 'transcript': 'Gaming commentary'} if stage == 'highlights' else
            {'metadata': {'title': 'Gaming highlights', 'description': 'Gaming highlights', 'instagram_caption': '', 'tags': []}, 'model': 'fixture'} if stage.startswith('copy:') else {}))
        draft = self.service.create({'profile': 'gaming', 'mode': 'highlights', 'video': str(self.video), 'thumbnail': str(self.thumb), 'minutes': 15, 'request_id': 'gaming'})
        result = self.service.run(draft['id'], 'gaming')
        self.assertEqual(result['status'], 'prepared')
        self.assertTrue({'highlight-signals', 'highlight-selection', 'highlights'}.issubset(result['stages']))
        self.assertEqual(result['platforms'], ['youtube'])

    def test_buffer_does_not_count_unapproved_or_uncertain_jobs(self):
        from datetime import datetime, timedelta
        from hinglish_publish.store import IST
        now = datetime(2026, 10, 29, 12, tzinfo=IST)
        jobs = [{'profile': 'cricket', 'platform': 'instagram', 'kind': 'short', 'due': (now + timedelta(days=n, hours=5)).timestamp(), 'status': 'ready', 'fingerprint': str(n)} for n in range(5)]
        self.assertEqual(buffer_status(jobs, 'cricket', now.timestamp())['days'], 5)
        jobs[0]['status'] = 'draft'
        jobs[1]['status'] = 'needs_review'
        self.assertEqual(buffer_status(jobs, 'cricket', now.timestamp())['shortfall'], 2)


if __name__ == '__main__':
    unittest.main()
