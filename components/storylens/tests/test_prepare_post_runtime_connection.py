"""Connection contracts only; no model inference or media rendering."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from hinglish_publish.prepare_post_runtime import IsolatedRuntime, runtime_connection


class RuntimeConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_reports_configured_model_without_starting_inference(self):
        with patch('hinglish_cut.model_preferences.preferences', return_value={'planning_model': 'actual-local-model', 'cuda_runtime_python': str(Path(__file__).resolve())}):
            status = runtime_connection(self.root)
        self.assertEqual(status['planning_model'], 'actual-local-model')
        self.assertTrue(status['runtime_available'])
        self.assertEqual(status['provider'], 'ollama')

    def test_local_readiness_ignores_system_web_proxy(self):
        import io
        import urllib.request
        from hinglish_publish.prepare_post_runtime import runtime_health
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"models":[{"name":"actual-local-model"}]}')
        with patch('hinglish_cut.model_preferences.preferences', return_value={'planning_model':'actual-local-model'}), \
                patch('urllib.request.getproxies', return_value={'http':'http://unreachable-proxy.invalid:3128'}), \
                patch('urllib.request.build_opener', return_value=opener) as build:
            status = runtime_health(self.root)
        self.assertTrue(status['service_online'])
        self.assertTrue(status['planning_model_installed'])
        self.assertIsInstance(build.call_args.args[0], urllib.request.ProxyHandler)
        self.assertEqual(build.call_args.args[0].proxies, {})
        opener.open.assert_called_once_with('http://127.0.0.1:11434/api/tags', timeout=1)

    def test_worker_uses_configured_runtime_and_saved_stage_request(self):
        request = self.root / 'request.json'
        with patch('hinglish_cut.model_preferences.preferences', return_value={'cuda_runtime_python': str(Path(__file__).resolve())}):
            command = IsolatedRuntime(self.root).command(request)
        self.assertEqual(command[0], str(Path(__file__).resolve()))
        self.assertIn('hinglish_publish.prepare_post_worker', command)
        self.assertEqual(command[-1], str(request))

    def test_missing_runtime_stops_before_starting_a_stage(self):
        with patch('hinglish_cut.model_preferences.preferences', return_value={'cuda_runtime_python': str(self.root / 'missing.exe')}):
            with self.assertRaisesRegex(ValueError, 'runtime'):
                IsolatedRuntime(self.root).command(self.root / 'request.json')

    def test_immediate_cancel_terminates_only_the_owned_native_worker(self):
        from hinglish_publish.prepare_post import Stopped
        runtime = IsolatedRuntime(self.root)
        progress, process = Mock(), Mock()
        progress.check_cancel.side_effect = Stopped()
        process.poll.return_value = None
        with patch.object(runtime, 'command', return_value=['fixture-worker']), \
                patch('hinglish_publish.prepare_post_runtime.subprocess.Popen', return_value=process), \
                patch('hinglish_app.publishing_speech.stop_owned') as stop:
            with self.assertRaises(Stopped):
                runtime.stage('speech', {'id':'cancel-fixture'}, progress)
        progress.check_cancel.assert_called_once()
        stop.assert_called_once_with(process)

    def test_prepare_post_honors_the_configured_cuda_device(self):
        from hinglish_publish.prepare_post_runtime import inference_device
        with patch('hinglish_cut.model_preferences.preferences', return_value={'device':'cuda','require_cuda_inference':True}):
            self.assertEqual(inference_device(self.root), 'cuda')

    def test_explicit_cpu_is_allowed_only_when_cuda_is_not_required(self):
        from hinglish_publish.prepare_post_runtime import inference_device
        with patch('hinglish_cut.model_preferences.preferences', return_value={'device':'cpu','require_cuda_inference':False}):
            self.assertEqual(inference_device(self.root), 'cpu')
        with patch('hinglish_cut.model_preferences.preferences', return_value={'device':'cpu','require_cuda_inference':True}):
            with self.assertRaisesRegex(ValueError, 'CUDA'):
                inference_device(self.root)

    def test_speech_enables_independent_retry_without_skipping_cricket_or_using_cpu(self):
        from hinglish_cut.model import Word
        from hinglish_publish.prepare_post_runtime import LocalRuntime
        words=[Word('Cricket',0,1)]
        with patch('hinglish_shorts.source.open_video',return_value=Mock()), \
                patch('hinglish_shorts.source.transcribe',return_value=words) as transcribe, \
                patch('hinglish_publish.memory.correct_words',return_value=(words,[])), \
                patch('hinglish_publish.prepare_post_runtime.inference_device',return_value='cuda'):
            result=LocalRuntime(self.root)._stage('speech',{'source':{'path':'exact.mp4'},'stages':{},'profile':'cricket'},self.root,{},lambda _:None)
        self.assertTrue(transcribe.call_args.kwargs['retry_unreadable'])
        self.assertFalse(transcribe.call_args.kwargs['skip_invalid_recognition'])
        self.assertEqual(transcribe.call_args.kwargs['device'],'cuda')
        self.assertEqual(result['device'],'cuda')

    def test_truncated_json_is_retried_once_with_preserved_source_and_saved_receipts(self):
        from hinglish_publish.prepare_post_runtime import RecordedBrain
        brain=Mock(name='local');brain.name='fixture-local';brain.last_usage={}
        brain.json.side_effect=[json.JSONDecodeError('Unterminated','{"shorts":',9),{'shorts':[]}]
        recorder=RecordedBrain(brain,self.root,{'all_guidance':'retained'})
        result=recorder.json('Select',{'source':'exact speech'}, {'type':'object'},max_tokens=700,think=True)
        self.assertEqual(result,{'shorts':[]})
        self.assertEqual(brain.json.call_args.args[1]['source'],'exact speech')
        self.assertFalse(brain.json.call_args.kwargs['think'])
        self.assertEqual(len(list(self.root.glob('model-*.json'))),2)
        self.assertTrue(any(json.loads(p.read_text()).get('format_recovery') for p in self.root.glob('model-*.json')))


    def test_decoder_failure_is_shown_to_model_once_and_preserves_context(self):
        from hinglish_publish.prepare_post_runtime import RecordedBrain
        error = RuntimeError('The model produced output that does not match the expected peg-native format')
        for succeeds in (True, False):
            with self.subTest(succeeds=succeeds), tempfile.TemporaryDirectory(dir=self.root) as folder:
                brain=Mock();brain.name='fixture-local';brain.last_usage={}
                brain.json.side_effect=[error, {'shorts':[]} if succeeds else error]
                recorder=RecordedBrain(brain,Path(folder),{'guidance':'keep'})
                args=('Select',{'source':'exact speech'},{'type':'object'})
                if succeeds:self.assertEqual(recorder.json(*args),{'shorts':[]})
                else:
                    with self.assertRaises(RuntimeError):recorder.json(*args)
                self.assertEqual(brain.json.call_count,2)
                feedback=brain.json.call_args.args[1]
                self.assertEqual(feedback['source'],'exact speech')
                self.assertIn('peg-native',feedback['previous_format_error'])
                self.assertIn('format_correction',feedback)
                self.assertFalse(brain.json.call_args.kwargs['think'])
                if not succeeds:
                    brain.json.reset_mock();brain.json.side_effect=None;brain.json.return_value={'shorts':[]}
                    self.assertEqual(recorder.json(*args),{'shorts':[]})
                    self.assertEqual(brain.json.call_count,1)
                    self.assertIn('previous_format_error',brain.json.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
