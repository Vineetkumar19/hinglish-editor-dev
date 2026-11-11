"""Manual Sound Design scope is chosen by a bounded local plan, not injected."""
import unittest


class ManualSoundPlanTests(unittest.TestCase):
    text='Run Sound Design on the attached ten-second timeline. Suggest music and sound effects for manual review; I choose. Keep the existing audio unchanged. No full mix or automatic placement.'

    def test_model_schema_exposes_and_requires_manual_recommendations(self):
        from hinglish_app.assistant_plan import schema
        from hinglish_app.assistant_contracts import constrain
        bound=constrain(schema(),self.text,[{'kind':'.xml','name':'native.xml'}])
        options=bound['properties']['steps']['items']['properties']['options']
        self.assertEqual(options['properties']['sound_action']['enum'],['recommend'])
        self.assertIn('sound_action',options['required'])
        self.assertEqual(bound['properties']['steps']['items']['properties']['tool']['enum'],['sound'])

    def test_actual_auto_default_cannot_pass_manual_scope(self):
        from hinglish_app.assistant_contracts import validate
        for options in ({},{'sound_action':'auto'}):
            with self.assertRaisesRegex(ValueError,'recommend'):
                validate({'question':'','steps':[{'tool':'sound','options':options}]},self.text)

    def test_selected_manual_action_reaches_normal_worker_payload(self):
        from hinglish_app.assistant_plan import job_payload,validate_plan
        plan=validate_plan({'reply':'Review only','question':'','steps':[{'tool':'sound','options':{'sound_action':'recommend','script':'exact ASR words'}}]})
        payload=job_payload(plan['steps'][0],['actual-source.mp4'])
        self.assertEqual(payload['panel_sound_action'],'recommend');self.assertEqual(payload['script'],'exact ASR words')
        self.assertFalse(payload['panel_auto_import'])

    def test_attached_shared_script_cannot_be_rewritten_by_manual_sound_plan(self):
        from hinglish_app.assistant_plan import job_payload
        payload=job_payload({'tool':'sound','options':{'sound_action':'recommend','script':'model paraphrase'}},['source.mp4'],'Exact attached ASR words')
        self.assertEqual(payload['script'],'Exact attached ASR words')

    def test_single_manual_router_fits_with_real_saved_sound_guidance_and_full_profile(self):
        from pathlib import Path
        from types import SimpleNamespace
        from hinglish_app.assistant_contracts import planning_system,constrain
        from hinglish_app.assistant_plan import SYSTEM,schema
        from hinglish_app.assistant_plan_context import fit
        from hinglish_niche.profiles import Profiles,use
        root=Path('.').resolve();brain=SimpleNamespace(root=root)
        system=planning_system(SYSTEM,self.text)
        data={'request':self.text,'attachments':[{'kind':'.xml','name':'native.xml'},{'kind':'.txt','name':'ASR.txt'}],
              'conversation':[],'shared_memory':{},'tools':{'sound':'Sound Design'}}
        with use(Profiles(root).context('gaming')):
            bounded=fit(brain,system,data,constrain(schema(include_creative=False),self.text,data['attachments']),1600)
        self.assertEqual(bounded['request'],self.text);self.assertLess(len(system),4000)
        self.assertEqual(planning_system(SYSTEM,'Prepare publishing drafts'),SYSTEM)


if __name__=='__main__':unittest.main()
