"""Exact export speech must survive a renamed publishing copy; no model calls."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from hinglish_publish.store import fingerprint


class PublisherTranscriptReuseTests(TestCase):
    def fixture(self):
        temp = TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        library = root / 'All Shorts'; library.mkdir()
        output = root / 'output/shorts/saved'; output.mkdir(parents=True)
        original = output / '03 - Match.mp4'; original.write_bytes(b'exact finished export')
        source = library / 'Shorts 4.mp4'; source.write_bytes(original.read_bytes())
        target = root / 'delivery/short-01.mp4'; target.parent.mkdir()
        target.write_bytes(source.read_bytes())
        (library / 'library.json').write_text(json.dumps({'shorts': [{
            'file': source.name, 'sha256': fingerprint(source), 'original_paths': [str(original)]}]}))
        (output / 'shorts-project.json').write_text(json.dumps({'shorts': [{
            'mp4': original.name, 'pieces': [[2, 5]]}], 'words': [
                ['Excluded', 0, 1], ['Exact', 2, 3], ['spoken', 3, 4], ['words', 4, 5], ['Excluded', 7, 8]]}))
        return root, source, target

    def test_renamed_exact_copy_keeps_recorded_words_and_evidence_without_asr(self):
        from hinglish_publish.source_context import preserve_transcript
        from hinglish_app.assistant_publish import transcripts
        root, source, target = self.fixture()
        self.assertTrue(preserve_transcript(root, source, target))
        self.assertEqual(target.with_suffix('.txt').read_text(), 'Exact spoken words')
        receipt = json.loads(target.with_suffix('.transcript-source.json').read_text())
        self.assertEqual(receipt['sha256'], fingerprint(target))
        self.assertEqual(receipt['method'], 'saved_export_word_timings')
        with patch('hinglish_semantic.speech.speech_engine') as speech:
            transcripts(root, [target], lambda _: None)
        speech.assert_not_called()

    def test_changed_copy_is_not_given_old_words_and_creator_sidecar_is_preserved(self):
        from hinglish_publish.source_context import preserve_transcript
        root, source, target = self.fixture()
        target.write_bytes(b'different export')
        with self.assertRaisesRegex(ValueError, 'changed'):
            preserve_transcript(root, source, target)
        self.assertFalse(target.with_suffix('.txt').exists())
        target.write_bytes(source.read_bytes()); target.with_suffix('.txt').write_text('Owner transcript')
        self.assertFalse(preserve_transcript(root, source, target))
        self.assertEqual(target.with_suffix('.txt').read_text(), 'Owner transcript')

    def test_unknown_or_changed_original_does_not_manufacture_transcript(self):
        from hinglish_publish.source_context import preserve_transcript
        root, source, target = self.fixture()
        original = root / 'output/shorts/saved/03 - Match.mp4'
        original.write_bytes(b'changed since export')
        self.assertFalse(preserve_transcript(root, source, target))
        self.assertFalse(target.with_suffix('.txt').exists())
