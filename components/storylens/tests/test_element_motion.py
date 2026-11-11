import copy
import unittest


class ElementMotionTests(unittest.TestCase):
    def test_explicit_element_script_is_data_and_bypasses_unrelated_planner_context(self):
        from hinglish_app.assistant_motion_reference import request
        script='It still fails the reference comparison: wrong crops, clipped text and blank sections remain.'
        r=request('Create Motion Graphics using Element animation, 9:16 Quick preview.\nSCRIPT:\n'+script)
        self.assertEqual(r['script'],script)
        self.assertNotIn('reference',r)
    def test_new_element_failures_use_shared_plain_language_errors(self):
        from hinglish_app.user_messages import problem,catalog
        catalog.cache_clear()
        r=problem(ValueError('Element motion plan invalid: parent cycle.'),feature='Motion Graphics')
        self.assertEqual(r['code'],'motion_elements')
        self.assertIn('saved',r['message'].lower())
    def fixture(self):
        def object_(id,kind,x,dx):
            return {'id':id,'kind':kind,'parent':'','label':'','w':.2,'h':.2,'fill':'#11cccc','stroke':'#ffffff','stroke_width':2,'radius':.02,'clip':False,
                    'keys':[{'t':0,'x':x,'y':.3,'scale':1,'rotation':0,'opacity':1},{'t':1,'x':x+dx,'y':.4,'scale':1,'rotation':0,'opacity':1}]}
        return {'background':'#101018','objects':[object_('frame','frame',.1,0),object_('card','rect',.1,.2),object_('dot','ellipse',.5,-.2),object_('path','line',.2,0)],
                'sound_intents':[{'time':.4,'query':'soft whoosh','gain_db':-18}]}

    def test_script_partition_preserves_the_actual_statement_and_order(self):
        from hinglish_motion.element_motion import bind_story
        words='One normal statement. Another short sentence.'
        story={'scenes':[{'start':0,'count':3,'duration':4,'concept':'A moving object'},{'start':3,'count':3,'duration':4,'concept':'Objects settle'}]}
        self.assertEqual(' '.join(s['caption'] for s in bind_story(words,story)),words)
        broken=copy.deepcopy(story);broken['scenes'][1]['start']=2
        with self.assertRaises(ValueError):bind_story(words,broken)

    def test_graph_requires_independent_element_motion_not_only_text_or_camera(self):
        from hinglish_motion.element_motion import validate_scene
        self.assertEqual(validate_scene(self.fixture(),4)['objects'][0]['id'],'frame')
        a=self.fixture()
        for o in a['objects']:o['keys'][-1]=dict(o['keys'][0],t=1)
        with self.assertRaisesRegex(ValueError,'independent'):validate_scene(a,4)

    def test_bad_parent_geometry_and_reveal_times_are_rejected_together(self):
        from hinglish_motion.element_motion import validate_scene
        a=self.fixture();a['objects'][1]['parent']='missing'
        with self.assertRaisesRegex(ValueError,'parent'):validate_scene(a,4)
        a=self.fixture();a['objects'][0]['parent']='card';a['objects'][1]['parent']='frame'
        with self.assertRaisesRegex(ValueError,'cycle'):validate_scene(a,4)
        a=self.fixture();a['objects'][0]['w']=-1
        with self.assertRaises(ValueError):validate_scene(a,4)
        a=self.fixture();a['sound_intents'][0]['time']=8
        with self.assertRaises(ValueError):validate_scene(a,4)


if __name__=='__main__':unittest.main()
