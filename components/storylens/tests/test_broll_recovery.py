import json
import os
from dataclasses import asdict
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

import requests

from hinglish_clean.detection import write_json
from hinglish_broll.recovery import RunStore, request_key, restore_choices, retry
from hinglish_broll.settings import BrollSettings, profile_for
from hinglish_broll.stock import Candidate, PexelsClient
from tests.test_broll_media import fake_video, response


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{},clear=False);self.env.start();self.addCleanup(self.env.stop)
        os.environ.pop('STORYLENS_BROLL_CHECKPOINT',None)

    def test_windows_atomic_save_retries_a_brief_reader_lock_and_preserves_old_file(self):
        from hinglish_broll.recovery import write_json as atomic_save
        file=self.root/'progress.json';file.write_text('{"old":true}')
        original=Path.replace;attempts=[]
        def replace(path,target):
            attempts.append(1)
            if len(attempts)<3:
                self.assertEqual(json.loads(file.read_text()),{'old':True})
                raise PermissionError('Reader is still closing the old file')
            return original(path,target)
        with patch.object(Path,'replace',replace),patch('hinglish_broll.recovery.time.sleep'):
            atomic_save(file,{'new':True})
        self.assertEqual(json.loads(file.read_text()),{'new':True})
        self.assertEqual(len(attempts),3);self.assertEqual(list(self.root.glob('*.tmp')),[])

    def test_resume_same_work_but_new_source_or_finished_request_gets_new_run(self):
        source=self.root/'source.mp4';source.write_bytes(b'first')
        settings=BrollSettings(pexels_key='private-key')
        key=request_key(source,settings,count=5)
        store=RunStore(self.root,key);store.start(self.root/'output/broll/one')
        self.assertNotIn('private-key',store.file.read_text())
        self.assertEqual(RunStore(self.root,key).output,store.output)
        settings.pexels_key='replacement-key'
        self.assertEqual(request_key(source,settings,count=5),key)
        source.write_bytes(b'different source')
        self.assertIsNone(RunStore(self.root,request_key(source,settings,count=5)).output)
        store.data['state']='complete';store.save()
        self.assertIsNone(RunStore(self.root,key).output)

    def test_untrusted_marker_cannot_resume_outside_output_and_corrupt_journal_is_ignored(self):
        marker=self.root/'marker.json';os.environ['STORYLENS_BROLL_CHECKPOINT']=str(marker)
        write_json(marker,{'key':'same','journal':str(self.root/'recovery.json')})
        self.assertIsNone(RunStore(self.root,'same').output)
        journal=self.root/'output/broll/one/recovery.json';journal.parent.mkdir(parents=True)
        journal.write_text('{broken')
        write_json(marker,{'key':'same','journal':str(journal)})
        self.assertIsNone(RunStore(self.root,'same').output)

    def test_temporary_failure_recovers_but_auth_and_relevance_veto_are_not_retried(self):
        operation=Mock(side_effect=[requests.Timeout('offline'),42])
        with patch('hinglish_broll.recovery.time.sleep'):
            self.assertEqual(retry(operation,lambda _:None,'Search'),42)
            for error in (PermissionError('bad key'),ValueError('B-roll rejected')):
                operation=Mock(side_effect=error)
                with self.assertRaises(type(error)):retry(operation,lambda _:None,'Search')
                self.assertEqual(operation.call_count,1)
            operation=Mock(side_effect=requests.Timeout('offline'))
            with self.assertRaises(requests.Timeout):retry(operation,lambda _:None,'Search')
            self.assertEqual(operation.call_count,3)

    def test_bad_key_is_not_queried_again_until_the_key_changes(self):
        session=Mock();session.get.return_value=response({},401)
        for _ in range(2):
            with self.assertRaises(PermissionError):PexelsClient('bad',self.root,session)._get('https://api.pexels.com/videos/search',{})
        self.assertEqual(session.get.call_count,1)
        session.get.return_value=response({'videos':[]})
        self.assertEqual(PexelsClient('new',self.root,session)._get('https://api.pexels.com/videos/search',{}),{'videos':[]})
        self.assertEqual(session.get.call_count,2)

    def test_bad_saved_media_is_repaired_without_discarding_good_choices_or_timing(self):
        fake_video(self.root/'good.mp4',seconds=1,width=64,height=96)
        (self.root/'broken.mp4').write_bytes(b'interrupted')
        slot={'options':[{'id':'good','clip':'good.mp4'},{'id':'bad','clip':'broken.mp4'}],
            'chosen':{'id':'good'},'clip':'good.mp4','start':1.2,'end':1.8,'source_in':.1,
            'collection_complete':True,'attempted':[{'id':'bad'}]}
        restore_choices(self.root,{'slots':[slot]})
        self.assertEqual([c['id'] for c in slot['options']],['good'])
        self.assertEqual((slot['start'],slot['end'],slot['source_in']),(1.2,1.8,.1))
        self.assertFalse(slot['collection_complete']);self.assertEqual(slot['attempted'],[])

    def test_worker_interrupted_mid_keyword_resumes_after_the_saved_option(self):
        from hinglish_broll.pipeline import run, timeline_to_dict
        from hinglish_broll.placement import Moment, Slot
        from hinglish_broll.phrases import Phrase
        from hinglish_broll.timeline import parse_xmeml
        from hinglish_cut.model import Media, Cut
        from hinglish_cut.xml_export import export_xml
        source=self.root/'speech.mp4';fake_video(source,seconds=3,width=64,height=96)
        folder=self.root/'output/broll/resume/001-speech';folder.mkdir(parents=True)
        xml=folder/'source-timeline.xml'
        media=Media('speech',str(source),3,'25',64,96,2,48000)
        export_xml(xml,[Cut('speech',0,75,0)],{'speech':media})
        timeline=parse_xmeml(xml)
        settings=BrollSettings(use_library=False,use_pexels=False,use_pixabay=False)
        options=dict(output_format=None,black_background=False,target_count=1,brief='',review_options=True,options_per_moment=2,reference_script='')
        store=RunStore(self.root,request_key(source,settings,**options));store.start(folder.parent)
        slot=Slot(Moment(0,'bed',['bed']),.5,1.5,'a bed')
        store.data['plans']=[{'folder':folder.name,'summary':{'topic':'bed'},'profile':asdict(profile_for(3)),
            'slots':[asdict(slot)],'phrases':[asdict(Phrase(0,.5,1.5,'a bed'))]}];store.save()
        candidates=[Candidate('pixabay',name,'bed',3,64,96,score=.7) for name in ('a','b')]
        write_json(folder/'ranked-candidates.json',{'1':[c.to_dict() for c in candidates]})
        calls=[]
        def render(root,folder,timeline,i,entry,candidate,*args,**kwargs):
            calls.append(candidate.id)
            if calls==['a','b']:raise KeyboardInterrupt()
            clip=folder/(candidate.id+'.mp4');fake_video(clip,seconds=2,width=64,height=96)
            entry.update(source_in=.2,source_duration=2)
            entry.setdefault('checks',[]).append({'id':candidate.id,'passed':True,'reason':'test fixture'})
            return clip
        def outputs(root,folder,project):
            (folder/'report.html').write_text('saved');return folder/'BROLL_SEQUENCE.xml'
        with patch('hinglish_broll.pipeline.load_settings',return_value=settings), \
             patch('hinglish_broll.pipeline.timelines_for',return_value=[(timeline,folder)]), \
             patch('hinglish_visuals.brain.open_brain') as brain, \
             patch('hinglish_broll.vision.Vision') as vision, \
             patch('hinglish_broll.verify.Checker'), \
             patch('hinglish_broll.pipeline.render_choice',side_effect=render), \
             patch('hinglish_broll.pipeline.write_outputs',side_effect=outputs), \
             patch('hinglish_cut.model_preferences.release_ollama'):
            with self.assertRaises(KeyboardInterrupt):run(self.root,source,target_count=1,review_options=True,options_per_moment=2,progress=lambda _:None)
            saved=json.loads((folder/'broll-project.json').read_text())
            self.assertEqual([c['id'] for c in saved['slots'][0]['options']],['a'])
            result=run(self.root,source,target_count=1,review_options=True,options_per_moment=2,progress=lambda _:None)
            self.assertTrue(result.is_file());brain.assert_not_called();vision.assert_not_called()
        self.assertEqual(calls,['a','b','b'])
        saved=json.loads((folder/'broll-project.json').read_text())
        self.assertEqual([c['id'] for c in saved['slots'][0]['options']],['a','b'])
        self.assertEqual(saved['slots'][0]['source_in'],.2)

    def test_app_job_and_progress_survive_server_restart_without_exposing_creator_context(self):
        from hinglish_app.server import AppState
        state=AppState(self.root,port=18967)
        job={'id':'abcdef123456','mode':'broll','status':'running','progress':30,'logs':['Checked first clip'],
            'stage':'Checking next clip','recovery_attempts':1,'recovery_request':{
                'payload':{'mode':'broll','_creator_context':{'keep':'all guidance'}},'paths':[],'input':str(self.root/'source.mp4'),'script':''}}
        state.jobs[job['id']]=job;state._persist_broll_job(job)
        self.assertNotIn('recovery_request',state.snapshot(job['id']))
        with patch.object(AppState,'_run_job') as resume:
            restored=AppState(self.root,port=18967)
            # Restore dispatch is asynchronous, wait for this lightweight thread.
            for thread in threading.enumerate():
                if thread is not threading.current_thread() and thread.name.endswith('(_run_job)'):thread.join(1)
            resume.assert_called_once()
            self.assertEqual(restored.jobs[job['id']]['recovery_request']['payload']['_creator_context'],{'keep':'all guidance'})


if __name__=='__main__':unittest.main()
