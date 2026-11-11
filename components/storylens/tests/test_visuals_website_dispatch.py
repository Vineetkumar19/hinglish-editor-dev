"""Application dispatch contract; real footage acceptance is tested separately."""
import unittest
from pathlib import Path


class VisualsWebsiteDispatchTests(unittest.TestCase):
    def test_new_jobs_use_web_options_without_vision_even_with_stale_toggles(self):
        from hinglish_app.visuals_search_dispatch import arguments
        args=arguments({'visuals_check':True,'visuals_web':False})
        self.assertEqual(args,['--search-method','website','--evaluator','off'])

    def test_verified_is_explicit_and_invalid_methods_fail_before_work(self):
        from hinglish_app.visuals_search_dispatch import arguments
        self.assertEqual(arguments({'visuals_search_method':'verified'}),['--search-method','verified'])
        self.assertIn('--no-web',arguments({'visuals_search_method':'verified','visuals_web':False}))
        for bad in ['api','',None,True]:
            with self.assertRaises(ValueError):arguments({'visuals_search_method':bad})

    def test_chat_plans_default_to_the_same_manual_web_method(self):
        from hinglish_app.assistant_plan import job_payload,validate_plan
        for fmt,count in [('instagram_vertical',5),('youtube_horizontal',2)]:
            plan=validate_plan({'reply':'Starting','question':'','steps':[{'tool':'visuals','options':{'format':fmt,'visuals_search_method':'website'}}]})
            job=job_payload(plan['steps'][0],['test.mov'])
            self.assertEqual(job['visuals_search_method'],'website')
            self.assertFalse(job['visuals_check']);self.assertTrue(job['visuals_web'])
            self.assertTrue(job['visuals_review_options']);self.assertEqual(job['visuals_options_per_moment'],count)

    def test_main_run_does_not_send_a_hidden_vision_requirement(self):
        root=Path(__file__).resolve().parents[1]
        script=(root/'hinglish_app/static/app.js').read_text('utf-8')
        self.assertIn("visuals_search_method:'website'",script)
        self.assertIn('visuals_check:false',script)
        self.assertNotIn("$('#visualsCheck').checked",script)
        self.assertTrue("includes('visuals_website_options_v1')" in script,'Old services must not silently run verified mode')

    def test_horizontal_bank_is_complete_at_two_and_still_needs_human_review(self):
        from hinglish_app.visuals_search_dispatch import summary
        result=summary([{'search_method':'website','review_options':True,'options_per_moment':2,
            'slots':[{'options':[{},{}]}]}])
        self.assertEqual(result['complete_subjects'],1);self.assertFalse(result['partial'])
        self.assertTrue(result['research_complete']);self.assertEqual(result['review_policy'],'human')
        self.assertFalse(result['vision_checked']);self.assertFalse(summary([])['research_complete'])


if __name__=='__main__':unittest.main()
