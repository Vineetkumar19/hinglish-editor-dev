"""Manual website-review controller fixtures, never real-model acceptance."""
import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from hinglish_visuals.web import Media,Entity
from hinglish_visuals.manual_web import collect,resume


def project():
    return {'version':2,'search_method':'website','review_policy':'human','review_options':True,
        'options_per_moment':2,'timeline':{'name':'Owner speech','fps':'30','duration':15.,'width':720,'height':1280,'xml_path':'fixture.xml'},
        'brain':'synthetic local-planner fixture','summary':{},'entities':{'z':Entity('z','Zomato','brand').to_dict()},
        'slots':[{'index':0,'start':1.2,'end':3.4,'text':'Maine Zomato se khana mangaya','quote':'Zomato',
            'meaning':'Ordering food from Zomato','entity':'z','label':'Zomato','show':'logo','display':'popup',
            'category':'logo','visual':'Zomato logo PNG','queries':['Zomato logo png','Zomato food delivery logo'],
            'reference_type':'identity','evidence_terms':[],'options':[],'alternatives':[],'rejected':[],
            'chosen':None,'clip':None,'evaluation':None}]}


class Finder:
    def __init__(self,interrupt=False):self.queries=[];self.downloads=[];self.interrupt=interrupt
    def begin_subject(self):pass
    def images(self,query,limit,transparent=False):
        self.queries.append(query)
        return [Media('image','web',str(i),'Zomato '+str(i),'https://images.test/'+str(i)+'.png',
            page_url='https://source.test/'+str(i),width=300,height=200,text='Source description') for i in range(5)]
    def download_image(self,media,target):
        self.downloads.append(media.id)
        if self.interrupt and len(self.downloads)==2:raise KeyboardInterrupt()
        if media.id=='2':target.write_text('not an image');return target
        Image.new('RGB',(300,200),(30+int(media.id)*35,40,90)).save(target,format='PNG')
        return target


