"""CPU-only configuration tests; no runtime, GPU allocation or inference."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hinglish_visuals.settings import load_settings
from hinglish_visuals.brain import open_brain


class VisualsGpuPolicyTests(unittest.TestCase):
    def test_direct_run_inherits_shared_gpu_device(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'config.models.local.json').write_text(json.dumps({'device':'cuda','require_cuda_inference':True}))
            self.assertEqual(load_settings(temp).device,'cuda')

    def test_required_gpu_overrides_stale_feature_or_run_cpu_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'config.models.local.json').write_text(json.dumps({'device':'cuda','require_cuda_inference':True}))
            Path(temp,'config.visuals.local.json').write_text(json.dumps({'device':'cpu','density':'low'}))
            settings=load_settings(temp,device='cpu')
            self.assertEqual(settings.device,'cuda');self.assertEqual(settings.density,'low')

    def test_cpu_remains_available_without_gpu_requirement(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(load_settings(temp).device,'cpu')
            Path(temp,'config.models.local.json').write_text(json.dumps({'device':'cuda'}))
            self.assertEqual(load_settings(temp,device='cpu').device,'cpu')

    def test_required_gpu_never_silently_starts_the_unverified_cpu_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'config.models.local.json').write_text(json.dumps({'device':'cuda','require_cuda_inference':True}))
            with patch('hinglish_visuals.brain.OllamaBrain',side_effect=RuntimeError('runtime unavailable')),                  patch('hinglish_visuals.brain.LocalBrain') as cpu:
                with self.assertRaisesRegex(RuntimeError,'GPU'):
                    open_brain(temp,progress=lambda _:None)
                cpu.assert_not_called()
            with patch('hinglish_visuals.brain.LocalBrain') as cpu:
                with self.assertRaisesRegex(RuntimeError,'GPU'):open_brain(temp,choice='local')
                cpu.assert_not_called()
            with patch('hinglish_visuals.brain.LocalBrain') as cpu:
                with self.assertRaisesRegex(RuntimeError,'GPU'):open_brain(temp,choice='unknown')
                cpu.assert_not_called()

    def test_working_ollama_and_legacy_fallback_contracts_remain(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'config.models.local.json').write_text(json.dumps({'device':'cuda','require_cuda_inference':True}))
            with patch('hinglish_visuals.brain.OllamaBrain',return_value='local-GPU-runtime') as runtime,                  patch('hinglish_visuals.brain.LocalBrain') as cpu:
                self.assertEqual(open_brain(temp,model='owner-selected-model'),'local-GPU-runtime')
                self.assertEqual(runtime.call_args.args[1],'owner-selected-model');cpu.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            with patch('hinglish_visuals.brain.OllamaBrain',side_effect=RuntimeError('unavailable')),                  patch('hinglish_visuals.brain.LocalBrain',return_value='legacy'):
                self.assertEqual(open_brain(temp,progress=lambda _:None),'legacy')


if __name__=='__main__':unittest.main()
