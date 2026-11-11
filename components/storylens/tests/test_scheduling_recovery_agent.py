import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from hinglish_publish.local_browser import LocalBrowser
from hinglish_publish.scheduling_recovery_agent import recover


class SchedulingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=time.time()
        self.browser=LocalBrowser(self.root)
        self.browser.seen=self.now;self.browser.worker_supports=['youtube_schedule']
        task=self.browser.enqueue_youtube('UC'+'g'*22,'new00000001','2035-01-01T13:30:00+00:00',
            'prepare-post:prep',authorized=True,video_kind='long')
        self.task=self.browser.data['jobs'][0]
        self.task.update(status='needs_review',finished=self.now-200,
            message='Studio opened: Studio did not finish loading the video visibility dialog.')
        from datetime import datetime
        self.job={'id':'job','status':'needs_review','platform':'youtube','profile':'cricket','kind':'long',
            'release_action':'schedule','release_authorized_at':1,'authorized_at':1,'prepare_post_id':'prep',
            'due':datetime.fromisoformat(task['publish_at']).timestamp(),
            'remote':{'id':task['video_id']},'account_id':task['channel_id'],'browser_schedule_id':task['id']}
        self.folder=self.root/'output/publisher-prepare-post/workflows';self.folder.mkdir(parents=True)
        self.flow={'id':'flow','status':'working','profile':'cricket','request_id':'ask-full-'+'a'*16+'-123',
            'intent':{'accounts':{'youtube':task['channel_id']}},'jobs':{'long':['job']},'preparations':{'long':'prep'}}
        self.save_flow()
        folder=self.root/'cache/assistant';folder.mkdir(parents=True)
        self.session=folder/('a'*16+'.json');self.session.write_text(json.dumps({'status':'running','stop':False}))
        self.pub=SimpleNamespace(root=self.root,browser=self.browser,store=Mock(),
            accounts=lambda _: {'youtube':{'connected':True,'id':task['channel_id'],'name':'Cricket'}})

    def save_flow(self):
        (self.folder/'flow.json').write_text(json.dumps(self.flow))

    def test_recovery_reuses_exact_task_with_bounded_attempts_no_provider(self):
        for n in range(3):
            self.assertTrue(recover(self.pub,self.job,self.now))
            self.assertEqual(len(self.browser.data['jobs']),1)
            self.assertEqual(self.task['schedule_recovery_count'],n+1)
            self.assertEqual(self.task['video_id'],'new00000001')
            self.task.update(status='needs_review',finished=self.now-200,
                message='Studio did not finish loading the video visibility dialog.')
        self.assertFalse(recover(self.pub,self.job,self.now))

    def test_uncertain_submission_cancellation_identity_and_login_fail_closed(self):
        original=dict(self.task)
        for change in ({'submission_started':True},{'stop':True},{'video_id':'other000001'},
                       {'channel_id':'UC'+'x'*22},{'message':'Studio sign-in is required.'},
                       {'publish_at':'2035-01-02T13:30:00+00:00'},{'finished':self.now}):
            self.task.clear();self.task.update(original);self.task.update(change)
            self.assertFalse(recover(self.pub,self.job,self.now),change)
        self.pub.store.change.assert_not_called()

    def test_stopped_unrelated_and_other_profile_workflows_are_untouched(self):
        for change in ({'status':'stopped'},{'profile':'gaming'},{'jobs':{'long':['other']}}):
            original=dict(self.flow);self.flow.update(change);self.save_flow()
            self.assertFalse(recover(self.pub,self.job,self.now))
            self.flow=original
        self.save_flow();self.session.write_text(json.dumps({'status':'running','stop':True}))
        self.assertFalse(recover(self.pub,self.job,self.now))

    def test_gaming_short_uses_its_own_binding(self):
        self.job.update(profile='gaming',kind='short');self.flow['profile']='gaming';self.save_flow()
        self.assertTrue(recover(self.pub,self.job,self.now))
        self.assertEqual(self.task['video_kind'],'short')
