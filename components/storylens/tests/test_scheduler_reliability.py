import tempfile,time
from datetime import datetime,timezone
from pathlib import Path
import unittest
from unittest.mock import patch
from hinglish_publish.local_browser import LocalBrowser


class SchedulerReliabilityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.video=self.root/'clip.mp4';self.video.write_bytes(b'video')
        self.queue=LocalBrowser(self.root)

    def scheduled(self):
        self.due=time.time()+600
        return self.queue.enqueue('reel','creator',str(self.video),'Video caption',authorized=True,
            publish_at=datetime.fromtimestamp(self.due,timezone.utc).isoformat())

    def test_clock_runs_preflight_then_the_due_reel_without_daily_prompts(self):
        job=self.scheduled();self.assertIsNone(self.queue.claim('0.4.0')['job'])
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due-290):
            claimed=self.queue.claim('0.4.0')['job'];self.assertEqual(claimed['action'],'inspect')
            self.assertIsNone(self.queue.claim('0.4.0')['job'])
            self.queue.finish(claimed['id'],claimed['lease'],{'status':'complete','account':'creator'})
        restarted=LocalBrowser(self.root)
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due-1):self.assertIsNone(restarted.claim('0.4.0')['job'])
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due+1):
            claimed=restarted.claim('0.4.0')['job'];self.assertEqual(claimed['id'],job['id'])
            self.assertEqual(claimed['action'],'reel')

    def test_failed_readiness_pauses_parent_before_due_and_never_selects_media(self):
        job=self.scheduled()
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due-290):
            claimed=self.queue.claim('0.4.0')['job']
            self.queue.finish(claimed['id'],claimed['lease'],{'status':'needs_review','message':'Login required'})
            self.assertIsNone(self.queue.claim('0.4.0')['job'])
            self.assertEqual(self.queue.get(job['id'])['status'],'needs_review')
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due+1):self.assertIsNone(self.queue.claim('0.4.0')['job'])
        self.assertEqual(self.queue.get(job['id'])['status'],'needs_review')
        self.assertFalse(self.queue.get(job['id'])['submission_started'])
        self.assertEqual(self.queue.readiness()['attention_required'],1)

    def test_wrong_account_cannot_pass_preflight(self):
        self.scheduled()
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due-290):
            claimed=self.queue.claim('0.4.0')['job']
            with self.assertRaises(ValueError):self.queue.finish(claimed['id'],claimed['lease'],{'status':'complete','account':'wrong'})

    def test_only_verified_empty_composer_failures_retry_twice_before_share(self):
        job=self.queue.enqueue('reel','creator',str(self.video),'Video caption',authorized=True)
        for attempt in range(3):
            with patch('hinglish_publish.local_browser.time.time',return_value=time.time()+20*(attempt+1)):
                claimed=self.queue.claim('0.4.0')['job'];self.assertEqual(claimed['id'],job['id'])
                self.queue.phase(job['id'],claimed['lease'],'running')
                result=self.queue.finish(job['id'],claimed['lease'],{'status':'needs_review',
                    'message':'Empty owned composer closed. [storylens-safe-retry:empty-composer]'})
                self.assertEqual(result['status'],'queued' if attempt<2 else 'needs_review')
        self.assertEqual(self.queue.get(job['id'])['retry_count'],2)

    def test_after_share_failure_is_never_automatically_retried(self):
        job=self.queue.enqueue('reel','creator',str(self.video),'Video caption',authorized=True)
        claimed=self.queue.claim('0.4.0')['job'];self.queue.phase(job['id'],claimed['lease'],'sharing')
        result=self.queue.finish(job['id'],claimed['lease'],{'status':'needs_review',
            'message':'[storylens-safe-retry:empty-composer]'})
        self.assertEqual(result['status'],'needs_review');self.assertIsNone(self.queue.claim('0.4.0')['job'])

    def test_missed_slot_remains_failed_after_restart_and_never_posts_late(self):
        job=self.scheduled();restarted=LocalBrowser(self.root)
        with patch('hinglish_publish.local_browser.time.time',return_value=self.due+901):
            self.assertIsNone(restarted.claim('0.4.0')['job'])
        self.assertEqual(restarted.get(job['id'])['status'],'needs_review')
        self.assertEqual(restarted.readiness()['published'],0)


if __name__=='__main__':unittest.main()
