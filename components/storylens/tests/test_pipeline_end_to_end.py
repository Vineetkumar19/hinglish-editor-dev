"""Contract tests: real chat/orchestration/stores, simulated model/media/platforms.

All files live in TemporaryDirectory. No production account or network is used.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from hinglish_app.server import AppState
from hinglish_app import assistant_pipeline as pipeline
from hinglish_app.assistant_distribution import arm
from hinglish_publish.local_browser import LocalBrowser

CHANNEL = 'UC' + 'g' * 22


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = AppState(self.root)
        self.a = self.state.assistant
        self.sid = self.a.create()['id']
        self.accounts = patch.object(self.state.publisher, 'accounts', return_value={
            'youtube': {'connected': True, 'id': CHANNEL, 'name': 'Gaming'}})
        self.accounts.start()
        self.addCleanup(self.accounts.stop)
        self.bridge = self.state.local_browser
        self.bridge.bind('gaming', 'gaming_handle')
        self.bridge.claim('0.4.7', ['youtube_schedule'])
        self.first = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
        self.uploads = []
        owner = self

        class Provider:
            def __init__(self, *args): pass
            def publish(self, job, checkpoint):
                owner.uploads.append(job['id'])
                remote = {'id': f'new{len(owner.uploads):08d}', 'privacy': 'private',
                          'url': f'https://www.youtube.com/watch?v=new{len(owner.uploads):08d}'}
                checkpoint(remote)
                return remote, 'uploaded_private'
        self.state.publisher.providers['youtube'] = Provider

    def wait(self):
        for _ in range(1000):
            current = self.a.snapshot(self.sid)
            if current['status'] not in ('planning', 'running', 'transcribing'):
                return current
            time.sleep(.01)
        self.fail('Fixture pipeline did not finish')

    def test_instagram_receipt_cannot_complete_an_unfinished_youtube_schedule(self):
        review={'id':'owned','ids':[],'rows':[{'schedule_verified':False}],
                'instagram_rows':[{'status':'published'}],'schedule':True}
        state={'status':'complete','pipeline':{'automatic':True,'phase':'waiting_instagram',
               'authorized_review':'owned'},'publishing_review':review}
        self.a._update(self.sid,pipeline=state['pipeline'])
        with patch.object(self.a,'snapshot',return_value=state):
            self.assertFalse(pipeline.tick(self.a,self.sid))
        self.assertEqual(self.a._get(self.sid)['status'],'needs_review')
        self.assertEqual(self.a._get(self.sid)['pipeline']['phase'],'attention')

    def test_explicit_resume_reuses_this_chats_authorized_receipt_without_replanning(self):
        review={'id':'owned','ids':['saved-upload'],'uploaded_count':1,'retryable':True,
            'declarations_confirmed':True,'made_for_kids':False,'synthetic_media':False,
            'schedule':True,'rows':[{'schedule_verified':False,'publish_at':self.first+'T19:00:00+05:30'}],
            'instagram_rows':[{'status':'published'}]}
        state={'pipeline':{'authorized_review':'owned'},'publishing_review':review}
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertTrue(pipeline.resume_saved(self.a,self.sid,
                'Resume the saved workflow. No new extraction or upload.',state))
            start.assert_called_once()
            self.assertEqual(start.call_args.args[1]['review'],'owned')
            self.assertFalse(self.uploads)

    def test_prompt_to_seven_paired_days_recovers_copy_failure_without_reediting(self):
        source_dir = self.root / 'videos'
        source_dir.mkdir()
        source = source_dir / 'mi final.mp4'
        source.write_bytes(b'long recording')
        (source_dir / 'other.mp4').write_bytes(b'not requested')
        exports = []
        for i in range(7):
            path = self.root / f'export-{i}.mp4'
            path.write_bytes(f'clip{i}'.encode())
            exports.append(str(path))
        brain = Mock(name='local_model')
        brain.name = 'local fixture'
        brain.json.return_value = {
            'action': 'edit', 'reply': 'Preparing.', 'count': 7, 'max_seconds': 50,
            'profile': 'gaming', 'platforms': 'paired', 'first_date': self.first,
            'clock': '19:00', 'captions': True}
        text = (f'From "{source_dir}" take mi final.mp4 and extract seven shorts with captions. '
                f'Upload on my gaming channel on YouTube and Instagram one per day from {self.first} '
                'at 19:00. Not made for kids, no synthetic media.')
        def render(payload):
            self.assertEqual(payload['source_paths'], [str(source)])
            self.assertTrue(payload['shorts_captions'])
            job = {'id': 'fixture-render', 'status': 'complete',
                   'result': {'folder': str(self.root), 'previews': exports}}
            self.state.jobs[job['id']] = job
            return job
        copies = []
        failed = [False]
        def copy(root, path, *args, **kwargs):
            copies.append(path.name)
            if path.name == 'short-03.mp4' and not failed[0]:
                failed[0] = True
                raise TimeoutError('Local inference timed out')
            return {'title': path.stem, 'description': 'The clip story. #Cricket #IPL #Shorts',
                    'instagram_caption': 'The clip story. #Cricket #IPL #Shorts',
                    'tags': ['Cricket']}, 'local fixture'
        actual = {}
        enqueue = self.bridge.enqueue_youtube
        schedules = []
        def studio(channel, video, due, session, **kwargs):
            schedules.append(video)
            task = enqueue(channel, video, due, session, **kwargs)
            claimed = self.bridge.claim('0.4.7', ['youtube_schedule'])['job']
            self.assertEqual(claimed['id'], task['id'])
            self.bridge.phase(task['id'], claimed['lease'], 'sharing')
            self.bridge.finish(task['id'], claimed['lease'], {
                'status': 'submitted', 'video_id': video, 'channel_id': channel,
                'publish_at': task['publish_at']})
            actual[video] = task['publish_at']
            return task
        def verify(root, job, due, *args):
            if job['remote']['id'] not in actual: return None
            return {**job['remote'], 'publish_at': actual[job['remote']['id']],
                    'schedule_verified_at': time.time()}
        with patch('hinglish_visuals.brain.open_brain', return_value=brain), \
             patch.object(self.state, 'create_job', side_effect=render) as renderer, \
             patch('hinglish_app.assistant_media.outputs', return_value=exports), \
             patch('hinglish_shorts.source.open_video', return_value=SimpleNamespace(
                 width=1080, height=1920, duration=35)), \
             patch('hinglish_app.assistant_publish.transcripts'), \
             patch('hinglish_app.assistant_distribution.prepare_copy', side_effect=copy), \
             patch.object(self.bridge, 'enqueue_youtube', side_effect=studio), \
             patch('hinglish_app.assistant_schedule.verify', side_effect=verify):
            self.a.send(self.sid, text, profile='gaming')
            interrupted = self.wait()
            self.assertEqual(interrupted['pipeline']['phase'], 'waiting_retry')
            self.assertEqual(len(list((self.root/'output/campaigns').glob('*'))), 1)
            self.assertEqual(self.uploads, [])
            pipeline.change(self.a, self.sid, next_retry=0)
            self.assertTrue(pipeline.tick(self.a, self.sid))
            completed = self.wait()
            self.assertEqual(completed['status'], 'complete', completed.get('stage'))
            renderer.assert_called_once()
        review = completed['publishing_review']
        self.assertEqual(review['scheduled_count'], 7)
        self.assertEqual(review['instagram_queued_count'], 7)
        self.assertEqual(len(self.uploads), 7)
        self.assertEqual(len(schedules), 7)
        self.assertEqual(copies.count('short-01.mp4'), 1)
        self.assertEqual(copies.count('short-02.mp4'), 1)
        self.assertEqual(copies.count('short-03.mp4'), 2)
        self.assertEqual(len(list((self.root/'output/campaigns').glob('*'))), 1)
        for youtube, insta in zip(review['rows'], review['instagram_rows']):
            self.assertEqual(youtube['video'], insta['video'])
            self.assertEqual(youtube['publish_at'], insta['publish_at'])
        # Seven separate days, process restart before each one, no chat reminder.
        for row in review['instagram_rows']:
            queue = LocalBrowser(self.root)
            due = datetime.fromisoformat(row['publish_at']).timestamp()
            with patch('hinglish_publish.local_browser.time.time', return_value=due-200):
                check = queue.claim('0.4.7', ['youtube_schedule'])['job']
                self.assertEqual(check['action'], 'inspect')
                queue.finish(check['id'], check['lease'], {'status': 'complete', 'account': 'gaming_handle'})
                self.assertIsNone(queue.claim('0.4.7', ['youtube_schedule'])['job'])
            with patch('hinglish_publish.local_browser.time.time', return_value=due+1):
                reel = queue.claim('0.4.7', ['youtube_schedule'])['job']
                self.assertEqual(reel['id'], row['browser_job_id'])
                queue.phase(reel['id'], reel['lease'], 'sharing')
                queue.finish(reel['id'], reel['lease'], {'status': 'published',
                    'account': 'gaming_handle', 'url': 'https://www.instagram.com/reel/fixture' + reel['id'] + '/'})
        self.assertEqual(LocalBrowser(self.root).readiness()['published'], 7)

    def test_legacy_or_unknown_uploads_never_gain_autonomous_authority(self):
        self.a._update(self.sid, status='interrupted')
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertFalse(pipeline.tick(self.a, self.sid))
            start.assert_not_called()

    def test_single_prompt_instagram_recovers_copy_and_publishes_without_second_user_turn(self):
        source=self.root/'mi final.mp4';source.write_bytes(b'long-video')
        clip=self.root/'edited-short.mp4';clip.write_bytes(b'rendered-short')
        clip.with_suffix('.txt').write_text('Rohit Sharma Mumbai Indians 2011 se. 10 saal 16 saal.','utf-8')
        self.bridge.bind('cricket','cricket_handle')
        text=f'{source}\n take mi final and extract 1 short clip n upload on my cricket insta page'
        from hinglish_app.assistant_edit_workflow import constraints
        from hinglish_app.assistant_distribution import context
        facts=constraints(text,[],context(self.root))
        calls=[]
        caption='Rohit Sharma and Mumbai Indians are the focus of this IPL retrospective. The clip explores leadership and the team’s journey. #RohitSharma #MumbaiIndians #IPL'
        def answer(system,data,schema,**kwargs):
            if 'attached_media' in data:
                return {'action':'edit','reply':'Preparing.','count':1,'max_seconds':50,'profile':'cricket',
                        'platforms':'instagram','first_date':facts['first_date'],'clock':facts['clock'],'captions':True}
            calls.append(data)
            if len(calls)<=3:return {'instagram_caption':'Rohit Sharma in 2015. #RohitSharma #MumbaiIndians #IPL'}
            return {'instagram_caption':caption}
        brain=Mock();brain.name='local fixture';brain.json.side_effect=answer
        def render(payload):
            self.assertEqual(payload['source_paths'],[str(source)])
            result={'id':'one-render','status':'complete','result':{'folder':str(self.root),'previews':[str(clip)]}}
            self.state.jobs[result['id']]=result;return result
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),\
             patch.object(self.state,'create_job',side_effect=render) as renderer,\
             patch('hinglish_app.assistant_media.outputs',return_value=[str(clip)]),\
             patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(width=1080,height=1920,duration=33)),\
             patch('hinglish_app.assistant_publish.transcripts'),\
             patch('hinglish_publish.metadata.generate_youtube',side_effect=AssertionError('Instagram must not depend on YouTube metadata')):
            self.a.send(self.sid,text,profile='gaming')
            result=self.wait()
        self.assertEqual(result['status'],'complete',result['stage'])
        self.assertEqual(len([m for m in result['messages'] if m['role']=='user']),1)
        renderer.assert_called_once()
        review=result['publishing_review'];self.assertFalse(review['rows'])
        row=review['instagram_rows'][0]
        self.assertEqual(row['account'],'cricket_handle');self.assertEqual(row['caption'],caption)
        self.assertEqual(row['publish_at'],'');self.assertTrue(row['immediate'])
        self.assertEqual(len(calls),4);self.assertIn('source_evidence',calls[-1])
        self.assertFalse(self.uploads);self.assertFalse(self.state.publisher.store.list())
        job=self.bridge.claim('0.4.11')['job'];self.assertEqual(job['id'],row['browser_job_id'])
        self.bridge.phase(job['id'],job['lease'],'sharing')
        self.bridge.finish(job['id'],job['lease'],{'status':'published','account':'cricket_handle',
            'url':'https://www.instagram.com/cricket_handle/reel/ONEPROMPT/'})
        pipeline.tick(self.a,self.sid)
        self.assertEqual(self.a.snapshot(self.sid)['pipeline']['phase'],'complete')

    def test_caption_free_single_prompt_extracts_and_queues_without_any_writing_dependency(self):
        self._caption_free_flow()

    def test_no_captions_with_instagram_title_uses_the_local_selected_title(self):
        self._caption_free_flow(' (no captions need) just add title when uploading on instagram',True)

    def _caption_free_flow(self,suffix='',title_only=False):
        import json
        from hinglish_app.assistant_distribution import WORKFLOW
        policy={'burn_in_captions':False,'instagram_captions':False,'publishing_copy':'minimal'}
        (self.root/'config.workflow.local.json').write_text(json.dumps({**WORKFLOW,'content_features':policy}),'utf-8')
        source=self.root/'mi final.mp4';source.write_bytes(b'long source')
        clip=self.root/'01 - Rohit-Sharma-Mumbai-Indians.mp4';clip.write_bytes(b'clip')
        self.bridge.bind('cricket','cricket_handle')
        text=f'{source}\ntake mi final and extract 1 short clip n upload on my cricket insta page'+suffix
        from hinglish_app.assistant_edit_workflow import constraints
        facts=constraints(text,[],WORKFLOW)
        brain=Mock();brain.name='local fixture'
        brain.json.return_value={'action':'edit','reply':'Preparing.','count':1,'max_seconds':50,
            'profile':'cricket','platforms':'instagram','first_date':facts['first_date'],'clock':facts['clock'],'captions':True}
        def render(payload):
            self.assertFalse(payload['shorts_captions'])
            result={'id':'caption-free-render','status':'complete','result':{'folder':str(self.root),'previews':[str(clip)]}}
            self.state.jobs[result['id']]=result;return result
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),\
             patch.object(self.state,'create_job',side_effect=render) as renderer,\
             patch('hinglish_app.assistant_media.outputs',return_value=[str(clip)]),\
             patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(width=1080,height=1920,duration=33)),\
             patch('hinglish_app.assistant_publish.transcripts',side_effect=AssertionError('No copy transcription')) as transcripts,\
             patch('hinglish_publish.metadata.generate_youtube',side_effect=AssertionError('No extra YouTube writer')) as youtube,\
             patch('hinglish_publish.metadata.generate_instagram',side_effect=AssertionError('No Instagram writer')) as instagram:
            self.a.send(self.sid,text,profile='gaming')
            result=self.wait()
        self.assertEqual(result['status'],'complete',result['stage'])
        self.assertEqual(len([m for m in result['messages'] if m['role']=='user']),1)
        renderer.assert_called_once();youtube.assert_not_called();instagram.assert_not_called();transcripts.assert_not_called()
        brain.json.assert_called_once()
        row=result['publishing_review']['instagram_rows'][0]
        self.assertEqual(row['account'],'cricket_handle')
        self.assertEqual(row['caption'],'Rohit Sharma Mumbai Indians' if title_only else '')
        self.assertEqual(row['metadata']['title'],'Rohit Sharma Mumbai Indians')
        self.assertEqual(row['publish_at'],'');self.assertFalse(result['publishing_review']['ids'])

    def test_pre_share_browser_failure_recovers_after_extension_update_without_new_prompt(self):
        clip=self.root/'clip.mp4';clip.write_bytes(b'clip')
        pipeline.begin(self.a,self.sid,'Extract one short and upload on Instagram',
                       [{'tool':'shorts'},{'tool':'distribute','options':{}}],['source'])
        job=self.bridge.enqueue('reel','gaming_handle',str(clip),'',session=self.sid,authorized=True)
        claimed=self.bridge.claim('0.4.12')['job']
        self.bridge.finish(job['id'],claimed['lease'],{'status':'needs_review',
            'message':'Keep one Instagram working tab open. Storylens will reuse it instead of creating more tabs.'})
        review={'id':'review','ids':[],'rows':[],'state':'queued','instagram_rows':[
            {'id':'clip','browser_job_id':job['id'],'status':'needs_review'}]}
        self.a._update(self.sid,publishing_review=review,status='needs_review')
        pipeline.change(self.a,self.sid,phase='attention',authorized_review='review')
        later=self.bridge.get(job['id'])['finished']+10
        with patch('hinglish_app.assistant_pipeline.time.time',return_value=later):
            pipeline.tick(self.a,self.sid)
            self.assertEqual(self.bridge.get(job['id'])['status'],'needs_review')
            self.bridge.claim('0.4.13')
            pipeline.tick(self.a,self.sid)
        self.assertEqual(self.bridge.get(job['id'])['status'],'queued')
        self.assertEqual(self.a.snapshot(self.sid)['pipeline']['instagram_retries'][job['id']],1)
        self.assertEqual(len(self.bridge.data['jobs']),1)
        # A newly opened Instagram tab can still be navigating when Chrome
        # tries to reattach the packaged listener. Resume the same pre-Share job.
        claimed=self.bridge.claim('0.4.13')['job']
        self.bridge.finish(job['id'],claimed['lease'],{'status':'needs_review',
            'message':'Cannot access contents of the page. Extension manifest must request permission to access the respective host.'})
        with patch('hinglish_app.assistant_pipeline.time.time',return_value=later+30):
            pipeline.tick(self.a,self.sid)
        self.assertEqual(self.bridge.get(job['id'])['status'],'queued')
        self.assertEqual(self.a.snapshot(self.sid)['pipeline']['instagram_retries'][job['id']],2)
        self.assertEqual(len(self.bridge.data['jobs']),1)
        claimed=self.bridge.claim('0.4.13')['job']
        self.bridge.phase(job['id'],claimed['lease'],'sharing')
        self.bridge.finish(job['id'],claimed['lease'],{'status':'needs_review','message':'Receiving end does not exist.'})
        with patch('hinglish_app.assistant_pipeline.time.time',return_value=later+100):pipeline.tick(self.a,self.sid)
        self.assertEqual(self.bridge.get(job['id'])['status'],'needs_review')
        self.assertEqual(len(self.bridge.data['jobs']),1)

    def test_new_request_does_not_recover_old_exports_after_a_render_failure(self):
        self.a._update(self.sid,shorts_paths=['old-short'],campaign='old-campaign')
        pipeline.begin(self.a,self.sid,'Extract shorts from the new video and upload',
                       [{'tool':'shorts'},{'tool':'distribute','options':{}}],['new-source'])
        self.a._update(self.sid,status='failed')
        pipeline.failed(self.a,self.sid,TimeoutError('renderer timed out'))
        snapshot=self.a.snapshot(self.sid)
        self.assertEqual(snapshot['shorts_paths'],[])
        self.assertEqual(snapshot['pipeline']['phase'],'editing')
        with patch('hinglish_app.assistant_distribution.from_outputs') as handoff:
            self.assertFalse(pipeline.tick(self.a,self.sid))
            handoff.assert_not_called()

    def test_profile_adapter_update_resumes_same_job_and_restores_requested_title(self):
        import json
        (self.root/'config.workflow.local.json').write_text(json.dumps({'content_features':{
            'burn_in_captions':False,'instagram_captions':False,'publishing_copy':'minimal'}}),'utf-8')
        clip=self.root/'clip.mp4';clip.write_bytes(b'clip')
        pipeline.begin(self.a,self.sid,'Extract one short and upload to Instagram, no captions, just add title',
            [{'tool':'shorts'},{'tool':'distribute','options':{}}],['source'])
        job=self.bridge.enqueue('reel','gaming_handle',str(clip),'',session=self.sid,authorized=True,reference='clip')
        claimed=self.bridge.claim('0.4.14')['job']
        self.bridge.phase(job['id'],claimed['lease'],'running')
        self.bridge.finish(job['id'],claimed['lease'],{'status':'needs_review','message':'Instagram has not opened the destination profile.'})
        review={'id':'review','ids':[],'rows':[],'state':'queued','instagram_rows':[{'id':'clip','video':str(clip),'caption':'',
            'metadata':{'title':'Local cricket title'},'status':'needs_review','browser_job_id':job['id'],'publish_at':''}]}
        self.a._update(self.sid,publishing_review=review,status='needs_review')
        pipeline.change(self.a,self.sid,phase='attention',authorized_review='review')
        later=self.bridge.get(job['id'])['finished']+10
        with patch('hinglish_app.assistant_pipeline.time.time',return_value=later):
            pipeline.tick(self.a,self.sid)
            self.assertEqual(self.bridge.get(job['id'])['status'],'needs_review')
            self.bridge.claim('0.4.15');pipeline.tick(self.a,self.sid)
        saved=self.bridge.get(job['id'])
        self.assertEqual(saved['status'],'queued');self.assertEqual(saved['caption'],'Local cricket title')
        self.assertEqual(len(self.bridge.data['jobs']),1)
        self.assertEqual(self.a.snapshot(self.sid)['publishing_review']['instagram_rows'][0]['caption'],'Local cricket title')

    def test_approval_is_not_invented_from_unrelated_previous_batch(self):
        pipeline.begin(self.a, self.sid, 'Extract 2 shorts and post on both platforms',
                       [{'tool': 'shorts'}, {'tool': 'distribute', 'options': {}}], ['source'])
        review = {'id': 'current', 'ids': ['new'], 'upload_requested': True, 'state': 'review'}
        with patch('hinglish_app.assistant_publish.start') as start:
            pipeline.prepared(self.a, self.sid, review)
            start.assert_not_called()
        self.assertTrue(self.a.snapshot(self.sid)['messages'][-1]['question'])

    def test_stop_and_retry_budget_are_respected(self):
        pipeline.begin(self.a, self.sid, 'Extract 2 shorts and post on both platforms',
                       [{'tool': 'shorts'}, {'tool': 'distribute', 'options': {}}], ['source'])
        self.a._update(self.sid, shorts_paths=['finished'], status='failed')
        for i in range(3):
            pipeline.failed(self.a, self.sid, TimeoutError('timed out'))
            self.assertEqual(self.a.snapshot(self.sid)['pipeline']['attempts'], i+1)
        pipeline.failed(self.a, self.sid, TimeoutError('timed out'))
        self.assertEqual(self.a.snapshot(self.sid)['pipeline']['phase'], 'attention')
        self.a._update(self.sid, stop=True, status='interrupted')
        self.assertFalse(pipeline.tick(self.a, self.sid))

    def test_pause_button_stops_a_pending_automatic_retry(self):
        pipeline.begin(self.a,self.sid,'Extract shorts and upload on both platforms',
                       [{'tool':'distribute','options':{}}],['source'])
        self.a._update(self.sid,status='failed',shorts_paths=['finished'])
        pipeline.failed(self.a,self.sid,TimeoutError('timed out'))
        self.a.stop(self.sid)
        saved=self.a.snapshot(self.sid)
        self.assertEqual(saved['pipeline']['phase'],'paused')
        self.assertEqual(saved['status'],'stopped')
        self.assertFalse(pipeline.tick(self.a,self.sid))

    def test_restart_only_continues_the_exact_authorized_review(self):
        from hinglish_publish.store import fingerprint
        video=self.root/'clip.mp4';video.write_bytes(b'fixture')
        metadata={'title':'Moment','description':'The moment. #Story #Highlights #Shorts',
                  'instagram_caption':'The moment.','tags':['Story']}
        key=self.state.publisher.store.add_batch([{
            'video':str(video),'fingerprint':fingerprint(video),'platform':'youtube','profile':'gaming',
            'kind':'short','metadata':metadata,'visibility':'private'}])[0]
        self.state.publisher.store.change(key,status='uploaded_private',account_id=CHANNEL,
            remote={'id':'new00000001','privacy':'private','url':'https://www.youtube.com/watch?v=new00000001'})
        review={'id':'review','state':'scheduling','ids':[key],'rows':[{'id':key,'metadata':metadata}],
                'declarations_confirmed':True,'made_for_kids':False,'synthetic_media':False}
        pipeline.begin(self.a,self.sid,'Extract shorts and post on both platforms',
                       [{'tool':'distribute','options':{}}],['source'])
        pipeline.change(self.a,self.sid,phase='publishing',authorized_review='review')
        self.a._update(self.sid,status='interrupted',publishing_review=review)
        def resumed(*args,**kwargs):
            self.a._update(self.sid,status='complete')
        with patch('hinglish_app.assistant_publish.start',side_effect=resumed) as start:
            self.assertTrue(pipeline.tick(self.a,self.sid))
            self.wait()
            start.assert_called_once()
            self.assertEqual(start.call_args.args[1]['review'],'review')
        # A new review is not authorized by the old workflow.
        self.a._update(self.sid,status='interrupted',publishing_review={**review,'id':'different'})
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertFalse(pipeline.tick(self.a,self.sid))
            start.assert_not_called()
        # An unknown upload outcome cannot be replayed after restart either.
        self.state.publisher.store.change(key,status='needs_review',remote={})
        self.a._update(self.sid,status='interrupted',publishing_review=review)
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertFalse(pipeline.tick(self.a,self.sid))
            start.assert_not_called()

    def test_approved_workflow_waits_for_chrome_then_continues_without_another_prompt(self):
        pipeline.begin(self.a,self.sid,'Extract shorts and post on Instagram',
                       [{'tool':'distribute','options':{}}],['source'])
        review={'id':'review','state':'review','ids':[],'rows':[],
                'instagram_rows':[{'id':'reel1','status':'draft'}],'upload_requested':True}
        self.bridge.seen=0
        pipeline.prepared(self.a,self.sid,review)
        self.assertEqual(self.a.snapshot(self.sid)['pipeline']['phase'],'waiting_executor')
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertFalse(pipeline.tick(self.a,self.sid))
            start.assert_not_called()
        self.bridge.claim('0.4.7',['youtube_schedule'])
        def started(*args,**kwargs):
            self.a._update(self.sid,status='complete')
        with patch('hinglish_app.assistant_publish.start',side_effect=started) as start:
            self.assertTrue(pipeline.tick(self.a,self.sid))
            self.wait()
            start.assert_called_once()

    def test_arming_a_saved_slot_after_its_due_time_reuses_its_receipt(self):
        clip = self.root/'clip.mp4'
        clip.write_bytes(b'clip')
        from hinglish_publish.store import fingerprint
        row = {'id': 'batch:gaming:1', 'profile': 'gaming', 'account': 'gaming_handle',
               'video': str(clip), 'fingerprint': fingerprint(clip), 'caption': 'Story #Cricket',
               'publish_at': (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        review = {'id': 'review', 'ids': [], 'rows': [], 'instagram_rows': [row]}
        arm(self.a, self.sid, review)
        original = row['browser_job_id']
        with patch('hinglish_app.assistant_distribution.time.time', return_value=time.time()+172800):
            arm(self.a, self.sid, review)
        self.assertEqual(row['browser_job_id'], original)
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']), 1)

    def test_restart_reclaims_preparation_without_changing_the_original_request(self):
        steps=[{'tool':'shorts'}, {'tool':'distribute','options':{'clock':'19:00'}}]
        request='Extract shorts and post on both platforms'
        pipeline.begin(self.a,self.sid,request,steps,['original'])
        self.a._update(self.sid,status='running',shorts_paths=['finished'],last_result={'folder':str(self.root)})
        pipeline.checkpoint(self.a,self.sid)
        from hinglish_app.assistant import Assistant
        restarted=Assistant(self.state)
        self.assertEqual(restarted.snapshot(self.sid)['status'],'interrupted')
        def prepared(*args):
            restarted._update(self.sid,status='needs_review')
        with patch('hinglish_app.assistant_distribution.from_outputs',side_effect=prepared) as handoff, \
             patch.object(self.state,'create_job') as renderer:
            self.assertTrue(pipeline.tick(restarted,self.sid))
            for _ in range(200):
                if restarted.snapshot(self.sid)['status']!='running':break
                time.sleep(.01)
            renderer.assert_not_called()
            self.assertEqual(handoff.call_args.args[3],request)

    def test_local_queue_checkpoint_retries_windows_lock_and_survives_reload(self):
        original=Path.replace
        collisions=[]
        def replace(path,target):
            if Path(target).name=='state.json' and len(collisions)<3:
                collisions.append(True)
                raise PermissionError('Windows sharing lock')
            return original(path,target)
        with patch.object(Path,'replace',new=replace),patch('hinglish_app.durable_json.time.sleep'):
            self.bridge.bind('cricket','cricket_handle')
        self.assertEqual(len(collisions),3)
        self.assertEqual(LocalBrowser(self.root).snapshot()['accounts']['cricket'],'cricket_handle')


if __name__ == '__main__':
    unittest.main()
