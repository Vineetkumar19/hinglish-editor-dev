import tempfile,unittest
from pathlib import Path
from hinglish_broll.stock import Candidate


class OrientationTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-broll-orientation';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.timeline={'name':'e3','fps':'30','width':1080,'height':1920,'duration':38}
        self.slots=[{'moment':{'visual':'wireless router','queries':['wireless router']},'text':'Wi-Fi?', 'start':6.56,'end':8.14}]

    def test_vertical_search_uses_actual_discover_filter(self):
        from hinglish_broll.website_review import search_url
        self.assertEqual(search_url('washing machine','vertical'),
            'https://mixkit.co/free-stock-video/discover/washing-machine/?orientation=vertical')

    def test_five_native_vertical_files_are_offered_and_horizontal_is_not_disguised(self):
        from hinglish_broll.website_review import collect
        rows=[Candidate('website',str(n),'Video',10,0,0) for n in range(10)]
        def acquire(c,folder):
            p=folder/(c.id+'.mp4');p.write_bytes(b'video')
            return {'path':str(p),'duration':10,'width':1280 if c.id=='0' else 720,'height':720 if c.id=='0' else 1280}
        bank=collect(self.folder,self.timeline,self.slots,limit=6,orientation='vertical',
            search=lambda _ :rows,acquire=acquire,progress=lambda _:None)
        self.assertEqual(len(bank['slots'][0]['options']),5)
        self.assertTrue(all(o['height']>o['width'] for o in bank['slots'][0]['options']))
        self.assertEqual(bank['orientation'],'vertical')
        self.assertEqual(bank['option_limit'],5)

    def test_horizontal_selection_excludes_portrait(self):
        from hinglish_broll.website_review import matches_orientation
        self.assertFalse(matches_orientation(720,1280,'horizontal'))
        self.assertFalse(matches_orientation(1280,720,'vertical'))
        self.assertTrue(matches_orientation(720,1280,'vertical'))
        self.assertFalse(matches_orientation(720,720,'vertical'))

    def test_changing_orientation_keeps_original_bank_and_requires_separate_result(self):
        from hinglish_broll.website_review import collect
        collect(self.folder,self.timeline,self.slots,orientation='vertical',search=lambda _:[],progress=lambda _:None)
        with self.assertRaisesRegex(ValueError,'separate|another'):
            collect(self.folder,self.timeline,self.slots,orientation='horizontal',search=lambda _:[],progress=lambda _:None)

    def test_wifi_search_expands_without_changing_quote_or_timestamps(self):
        from hinglish_broll.website_review import expanded_queries,new_bank
        queries=expanded_queries(['wireless router'],'wireless router')
        self.assertIn('internet connection',queries);self.assertIn('wifi router',queries)
        bank=new_bank(self.timeline,self.slots)
        self.assertEqual(bank['slots'][0]['text'],'Wi-Fi?')
        self.assertEqual((bank['slots'][0]['start'],bank['slots'][0]['end']),(6.56,8.14))

    def test_review_has_two_short_format_buttons(self):
        from hinglish_broll.website_review import collect
        collect(self.folder,self.timeline,self.slots,orientation='vertical',search=lambda _:[],progress=lambda _:None)
        page=(self.folder/'report.html').read_text('utf-8')
        self.assertIn('data-orientation="vertical"',page)
        self.assertIn('data-orientation="horizontal"',page)
        self.assertIn('Up to 5 videos',page)

    def test_main_run_asks_format_before_submission_and_sends_six_option_setting(self):
        root=Path(__file__).resolve().parents[1]
        script=(root/'hinglish_app/static/app.js').read_text('utf-8')
        self.assertIn('await window.storylensBrollFormat.ask()',script)
        self.assertIn('broll_orientation',script)
        self.assertIn('window.storylensBrollFormat.limit(brollOrientation',script)
        self.assertIn('--orientation',(root/'hinglish_app/server.py').read_text('utf-8'))

    def test_cli_passes_selected_orientation_and_six_options_to_pipeline(self):
        from unittest.mock import patch
        from hinglish_broll.__main__ import main
        with patch('sys.argv',['broll','--input','video.mp4','--review-options','--orientation','vertical','--options-per-moment','6']), \
             patch('hinglish_broll.__main__.run',return_value=Path('report.html')) as run:
            self.assertEqual(main(),0)
        self.assertEqual(run.call_args.kwargs['orientation'],'vertical')
        self.assertEqual(run.call_args.kwargs['options_per_moment'],5)

    def test_local_chat_planner_asks_format_and_accepts_six(self):
        from hinglish_app.assistant_plan import validate_plan,job_payload
        missing=validate_plan({'reply':'Starting','question':'','steps':[{'tool':'broll','options':{}}]})
        self.assertEqual(missing['question'],'B-roll format?');self.assertEqual(missing['steps'],[])
        chosen=validate_plan({'reply':'Starting','question':'','steps':[{'tool':'broll','options':{'broll_orientation':'vertical','broll_options_per_moment':5}}]})
        payload=job_payload(chosen['steps'][0],['e3.mp4'])
        self.assertEqual(payload['broll_orientation'],'vertical');self.assertEqual(payload['broll_options_per_moment'],5)

if __name__=='__main__':unittest.main()
