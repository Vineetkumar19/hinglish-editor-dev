import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hinglish_app.caption_native_timing import align_words, validate_capture, execute, recognize


class NativeTimingTests(unittest.TestCase):
    def test_script_words_keep_actual_uneven_speech_onsets_and_silence(self):
        spoken=[{'text':t,'start':a,'end':b} for t,a,b in [('My',.5,.7),('fresh',.72,1.1),('IDEAS',1.12,1.6),('help',4.0,4.3),('people',4.4,5.0)]]
        result=align_words('My fresh ideas help people.',spoken,8)
        self.assertEqual([w['text'] for w in result], 'My fresh ideas help people.'.split())
        self.assertEqual([w['start'] for w in result],[.5,.72,1.12,4,4.4])
        self.assertEqual(result[-1]['end'],5)

    def test_wrong_script_missing_numbers_and_coarse_windows_cannot_be_labelled_speech_timing(self):
        for script,observed in [('Mumbai won 2009',[{'text':'Mumbai','start':1,'end':1.3},{'text':'won','start':1.4,'end':1.7},{'text':'2008','start':1.8,'end':2}]),('one two',[{'text':'one','start':0,'end':2},{'text':'two','start':0,'end':2}]),('one missing two',[{'text':'one','start':0,'end':.4},{'text':'two','start':1,'end':1.4}])]:
            with self.subTest(script=script), self.assertRaises(ValueError):align_words(script,observed,5)

    def test_capture_accepts_silent_gaps_but_rejects_speed_nested_audio_and_overlapping_narration(self):
        c={'host':'aftereffects','project_id':'p','sequence_id':'2','width':1080,'height':1920,'fps':30,'duration':8,'unsupported':[], 'clips':[{'path':'D:/narration.mp4','start':1,'end':4,'source_in':2,'kind':'video','stretch':100}]}
        scan=validate_capture(c)
        self.assertEqual(scan['audio'][0]['source_in'],2)
        self.assertEqual(scan['audio'][0]['start'],1)
        for change in [{'unsupported':['Nested narration']},{'clips':[{**c['clips'][0],'stretch':90}]},{'clips':c['clips']*2},{'duration':float('nan')}]:
            with self.subTest(change=change),self.assertRaises(ValueError):validate_capture({**c,**change})

    def test_extra_spoken_words_do_not_retime_matched_script_words(self):
        observed=[{'text':t,'start':i,'end':i+.4} for i,t in enumerate('hello um my friends'.split())]
        result=align_words('hello my friends',observed,6)
        self.assertEqual([w['start'] for w in result],[0,2,3])

    def test_compound_english_and_hindi_spellings_keep_their_actual_spoken_span(self):
        observed=[{'text':t,'start':i,'end':i+.4} for i,t in enumerate('my night life and kaimara work'.split())]
        result=align_words('My nightlife and camera work.',observed,8)
        self.assertEqual([w['text'] for w in result],['My','nightlife','and','camera','work.'])
        self.assertEqual((result[1]['start'],result[1]['end']),(1,2.4))
        self.assertEqual(result[3]['start'],4)

    def test_actual_live_hinglish_case_reconciles_token_splits_without_distributing_missing_words(self):
        from uroman import Uroman
        from hinglish_app.template_text_model import speech_normal
        fixture=json.loads(Path('tests/fixtures/caption-native-live-hinglish.json').read_text(encoding='utf8'));r=Uroman()
        words=align_words(fixture['script'],fixture['observed'],fixture['duration'],lambda s:speech_normal(r.romanize_string(s,lcode='hin')),allow_partial=True)
        self.assertGreaterEqual(len(words)/len(fixture['script'].split()),.9)
        self.assertIn('cafe',[w['text'] for w in words])
        self.assertEqual([w['text'] for w in words if w['text'].lower().startswith('nightlife')],['nightlife','Nightlife?'])
        spans={(w['start'],w['end']) for w in fixture['observed']}
        self.assertTrue(all((w['start'],w['end']) in spans or w.get('alignment')=='compound' for w in words))

    def test_saved_worker_runs_audio_only_maps_exact_script_and_reuses_timed_evidence(self):
        with tempfile.TemporaryDirectory(dir='output/caption-one-speech-sync-20261029') as tmp:
            root=Path(tmp).resolve();source=root/'narration.wav';source.write_bytes(b'audio fixture');model=root/'local-model';model.mkdir();calls=[]
            class Speech:
                def __init__(self,*args,**kw):
                    calls.append(kw);self.assertions=kw
                def transcribe(self,*args,**kw):
                    if kw.get('initial_prompt'):raise AssertionError('Script must not be hallucinated as a prompt')
                    assert kw['word_timestamps']
                    return iter([SimpleNamespace(end=5,words=[SimpleNamespace(word=t,start=a,end=b,probability=.98) for t,a,b in [('My',.5,.7),('ideas',3.1,3.6)]])]),None
            capture={'project_id':'p','sequence_id':'2','duration':8,'clips':[{'path':str(source),'start':0,'end':8,'source_in':0}],'unsupported':[]}
            modules={'faster_whisper':SimpleNamespace(WhisperModel=Speech),'uroman':SimpleNamespace(Uroman=lambda:SimpleNamespace(romanize_string=lambda text,**kw:text))}
            def decode(scan,dest):Path(dest).write_bytes(b'decoded fixture')
            with patch.dict('sys.modules',modules),patch('hinglish_cut.model_storage.configure'),patch('hinglish_app.caption_compute.options_for',return_value={'device':'cpu','compute_type':'int8'}),patch('hinglish_cut.model_storage.role',return_value={'path':str(model),'repo':'installed-local-speech','revision':'1'}),patch('hinglish_app.template_text_audio.decode_map',side_effect=decode) as decoded:
                for key in ('a'*32,'b'*32):
                    folder=root/'output/captions/ae-speech'/key;folder.mkdir(parents=True)
                    (folder/'request.json').write_text(json.dumps({'script':'My ideas.','timing_context':capture}))
                    execute(root,key)
                    project=json.loads((folder/'caption-project.json').read_text())
                    self.assertEqual([c['words'][0]['text'] for c in project['cues']],['My','ideas.'])
                    self.assertEqual([c['start'] for c in project['cues']],[.5,3.1])
                    self.assertEqual(project['transcription']['estimated_words'],0)
                    self.assertEqual(json.loads((folder/'status.json').read_text())['status'],'complete')
                self.assertEqual(decoded.call_count,1);self.assertEqual(len(calls),1)
                self.assertEqual(calls[0]['compute_type'],'int8');self.assertEqual(calls[0]['device'],'cpu')

    def test_recognizer_generator_is_closed_on_progress_failure(self):
        closed=[]
        class Speech:
            def __init__(self,*args,**kw):pass
            def transcribe(self,*args,**kw):
                def stream():
                    try:yield SimpleNamespace(end=1,words=[])
                    finally:closed.append(True)
                return stream(),None
        def stopped(*args):raise RuntimeError('fixture stopped')
        with self.assertRaises(RuntimeError):recognize(Speech,'local','audio.wav',3,stopped)
        self.assertEqual(closed,[True])

if __name__=='__main__':unittest.main()
