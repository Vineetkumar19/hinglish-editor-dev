"""GPU-only voice synthesis contracts; written before the fallback change."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from hinglish_voice import worker


class VoiceoverGPUTests(unittest.TestCase):
    def test_explicit_cpu_request_never_initializes_cuda(self):
        torch=self.torch(available=False)
        self.assertEqual(worker.gpu_config(torch, 'cpu'),('cpu','fp32'))
        torch.cuda.is_available.assert_not_called()

    def test_unknown_device_is_rejected(self):
        with self.assertRaises(ValueError): worker.gpu_config(self.torch(),'automatic')

    def torch(self, available=True, bf16=True):
        return types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=Mock(return_value=available),
                                      is_bf16_supported=Mock(return_value=bf16),
                                      get_device_name=Mock(return_value='Test NVIDIA GPU')),
            bfloat16='bf16', float32='fp32')

    def test_cuda_unavailable_never_falls_back_to_cpu(self):
        with self.assertRaisesRegex(RuntimeError, 'Voiceover GPU:'):
            worker.gpu_config(self.torch(available=False))

    def test_cuda_precision_matches_hardware_support(self):
        for bf16, expected in ((True, 'bf16'), (False, 'fp32')):
            with self.subTest(bf16=bf16):
                self.assertEqual(worker.gpu_config(self.torch(bf16=bf16)), ('cuda', expected))

    def test_worker_passes_cuda_to_model_and_records_gpu_receipt(self):
        torch = self.torch()
        torch.set_num_threads = Mock()
        torch.inference_mode = contextlib.nullcontext
        torch.from_numpy = Mock(return_value=Mock())
        audio = Mock()
        model = Mock(sampling_rate=24000)
        model.generate.return_value = [audio]
        engine = Mock()
        engine.from_pretrained.return_value = model
        soundfile = types.SimpleNamespace(read=Mock(return_value=([.1, .2], 24000)), write=Mock())
        task = dict(source='not-a-real-runtime', model='local-model', reference='ref.wav',
                    script='My exact words.', transcript='Reference words.', language='en', speed=1, output='out.wav')
        Path('work/voiceover-tests').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir='work/voiceover-tests') as folder:
            path = Path(folder)/'task.json'
            path.write_text(json.dumps(task), encoding='utf-8')
            output = io.StringIO()
            with patch.object(sys, 'argv', ['worker.py', str(path)]), patch.object(sys, 'path', list(sys.path)), \
                 patch.dict(sys.modules, {'torch':torch, 'soundfile':soundfile,
                                          'omnivoice':types.SimpleNamespace(OmniVoice=engine)}), \
                 contextlib.redirect_stdout(output):
                worker.main()
        engine.from_pretrained.assert_called_once_with('local-model', device_map='cuda', dtype='bf16', load_asr=False)
        self.assertEqual(model.generate.call_args.kwargs['text'], 'My exact words.')
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt['device'], 'cuda')
        self.assertEqual(receipt['gpu'], 'Test NVIDIA GPU')

    def test_gpu_error_uses_shared_plain_language_catalog(self):
        from hinglish_app.user_messages import problem
        issue = problem(RuntimeError('Voiceover GPU: CUDA is unavailable; CPU fallback is disabled.'), feature='Voiceover')
        self.assertEqual(issue['code'], 'voiceover_gpu')
        self.assertIn('NVIDIA', issue['message'])
        self.assertIn('saved', issue['message'])
        self.assertIn('CPU fallback', issue['details'])


if __name__ == '__main__': unittest.main()
