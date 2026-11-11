import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from hinglish_niche.profiles import Profiles, account_key, inject, use
from hinglish_niche.research import fetch, usable_context, allowed_url
from hinglish_niche.gaming import select, validate_moments, approved_memes, render, signals
from hinglish_app.assistant_plan import quick_plan
from hinglish_app.server import AppState
from hinglish_cut.model import Word
from hinglish_broll.phrases import Phrase
from hinglish_publish.store import Store, IST
from hinglish_publish.memory import CreatorMemory
from hinglish_publish.service import Publisher

class ProfileTests(unittest.TestCase):
    def test_general_context_is_identical_and_preferences_are_isolated(self):
        with tempfile.TemporaryDirectory() as root:
            profiles=Profiles(root)
            profiles.save('gaming', {'feedback':'Funny edits', 'topic':'Minecraft'})
            self.assertEqual(profiles.context()['profile'],'general')
            self.assertEqual(profiles.context('cricket')['feedback'],'')
            self.assertEqual(profiles.context('gaming')['feedback'],'Funny edits')
            system,data='Exact existing prompt',{'input':123}
            with use(profiles.context('general')):
                self.assertEqual(inject(system,data),(system,data))
            with use(profiles.context('gaming')):
                new,context=inject(system,data)
                self.assertIn('gaming',context['creator_profile']['profile'])
                self.assertEqual(context['input'],123)
            self.assertEqual(inject(system,data),(system,data))

    def test_niche_memory_cannot_change_general(self):
        with tempfile.TemporaryDirectory() as root:
            with use(Profiles(root).context('gaming')):
                CreatorMemory(root).add({'scope':'title','want':'Comedy hooks'})
            self.assertEqual(CreatorMemory(root).list(),[])
            self.assertEqual(CreatorMemory(root,'cricket').list(),[])
            self.assertEqual(len(CreatorMemory(root,'gaming').list()),1)

    def test_implicit_job_remains_general_when_saved_selection_is_gaming(self):
        with tempfile.TemporaryDirectory() as root:
            Profiles(root).save('gaming')
            source=Path(root)/'sample.mp4';source.write_bytes(b'video')
            state=AppState(root);seen=[];done=threading.Event()
            def runner(*args): seen.append(args[1]);done.set()
            with patch.object(state,'_run_job',side_effect=runner):
                state.create_job({'mode':'clean','source_paths':[str(source)]})
                self.assertTrue(done.wait(2))
            self.assertEqual(seen[0]['profile'],'general')
            self.assertEqual(seen[0]['_creator_context']['profile'],'general')

    def test_profile_rejects_unknown_fields_and_names(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError): Profiles(root).save('unknown')
            with self.assertRaises(ValueError): Profiles(root).save('gaming',{'shell':'run'})
            with self.assertRaises(ValueError): account_key('youtube','../other')
            self.assertEqual(account_key('youtube'),'youtube')
            self.assertEqual(account_key('instagram','cricket'),'instagram-cricket')

