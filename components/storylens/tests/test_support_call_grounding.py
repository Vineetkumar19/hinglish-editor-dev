import json
from unittest import TestCase, main
from unittest.mock import patch
from hinglish_app import support_call_router as router

ENGINE = {'tool':'motion','kind':'select','label':'Render engine','id':'motionEngine',
          'purpose':'Selects the renderer.',
          'options':[{'label':'Remotion','value':'remotion','disabled':False},
                     {'label':'Hyperframes','value':'hyperframes','disabled':False}],
          'matched_options':[{'label':'Hyperframes','value':'hyperframes','disabled':False}]}

class GroundedVoiceRouterTests(TestCase):
    def test_nested_option_is_retrieved_outside_its_parent_feature(self):
        with patch.object(router, '_search', return_value=(ENGINE,)):
            context=router.routing_context('What is Hyperframes?','clean',(),())
        self.assertIn('"motion"',context)
        self.assertIn('Render engine',context)
        self.assertIn('hyperframes',context)
        self.assertIn('Makes animated visuals',context)
        self.assertIn('NOT proof',context)

    def test_actual_catalogue_supplies_both_hyperframes_parent_paths(self):
        answer=router.catalog_answer('Where is Hyperframes?','clean')
        self.assertIn('Motion Graphics',answer)
        self.assertIn('Render engine',answer)
        self.assertIn('Auto Captions',answer)
        self.assertIn('Generation method',answer)
        self.assertNotIn('Opened',answer)

    def test_real_named_dropdown_outweighs_generic_scoped_control_list(self):
        question='What options are in Render engine in Motion Graphics?'
        answer=router.catalog_answer(question,'captions')
        self.assertEqual(answer, 'Motion Graphics → Render engine choices are Remotion, Motion Canvas, Hyperframes.')
        self.assertEqual(router.ground_answer(question,'This feature is not in Storylens.','captions'),answer)
        self.assertNotIn('AI brain',answer)
        self.assertNotIn('Auto Captions',answer)

    def test_dynamic_menu_existence_does_not_invent_choices(self):
        dynamic={'tool':'voiceover','kind':'select','id':'voice','label':'Saved voice',
                 'options':[],'dynamic':True}
        with patch.object(router,'_search',return_value=(dynamic,)):
            answer=router.catalog_answer('What choices are in Saved voice?', 'voiceover')
        self.assertIn('dynamic menu',answer)
        self.assertIn('not been verified',answer)
        self.assertNotIn('Vineet',answer)

    def test_options_questions_need_a_known_unambiguous_dropdown(self):
        self.assertEqual(router.catalog_answer('What choices are in Quantum Dragon?','clean'),'')
        self.assertEqual(router.catalog_answer('Select Hyperframes','motion'),'')
        with patch.object(router,'_search',return_value=(ENGINE,dict(ENGINE,id='other'))):
            self.assertEqual(router.catalog_answer('What options are in Render engine?','motion'),'')

    def test_named_late_option_survives_context_budget(self):
        record=dict(ENGINE)
        record['options']=[{'label':f'Option {n}','value':str(n)} for n in range(40)]+ENGINE['options']
        compact=router._compact_records([record])[0]
        self.assertTrue(any(row['value']=='hyperframes' for row in compact['options']))
        self.assertLessEqual(len(compact['options']),12)
        self.assertGreater(compact['more_options'],0)

    def test_known_nested_option_absence_is_replaced_by_its_real_location(self):
        with patch.object(router,'_search',return_value=(ENGINE,)):
            answer=router.ground_answer('What is Hyperframes?',
                'Hyperframes is not a feature in Storylens.','clean')
        self.assertEqual(answer,'Hyperframes is in Motion Graphics → Render engine.')
        self.assertNotIn('Opened',answer)

    def test_unknown_speech_name_is_clarified_not_declared_nonexistent(self):
        with patch.object(router,'_search',return_value=()):
            for question,reply in [
                ('What is the feature of Reve Reveal?', "Reve Reveal isn't a Storylens feature."),
                ('Explain Quantum Banana feature', 'This feature does not exist in Storylens.')]:
                answer=router.ground_answer(question,reply,'clean')
                self.assertNotEqual(answer,reply)
                self.assertTrue('?' in answer)
                self.assertNotIn("isn't",answer)
                self.assertNotIn('does not exist',answer)

    def test_known_feature_denial_is_corrected_without_claiming_execution(self):
        with patch.object(router,'_search',return_value=()):
            answer=router.ground_answer('Explain Voice Clone',
                                        'Voice Clone is not available in Storylens.','clean')
        self.assertIn('Voice Clone is a Storylens feature.',answer)
        self.assertNotIn('Opened',answer)

    def test_model_runtime_claim_is_unverified_and_unrelated_question_is_preserved(self):
        with patch.object(router,'_search',return_value=()):
            for question,reply,active in [
                ('Why is Motion Graphics not rendering?',
                 'The configured model is not installed, so rendering cannot start.','motion'),
                ('What are unicorns?', 'Unicorns do not exist as real animals.',''),
                ('Does Smart Clean have teleportation?', 'Teleportation is not a real editing feature.','clean')]:
                answer=router.ground_answer(question,reply,active)
                if 'teleportation' in question:
                    self.assertNotIn('Smart Clean is a Storylens feature',answer)
                elif 'Motion Graphics' in question:
                    self.assertIn('readiness has not been verified',answer)
                    self.assertNotIn('not installed',answer)
                else:
                    self.assertEqual(answer,reply)

    def test_topic_catalogue_is_not_lost_when_not_a_sidebar_route(self):
        context=router.routing_context('What is 3D2?', 'clean', (), ())
        self.assertIn('3D1',context)
        self.assertIn('caption families',context)
        self.assertIn('nativeCaptions',context)

    def test_live_disabled_evidence_is_preserved_but_invented_runtime_state_is_not(self):
        field=dict(ENGINE,live=True,disabled=True)
        with patch.object(router,'_search',return_value=(field,)):
            answer=router.ground_answer('Use Hyperframes','It is disabled.','motion')
        self.assertIn('currently disabled',answer)
        with patch.object(router,'_search',return_value=(ENGINE,)):
            answer=router.ground_answer('What is Hyperframes?',
                'Hyperframes is currently not available because the model is not installed.','motion')
        self.assertIn('readiness has not been verified',answer)
        self.assertNotIn('not installed',answer)

    def test_specific_negative_capability_is_not_confused_with_feature_absence(self):
        reply='Reel Recreate does not support automatic lip sync.'
        self.assertEqual(router.ground_answer('Does Reel Recreate do automatic lip sync?',
                                             reply, 'reelRecreate'), reply)

    def test_hindi_denial_uses_a_grounded_hindi_location(self):
        with patch.object(router,'_search',return_value=(ENGINE,)):
            answer=router.ground_answer('Hyperframes कहाँ है?',
                                        'यह फीचर Storylens में नहीं है।','clean',language='hi')
        self.assertIn('Motion Graphics → Render engine',answer)
        self.assertIn('में है',answer)
        self.assertNotIn('खोल दिया',answer)

    def test_location_lookup_is_informational_and_does_not_execute(self):
        with patch.object(router,'_search',return_value=(ENGINE,)):
            self.assertEqual(router.catalog_answer('Where is Hyperframes?','clean'),
                             'Hyperframes is in Motion Graphics → Render engine.')
            self.assertEqual(router.catalog_answer('Use Hyperframes','clean'),'')
            self.assertEqual(router.catalog_answer('How do I render with Hyperframes?','clean'),'')

if __name__ == '__main__':
    main()
