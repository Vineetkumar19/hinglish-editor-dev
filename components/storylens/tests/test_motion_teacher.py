import tempfile
import unittest
from pathlib import Path
import numpy as np


class MotionTeacherTests(unittest.TestCase):
    def test_boolean_choices_generate_a_valid_model_schema(self):
        import jsonschema
        from hinglish_motion.reference_slots import enum
        jsonschema.validate(False,enum([False]))

    def test_actual_teacher_opening_contains_visible_layers(self):
        import av
        file=Path(__file__).resolve().parents[1]/'output/motion/teacher-world-culture-20261024/MOTION_GRAPHICS.mp4'
        if not file.exists():self.skipTest('Actual teacher render not generated on this host')
        with av.open(str(file)) as c:frame=next(f for f in c.decode(video=0) if f.time>=.7)
        pixels=frame.to_ndarray(format='rgb24')
        self.assertGreater(np.count_nonzero(pixels.min(axis=2)<180),5000,'Opening must show real photo/text layers, not a blank page')

    def test_teacher_package_is_source_bound_and_cannot_read_an_unrelated_plan(self):
        import hashlib,json
        from hinglish_motion.teacher_demo import teacher_package
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'output/motion/example';out.mkdir(parents=True)
            source=root/'source.mp4';source.write_bytes(b'video')
            plan=out/'teacher-plan.json';plan.write_text(json.dumps({'source_sha256':hashlib.sha256(b'video').hexdigest()}))
            self.assertEqual(teacher_package(root,source,'Teacher package: '+str(plan)),plan.resolve())
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError):teacher_package(root,source,'Teacher package: '+str(plan))
            with self.assertRaises(ValueError):teacher_package(root,source,'Teacher package: '+str(root/'outside.json'))

    def test_teacher_preserves_authored_tracks_and_rejects_missing_scene_time(self):
        from hinglish_motion.teacher_memory import validate_plan
        plan={'width':720,'height':1280,'duration':2.,'scenes':[{'id':'a','start':0.,'end':2.,'camera':[{'time':0.,'scale':1.35,'x':0.,'y':0.},{'time':2.,'scale':.93,'x':-35.,'y':12.}],'layers':[]}]}
        self.assertIs(validate_plan(plan),plan)
        with self.assertRaises(ValueError):validate_plan({**plan,'scenes':[{**plan['scenes'][0],'start':.5}]})
        with self.assertRaises(ValueError):validate_plan({**plan,'scenes':[{**plan['scenes'][0],'camera':[{'time':0.,'scale':float('nan'),'x':0.,'y':0.}]}]})

    def test_vector_memory_retrieves_camera_lesson_and_separates_draft_from_approval(self):
        from hinglish_motion.teacher_memory import TeacherIndex
        with tempfile.TemporaryDirectory() as d:
            index=TeacherIndex(Path(d)/'memory.sqlite')
            rows=[{'id':'camera','text':'Camera keyframes and independent foreground parallax','status':'draft'},
                  {'id':'type','text':'Reserve complete text width before character reveal','status':'approved'}]
            index.put('sample',rows,np.array([[1.,0.],[0.,1.]],dtype=np.float32))
            self.assertEqual(index.search([1.,0.],allow_draft=True)[0]['id'],'camera')
            self.assertEqual(index.search([1.,0.])[0]['id'],'type')
            with self.assertRaises(ValueError):index.put('bad',rows,np.array([[float('nan'),0.],[0.,1.]]))
            index.close()

    def test_guidance_is_scoped_data_and_keeps_existing_creator_context(self):
        from hinglish_motion.teacher_memory import inject
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'context.json';p.write_text('{"kind":"retrieved teacher examples; weights unchanged","chunks":[{"text":"character reveal with fixed slots"}]}')
            result=inject('Full creator profile stays here.',p)
            self.assertTrue(result.startswith('Full creator profile stays here.'))
            self.assertIn('reference data',result)
            self.assertIn('weights unchanged',result)

    def test_planning_and_vision_request_paths_receive_teacher_data_only_for_motion(self):
        import os,json
        from unittest.mock import patch
        from hinglish_cut.creative_memory import configure
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'context.json';p.write_text(json.dumps({'kind':'reference memory, not weight training','chunks':[{'text':'fixed row character motion'}]}))
            for model in ('storylens-meaning:14b','storylens-planner:9b-q6'):
                body={'model':model,'messages':[{'role':'system','content':'FULL CREATOR GUIDANCE'},{'role':'user','content':'{"script":"motion sample"}'}]}
                with patch.dict(os.environ,{'STORYLENS_REFERENCE_FEATURE':'motion','STORYLENS_MOTION_TEACHER_CONTEXT':str(p)}):configure(Path(d),body)
                self.assertIn('FULL CREATOR GUIDANCE',body['messages'][0]['content']);self.assertIn('Storylens motion teacher examples',body['messages'][0]['content'])
            body={'messages':[{'role':'system','content':'FULL CREATOR GUIDANCE'},{'role':'user','content':'{"script":"sound sample"}'}]}
            with patch.dict(os.environ,{'STORYLENS_REFERENCE_FEATURE':'sound','STORYLENS_MOTION_TEACHER_CONTEXT':str(p)}):configure(Path(d),body)
            self.assertNotIn('Storylens motion teacher examples',body['messages'][0]['content'])


if __name__=='__main__':unittest.main()
