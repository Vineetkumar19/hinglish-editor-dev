"""Saved workflow recovery contracts; no browser, model or platform calls."""
import copy
from datetime import datetime
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_recovery import release, recover, ReleaseNotReady
from hinglish_publish.prepare_post_workflow import Workflow
from hinglish_app.assistant_upload_workflow import resume_tick


class ReleaseRecovery(unittest.TestCase):
    def setUp(self):
        self.job = {'id':'queue', 'profile':'cricket', 'platform':'youtube', 'kind':'long',
                    'status':'needs_review', 'remote':{'id':'exact-video'}, 'account_id':'exact-channel',
                    'release_authorized_at':time.time(), 'release_action':'schedule',
                    'due':time.time()+86400, 'browser_schedule_id':'task', 'prepare_post_id':'prep'}
        self.publisher = Mock(root='fixture')
        self.publisher.accounts.return_value = {'youtube':{'name':'Cricket'}}
        self.task = {'id':'task', 'video_id':'exact-video', 'channel_id':'exact-channel',
                     'action':'youtube_schedule', 'publish_at':datetime.fromtimestamp(self.job['due']).astimezone().isoformat(),
                     'status':'needs_review', 'submission_started':False, 'stop':False}
        self.publisher.browser.get.return_value = self.task
        self.publisher.browser.enqueue_youtube.return_value = self.task
        self.proof = {'id':'exact-video', 'privacy':'private', 'publish_at':'', 'private_verified_at':time.time()}

    def test_pre_submission_failure_reuses_exact_task_and_never_uploads(self):
        with patch('hinglish_app.assistant_schedule.verify', side_effect=[None,self.proof]):
            self.assertTrue(release(self.publisher,self.job))
        self.publisher.browser.enqueue_youtube.assert_called_once()
        self.assertEqual(self.publisher.browser.enqueue_youtube.call_args.args[:2],('exact-channel','exact-video'))
        self.assertEqual(self.publisher.store.change.call_args.kwargs['status'],'uploaded_private')
        self.publisher.provider.assert_not_called()

    def test_already_applied_schedule_is_only_read_back(self):
        with patch('hinglish_app.assistant_schedule.verify', return_value={'id':'exact-video','publish_at':'saved'}):
            self.assertTrue(release(self.publisher,self.job))
        self.publisher.browser.enqueue_youtube.assert_not_called()
        self.assertEqual(self.publisher.store.change.call_args.kwargs['status'],'scheduled')

    def test_uncertain_upload_without_remote_id_is_never_repeated(self):
        self.job['remote']={}
        with patch('hinglish_app.assistant_schedule.verify') as verify:
            self.assertFalse(release(self.publisher,self.job));verify.assert_not_called()
        self.publisher.store.change.assert_not_called()

    def test_identity_mismatch_or_unverified_private_proof_never_replays(self):
        for field,value in [('video_id','other'),('channel_id','other'),('publish_at','2035-01-01T00:00:00+00:00'),('stop',True)]:
            self.publisher.browser.get.return_value={**self.task,field:value}
            with patch('hinglish_app.assistant_schedule.verify',side_effect=[None,self.proof]):
                self.assertFalse(release(self.publisher,self.job))
        self.publisher.browser.enqueue_youtube.assert_not_called()
        with patch('hinglish_app.assistant_schedule.verify',side_effect=[None,None]):
            with self.assertRaises(ReleaseNotReady):release(self.publisher,self.job)
        self.publisher.store.change.assert_not_called()

    def test_processing_upload_waits_without_replaying_studio_or_upload(self):
        with patch('hinglish_app.assistant_schedule.verify',side_effect=[None,None]):
            with self.assertRaises(ReleaseNotReady):release(self.publisher,self.job)
        self.publisher.browser.enqueue_youtube.assert_not_called()
        self.publisher.store.change.assert_not_called()
        self.publisher.provider.assert_not_called()

    def test_failed_preparation_resumes_only_without_submission_or_cancellation(self):
        workflow=Mock();workflow.engine.publisher.store.get.side_effect=[]
        value={'current_step':'shorts_prepare','preparations':{'shorts':'prep'},'profile':'cricket','jobs':{}}
        workflow.engine.get.return_value={'status':'failed','jobs_by_platform':{}}
        self.assertTrue(recover(workflow,value))
        workflow.engine.get.return_value['cancel_requested']=True
        self.assertFalse(recover(workflow,value))

    def test_saved_media_transfer_waits_for_delivery_instead_of_exhausting_workflow(self):
        workflow=Mock();workflow.root='fixture'
        workflow.engine.publisher.store.get.return_value={**self.job,'remote':{}}
        value={'jobs':{'long':['queue']},'current_step':'long_verify'}
        with patch('hinglish_publish.youtube_upload.Session') as saved:
            saved.return_value.resumable.return_value=True
            with self.assertRaises(ReleaseNotReady):recover(workflow,value)
        workflow.engine.publisher.browser.enqueue_youtube.assert_not_called()

    def test_uncertain_long_does_not_block_short_release_recovery(self):
        workflow=Mock();long={**self.job,'id':'long','remote':{}};short={**self.job,'id':'short'}
        workflow.engine.publisher.store.get.side_effect=lambda key:{'long':long,'short':short}[key]
        value={'jobs':{'long':['long'],'youtube':['short']},'current_step':'youtube_verify'}
        with patch('hinglish_publish.prepare_post_recovery.release',return_value=True) as replay:
            self.assertTrue(recover(workflow,value))
        replay.assert_called_once_with(workflow.engine.publisher,short)

    def test_uncertain_long_does_not_block_short_preparation_recovery(self):
        workflow=Mock();workflow.engine.publisher.store.get.side_effect=AssertionError('Unrelated job was consulted')
        workflow.engine.get.return_value={'status':'failed','jobs_by_platform':{}}
        value={'jobs':{'long':['long']},'profile':'cricket','current_step':'shorts_prepare','preparations':{'shorts':'saved'}}
        self.assertTrue(recover(workflow,value))


