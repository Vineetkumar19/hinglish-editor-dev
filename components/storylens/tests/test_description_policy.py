"""Metadata/state checks only; no model calls, media work or platform publication."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from hinglish_publish.description_policy import apply, policy
from hinglish_publish.prepare_post import PreparePost, file_identity
from hinglish_publish.store import Store
from hinglish_niche.profiles import Profiles


class DescriptionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        assert Path(self.tmp.name).resolve().is_relative_to(Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        saved = json.loads((Path(__file__).resolve().parents[1] / 'config.workflow.local.json').read_text('utf-8'))
        (self.root / 'config.workflow.local.json').write_text(json.dumps({'youtube_description_policy': saved['youtube_description_policy']}), 'utf-8')
        self.meta = {'title': 'A real story', 'description': 'Source-grounded documentary.\n\n#Cricket #IPL #History', 'tags': ['Cricket'], 'instagram_caption': 'A short caption\n\n#Cricket #IPL #History'}

    def test_channel_links_are_idempotent_and_hashtags_stay_last(self):
        for profile in ('cricket', 'gaming'):
            result = apply(self.root, profile, self.meta)
            expected = policy(self.root, profile)['links']
            for link in expected:
                self.assertEqual(result['description'].count(link['url']), 1)
            self.assertEqual(result, apply(self.root, profile, result))
            self.assertTrue(result['description'].endswith('#Cricket #IPL #History'))
            self.assertEqual(result['instagram_caption'], self.meta['instagram_caption'])
            self.assertEqual(self.meta['description'], 'Source-grounded documentary.\n\n#Cricket #IPL #History')
            if profile == 'gaming':
                self.assertNotIn('Telegram', result['description'])
                self.assertNotIn('fantasy', result['description'])

    def test_instagram_and_general_remain_unchanged_no_music_bank(self):
        self.assertEqual(apply(self.root, 'cricket', self.meta, 'instagram'), self.meta)
        self.assertEqual(apply(self.root, 'general', self.meta), self.meta)
        for profile in ('cricket', 'gaming'):
            self.assertFalse(policy(self.root, profile)['blanket_music_credit_bank_enabled'])
            self.assertIn('youtube_description_policy', Profiles(self.root).context(profile))

    def test_links_fit_or_fail_without_silently_cutting_copy(self):
        original = {**self.meta, 'description': 'x' * 4990}
        with self.assertRaisesRegex(ValueError, '5,000'):
            apply(self.root, 'cricket', original)
        self.assertEqual(original['description'], 'x' * 4990)

    def test_old_preparation_review_edit_and_queue_use_same_youtube_policy(self):
        video = self.root / 'source.mp4'
        video.write_bytes(b'identity fixture, never decoded or uploaded')
        publisher = Mock(root=self.root)
        publisher.store = Store(self.root)
        publisher.accounts.return_value = {'youtube': {'id': 'cricket-account', 'connected': True}, 'instagram': {'id': 'instagram-account', 'connected': True, 'transport': 'browser'}}
        publisher.settings.return_value = {'visibility': 'private', 'daily_time': '19:00'}
        prep = PreparePost(publisher)
        draft = prep.create({'profile': 'cricket', 'mode': 'long', 'video': str(video), 'request_id': 'policy-check'})
        draft['stages'] = {'inspect': {'duration': 100, 'width': 1920, 'height': 1080}, 'copy:youtube:1': {'metadata': copy.deepcopy(self.meta)}}
        draft['status'] = 'prepared'
        prep._save(draft)
        reviewed = prep.list('cricket')[0]['stages']['copy:youtube:1']['metadata']
        self.assertIn('https://t.me/fantasylegends11', reviewed['description'])
        prep.edit(draft['id'], 'cricket', 'youtube', 1, {**self.meta, 'description': 'Owner edited story.\n\n#Cricket #IPL #History'})
        edited = prep.get(draft['id'], 'cricket')['stages']['copy:youtube:1']['metadata']
        self.assertIn('https://t.me/fantasylegends11', edited['description'])
        queued = prep.queue(draft['id'], 'cricket', 'youtube')[0]
        self.assertEqual(queued['metadata'], edited)
        publisher.authorize.assert_not_called()

    def test_publisher_authorization_enforces_youtube_only_without_starting_worker(self):
        from hinglish_publish.service import Publisher
        publisher = Publisher(self.root)
        publisher.accounts = Mock(return_value={'youtube': {'id': 'cricket-account', 'connected': True}, 'instagram': {'id': 'instagram-account', 'connected': True}})
        source = self.root / 'source.mp4'
        source.write_bytes(b'identity fixture only')
        items = [{'video': str(source), 'fingerprint': file_identity(source)['sha256'], 'profile': 'cricket',
                  'platform': platform, 'kind': 'short', 'metadata': self.meta, 'visibility': 'private',
                  'thumbnail': '', 'brain': 'fixture'} for platform in ('youtube', 'instagram')]
        ids = publisher.store.add_batch(items)
        publisher.authorize({'ids': ids, 'authorize': True, 'made_for_kids': False, 'synthetic_media': False})
        by_platform = {publisher.store.get(key)['platform']: publisher.store.get(key) for key in ids}
        self.assertIn('https://t.me/fantasylegends11', by_platform['youtube']['metadata']['description'])
        self.assertEqual(by_platform['instagram']['metadata'], self.meta)
        self.assertIsNone(publisher.thread)


if __name__ == '__main__':
    unittest.main()
