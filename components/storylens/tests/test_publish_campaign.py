from datetime import datetime
import unittest
from hinglish_publish.campaign import IST, slots, valid_picks


class CampaignTests(unittest.TestCase):
    def test_romanized_hinglish_and_non_mumbai_subjects_have_boundary_options(self):
        from hinglish_cut.model import Word
        from hinglish_publish.campaign_boundaries import candidates
        words=[Word('Kolkata',0,.5),Word('Gambhir',1,1.5),Word('jeet',5,5.5),
               Word('gayi.',11,11.5),Word('Narine',12,12.5),Word('wicket',17,17.5),Word('liya.',23,23.5)]
        first={'pieces':[[0,11.8]]}
        future={'pieces':[[11.88,23.8]]}
        options=candidates(words,first,24,60,reserved=[future])
        self.assertTrue(options)
        self.assertTrue(any(c['original_moment'] for c in options))
        for option in options:
            valid_picks([{'pieces':[[option['start'],option['end']]]},future],24,60)

    def test_punctuation_without_known_verb_or_team_retains_local_original_choice(self):
        from hinglish_cut.model import Word
        from hinglish_publish.campaign_boundaries import candidates
        words=[Word('Unexpected',.1,.4),Word('team',1,1.4),Word('wins!',11,11.4)]
        options=candidates(words,{'pieces':[[0,11.7]]},12,60,maximum=1)
        self.assertEqual(len(options),1)
        self.assertTrue(options[0]['original_moment'])
        self.assertGreaterEqual(options[0]['end'],words[-1].end)

    def test_new_campaign_replaces_old_targets_and_keeps_only_user_corrections(self):
        from hinglish_app.assistant_campaign import active_turns
        old='Extract seven Shorts and schedule on Fantasy Legends.'
        new='Extract seven Shorts and schedule on my gaming channel only.'
        correction='Upload in the gaming channel only. I will fix that later. Do not worry now.'
        history={'messages':[{'role':'user','text':old},
            {'role':'assistant','text':'Your Fantasy Legends campaign is complete.'},
            {'role':'user','text':new},
            {'role':'assistant','text':'Did you want Fantasy Legends or gaming?'},
            {'role':'user','text':correction}]}
        self.assertEqual(active_turns(history,correction),[new,correction])
        self.assertEqual(active_turns(history,'gaming channel (Vineet Kumar)'),
                         [new,correction,'gaming channel (Vineet Kumar)'])

    def test_actual_planner_prompt_cannot_reuse_old_assistant_claims(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from hinglish_app.assistant_campaign import plan_with_model
        answer={'action':'prepare','reply':'Preparing for gaming; public scheduling needs Studio.',
                'question':'','source_folder_id':0,'source_topic':'cricket','targets':['gaming'],
                'first_date':'2030-10-20','clock':'18:00','count':7,
                'max_seconds_exclusive':60,'different_source':True}
        invalid={**answer,'clock':'2030-10-19T11:24:00+05:30'}
        recorder=SimpleNamespace(json=Mock(side_effect=[invalid,answer]))
        evidence={'folders':[],'accounts':[],'capabilities':{},'previous_sources':['old.mp4']}
        turns=['Extract seven cricket Shorts and schedule on gaming at 6 p.m.', 'Gaming only.']
        result=plan_with_model(recorder,turns,evidence,'2030-10-19T11:24:00+05:30',lambda _:None)
        self.assertEqual(result,answer)
        second_input=recorder.json.call_args.args[1]
        self.assertEqual(second_input['latest_instruction'],'Gaming only.')
        self.assertEqual(second_input['user_turns'],turns)
        self.assertIn('validation_error',second_input)
        self.assertNotIn('history',second_input)

    def test_model_is_asked_to_correct_requests_for_user_written_metadata(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from hinglish_app.assistant_campaign import plan_with_model
        answer={'action':'prepare','reply':'I will provide titles and descriptions from the footage.',
                'question':'','source_folder_id':0,'source_topic':'cricket','targets':['gaming'],
                'first_date':'2030-10-20','clock':'18:00','count':7,
                'max_seconds_exclusive':60,'different_source':True}
        bad={**answer,'reply':'Please provide the title and description for the upload.'}
        recorder=SimpleNamespace(json=Mock(side_effect=[bad,answer]))
        result=plan_with_model(recorder,['Extract seven Shorts with title and description.'],
            {'folders':[],'accounts':[],'capabilities':{},'previous_sources':[]},
            '2030-10-19T12:00:00+05:30',lambda _:None)
        self.assertEqual(result,answer)
        self.assertIn('generates titles',recorder.json.call_args.args[1]['validation_error'])

    def test_chat_route_leaves_semantic_decisions_to_local_model(self):
        from hinglish_app.assistant_campaign import requested
        self.assertTrue(requested('Extract seven cricket Shorts and schedule every day on YouTube'))
        self.assertTrue(requested('How do I schedule cricket Shorts?'))
        self.assertTrue(requested('Do not schedule cricket clips'))
        self.assertFalse(requested('Upload a private YouTube video'))
        self.assertTrue(requested('Create daily YouTube Shorts from my gaming stream'))
        self.assertTrue(requested('Extract seven cricket Shorts, schedule on Fantasy Legends and upload on my gaming channel'))

    def test_plan_only_does_not_write_copy_or_render_the_initial_candidates(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch,Mock
        from hinglish_publish.campaign import prepare
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/'sources'
            source.mkdir()
            video=source/'source.mp4'
            video.write_bytes(b'fixture')
            folder=root/'campaign'
            folder.mkdir()
            (folder/'campaign.json').write_text(json.dumps({'source_root':str(source.resolve()),
                'source':str(video),'source_fingerprint':'fixture','clips':[], 'status':'preparing',
                'start_date':'2030-01-01','clock':'18:00',
                'picks':[{'title':'A complete cricket moment','pieces':[[0,30]],'text':'Actual speech'}]}),'utf-8')
            (folder/'words.json').write_text('[]','utf-8')
            brain=SimpleNamespace(name='Local fixture',json=Mock(),close=Mock())
            with patch('hinglish_cut.gpu_lock.gpu_lock'), \
                 patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(duration=120)), \
                 patch('hinglish_shorts.source.quick_fingerprint',return_value='fixture'), \
                 patch('hinglish_visuals.brain.open_brain',return_value=brain), \
                 patch('hinglish_publish.campaign.render') as encoder, \
                 patch('hinglish_publish.campaign.slots',return_value=['2030-01-01T18:00:00+05:30']):
                result=prepare(root,source,folder,progress=lambda _:None,plan_only=True)
            encoder.assert_not_called()
            brain.json.assert_not_called()
            self.assertEqual(result['status'],'planned')
            self.assertFalse((folder/'short-01.mp4').exists())
    def test_exact_daily_ist_slots(self):
        result=slots(7,now=datetime(2026,10,19,10,tzinfo=IST))
        self.assertEqual(result[0],'2026-10-19T18:00:00+05:30')
        self.assertEqual(result[-1],'2026-10-25T18:00:00+05:30')

    def test_no_silent_past_date_repair(self):
        with self.assertRaises(ValueError):
            slots(7,now=datetime(2026,10,19,19,tzinfo=IST))

    def test_strict_fifty_second_limit(self):
        for pieces in ([[0,50]],[[0,51]],[[0,100]],[[10,9]],[[0,9],[8,10]]):
            with self.assertRaises(ValueError):
                valid_picks([{'pieces':pieces}],100)
        self.assertEqual(len(valid_picks([{'pieces':[[0,49.99]]}],100)),1)

    def test_no_repeated_footage(self):
        with self.assertRaises(ValueError):
            valid_picks([{'pieces':[[1,22]]},{'pieces':[[20,45]]}],100)
        self.assertEqual(len(valid_picks([{'pieces':[[1,22]]},{'pieces':[[22,45]]}],100)),2)

    def test_user_duration_cap_is_enforced_without_silently_reverting_to_fifty(self):
        self.assertEqual(len(valid_picks([{'pieces':[[0,59.9]]}],100,60)),1)
        with self.assertRaises(ValueError):
            valid_picks([{'pieces':[[0,60]]}],100,60)

    def test_word_refinement_keeps_precise_eof_and_skips_reversed_candidates(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch,Mock
        from hinglish_publish.campaign import word_refine
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            video=folder/'short-01.mp4'
            video.write_bytes(b'fixture')
            duration=15.1266666667
            (folder/'words.json').write_text(json.dumps([
                {'text':'है','start':0,'end':.2},
                {'text':'मुंबई','start':1,'end':1.5},
                {'text':'जीती','start':14.8,'end':15.12}]),'utf-8')
            (folder/'campaign.json').write_text(json.dumps({'source':'source.mp4','clips':[
                {'index':1,'video':str(video),'pick':{'title':'Team victory','pieces':[[1,15.12]]}}]}),'utf-8')
            def choose(system,data,schema,**options):
                if 'candidates' in data:
                    return {'candidate_id':data['candidates'][0]['id'],'title':'Team victory','why':'Complete result'}
                return {'title':'Team victory','description':'A completed team victory. #Cricket #IPL #History',
                        'tags':['Cricket'],'instagram_caption':'A completed team victory.'}
            brain=SimpleNamespace(name='Local fixture',json=Mock(side_effect=choose),close=Mock())
            rendered=[]
            with patch('hinglish_cut.gpu_lock.gpu_lock'), \
                 patch('hinglish_cut.model_preferences.release_ollama'), \
                 patch('hinglish_visuals.brain.open_brain',return_value=brain), \
                 patch('hinglish_publish.campaign.render',side_effect=lambda v,p,t,cb:rendered.append(p)), \
                 patch('hinglish_publish.store.fingerprint',return_value='fixture'), \
                 patch('hinglish_shorts.source.open_video',side_effect=lambda p:SimpleNamespace(
                     duration=duration if str(p)=='source.mp4' else rendered[-1]['duration'],width=1080,height=1920)):
                result=word_refine(folder,folder,lambda _:None)
            pick=result['clips'][0]['pick']
            self.assertEqual(pick['pieces'][0][1],duration)
            self.assertGreaterEqual(pick['pieces'][0][1],15.12)
            valid_picks([pick],duration)
            self.assertEqual(len(rendered),1)

    def test_different_source_is_removed_before_local_model_selection(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch,Mock
        from hinglish_publish.campaign import prepare
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/'library'
            source.mkdir()
            previous=source/'previous.mp4'
            new=source/'new.mp4'
            previous.write_bytes(b'old')
            new.write_bytes(b'new')
            choice=Mock(return_value={'id':0,'reason':'Local model choice'})
            brain=SimpleNamespace(name='Local fixture',json=choice,close=Mock())
            pick=SimpleNamespace(duration=55,to_dict=lambda:{'pieces':[[0,55]],'title':'Story','text':'Words'})
            spec={'count':7,'first_date':'2030-01-01','clock':'18:00',
                  'excluded_sources':[str(previous)],'max_seconds_exclusive':60,
                  'targets':[{'profile':'gaming','id':'gaming-channel'}]}
            with patch('hinglish_cut.gpu_lock.gpu_lock'), \
                 patch('hinglish_cut.model_preferences.release_ollama'), \
                 patch('hinglish_shorts.source.open_video',side_effect=lambda p:SimpleNamespace(duration=600,width=1920,height=1080)), \
                 patch('hinglish_shorts.source.quick_fingerprint',return_value='fixture'), \
                 patch('hinglish_shorts.source.transcribe',return_value=[]), \
                 patch('hinglish_visuals.brain.open_brain',return_value=brain), \
                 patch('hinglish_shorts.find.find_shorts',return_value=([pick],'summary',{})), \
                 patch('hinglish_publish.campaign.render') as encoder:
                result=prepare(root,source,root/'campaign',lambda _:None,spec,plan_only=True)
            inventory=choice.call_args.args[1]['inventory']
            self.assertEqual([i['name'] for i in inventory],['new.mp4'])
            self.assertEqual(result['source'],str(new.resolve()))
            self.assertEqual(result['channel_id'],'gaming-channel')
            self.assertEqual(result['max_seconds_exclusive'],60)
            encoder.assert_not_called()


if __name__=='__main__':
    unittest.main()
