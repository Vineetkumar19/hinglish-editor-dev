"""Workflow authorization, source reuse and replay contracts; not live receipts."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from tests import test_prepare_post as fixtures
from hinglish_publish.prepare_post_workflow import Workflow


class WorkflowContracts(unittest.TestCase):
    setUp=fixtures.PreparePostTests.setUp
    draft=fixtures.PreparePostTests.draft

    def workflow(self):
        return Workflow(SimpleNamespace(root=self.root,publisher=self.publisher,work_lock=threading.RLock()),self.service)

    def test_failed_long_readback_records_long_boundary_before_recovery(self):
        flow=self.workflow()
        value={'jobs':{'long':['saved-long']},'current_step':'youtube_verify'}
        flow.save=Mock();flow.engine.start_delivery=Mock()
        with patch.object(flow.engine.publisher.store,'get',return_value={
                'status':'needs_review','error':'Pending Studio visibility'}):
            with self.assertRaisesRegex(ValueError,'Pending Studio visibility'):
                flow.wait(value,'long',Mock())
        self.assertEqual(value['current_step'],'long_verify')

    def payload(self):
        return {'profile':'cricket','video':str(self.video),'thumbnail':str(self.thumb),'count':5,
                'request_id':'single-click','authorize':True,'made_for_kids':False,'synthetic_media':False,'minute_test':True}

    def test_repeated_click_reuses_intent_and_changed_count_cannot_rebind_it(self):
        flow=self.workflow();p=self.payload()
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):
            first=flow.create(p);second=flow.create(p)
            self.assertEqual(first['id'],second['id'])
            with self.assertRaises(ValueError):flow.create({**p,'minute_test':False,'count':6})
        self.assertEqual(self.publisher.store.list(),[])

    def test_missing_explicit_authorization_creates_no_posts(self):
        flow=self.workflow()
        with self.assertRaisesRegex(ValueError,'authorize'):flow.create({**self.payload(),'authorize':False})
        self.assertEqual(flow.list('cricket'),[])
        self.assertEqual(self.publisher.store.list(),[])

    def test_new_workflow_has_discovery_but_old_saved_workflow_does_not_adopt_it(self):
        flow=self.workflow()
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):
            new=flow.create(self.payload())
            old=flow.create({**self.payload(),'request_id':'old-saved'})
        self.assertTrue(flow.preparation(new,'long')['discovery_review'])
        old.pop('discovery_settings');flow.save(old)
        self.assertFalse(flow.preparation(old,'long')['discovery_review'])
        self.assertEqual(self.publisher.store.list(),[])

    def test_exact_existing_long_receipt_is_reused_without_new_upload(self):
        draft=self.draft('long');self.service.run(draft['id'],'cricket');job=self.service.queue(draft['id'],'cricket','youtube')[0]
        self.publisher.store.change(job['id'],status='scheduled',remote={'id':'existing-video','url':'https://youtube.com/watch?v=existing-video'})
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):value=self.workflow().create(self.payload())
        self.assertEqual(value['jobs']['long'],[job['id']])
        self.assertEqual(len(self.publisher.store.list()),1)

    def test_identical_source_reuses_speech_but_new_path_is_explicit(self):
        original=self.draft('long');self.service.run(original['id'],'cricket')
        flow=self.workflow()
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):value=flow.create(self.payload())
        short=flow.preparation(value,'shorts')
        self.assertEqual(short['reused_speech_from'],original['id'])
        self.assertEqual(short['stages']['speech']['source'],short['source'])
        self.assertNotIn('selection',short['stages'])

    def test_explicit_long_reuse_overrides_repeat_mode_and_rejects_missing_id(self):
        draft=self.draft('long');self.service.run(draft['id'],'cricket');job=self.service.queue(draft['id'],'cricket','youtube')[0]
        self.publisher.store.change(job['id'],status='uploaded_private',remote={'id':'saved-video'})
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}),patch('hinglish_publish.test_mode.enabled',return_value=True):
            flow=self.workflow()
            value=flow.create({**self.payload(),'reuse_long_video_id':'saved-video'})
            self.assertEqual(value['jobs']['long'],[job['id']])
            with self.assertRaisesRegex(ValueError,'does not match'):
                flow.create({**self.payload(),'request_id':'missing','reuse_long_video_id':'missing'})
            self.publisher.store.change(job['id'],status='cancelled')
            with self.assertRaisesRegex(ValueError,'was cancelled'):
                flow.create({**self.payload(),'request_id':'cancelled','reuse_long_video_id':'saved-video'})

    def test_fresh_workflow_does_not_reuse_older_long_or_transcript(self):
        old=self.draft('long');self.service.run(old['id'],'cricket')
        job=self.service.queue(old['id'],'cricket','youtube')[0]
        self.publisher.store.change(job['id'],status='uploaded_private',remote={'id':'old-video'})
        flow=self.workflow()
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):
            value=flow.create({**self.payload(),'fresh_start':True})
        self.assertEqual(value['jobs'],{})
        long=flow.preparation(value,'long')
        self.assertEqual(long['stages'],{})
        self.assertTrue(long['fresh_start'])
        self.service.run(long['id'],'cricket')
        short=flow.preparation(value,'shorts')
        self.assertEqual(short['reused_speech_from'],long['id'])

    def test_explicit_workflow_resume_clears_child_stop_at_stage_boundary(self):
        flow=self.workflow()
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):value=flow.create(self.payload())
        short=flow.preparation(value,'shorts')
        self.service.cancel(short['id'],'cricket')
        value.update(status='failed');flow.save(value)
        self.publisher.task=Mock()
        flow.start(value['id'],'cricket')
        resumed=self.service.get(short['id'],'cricket')
        self.assertFalse(resumed['cancel_requested'])
        self.assertEqual(resumed['status'],'queued')
        self.publisher.task.assert_called_once()

    def test_preparation_retry_does_not_claim_an_upload_was_verified(self):
        flow=self.workflow()
        with patch('hinglish_app.assistant_preferences.declarations',return_value={}):value=flow.create(self.payload())
        value.update(current_step='long_prepare',automatic_recovery={'enabled':True})
        flow.save(value)
        flow.run=Mock(side_effect=[ValueError('Invalid source excerpts'),'finished'])
        self.publisher.stop=Mock();self.publisher.stop.wait.return_value=False
        progress=Mock()
        with patch('hinglish_publish.prepare_post_recovery.recover',return_value=True):
            self.assertEqual(flow.supervise(value['id'],'cricket',progress),'finished')
        message=progress.call_args.args[0]
        self.assertIn('unfinished preparation',message)
        self.assertNotIn('upload verified',message.lower())
