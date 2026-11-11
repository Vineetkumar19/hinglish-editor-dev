import unittest
from unittest.mock import Mock
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class DirectCaptionAlignmentTests(unittest.TestCase):
    def test_punctuation_is_preserved_as_formatting_not_a_spoken_word(self):
        from hinglish_app.caption_speech_text import caption_tokens
        words=caption_tokens('Next episode — Rapido ka scam.')
        self.assertEqual([w['spoken'] for w in words],['Next','episode','Rapido','ka','scam.'])
        self.assertEqual(' '.join(w['text'] for w in words),'Next episode — Rapido ka scam.')
        self.assertEqual(caption_tokens('— …'),[])

    def test_initialisms_match_their_spoken_letter_names_generically(self):
        from hinglish_app.caption_native_timing import align_words
        observed=[{'text':w,'start':i,'end':i+.4} for i,w in enumerate(['piji','eisi','arpiem'])]
        words=align_words('PG AC RPM',observed,4)
        self.assertEqual([w['text'] for w in words],['PG','AC','RPM'])
        self.assertEqual([w['start'] for w in words],[0,1,2])

    def test_direct_timing_keeps_real_uneven_word_spans_and_marks_uncertain_words(self):
        from hinglish_app.caption_audio_alignment import validate_aligned
        raw=[{'start':.42,'end':.66,'probability':.9},{'start':.70,'end':1.28,'probability':.12},{'start':3.9,'end':4.12,'probability':.8}]
        words=validate_aligned(['my','exact','words'],raw,6)
        self.assertEqual([(w['start'],w['end']) for w in words],[(.42,.66),(.70,1.28),(3.9,4.12)])
        self.assertTrue(words[1]['review_reason'])
        self.assertFalse(words[0].get('review_reason'))

    def test_zero_duration_word_uses_a_labelled_shared_audio_span_not_invented_word_precision(self):
        from hinglish_app.caption_audio_alignment import validate_aligned
        raw=[{'start':1,'end':1,'probability':.01},{'start':1,'end':1.6,'probability':.9}]
        words=validate_aligned(['AC','room'],raw,4)
        self.assertEqual([(w['start'],w['end']) for w in words],[(1,1.6),(1,1.6)])
        self.assertEqual(words[0]['alignment'],'acoustic_phrase')

    def test_invalid_acoustic_results_are_rejected(self):
        from hinglish_app.caption_audio_alignment import validate_aligned
        for raw in [[],[{'start':float('nan'),'end':1,'probability':.9}],[{'start':0,'end':9,'probability':.9}],[{'start':1,'end':0,'probability':.9}]]:
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate_aligned(['word'],raw,4)

    def test_unrelated_script_and_conflicting_numbers_stop_before_forced_alignment(self):
        from hinglish_app.caption_audio_alignment import check_relation
        with self.assertRaises(ValueError):check_relation(['gardening','flowers','watering','plants'],[],[{'text':'Mumbai won today'}],lambda s:s.lower())
        with self.assertRaises(ValueError):check_relation(['Mumbai','won','2009'],[{'script_index':0,'alignment':'matched'},{'script_index':1,'alignment':'matched'}],[{'text':'Mumbai'},{'text':'won'},{'text':'2008'}],lambda s:s.lower())

    def test_windows_follow_known_audio_anchors_and_stay_bounded(self):
        from hinglish_app.caption_audio_alignment import plan_windows
        anchors=[{'script_index':i,'start':i*.5,'end':i*.5+.3,'alignment':'matched'} for i in range(70)]
        windows=plan_windows(list(map(str,range(70))),anchors,36)
        self.assertEqual(windows[0]['first'],0)
        self.assertEqual(windows[-1]['last'],70)
        self.assertTrue(all(.2<=w['end']-w['start']<=28 for w in windows))
        for a,b in zip(windows,windows[1:]):self.assertEqual(a['last'],b['first'])

    def test_native_tiny_window_guard_never_calls_the_crashing_alignment_backend(self):
        from hinglish_app.caption_audio_alignment import guard_alignment
        model=Mock();model.find_alignment.return_value=['real']
        real=model.find_alignment;guard_alignment(model)
        self.assertEqual(model.find_alignment(None,[[1,2]],None,1),[[]]);real.assert_not_called()
        self.assertEqual(model.find_alignment(None,[[1,2]],None,100),['real']);real.assert_called_once()

    def test_number_anchors_bound_the_audio_windows_instead_of_reordering_direct_results(self):
        from hinglish_app.caption_audio_alignment import align_from_audio
        import wave
        observed=[{'text':t,'start':a,'end':b,'probability':.95} for t,a,b in [('before',.1,.4),('10',.5,.65),('after',1.1,1.4),('now',1.6,1.9)]]
        calls=[]
        class Aligner:
            def __init__(self,*a,**kw):pass
            def align(self,audio,words):
                calls.append(words)
                if '10' in words:raise AssertionError('A verified number must constrain, not be retimed by, direct alignment')
                return [{'start':.1+i*.25,'end':.2+i*.25,'probability':.9} for i in range(len(words))]
        with tempfile.TemporaryDirectory(dir='output/caption-one-general-speech-20261029') as tmp:
            wav=Path(tmp)/'voice.wav'
            with wave.open(str(wav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*64000)
            words=align_from_audio('installed',wav,'before 10 after now',observed,4,lambda s:s.lower(),lambda *a:None,factory=Aligner)
        self.assertEqual((words[1]['start'],words[1]['end']),(.5,.65))
        self.assertTrue(all(a['start']<=b['start'] for a,b in zip(words,words[1:])))
        self.assertTrue(all('10' not in group for group in calls))

    def test_recovery_never_retimes_verified_speech_words_and_only_aligns_the_gap(self):
        from hinglish_app.caption_audio_alignment import align_from_audio
        import wave
        observed=[{'text':'before','start':.1,'end':.4,'probability':.95},{'text':'after','start':1.3,'end':1.6,'probability':.98}]
        class DriftingAligner:
            def __init__(self,*a,**kw):pass
            def align(self,audio,words):
                self.words=words
                spans={'before':(.25,.39),'a':(.5,.65),'new':(.8,1.1),'after':(1.45,1.6)}
                return [{'start':spans[w][0],'end':spans[w][1],'probability':.9} for w in words]
        with tempfile.TemporaryDirectory(dir='output/caption-one-general-speech-20261029') as tmp:
            wav=Path(tmp)/'voice.wav'
            with wave.open(str(wav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*32000)
            words=align_from_audio('installed',wav,'before a new after',observed,2,lambda s:s.lower(),lambda *a:None,factory=DriftingAligner)
        self.assertEqual([(words[i]['start'],words[i]['end']) for i in (0,3)],[(.1,.4),(1.3,1.6)])
        self.assertEqual([w['text'] for w in words],['before','a','new','after'])
        self.assertTrue(all(.4<=words[i]['start']<words[i]['end']<=1.3 for i in (1,2)))

    def test_real_worker_uses_audio_recovery_and_keeps_all_script_words(self):
        from hinglish_app.caption_native_timing import execute
        with tempfile.TemporaryDirectory(dir='output/caption-one-general-speech-20261029') as tmp:
            root=Path(tmp).resolve();source=root/'voice.wav';source.write_bytes(b'audio');model=root/'model';model.mkdir();folder=root/'output/captions/ae-speech'/('d'*32);folder.mkdir(parents=True)
            capture={'duration':6,'unsupported':[],'clips':[{'path':str(source),'start':0,'end':6,'source_in':0}]}
            script='My final caption words.';(folder/'request.json').write_text(json.dumps({'script':script,'timing_context':capture}))
            class Speech:
                def __init__(self,*a,**kw):pass
                def transcribe(self,*a,**kw):return iter([SimpleNamespace(end=5,words=[])]),None
            modules={'faster_whisper':SimpleNamespace(WhisperModel=Speech),'uroman':SimpleNamespace(Uroman=lambda:SimpleNamespace(romanize_string=lambda s,**kw:s))}
            recovered=[{'text':t,'script_index':i,'start':a,'end':b,'alignment':'acoustic_word',**({'review_reason':'Review wording'} if i==1 else {})} for i,(t,a,b) in enumerate([('My',0,.4),('final',.5,1),('caption',1.1,1.8),('words.',2,2.4)])]
            retry_words=[{'text':t,'start':i,'end':i+.4,'probability':.98} for i,t in enumerate(['My','spoken','words'])]
            with patch.dict('sys.modules',modules),patch('hinglish_cut.model_storage.configure'),patch('hinglish_app.caption_compute.options_for',return_value={'device':'cpu','compute_type':'int8'}),patch('hinglish_cut.model_storage.role',return_value={'path':str(model)}),patch('hinglish_app.template_text_audio.decode_map',side_effect=lambda s,p:Path(p).write_bytes(b'audio')),patch('hinglish_app.caption_recognition_recovery.recognize_windows',return_value=retry_words) as recognition_retry,patch('hinglish_app.caption_audio_alignment.align_from_audio',return_value=recovered) as recovery:
                execute(root,'d'*32)
            recognition_retry.assert_called_once()
            recovery.assert_called_once();project=json.loads((folder/'caption-project.json').read_text())
            self.assertEqual(project['reference_script'],script)
            self.assertEqual([c['words'][0]['text'] for c in project['cues']],script.split())
            self.assertEqual(project['transcription']['acoustic_review_words'],['final'])
            self.assertEqual(project['transcription']['omitted_script_words'],[])
            # Integration regression: an exact cached result needs neither ASR nor the
            # shared heavy-model slot. This is supplementary cache coverage.
            again=root/'output/captions/ae-speech'/('e'*32);again.mkdir()
            (again/'request.json').write_text((folder/'request.json').read_text())
            with patch.dict('sys.modules',modules),patch('hinglish_cut.model_storage.configure'),patch('hinglish_app.caption_compute.options_for',return_value={'device':'cpu','compute_type':'int8'}),patch('hinglish_cut.model_storage.role',return_value={'path':str(model)}),patch('hinglish_cut.gpu_lock.gpu_lock',side_effect=AssertionError('Cached timing must not wait for the model slot')),patch('hinglish_app.caption_audio_alignment.align_from_audio',side_effect=AssertionError('Cached timing must not reload the model')):
                execute(root,'e'*32)
            self.assertEqual(json.loads((again/'caption-project.json').read_text())['cues'],project['cues'])

if __name__=='__main__':unittest.main()
