import tempfile
import unittest
from pathlib import Path


class NativeTextTests(unittest.TestCase):
    def test_live_reference_request_reports_actual_running_stage(self):
        from unittest.mock import Mock,patch
        from hinglish_app.assistant_motion_reference import execute
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as directory:
            video=Path(directory)/'reference.mp4';video.write_bytes(b'fixture')
            assistant=Mock();assistant.state.create_job.return_value={'id':'example'}
            assistant.state.snapshot.side_effect=[{'id':'example','status':'running','stage':'Hyperframes rendering camera motion'},
                {'status':'complete','result':{'previews':[]}}]
            with patch('hinglish_app.assistant_motion_reference.time.sleep'):
                execute(assistant,'session','Create Motion Graphics.\nReference: '+str(video),'general')
            self.assertTrue(any(c.kwargs.get('stage')=='Hyperframes rendering camera motion' for c in assistant._update.call_args_list))

    def test_reference_motion_plan_contains_real_camera_and_independent_layer_travel(self):
        from hinglish_motion.reference_motion import compile_motion
        answer={'camera':'push-in','image_motion':'parallax-left','travel':.08,'light_sweep':True,'particles':16,'transition':'zoom-blur'}
        motion=compile_motion(answer,6.)
        self.assertNotEqual(motion['camera'][0]['scale'],motion['camera'][-1]['scale'])
        self.assertGreater(abs(motion['image']['x']),0)
        self.assertTrue(motion['light_sweep'])
        self.assertEqual(motion['camera'][-1]['time'],6.)
        with self.assertRaises(ValueError):compile_motion({**answer,'camera':'static'},6.)
        with self.assertRaises(ValueError):compile_motion({**answer,'travel':float('nan')},6.)

    def test_model_choices_cannot_skip_words_or_choose_invalid_main_ranges(self):
        from hinglish_motion.native_text import group_choices, schedule_choices
        words="You don't need motivation. You need discipline.".split()
        choices=group_choices(words,0)
        first=next(k for k,v in choices.items() if v=={'word_start':0,'word_count':4,'main_start':3,'main_count':1})
        self.assertIn('motivation.',first)
        second_choices=group_choices(words,4)
        second=next(k for k,v in second_choices.items() if v=={'word_start':4,'word_count':3,'main_start':2,'main_count':1})
        selected=[{**choices[first],'recipe':0,'effect':'text-stagger','hold_weight':2},
                  {**second_choices[second],'recipe':1,'effect':'soft-blur-in','hold_weight':1}]
        answer=schedule_choices(selected,7)
        self.assertEqual(answer['groups'][0]['start_fraction'],0)
        self.assertEqual(answer['groups'][0]['end_fraction'],answer['groups'][1]['start_fraction'])
        self.assertEqual(answer['groups'][-1]['end_fraction'],1)
        with self.assertRaises(ValueError):schedule_choices(selected[:-1],7)

    def test_native_groups_keep_all_words_and_reference_font_hierarchy(self):
        from hinglish_motion.native_text import compile_groups
        profiles=[{'support_font':'Bodoni','main_font':'Inter','support_size':.06,'main_size':.12,'ink_gap':8}]
        answer={'groups':[{'word_start':0,'word_count':4,'main_start':3,'main_count':1,'start_fraction':0.,'end_fraction':1.,'anchor_x':.5,'anchor_y':.35,'recipe':0,'effect':'bottom-up-letters'}]}
        result=compile_groups("You don't need motivation.".split(),answer,profiles,4.)
        self.assertEqual(result[0]['header'],"You don't need")
        self.assertEqual(result[0]['main'],'motivation.')
        self.assertEqual(result[0]['support_font'],'Bodoni');self.assertEqual(result[0]['main_font'],'Inter')
        self.assertEqual(result[0]['end'],4.)

    def test_missing_words_bad_recipe_and_reversed_timing_stop(self):
        from hinglish_motion.native_text import compile_groups
        profile=[{'support_font':'Bodoni','main_font':'Inter','support_size':.06,'main_size':.12,'ink_gap':8}]
        base={'word_start':0,'word_count':3,'main_start':2,'main_count':1,'start_fraction':0.,'end_fraction':1.,'anchor_x':.5,'anchor_y':.35,'recipe':0,'effect':'text-stagger'}
        for updates in ({'word_count':2},{'recipe':99},{'start_fraction':1.,'end_fraction':.5}):
            with self.subTest(updates=updates),self.assertRaises(ValueError):compile_groups(['Keep','every','word'],{'groups':[{**base,**updates}]},profile,4.)

    def test_bundle_uses_official_installed_hyperframes_fragments(self):
        from hinglish_motion.native_text import bundle
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            p=Path(directory);bundle(p)
            text=(p/'native-hyperframes.js').read_text('utf-8')
            self.assertIn('hf-bottom-up-letters-char',text)
            self.assertIn('hf-transition-text-stagger',text)
            self.assertTrue((p/'vendor/hyperframes/bottom-up-letters.html').is_file())

    def test_group_choices_keep_sentence_boundaries_and_content_emphasis(self):
        from hinglish_motion.native_text import group_choices
        words="You don't need motivation. You need discipline.".split()
        choices=group_choices(words,0)
        self.assertTrue(all(r['word_count']<=4 for r in choices.values()))
        self.assertFalse(any(r['main_start']==0 for r in choices.values()))
        self.assertIn("You don't need [motivation.]",choices)

    def test_native_word_spans_keep_measured_spaces_and_never_wrap(self):
        text=(Path(__file__).resolve().parents[1]/'hinglish_motion/web/native-text-binding.js').read_text('utf-8')
        self.assertIn("display:'inline-flex'",text)
        self.assertIn("flexWrap:'nowrap'",text)
        self.assertIn("measureText(' ').width",text)
