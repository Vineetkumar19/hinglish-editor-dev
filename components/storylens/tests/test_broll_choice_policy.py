import tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class ChoicePolicyTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-broll-choice-policy';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_platform_defaults_and_legacy_requests_are_capped(self):
        from hinglish_broll.choice_policy import choice_limit
        for value in (None,5,6):
            self.assertEqual(choice_limit(value,'vertical'),5)
            self.assertEqual(choice_limit(value,'horizontal'),2)
        self.assertEqual(choice_limit(1,'horizontal'),1)
        self.assertEqual(choice_limit(None,output_format='youtube_horizontal'),2)
        self.assertEqual(choice_limit(None,timeline={'width':1920,'height':1080}),2)
        for value in (0,7,True,'5'):
            with self.assertRaises(ValueError):choice_limit(value,'vertical')

    def test_collector_never_offers_more_than_the_platform_cap(self):
        from hinglish_broll.website_review import collect
        from hinglish_broll.stock import Candidate
        slots=[{'moment':{'visual':'restaurant','queries':['restaurant']},'text':'restaurant','start':1,'end':2}]
        for orientation,width,height,limit in [('vertical',1080,1920,5),('horizontal',1920,1080,2)]:
            folder=self.root/orientation;folder.mkdir()
            def acquire(c,folder):
                p=folder/(c.id+'.mp4');p.write_bytes(b'fixture')
                return {'path':str(p),'duration':10,'width':width,'height':height}
            bank=collect(folder,{'name':'test','duration':4,'fps':'30','width':width,'height':height},slots,
                limit=6,orientation=orientation,search=lambda _:[Candidate('website',str(n),'Restaurant',10,0,0) for n in range(9)],acquire=acquire)
            self.assertEqual(bank['option_limit'],limit);self.assertEqual(len(bank['slots'][0]['options']),limit)

    def test_cli_applies_caps_before_handoff_to_pipeline(self):
        from hinglish_broll.__main__ import main
        for orientation,expected in [('vertical',5),('horizontal',2)]:
            with patch('sys.argv',['broll','--root',str(self.root),'--input','sample.mov','--orientation',orientation,'--options-per-moment','6']),patch('hinglish_broll.__main__.run',return_value=Path('report.html')) as run:
                self.assertEqual(main(),0)
                self.assertEqual(run.call_args.kwargs['options_per_moment'],expected)

    def test_local_chat_payload_obeys_platform_caps(self):
        from hinglish_app.assistant_plan import job_payload
        for orientation,expected in [('vertical',5),('horizontal',2)]:
            payload=job_payload({'tool':'broll','options':{'broll_orientation':orientation,'broll_options_per_moment':6}},['sample.mov'])
            self.assertEqual(payload['broll_options_per_moment'],expected)

if __name__=='__main__':unittest.main()
