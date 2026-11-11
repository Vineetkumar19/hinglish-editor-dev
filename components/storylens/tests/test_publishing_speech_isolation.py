"""Exercise real child exits without loading speech models or publishing."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


class PublishingSpeechIsolationTests(TestCase):
    def fixture(self):
        tmp = TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name); video = root / 'clip.mp4'; video.write_bytes(b'fixture')
        return root, video

    def test_child_failure_is_saved_and_parent_can_continue_without_transcript(self):
        from hinglish_app.publishing_speech import transcribe, PublishingSpeechError
        root, video = self.fixture()
        with patch('hinglish_app.publishing_speech.command', return_value=[sys.executable, '-c', 'import os;os._exit(23)']):
            with self.assertRaisesRegex(PublishingSpeechError, 'speech worker stopped') as failure:
                transcribe(root, [video], lambda _: None)
        self.assertIn('23', failure.exception.stderr)
        self.assertFalse(video.with_suffix('.txt').exists())
        states = list((root / 'cache/publisher/speech').glob('*/status.json'))
        self.assertEqual(len(states), 1)
        self.assertEqual(json.loads(states[0].read_text())['status'], 'failed')

    def test_real_worker_module_validates_source_and_saves_a_completed_checkpoint(self):
        from hinglish_app.publishing_speech_worker import execute
        from hinglish_publish.store import fingerprint
        root, video = self.fixture(); key = 'a' * 32
        folder = root / 'cache/publisher/speech' / key; folder.mkdir(parents=True)
        request = {'videos': [{'path': str(video), 'sha256': fingerprint(video)}], 'gpu_locked_by_parent': False}
        (folder / 'request.json').write_text(json.dumps(request))
        def fixture_speech(root, videos, progress):
            progress('Reading the spoken content: 0/2s')
            videos[0].with_suffix('.txt').write_text('Observed words')
        with patch('hinglish_app.assistant_publish._transcripts_in_process', side_effect=fixture_speech) as speech:
            execute(root, key)
        self.assertEqual(json.loads((folder / 'status.json').read_text())['status'], 'ready')
        video.write_bytes(b'changed')
        with patch('hinglish_app.assistant_publish._transcripts_in_process') as changed:
            with self.assertRaisesRegex(ValueError, 'changed'):execute(root, key)
        changed.assert_not_called(); speech.assert_called_once()

    def test_completed_child_checkpoint_is_accepted_and_existing_copy_skips_worker(self):
        from hinglish_app.publishing_speech import transcribe
        root, video = self.fixture()
        def fixture_command(root, key):
            folder = root / 'cache/publisher/speech' / key
            script = ('import json;from pathlib import Path;'
                f'p=Path({str(video.with_suffix(".txt"))!r});p.write_text("Recorded local speech");'
                f'Path({str(folder / "status.json")!r}).write_text(json.dumps({{"status":"ready","stage":"Speech saved"}}))')
            return [sys.executable, '-c', script]
        with patch('hinglish_app.publishing_speech.command', side_effect=fixture_command) as launch:
            transcribe(root, [video], lambda _: None)
            transcribe(root, [video], lambda _: None)
        launch.assert_called_once()
        self.assertEqual(video.with_suffix('.txt').read_text(), 'Recorded local speech')

    def test_cancellation_stops_only_owned_child_and_keeps_preparation(self):
        from hinglish_app.publishing_speech import transcribe
        root, video = self.fixture()
        with patch('hinglish_app.publishing_speech.command', return_value=[sys.executable, '-c', 'import time;time.sleep(30)']):
            with self.assertRaisesRegex(ValueError, 'Stopped'):
                transcribe(root, [video], lambda _: None, cancelled=lambda: True)
        state = json.loads(next((root / 'cache/publisher/speech').glob('*/status.json')).read_text())
        self.assertEqual(state['status'], 'cancelled')
        self.assertTrue(video.exists()); self.assertFalse(video.with_suffix('.txt').exists())

    def test_unavailable_runtime_is_not_left_as_an_endless_queued_worker(self):
        from hinglish_app.publishing_speech import transcribe
        root, video = self.fixture()
        with patch('hinglish_app.publishing_speech.command', side_effect=ValueError('Check the local runtime.')):
            with self.assertRaisesRegex(ValueError, 'runtime'):transcribe(root, [video], lambda _: None)
        state = json.loads(next((root / 'cache/publisher/speech').glob('*/status.json')).read_text())
        self.assertEqual(state['status'], 'failed')
