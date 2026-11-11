import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

from hinglish_app.assistant_artifacts import editing_requested
from hinglish_app.assistant_plan import job_payload,validate_plan
from hinglish_app.assistant_zoom_plan import requested,plan


class SmartZoomChatTests(TestCase):
    def test_sound_policy_question_routes_to_help_instead_of_edit_planning(self):
        from hinglish_app.assistant_plan import is_help_request
        self.assertTrue(is_help_request('What sound effects are allowed for SmartZoom under my latest preference?'))
        self.assertTrue(is_help_request('Which SmartZoom sounds may you use?'))
        self.assertFalse(is_help_request('Run SmartZoom with basic whoosh sound effects.'))

    def test_sound_question_uses_sound_rule_and_keeps_full_creator_profile(self):
        from hinglish_app.assistant_zoom_plan import explain
        from hinglish_niche.profiles import inject,use
        brain=Mock()
        brain.json.return_value={'reply':'Only the approved basic whooshes; leave overlays unchanged.'}
        profile={'profile':'gaming','brief':'Complete owner guidance. '*200}
        with use(profile):
            result=explain(brain,'What sound effects may SmartZoom use?',[],{})
            system,data,schema=brain.json.call_args.args
            _,injected=inject(system,data)
        self.assertEqual(injected['creator_profile'],profile)
        self.assertIn('basic Whoosh',data['current_owner_policy'][0])
        self.assertNotIn('runtime_zoom_policy',data)
        self.assertEqual(result['steps'],[])

    def test_saved_owner_rule_is_required_even_with_old_chat_timing(self):
        from hinglish_app.assistant_zoom_plan import explain
        brain=Mock()
        brain.json.return_value={'reply':'Alternate at cuts; hold until the next cut.'}
        result=explain(brain,'What are my SmartZoom rules?',
                       [{'role':'assistant','text':'Wait 10-13 seconds between zooms.'}],{})
        system,data,schema=brain.json.call_args.args
        self.assertIn('override',system)
        self.assertTrue(data['current_owner_policy'])
        self.assertEqual(data['runtime_zoom_policy']['short']['pacing'],'cuts')
        self.assertEqual(data['runtime_zoom_policy']['short']['cut_ramp'],.8)
        self.assertEqual(data['runtime_zoom_policy']['short']['cut_ramp_out'],.7)
        self.assertEqual(data['runtime_zoom_policy']['short']['framing'],'fixed_focal')
        self.assertEqual(data['runtime_zoom_policy']['short']['hold'],'until_next_cut')
        self.assertFalse(data['runtime_zoom_policy']['short']['timer'])
        self.assertIn('eight seconds',data['current_owner_policy'][0])
        self.assertEqual(result['steps'],[])

    def test_tool_name_routes_exact_source_without_publishing(self):
        text='Run SmartZoom on this existing edited video:\nA:\\Full Drive\\thisis.vineet\\e7\\E7 final.mp4'
        self.assertTrue(editing_requested(text))
        self.assertTrue(requested(text))
        self.assertFalse(requested('How does SmartZoom work?'))
        self.assertFalse(requested('Run Smart Clean and then SmartZoom on this video.'))
        self.assertFalse(requested('Run SmartZoom and upload the video.'))

    def test_zoom_settings_reach_the_tool_including_face_and_frequency(self):
        options={'zoom_style':'smooth','zoom_strength':'subtle','zoom_frequency':'low',
                 'zoom_face':False,'zoom_jump_cuts':False}
        result=validate_plan({'reply':'Starting SmartZoom.','question':'','combine':False,
            'steps':[{'tool':'zoom','options':options}]})
        payload=job_payload(result['steps'][0],['edited.mp4'])
        self.assertEqual(payload['mode'],'zoom')
        for key,value in options.items():self.assertEqual(payload[key],value)

    def test_current_strength_overrides_older_demo_strength(self):
        brain=Mock()
        old={'zoom_style':'smooth','zoom_strength':'strong','zoom_frequency':'medium',
             'zoom_face':True,'zoom_jump_cuts':False}
        reply=lambda opts: {'reply':'Starting.','question':'','combine':False,'steps':[{'tool':'zoom','options':opts}]}
        brain.json.side_effect=[reply(old),reply({**old,'zoom_strength':'medium'})]
        result=plan(brain,'Run SmartZoom: smooth style, medium strength, medium frequency.',
                    [{'role':'assistant','text':'The previous demo used strong strength.'}],[],{})
        self.assertEqual(result['steps'][0]['options']['zoom_strength'],'medium')
        self.assertEqual(brain.json.call_count,2)
        options=brain.json.call_args.args[2]['properties']['steps']['items']['properties']['options']['properties']
        self.assertEqual(options['zoom_strength']['enum'],['medium'])

    def test_bounded_planner_keeps_full_creator_profile(self):
        from hinglish_niche.profiles import inject,use
        profile={'profile':'gaming','brief':'Preserve creator guidance. '*450}
        options={'zoom_style':'smooth','zoom_strength':'subtle','zoom_frequency':'medium',
                 'zoom_face':True,'zoom_jump_cuts':False}
        with tempfile.TemporaryDirectory() as folder,use(profile):
            brain=Mock(root=Path(folder))
            brain.json.return_value={'reply':'Starting SmartZoom.','question':'','combine':False,
                'steps':[{'tool':'zoom','options':options}]}
            result=plan(brain,'Run SmartZoom with gentle face-centred zooms.',[],[{'name':'edited.mp4','kind':'.mp4'}],{})
            system,data,schema=brain.json.call_args.args
            _,injected=inject(system,data,root=Path(folder))
            self.assertEqual(injected['creator_profile'],profile)
            self.assertEqual(result['steps'][0]['options'],options)
            self.assertEqual(schema['properties']['steps']['items']['properties']['tool']['enum'],['zoom'])
