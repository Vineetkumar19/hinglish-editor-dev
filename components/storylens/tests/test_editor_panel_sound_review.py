import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from hinglish_app.editor_panel import PanelService
from tests.test_editor_panel_review import ImmediateThread


class EditorPanelSoundReviewTests(unittest.TestCase):
    def test_manual_sound_routes_ranked_descriptor_without_the_old_auto_selected_sources(self):
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            state=SimpleNamespace(root=Path(folder),license_client=None,create_job=Mock(return_value={
                'id':'engine-sound','status':'complete','result':{'folder':folder,'sound_recommendations':{'status':'ready'},'review_required':True}}))
            service=PanelService(state);service.contexts.load=Mock(return_value={'id':'context','host':'premiere','content_format':'short'})
            descriptor={'job_id':'engine-sound','groups':[],'auto_insert':False}
            with patch('hinglish_app.editor_panel.job_payload',return_value={'mode':'sound','panel_auto_import':False}), \
                 patch('hinglish_app.editor_panel.threading.Thread',ImmediateThread), \
                 patch('hinglish_app.panel_sound_review.describe',return_value=descriptor), \
                 patch('hinglish_app.editor_panel.sound_choices',return_value=[]) as old, \
                 patch('hinglish_app.editor_panel.prepare_import') as importer:
                job=service.start({'context_id':'context','mode':'sound'})
            self.assertEqual(job['sound_review'],descriptor);self.assertFalse(job['auto_import'])
            old.assert_not_called();importer.assert_not_called()
