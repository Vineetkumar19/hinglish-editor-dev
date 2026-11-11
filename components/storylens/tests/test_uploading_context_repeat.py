"""Nonpublishing contracts for scoped context and explicitly repeated test runs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_cut.model_preferences import configure_request, uploading_context
from tests.test_prepare_post import PreparePostTests
from hinglish_publish.prepare_post_workflow import Workflow
from types import SimpleNamespace
import threading


class UploadingContextTests(unittest.TestCase):
    def test_native_upload_context_does_not_change_other_features(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            root=Path(tmp)
            (root/'config.models.local.json').write_text(json.dumps({'context_limit':12288,
                'publishing_context_limit':40960,'publishing_context_model':'local:14b',
                'device':'cuda','ollama_num_gpu':-1,'allow_ollama_cpu_offload':True}), 'utf-8')
            def body():return {'model':'local:14b','messages':[{'role':'user','content':'Keep all source words'}],
                               'options':{'num_ctx':12288,'num_predict':800}}
            normal=body();configure_request(root,normal)
            with uploading_context():
                upload=body();configure_request(root,upload)
            later=body();configure_request(root,later)
            self.assertEqual(normal['options']['num_ctx'],12288)
            self.assertEqual(upload['options']['num_ctx'],40960)
            self.assertEqual(later['options']['num_ctx'],12288)
            self.assertEqual(upload['options']['num_gpu'],-1)
            self.assertEqual(upload['messages'],normal['messages'])
            with uploading_context(),self.assertRaisesRegex(ValueError,'another model'):
                configure_request(root,{**body(),'model':'different:model'})


class RepeatUploadTests(unittest.TestCase):
    setUp=PreparePostTests.setUp
    draft=PreparePostTests.draft

    def enable(self):
        (self.root/'config.workflow.local.json').write_text(json.dumps({'publishing_test_mode':{
            'allow_repeat_uploads':True,'profiles':['cricket']}}),'utf-8')

    def test_new_preparation_can_repeat_same_bytes_but_same_preparation_retry_reuses_job(self):
        old=self.draft('long');self.service.run(old['id'],'cricket')
        old_job=self.service.queue(old['id'],'cricket','youtube')[0]
        self.enable()
        new=self.service.create({**old['intent'],'request_id':'another-test','minutes':15,'visibility':'private'})
        self.service.run(new['id'],'cricket')
        first=self.service.queue(new['id'],'cricket','youtube')[0]
        again=self.service.queue(new['id'],'cricket','youtube')[0]
        self.assertNotEqual(old_job['id'],first['id']);self.assertEqual(first['id'],again['id'])
        self.assertEqual(first['fingerprint'],old_job['fingerprint'])
        self.assertEqual(len(self.publisher.store.list()),2)
        self.publisher.authorize.assert_not_called()

    def test_repeat_workflow_does_not_reuse_old_remote_upload(self):
        old=self.draft('long');self.service.run(old['id'],'cricket')
        job=self.service.queue(old['id'],'cricket','youtube')[0]
        self.publisher.store.change(job['id'],remote={'id':'older-upload'},status='scheduled')
        self.enable()
        flow=Workflow(SimpleNamespace(root=self.root,publisher=self.publisher,work_lock=threading.RLock()),self.service)
        with patch('hinglish_app.assistant_preferences.declarations',return_value={'made_for_kids':False,'synthetic_media':False}):
            value=flow.create({'profile':'cricket','video':str(self.video),'count':3,'request_id':'repeat-workflow','authorize':True})
        self.assertTrue(value['intent']['repeat_uploads']);self.assertNotIn('long_reused',value['steps']);self.assertEqual(value['jobs'],{})

    def test_repeat_scope_rejected_unless_explicitly_enabled(self):
        with self.assertRaisesRegex(ValueError,'test mode'):
            self.publisher.store.add_batch([{'profile':'cricket','platform':'youtube','kind':'long',
                'video':str(self.video),'fingerprint':'same-bytes','test_repeat_scope':'a'*32}])


class WorkflowIntentTests(unittest.TestCase):
    def test_full_request_is_not_a_question_or_an_individual_short_request(self):
        from hinglish_app.assistant_upload_workflow import requested
        self.assertTrue(requested('Schedule this long cricket video, then extract 3 Shorts and schedule YouTube and Instagram Reels.'))
        self.assertFalse(requested('Can I schedule a long cricket video and then extract 3 Shorts?'))
        self.assertFalse(requested('Extract 3 cricket Shorts and schedule them.'))


if __name__=='__main__':unittest.main()
