"""Real failure: a new three-Reel request overlaps an older scheduled job."""
import copy
import unittest
import threading
from unittest.mock import Mock
from hinglish_app.assistant_request_status import review_is_current,background_instagram,pipeline_is_current


class RequestStatusTests(unittest.TestCase):
    def stale_session(self):
        # Live failure: an old completed three-post batch became Attention
        # when a new mixed-platform request failed, then reported success again.
        return {'id':'chat','status':'failed','active_request_message_id':'new','active_request_created':200,
            'pipeline':{'automatic':True,'phase':'attention','authorized_review':'old-review','created':100},
            'publishing_review':{'id':'old-review','request_message_id':'old','created':100,
                'instagram_rows':[{'status':'published'} for _ in range(3)]}}

    def test_failed_new_request_cannot_reactivate_older_completed_pipeline(self):
        from hinglish_app.assistant_pipeline import failed,tick
        from hinglish_app.pipeline_audit import reconcile_due
        session=self.stale_session();before=copy.deepcopy(session)
        assistant=Mock();assistant.lock=threading.RLock();assistant.snapshot.return_value=session
        failed(assistant,'chat',ValueError('The local model could not select a ready saved batch.'))
        self.assertFalse(tick(assistant,'chat'))
        reconcile_due(assistant,'chat',session)
        self.assertEqual(session,before)
        assistant._update.assert_not_called();assistant._message.assert_not_called()
        assistant.state.local_browser.retry_before_share.assert_not_called()

    def test_explicitly_authorized_continuation_can_own_existing_review(self):
        session=self.stale_session()
        self.assertFalse(pipeline_is_current(session))
        session['publishing_review']['request_message_id']='new'
        self.assertTrue(pipeline_is_current(session))
        session['pipeline']['request_message_id']='new'
        self.assertTrue(pipeline_is_current(session))

    def test_previous_two_post_result_does_not_belong_to_new_request(self):
        session={'id':'current','active_request_message_id':'new','active_request_created':200}
        self.assertFalse(review_is_current(session,{'request_message_id':'old','created':100}))
        self.assertFalse(review_is_current(session,{'created':100}))
        self.assertTrue(review_is_current(session,{'request_message_id':'new','created':250}))
        self.assertTrue(review_is_current(session,{'created':250}))

    def test_independent_due_job_is_separate_from_exactly_three_current_posts(self):
        session={'id':'current','active_request_message_id':'new','active_request_created':200,
            'publishing_review':{'request_message_id':'new','instagram_rows':[
                {'browser_job_id':f'new-{i}'} for i in range(3)]}}
        jobs=[{'id':f'new-{i}','session':'current','created':250,'action':'reel',
               'account':'cricket','status':'published','finished':400} for i in range(3)]
        jobs.extend([
            {'id':'old-gaming','session':'earlier-chat','created':10,'action':'reel',
             'account':'gaming','status':'sharing','publish_at':'2030-01-01T19:00:00+05:30'},
            {'id':'future','session':'another-chat','created':20,'action':'reel',
             'account':'cricket','status':'queued','publish_at':'2030-01-02T19:00:00+05:30'},
            {'id':'inspect','session':'earlier-chat','action':'inspect','status':'running'}])
        before=copy.deepcopy(jobs)
        result=background_instagram(session,jobs,now=500)
        self.assertEqual([j['id'] for j in result],['old-gaming','future'])
        self.assertEqual(result[0]['session'],'earlier-chat')
        self.assertEqual(jobs,before)  # Visibility cannot cancel or move another job.

    def test_recent_scheduled_publication_retains_its_original_chat(self):
        job={'id':'old','action':'reel','session':'source-chat','account':'gaming',
             'status':'published','publish_at':'2030-01-01T19:00:00+05:30','finished':450}
        self.assertEqual(background_instagram({'id':'current'},[job],now=500)[0]['session'],'source-chat')
        self.assertEqual(background_instagram({'id':'current'},[job],now=1200),[])
