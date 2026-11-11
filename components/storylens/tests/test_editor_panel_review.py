"""Panel controller tests only; mock engine results are not native acceptance."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hinglish_app.editor_panel import PanelService


class ImmediateThread:
    def __init__(self, target, **kwargs): self.target=target
    def start(self): self.target()


class PanelReviewTests(unittest.TestCase):
    def run_result(self, mode, review=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'output/phase2/sample';output.mkdir(parents=True)
            (output/'report.json').write_text(json.dumps({'status':'REVIEW_REQUIRED'}))
            result={'folder':str(output),'quality_summary':{'passed':True,'score':100},'review_required':review}
            state=SimpleNamespace(root=root,license_client=None,
                create_job=Mock(return_value={'id':'engine','status':'complete','result':result}))
            service=PanelService(state)
            service.contexts.load=Mock(return_value={'id':'context','host':'premiere','content_format':'short'})
            with patch('hinglish_app.editor_panel.job_payload',return_value={'mode':mode,'panel_auto_import':True}), \
                 patch('hinglish_app.editor_panel.threading.Thread',ImmediateThread), \
                 patch('hinglish_app.editor_panel.prepare_import',return_value={'type':'files'}) as importer:
                initial=service.start({'context_id':'context','mode':mode})
                return service.snapshot(initial['id']),importer.call_count

    def test_script_quality_score_does_not_bypass_semantic_draft_review(self):
        job,imports=self.run_result('script')
        self.assertEqual(imports,0)
        self.assertFalse(job['auto_import'])
        self.assertTrue(job['review_required'])
        self.assertIn('draft',job['stage'].lower())
        self.assertIsNone(job['manifest'])

    def test_explicit_engine_review_flag_prevents_any_automatic_import(self):
        job,imports=self.run_result('clean',review=True)
        self.assertEqual(imports,0)
        self.assertFalse(job['auto_import'])

    def test_ordinary_successful_clean_keeps_existing_automatic_handoff(self):
        job,imports=self.run_result('clean')
        self.assertEqual(imports,1)
        self.assertTrue(job['auto_import'])

