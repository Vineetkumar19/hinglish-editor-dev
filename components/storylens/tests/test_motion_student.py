import copy
import unittest


class MotionStudentTests(unittest.TestCase):
    def test_failed_student_plan_uses_actionable_shared_error(self):
        from hinglish_app.user_messages import problem,catalog
        catalog.cache_clear()
        result=problem(RuntimeError('Local Qwen could not create a valid scene after its correction: bad camera units'),feature='Motion graphics')
        self.assertEqual(result['code'],'motion_student_plan')
        self.assertIn('saved',result['message'].lower())

    def fixture(self):
        reference={'id':'ideas','start':0.,'end':2.,'background':'#ffffff','camera':[{'time':0.,'scale':1.6,'x':0.,'y':0.},{'time':2.,'scale':1.,'x':0.,'y':0.}],
          'mode3d':'blackhole','layers':[{'id':'word','kind':'text','text':'Ideas','x':10,'y':20,'w':300,'size':80,'color':'#009f9d'}]}
        answer={'background':'#ffffff','entrance':'none','exit':'none',
          'camera':{'from':{'scale':1.2,'x':0.,'y':0.,'rotation':0.},'via':{'scale':1.1,'x':8.,'y':-3.,'rotation':.5},'to':{'scale':1.,'x':15.,'y':-8.,'rotation':1.},'middle_phase':.3},
          'layers':{'word':{'x':80.,'y':240.,'w':450.,'size':90.,'color':'#008f91','weight':700,'rotation':-2.,'opacity':1.,'delay':.1,'reveal':'characters','stagger':.03,'drift':[4.,-8.,12.]}},
          'world':{'camera_z_from':9.,'camera_z_to':8.,'camera_x_from':0.,'camera_x_to':.1,'plate_scale_from':1.,'plate_scale_to':1.1,'debris_speed':.7,'pose_scale':1.}}
        return reference,answer

    def test_uses_actual_model_geometry_without_teacher_design_backfill(self):
        from hinglish_motion.student_demo import compile_scene
        reference,answer=self.fixture();before=copy.deepcopy(reference);scene=compile_scene(reference,answer)
        self.assertEqual(scene['layers'][0]['text'],'Ideas')
        self.assertEqual(scene['layers'][0]['x'],80.)
        self.assertEqual(scene['camera'][0],{'time':0.,**answer['camera']['from']})
        self.assertEqual(scene['camera'][-1],{'time':2.,**answer['camera']['to']})
        self.assertEqual(scene['camera'][1]['time'],.6)
        self.assertEqual(scene['world'],answer['world'])
        self.assertEqual(reference,before)

    def test_missing_bad_or_static_model_output_stops_instead_of_falling_back(self):
        from hinglish_motion.student_demo import compile_scene
        ref,answer=self.fixture()
        cases=[]
        a=copy.deepcopy(answer);del a['layers']['word']['x'];cases.append(a)
        a=copy.deepcopy(answer);a['layers']['word']['w']=-1;cases.append(a)
        a=copy.deepcopy(answer);a['layers']['word']['color']='red;position:fixed';cases.append(a)
        a=copy.deepcopy(answer);a['layers']['word']['x']=float('nan');cases.append(a)
        a=copy.deepcopy(answer);a['camera']['middle_phase']=1.5;cases.append(a)
        for a in cases:
            with self.subTest(answer=a),self.assertRaises(ValueError):compile_scene(ref,a)

    def test_student_reconstruction_has_verifiable_model_receipts(self):
        from hinglish_motion.student_demo import compile_scene
        ref,answer=self.fixture();scene=compile_scene(ref,answer)
        self.assertEqual(scene['authored_parameters'],'local_model')
        self.assertEqual(scene['content_binding'],'exact supplied reference words/assets')

    def test_css_shorthand_colour_is_expanded_without_changing_the_model_colour(self):
        from hinglish_motion.student_demo import compile_scene
        ref,answer=self.fixture();answer['background']='#fff'
        self.assertEqual(compile_scene(ref,answer)['background'],'#ffffff')

    def test_zero_stagger_is_a_valid_explicit_model_choice(self):
        from hinglish_motion.student_demo import compile_scene
        ref,answer=self.fixture();answer['layers']['word'].update(stagger=0.,reveal='soft')
        self.assertEqual(compile_scene(ref,answer)['layers'][0]['stagger'],0.)

    def test_resume_can_use_only_matching_genuine_model_replies(self):
        from hinglish_motion.student_demo import recover_reply
        ref,answer=self.fixture();answer['layers']['word']['stagger']=0.
        receipt={'model':'Ollama local-qwen','request':{'reference_recipe':ref},'answer':answer}
        self.assertEqual(recover_reply(ref,[receipt],'Ollama local-qwen')['layers'][0]['stagger'],0.)
        self.assertIsNone(recover_reply(ref,[receipt],'another model'))
        wrong=copy.deepcopy(receipt);wrong['request']['reference_recipe']['id']='another-reference'
        self.assertIsNone(recover_reply(ref,[wrong],'Ollama local-qwen'))

