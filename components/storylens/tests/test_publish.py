import json
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from hinglish_publish import metadata, secrets
from hinglish_publish.providers import PreflightError
from hinglish_publish.service import Publisher
from hinglish_publish.store import IST, Store, fingerprint, next_slot
from hinglish_publish.worker_lock import acquire

META = {'title': 'Mumbai Indians Journey', 'description': 'The journey discussed in this video.',
        'instagram_caption': 'Mumbai Indians journey. #MumbaiIndians #Cricket #IPL', 'tags': ['Mumbai Indians']}


class Success:
    calls = []
    def __init__(self, root, config):
        pass

    def publish(self, job, checkpoint):
        self.calls.append(job['id'])
        remote = {'id': 'remote123', 'url': 'https://www.youtube.com/watch?v=remote123'}
        checkpoint(remote)
        return remote, 'published'


class Ambiguous(Success):
    def publish(self, job, checkpoint):
        self.calls.append(job['id'])
        checkpoint({'id': 'accepted-before-timeout'})
        raise TimeoutError('connection lost after upload')


class Blocked(Success):
    def publish(self, job, checkpoint):
        raise PreflightError('Connect account first')


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / 'Mumbai Indians Journey.mp4'
        self.video.write_bytes(b'a finished export')
        Success.calls = []
        self.publisher = Publisher(self.root, {'youtube': Success, 'instagram': Success})

    def tearDown(self):
        self.publisher.stop.set()
        self.temp.cleanup()

    def item(self, platform='youtube', kind='long', video=None):
        video = video or self.video
        return {'video': str(video), 'fingerprint': fingerprint(video), 'platform': platform,
                'kind': kind, 'metadata': dict(META), 'thumbnail': '', 'visibility': 'public'}

    def ready(self, item=None):
        job_id = self.publisher.store.add_batch([item or self.item()])[0]
        self.publisher.store.change(job_id, status='ready', account_id='channel', made_for_kids=False,
                                    synthetic_media=False)
        return job_id

    def test_same_short_gets_same_ist_date_on_both_platforms_and_next_day_is_reserved(self):
        now = datetime(2026, 10, 4, 12, tzinfo=IST).timestamp()
        second = self.root / 'second.mp4'
        second.write_bytes(b'different clip')
        ids = self.publisher.store.add_batch([self.item('youtube', 'short'), self.item('instagram', 'short'),
                                              self.item('youtube', 'short', second),
                                              self.item('instagram', 'short', second)], now=now)
        jobs = [self.publisher.store.get(j) for j in ids]
        self.assertEqual(jobs[0]['due'], jobs[1]['due'])
        self.assertEqual(jobs[2]['due'], jobs[3]['due'])
        self.assertEqual(jobs[2]['due'] - jobs[0]['due'], 86400)
        self.assertEqual(datetime.fromtimestamp(jobs[0]['due'], IST).strftime('%H:%M'), '19:00')

    def test_batches_reserve_one_slot_per_day_globally(self):
        now = datetime(2026, 10, 4, 20, tzinfo=IST).timestamp()
        first = self.publisher.store.add_batch([self.item('youtube', 'short')], now=now)[0]
        other = self.root / 'other.mp4'
        other.write_bytes(b'other')
        second = self.publisher.store.add_batch([self.item('youtube', 'short', other)], now=now)[0]
        self.assertEqual(self.publisher.store.get(second)['due'] - self.publisher.store.get(first)['due'], 86400)

    def test_duplicate_content_does_not_create_a_second_upload(self):
        one = self.publisher.store.add_batch([self.item()])
        two = self.publisher.store.add_batch([self.item()])
        self.assertEqual(one, two)
        self.assertEqual(len(self.publisher.store.list()), 1)

    def test_pause_and_draft_never_upload(self):
        self.publisher.store.add_batch([self.item()])
        self.assertIsNone(self.publisher.tick())
        self.publisher.settings({'enabled': True})
        self.assertIsNone(self.publisher.tick())
        self.assertEqual(Success.calls, [])

    def test_verified_receipt_and_no_second_upload_after_restart(self):
        self.ready()
        self.publisher.settings({'enabled': True})
        result = self.publisher.tick()
        self.assertEqual(result['status'], 'published')
        again = Publisher(self.root, {'youtube': Success, 'instagram': Success})
        self.assertIsNone(again.tick())
        self.assertEqual(len(Success.calls), 1)
        self.assertIn('Published and verified', self.publisher.store.events()[0]['message'])

    def test_uncertain_upload_retains_remote_id_and_does_not_retry(self):
        self.publisher.providers['youtube'] = Ambiguous
        job_id = self.ready()
        self.publisher.settings({'enabled': True})
        result = self.publisher.tick()
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['remote']['id'], 'accepted-before-timeout')
        self.assertIsNone(self.publisher.tick())
        self.assertEqual(len(Success.calls), 1)
        self.assertEqual(self.publisher.store.get(job_id)['status'], 'needs_review')

    def test_missing_setup_is_blocked_without_claiming_success(self):
        self.publisher.providers['youtube'] = Blocked
        self.ready()
        self.publisher.settings({'enabled': True})
        self.assertEqual(self.publisher.tick()['status'], 'blocked')
        self.assertEqual(Success.calls, [])

    def test_changed_source_cannot_publish_previously_approved_content(self):
        self.ready()
        self.video.write_bytes(b'a modified export')
        self.publisher.settings({'enabled': True})
        self.assertEqual(self.publisher.tick()['status'], 'blocked')
        self.assertEqual(Success.calls, [])

    def test_atomic_claim_across_connections(self):
        self.ready()
        stores = [Store(self.root), Store(self.root)]
        barrier = threading.Barrier(2)
        results = []
        def claim(store):
            barrier.wait()
            results.append(store.claim(time.time()))
        threads = [threading.Thread(target=claim, args=(s,)) for s in stores]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sum(x is not None for x in results), 1)

    def test_interrupted_upload_requires_review(self):
        job_id = self.ready()
        self.publisher.store.claim(time.time())
        self.publisher.store.recover()
        self.assertEqual(self.publisher.store.get(job_id)['status'], 'needs_review')

    def test_edit_revokes_ready_and_cannot_race_upload_claim(self):
        job_id = self.ready()
        self.publisher.edit({'id': job_id, 'metadata': {**META, 'title': 'Corrected title'}})
        self.assertEqual(self.publisher.store.get(job_id)['status'], 'draft')
        self.publisher.store.change(job_id, status='ready')
        self.publisher.store.claim(time.time())
        with self.assertRaises(ValueError):
            self.publisher.edit({'id': job_id, 'metadata': META})

    def test_authorization_requires_accounts_and_declarations(self):
        job_id = self.publisher.store.add_batch([self.item()])[0]
        with self.assertRaises(ValueError):
            self.publisher.authorize({'ids': [job_id], 'authorize': True})
        with patch.object(self.publisher, 'accounts', return_value={'youtube': {'connected': True, 'id': 'channel'}}):
            self.publisher.authorize({'ids': [job_id], 'authorize': True,
                                      'made_for_kids': False, 'synthetic_media': True})
        self.assertEqual(self.publisher.store.get(job_id)['account_id'], 'channel')

    def test_scan_exact_thumbnail_match_and_command_resolution(self):
        self.publisher.init_folders()
        folders = self.publisher.folders()
        video = folders['long-youtube'] / self.video.name
        video.write_bytes(self.video.read_bytes())
        os.utime(video, (time.time() - 20, time.time() - 20))
        wrong = folders['thumbnails-youtube'] / 'Mumbai Indians Journey extra.png'
        wrong.write_bytes(b'wrong')
        self.assertFalse(self.publisher.scan()[0]['thumbnail'])
        correct = folders['thumbnails-youtube'] / 'Mumbai Indians Journey.png'
        correct.write_bytes(b'correct')
        found = self.publisher.selected('Upload Mumbai Indians Journey on YouTube')
        self.assertEqual(found['thumbnail'], str(correct.resolve()))
        with self.assertRaises(ValueError):
            self.publisher.selected('Mumbai')

    def test_future_instagram_does_not_publish_early(self):
        job_id = self.ready(self.item('instagram', 'short'))
        self.publisher.settings({'enabled': True})
        self.assertGreater(self.publisher.store.get(job_id)['due'], time.time())
        self.assertIsNone(self.publisher.tick())

    def test_one_worker_lock_per_project(self):
        lock = acquire(self.root)
        try:
            with self.assertRaises(RuntimeError):
                acquire(self.root)
        finally:
            lock.close()

    def test_invalid_times_and_metadata_are_rejected(self):
        with self.assertRaises(ValueError):
            self.publisher.settings({'daily_time': '25:00'})
        with self.assertRaises(ValueError):
            metadata.validate({**META, 'title': 'x' * 101})
        with self.assertRaises(ValueError):
            metadata.validate({**META, 'description': ''})
        self.assertEqual(metadata.validate({**META,'instagram_caption':''})['instagram_caption'],'')

    def test_creator_sidecar_reuses_metadata_without_loading_a_model(self):
        self.video.with_suffix('.publish.json').write_text(json.dumps({'metadata_language': 'en', 'metadata': META}))
        data, origin = metadata.generate(self.root, self.video)
        self.assertEqual(data, META)
        self.assertEqual(origin, 'Creator sidecar')

    def test_chrome_caption_uses_local_model_without_youtube_description_generation(self):
        from unittest.mock import Mock
        brain = Mock(name='local writer')
        brain.name = 'Ollama local fixture'
        brain.json.return_value = {'instagram_caption': META['instagram_caption']}
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            data, origin = metadata.generate_instagram(self.root, self.video,
                transcript='A retrospective on the Mumbai Indians IPL journey.', progress=lambda _: None)
        self.assertEqual(data, {'instagram_caption': META['instagram_caption']})
        self.assertEqual(origin, brain.name)
        self.assertEqual(brain.json.call_count, 1)
        schema = brain.json.call_args.args[2]
        self.assertEqual(schema['required'], ['instagram_caption'])
        self.assertFalse(brain.json.call_args.kwargs['think'])
        brain.close.assert_called_once()

    def test_chrome_caption_with_missing_hashtags_cannot_be_queued(self):
        from unittest.mock import Mock
        brain = Mock()
        brain.json.return_value = {'instagram_caption': 'Mumbai Indians IPL journey.'}
        with patch('hinglish_visuals.brain.open_brain', return_value=brain), self.assertRaises(ValueError):
            metadata.generate_instagram(self.root, self.video, transcript='Mumbai Indians journey.', progress=lambda _: None)
        brain.close.assert_called_once()

    def test_chrome_caption_revises_invalid_json_and_unrequested_numerical_claims(self):
        from unittest.mock import Mock
        brain = Mock()
        brain.name = 'local writer'
        brain.json.side_effect = [ValueError('Malformed JSON'),
            {'instagram_caption': 'The most successful team won five titles. #MumbaiIndians #IPL #Cricket'},
            {'instagram_caption': META['instagram_caption']}]
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            data, _ = metadata.generate_instagram(self.root, self.video,
                transcript='Mumbai Indians IPL journey.', progress=lambda _: None)
        self.assertEqual(data['instagram_caption'], META['instagram_caption'])
        self.assertEqual(brain.json.call_count, 3)
        self.assertIn('Malformed JSON', brain.json.call_args_list[1].args[1]['correction_required'])
        self.assertIn('numerical', brain.json.call_args_list[2].args[1]['correction_required'])

    def test_supported_qualifier_round_name_is_not_an_unrequested_record(self):
        from unittest.mock import Mock
        brain = Mock()
        brain.name = 'local writer'
        brain.json.return_value = {'instagram_caption': 'Mumbai Indians exited in Qualifier 2. #MumbaiIndians #IPL #Cricket'}
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            data, _ = metadata.generate_instagram(self.root, self.video,
                transcript='Their journey ends in Qualifier 2.', progress=lambda _: None)
        self.assertIn('Qualifier 2', data['instagram_caption'])
        brain.json.return_value = {'instagram_caption': 'Mumbai Indians exited in Qualifier 1. #MumbaiIndians #IPL #Cricket'}
        with patch('hinglish_visuals.brain.open_brain', return_value=brain), self.assertRaises(ValueError):
            metadata.generate_instagram(self.root, self.video,
                transcript='Their journey ends in Qualifier 2.', progress=lambda _: None)

    def test_instagram_accepts_spoken_hindi_year_and_score_as_digits(self):
        from unittest.mock import Mock
        brain=Mock();brain.name='local fixture'
        caption='Mumbai Indians won in 2013, with a 125-run innings. #MumbaiIndians #IPL #Cricket'
        brain.json.return_value={'instagram_caption':caption}
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            result,_=metadata.generate_instagram(self.root,self.video,
                transcript='do hazaar terah mein Mumbai Indians jeeti. usne ek sau pachis runs banaye.',progress=lambda _:None)
        self.assertEqual(result['instagram_caption'],caption)

    def test_instagram_recovers_from_repeated_ambiguous_score_by_model_summary(self):
        from unittest.mock import Mock
        brain=Mock();brain.name='local fixture'
        invalid={'instagram_caption':'Saha took Punjab to 199. #PunjabKings #IPL #Cricket'}
        valid={'instagram_caption':"Wriddhiman Saha stepped up for Punjab in the final. His batting helped the team recover after early wickets. #WriddhimanSaha #PunjabKings #IPL"}
        brain.json.side_effect=[invalid,invalid,invalid,valid]
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            result,_=metadata.generate_instagram(self.root,self.video,
                transcript='Wriddhiman Saha final mein team ko 1 99 tak le gaye.',progress=lambda _:None)
        self.assertEqual(result,valid)
        self.assertEqual(brain.json.call_count,4)
        self.assertIn('199',brain.json.call_args_list[1].args[1]['correction_required'])
        self.assertEqual(brain.json.call_args_list[1].args[1]['rejected_caption'],invalid['instagram_caption'])
        self.assertIn('Recovery writing contract',brain.json.call_args_list[3].args[0])
        reports=list((self.root/'cache/publisher/instagram-copy-review').glob('*.json'))
        self.assertEqual(json.loads(reports[0].read_text('utf-8'))['events'][-1]['stage'],'accepted')

    def test_instagram_recovery_discards_rejected_claims_and_keeps_source_topic(self):
        from unittest.mock import Mock
        brain=Mock();brain.name='local fixture'
        invalid={'instagram_caption':'Rohit Sharma led Mumbai Indians in 2015. #MumbaiIndians #RohitSharma #IPL'}
        ordinal={'instagram_caption':'Rohit Sharma led Mumbai Indians in his first season. #MumbaiIndians #RohitSharma #IPL'}
        valid={'instagram_caption':'Rohit Sharma and Mumbai Indians are the focus of this IPL retrospective. The clip looks at leadership and the team’s journey. #MumbaiIndians #RohitSharma #IPL'}
        brain.json.side_effect=[invalid,invalid,invalid,ordinal,valid]
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            result,_=metadata.generate_instagram(self.root,self.video,
                transcript='Rohit Sharma Mumbai Indians 2011 se. 10 saal 16 saal.',progress=lambda _:None)
        self.assertEqual(result,valid)
        recovery=brain.json.call_args_list[3].args[1]
        self.assertNotIn('rejected_caption',recovery)
        self.assertNotIn('2015',json.dumps(recovery))
        self.assertNotIn('2011',recovery['source_evidence'])
        self.assertIn('Rohit Sharma',recovery['source_evidence'])
        self.assertNotIn('correction_required',brain.json.call_args.args[1])

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_tokens_are_encrypted_and_dashboard_does_not_expose_them(self):
        secrets.save(self.root, 'instagram', {'token': 'sensitive-token', 'account_id': '123', 'name': 'creator'})
        file = self.root / 'cache' / 'publisher' / 'instagram.dpapi'
        self.assertNotIn(b'sensitive-token', file.read_bytes())
        self.assertEqual(secrets.load(self.root, 'instagram')['token'], 'sensitive-token')
        self.assertNotIn('sensitive-token', json.dumps(self.publisher.snapshot()))


if __name__ == '__main__':
    unittest.main()