class ResearchTests(unittest.TestCase):
    def test_private_urls_and_redirect_targets_are_rejected(self):
        for url in ['http://icc-cricket.com/a','https://127.0.0.1/a','https://icc-cricket.com.evil.org/a','https://user:pass@icc-cricket.com/a','https://icc-cricket.com:8767/a']:
            self.assertFalse(allowed_url(url))
        self.assertTrue(allowed_url('https://www.cricket.or.jp/en/'))

    def test_stale_scores_are_removed(self):
        receipt={'retrieved_at':100,'matches':[{'score':'123'}],'sources':[{'text':'old'}]}
        stale=usable_context(receipt,now=2000)
        self.assertEqual(stale['matches'],[])
        self.assertEqual(stale['sources'],[])
        self.assertEqual(receipt['matches'],[{'score':'123'}])

    def test_no_keys_is_explicit_and_does_not_invent_facts(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'','CRICKETDATA_API_KEY':''}):
            Profiles(root).save('cricket',{'topic':'Match tonight'})
            client=Mock();receipt=fetch(root,'cricket',session=client)
            client.get.assert_not_called()
            self.assertEqual(receipt['matches'],[])
            self.assertTrue(receipt['warnings'])

    def test_current_match_list_has_no_selected_score_context(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'','CRICKETDATA_API_KEY':'fake'}):
            Profiles(root).save('cricket',{'topic':'India match'})
            client=Mock();client.get.return_value.json.return_value={'status':'success','data':[{'id':'one','name':'India vs Test','score':[{'r':100}],'date':'2026-10-04'}]}
            fetch(root,'cricket',session=client)
            with use(Profiles(root).context('cricket')):
                _,data=inject('Prompt',{})
            self.assertNotIn('score',data['creator_profile']['research']['matches'][0])
            raw=(Path(root)/'cache/niche/cricket-research.json').read_text()
            self.assertNotIn('fake',raw)

    def test_selected_match_receipt_contains_id_and_scores(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'','CRICKETDATA_API_KEY':'fake'}):
            Profiles(root).save('cricket',{'topic':'India match','match_id':'exact-id'})
            client=Mock();client.get.return_value.json.return_value={'status':'success','data':{'id':'exact-id','score':[{'r':100}]}}
            receipt=fetch(root,'cricket',session=client)
            self.assertEqual(receipt['selected_match_id'],'exact-id')
            self.assertEqual(client.get.call_args.kwargs['params']['id'],'exact-id')
            self.assertTrue(receipt['matches'][0]['score'])

    def test_changing_topic_drops_prior_research(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'','CRICKETDATA_API_KEY':''}):
            p=Profiles(root);p.save('cricket',{'topic':'Old match'});fetch(root,'cricket',session=Mock())
            p.save('cricket',{'topic':'New match'})
            self.assertNotIn('research',p.context('cricket'))

    def test_changed_match_id_drops_old_scorecard_even_with_same_topic(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'','CRICKETDATA_API_KEY':'fake'}):
            p=Profiles(root);p.save('cricket',{'topic':'India match','match_id':'old-id'})
            client=Mock();client.get.return_value.json.return_value={'status':'success','data':{'id':'old-id','score':[{'r':100}]}}
            fetch(root,'cricket',session=client)
            p.save('cricket',{'match_id':'new-id'})
            self.assertNotIn('research',p.context('cricket'))

    def test_provider_cannot_substitute_a_different_match(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'','CRICKETDATA_API_KEY':'fake'}):
            Profiles(root).save('cricket',{'topic':'India match','match_id':'requested'})
            client=Mock();client.get.return_value.json.return_value={'status':'success','data':{'id':'different','score':[{'r':999}]}}
            receipt=fetch(root,'cricket',session=client)
            self.assertEqual(receipt['matches'],[])
            self.assertNotIn('selected_match_id',receipt)

class QueueTests(unittest.TestCase):
    def test_duplicate_identity_and_daily_slots_are_separate_by_channel(self):
        with tempfile.TemporaryDirectory() as root:
            queue=Store(root);now=datetime(2026,10,4,12,tzinfo=IST).timestamp()
            base={'fingerprint':'same-content','platform':'youtube','kind':'short'}
            batch=[{**base,'profile':p} for p in ('general','cricket','gaming')]
            ids=queue.add_batch(batch,now=now)
            self.assertEqual(len(set(ids)),3)
            self.assertEqual(len({queue.get(j)['due'] for j in ids}),1)
            self.assertEqual(ids,queue.add_batch(batch,now=now))
            more=queue.add_batch([{**base,'fingerprint':'next','profile':'gaming'}],now=now)[0]
            self.assertEqual(queue.get(more)['due']-queue.get(ids[2])['due'],86400)

    def test_authorization_never_falls_back_to_general_accounts(self):
        with tempfile.TemporaryDirectory() as root:
            publisher=Publisher(root)
            meta={'title':'Test Title','description':'Test description','instagram_caption':'A caption','tags':['Test']}
            job=publisher.store.add_batch([{'fingerprint':'x','platform':'youtube','kind':'long','metadata':meta,'profile':'gaming'}])[0]
            def account_load(root,key):
                if key=='youtube': return {'channel_id':'general','name':'General'}
                raise RuntimeError('Not connected')
            with patch('hinglish_publish.service.secrets.load',side_effect=account_load):
                with self.assertRaises(ValueError): publisher.authorize({'ids':[job],'authorize':True,'made_for_kids':False,'synthetic_media':False})
            self.assertEqual(publisher.store.get(job)['status'],'draft')

    def test_folders_settings_and_enabled_queue_stay_in_selected_profile(self):
        with tempfile.TemporaryDirectory() as root:
            publisher=Publisher(root)
            publisher.settings({'daily_time':'20:15','enabled':True},profile='gaming')
            self.assertEqual(publisher.settings()['daily_time'],'19:00')
            self.assertFalse(publisher.settings()['enabled'])
            self.assertEqual(publisher.settings(profile='cricket')['daily_time'],'19:00')
            publisher.init_folders('gaming')
            self.assertTrue((Path(root)/'publishing/gaming/long-youtube').is_dir())
            self.assertFalse((Path(root)/'publishing/cricket/long-youtube').exists())
            ids=publisher.store.add_batch([{'fingerprint':p,'platform':'youtube','kind':'long','profile':p} for p in ('general','gaming')],now=1)
            for item in ids: publisher.store.change(item,status='ready')
            claimed=publisher.store.claim(time.time(),['gaming'])
            self.assertEqual(claimed['profile'],'gaming')
            self.assertEqual(publisher.store.get(ids[0])['status'],'ready')

    def test_paused_profile_is_not_verified_when_another_worker_is_enabled(self):
        with tempfile.TemporaryDirectory() as root:
            provider=Mock();publisher=Publisher(root,{'youtube':provider})
            publisher.settings({'enabled':True},profile='gaming')
            jid=publisher.store.add_batch([{'fingerprint':'x','platform':'youtube','kind':'long','profile':'cricket'}],now=1)[0]
            publisher.store.change(jid,status='scheduled',due=1)
            self.assertIsNone(publisher.tick())
            provider.assert_not_called()