class ManualWebTests(unittest.TestCase):
    def test_collects_valid_distinct_raw_files_without_vision_or_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'review';folder.mkdir();p=project();original=copy.deepcopy(p['slots'][0]);finder=Finder()
            with patch('hinglish_visuals.pipeline.write_outputs'),                  patch('hinglish_visuals.evaluator.open_evaluator',side_effect=AssertionError('no Vision')):
                collect(root,[(None,folder,p)],finder,SimpleNamespace(options_per_moment=2),lambda _:None)
            saved=json.loads((folder/'visuals-project.json').read_text('utf-8'));s=saved['slots'][0]
            self.assertEqual(len(s['options']),2);self.assertEqual((s['start'],s['end']),(original['start'],original['end']))
            self.assertIsNone(s['chosen']);self.assertIsNone(s['clip'])
            for o in s['options']:
                self.assertIsNone(o['evaluation']['passed']);self.assertTrue(o['requires_human_review'])
                self.assertTrue(o['file_validation']['passed']);self.assertTrue((folder/o['asset']).is_file())
                self.assertEqual(o['page_url'],'https://source.test/'+o['id'])
            self.assertEqual(saved['review_policy'],'human');self.assertFalse(saved['vision_checked'])
            self.assertNotIn('api_key',str(finder.queries))
            from hinglish_visuals.source_bank import build_source_bank,selected_source_assets
            bank=build_source_bank(folder/'visuals-project.json',{'0':s['options'][0]['id']})
            self.assertEqual(len(bank['banks'][0]['choices']),2)
            self.assertEqual(len(selected_source_assets(bank,folder/'visuals-project.json')),1)
            self.assertTrue(bank['banks'][0]['choices'][0]['verification']['requires_human_review'])
            self.assertFalse(bank['banks'][0]['choices'][0]['verification']['vision_checked'])
            p['search_method']='verified';(folder/'visuals-project.json').write_text(json.dumps(p))
            strict=build_source_bank(folder/'visuals-project.json')
            self.assertEqual(strict['banks'][0]['choices'],[])

    def test_website_marker_cannot_relabel_a_negative_visual_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);p=project()
            with patch('hinglish_visuals.pipeline.write_outputs'):collect(folder,[(None,folder,p)],Finder(),SimpleNamespace(options_per_moment=2),lambda _:None)
            p['slots'][0]['options'][0]['evaluation']['passed']=False
            (folder/'visuals-project.json').write_text(json.dumps(p))
            from hinglish_visuals.source_bank import build_source_bank
            self.assertEqual(len(build_source_bank(folder/'visuals-project.json')['banks'][0]['choices']),1)

    def test_interrupt_checkpoints_each_file_and_resume_never_replans(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'review';folder.mkdir();p=project();finder=Finder(interrupt=True)
            with patch('hinglish_visuals.pipeline.write_outputs'):
                with self.assertRaises(KeyboardInterrupt):collect(root,[(None,folder,p)],finder,SimpleNamespace(options_per_moment=2),lambda _:None)
            saved=json.loads((folder/'visuals-project.json').read_text('utf-8'))
            self.assertEqual(len(saved['slots'][0]['options']),1);self.assertEqual(saved['research_state']['stage'],'paused')
            second=Finder()
            with patch('hinglish_visuals.pipeline.write_outputs'),patch('hinglish_visuals.brain.open_brain',side_effect=AssertionError('no replanning')):
                resume(root,folder/'visuals-project.json',finder=second,progress=lambda _:None)
            saved=json.loads((folder/'visuals-project.json').read_text('utf-8'))
            self.assertEqual(len(saved['slots'][0]['options']),2);self.assertNotIn('0',second.downloads)
            from hinglish_visuals.source_result import ensure_source_result
            self.assertEqual(ensure_source_result(folder/'visuals-project.json')['schema'],'storylens.smart_visuals.source_bank')

    def test_find_more_advances_snapshot_and_preserves_explicit_human_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'review';folder.mkdir();p=project();file=folder/'visuals-project.json'
            with patch('hinglish_visuals.pipeline.write_outputs'):collect(root,[(None,folder,p)],Finder(),SimpleNamespace(options_per_moment=2),lambda _:None)
            from hinglish_visuals.source_result import ensure_source_result,apply_source_request
            desc=ensure_source_result(file)
            chosen=apply_source_request({'type':'smart_visuals.source_bank.select','version':1,'project_path':str(file),
                'base_manifest':desc['manifest_path'],'base_manifest_sha256':desc['manifest_sha256'],
                'choices':{'0':p['slots'][0]['options'][0]['id']}})
            with patch('hinglish_visuals.pipeline.write_outputs'):resume(root,file,finder=Finder(),find_more=True,progress=lambda _:None)
            current=ensure_source_result(file)
            from hinglish_visuals.source_bank import selected_source_assets
            manifest=json.loads(Path(current['manifest_path']).read_text('utf-8'))
            self.assertEqual(len(selected_source_assets(manifest,file)),1)
            self.assertNotEqual(current['manifest_sha256'],chosen['manifest_sha256'])
            self.assertTrue(Path(chosen['manifest_path']).is_file())

    def test_failed_files_dedup_and_tampered_bytes_are_not_approved(self):
        class Broken(Finder):
            def download_image(self,media,target):
                if media.id in ('0','1'):Image.new('RGB',(300,200),(30,40,50)).save(target,format='PNG');return target
                target.write_text('<html>Not a picture</html>');return target
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);p=project()
            with patch('hinglish_visuals.pipeline.write_outputs'):collect(folder,[(None,folder,p)],Broken(),SimpleNamespace(options_per_moment=2),lambda _:None)
            self.assertEqual(len(p['slots'][0]['options']),1);self.assertEqual(p['research_state']['stage'],'partial')
            self.assertTrue(p['slots'][0]['preparation_errors'])
            o=p['slots'][0]['options'][0];(folder/o['asset']).write_text('changed')
            from hinglish_visuals.source_bank import build_source_bank
            self.assertFalse(build_source_bank(folder/'visuals-project.json')['banks'][0]['choices'])

    def test_manual_report_never_claims_checked_or_approved_choices(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);p=project()
            with patch('hinglish_visuals.pipeline.write_outputs'):collect(folder,[(None,folder,p)],Finder(),SimpleNamespace(options_per_moment=2),lambda _:None)
            from hinglish_visuals.report import write_report
            write_report(folder/'report.html',p)
            html=(folder/'report.html').read_text('utf-8')
            self.assertIn('Human review',html);self.assertIn('choices to review',html)
            self.assertNotIn('checked choices',html);self.assertNotIn('No approved options',html)
            self.assertIn('src="/editor-handoff.js"',html)
            self.assertIn('location.origin',html)

    def test_production_run_wires_model_slots_to_manual_collector_only(self):
        from hinglish_visuals.pipeline import run
        from hinglish_visuals.planner import VisualMoment
        from hinglish_cut.model import Word
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'output/visuals/job/clip';folder.mkdir(parents=True)
            timeline=SimpleNamespace(name='Owner E5 fixture',duration=15.,warnings=[],orientation='portrait',
                width=720,height=1280,sources=lambda:['speech.mov'])
            words=[Word('I',.2,.5),Word('used',.5,.8),Word('Zomato',1.2,1.7)]
            moment=VisualMoment(0,'Zomato logo png',['Zomato logo png'],3,'Zomato','Food app','z','Zomato','logo','popup',category='logo')
            brain=SimpleNamespace(name='synthetic local planner')
            def timelines(r,source,out,fmt,progress):
                nonlocal folder
                folder=out/'clip';folder.mkdir(parents=True)
                return [(timeline,folder)]
            with patch('hinglish_visuals.pipeline.timelines_for',side_effect=timelines), \
                 patch('hinglish_visuals.pipeline.transcripts_for',return_value=({'speech.mov':words},[])), \
                 patch('hinglish_visuals.pipeline.timeline_words',return_value=words), \
                 patch('hinglish_visuals.pipeline.timeline_to_dict',return_value=project()['timeline']), \
                 patch('hinglish_visuals.pipeline.summarize',return_value={'topic':'Food apps','country':'India'}), \
                 patch('hinglish_visuals.pipeline.plan_visuals',return_value=([moment],{'z':{'name':'Zomato','kind':'brand','about':'Food app'}},['Food'])) as planner, \
                 patch('hinglish_visuals.pipeline.resolve_visual_entity',side_effect=AssertionError('no canonical substitution')), \
                 patch('hinglish_visuals.pipeline.open_evaluator',side_effect=AssertionError('no Vision')), \
                 patch('hinglish_visuals.pipeline.PexelsClient',side_effect=AssertionError('no stock API')), \
                 patch('hinglish_visuals.pipeline.PixabayClient',side_effect=AssertionError('no stock API')), \
                 patch('hinglish_visuals.pipeline.write_outputs'):
                result=run(root,root/'speech.mov',brain=brain,finder=Finder(),search_method='website',
                    review_options=True,options_per_moment=2)
            planner.assert_called_once()
            saved=json.loads((folder/'visuals-project.json').read_text('utf-8'))
            self.assertEqual(saved['search_method'],'website');self.assertFalse(saved['vision_checked'])
            self.assertEqual(saved['slots'][0]['start'],1.2)
            self.assertEqual(len(saved['slots'][0]['options']),2)
            self.assertEqual(result,folder/'report.html')

    def test_recovery_dispatch_uses_manual_resume_without_opening_models(self):
        from hinglish_visuals.references import recheck_project
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'output/visuals/job/clip';folder.mkdir(parents=True)
            file=folder/'visuals-project.json';file.write_text(json.dumps(project()))
            with patch('hinglish_visuals.manual_web.resume',return_value={'filled':2}) as continued, \
                 patch('hinglish_visuals.brain.open_brain',side_effect=AssertionError('no planner')), \
                 patch('hinglish_visuals.evaluator.open_evaluator',side_effect=AssertionError('no Vision')):
                self.assertEqual(recheck_project(file),{'filled':2})
            self.assertEqual(continued.call_args.args[0],root)

    def test_cli_dispatch_explicit_website_and_default_verified(self):
        import sys
        from hinglish_visuals.__main__ import main
        for flags,expected in [(['--search-method','website','--evaluator','off'],'website'),([], 'verified')]:
            with patch.object(sys,'argv',['visuals','--input','fixture.mov']+flags), \
                 patch('hinglish_visuals.__main__.run',return_value=Path('report.html')) as run:
                self.assertEqual(main(),0)
                self.assertEqual(run.call_args.kwargs['search_method'],expected)

    def test_manual_download_rejects_local_or_credential_urls_before_fetch(self):
        from hinglish_visuals.manual_web import _adopt
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);finder=Finder();slot=project()['slots'][0]
            for url in ['http://127.0.0.1/private.png','http://192.168.1.2/a.png','http://localhost/a.png',
                        'http://[::1]/a.png','https://user:secret@images.test/a.png']:
                media=Media('image','web','0','fixture',url,page_url='https://source.test/page')
                with self.assertRaises(ValueError):_adopt(folder,media,finder,slot)
            self.assertEqual(finder.downloads,[])

    def test_explicit_rebuild_rejects_changed_manual_source_before_render(self):
        from hinglish_visuals.pipeline import rebuild_project
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);p=project();file=folder/'visuals-project.json'
            with patch('hinglish_visuals.pipeline.write_outputs'):collect(folder,[(None,folder,p)],Finder(),SimpleNamespace(options_per_moment=2),lambda _:None)
            option=p['slots'][0]['options'][0]
            Image.new('RGB',(300,200),(100,100,100)).save(folder/option['asset'])
            with patch('hinglish_visuals.pipeline.parse_xmeml',return_value=SimpleNamespace()), \
                 patch('hinglish_visuals.pipeline.render_slot',side_effect=AssertionError('changed source must not render')):
                with self.assertRaises(ValueError):rebuild_project(file,{'0':option['id']})


if __name__=='__main__':unittest.main()
