"""Saved recommendation receipts, not local inference or listening evidence."""
import copy
import unittest
from unittest.mock import patch
from tests import test_panel_sound_review as fixtures


class CompletedSoundJobsTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.PanelSoundReviewTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.root=self.fx.fx.root;self.job=copy.deepcopy(self.fx.job)
        self.job['payload']={'private_context':'not a public receipt'}

    def test_saved_completed_review_restores_without_starting_inference(self):
        from hinglish_app.completed_sound_jobs import save,load
        from hinglish_app.server import AppState
        self.assertTrue(save(self.root,8765,self.job))
        self.assertNotIn('payload',load(self.root,8765)['actual-sound'])
        with patch.object(AppState,'_run_job') as run:
            state=AppState(self.root,8765)
        self.assertEqual(state.snapshot('actual-sound')['result'],self.job['result']);run.assert_not_called()

    def test_running_failed_foreign_and_other_port_are_not_completed_reviews(self):
        from hinglish_app.completed_sound_jobs import save,load
        for status in ('running','queued','failed'):
            self.assertFalse(save(self.root,8765,{**self.job,'status':status}))
        foreign=copy.deepcopy(self.job);foreign['result']['folder']=str(self.root)
        self.assertFalse(save(self.root,8765,foreign));self.assertEqual(load(self.root,8766),{})

    def test_changed_manifest_is_not_restored_after_restart(self):
        from hinglish_app.completed_sound_jobs import save,load
        self.assertTrue(save(self.root,8765,self.job));self.fx.fx.path.write_text('{}')
        self.assertEqual(load(self.root,8765),{})
