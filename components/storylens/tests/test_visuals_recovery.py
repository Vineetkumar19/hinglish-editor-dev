import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_visuals.recovery import checkpoint, context_key, resumable_projects
from hinglish_visuals.references import context_info
from hinglish_visuals.web import Entity, Web
from hinglish_visuals.websearch import WebSearch


class RecoveryTests(unittest.TestCase):
    def test_high_profile_article_is_not_a_player_profile(self):
        from hinglish_visuals.recovery import profile_source
        self.assertFalse(profile_source('https://www.cricinfo.com/story/ipl-2012-manvinder-bisla-high-profile-opportunity-566550'))
        self.assertTrue(profile_source('https://www.cricinfo.com/cricketers/manvinder-bisla-27280'))

    def test_worker_checkpoint_recovers_only_its_own_real_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'output/visuals/run/video';folder.mkdir(parents=True)
            marker=root/'cache/checkpoint.json'
            p={'slots':[{'options':[{'id':'kept'}]}]}
            with patch.dict('os.environ',{'STORYLENS_VISUALS_CHECKPOINT':str(marker)}):
                checkpoint(folder,p,'checking','Player')
                checkpoint(folder,p,'checking','Player')
            self.assertEqual(resumable_projects(marker,root),[folder/'visuals-project.json'])
            self.assertEqual(p['research_state']['checked_options'],1)
            record=json.loads(marker.read_text('utf-8'))
            self.assertEqual(len(record['projects']),1)
            record['projects'].append(str(root/'outside/visuals-project.json'))
            marker.write_text(json.dumps(record))
            self.assertEqual(len(resumable_projects(marker,root)),1)

    def test_check_reuse_invalidates_when_team_or_logo_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            logo=Path(tmp)/'logo';logo.write_bytes(b'one')
            info={'name':'Rohit','required_team':'MI','team_reference':str(logo)}
            before=context_key(info)
            self.assertNotEqual(before,context_key({**info,'required_team':'India'}))
            logo.write_bytes(b'two')
            self.assertNotEqual(before,context_key(info))

    def test_identity_fallback_inherits_team_from_its_fact_request_queries(self):
        player=Entity('p','Suresh Raina','person').to_dict()
        team=Entity('csk','Chennai Super Kings','brand',aliases=['CSK']).to_dict()
        slot={'entity':'p','label':'Suresh Raina','show':'photo','category':'person',
            'visual':'Suresh Raina photo','queries':['Suresh Raina photo'],'text':'Raina',
            'meaning':'Raina','reference_type':'identity'}
        fact={**slot,'reference_type':'evidence','queries':['Suresh Raina Chennai Super Kings 71 runs']}
        project={'summary':{'topic':'IPL'},'entities':{'p':player,'csk':team},'slots':[slot,fact]}
        self.assertEqual(context_info(slot,project)['required_team'],'Chennai Super Kings')

    def test_external_search_budget_does_not_block_cached_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            finder=WebSearch(tmp)
            finder._cached('test','saved',lambda:['saved source'])
            finder.begin_subject(seconds=-1)
            self.assertEqual(finder._cached('test','saved',lambda:self.fail()),['saved source'])
            with self.assertRaises(TimeoutError):finder._cached('test','new',lambda:self.fail())

    def test_wikimedia_retry_after_cannot_hold_the_run_for_hours(self):
        with tempfile.TemporaryDirectory() as tmp:
            from types import SimpleNamespace
            session=SimpleNamespace(headers={},get=lambda *a,**kw:SimpleNamespace(status_code=429,headers={'Retry-After':'3600'}))
            web=Web(tmp,session=session);web.begin_subject()
            with self.assertRaisesRegex(RuntimeError,'asked us to wait'):web.get('https://example.com',{})

    def test_service_restores_interrupted_research_but_caps_crash_retries(self):
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'output/visuals/run/video/visuals-project.json'
            project.parent.mkdir(parents=True);project.write_text('{}')
            jobs=root/'cache/app/visuals-jobs/8768';jobs.mkdir(parents=True)
            for name,attempts in [('once',1),('twice',2)]:
                (jobs/(name+'.json')).write_text(json.dumps({'id':name,'status':'running','attempts':attempts,
                    'visuals_project':str(project)}))
            with patch.object(AppState,'_start_visuals_research') as start:
                state=AppState(root,8768)
            start.assert_called_once_with('once',project.resolve())
            self.assertEqual(state.jobs['twice']['status'],'failed')
            # A different workspace port must not start this work again.
            with patch.object(AppState,'_start_visuals_research') as start:
                AppState(root,8765)
            start.assert_not_called()

    def test_uncertain_face_requires_a_positive_profile_comparison_and_correct_team(self):
        from PIL import Image
        from hinglish_visuals.evaluator import Evaluator
        class Model:
            name='local vision'
            def __init__(self,match):self.match=match
            def look(self,images,system,schema=None,prompt=None):
                if schema:
                    if 'same_person' in schema['properties']:return {'same_person':self.match,'reason':'Face comparison'}
                    return {'team':'India','confidence':'clear'}
                return {'category_ok':True,'identity':'unsure','fits_moment':True,'quality_ok':True,'seen':'a player'}
        with tempfile.TemporaryDirectory() as tmp:
            profile=Path(tmp)/'profile.png';Image.new('RGB',(120,120)).save(profile)
            info={'name':'Player','kind':'person','show':'photo','category':'person','visual':'player photo',
                'strict_context':True,'identity_reference':str(profile),'identity_reference_source':'publisher profile'}
            for match,expected in [('yes',True),('no',False),('unsure',False)]:
                self.assertEqual(Evaluator(Model(match))._check([Image.new('RGB',(500,500))],info,'picture','photo').passed,expected)
            info.update(required_team='KKR',team_aliases=['KKR'])
            self.assertFalse(Evaluator(Model('yes'))._check([Image.new('RGB',(500,500))],info,'picture','photo').passed)

    def test_misspelling_leads_need_source_and_entity_confirmation(self):
        from types import SimpleNamespace
        from hinglish_visuals.planner import resolve_entity
        class Brain:
            def json(self,system,data,schema,**kw):
                if 'names' in schema['properties']:return {'names':['Jacques Kallis','Manvinder Bisla']}
                if 'name' in schema['properties']:return {'name':'Jacques Kallis'}
                return {'id':'Q1'}
        class Web:
            def search_entities(self,name):
                return [{'id':'Q1','label':'Jacques Kallis','description':'South African cricketer'}] if name=='Jacques Kallis' else []
            def entity(self,key,name,kind,qid):return Entity(key,name,kind,qid,label='Jacques Kallis')
        with patch('hinglish_visuals.reach.search',return_value=[{'title':'Jacques Kallis IPL profile','text':'Jacques Kallis'}]) as search:
            found=resolve_entity(Brain(),Web(),{'key':'p','name':'jaykaalis','kind':'person','about':'cricketer'},
                {'topic':'IPL final'},SimpleNamespace(root='.'))
        self.assertEqual(found.label,'Jacques Kallis')
        self.assertTrue(any('Jacques Kallis' in call.args[1] for call in search.call_args_list))
        self.assertFalse(any('Manvinder Bisla' in call.args[1] for call in search.call_args_list))

    def test_compact_picker_groups_photo_and_evidence_without_removing_provenance(self):
        from hinglish_visuals.report import write_report
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'report.html'
            slot={'index':0,'entity':'p','label':'Player','start':1.,'end':3.,'text':'spoken words',
                'visual':'Player team photo','queries':['Player team photo'],'options':[],
                'reference_type':'identity','clip':None,'rejected':[]}
            project={'review_options':True,'timeline':{'name':'0000-123456abcdef-Shorts 12 · audio on black'},
                'brain':'Ollama storylens-meaning:14b','slots':[slot,{**slot,'index':1,'reference_type':'evidence'}]}
            write_report(file,project)
            page=file.read_text('utf-8')
            self.assertIn('Find more',page);self.assertIn('Save &amp; rebuild',page)
            self.assertIn('14B',page);self.assertIn('2</b> keywords',page)
            self.assertEqual(page.count('<h2>Player</h2>'),1)
            self.assertNotIn('<audio',page)
            self.assertNotIn('No visual selected for this moment',page)
            self.assertIn('spoken words',page)  # kept in expandable research details
            self.assertIn('data-slot="0"',page);self.assertIn('data-slot="1"',page)

    def test_profile_reference_requires_named_profile_and_named_image(self):
        from PIL import Image
        from types import SimpleNamespace
        from hinglish_visuals.references import profile_reference
        from hinglish_visuals.web import Media
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'headshot.png';Image.new('RGB',(120,120)).save(image)
            entity=Entity('p','Manvinder Bisla','person','Q1',label='Manvinder Bisla')
            entry={'entity':'p','visual':'Manvinder Bisla photo','reference_type':'identity'}
            project={'entities':{'p':entity.to_dict()}}
            related=Media('image','web','bad','Related image','https://example.com/unrelated.png',
                page_url='https://sports.ndtv.com/cricket/players/manvinder-bisla-playerprofile')
            named=Media('image','web','good','Profile','https://s.ndtvimg.com/manvinder-bisla.png',
                page_url=related.page_url)
            with patch('hinglish_visuals.pipeline.fetch',return_value=image) as fetch:
                profile_reference(tmp,entry,project,[related,named],SimpleNamespace(session=None),None)
            fetch.assert_called_once();self.assertEqual(fetch.call_args.args[1].id,'good')
            self.assertEqual(project['identity_references']['p']['source'],named.page_url)

    def test_publisher_profile_headshot_can_use_a_numeric_cdn_filename(self):
        from PIL import Image
        from types import SimpleNamespace
        from hinglish_visuals.references import profile_reference
        from hinglish_visuals.web import Media
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'headshot.png';Image.new('RGB',(320,320)).save(image)
            entity=Entity('p','Manvinder Bisla','person','Q1',label='Manvinder Bisla')
            project={'entities':{'p':entity.to_dict()}}
            media=Media('image','web','profile','Manvinder Bisla Profile - Cricket Player',
                'https://img1.hscicdn.com/image/upload/399236.2.png',
                page_url='https://www.cricinfo.com/cricketers/manvinder-bisla-27280')
            with patch('hinglish_visuals.pipeline.fetch',return_value=image):
                profile_reference(tmp,{'entity':'p','visual':'photo','reference_type':'identity'},project,[media],SimpleNamespace(session=None),None)
            self.assertIn('p',project['identity_references'])

    def test_rebuild_cannot_overwrite_research_that_is_still_running(self):
        import threading
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'output/visuals/run/video/visuals-project.json'
            file.parent.mkdir(parents=True);file.write_text('{"kept": true}')
            app=AppState(root,8768);ready=threading.Event();release=threading.Event()
            def work():
                with app.work_lock:ready.set();release.wait(3)
            thread=threading.Thread(target=work);thread.start();self.assertTrue(ready.wait(2))
            try:
                with self.assertRaisesRegex(ValueError,'selections are kept'):
                    app.rebuild_visuals({'project_path':str(file),'choices':{'0':''}})
                self.assertEqual(json.loads(file.read_text()),{'kept':True})
            finally:release.set();thread.join(3)

    def test_library_exit_marks_research_failed_instead_of_leaving_it_running(self):
        from hinglish_app.server import AppState
        class InlineThread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'output/visuals/run/video/visuals-project.json'
            file.parent.mkdir(parents=True);file.write_text('{"kept": true}')
            app=AppState(root,8768)
            app.jobs['test']={'id':'test','status':'queued','logs':[],'visuals_project':str(file)}
            with patch('hinglish_app.server.threading.Thread',InlineThread),patch('hinglish_visuals.references.recheck_project',side_effect=SystemExit('local worker exited')):
                app._start_visuals_research('test',file)
            self.assertEqual(app.jobs['test']['status'],'failed')
            self.assertEqual(json.loads(file.read_text()),{'kept':True})


if __name__=='__main__':unittest.main()
