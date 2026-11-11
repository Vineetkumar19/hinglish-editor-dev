"""Public website collection and explicit human approval, without model verdicts."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class WebsiteReviewTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-website-review'
        base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'output/broll/test/001-e3'
        self.folder.mkdir(parents=True)
        self.plan=[{'moment':{'visual':'refrigerator','queries':['refrigerator','fridge'],
            'quote':'Fridge?','meaning':'a refrigerator'},'text':'Fridge?',
            'start':10.12,'end':12.32},
            {'moment':{'visual':'wireless router','queries':['wireless router']},
             'text':'Wi Fi?','start':6.56,'end':8.14}]
        self.timeline={'name':'e3','fps':'30','width':1080,'height':1920,'duration':37.45}

    def test_public_search_extracts_only_same_site_detail_pages_and_deduplicates(self):
        from hinglish_broll.website_review import detail_links,search_url
        markup='''<a href="/free-stock-video/open-fridge-123/">a</a>
        <a href="https://mixkit.co/free-stock-video/open-fridge-123/">b</a>
        <a href="https://evil.example/free-stock-video/other-99/">no</a>
        <a href="/free-stock-video/fridge/">category</a>'''
        self.assertEqual(detail_links(markup),['https://mixkit.co/free-stock-video/open-fridge-123/'])
        self.assertEqual(search_url('washing machine'),'https://mixkit.co/free-stock-video/washing-machine/')

    def test_all_planned_moments_exist_before_search_and_are_not_approved(self):
        from hinglish_broll.website_review import new_bank
        bank=new_bank(self.timeline,self.plan)
        self.assertEqual(len(bank['slots']),2)
        self.assertEqual([s['status'] for s in bank['slots']],['pending','pending'])
        self.assertEqual(bank['slots'][0]['start'],10.12)
        self.assertIsNone(bank['slots'][0]['selected'])
        self.assertEqual(bank['review_mode'],'website_manual')

    def test_failed_keyword_does_not_abort_next_and_resume_keeps_completed_work(self):
        from hinglish_broll.website_review import collect
        calls=[]
        def search(query):
            calls.append(query)
            if query in ('refrigerator','fridge'):raise RuntimeError('website timeout')
            return []
        bank=collect(self.folder,self.timeline,self.plan,limit=5,search=search)
        self.assertEqual([s['status'] for s in bank['slots']],['no_results','no_results'])
        self.assertEqual(bank['state'],'complete');self.assertGreaterEqual(len(calls),3)
        completed_calls=len(calls)
        again=collect(self.folder,self.timeline,self.plan,limit=5,search=search)
        self.assertEqual(len(calls),completed_calls);self.assertEqual(again['bank_id'],bank['bank_id'])

    def test_video_only_five_max_local_files_hashed_and_no_vision_flag(self):
        from hinglish_broll.website_review import collect
        from hinglish_broll.stock import Candidate
        rows=[Candidate('website',str(i),'Fridge',20,640,360,
            download_url=f'https://assets.mixkit.co/videos/{i}/{i}-720.mp4',
            page_url=f'https://mixkit.co/free-stock-video/fridge-{i}/') for i in range(9)]
        def acquire(candidate,folder):
            p=folder/'media'/f'{candidate.id}.mp4';p.parent.mkdir(exist_ok=True)
            p.write_bytes(b'actual-video-fixture');return {'path':str(p),'duration':20,'width':640,'height':360}
        bank=collect(self.folder,self.timeline,self.plan[:1],limit=5,
            search=lambda _:rows,acquire=acquire)
        options=bank['slots'][0]['options'];self.assertEqual(len(options),5)
        self.assertTrue(all(o['review_status']=='needs_human_review' for o in options))
        self.assertFalse(any('passed' in o or 'verified' in o for o in options))
        self.assertEqual(options[0]['sha256'],hashlib.sha256(b'actual-video-fixture').hexdigest())

    def test_only_explicit_offered_choice_can_prepare_native_timing(self):
        from hinglish_broll.website_review import collect,prepare_choice
        from hinglish_broll.stock import Candidate
        candidate=Candidate('website','one','Fridge',20,1080,1920,
            page_url='https://mixkit.co/free-stock-video/fridge-1/')
        p=self.folder/'one.mp4';p.write_bytes(b'fixture')
        collect(self.folder,self.timeline,self.plan[:1],search=lambda _:[candidate],
            acquire=lambda *_:{'path':str(p),'duration':20,'width':1080,'height':1920})
        context={'host':'aftereffects','project_id':'owner','sequence_id':'test','fps':30}
        with self.assertRaises(ValueError):prepare_choice(self.root,self.folder,0,'other',context)
        with patch('hinglish_broll.website_review.prepare_native',return_value={'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'duration':20}), \
             patch('hinglish_app.timed_choice_delivery.TimedChoiceDelivery.prepare',return_value={'operation_id':'test'}) as prepare:
            prepare_choice(self.root,self.folder,0,'one',context)
        request=prepare.call_args.args[0]
        self.assertEqual((request['start_frame'],request['end_frame']),(304,370))
        self.assertEqual(request['asset_path'],str(p.resolve()))
        import json
        saved=json.loads((self.folder/'website-review.json').read_text('utf-8'))
        self.assertEqual(saved['slots'][0]['selected'],'one')
        self.assertEqual(saved['slots'][0]['approval']['method'],'explicit_user_choice')

    def test_owner_can_save_and_clear_choice_without_opening_after_effects(self):
        from hinglish_broll.website_review import collect,choose
        from hinglish_broll.stock import Candidate
        p=self.folder/'one.mp4';p.write_bytes(b'fixture')
        collect(self.folder,self.timeline,self.plan[:1],search=lambda _:[Candidate('website','one','Fridge',20,640,360)],
            acquire=lambda *_:{'path':str(p),'duration':20,'width':640,'height':360})
        chosen=choose(self.root,self.folder,0,'one')
        self.assertEqual(chosen['slots'][0]['approval']['method'],'explicit_user_choice')
        self.assertEqual(choose(self.root,self.folder,0,None)['slots'][0]['selected'],None)

    def test_interrupted_collection_retries_empty_groups_and_keeps_old_attempts(self):
        from hinglish_broll.website_review import collect
        from hinglish_broll.stock import Candidate
        import json
        def interrupted(query):
            if 'router' in query:raise KeyboardInterrupt()
            return []
        with self.assertRaises(KeyboardInterrupt):collect(self.folder,self.timeline,self.plan,search=interrupted,limit=1)
        old=json.loads((self.folder/'website-review.json').read_text('utf-8'))
        self.assertEqual(old['slots'][0]['status'],'no_results');self.assertEqual(old['state'],'stopped')
        clip=self.folder/'restored.mp4';clip.write_bytes(b'fixture')
        def found(query):return [Candidate('website',query,query,20,1080,1920)]
        bank=collect(self.folder,self.timeline,self.plan,search=found,limit=1,
            acquire=lambda *_:{'path':str(clip),'duration':20,'width':1080,'height':1920})
        self.assertEqual([len(s['options']) for s in bank['slots']],[1,1])
        self.assertEqual(bank['slots'][0]['previous_attempts'],old['slots'][0]['attempts'])

    def test_search_follows_bounded_same_site_redirects_but_never_external_destinations(self):
        from hinglish_broll.website_review import _html
        from unittest.mock import MagicMock
        first=MagicMock();first.is_redirect=True;first.headers={'Location':'/free-stock-video/discover/small-table/'}
        second=MagicMock();second.is_redirect=False;second.encoding='utf-8';second.iter_content.return_value=[b'<html>results</html>']
        session=MagicMock();session.get.side_effect=[first,second]
        first.__enter__.return_value=first;second.__enter__.return_value=second
        self.assertEqual(_html(session,'https://mixkit.co/free-stock-video/small-table/'),'<html>results</html>')
        first.headers={'Location':'http://127.0.0.1/private'};session.get.side_effect=[first]
        with self.assertRaises(ValueError):_html(session,'https://mixkit.co/free-stock-video/small-table/')

    def test_live_page_updates_do_not_truncate_the_file_a_browser_is_reading(self):
        from hinglish_broll.website_review import new_bank,write_page
        page=self.folder/'report.html';page.write_text('old complete page',encoding='utf-8')
        original=Path.write_text
        def write(path,*args,**kwargs):
            self.assertNotEqual(path,page,'Live report must be replaced atomically, never truncated in place')
            self.assertEqual(page.read_text('utf-8'),'old complete page')
            return original(path,*args,**kwargs)
        with patch.object(Path,'write_text',write):write_page(self.folder,new_bank(self.timeline,self.plan))
        self.assertIn('keyword moments',page.read_text('utf-8'))

    def test_retired_api_hook_cannot_run_any_callback(self):
        from hinglish_broll.website_review import collect
        events=[]
        def api(query):
            events.append(('api',query));return []
        def website(query):events.append(('website',query));return []
        with self.assertRaisesRegex(ValueError,'API search is disabled'):
            collect(self.folder,self.timeline,self.plan,api_search=api,search=website)
        self.assertEqual(events,[])

    def test_website_collection_never_uses_provider_api_clients(self):
        from hinglish_broll.website_review import collect
        with patch('hinglish_broll.stock.PexelsClient.search',side_effect=AssertionError('API called')) as pexels, \
             patch('hinglish_broll.stock.PixabayClient.search',side_effect=AssertionError('API called')) as pixabay:
            bank=collect(self.folder,self.timeline,self.plan[:1],search=lambda _:[])
        pexels.assert_not_called();pixabay.assert_not_called()
        self.assertEqual(bank['state'],'complete')

    def test_page_is_manual_review_only_with_all_slots_and_compact_ae_control(self):
        from hinglish_broll.website_review import collect
        collect(self.folder,self.timeline,self.plan,search=lambda _:[])
        page=(self.folder/'report.html').read_text('utf-8')
        self.assertIn('2 keyword moments',page);self.assertIn('After Effects',page)
        self.assertIn('You review and choose',page);self.assertIn('Wi Fi?',page)
        self.assertNotIn('AI-approved',page);self.assertNotIn('Premiere Pro',page)

    def test_normal_review_run_defaults_to_websites_before_loading_vision(self):
        import inspect
        from hinglish_broll import pipeline
        signature=inspect.signature(pipeline.run)
        self.assertTrue(signature.parameters['website_review'].default)
        source=inspect.getsource(pipeline.run)
        self.assertLess(source.index('return finish_plans('),source.index('from .vision import Vision'))
        root=Path(__file__).resolve().parents[1]
        self.assertIn('brollSearchMethod',(root/'hinglish_app/static/index.html').read_text('utf-8'))
        self.assertNotIn("command.append('--strict-vision-review')",(root/'hinglish_app/server.py').read_text('utf-8'))

    def test_website_http_only_uses_saved_options_and_current_ae_context(self):
        from types import SimpleNamespace
        from hinglish_app.editor_panel_http import post
        context={'id':'ctx','host':'aftereffects','transport':'aftereffects_script'}
        panels=SimpleNamespace(contexts=SimpleNamespace(load=lambda _:context))
        handler=SimpleNamespace(_json=lambda status,value:(status,value))
        state=SimpleNamespace(root=self.root)
        manifest={'operation_id':'one'};receipt={'ok':True}
        with patch('hinglish_app.editor_panel_http.panel_service',return_value=panels), \
             patch('hinglish_app.editor_panel_http.ensure_license'), \
             patch('hinglish_broll.website_review.prepare_choice',return_value=manifest) as prepare, \
             patch('hinglish_app.broll_ae_direct.AfterEffectsDirect.invoke_choice',return_value=receipt), \
             patch('hinglish_app.timed_choice_delivery.TimedChoiceDelivery.accept',return_value=receipt):
            code,result=post(handler,state,'/api/panel/broll-website',{'action':'select','folder':str(self.folder),
                'host':'aftereffects','context_id':'ctx','slot_index':0,'source_id':'one'})
        self.assertEqual(code,200);self.assertEqual(result['status'],'confirmed')
        self.assertEqual(prepare.call_args.args[-1],context)

if __name__=='__main__':unittest.main()
