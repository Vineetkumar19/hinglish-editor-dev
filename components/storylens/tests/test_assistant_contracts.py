import tempfile
import unittest
from unittest.mock import patch
from hinglish_app.assistant_contracts import preview_only,constrain,validate
from hinglish_app.assistant_plan import plan,schema


class ContractTests(unittest.TestCase):
    def test_actual_failed_visual_plan_is_rejected_before_another_feature_job(self):
        text='Run Smart Visuals on D:/source/e2(1).mp4. Collect raw source-image choices. Short-form, five per subject. Keep the original speech over plain black.'
        actual_failed={'question':'','steps':[{'tool':'visuals','options':{'visuals_presentation':'auto','zoom_style':'punch'}}]}
        with self.assertRaisesRegex(ValueError,'black'):
            validate(actual_failed,text)

    def test_explicit_raw_visual_review_binds_black_and_five_options(self):
        text='Run Smart Visuals on this video. Short-form raw source-image choices, up to five images per subject. Keep speech over plain black; no cards or lettering.'
        bound=constrain(schema(),text,[{'name':'e2.mp4','kind':'.mp4'}])
        step=bound['properties']['steps']['items'];options=step['properties']['options']
        self.assertEqual(step['properties']['tool']['enum'],['visuals'])
        self.assertEqual(options['properties']['visuals_black_background']['enum'],[True])
        self.assertEqual(options['properties']['visuals_options_per_moment']['enum'],[5])
        self.assertEqual(options['properties']['visuals_popups']['enum'],[False])
        self.assertEqual(options['properties']['visuals_review_options']['enum'],[True])
        with self.assertRaisesRegex(ValueError,'black'):
            validate({'question':'','steps':[{'tool':'visuals','options':{}}]},text)

    def test_local_visual_options_reach_normal_engine_payload(self):
        from hinglish_app.assistant_plan import job_payload,validate_plan
        parsed=validate_plan({'reply':'Prepare choices.','question':'','steps':[{'tool':'visuals','options':{
            'visuals_black_background':True,'visuals_popups':False,'visuals_options_per_moment':2,'visuals_review_options':True}}]})
        payload=job_payload(parsed['steps'][0],['exact-source.mp4'])
        self.assertTrue(payload['visuals_black_background']);self.assertFalse(payload['visuals_popups'])
        self.assertEqual(payload['visuals_options_per_moment'],2)
        self.assertTrue(payload['visuals_review_options'])

    def test_named_account_check_does_not_need_a_video_or_authorize_uploading(self):
        text='Switch Instagram in Chrome to @creator and check the signed-in account. Do not upload anything.'
        bound=constrain(schema(),text)
        options=bound['properties']['steps']['items']['properties']['options']
        self.assertEqual(options['properties']['instagram_action']['enum'],['inspect'])
        self.assertEqual(bound['properties']['question']['enum'],[''])
        parsed={'question':'','steps':[{'tool':'instagram','options':{'instagram_action':'inspect','instagram_account':'creator'}}]}
        validate(parsed,text)
        from hinglish_app.assistant_distribution import validate_edit_plan,WORKFLOW
        validate_edit_plan(parsed,text,WORKFLOW)
        with self.assertRaises(ValueError):validate({**parsed,'question':'Why do you want to check?'},text)

    def test_fully_supplied_preview_cannot_reopen_source_selection(self):
        bound=constrain(schema(),'Prepare an Instagram preview on @creator. Do not post.',[{'name':'clip.mp4','kind':'.mp4'}])
        self.assertEqual(bound['properties']['question']['enum'],[''])
        self.assertEqual(bound['properties']['steps']['minItems'],1)
        self.assertEqual(bound['properties']['steps']['items']['properties']['tool']['enum'],['instagram'])
        self.assertEqual(bound['properties']['steps']['items']['properties']['options']['properties']['instagram_account']['enum'],['creator'])
        missing=constrain(schema(),'Prepare an Instagram preview on @creator.',[])
        self.assertNotIn('enum',missing['properties']['question'])

    def test_sentence_punctuation_cannot_change_the_destination_account(self):
        from hinglish_publish.local_browser import explicit_handles
        self.assertEqual(explicit_handles('Preview on @fantasy_legends91. Do not Share.'),['fantasy_legends91'])
        self.assertEqual(explicit_handles('Use @one.account, then @second_account!'),['one.account','second_account'])
        self.assertEqual(explicit_handles('Mail creator@example.com'),[])
        with self.assertRaises(ValueError):explicit_handles('@'+'a'*31)

    def test_preview_scope_is_bound_without_turning_a_negation_into_permission(self):
        for text in ('Prepare an Instagram preview. Do not post.',
                     'Show a draft on Instagram, without sharing it',
                     'I want an Instagram preview only'):
            self.assertTrue(preview_only(text))
            constrained=constrain(schema(),text)
            self.assertEqual(constrained['properties']['steps']['items']['properties']['options']['properties']['instagram_action']['enum'],['preview'])
        self.assertFalse(preview_only('Do not prepare an Instagram preview.'))

    def test_local_planner_repairs_invalid_operation_before_executor_sees_it(self):
        calls=[]
        class Brain:
            name='local fixture'
            def json(self,system,data,schema,**kwargs):
                calls.append(data)
                return {'reply':'Preparing preview only.','question':'','steps':[{'tool':'instagram',
                    'options':{'instagram_action':'reel' if len(calls)==1 else 'preview'}}]}
            def close(self):pass
        with tempfile.TemporaryDirectory() as root,patch('hinglish_visuals.brain.open_brain',return_value=Brain()):
            result,_=plan(root,'Prepare an Instagram preview of the attached clip. Do not post.',[],[{'name':'clip.mp4'}],False)
        self.assertEqual(len(calls),2)
        self.assertIn('PREVIEW ONLY',calls[1]['validation_error'])
        self.assertEqual(result['steps'][0]['options']['instagram_action'],'preview')


if __name__=='__main__':unittest.main()
