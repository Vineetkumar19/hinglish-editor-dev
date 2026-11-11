"""Configured CUDA must reach the real model callers, without loading models."""
import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import wave


class GpuDispatchPolicyTests(TestCase):
    def workspace(self, device='cuda', **settings):
        tmp = TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / 'config.models.local.json').write_text(json.dumps({
            'device': device, 'context_limit': 12288, **settings}))
        return root

    def test_publishing_uses_dynamic_gpu_allocation_instead_of_28_layer_cap(self):
        from hinglish_cut.model_preferences import configure_request, publishing_memory_budget
        root = self.workspace(ollama_num_gpu=-1)
        messages = [{'role': 'user', 'content': 'Choose one existing saved Short.'}]
        body = {'messages': messages, 'options': {'num_ctx': 12288, 'num_predict': 500}}
        with publishing_memory_budget():
            configure_request(root, body)
        self.assertEqual(body['options']['num_gpu'], -1)
        self.assertEqual(body['options']['num_ctx'], 4096)
        self.assertIs(body['messages'], messages)

    def test_gpu_policy_also_reaches_ordinary_local_model_calls(self):
        from hinglish_cut.model_preferences import configure_request
        root = self.workspace(ollama_num_gpu=-1)
        body = configure_request(root, {'model': 'existing:local', 'messages': []})
        self.assertEqual(body['options']['num_gpu'], -1)
        self.assertEqual(body['model'], 'existing:local')

    def test_cuda_policy_cannot_silently_disable_gpu(self):
        from hinglish_cut.model_preferences import configure_request
        for value in [0, -2, True, 'all']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'GPU'):
                configure_request(self.workspace(ollama_num_gpu=value), {'messages': []})

    def test_legacy_publisher_short_extraction_honors_cuda_setting(self):
        from hinglish_publish.service import Publisher
        root = self.workspace()
        video = root / 'long.mp4'; video.write_bytes(b'local transport fixture')
        publisher = Publisher.__new__(Publisher); publisher.root = root
        publisher.item = Mock(return_value=[])
        publisher.settings = Mock(return_value={'shorts_count': '1', 'shorts_look': 'template'})
        class ReachedExtraction(Exception): pass
        run = Mock(side_effect=ReachedExtraction)
        with patch.dict('sys.modules', {'hinglish_shorts.pipeline': SimpleNamespace(run=run)}), \
             patch('hinglish_niche.profiles.Profiles.context', return_value={'profile': 'cricket'}), \
             self.assertRaises(ReachedExtraction):
            publisher.prepare_file({'video': str(video), 'kind': 'long', 'thumbnail': ''},
                {'profile': 'cricket', 'make_shorts': True}, lambda _: None)
        self.assertEqual(run.call_args.args[2].device, 'cuda')

    def test_voice_model_honors_gpu_and_holds_shared_slot_during_inference(self):
        from hinglish_app.assistant_media import transcribe_voice
        root = self.workspace()
        folder = root / 'models'; folder.mkdir()
        model = root / 'speech'; model.mkdir(); (model / 'model.bin').write_bytes(b'fixture')
        (folder / 'meaning-models.json').write_text(json.dumps({'speech_path': str(model)}))
        audio = root / 'voice.wav'
        with wave.open(str(audio), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 3200)
        held = []
        @contextmanager
        def slot(_):
            held.append(True)
            try: yield
            finally: held.pop()
        def factory(*args, **kwargs):
            self.assertTrue(held, 'Voice inference must own the shared GPU slot')
            self.assertEqual(kwargs['device'], 'cuda')
            self.assertEqual(kwargs['compute_type'], 'int8_float16')
            def transcribe(*args, **kwargs):
                self.assertTrue(held)
                return iter([SimpleNamespace(text='Test voice request')]), None
            return SimpleNamespace(transcribe=transcribe)
        runtime = Mock()
        with patch.dict('sys.modules', {'faster_whisper': SimpleNamespace(WhisperModel=factory)}), \
             patch('hinglish_cut.gpu_lock.gpu_lock', slot), \
             patch('hinglish_cut.model_preferences.release_ollama') as release, \
             patch('hinglish_app.caption_compute.prepare_runtime', runtime):
            self.assertEqual(transcribe_voice(root, audio), 'Test voice request')
        release.assert_called_once_with(root)
        runtime.assert_called_once_with(root, {'device': 'cuda', 'compute_type': 'int8_float16'})
        self.assertFalse(held)
