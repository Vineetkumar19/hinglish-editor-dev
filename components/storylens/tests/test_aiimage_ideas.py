import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from hinglish_aigen.direct import ENVELOPE,channel_context,decode_request,plan_idea,image_planning_context
from hinglish_aigen.settings import GenSettings
from hinglish_aigen import pipeline
from tests.test_aigen import READY,fake_generate

class Brain:
    name='test-only planner'
    last_usage={'test_only':True}
    def json(self,system,data,schema,**kwargs):
        if 'people' in schema['properties']:return dict(people=[],brands=[],places=[])
        self.data=data
        return dict(prompt='A single red cricket ball strikes three wooden stumps on a dusty cricket pitch, two bails suspended above them, warm afternoon side light, shallow depth of field, low sports photography angle, clear sharp focal detail and a softly blurred empty outfield, no text or logos.',reason='One clear cricket action')
    def close(self):pass

class DirectImageTests(unittest.TestCase):
    def test_old_bridge_preserves_idea_and_specialist_settings(self):
        idea='Last ball pe wicket, red ball aur dramatic light'
        text,settings=decode_request(ENVELOPE+json.dumps(dict(idea=idea,channel='cricket',purpose='thumbnail')))
        self.assertEqual(text,idea)
        self.assertEqual(settings,dict(request_mode='idea',channel='cricket',purpose='thumbnail'))
        self.assertEqual(decode_request('An ordinary script'),('An ordinary script',{}))

    def test_malformed_envelope_does_not_become_a_silent_script(self):
        for body in ['[]','{}','{"idea":"hello","channel":"unknown"}','{"idea":"hello","path":"x"}']:
            with self.assertRaisesRegex(ValueError,'could not be read'):decode_request(ENVELOPE+body)

    def test_short_hinglish_idea_gets_one_scene_and_a_saved_knowledge_receipt(self):
        brain=Brain();idea='cricket wicket'
        moments,entities,receipt=plan_idea(brain,idea,GenSettings(request_mode='idea',channel='cricket'),lambda _:None)
        self.assertEqual(len(moments),1)
        self.assertEqual(moments[0].text,idea)
        self.assertEqual(receipt['original_idea'],idea)
        self.assertFalse(receipt['weight_training'])
        self.assertIn('baseball',' '.join(brain.data['channel_knowledge']['direction']))

    def test_channel_auto_follows_subject_and_explicit_choice_wins(self):
        self.assertEqual(channel_context('auto','IPL cricket wicket')['channel'],'cricket')
        self.assertEqual(channel_context('auto','rooftop 1v4 gaming clutch')['channel'],'gaming')
        self.assertEqual(channel_context('cricket','rooftop gaming')['channel'],'cricket')
        self.assertEqual(channel_context('auto','a quiet woodland lake')['channel'],'general')

    def test_unified_image_planner_keeps_full_creator_profile(self):
        creator={'profile':'cricket','feedback':'My full saved guidance remains here'}
        data={'story':'A red cricket ball hits the wickets','design':{'category':'general'},'creator_profile':creator,'profile':'cricket'}
        system,payload=image_planning_context(Path.cwd(),'Original planner',data,{'properties':{'concepts':{}}})
        self.assertIs(payload['creator_profile'],creator)
        self.assertEqual(payload['image_channel_knowledge']['channel'],'cricket')
        self.assertEqual(data.keys(),{'story','design','creator_profile','profile'})
        self.assertTrue(system.startswith('Original planner'))

    def test_unrelated_planning_is_unchanged(self):
        data={'story':'A cricket story'};schema={'properties':{'cuts':{}}}
        self.assertEqual(image_planning_context(Path.cwd(),'original',data,schema),('original',data))

    def test_empty_idea_stops_before_gpu_start(self):
        with patch.object(pipeline.engine,'doctor') as doctor:
            with self.assertRaisesRegex(ValueError,'Describe the image'):pipeline.run(Path.cwd(),script='',settings=GenSettings(request_mode='idea'))
            doctor.assert_not_called()

    def test_saved_direct_project_contains_request_receipt_download_and_remake(self):
        # A transport/persistence test only: the application run uses the real GPU.
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            with patch.object(pipeline.engine,'doctor',return_value=READY),patch.object(pipeline.engine,'generate',side_effect=fake_generate),patch('hinglish_visuals.brain.open_brain',return_value=Brain()):
                page=pipeline.run(root,script='cricket wicket',settings=GenSettings(request_mode='idea',channel='cricket',check=False,options=1),progress=lambda _:None)
                project=json.loads((page.parent/'aiimage-project.json').read_text('utf-8'))
                self.assertEqual(project['settings']['request_mode'],'idea')
                self.assertEqual(project['image_direction']['knowledge']['channel'],'cricket')
                self.assertTrue((page.parent/'image-direction.json').is_file())
                self.assertEqual(len(list((page.parent/'chosen').glob('*.png'))),1)
                self.assertIn('Download image',page.read_text('utf-8'))
                result=pipeline.rebuild_project(page.parent/'aiimage-project.json',{'regenerate':{'1':'A single red cricket ball beside three wooden stumps at golden hour.'}},lambda _:None)
                self.assertEqual(result['with_visual'],1)
                self.assertEqual(pipeline.engine.generate.call_args.args[0],root)

if __name__=='__main__':unittest.main()
