import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from hinglish_captions.proofread import review
from hinglish_captions.audio_evidence import collect,suspicious
from hinglish_captions.numbers import digits
from hinglish_cut.model import Word


def words(text):return [Word(t,i*.25,i*.25+.2) for i,t in enumerate(text.split())]


class CricketCaptionReviewTests(unittest.TestCase):
    def test_valid_singular_plural_cricket_terms_and_roman_spellings_are_preserved(self):
        def model(system,data,schema,**kwargs):
            if 'entities' in schema['properties']:return {'entities':[]}
            if 'accepted_ids' in schema['properties']:
                self.assertFalse(any(r['original'] in ('wicket','wickets','kaafi') for r in data['candidates']))
                return {'accepted_ids':[]}
            return {'corrections':[{'index':0,'before':'wicket','after':'wickets'},
                {'index':2,'before':'kaafi','after':'kaaphi'}],'spans':[]}
        brain=Mock();brain.json.side_effect=model
        result,_=review(brain,words('wicket aur kaafi wickets'),lambda _:None)
        self.assertEqual(' '.join(w.text for w in result),'wicket aur kaafi wickets')

    def test_name_spans_cannot_consume_adjacent_hindi_words(self):
        def model(system,data,schema,**kwargs):
            if 'entities' in schema['properties']:return {'entities':['Punjab Kings','Reddimaan Saha']}
            if 'accepted_ids' in schema['properties']:
                self.assertFalse(any(r['original'] in ('kahin Punjab Kings','Punjab Kings ki','mein reddimaan saha')
                                     for r in data['candidates']))
                return {'accepted_ids':[]}
            return {'corrections':[],'spans':[{'start_index':0,'end_index':2,
                'before':'kahin Punjab Kings','after':'Punjab Kings','kind':'entity','evidence_quote':''}]}
        brain=Mock();brain.json.side_effect=model
        original=words('kahin Punjab Kings ki brand value aur mein reddimaan saha')
        result,_=review(brain,original,lambda _:None)
        self.assertEqual(' '.join(w.text for w in result),' '.join(w.text for w in original))

    def test_split_surname_from_live_dc_transcript_preserves_span_timing(self):
        def model(system,data,schema,**kwargs):
            if 'entities' in schema['properties']:return {'entities':[]}
            if 'accepted_ids' in schema['properties']:
                return {'accepted_ids':[r['id'] for r in data['candidates']
                    if r['original']=='sachin taankul kar' and r['proposed']=='Sachin Tendulkar']}
            return {'corrections':[],'spans':[]}
        brain=Mock();brain.json.side_effect=model
        original=words('sachin taankul kar bhi kah sakte ho')
        result,changes=review(brain,original,lambda _:None)
        self.assertEqual(' '.join(w.text for w in result),'Sachin Tendulkar bhi kah sakte ho')
        self.assertEqual(result[0].start,original[0].start)
        self.assertEqual(result[1].end,original[2].end)
        self.assertEqual(len(changes),1)

    def test_expanded_cricket_vocabulary_checks_terms_and_preserves_valid_names(self):
        def model(system,data,schema,**kwargs):
            if 'entities' in schema['properties']:return {'entities':[]}
            if 'accepted_ids' in schema['properties']:
                self.assertFalse(any(r['original']=='David Hussey' and r['proposed']!='David Hussey' for r in data['candidates']))
                return {'accepted_ids':[r['id'] for r in data['candidates']
                    if (r['original'],r['proposed']) in {('Kolkatta Knight Riders','Kolkata Knight Riders'),('wickett','wicket')}]}
            self.assertIn('leg before wicket',data['reference_spellings']['cricket_terms'])
            return {'corrections':[],'spans':[]}
        brain=Mock();brain.json.side_effect=model
        result,changes=review(brain,words('Kolkatta Knight Riders ne David Hussey ka wickett liya'),lambda _:None)
        self.assertEqual(' '.join(w.text for w in result),'Kolkata Knight Riders ne David Hussey ka wicket liya')
        self.assertEqual(len(changes),2)

    def test_local_model_knowledge_can_supply_a_name_absent_from_saved_creator_examples(self):
        def model(system,data,schema,**kwargs):
            if 'entities' in schema['properties']:return {'entities':['Gautam Gambhir','Unrelated Famous Player']}
            if 'accepted_ids' in schema['properties']:
                return {'accepted_ids':[r['id'] for r in data['candidates'] if r['proposed']=='Gautam Gambhir']}
            return {'corrections':[],'spans':[]}
        brain=Mock();brain.json.side_effect=model
        result,changes=review(brain,words('Goutam Gambhir ne IPL mein captaincy ki'),lambda _:None)
        self.assertEqual(' '.join(w.text for w in result),'Gautam Gambhir ne IPL mein captaincy ki')
        self.assertEqual(len(changes),1)

    def test_local_model_selects_ids_and_only_selected_corrections_are_applied(self):
        def choose(system,data,schema,**kwargs):
            if 'accepted_ids' in schema['properties']:
                return {'accepted_ids':[r['id'] for r in data['candidates'] if r['proposed']=='Kieron Pollard']}
            return {'corrections':[],'spans':[]}
        brain=Mock();brain.json.side_effect=choose
        result,changes=review(brain,words('Karen Pollard aur Mumbai Indies'),lambda _:None)
        self.assertEqual(' '.join(w.text for w in result),'Kieron Pollard aur Mumbai Indies')
        self.assertEqual(len(changes),1);self.assertIn('local_candidate_id',changes[0])

    def test_invalid_or_conflicting_candidate_choices_cannot_be_applied(self):
        brain=Mock();brain.json.return_value={'accepted_ids':['invented']}
        with self.assertRaisesRegex(ValueError,'invalid correction IDs'):
            review(brain,words('Karen Pollard'),lambda _:None)
        def ambiguous(system,data,schema,**kwargs):return {'accepted_ids':[r['id'] for r in data['candidates']]}
        brain.json.side_effect=ambiguous
        evidence=[{'start':0,'end':2,'transcript':'148 aur 125 runs','supported_digits':['148','125']}]
        with self.assertRaisesRegex(ValueError,'conflicting caption corrections'):
            review(brain,words('01Y48 runs'),lambda _:None,evidence=evidence)

    def test_local_entity_span_can_correct_all_creator_reported_names(self):
        for before,after in [('Mumbai Indies','Mumbai Indians'),('Karen Pollard','Kieron Pollard'),
                             ('Michael Kessy','Michael Hussey'),('Michael Heslip','Michael Hussey')]:
            brain=Mock();brain.json.return_value={'corrections':[],'spans':[{
                'start_index':0,'end_index':1,'before':before,'after':after,'kind':'entity','evidence_quote':''}]}
            original=words(before+' ne khela')
            result,changes=review(brain,original,lambda _:None)
            with self.subTest(before=before):
                self.assertEqual(' '.join(w.text for w in result),after+' ne khela')
                self.assertEqual(len(changes),1)
                self.assertEqual((result[0].start,result[1].end),(original[0].start,original[1].end))
                self.assertEqual([(w.start,w.end) for w in result],[(w.start,w.end) for w in original])
                self.assertEqual(original[0].text,before.split()[0])
                self.assertIn(after,brain.json.call_args.args[1]['reference_spellings']['cricket_entities'])

    def test_model_can_fix_roman_hindi_without_translating(self):
        brain=Mock();brain.json.return_value={'corrections':[{'index':0,'before':'Kaphii','after':'kaafi'}],'spans':[]}
        result,_=review(brain,words('Kaphii achha khela'),lambda _:None)
        self.assertEqual([w.text for w in result],['kaafi','achha','khela'])

    def test_invalid_json_review_retries_before_retaining_original_speech(self):
        calls=[]
        def model(system,data,schema,**kwargs):
            if 'entities' in schema['properties']:return {'entities':[]}
            if 'accepted_ids' in schema['properties']:return {'accepted_ids':[]}
            calls.append(dict(data))
            if len(calls)==1:raise ValueError('Incomplete JSON')
            return {'corrections':[{'index':0,'before':'Kaphii','after':'kaafi'}],'spans':[]}
        brain=Mock();brain.json.side_effect=model
        result,_=review(brain,words('Kaphii achha khela'),lambda _:None)
        self.assertEqual([w.text for w in result],['kaafi','achha','khela'])
        self.assertEqual(len(calls),2)
        self.assertIn('validation_error',calls[1])

    def test_scores_require_local_independent_audio_evidence_not_historical_guesses(self):
        for heard,correct,quote in [('01Y48','148','एक सौ अड़तालीस'),('0125','125','एक सौ पच्चीस')]:
            brain=Mock();brain.json.return_value={'corrections':[],'spans':[{
                'start_index':0,'end_index':0,'before':heard,'after':correct,'kind':'number','evidence_quote':quote}]}
            evidence=[{'start':0,'end':2,'transcript':quote+' रन बनाए','supported_digits':[correct]}]
            fixed,_=review(brain,words(heard+' runs banaye'),lambda _:None,evidence=evidence)
            self.assertEqual(fixed[0].text,correct)
            with self.assertRaisesRegex(ValueError,'could not verify a malformed score'):
                review(brain,words(heard+' runs banaye'),lambda _:None)
            with self.assertRaisesRegex(ValueError,'could not verify a malformed score'):
                review(brain,words(heard+' runs banaye'),lambda _:None,evidence=[{**evidence[0],'supported_digits':['99']}])

    def test_fifth_and_compound_ordinals_are_digits_and_second_can_remain_a_time_unit(self):
        for before,after in [('fifth position','5th position'),('twenty-first, place','21st, place'),
                             ('one second','1 second'),('second position','2nd position')]:
            self.assertEqual(' '.join(w.text for w in digits(words(before))),after)
        for token in ('01Y48','0125','1Y48'):self.assertTrue(suspicious(token))
        for token in ('125','148','5th','T20','T20I','U19','IPL2013','3D','H264'):self.assertFalse(suspicious(token))
        self.assertEqual(' '.join(w.text for w in digits(words('१४८ रन'))),'148 रन')
        brain=Mock();brain.json.return_value={'corrections':[{'index':0,'before':'fifth','after':'fifty'}],'spans':[]}
        reviewed,_=review(brain,words('fifth position'),lambda _:None)
        self.assertEqual(' '.join(w.text for w in digits(reviewed)),'5th position')

    def test_audio_window_decoder_preserves_real_signal_at_requested_time(self):
        import numpy as np
        from tests.test_shorts import make_video
        from hinglish_shorts.source import open_video
        from hinglish_captions.audio_evidence import clip_audio
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'synthetic-tone.mp4';make_video(source,seconds=3,size=(64,64))
            audio=clip_audio(open_video(source),1,2)
        self.assertEqual(len(audio),16000)
        self.assertTrue(np.isfinite(audio).all())
        self.assertGreater(float(np.sqrt(np.mean(audio**2))),.03)

    def test_reference_names_do_not_authorize_replacing_an_unrelated_subject(self):
        for original in ('Different person','Michael Jordan'):
            brain=Mock();brain.json.return_value={'corrections':[],'spans':[{
                'start_index':0,'end_index':1,'before':original,'after':'Michael Hussey','kind':'entity','evidence_quote':''}]}
            result,changes=review(brain,words(original+' khela'),lambda _:None)
            self.assertEqual(' '.join(w.text for w in result),original+' khela');self.assertFalse(changes)

    def test_audio_checker_is_local_unprompted_and_cached_without_decoding_whole_video(self):
        import sys
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=SimpleNamespace(path=str(root/'source.mp4'),duration=60,video_start=0)
            engine=Mock();engine.transcribe.return_value=([SimpleNamespace(text='एक सौ अड़तालीस रन बनाए')],None)
            constructor=Mock(return_value=engine)
            with patch.dict(sys.modules,{'faster_whisper':SimpleNamespace(WhisperModel=constructor)}),\
                 patch('hinglish_cut.model_storage.role',return_value={'path':'installed-local-model','repo':'local-independent-asr'}),\
                 patch('hinglish_cut.model_storage.configure'),\
                 patch('hinglish_cut.model_preferences.release_ollama'),\
                 patch('hinglish_cut.model_preferences.preferred_device',return_value='cpu'),\
                 patch('hinglish_shorts.source.quick_fingerprint',return_value='unchanged-source'),\
                 patch('hinglish_captions.audio_evidence.clip_audio',return_value='audio-window') as decode:
                first=collect(root,video,words('01Y48 runs'),[(0,1)],lambda _:None)
                second=collect(root,video,words('01Y48 runs'),[(0,1)],lambda _:None)
            self.assertEqual(first,second);self.assertIn('148',first[0]['supported_digits'])
            constructor.assert_called_once();decode.assert_called_once()
            self.assertTrue(constructor.call_args.kwargs['local_files_only'])
            self.assertNotIn('initial_prompt',engine.transcribe.call_args.kwargs)
            self.assertLess(decode.call_args.args[2]-decode.call_args.args[1],6)


if __name__=='__main__':unittest.main()
