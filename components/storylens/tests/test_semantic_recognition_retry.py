"""Recover the unreadable source seen in the live Script Edit batch."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hinglish_cut.model import Media
from hinglish_cut.recognition_quality import InvalidRecognitionError
from hinglish_semantic.analysis import analyze_sources
from hinglish_semantic.core import SemanticSettings


class SemanticRecognitionRetryTests(unittest.TestCase):
    def analyze(self, retry_error=None):
        settings=SemanticSettings(device='cuda')
        primary=Mock();recovery=Mock();calls=[]
        transcript=object()
        def transcribe(media,digest,root,config,progress,engines):
            calls.append(config)
            if config.speech_backend=='swift':
                engines['engine']=primary
                raise InvalidRecognitionError('invalid placeholder text')
            primary.close.assert_called_once()
            engines['engine']=recovery
            if retry_error:raise retry_error
            return transcript,Path('actual-audio.wav')
        with patch('hinglish_semantic.analysis.fingerprint',return_value='digest'), \
             patch('hinglish_semantic.analysis.prepare_media',return_value=(Media('source','VID.mp4',10,'30',640,360,2,16000),'')), \
             patch('hinglish_semantic.analysis.transcribe_media',side_effect=transcribe):
            result=analyze_sources([Path('VID.mp4')],Path('.'),settings,lambda _:None)
        self.assertEqual(settings.speech_backend,'swift')
        self.assertEqual([(c.device,c.speech_backend) for c in calls],[('cuda','swift'),('cuda','turbo')])
        recovery.close.assert_called_once()
        return result,transcript

    def test_unreadable_source_is_recovered_by_another_local_model(self):
        (transcripts,wavs,errors),expected=self.analyze()
        self.assertEqual(transcripts,[expected])
        self.assertEqual(wavs,{'source':Path('actual-audio.wav')})
        self.assertEqual(errors,[])

    def test_failed_retry_remains_an_explicit_source_error(self):
        (transcripts,wavs,errors),_=self.analyze(InvalidRecognitionError('invalid placeholder text'))
        self.assertEqual((transcripts,wavs),([],{}))
        self.assertEqual(errors[0]['reason'],'invalid_recognition')
        self.assertEqual(errors[0]['source'],'VID.mp4')

    def test_independent_recognizer_also_rejects_placeholders(self):
        from hinglish_semantic.speech import TurboSpeech
        engine=TurboSpeech.__new__(TurboSpeech)
        engine.turbo=Mock()
        engine.turbo.transcribe.return_value=([SimpleNamespace(text='nan')],None)
        with self.assertRaises(InvalidRecognitionError):engine.recognize([0]*1600)


if __name__=='__main__':unittest.main()
