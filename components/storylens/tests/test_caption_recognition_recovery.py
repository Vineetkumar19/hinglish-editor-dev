import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace


class RecognitionRecoveryTests(unittest.TestCase):
    def test_retry_reads_entire_audio_in_bounded_overlapping_windows_without_vad_or_script_prompt(self):
        from hinglish_app.caption_recognition_recovery import recognize_windows
        calls=[]
        class Speech:
            def __init__(self,*a,**kw):calls.append(('model',kw))
            def transcribe(self,audio,**kw):
                calls.append((len(audio),kw))
                assert kw['vad_filter'] is False
                assert kw['no_speech_threshold'] is None
                assert not kw.get('initial_prompt')
                assert len(audio)<=14*16000
                # Every chunk includes independently recognized words.
                return iter([SimpleNamespace(words=[SimpleNamespace(word=' spoken',start=1,end=1.4,probability=.9)],end=len(audio)/16000)]),None
        with tempfile.TemporaryDirectory(dir="output") as tmp:
            wav=Path(tmp)/'audio.wav'
            with wave.open(str(wav),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\1\0'*41*16000)
            result=recognize_windows(Speech,'model',wav,41,lambda *a:None,{'device':'cuda','compute_type':'int8_float16'})
        self.assertEqual(len(calls),5)
        self.assertEqual(calls[0][1]['device'],'cuda')
        self.assertEqual([w['start'] for w in result],[1,12,24,36])
        self.assertEqual(calls[-1][0],6*16000)

    def test_overlap_stitch_keeps_boundary_word_once_and_preserves_genuine_repetition(self):
        from hinglish_app.caption_recognition_recovery import stitch
        def w(t,a,b):return {'text':t,'start':a,'end':b,'probability':.9}
        left=[w('book',10,10.3),w('ride',11.8,12.1)]
        right=[w('ride',11.9,12.2),w('ride',12.3,12.6),w('now',12.8,13.1)]
        result=stitch(left,right,12)
        self.assertEqual([v['text'] for v in result],['book','ride','ride','now'])
        self.assertTrue(all(a['start']<=b['start'] for a,b in zip(result,result[1:])))

    def test_word_spaces_from_recognizer_are_retained_with_honest_shared_phrase_timing(self):
        from hinglish_app.caption_recognition_recovery import word_rows
        result=word_rows(SimpleNamespace(word='New York',start=.2,end=.6,probability=.8),5,8)
        self.assertEqual([w['text'] for w in result],['New','York'])
        self.assertEqual([(w['start'],w['end']) for w in result],[(5.2,5.6)]*2)

    def test_failed_stream_closes_and_does_not_return_partial_success(self):
        from hinglish_app.caption_recognition_recovery import recognize_windows
        closed=[]
        class Speech:
            def __init__(self,*a,**kw):pass
            def transcribe(self,*a,**kw):
                def stream():
                    try:
                        yield SimpleNamespace(words=[],end=1)
                        raise RuntimeError('model stopped')
                    finally:closed.append(True)
                return stream(),None
        with tempfile.TemporaryDirectory(dir="output") as tmp:
            wav=Path(tmp)/'audio.wav'
            with wave.open(str(wav),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\1\0'*16000)
            with self.assertRaisesRegex(RuntimeError,'model stopped'):
                recognize_windows(Speech,'model',wav,1,lambda *a:None,{})
        self.assertEqual(closed,[True])


if __name__=='__main__':unittest.main()

