"""Regression cases discovered in the real reconnect and finished-video check."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from hinglish_publish.local_browser import LocalBrowser
from hinglish_cut.recognition_quality import InvalidRecognitionError
from hinglish_shorts.source import transcribe

class BrowserInspectionTests(TestCase):
    def test_profile_inspection_requests_saved_account_without_rebinding(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            bridge=LocalBrowser(tmp);bridge.bind('cricket','fantasy_legends91')
            job=bridge.inspect_account('cricket')
            self.assertEqual((job['action'],job['account']),('inspect','fantasy_legends91'))
            self.assertEqual(bridge.data['accounts'],{'cricket':'fantasy_legends91'})
    def test_missing_profile_binding_does_not_inspect_an_unrelated_account(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            bridge=LocalBrowser(tmp)
            with self.assertRaisesRegex(ValueError,'saved'):bridge.inspect_account('cricket')
            self.assertEqual(bridge.data['jobs'],[])
    def test_unbound_inspection_accepts_matching_observed_account_without_rebinding(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            bridge=LocalBrowser(tmp)
            job=bridge.enqueue('inspect');claim=bridge.claim('0.4.35')['job']
            result=bridge.finish(job['id'],claim['lease'],{'status':'complete','account':'fantasy_legends91','switch_trace':['fantasy_legends91']})
            self.assertEqual(result['status'],'complete');self.assertEqual(bridge.data['accounts'],{})
    def test_bound_inspection_still_refuses_a_different_account_trace(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            bridge=LocalBrowser(tmp)
            job=bridge.enqueue('inspect','fantasy_legends91');claim=bridge.claim('0.4.35')['job']
            with self.assertRaisesRegex(ValueError,'evidence'):
                bridge.finish(job['id'],claim['lease'],{'status':'complete','account':'other_account','switch_trace':['other_account']})

class PublishingSpeechRetryTests(TestCase):
    def run_recognition(self,recovery_error=None):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            root=Path(tmp);(root/'config.phase2.json').write_text(json.dumps({'device':'cpu'}))
            video=Mock(path=root/'exact.mp4');primary=Mock();secondary=Mock();calls=[]
            def recognize(media,digest,root,settings,progress,engines,**kwargs):
                calls.append((media,digest,settings))
                if settings.speech_backend=='swift':
                    engines['engine']=primary;raise InvalidRecognitionError('invalid speech placeholder')
                primary.close.assert_called_once();engines['engine']=secondary
                if recovery_error:raise recovery_error
                return SimpleNamespace(words=['actual spoken content']),Path('audio.wav')
            with patch('hinglish_shorts.source.quick_fingerprint',return_value='same-source'),patch('hinglish_semantic.analysis.transcribe_media',side_effect=recognize):
                try:result=transcribe(root,video,retry_unreadable=True,progress=lambda _:None)
                finally:
                    if len(calls)>1:secondary.close.assert_called_once()
            self.assertEqual([(c[1],c[2].speech_backend) for c in calls],[('shorts-same-source','swift'),('shorts-same-source','turbo')])
            self.assertIs(calls[0][0],calls[1][0])
            return result
    def test_actual_audio_retries_once_with_independent_local_recognizer(self):
        self.assertEqual(self.run_recognition(),['actual spoken content'])
    def test_failed_recovery_keeps_an_explicit_error(self):
        with self.assertRaises(InvalidRecognitionError):self.run_recognition(InvalidRecognitionError('still unreadable'))
