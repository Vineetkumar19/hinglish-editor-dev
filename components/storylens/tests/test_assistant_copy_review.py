import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from hinglish_publish.metadata import validate_source_copy,concise_youtube,normalize_youtube_hashtags,has_numerical_claim,generate_youtube
from hinglish_publish.store import fingerprint
from hinglish_app.server import AppState
from hinglish_app.assistant_copy_review import ensure


class CopyReviewTests(unittest.TestCase):
    def test_extra_model_hashtags_are_formatted_without_repeating_inference(self):
        value={'title':'RCB finals','description':'A story. #RCB #IPL #Cricket #Finals #History #Team #Sports','tags':['RCB']}
        result=normalize_youtube_hashtags(value)
        self.assertEqual(result['description'],'A story.\n\n#RCB #IPL #Cricket #Finals #History')
        self.assertEqual(value['description'].count('#'),7)
    def test_concise_local_fallback_returns_complete_copy_and_rejects_invented_numbers(self):
        from unittest.mock import Mock
        brain=Mock();brain.json.side_effect=[
            {'title':'RCB 2019 final','description':'A close final. #RCB #IPL #Cricket','tags':['RCB']},
            {'title':'RCB finals heartbreak','description':'A look back at RCB’s promising starts and batting struggles in decisive matches. #RCB #IPL #Cricket','tags':['RCB']}]
        result=concise_youtube(brain,'Do hazaar nau mein RCB final haar gai.',lambda _:None)
        self.assertTrue(result['description']);self.assertEqual(brain.json.call_count,2)
        self.assertNotIn('think',brain.json.call_args.kwargs)

    def test_spoken_years_constrain_title_description_and_hashtags(self):
        speech='Do hazaar nau aur do hazaar solah mein RCB final haar gai.'
        validate_source_copy({'title':'RCB finals','description':'2009 and 2016 #IPL2009','tags':[]},speech)
        with self.assertRaisesRegex(ValueError,'unsupported years'):
            validate_source_copy({'title':'RCB finals','description':'RCB #IPL2019 #IPL2020','tags':[]},speech)
        with self.assertRaisesRegex(ValueError,'editorial commentary'):
            validate_source_copy({'description':'The transcript highlights cricket.','tags':[]},speech)

    def test_t20_format_identifiers_do_not_reject_a_complete_fallback(self):
        from unittest.mock import Mock
        brain=Mock();brain.json.return_value={
            'title':'Mumbai Indians and Chennai Super Kings in a T20 final',
            'description':'A look back at the bowling and batting contest. #Cricket #MumbaiIndians #T20Final',
            'tags':['T20Final','Cricket','MumbaiIndians']}
        result=concise_youtube(brain,'Mumbai Indians CSK ka final match.',lambda _:None)
        self.assertIn('#T20Final',result['description']);brain.json.assert_called_once()
        for text in ('T20','T20I cricket','#T20Final #U19WorldCup'):
            self.assertFalse(has_numerical_claim(text),text)
        for text in ('2013 final','#IPL2013','125 runs','T2013','U191','1Y48','T20 final 60 not out'):
            self.assertTrue(has_numerical_claim(text),text)

    def test_copy_failure_reports_actual_reason_instead_of_generic_model_error(self):
        from unittest.mock import Mock
        brain=Mock();brain.json.return_value={'title':'Cricket','description':'','tags':['Cricket']}
        with self.assertRaisesRegex(RuntimeError,'Publishing copy needs review: description is empty'):
            concise_youtube(brain,'Cricket.',lambda _:None)

    def test_youtube_copy_recovers_malformed_answer_and_logs_rejection_without_media_work(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=root/'clip.mp4'
            video.with_suffix('.txt').write_text('Mumbai Indians CSK ka final match.','utf-8')
            brain=Mock();brain.name='local fixture'
            brain.json.side_effect=[ValueError('Malformed JSON'),{
                'title':'Mumbai Indians and Chennai Super Kings',
                'description':'A look back at a T20 contest. #Cricket #MumbaiIndians #T20Final',
                'tags':['Cricket','MumbaiIndians','T20Final']}]
            with patch('hinglish_visuals.brain.open_brain',return_value=brain):
                value,name=generate_youtube(root,video,progress=lambda _:None)
            self.assertIn('#T20Final',value['description']);self.assertEqual(name,'local fixture')
            self.assertEqual(brain.json.call_count,2)
            report=__import__('json').loads(next((root/'cache/publisher/copy-review').glob('*.json')).read_text('utf-8'))
            self.assertEqual(report['events'][0]['error'],'Malformed JSON')
            self.assertEqual(report['events'][-1]['stage'],'youtube_accepted')
            self.assertFalse(video.exists());self.assertFalse(video.with_suffix('.copy-review.json').exists())

    def test_two_failed_main_drafts_can_recover_through_t20_fallback_without_uploading(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=root/'short.mp4';video.with_suffix('.txt').write_text('Mumbai aur CSK ka final.','utf-8')
            bad={'title':'IPL 2019 final','description':'A match. #Cricket #IPL2019 #MumbaiIndians','tags':['Cricket']}
            good={'title':'Mumbai and CSK final','description':'A T20 match. #Cricket #MumbaiIndians #T20Final','tags':['Cricket','T20Final']}
            brain=Mock();brain.name='local fixture';brain.json.side_effect=[bad,bad,good]
            with patch('hinglish_visuals.brain.open_brain',return_value=brain):
                value,_=generate_youtube(root,video,progress=lambda _:None)
            self.assertIn('#T20Final',value['description']);self.assertEqual(brain.json.call_count,3)

    def test_local_repair_updates_the_same_draft_before_upload_without_selecting_another_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=AppState(root);a=state.assistant;sid=a.create()['id']
            video=root/'clip.mp4';video.write_bytes(b'video');video.with_suffix('.txt').write_text('Do hazaar nau mein final haar gai.')
            bad={'title':'RCB 2019 final','description':'The transcript highlights 2019. #RCB #IPL #Cricket','tags':[],'instagram_caption':'RCB final'}
            job_id=state.publisher.store.add_batch([{'video':str(video),'fingerprint':fingerprint(video),
                'profile':'gaming','platform':'youtube','kind':'short','metadata':bad,'visibility':'private'}])[0]
            review={'rows':[{'id':job_id,'metadata':bad}]}
            correct={**bad,'title':'RCB finals heartbreak','description':'RCB in the 2009 final. #RCB #IPL #Cricket'}
            with patch('hinglish_publish.metadata.generate_youtube',return_value=(correct,'local14b')) as generate:
                result=ensure(a,sid,review,state.publisher.store.get(job_id))
                result=ensure(a,sid,review,result)
            self.assertEqual(result['id'],job_id);self.assertEqual(result['video'],str(video))
            self.assertEqual(result['metadata'],correct);self.assertEqual(review['rows'][0]['metadata'],correct)
            self.assertEqual(generate.call_count,1);self.assertFalse(result['remote'])


if __name__=='__main__':unittest.main()