class GamingTests(unittest.TestCase):
    def test_bundle_routes_to_two_tools_without_full_stream_clean(self):
        plan=quick_plan('Make 12 Shorts from my gaming stream, then create a 15-minute gaming highlights compilation.')
        self.assertEqual([s['tool'] for s in plan['steps']],['shorts','gaming'])
        self.assertEqual(plan['steps'][1]['options']['target_minutes'],15)

    def test_moment_ids_lengths_and_scores_are_checked(self):
        words=[Word('setup',0,5),Word('payoff',5,15)]
        lines=[Phrase(0,0,5,'Setup happens'),Phrase(1,5,15,'Funny payoff happens')]
        base={'first':0,'last':1,'score':8,'title':'Funny Payoff','kind':'funny','reason':'A reaction'}
        good=validate_moments([base],lines,words,15)
        self.assertEqual(len(good),1)
        for changes in [{'last':99},{'score':11},{'first':True},{'kind':'invented'}]:
            self.assertEqual(validate_moments([{**base,**changes}],lines,words,15),[])
        self.assertEqual(validate_moments([base],lines,words,4),[])

    def test_best_nonoverlapping_moments_stay_in_source_order(self):
        def m(a,b,s):return {'start':a,'end':b,'score':s}
        chosen=select([m(10,30,9),m(15,35,8),m(40,60,7),m(70,90,5)],40)
        self.assertEqual(chosen,[m(10,30,9),m(40,60,7)])
        self.assertEqual(select([m(0,60,9)],30),[])

    def test_gaming_moment_selection_uses_bounded_local_responses(self):
        from hinglish_niche.gaming import candidates
        brain=Mock();brain.json.return_value={'moments':[{'first':0,'last':1,'score':8,
            'title':'Unexpected reaction','kind':'funny','reason':'The transcript contains a setup and reaction.'}]}
        moments=candidates(brain,[Word('setup',0,4),Word('reaction',5,15)],20,{},lambda _:None)
        self.assertEqual(len(moments),1)
        self.assertFalse(brain.json.call_args.kwargs['think'])

    def test_oversized_gaming_section_splits_and_keeps_every_source_line(self):
        from hinglish_niche.gaming import candidates
        import requests
        response=requests.Response();response.status_code=400;response._content=b'request exceeds context size'
        brain=Mock();brain.json.side_effect=[requests.HTTPError(response=response),{'moments':[]},{'moments':[]}]
        candidates(brain,[Word('setup',0,4),Word('reaction',5,15)],20,{},lambda _:None)
        self.assertEqual(brain.json.call_count,3)
        original=brain.json.call_args_list[0].args[1]['transcript']
        retried='\n'.join(call.args[1]['transcript'] for call in brain.json.call_args_list[1:])
        self.assertTrue(all(line in retried for line in original.splitlines()))

    def test_unapproved_or_escaping_meme_files_are_not_used(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)/'library/creator-memes';base.mkdir(parents=True)
            (base/'good.mp4').write_bytes(b'video');(Path(root)/'escape.mp4').write_bytes(b'video')
            (base/'manifest.json').write_text(json.dumps({'assets':[{'file':'good.mp4','approved':True,'rights':'owned','tags':['funny']},{'file':'../../../escape.mp4','approved':True,'rights':'licensed'},{'file':'good.mp4','approved':False,'rights':'owned'}]}))
            self.assertEqual(len(approved_memes(root)),1)

    def test_real_render_preserves_stereo_and_exports_timeline(self):
        import subprocess
        from imageio_ffmpeg import get_ffmpeg_exe
        from hinglish_shorts.source import open_video
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source.mp4'
            subprocess.run([get_ffmpeg_exe(),'-y','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=60:d=3','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-ac','2','-c:v','libx264','-threads','2','-c:a','aac','-shortest',str(source)],check=True)
            video=open_video(source);cues=signals(root,video,lambda _:None)
            self.assertTrue(cues['audio'])
            folder=Path(root)/'render';folder.mkdir()
            target,_=render(root,video,[{'start':.2,'end':2.2,'kind':'funny'}],folder,False,lambda _:None)
            facts=open_video(target)
            self.assertEqual((facts.width,facts.height,facts.fps,facts.channels),(320,180,60,2))
            self.assertAlmostEqual(facts.duration,2,delta=.1)
            self.assertTrue((folder/'GAMING_SEQUENCE.xml').exists())

