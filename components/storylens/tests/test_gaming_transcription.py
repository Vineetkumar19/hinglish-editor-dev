import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from hinglish_cut.model import Media,Word
from hinglish_cut.recognition_quality import InvalidRecognitionError
from hinglish_semantic.analysis import transcribe_media
from hinglish_semantic.core import SemanticSettings


class GamingTranscriptionTests(unittest.TestCase):
    def test_publishing_copy_keeps_real_speech_but_ignores_placeholder_windows(self):
        from hinglish_app.assistant_publish import transcripts
        import hashlib
        for speech,accepted in [(['Actual gameplay reaction',InvalidRecognitionError('placeholder')],True),
                                ([InvalidRecognitionError('placeholder')]*2,False)]:
            with self.subTest(accepted=accepted),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);video=root/'clip.mp4';video.write_bytes(b'video')
                (root/'config.phase2.json').write_text('{}',encoding='utf-8')
                cache=root/'cache/publisher/chat-audio';cache.mkdir(parents=True)
                (cache/(hashlib.sha256(str(video).encode()).hexdigest()+'.wav')).write_bytes(b'audio')
                engine=SimpleNamespace(recognize=Mock(side_effect=speech),close=Mock())
                with patch('hinglish_cut.model_preferences.release_ollama'), \
                     patch('hinglish_cut.model_preferences.preferred_device',return_value='cpu'), \
                     patch('hinglish_cut.media.read_audio',return_value=[0]*16000), \
                     patch('hinglish_semantic.speech.speech_engine',return_value=engine), \
                     patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(duration=29)):
                    if accepted:
                        transcripts(root,[video],lambda _:None)
                        self.assertEqual(video.with_suffix('.txt').read_text('utf-8'),'Actual gameplay reaction')
                    else:
                        with self.assertRaisesRegex(InvalidRecognitionError,'no usable speech'):transcripts(root,[video],lambda _:None)
                        self.assertFalse(video.with_suffix('.txt').exists())
                engine.close.assert_called_once()

    def run_case(self,root,engine,skip):
        media=Media('stream','stream.mp4',60,'30',640,360,2,44100)
        def extract(media,target):Path(target).write_bytes(b'cached audio')
        with patch('hinglish_semantic.analysis.extract_audio',side_effect=extract), \
             patch('hinglish_semantic.analysis.detect_blocks',return_value=[(0,20),(30,50)]), \
             patch('hinglish_semantic.analysis.read_audio',return_value=[0]*16000), \
             patch('hinglish_semantic.analysis.speech_engine',return_value=engine), \
             patch('hinglish_cut.model_storage.signature',return_value={}):
            return transcribe_media(media,'shorts-fixture',root,SemanticSettings(),lambda _:None,{},skip_invalid_recognition=skip)[0]

    def engine(self):
        return SimpleNamespace(recognize=Mock(side_effect=[InvalidRecognitionError('placeholder'), 'Actual gameplay reaction']),
            align=Mock(return_value=[Word('Actual',0,5,.99,True)]),romanize=lambda text:text)

    def test_gaming_skips_bad_window_keeps_later_speech_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            engine=self.engine();root=Path(folder)
            result=self.run_case(root,engine,True)
            self.assertEqual([w.text for w in result.words],['Actual'])
            self.assertGreaterEqual(result.words[0].start,29)
            self.assertTrue(any(i.startswith('invalid_recognition_skipped:') for i in result.issues))
            self.run_case(root,engine,True);self.assertEqual(engine.recognize.call_count,2)
            with self.assertRaises(InvalidRecognitionError):self.run_case(root,engine,False)

    def test_strict_editing_still_rejects_invalid_recognition(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(InvalidRecognitionError):self.run_case(Path(folder),self.engine(),False)

    def test_shorts_pipeline_skips_invalid_windows_only_for_gaming(self):
        from hinglish_shorts.pipeline import run
        from hinglish_niche.profiles import use
        for profile in ('gaming','cricket','general'):
            with self.subTest(profile=profile),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'highlight.mp4';source.write_bytes(b'video')
                video=SimpleNamespace(duration=719,width=1280,height=720,fps=30)
                with use({'profile':profile}),patch('hinglish_shorts.pipeline.open_video',return_value=video), \
                     patch('hinglish_shorts.pipeline.transcribe',side_effect=ValueError('transcription reached')) as transcribe:
                    with self.assertRaisesRegex(ValueError,'transcription reached'):run(root,source,progress=lambda _:None)
                self.assertEqual(transcribe.call_args.kwargs,{'skip_invalid_recognition':True} if profile=='gaming' else {})