class SupervisorRecovery(unittest.TestCase):
    def test_upload_only_supervisor_skips_unrelated_and_explicitly_stopped_chats(self):
        import json
        from hinglish_app.assistant_upload_workflow import supervise
        assistant=Mock();assistant.sessions={'a'*16:{'status':'interrupted'}}
        records=[{'id':'a'*16,'status':'running','upload_workflow':{'auto_resume':True}},
                 {'id':'b'*16,'status':'interrupted','pipeline':{'automatic':True}},
                 {'id':'c'*16,'status':'interrupted','stop':True,'upload_workflow':{'auto_resume':True}}]
        assistant.folder.glob.return_value=[SimpleNamespace(stem=d['id'],read_text=Mock(return_value=json.dumps(d))) for d in records]
        snapshot={**records[0],'status':'interrupted'};assistant.snapshot.return_value=snapshot
        stop=Mock();stop.wait.side_effect=[False,True]
        with patch('hinglish_app.assistant_upload_workflow.resume_tick') as resume, \
                patch('hinglish_app.assistant_upload_workflow.recover_delivery'):
            supervise(assistant,stop)
        assistant.snapshot.assert_called_once_with('a'*16)
        resume.assert_called_once_with(assistant,'a'*16,snapshot)

    def test_completed_long_receipt_is_a_local_boundary_not_a_remote_dependency(self):
        from hinglish_publish.prepare_post_workflow import completed_long_checkpoint
        publisher=Mock()
        job={'profile':'cricket','platform':'youtube','kind':'long','account_id':'channel','fingerprint':'source',
             'remote':{'id':'old-upload'}}
        publisher.store.get.return_value=job
        value={'profile':'cricket','jobs':{'long':['job']},
            'receipts':{'long':[{'job':'job','status':'scheduled','remote':{'id':'old-upload','schedule_verified_at':1}}]},
            'source':{'sha256':'source'},'intent':{'accounts':{'youtube':'channel'}}}
        self.assertTrue(completed_long_checkpoint(publisher,value));publisher.provider.assert_not_called()
        value['receipts']['long'][0]['remote'].pop('schedule_verified_at')
        self.assertFalse(completed_long_checkpoint(publisher,value))
        value['receipts']['long'][0]['remote']['schedule_verified_at']=1
        job['account_id']='different'
        with self.assertRaisesRegex(ValueError,'does not match'):completed_long_checkpoint(publisher,value)

    def test_retry_after_long_completion_runs_only_saved_shorts_and_delivery(self):
        flow=object.__new__(Workflow);flow.state=SimpleNamespace(work_lock=threading.RLock());flow.engine=Mock();flow.root='fixture'
        value={'id':'flow','profile':'cricket','steps':{},'errors':{},'receipts':{'long':[{'job':'long','status':'scheduled','remote':{'id':'old','schedule_verified_at':1}}]},
               'jobs':{'long':['long'],'youtube':['yt1','yt2','yt3'],'instagram':['ig1','ig2','ig3']},
               'intent':{'count':3,'declarations':{},'minute_test':False,'accounts':{'youtube':'channel'}},'source':{'sha256':'source'}}
        flow.get=Mock(return_value=value);flow.save=Mock();flow.checkpoint=Mock();flow.wait=Mock()
        flow.preparation=Mock(return_value={'id':'saved-shorts'});flow.engine.run.return_value={'id':'saved-shorts','count':3,'status':'prepared','stages':{}}
        flow.engine.publisher.store.get.return_value={'profile':'cricket','platform':'youtube','kind':'long','account_id':'channel','fingerprint':'source','remote':{'id':'old'}}
        with patch('hinglish_publish.prepare_post_workflow.reconcile_existing_long') as reconcile:
            flow.run('flow','cricket',Mock());reconcile.assert_not_called()
        flow.preparation.assert_called_once_with(value,'shorts')
        self.assertEqual([call.args[1] for call in flow.wait.call_args_list],['youtube'])
        flow.engine.post.assert_not_called();self.assertTrue(value['steps']['long_checkpoint_reused'])

    def test_long_network_wait_does_not_block_short_preparation_or_buffer(self):
        flow=object.__new__(Workflow);flow.state=SimpleNamespace(work_lock=threading.RLock());flow.engine=Mock();flow.root='fixture'
        flow.engine.lock=threading.RLock()
        flow.engine.get.return_value={'id':'saved-shorts'}
        value={'id':'flow','profile':'cricket','steps':{},'errors':{},'receipts':{},'jobs':{'long':['long']},
               'intent':{'count':3,'declarations':{},'minute_test':False,'accounts':{'youtube':'channel'}},'source':{'sha256':'source'}}
        flow.get=Mock(return_value=value);flow.save=Mock();flow.checkpoint=Mock()
        flow.preparation=Mock(return_value={'id':'saved-shorts'})
        flow.engine.run.return_value={'id':'saved-shorts','count':3,'status':'prepared','stages':{}}
        flow.engine.post.side_effect=[{'jobs':[{'id':'yt'+str(i)} for i in range(3)]},{'jobs':[{'id':'ig'+str(i)} for i in range(3)]}]
        def wait(saved,platform,progress):
            self.assertTrue(flow.engine.run.called)
            self.assertEqual(len(saved['jobs']['instagram']),3)
            if platform=='long':raise RuntimeError('Long network wait')
        flow.wait=Mock(side_effect=wait)
        with self.assertRaisesRegex(RuntimeError,'Long network wait'):flow.run('flow','cricket',Mock())
        self.assertEqual([c.args[1] for c in flow.wait.call_args_list],['youtube','long'])
        self.assertEqual(len(value['jobs']['youtube']),3);self.assertNotEqual(value.get('status'),'complete')

    def test_explicit_chat_resume_reuses_plan_jobs_and_clips_without_new_planning(self):
        from hinglish_app.assistant_upload_workflow import resume_request
        assistant=Mock();assistant.state.port=8765
        snapshot={'upload_workflow':{'id':'a'*32,'profile':'cricket','plan':{'count':3}},'active_request_message_id':'new'}
        assistant.snapshot.return_value=snapshot
        flow=Mock();flow.lock=threading.RLock();flow.running=set()
        value={'id':'a'*32,'profile':'cricket','status':'failed','current_step':'shorts_prepare',
               'assistant_plan':{'session':'session','owner_port':8765,'message_id':'original'},
               'jobs':{'long':['existing-long']},'preparations':{'shorts':'existing-clips'},
               'automatic_recovery':{'enabled':True,'exhausted':True,'attempts':3}}
        flow.get.return_value=value
        with patch('hinglish_app.prepare_post_http.service'),patch('hinglish_app.prepare_post_http.workflow_service',return_value=flow),patch('hinglish_app.assistant_upload_workflow.execute') as run:
            self.assertFalse(resume_request(assistant,'session','Can you resume the workflow?',Mock(),'new'))
            self.assertTrue(resume_request(assistant,'session','Resume the saved RCB workflow.',Mock(),'new'))
            run.assert_called_once()
        self.assertEqual(value['jobs'],{'long':['existing-long']});self.assertEqual(value['preparations']['shorts'],'existing-clips')
        self.assertFalse(value['automatic_recovery']['exhausted']);self.assertEqual(value['automatic_recovery']['step_attempts']['shorts_prepare'],0)
        self.assertEqual(value['assistant_plan']['original_message_id'],'original');self.assertEqual(value['assistant_plan']['message_id'],'new')

    def test_completed_workflow_restores_future_buffer_without_new_model_or_queue(self):
        from hinglish_app.assistant_upload_workflow import restore_buffer
        assistant=Mock();assistant.state.port=8765
        engine=Mock();workflow=Mock()
        workflow.get.return_value={'status':'complete','profile':'cricket',
            'assistant_plan':{'session':'session','owner_port':8765},
            'jobs':{'instagram':['ig']},'preparations':{'shorts':'prep'},
            'intent':{'accounts':{'instagram':'account'}}}
        job={'status':'ready','authorized_at':1,'profile':'cricket','account_id':'account','prepare_post_id':'prep'}
        engine.publisher.store.get.return_value=job
        with patch('hinglish_app.prepare_post_http.service',return_value=engine),patch('hinglish_app.prepare_post_http.workflow_service',return_value=workflow):
            self.assertTrue(restore_buffer(assistant,'session',{'id':'id','profile':'cricket'}))
            engine.start_delivery.assert_called_once();engine.create.assert_not_called();engine.run.assert_not_called();engine.post.assert_not_called()
            job['status']='cancelled'
            self.assertFalse(restore_buffer(assistant,'session',{'id':'id','profile':'cricket'}))
            job['status']='ready';assistant.state.port=8872
            self.assertFalse(restore_buffer(assistant,'session',{'id':'id','profile':'cricket'}))

    def test_verified_later_cancellation_does_not_rearm_completed_long(self):
        from hinglish_publish.prepare_post_workflow import completed_long_cancelled
        publisher=Mock()
        job={'status':'cancelled','account_id':'channel','fingerprint':'source',
             'remote':{'id':'video','privacy':'private','publish_at':'','cancellation_verified_at':10}}
        publisher.store.get.return_value=job
        value={'jobs':{'long':['job']},'receipts':{'long':[{'job':'job','remote':{'id':'video'}}]},
               'intent':{'accounts':{'youtube':'channel'}},'source':{'sha256':'source'}}
        self.assertTrue(completed_long_cancelled(publisher,value))
        del job['remote']['cancellation_verified_at']
        self.assertFalse(completed_long_cancelled(publisher,value))
        job['remote']['cancellation_verified_at']=10;job['remote']['id']='different'
        self.assertFalse(completed_long_cancelled(publisher,value))

    def workflow(self):
        flow=object.__new__(Workflow)
        flow.state=SimpleNamespace(publisher=SimpleNamespace(stop=Mock()))
        flow.state.publisher.stop.wait.return_value=False
        self.saved={'id':'a'*32,'profile':'cricket','status':'failed','current_step':'long_verify',
                    'automatic_recovery':{'enabled':True,'attempts':0}}
        flow.get=Mock(side_effect=lambda *args:copy.deepcopy(self.saved))
        flow.save=Mock(side_effect=lambda value:self.saved.update(copy.deepcopy(value)))
        return flow

    def test_safe_failure_automatically_continues_same_workflow(self):
        flow=self.workflow();flow.run=Mock(side_effect=[ValueError('visibility not ready'),None])
        with patch('hinglish_publish.prepare_post_recovery.recover',return_value=True):
            flow.supervise('a'*32,'cricket',Mock())
        self.assertEqual(flow.run.call_count,2)
        self.assertEqual(self.saved['automatic_recovery']['attempts'],1)
        flow.state.publisher.stop.wait.assert_called_once_with(5)

    def test_processing_readback_waits_then_retries_same_release(self):
        flow=self.workflow();flow.run=Mock(side_effect=[ValueError('page loading'),ValueError('page loading'),None])
        with patch('hinglish_publish.prepare_post_recovery.recover',side_effect=[ReleaseNotReady('Processing saved upload'),True]):
            flow.supervise('a'*32,'cricket',Mock())
        recovery=self.saved['automatic_recovery']
        self.assertEqual(recovery['attempts'],1)
        self.assertEqual(recovery['readiness_checks']['long_verify'],1)
        self.assertFalse(recovery.get('exhausted',False))
        self.assertEqual(flow.run.call_count,3)

    def test_processing_readback_wait_is_bounded_and_honors_stop(self):
        flow=self.workflow();flow.run=Mock(side_effect=ValueError('page loading'))
        self.saved['automatic_recovery']['readiness_checks']={'long_verify':40}
        with patch('hinglish_publish.prepare_post_recovery.recover',side_effect=ReleaseNotReady('Still processing')),self.assertRaises(ReleaseNotReady):
            flow.supervise('a'*32,'cricket',Mock())
        flow.state.publisher.stop.wait.assert_not_called()
        self.assertTrue(self.saved['automatic_recovery']['exhausted'])
        flow=self.workflow();flow.run=Mock(side_effect=ValueError('page loading'))
        flow.state.publisher.stop.wait.return_value=True
        with patch('hinglish_publish.prepare_post_recovery.recover',side_effect=ReleaseNotReady('Still processing')),self.assertRaisesRegex(ValueError,'Storylens stopped'):
            flow.supervise('a'*32,'cricket',Mock())
        self.assertEqual(flow.run.call_count,1)

    def test_an_earlier_release_error_does_not_spend_the_preparation_retry_budget(self):
        flow=self.workflow()
        self.saved.update(current_step='shorts_prepare',automatic_recovery={'enabled':True,'attempts':3,
            'history':[{'step':'long_verify'}]*3})
        flow.run=Mock(side_effect=[ValueError('copy needs correction'),None])
        with patch('hinglish_publish.prepare_post_recovery.recover',return_value=True):
            flow.supervise('a'*32,'cricket',Mock())
        self.assertEqual(flow.run.call_count,2)
        self.assertEqual(self.saved['automatic_recovery']['step_attempts']['shorts_prepare'],1)
        self.assertEqual(self.saved['automatic_recovery']['attempts'],4)

    def test_retries_are_bounded_and_failed_verification_does_not_loop(self):
        flow=self.workflow();flow.run=Mock(side_effect=ValueError('same failure'))
        with patch('hinglish_publish.prepare_post_recovery.recover',return_value=True),self.assertRaises(ValueError):
            flow.supervise('a'*32,'cricket',Mock())
        self.assertEqual(flow.run.call_count,4)
        self.assertTrue(self.saved['automatic_recovery']['exhausted'])
        flow=self.workflow();flow.run=Mock(side_effect=ValueError('first failure'))
        with patch('hinglish_publish.prepare_post_recovery.recover',side_effect=ValueError('cannot verify')),self.assertRaisesRegex(ValueError,'cannot verify'):
            flow.supervise('a'*32,'cricket',Mock())
        self.assertTrue(self.saved['automatic_recovery']['exhausted'])
        self.assertEqual(flow.run.call_count,1)

    def test_restart_recovers_only_owned_current_request_and_starts_once(self):
        assistant=Mock();assistant.lock=threading.RLock();assistant.state.port=8765
        snapshot={'status':'interrupted','active_request_message_id':'message','upload_workflow':{
            'id':'a'*32,'profile':'cricket','auto_resume':True}}
        assistant.snapshot.side_effect=lambda *args:copy.deepcopy(snapshot)
        flow=Mock();flow.lock=threading.RLock();flow.running=set()
        flow.get.return_value={'id':'a'*32,'profile':'cricket','status':'working',
            'assistant_plan':{'session':'session','message_id':'message','owner_port':8765},
            'automatic_recovery':{'enabled':True}}
        with patch('hinglish_app.prepare_post_http.service'),patch('hinglish_app.prepare_post_http.workflow_service',return_value=flow),patch('threading.Thread') as thread:
            self.assertTrue(resume_tick(assistant,'session',snapshot))
            self.assertFalse(resume_tick(assistant,'session',snapshot))
            thread.assert_called_once();thread.return_value.start.assert_called_once()
            flow.running.clear();flow.get.return_value['assistant_plan']['message_id']='older-request'
            self.assertFalse(resume_tick(assistant,'session',snapshot))
            flow.running.clear();assistant.state.port=8872
            self.assertFalse(resume_tick(assistant,'session',snapshot))
            assistant.state.port=8765
            snapshot['stop']=True
            self.assertFalse(resume_tick(assistant,'session',snapshot))


if __name__=='__main__':unittest.main()
