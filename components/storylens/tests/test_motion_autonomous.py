import copy
import unittest


class AutonomousMotionTests(unittest.TestCase):
    def test_model_feedback_reports_all_invalid_camera_coordinates_together(self):
        from tests.test_motion_student import MotionStudentTests
        from hinglish_motion.student_demo import compile_scene
        ref,answer=MotionStudentTests().fixture();answer['camera']['from']['x']=-900;answer['camera']['to']['y']=-2000
        with self.assertRaises(ValueError) as error:compile_scene(ref,answer)
        self.assertIn('camera.from.x',str(error.exception));self.assertIn('camera.to.y',str(error.exception))
    def test_fresh_reference_can_use_a_full_frame_camera_pan_without_rewriting_old_plans(self):
        from tests.test_motion_student import MotionStudentTests
        from hinglish_motion.student_demo import compile_scene
        ref,answer=MotionStudentTests().fixture();answer['camera']['to']['y']=-640
        with self.assertRaisesRegex(ValueError,'camera.*to.*y'):compile_scene(ref,answer)
        ref['local_reference_version']=1
        result=compile_scene(ref,answer)
        self.assertEqual(result['camera'][-1]['y'],-640)
    def test_measurement_resume_finds_later_accepted_attempt_before_new_inference(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import Mock,patch
        from hinglish_motion.autonomous_reference import measure_scene
        answer={'background':'#dddddd','background_edge':'#777777','background_style':'radial','grid':False,'motion_reading':'Photo rises.',
          'layers':[{'kind':'image','text':'','asset_kind':'person','mask':'remove_background','font':'sans','weight':700,'color':'#000000','x':120,'y':200,'w':220,'h':400,'size':40,'radius':0,'rotation':0,'source_time':.5,'motion':'drift'}]}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            root=Path(d)
            (root/'measured-scene-01-1.json').write_text(json.dumps({'answer':{**answer,'background':'gray'}}))
            (root/'measured-scene-01-2.json').write_text(json.dumps({'answer':answer,'accepted':True}))
            with patch('hinglish_motion.autonomous_reference.ask',side_effect=AssertionError('Do not redo completed source measurement')):
                recipe=measure_scene(Mock(),root,[],0.,2.,720,1280,0)
            self.assertEqual(recipe['layers'][0]['x'],120)
    def test_source_schema_constrains_colour_syntax_before_model_decoding(self):
        from hinglish_motion.autonomous_reference import scene_schema
        self.assertIn('pattern',scene_schema(0.,2.,720,1280)['properties']['background'])
    def test_reference_measurements_are_corrected_by_local_qwen_not_filled_by_code(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock,patch
        from hinglish_motion.autonomous_reference import measure_scene
        answer={'background':'#dddddd','background_edge':'#777777','background_style':'radial','grid':False,'motion_reading':'Photo rises.',
          'layers':[{'kind':'image','text':'','asset_kind':'person','mask':'remove_background','font':'sans','weight':700,'color':'#000000','x':120,'y':200,'w':220,'h':400,'size':40,'radius':0,'rotation':0,'source_time':.5,'motion':'drift'}]}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            brain=Mock();brain.name='local qwen'
            replies=iter([{**answer,'background':'gray'},answer])
            def reply(brain,folder,name,*args,**kwargs):
                import json
                result=next(replies);(folder/(name+'.json')).write_text(json.dumps({'answer':result}))
                return result
            with patch('hinglish_motion.autonomous_reference.ask',side_effect=reply) as ask:
                recipe=measure_scene(brain,Path(d),[{'local_vision':'independent source reading'}],0.,2.,720,1280,0)
            self.assertEqual(recipe['layers'][0]['source_box'],[120,200,340,600])
            self.assertEqual(ask.call_count,2)
            self.assertTrue(ask.call_args.args[4]['corrections'])
            self.assertTrue(ask.call_args.kwargs.get('think'))
    def test_local_scene_parser_failure_returns_feedback_to_qwen_and_keeps_receipt(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import Mock,patch
        from tests.test_motion_student import MotionStudentTests
        from hinglish_motion.student_demo import author_scene
        ref,answer=MotionStudentTests().fixture();ref['local_reference_version']=1
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            brain=Mock(name='brain');brain.name='local qwen'
            with patch('hinglish_motion.student_demo.ask',side_effect=[ValueError('incomplete JSON'),answer]) as ask:
                scene=author_scene(brain,Path(d),ref,1)
            self.assertEqual(scene['layers'][0]['x'],80.)
            self.assertIn('incomplete JSON',ask.call_args_list[1].args[4]['corrections'][0])
            error=json.loads((Path(d)/'qwen-scene-01-attempt-1-error.json').read_text())
            self.assertIn('incomplete JSON',error['error'])
            with patch('hinglish_motion.student_demo.ask',side_effect=[ValueError('incomplete JSON'),answer]):
                author_scene(brain,Path(d),ref,1)
            self.assertTrue((Path(d)/'qwen-scene-01-attempt-2-error.json').exists())

    def test_authorship_audit_ignores_error_sidecars_but_requires_actual_model_answer(self):
        import tempfile,json
        from pathlib import Path
        from tests.test_motion_student import MotionStudentTests
        from hinglish_motion.student_demo import compile_scene
        from tools.audit_motion_student import audit
        ref,answer=MotionStudentTests().fixture()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            root=Path(d);pack=root/'pack';pack.mkdir()
            (pack/'teacher-plan.json').write_text(json.dumps({'scenes':[ref]}))
            (root/'student-plan.json').write_text(json.dumps({'scenes':[compile_scene(ref,answer)]}))
            (root/'qwen-scene-01-attempt-1-error.json').write_text('{"error":"incomplete JSON"}')
            (root/'qwen-scene-01-attempt-2.json').write_text(json.dumps({'model':'qwen','answer':answer}))
            self.assertTrue(audit(root,pack)['all_rendered_scenes_match_local_model_receipts'])

    def test_only_accepted_vision_receipts_are_reused_and_failed_replies_are_preserved(self):
        import tempfile,json
        from pathlib import Path
        from hinglish_motion.autonomous_reference import vision_receipt,accept_vision
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            root=Path(d);first,cached=vision_receipt(root,'scene')
            self.assertIsNone(cached);first.write_text(json.dumps({'answer':{'layers':[]},'accepted':False}))
            retry,cached=vision_receipt(root,'scene');self.assertNotEqual(first,retry);self.assertTrue(first.exists());self.assertIsNone(cached)
            retry.write_text(json.dumps({'answer':{'layers':['valid']},'accepted':False}));accept_vision(retry)
            chosen,cached=vision_receipt(root,'scene');self.assertEqual(chosen,retry);self.assertEqual(cached,{'layers':['valid']})

    def test_reference_analysis_error_explains_saved_progress(self):
        from hinglish_app.user_messages import problem,catalog
        catalog.cache_clear();r=problem(RuntimeError('Local reference analysis invalid: image crop box outside the image.'),feature='Motion Graphics')
        self.assertEqual(r['code'],'motion_reference_analysis')
        self.assertIn('saved',r['message'].lower())
    def test_natural_reference_request_uses_one_local_file(self):
        from hinglish_app.assistant_motion_reference import request
        result=request('Recreate Motion Graphics from this reference: D:/My samples/new clip.mp4')
        self.assertEqual(result['reference'],'D:/My samples/new clip.mp4')
        self.assertIsNone(request('Explain how to make motion graphics'))

    def test_new_reference_submission_selects_automatic_local_pipeline(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock,patch
        from hinglish_app.assistant_motion_reference import execute
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            file=Path(d)/'reference.mp4';file.write_bytes(b'fixture')
            assistant=Mock();assistant.state.create_job.return_value={'id':'job'};assistant.state.snapshot.return_value={'id':'job','status':'complete','result':{'previews':[]}}
            execute(assistant,'session','Create Motion Graphics.\nReference: '+str(file),'general')
            self.assertIn('Local model reference: automatic',assistant.state.create_job.call_args.args[0]['script'])

    def test_model_cut_choices_cover_source_once_without_handwritten_scenes(self):
        from hinglish_motion.autonomous_reference import intervals
        self.assertEqual(intervals([2.,5.],8.1),[(0.,2.),(2.,5.),(5.,8.1)])
        for cuts in ([5.,2.],[0.,2.],[2.,9.],[float('nan')]):
            with self.subTest(cuts=cuts),self.assertRaises(ValueError):intervals(cuts,8.1)

    def test_recipe_geometry_and_source_words_come_from_local_vision(self):
        from hinglish_motion.autonomous_reference import recipe_from_vision
        answer={'background':'#ccc','background_style':'radial','background_edge':'#777777','grid':True,'motion_reading':'The image drifts while text reveals.',
          'layers':[{'kind':'text','text':'EXACT 123','asset_kind':'object','mask':'keep','font':'sans','weight':700,'color':'#ff1188','x':100.,'y':200.,'w':450.,'h':85.,'size':80.,'radius':0.,'rotation':0.,'source_time':1.,'motion':'drift'}]}
        result=recipe_from_vision(answer,0.,2.,720,1280)
        self.assertEqual(result['layers'][0]['text'],'EXACT 123')
        self.assertEqual(result['layers'][0]['x'],100.)
        self.assertEqual(result['background'],'#cccccc')
        self.assertTrue(result['enforce_reveal_deadlines'])
        invalid=copy.deepcopy(answer);invalid['layers'][0]['w']=-20
        with self.assertRaises(ValueError):recipe_from_vision(invalid,0.,2.,720,1280)

    def test_new_source_reveals_must_finish_but_old_saved_plans_stay_readable(self):
        from tests.test_motion_student import MotionStudentTests
        from hinglish_motion.student_demo import compile_scene
        ref,answer=MotionStudentTests().fixture();answer['layers']['word'].update(delay=1.2,stagger=.09)
        ref['layers'][0]['text']='A considerably longer support sentence'
        compile_scene(ref,answer)
        ref['enforce_reveal_deadlines']=True
        with self.assertRaisesRegex(ValueError,'reveal'):compile_scene(ref,answer)


if __name__=='__main__':unittest.main()