class ThumbnailTests(unittest.TestCase):
    def test_bounded_thumbnail_planning_can_disable_optional_thinking(self):
        from hinglish_visuals.brain import OllamaBrain
        with tempfile.TemporaryDirectory() as folder:
            brain=object.__new__(OllamaBrain)
            brain.root=brain.cache=Path(folder);brain.model='selected:9b';brain.name='Ollama selected:9b';brain.url='http://127.0.0.1:11434'
            brain.session=Mock();response=brain.session.post.return_value
            response.status_code=200;response.json.return_value={'message':{'content':'{}'}}
            with patch('hinglish_cut.model_preferences.preferences',return_value={'planning_model':'selected:9b','planning_think':True}), \
                 patch('hinglish_niche.profiles.inject',side_effect=lambda system,data,**kw:(system,data)):
                brain.json('plan',{'story':'one'},{},think=False)
                self.assertFalse(brain.session.post.call_args.kwargs['json']['think'])
                brain.json('plan',{'story':'two'},{})
                self.assertTrue(brain.session.post.call_args.kwargs['json']['think'])

    def test_cpu_thumbnail_options_render_without_diffusion(self):
        from PIL import Image
        from hinglish_niche.thumbnail import run
        with tempfile.TemporaryDirectory() as root:
            background=Path(root)/'photo.png'
            Image.new('RGB',(1280,720),'#23608c').save(background)
            brain=Mock();brain.json.return_value={'concepts':[{'hook':t,'background_prompt':'A stadium with no text'} for t in ('The Great Comeback','A New Era','The Last Over')]}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain),use(Profiles(root).context('cricket')):
                page=run(root,'A cricket comeback story',background=background,generate=False,progress=lambda _:None)
            self.assertEqual(len(list(page.parent.glob('thumbnail-*.png'))),3)
            with Image.open(page.parent/'thumbnail-1.png') as image:self.assertEqual(image.size,(1280,720))
            project=json.loads((page.parent/'thumbnail-project.json').read_text())
            self.assertFalse(project['ai_backgrounds'])
            brain.close.assert_called_once()

    def test_no_images_cannot_be_reported_as_a_finished_thumbnail(self):
        from hinglish_niche.thumbnail import run
        with tempfile.TemporaryDirectory() as root,patch('hinglish_visuals.brain.open_brain') as brain:
            with self.assertRaisesRegex(ValueError,'needs imagery'):
                run(root,'A cricket story',generate=False)
            brain.assert_not_called()

    def test_saved_subjects_recover_cricket_profile_and_validate_verified_hooks(self):
        from PIL import Image
        from hinglish_niche.thumbnail import run
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'library/thumbnail-styles/mi';folder.mkdir(parents=True)
            Image.new('RGBA',(200,300),'blue').save(folder/'players.png')
            hooks=['CHAMPIONS AGAIN','THE FIFTH TITLE','BLUE GOLD DYNASTY']
            (folder/'style.json').write_text(json.dumps({'id':'mi','profile':'cricket',
                'match_all':['mumbai indians','2020'],'subjects':'players.png',
                'hook_choices':hooks,'verified_facts':['Fifth title.']}))
            brain=Mock();brain.json.return_value={'concepts':[{'hook':h,'background_prompt':'stadium'} for h in hooks]}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain),use({'profile':'gaming'}):
                page=run(root,'Mumbai Indians 2020 IPL journey',generate=False)
            data=json.loads((page.parent/'thumbnail-project.json').read_text())
            self.assertEqual((data['profile'],data['reference_style']),('cricket','mi'))
            self.assertFalse(brain.json.call_args.kwargs['think'])
            self.assertEqual(brain.json.call_args.args[1]['reference_guidance']['verified_facts'],['Fifth title.'])
            brain.json.return_value['concepts'][0]['hook']='THE LAST OVER'
            with patch('hinglish_visuals.brain.open_brain',return_value=brain):
                with self.assertRaisesRegex(ValueError,'verified reference claim'):
                    run(root,'Mumbai Indians 2020 IPL journey',generate=False)
