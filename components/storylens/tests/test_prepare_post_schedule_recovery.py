"""Same-video Studio recovery never repeats an uncertain upload."""
import tempfile
import time
import unittest
from pathlib import Path

from hinglish_publish.local_browser import LocalBrowser


class UnappliedScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.bridge=LocalBrowser(Path(self.tmp.name))
        self.task=self.bridge.enqueue_youtube('UC'+'g'*22,'new00000001','2035-01-01T18:30:00+05:30',
            'owned',authorized=True)
        self.saved=self.bridge.data['jobs'][0]
        self.saved.update(status='submitted',submitted_at=time.time()-80,updated=time.time()-70,submission_started=True,last_phase='sharing')
        self.proof={'id':'new00000001','privacy':'private','publish_at':'','private_verified_at':time.time()}

    def test_fresh_private_proof_reuses_task_and_preserves_previous_attempt(self):
        value=self.bridge.retry_unapplied_youtube(self.task['id'],self.proof)
        self.assertEqual(value['id'],self.task['id'])
        self.assertEqual(value['status'],'queued')
        self.assertEqual(value['attempts'][0]['private_only_readback'],self.proof)
        self.assertEqual(len(self.bridge.data['jobs']),1)
        self.saved.update(status='submitted',submitted_at=time.time()-80)
        self.bridge.retry_unapplied_youtube(self.task['id'],self.proof)
        self.saved.update(status='submitted',submitted_at=time.time()-80)
        with self.assertRaises(ValueError):self.bridge.retry_unapplied_youtube(self.task['id'],self.proof)

    def test_absent_stale_other_video_or_existing_schedule_proof_cannot_retry(self):
        for change in ({'id':'other-video'},{'private_verified_at':time.time()-30},
                       {'publish_at':'2035-01-01T13:00:00Z'},{'privacy':'public'}):
            with self.assertRaises(ValueError):
                self.bridge.retry_unapplied_youtube(self.task['id'],{**self.proof,**change})
        self.assertEqual(self.saved['status'],'submitted')
        self.assertEqual(len(self.bridge.data['jobs']),1)

    def test_new_studio_task_waits_for_previous_remote_confirmation(self):
        self.saved['needs_remote_confirmation']=True;self.saved['updated']=time.time()
        next_task=self.bridge.enqueue_youtube('UC'+'g'*22,'new00000002','2035-01-02T18:30:00+05:30',
            'owned',authorized=True)
        self.assertIsNone(self.bridge.claim('0.4.35',['youtube_schedule'])['job'])
        self.bridge.confirm_youtube(self.saved['id'],{'id':'new00000001','privacy':'private',
            'publish_at':self.saved['publish_at'],'schedule_verified_at':time.time()})
        self.assertEqual(self.bridge.claim('0.4.35',['youtube_schedule'])['job']['id'],next_task['id'])
