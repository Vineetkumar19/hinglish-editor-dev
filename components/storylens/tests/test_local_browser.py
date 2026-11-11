import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from hinglish_publish.local_browser import LocalBrowser
from hinglish_app.assistant_social import upload_intent, chrome_caption
from hinglish_app.assistant_plan import plan, quick_plan, validate_plan
from hinglish_app.server import serve


class QueueTests(unittest.TestCase):
    def test_offline_scheduled_reels_resume_in_release_order_without_replaying_share(self):
        from datetime import datetime,timezone,timedelta
        later=datetime.now(timezone.utc)+timedelta(hours=2);earlier=later-timedelta(hours=1)
        second=self.bridge.enqueue('reel','vineet_editz19',str(self.video),'Second clip',authorized=True,
            publish_at=later.isoformat(),reference='second')
        first=self.bridge.enqueue('reel','fantasy_legends91',str(self.video),'First clip',authorized=True,
            publish_at=earlier.isoformat(),reference='first')
        bridge=LocalBrowser(self.root)  # Same persisted queue after restart.
        with patch('hinglish_publish.local_browser.time.time',return_value=later.timestamp()+3600):
            check=bridge.claim()['job'];self.assertEqual(check['id'],first['preflight_id'])
            bridge.finish(check['id'],check['lease'],{'status':'complete','account':'fantasy_legends91'})
            claim=bridge.claim()['job'];self.assertEqual(claim['id'],first['id'])
            self.assertEqual(bridge.get(first['id'])['publish_at'],earlier.isoformat())
            bridge.phase(first['id'],claim['lease'],'sharing')
            interrupted=LocalBrowser(self.root)
            self.assertEqual(interrupted.get(first['id'])['status'],'needs_review')
            check=interrupted.claim()['job'];self.assertEqual(check['id'],second['preflight_id'])
            interrupted.finish(check['id'],check['lease'],{'status':'complete','account':'vineet_editz19'})
            self.assertEqual(interrupted.claim()['job']['id'],second['id'])
        self.assertEqual(sum(j['action']=='reel' for j in interrupted.data['jobs']),2)

    def test_explicit_continuation_replaces_only_its_stopped_pre_schedule_attempt(self):
        from datetime import datetime,timezone,timedelta
        with tempfile.TemporaryDirectory() as folder:
            bridge=LocalBrowser(folder);due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
            old=bridge.enqueue_youtube('UC'+'g'*22,'new00000001',due,'chat',authorized=True)
            claimed=bridge.claim('0.4.31',['youtube_schedule'])['job']
            bridge.cancel(old['id'])
            bridge.finish(old['id'],claimed['lease'],{'status':'needs_review','message':'Stopped before Schedule'})
            self.assertFalse(bridge.retire_stopped_youtube(old['id'],'another-chat'))
            self.assertTrue(bridge.retire_stopped_youtube(old['id'],'chat'))
            new=bridge.enqueue_youtube('UC'+'g'*22,'new00000001',due,'chat',authorized=True)
            self.assertNotEqual(old['id'],new['id']);self.assertEqual(new['video_id'],old['video_id'])
            claimed=bridge.claim('0.4.31',['youtube_schedule'])['job']
            bridge.phase(new['id'],claimed['lease'],'sharing');bridge.cancel(new['id'])
            bridge.finish(new['id'],claimed['lease'],{'status':'needs_review','message':'Check submitted outcome'})
            self.assertFalse(bridge.retire_stopped_youtube(new['id'],'chat'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / 'clip.mp4'
        self.video.write_bytes(b'user-selected-video')
        self.bridge = LocalBrowser(self.root)

    def enqueue(self):
        return self.bridge.enqueue('reel', 'vineet_editz19', str(self.video), 'Mumbai Indians journey. #Cricket', authorized=True)

    def test_upload_requires_intent_and_destination(self):
        for text in ('Do not upload this', "Don't post it", 'prepare a draft to post', 'schedule this upload'):
            self.assertFalse(upload_intent(text))
        self.assertTrue(upload_intent('Upload this video to Instagram @vineet_editz19'))
        with self.assertRaises(ValueError):
            self.bridge.enqueue('reel', 'vineet_editz19', str(self.video), 'caption')

    def test_instagram_transport_preserves_word_boundaries_when_editor_drops_raw_newlines(self):
        original="Mumbai Indians' IPL journey.\n\n#MumbaiIndians #IPL #Cricket"
        prepared=chrome_caption(original)
        self.assertEqual(prepared.replace('\n',''),"Mumbai Indians' IPL journey. #MumbaiIndians #IPL #Cricket")
        self.assertIn('\n\n',original)  # Source copy is retained; only the Chrome transport is normalized.

    def test_model_cannot_mix_publishing_with_editing(self):
        with self.assertRaises(ValueError):
            validate_plan({'steps': [{'tool': 'instagram', 'options': {}}, {'tool': 'clean', 'options': {}}]})
        self.assertIsNone(quick_plan('Upload this reel to Instagram'))

    def test_claim_is_once_and_media_scoped_to_lease(self):
        job = self.enqueue()
        claimed = self.bridge.claim()['job']
        self.assertEqual(claimed['id'], job['id'])
        self.assertIsNone(self.bridge.claim()['job'])
        with self.assertRaises(ValueError): self.bridge.media(job['id'], 'wrong', 0)
        data = self.bridge.media(job['id'], claimed['lease'], 0)
        self.assertEqual(data['bytes'], self.video.stat().st_size)
        self.video.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.bridge.media(job['id'], claimed['lease'], 0)
        with self.assertRaises(ValueError): self.bridge.phase(job['id'], claimed['lease'], 'running')

    def test_instagram_can_queue_without_caption_and_still_requires_file_and_account(self):
        job=self.bridge.enqueue('reel','vineet_editz19',str(self.video),'',authorized=True)
        self.assertEqual(job['caption'],'')
        self.assertEqual(self.bridge.claim('0.4.12')['job']['caption'],'')
        with self.assertRaises(ValueError):self.bridge.enqueue('reel','',str(self.video),'',authorized=True)
        with self.assertRaises(ValueError):self.bridge.enqueue('reel','vineet_editz19',str(self.video),None,authorized=True)

    def test_title_can_be_corrected_before_share_without_creating_another_upload(self):
        old=self.bridge.enqueue('reel','vineet_editz19',str(self.video),'',authorized=True)
        claim=self.bridge.claim('0.4.15')['job']
        self.bridge.phase(old['id'],claim['lease'],'running')
        self.bridge.finish(old['id'],claim['lease'],{'status':'needs_review','message':'Profile unavailable'})
        revised=self.bridge.enqueue('reel','vineet_editz19',str(self.video),'Local selected title',authorized=True)
        self.assertEqual(revised['id'],old['id']);self.assertEqual(revised['caption'],'Local selected title')
        self.assertEqual(len(self.bridge.data['jobs']),1)
        claim=self.bridge.claim('0.4.15')['job']
        self.bridge.phase(old['id'],claim['lease'],'sharing')
        self.bridge.finish(old['id'],claim['lease'],{'status':'needs_review','message':'Receipt unavailable'})
        with self.assertRaises(ValueError):
            self.bridge.enqueue('reel','vineet_editz19',str(self.video),'A different title',authorized=True)
        self.assertEqual(len(self.bridge.data['jobs']),1)

    def test_unstarted_scheduled_reel_can_move_to_now_without_duplicate(self):
        from datetime import datetime,timezone,timedelta
        due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        old=self.bridge.enqueue('reel','vineet_editz19',str(self.video),'Caption #Cricket',
            authorized=True,publish_at=due,reference='same-clip')
        check=old['preflight_id']
        updated=self.bridge.enqueue('reel','vineet_editz19',str(self.video),'Caption #Cricket',
            authorized=True,publish_at='',reference='same-clip')
        self.assertEqual(updated['id'],old['id'])
        self.assertEqual(updated['publish_at'],'')
        self.assertEqual(updated['not_before'],0)
        self.assertNotIn('preflight_id',updated)
        self.assertEqual(self.bridge.get(check)['status'],'cancelled')
        self.assertEqual(self.bridge.claim()['job']['id'],old['id'])
        self.assertEqual(sum(j['action']=='reel' for j in self.bridge.data['jobs']),1)

    def test_uncertain_share_can_only_be_recovered_by_read_only_matching_receipt(self):
        original=self.enqueue();claim=self.bridge.claim()['job']
        self.bridge.phase(original['id'],claim['lease'],'sharing')
        self.bridge.finish(original['id'],claim['lease'],{'status':'needs_review','message':'Receipt timed out'})
        check=self.bridge.verify_publication(original['id'])
        self.assertIsNone(self.bridge.claim('0.4.7')['job'])
        task=self.bridge.claim('0.4.8')
        self.assertEqual(task['job']['action'],'verify_reel')
        self.assertIsNone(task['media'])
        with self.assertRaises(ValueError):self.bridge.phase(check['id'],task['job']['lease'],'sharing')
        result={'status':'complete','account':'vineet_editz19',
            'url':'https://www.instagram.com/vineet_editz19/reel/NEW/',
            'caption_verified':True,'posted_at':time.time()}
        with self.assertRaises(ValueError):
            self.bridge.finish(check['id'],task['job']['lease'],{**result,'posted_at':check['after']-100})
        self.bridge.finish(check['id'],task['job']['lease'],result)
        restored=self.bridge.get(original['id'])
        self.assertEqual(restored['status'],'published')
        self.assertEqual(restored['url'],result['url'])
        self.assertEqual(sum(j['action']=='reel' for j in self.bridge.data['jobs']),1)

    def test_restarts_never_replay_claimed_uploads(self):
        job = self.enqueue()
        self.bridge.claim()
        restarted = LocalBrowser(self.root)
        self.assertEqual(restarted.get(job['id'])['status'], 'needs_review')
        self.assertIsNone(restarted.claim()['job'])
        self.assertEqual(restarted.enqueue('reel', 'vineet_editz19', str(self.video), 'Mumbai Indians journey. #Cricket', authorized=True)['id'], job['id'])

    def test_receipt_checks_do_not_block_new_destination_or_youtube_queue(self):
        from datetime import datetime, timezone, timedelta
        original=self.enqueue();claim=self.bridge.claim()['job']
        self.bridge.phase(original['id'],claim['lease'],'sharing')
        self.bridge.finish(original['id'],claim['lease'],{'status':'needs_review','message':'Receipt timed out'})
        check=self.bridge.verify_publication(original['id'])
        second=self.bridge.enqueue('reel','fantasy_legends91',str(self.video),'Second account caption',authorized=True)
        self.assertNotEqual(second['id'],original['id'])
        self.assertEqual(self.bridge.enqueue('reel','fantasy_legends91',str(self.video),'Second account caption',authorized=True)['id'],second['id'])
        due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        youtube=self.bridge.enqueue_youtube('UC'+'g'*22,'new00000001',due,'session',authorized=True)
        self.assertEqual(youtube['status'],'queued')
        self.assertEqual(self.bridge.get(check['id'])['status'],'queued')
        self.assertEqual(self.bridge.get(original['id'])['status'],'needs_review')

    def test_explicit_retry_reuses_caption_only_when_share_never_started(self):
        job=self.enqueue();lease=self.bridge.claim()['job']['lease']
        self.bridge.phase(job['id'],lease,'running')
        self.bridge.finish(job['id'],lease,{'status':'needs_review','message':'Page reloaded during account switch'})
        queued=self.bridge.retry_before_share(job['id'])
        self.assertEqual(queued['caption'],job['caption'])
        self.assertEqual(queued['id'],job['id'])
        new_lease=self.bridge.claim()['job']['lease']
        self.assertNotEqual(lease,new_lease)
        self.bridge.phase(job['id'],new_lease,'sharing')
        self.bridge.finish(job['id'],new_lease,{'status':'needs_review','message':'Connection lost after Share'})
        with self.assertRaises(ValueError):self.bridge.retry_before_share(job['id'])

    def test_new_authorized_request_retries_same_unsubmitted_job_but_never_uncertain_share(self):
        job=self.enqueue();lease=self.bridge.claim()['job']['lease']
        self.bridge.finish(job['id'],lease,{'status':'needs_review','message':'Unfinished composer'})
        retried=self.enqueue()
        self.assertEqual(retried['id'],job['id'])
        self.assertEqual(retried['status'],'queued')
        lease=self.bridge.claim()['job']['lease']
        self.bridge.phase(job['id'],lease,'sharing')
        self.bridge.finish(job['id'],lease,{'status':'needs_review','message':'Receipt unavailable'})
        self.assertEqual(self.enqueue()['status'],'needs_review')
        self.assertIsNone(self.bridge.claim()['job'])

    def test_retry_after_extension_reload_before_first_page_command(self):
        job = self.enqueue()
        lease = self.bridge.claim()['job']['lease']
        self.bridge.finish(job['id'], lease, {
            'status': 'needs_review',
            'message': 'Could not establish connection. Receiving end does not exist.'})
        self.assertEqual(self.bridge.get(job['id'])['last_phase'], 'queued')
        retried = self.bridge.retry_before_share(job['id'])
        self.assertEqual(retried['caption'], job['caption'])
        self.assertEqual(retried['id'], job['id'])
        self.assertNotEqual(self.bridge.claim()['job']['lease'], lease)

    def test_retry_refuses_missing_submission_boundary(self):
        job = self.enqueue()
        lease = self.bridge.claim()['job']['lease']
        self.bridge.finish(job['id'], lease, {'status': 'needs_review'})
        stored = next(j for j in self.bridge.data['jobs'] if j['id'] == job['id'])
        del stored['submission_started']
        with self.assertRaises(ValueError):
            self.bridge.retry_before_share(job['id'])

    def test_cannot_claim_success_without_matching_share_and_account(self):
        job = self.enqueue(); lease = self.bridge.claim()['job']['lease']
        result = {'status':'published', 'account':'vineet_editz19', 'url':'https://www.instagram.com/vineet_editz19/reel/NEW123/'}
        with self.assertRaises(ValueError): self.bridge.finish(job['id'], lease, result)
        self.bridge.phase(job['id'], lease, 'sharing')
        with self.assertRaises(ValueError): self.bridge.finish(job['id'], lease, {**result, 'account':'wrong_account'})
        with self.assertRaises(ValueError): self.bridge.finish(job['id'], lease, {**result, 'url':'https://evil.example/reel/NEW123/'})
        done=self.bridge.finish(job['id'], lease, result)
        self.assertEqual(done['status'],'published')
        self.assertEqual(self.enqueue()['id'],job['id'])

    def test_revoke_cancel_and_story_do_not_publish(self):
        key=self.bridge.pairing()['key']; job=self.enqueue(); lease=self.bridge.claim()['job']['lease']
        self.bridge.cancel(job['id'])
        self.assertTrue(self.bridge.phase(job['id'],lease,'sharing')['stop'])
        self.bridge.revoke()
        self.assertFalse(self.bridge.authorized(key))
        with self.assertRaises(ValueError): self.bridge.enqueue('story')
        snapshot=self.bridge.snapshot()
        self.assertNotIn('key',snapshot)
        self.assertNotIn('lease',snapshot['jobs'][0])
        self.assertNotIn('video',snapshot['jobs'][0])

    def test_preview_requires_new_extension_and_cannot_claim_publication(self):
        job=self.bridge.enqueue('preview','vineet_editz19',str(self.video),'Cricket preview',authorized=True)
        self.assertIsNone(self.bridge.claim()['job'])
        claimed=self.bridge.claim('0.1.1')['job']
        with self.assertRaises(ValueError):
            self.bridge.finish(job['id'],claimed['lease'],{'status':'published','account':'vineet_editz19','url':'https://www.instagram.com/vineet_editz19/reel/FAKE/'})
        done=self.bridge.finish(job['id'],claimed['lease'],{'status':'complete','account':'vineet_editz19','message':'Preview ready; nothing published.'})
        self.assertEqual(done['status'],'complete')
        self.assertFalse(done['url'])

    def test_planner_knows_bounded_local_chrome_tool(self):
        class Brain:
            name='local fixture'
            def json(self, system, data, schema, **kw):
                self_test.assertIn('independently of OpenAI', system)
                self_test.assertIn('instagram', data['tools'])
                return {'reply':'Uploading.', 'question':'', 'combine':False, 'steps':[{'tool':'instagram','options':{'instagram_action':'reel','instagram_account':'vineet_editz19'}}]}
            def close(self): pass
        self_test=self
        brain=Brain();brain.root=self.root
        # This test checks tool routing, using the owner's current40K planning
        # policy rather than a rootless fixture's unrelated8K fallback.
        with patch('hinglish_visuals.brain.open_brain',return_value=brain), \
                patch('hinglish_cut.feature_context.limits',return_value=(40960,40960)):
            value,_=plan(self.root,'Upload this reel to Instagram @vineet_editz19',[],[{'name':'clip.mp4','kind':'.mp4'}],False)
        self.assertEqual(value['steps'][0]['tool'],'instagram')


class BrowserHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.server,self.state=serve(self.root,0)
        self.base=f'http://127.0.0.1:{self.state.port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.temp.cleanup()
    def call(self,path,body=None,headers=None):
        with urlopen(Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})) as r:
            return json.load(r)
    def test_owner_can_preview_only_an_existing_reviewed_studio_task(self):
        from datetime import datetime,timedelta,timezone
        owner={'X-Hinglish-Token':self.state.token}
        task=self.state.local_browser.enqueue_youtube('UC'+'g'*22,'new00000001',
            (datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'session',authorized=True)
        with self.assertRaises(HTTPError):self.call('/api/local-browser/youtube-preview',{'id':task['id']})
        preview=self.call('/api/local-browser/youtube-preview',{'id':task['id']},owner)
        saved=self.state.local_browser.get(preview['id'])
        self.assertEqual(saved['action'],'youtube_schedule_preview');self.assertEqual(saved['video_id'],task['video_id'])
        self.assertNotEqual(saved['id'],task['id'])
        unrelated=self.state.local_browser.enqueue('inspect')
        with self.assertRaises(HTTPError):self.call('/api/local-browser/youtube-preview',{'id':unrelated['id']},owner)
    def test_extension_key_does_not_control_editor_and_editor_key_cannot_claim(self):
        editor={'X-Hinglish-Token':self.state.token}
        pair=self.call('/api/local-browser/pair',{},editor)
        browser={'X-Storylens-Browser':pair['key'],'Origin':'chrome-extension://'+'a'*32}
        with self.assertRaises(HTTPError):self.call('/api/local-browser/pair',{})
        with self.assertRaises(HTTPError):self.call('/api/assistant/session',{},browser)
        with self.assertRaises(HTTPError):self.call('/api/local-browser/worker/claim',{},editor)
        self.call('/api/local-browser/inspect',{},editor)
        claimed=self.call('/api/local-browser/worker/claim',{},browser)
        self.assertEqual(claimed['job']['action'],'inspect')
        self.call('/api/local-browser/worker/finish',{'id':claimed['job']['id'],'lease':claimed['job']['lease'],'result':{'status':'complete','account':'vineet_editz19','message':'Account checked.'}},browser)
        snapshot=self.call('/api/local-browser',headers=editor)
        self.assertTrue(snapshot['connected'])
        self.assertEqual(snapshot['jobs'][0]['status'],'complete')
        with urlopen(self.base+'/chrome.html') as r:
            html=r.read().decode()
        self.assertNotIn('__APP_TOKEN__',html)
        self.assertNotIn(pair['key'],html)


if __name__=='__main__':unittest.main()
