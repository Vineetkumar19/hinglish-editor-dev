"""Contract tests for durable comment state and safe reply decisions."""

from datetime import datetime, timedelta, timezone
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hinglish_app.reference_reel_research import ChatGPTUnavailable, _codex_failure
from hinglish_app.social_comments import ACCOUNTS, LOCAL_REPLY_MODEL, MODEL, ReplyDrafter, SocialComments
from hinglish_publish.comment_window import recent_publication


YT = ('youtube', 'cricket')
IG = ('instagram', 'gaming')


class Connector:
    write_ready = True
    eligible = True
    lose_confirmation = False

    def __init__(self):
        self.rows = []
        self.sent = []

    def check(self, profile, account_id):
        return {'read_ready': True, 'write_ready': self.write_ready,
                'blocker': '' if self.write_ready else 'Missing reply permission.'}

    def scan(self, profile, account_id, since):
        return self.rows

    def preflight(self, profile, account_id, row):
        return self.eligible

    def send(self, profile, account_id, row, text, *, authorize):
        authorize()
        self.sent.append((profile, account_id, row['source_id'], row['comment_id'], text))
        if self.lose_confirmation:
            raise TimeoutError('response lost')
        return 'verified-reply-id'


def sample(comment_id='comment-1', **extra):
    row = {'platform': 'youtube', 'profile': 'cricket', 'comment_id': comment_id, 'source_id': 'actual-video', 'author_id': 'fan',
           'text': 'That chase was something else.',
           'published_at': (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(),
           'source_published_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
           'source_title': 'Mumbai Indians 2020', 'source_description': 'Season retrospective'}
    return {**row, **extra}


def gpt(folder, row, recent):
    return {'decision': 'reply', 'reply': 'That chase still gets my heart racing.', 'reason': 'On topic'}


class SocialCommentsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = Connector()
        self.service = SocialComments(self.temp.name, youtube=self.adapter, drafter=gpt)

    def row(self, comment_id='comment-1'):
        return next(item for item in self.service.status()['comments'] if item['comment_id'] == comment_id)

    def test_cloud_unavailable_falls_back_and_sends_through_existing_connector(self):
        self.adapter.rows = [sample()]
        self.service.drafter = ReplyDrafter(Path(self.temp.name))
        self.service.settings(*YT, 'auto')
        with patch('hinglish_app.reference_reel_research.request_image_json',
                   side_effect=ChatGPTUnavailable('ChatGPT access or usage limit reached.')) as cloud:
            with patch('hinglish_app.social_comments._local_reply',
                       return_value=gpt(None, None, None)) as local:
                self.assertEqual([], self.service.run(*YT)['run_errors'])
        cloud.assert_called_once()
        local.assert_called_once()
        self.assertEqual('sent', self.row()['state'])
        self.assertEqual(LOCAL_REPLY_MODEL, self.row()['draft_model'])
        self.assertIn('usage limit', self.row()['draft_fallback_reason'])
        self.assertEqual(1, len(self.adapter.sent))

    def test_cloud_review_and_invalid_output_do_not_trigger_fallback(self):
        drafter = ReplyDrafter(Path(self.temp.name))
        with patch('hinglish_app.social_comments._local_reply') as local:
            with patch('hinglish_app.reference_reel_research.request_image_json', side_effect=[
                {'decision': 'review', 'reply': 'I hear you.', 'reason': 'Sensitive'},
                ValueError('No valid model output.'),
            ]):
                self.assertEqual(MODEL, drafter(self.service.folder, sample(), [])['model'])
                with self.assertRaisesRegex(ValueError, 'No valid model output'):
                    drafter(self.service.folder, sample(), [])
        local.assert_not_called()

    def test_review_without_suggested_text_never_sends(self):
        self.adapter.rows = [sample()]
        self.service.drafter = lambda *args: {
            'model': LOCAL_REPLY_MODEL, 'decision': 'review', 'reply': '', 'reason': 'Takedown request',
        }
        self.service.settings(*YT, 'auto')
        self.assertEqual([], self.service.run(*YT)['run_errors'])
        self.assertEqual('review', self.row()['state'])
        self.assertEqual(LOCAL_REPLY_MODEL, self.row()['draft_model'])
        self.assertEqual([], self.adapter.sent)

    def test_cloud_is_retried_after_an_outage(self):
        drafter = ReplyDrafter(Path(self.temp.name))
        decision = gpt(None, None, None)
        with patch('hinglish_app.reference_reel_research.request_image_json',
                   side_effect=[ChatGPTUnavailable('Unavailable.'), decision]) as cloud:
            with patch('hinglish_app.social_comments._local_reply', return_value=decision):
                for _ in range(2):
                    self.assertEqual(LOCAL_REPLY_MODEL, drafter(self.service.folder, sample(), [])['model'])
                cloud.assert_called_once()
                with patch('hinglish_app.social_comments.monotonic',
                           return_value=drafter.retry_cloud_at):
                    self.assertEqual(MODEL, drafter(self.service.folder, sample(), [])['model'])
        self.assertEqual(2, cloud.call_count)

    def test_cloud_failure_messages_do_not_expose_raw_log_or_fallback_on_moderation(self):
        log = Path(self.temp.name) / 'codex.log'
        log.write_text('ERROR: Usage limit reached. secret=fixture', 'utf-8')
        self.assertEqual('ChatGPT access or usage limit reached.', _codex_failure(log))
        log.write_text('ERROR: HTTP 403, content policy', 'utf-8')
        self.assertIsNone(_codex_failure(log))

    def test_initial_modes_and_skip_own_and_historical(self):
        self.assertTrue(all(account['mode'] == 'paused' for account in self.service.status()['accounts']))
        self.adapter.rows = [sample(), sample('own', author_id=ACCOUNTS[YT]),
                             sample('old', published_at='2020-01-01T00:00:00Z'),
                             sample('answered', already_replied=True)]
        self.service.refresh(*YT)
        self.assertEqual({'comment-1', 'answered'}, {item['comment_id'] for item in self.service.status()['comments']})
        self.assertEqual('already_replied', self.service.draft(*YT, 'answered')['state'])
        self.assertFalse(self.adapter.sent)

    def test_review_requires_explicit_send_and_exact_receipt(self):
        self.adapter.rows = [sample()]
        self.service.settings(*YT, 'review')
        self.service.run(*YT)
        self.assertEqual(MODEL, self.row()['draft_model'])
        self.assertFalse(self.adapter.sent)
        result = self.service.send(*YT, 'comment-1')
        self.assertEqual('sent', result['state'])
        self.assertEqual('verified-reply-id', result['reply_id'])
        self.assertEqual(('cricket', ACCOUNTS[YT], 'actual-video', 'comment-1'), self.adapter.sent[0][:4])
        with self.assertRaisesRegex(ValueError, 'matching comment'):
            self.service.send('youtube', 'gaming', 'comment-1')

    def test_write_block_and_no_instagram_connector(self):
        self.adapter.write_ready = False
        self.assertTrue(self.service.check(*YT)['read_ready'])
        self.assertFalse(self.service.check(*IG)['write_ready'])
        with self.assertRaisesRegex(ValueError, 'Missing reply permission'):
            self.service.settings(*YT, 'auto')
        self.service.settings(*YT, 'review')
        self.adapter.rows = [sample()]
        self.service.run(*YT)
        with self.assertRaisesRegex(ValueError, 'Missing reply permission'):
            self.service.send(*YT, 'comment-1')

    def test_uncertain_is_never_retried_after_restart(self):
        self.adapter.rows = [sample()]
        self.adapter.lose_confirmation = True
        self.service.settings(*YT, 'auto')
        self.service.run(*YT)
        self.assertEqual('uncertain', self.row()['state'])
        restarted = SocialComments(self.temp.name, youtube=self.adapter, drafter=gpt)
        restarted.run(*YT)
        self.assertEqual('uncertain', restarted.send(*YT, 'comment-1')['state'])
        self.assertEqual(1, len(self.adapter.sent))

    def test_edited_comment_invalidates_draft(self):
        self.adapter.rows = [sample()]
        self.service.settings(*YT, 'review')
        self.service.run(*YT)
        self.adapter.rows = [sample(text='Completely different question')]
        self.service.refresh(*YT)
        self.assertEqual('changed', self.service.send(*YT, 'comment-1')['state'])
        self.assertFalse(self.adapter.sent)

    def test_repeat_is_rejected_and_review_run_drafts_new_rows(self):
        self.adapter.rows = [sample()]
        self.service.settings(*YT, 'review')
        self.service.run(*YT)
        self.adapter.rows.append(sample('new-comment'))
        self.service.run(*YT)
        self.assertEqual('draft_error', self.row('new-comment')['state'])
        self.assertIn('repeated', self.row('new-comment')['error'])
        self.assertFalse(self.adapter.sent)

    def test_restart_detection_uses_saved_enabled_modes(self):
        with TemporaryDirectory() as empty:
            self.assertFalse(SocialComments.has_enabled_accounts(empty))
        self.assertFalse(SocialComments.has_enabled_accounts(self.temp.name))
        self.service.settings(*YT, 'review')
        self.assertTrue(SocialComments.has_enabled_accounts(self.temp.name))
        self.service.pause(*YT)
        self.assertFalse(SocialComments.has_enabled_accounts(self.temp.name))

    def test_scheduled_cycle_reloads_saved_timestamp_and_replies_to_backlog(self):
        self.adapter.rows = [sample('older',
                                    published_at=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat())]
        self.service.settings(*YT, 'auto', include_history=True, daily_cap=0)
        first = self.service.run(*YT, due_only=True)
        self.assertEqual('sent', self.row('older')['state'])
        account = next(item for item in first['accounts'] if item['platform'] == 'youtube' and item['profile'] == 'cricket')
        self.assertEqual(timedelta(hours=12),
                         datetime.fromisoformat(account['next_cycle']) - datetime.fromisoformat(account['last_cycle']))

        restarted = SocialComments(self.temp.name, youtube=self.adapter, drafter=gpt)
        self.adapter.rows.append(sample('second'))
        restarted.run(*YT, due_only=True)
        self.assertEqual(1, len(self.adapter.sent))
        self.assertFalse(any(row['comment_id'] == 'second' for row in restarted.status()['comments']))

    def test_new_comment_on_expired_post_is_ignored_on_all_accounts(self):
        self.service.instagram = self.adapter
        self.adapter.rows = [sample(source_published_at=(datetime.now(timezone.utc)-timedelta(days=6)).isoformat())]
        for key in ACCOUNTS:
            self.service.settings(*key, 'auto', include_history=True)
        self.assertEqual([], self.service.run()['run_errors'])
        self.assertEqual([], self.service.status()['comments'])
        self.assertEqual([], self.adapter.sent)

    def test_exact_five_day_boundary_and_missing_dates_are_ineligible(self):
        now = datetime.now(timezone.utc)
        boundary = now - timedelta(days=5)
        self.assertIsNone(recent_publication(boundary.isoformat(), now))
        self.assertEqual(boundary + timedelta(microseconds=1),
                         recent_publication((boundary + timedelta(microseconds=1)).isoformat(), now))
        self.assertIsNone(recent_publication('2026-01-01T00:00:00', now))
        self.assertIsNone(recent_publication((now + timedelta(seconds=1)).isoformat(), now))

    def test_reply_expires_between_preflight_and_submission(self):
        self.adapter.rows = [sample()]
        self.service.settings(*YT, 'review')
        self.service.run(*YT)
        sender = self.adapter.send

        def expires_first(*args, **kwargs):
            with patch('hinglish_app.social_comments.recent_publication', return_value=None):
                return sender(*args, **kwargs)

        self.adapter.send = expires_first
        self.assertIn('five-day', self.service.send(*YT, 'comment-1')['error'])
        self.assertEqual([], self.adapter.sent)

    def test_pause_during_final_live_preflight_prevents_send(self):
        self.adapter.rows = [sample()]
        self.service.settings(*YT, 'auto')
        sender = self.adapter.send

        def pause_first(profile, account_id, row, text, *, authorize):
            self.service.pause(*YT)
            return sender(profile, account_id, row, text, authorize=authorize)

        self.adapter.send = pause_first
        self.service.run(*YT)
        self.assertEqual('draft', self.row()['state'])
        self.assertIsNone(self.row()['attempted_at'])
        self.assertFalse(self.adapter.sent)

    def test_gpt_review_decision_never_auto_sends(self):
        self.service.drafter = lambda *args: {'decision': 'review', 'reply': 'I hear you.', 'reason': 'Sensitive'}
        self.adapter.rows = [sample()]
        self.service.settings(*YT, 'auto')
        self.service.run(*YT)
        self.assertEqual('review', self.row()['state'])
        self.service.pause(*YT)
        with self.assertRaisesRegex(ValueError, 'paused'):
            self.service.send(*YT, 'comment-1')
        self.assertFalse(self.adapter.sent)


if __name__ == '__main__':
    unittest.main()

