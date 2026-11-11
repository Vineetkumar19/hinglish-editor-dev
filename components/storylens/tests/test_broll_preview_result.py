"""Shared result contract; fixture bytes are not media playback evidence."""
import json
import tempfile
import unittest
from pathlib import Path

from hinglish_app.broll_preview_result import collect


class BrollPreviewResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'output/broll/bank'
        self.folder = self.output / '001-source'
        self.folder.mkdir(parents=True)
        self.preview = self.folder / 'preview.mp4'
        self.preview.write_bytes(b'OLD AGGREGATE PRESERVED')
        (self.output / 'audio-only-source.mp4').write_bytes(b'EXISTING GENERATED SOURCE')

    def project(self, state=None, **extra):
        data = dict(extra)
        if state is not None:
            data['preview_state'] = state
        (self.folder / 'broll-project.json').write_text(json.dumps(data))

    def test_deferred_hides_stale_aggregate_and_offers_only_fixed_source(self):
        self.project('deferred', preview_source='../audio-only-source.mp4')
        result = collect(self.root, self.output)
        self.assertEqual(result['previews'], [])
        self.assertEqual(result['broll_previews'][0]['source_url'], '/broll-output/bank/audio-only-source.mp4')
        self.assertIn('Save & rebuild', result['broll_preview_notice'])
        self.assertEqual(self.preview.read_bytes(), b'OLD AGGREGATE PRESERVED')

    def test_failed_and_unknown_states_do_not_offer_old_aggregate(self):
        for state in ('failed', 'untrusted'):
            with self.subTest(state=state):
                self.project(state)
                result = collect(self.root, self.output)
                self.assertEqual(result['previews'], [])
                self.assertIsNone(result['broll_previews'][0]['source_url'])

    def test_ready_and_legacy_keep_existing_preview_behavior(self):
        for state in ('ready', None):
            with self.subTest(state=state):
                self.project(state)
                self.assertEqual(collect(self.root, self.output)['previews'], [str(self.preview.resolve())])

    def test_deferred_source_does_not_trust_arbitrary_metadata_or_missing_file(self):
        for source in ('../../private.mp4', 'https://example.com/video.mp4', '../other.mp4'):
            self.project('deferred', preview_source=source)
            self.assertIsNone(collect(self.root, self.output)['broll_previews'][0]['source_url'])
        self.project('deferred', preview_source='../audio-only-source.mp4')
        (self.output / 'audio-only-source.mp4').unlink()
        self.assertIsNone(collect(self.root, self.output)['broll_previews'][0]['source_url'])

    def test_output_outside_generated_broll_is_rejected(self):
        with self.assertRaises(ValueError):
            collect(self.root, self.root)
