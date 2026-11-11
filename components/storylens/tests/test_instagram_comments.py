
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hinglish_publish.instagram_comments import InstagramComments
from hinglish_publish.local_browser import LocalBrowser


class InstagramCommentsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.browser = LocalBrowser(self.root)
        self.browser.bind('cricket', 'fantasy_legends91')
        self.adapter = InstagramComments(self.browser)

    def claim_comment_read(self):
        self.browser.claim('0.4.40', ['instagram_comments_read'])
        job_id = self.browser.enqueue_comment_read('cricket', 'fantasy_legends91')
        self.assertIsNone(self.browser.claim('0.4.38', ['instagram_comments_read'])['job'])
        job = self.browser.claim('0.4.39', ['instagram_comments_read'])['job']
        self.assertEqual(job_id, job['id'])
        return job_id, job['lease']

    def row(self, **fields):
        return dict({
            'comment_id': '1123', 'author_id': 'viewer',
            'source_id': 'EXACT', 'source_url': 'https://www.instagram.com/fantasy_legends91/reel/EXACT/',
            'published_at': datetime.now(timezone.utc).isoformat(), 'text': 'Where is this from?',
            'source_title': 'The exact post', 'source_description': 'The exact post',
        }, **fields)

    def test_read_is_ephemeral_and_cannot_submit(self):
        job_id, lease = self.claim_comment_read()
        with self.assertRaisesRegex(ValueError, 'cannot submit'):
            self.browser.phase(job_id, lease, 'sharing')
        with self.assertRaisesRegex(ValueError, 'cannot submit'):
            self.browser.finish(job_id, lease, {'status': 'published'})
        result = self.browser.finish(job_id, lease, {
            'status': 'complete', 'account': 'fantasy_legends91', 'rows': [self.row()],
        })
        self.assertEqual(result['comments'][0]['comment_id'], '1123')
        persisted = json.loads(self.browser.path.read_text(encoding='utf-8'))
        self.assertFalse(any(job['id'] == job_id for job in persisted['jobs']))
        self.assertFalse(self.adapter.check('cricket', 'fantasy_legends91')['write_ready'])

    def test_foreign_reel_and_duplicate_ids_are_rejected(self):
        job_id, lease = self.claim_comment_read()
        foreign = self.row(source_url='https://www.instagram.com/vineet_editz19/reel/EXACT/')
        for rows in ([foreign], [self.row(), self.row()]):
            with self.assertRaises(ValueError):
                self.browser.finish(job_id, lease, {
                    'status': 'complete', 'account': 'fantasy_legends91', 'rows': rows,
                })

    def test_empty_result_needs_exact_owned_post_evidence(self):
        job_id, lease = self.claim_comment_read()
        result = {'status': 'complete', 'account': 'fantasy_legends91', 'rows': []}
        with self.assertRaises(ValueError):
            self.browser.finish(job_id, lease, result)
        with self.assertRaises(ValueError):
            self.browser.finish(job_id, lease, {**result,
                'empty_source': 'https://www.instagram.com/vineet_editz19/reel/EXACT/'})
        result['empty_source'] = 'https://www.instagram.com/fantasy_legends91/reel/EXACT/'
        self.assertEqual([], self.browser.finish(job_id, lease, result)['comments'])

    def test_reply_requires_a_single_authorized_click_and_exact_readback(self):
        supports = ['instagram_comments_read', 'instagram_comments_reply', 'instagram_comments_window']
        self.browser.claim('0.4.43', supports)
        permissions = []
        row = self.row()
        jid = self.browser.enqueue_comment_action('cricket', 'fantasy_legends91', 'instagram_comments_reply',
            source_url=row['source_url'], comment_id=row['comment_id'], author=row['author_id'],
            comment_text=row['text'], reply_text='Thanks for watching!', authorize=lambda: permissions.append(True))
        job = self.browser.claim('0.4.43', supports)['job']
        receipt = {'status': 'complete', 'account': 'fantasy_legends91', 'parent_id': row['comment_id'],
                   'source_url': row['source_url'], 'text': 'Thanks for watching!', 'reply_id': '991'}
        with self.assertRaisesRegex(ValueError, 'exact Instagram reply'):
            self.browser.finish(jid, job['lease'], receipt)
        self.assertFalse(self.browser.phase(jid, job['lease'], 'sharing')['stop'])
        self.assertTrue(self.browser.phase(jid, job['lease'], 'sharing')['stop'])
        self.assertEqual([True], permissions)
        with self.assertRaisesRegex(ValueError, 'exact Instagram reply'):
            self.browser.finish(jid, job['lease'], {**receipt, 'parent_id': '777'})
        self.assertEqual('991', self.browser.finish(jid, job['lease'], receipt)['reply_id'])

    def test_expired_owned_post_is_cached_and_skipped_after_restart(self):
        supports = ['instagram_comments_read', 'instagram_comments_reply', 'instagram_comments_window']
        self.browser.claim('0.4.43', supports)
        row = self.row()
        cutoff = datetime.now(timezone.utc) - timedelta(days=5)
        jid = self.browser.enqueue_comment_action('cricket', 'fantasy_legends91', 'instagram_comments_read',
            source_url=row['source_url'], cutoff=cutoff.isoformat())
        self.assertIsNone(self.browser.claim('0.4.41', supports)['job'])
        job = self.browser.claim('0.4.43', supports)['job']
        self.assertEqual(cutoff.isoformat(), job['cutoff'])
        receipt = dict(status='complete', account='fantasy_legends91', source_url=row['source_url'],
            source_published_at=(cutoff - timedelta(seconds=1)).isoformat(), expired_source=True)
        with self.assertRaisesRegex(ValueError, 'expired Instagram post'):
            self.browser.finish(jid, job['lease'], {**receipt, 'rows': [row]})
        self.assertEqual([], self.browser.finish(jid, job['lease'], {**receipt, 'rows': []})['comments'])
        restarted = LocalBrowser(self.root)
        self.assertEqual({'EXACT'}, restarted.expired_comment_posts('fantasy_legends91', cutoff))
        self.assertEqual(set(), restarted.expired_comment_posts('vineet_editz19', cutoff))

    def test_manual_handoff_rejects_untrusted_hosts_and_foreign_accounts(self):
        self.assertEqual(self.adapter.manual_handoff('cricket', 'fantasy_legends91',
            'https://instagram.com/reel/EXACT/?tracking=ignored'),
            'https://www.instagram.com/reel/EXACT/')
        for source in (
            'https://www.instagram.com.evil.test/reel/EXACT/',
            'https://www.instagram.com/vineet_editz19/reel/EXACT/',
        ):
            with self.assertRaises(ValueError):
                self.adapter.manual_handoff('cricket', 'fantasy_legends91', source)

