"""Controller fixtures only, never local-model or native acceptance."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hinglish_app.editor_panel import PanelService,prepare_import
from tests.test_editor_panel_review import ImmediateThread


class PanelVisualSourcesTests(unittest.TestCase):
    def test_legacy_visual_import_cannot_bypass_typed_raw_selection(self):
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();output=root/'output/visuals/result';output.mkdir(parents=True)
            source=output/'source.png';source.write_bytes(b'synthetic')
            with self.assertRaisesRegex(ValueError,'source image'):
                prepare_import(root,'premiere',output,asset=str(source))

    def test_visual_result_uses_completed_job_typed_sources_without_legacy_cards(self):
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            state=SimpleNamespace(root=Path(folder),license_client=None,
                create_job=Mock(return_value={'id':'actual-engine','status':'complete','result':{'folder':folder}}))
            service=PanelService(state)
            service.contexts.load=Mock(return_value={'id':'context','host':'premiere','content_format':'short'})
            descriptor={'job_id':'actual-engine','manifest_sha256':'frozen','banks':[{'slot_index':0,'choices':[]}]}
            with patch('hinglish_app.editor_panel.job_payload',return_value={'mode':'visuals','panel_auto_import':False}), \
                 patch('hinglish_app.editor_panel.threading.Thread',ImmediateThread), \
                 patch('hinglish_app.visual_source_transport.VisualSourceTransport') as transport, \
                 patch('hinglish_app.editor_panel.asset_choices',return_value=[]) as legacy, \
                 patch('hinglish_app.editor_panel.prepare_import') as importer:
                transport.return_value.describe.return_value=descriptor
                job=service.start({'context_id':'context','mode':'visuals'})
            self.assertEqual(job['status'],'complete')
            self.assertEqual(job['visual_sources'],descriptor)
            self.assertEqual(job['choices'],[])
            transport.return_value.describe.assert_called_once_with('actual-engine')
            legacy.assert_not_called()
            importer.assert_not_called()

