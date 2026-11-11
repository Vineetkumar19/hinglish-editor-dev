"""Campaign orchestration contracts with fake uploads and a fake Studio worker."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch,MagicMock

from hinglish_app.server import AppState
from hinglish_app.assistant_campaign import stage_review
from hinglish_app.assistant_publish import start
from hinglish_app.assistant_schedule import verify
from hinglish_publish.store import fingerprint


CHANNEL='UC'+'g'*22


class ScheduleTests(unittest.TestCase):
    def test_upload_now_timing_is_application_owned_without_bound_reference(self):
        from hinglish_app.campaign_memory import catalog,decide
        brain=SimpleNamespace(json=Mock(return_value={'action':'schedule','campaign_id':'fixture',
            'question':'','clip_indices':[1,2],'clock':'23:51:42.726980+05:30'}))
        result=decide(brain,self.assistant.snapshot(self.session),
            'upload 2 shorts on cricket yt channel now',catalog(self.assistant),{})
        self.assertEqual(result['clock'],'')
        self.assertNotIn('clock',brain.json.call_args.args[2]['properties'])

    def test_upload_now_repairs_repeated_historical_schedule_error(self):
        from hinglish_app.campaign_memory import catalog,decide
        brain=SimpleNamespace(json=Mock(side_effect=[
            {'action':'clarify','campaign_id':'fixture','question':'The release time has passed. Choose a future date.','clip_indices':[]},
            {'action':'schedule','campaign_id':'fixture','question':'','clip_indices':[1,2]}]))
        result=decide(brain,self.assistant.snapshot(self.session),
            'upload 2 shorts on cricket yt channel now (make it private)',catalog(self.assistant),{})
        self.assertEqual(result['action'],'schedule')
        self.assertEqual(result['clip_indices'],[1,2])
        self.assertIn('fresh timing',brain.json.call_args.args[1]['validation_error'])

    def test_upload_now_planner_preserves_requested_count_and_existing_modes(self):
        from hinglish_app.campaign_memory import catalog,decide
        brain=SimpleNamespace(json=Mock(side_effect=[
            {'action':'private','campaign_id':'fixture','question':'','clip_indices':[]},
            {'action':'private','campaign_id':'fixture','question':'','clip_indices':[1,2]}]))
        result=decide(brain,self.assistant.snapshot(self.session),
            'upload 2 shorts on gaming yt channel now (make it private)',catalog(self.assistant),{})
        self.assertEqual(result['action'],'private')
        self.assertEqual(result['clip_indices'],[1,2])
        self.assertEqual(brain.json.call_count,2)
        self.assertIn('schedule',brain.json.call_args.args[2]['properties']['action']['enum'])

    def test_new_upload_now_refreshes_expired_campaign_dates(self):
        campaign=json.loads((self.folder/'campaign.json').read_text('utf-8'))
        old_ids=self.state.publisher.store.add_batch([
            {'platform':'youtube','profile':'gaming','kind':'short','fingerprint':clip['fingerprint'],
             'video':clip['video'],'metadata':clip['metadata'],'visibility':'public'}
            for clip in campaign['clips'][:2]])
        for clip in campaign['clips']:
            clip['publish_at']=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        (self.folder/'campaign.json').write_text(json.dumps(campaign),'utf-8')
        self.assistant._message(self.session,'user','upload 2 shorts on cricket yt channel now (make it private)')
        message=self.assistant.snapshot(self.session)['messages'][-1]['id']
        self.assistant._update(self.session,active_request_message_id=message)
        stage_review(self.assistant,self.session,schedule=True,schedule_spec={'clip_indices':[1,2]})
        review=self.assistant.snapshot(self.session)['publishing_review']
        self.assertTrue(review['schedule'])
        self.assertEqual(len(review['rows']),2)
        self.assertTrue(all(datetime.fromisoformat(row['publish_at']).timestamp()>time.time()+60 for row in review['rows']))
        self.assertEqual(review['ids'],old_ids)
        self.assertTrue(all(self.state.publisher.store.get(key)['visibility']=='private' for key in old_ids))
        self.assertTrue(any('apply the schedule' in m['text'] for m in self.assistant.snapshot(self.session)['messages'] if m['role']=='assistant'))
        self.assertFalse(self.calls)
        self.assertFalse(self.state.local_browser.snapshot()['jobs'])

    def test_explicit_schedule_still_rejects_expired_dates(self):
        campaign=json.loads((self.folder/'campaign.json').read_text('utf-8'))
        for clip in campaign['clips']:
            clip['publish_at']=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        (self.folder/'campaign.json').write_text(json.dumps(campaign),'utf-8')
        self.assistant._message(self.session,'user','Schedule 2 shorts on cricket YouTube using the saved dates.')
        message=self.assistant.snapshot(self.session)['messages'][-1]['id']
        self.assistant._update(self.session,active_request_message_id=message)
        with self.assertRaisesRegex(ValueError,'has passed'):
            stage_review(self.assistant,self.session,schedule=True,schedule_spec={'clip_indices':[1,2]})
        self.assertFalse(self.calls)

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.state=AppState(self.root);self.assistant=self.state.assistant
        self.session=self.assistant.create()['id'];self.folder=self.root/'output/campaigns/fixture';self.folder.mkdir(parents=True)
        self.calls=[];self.events=[]
        self.accounts=patch.object(self.state.publisher,'accounts',return_value={'youtube':{'connected':True,'id':CHANNEL,'name':'Gaming'}})
        self.accounts.start();self.addCleanup(self.accounts.stop)
        clips=[]
        first=datetime.now(timezone.utc)+timedelta(days=2)
        for i in range(7):
            video=self.folder/f'short-{i}.mp4';video.write_bytes(f'export-{i}'.encode())
            clips.append({'index':i+1,'video':str(video),'fingerprint':fingerprint(video),'duration':30,
                'publish_at':(first+timedelta(days=i)).isoformat(),
                'metadata':{'title':f'Cricket moment {i}','description':'Actual video context. #Cricket #IPL #Shorts',
                            'tags':['Cricket'],'instagram_caption':'Actual video context.'}})
        (self.folder/'campaign.json').write_text(json.dumps({'status':'reviewed','profile':'gaming','channel_id':CHANNEL,
            'targets':[{'profile':'gaming','id':CHANNEL}],'clips':clips,'source':'original.mp4','model':'Local fixture'}),'utf-8')
        self.assistant._update(self.session,campaign=str(self.folder))
        owner=self
        class Provider:
            def __init__(self,*args):pass
            def publish(self,job,checkpoint):
                owner.calls.append(job);owner.events.append('upload')
                remote={'id':f'new{len(owner.calls):08d}','url':f'https://www.youtube.com/watch?v=new{len(owner.calls):08d}','privacy':'private'}
                checkpoint(remote);return remote,'uploaded_private'
        self.state.publisher.providers['youtube']=Provider
    def review(self):
        stage_review(self.assistant,self.session,schedule=True)
        return self.assistant.snapshot(self.session)['publishing_review']
    def wait(self):
        for _ in range(600):
            s=self.assistant.snapshot(self.session)
            if s['status'] not in ('planning','running'):return s
            time.sleep(.01)
        self.fail('Scheduling did not finish')
    def submit(self,review):
        return start(self.assistant,{'session':self.session,'review':review['id'],'made_for_kids':False,'synthetic_media':False})

    def test_seven_exports_stage_only_youtube_and_exact_dates(self):
        review=self.review()
        self.assertEqual(len(review['rows']),7)
        self.assertTrue(review['schedule'])
        self.assertEqual({self.state.publisher.store.get(i)['platform'] for i in review['ids']},{'youtube'})
        for row in review['rows']:
            self.assertEqual(self.state.publisher.store.get(row['id'])['due'],datetime.fromisoformat(row['publish_at']).timestamp())
        self.assertFalse(self.calls)
        self.assertEqual(self.review()['ids'],review['ids'])

    def test_missing_studio_connection_blocks_before_any_upload(self):
        review=self.review()
        with self.assertRaisesRegex(ValueError,'Enable YouTube Studio'):
            self.submit(review)
        self.assertFalse(self.calls)
        self.assertEqual(self.assistant.snapshot(self.session)['publishing_review']['state'],'review')

    def test_stale_review_cannot_start_when_new_edit_handoff_is_pending(self):
        review=self.review()
        self.assistant._update(self.session,edit_publish_checkpoint={'result':{'folder':str(self.root/'new-edit')}})
        with self.assertRaisesRegex(ValueError,'older batch'):self.submit(review)
        self.assertFalse(self.calls)

    def test_old_worker_cannot_repeat_false_sign_in_failure(self):
        review=self.review()
        for version in ('0.4.0','0.4.5'):
            with patch.object(self.state.local_browser,'snapshot',return_value={'youtube_scheduling':True,'extension_version':version}):
                with self.assertRaisesRegex(ValueError,'0.4.7'):
                    self.submit(review)
        self.assertFalse(self.calls)

    def test_scheduling_failure_reports_saved_uploads_separately(self):
        review=self.review()
        with patch.object(self.state.local_browser,'snapshot',return_value={'youtube_scheduling':True,'extension_version':'0.4.7'}), \
             patch('hinglish_app.assistant_schedule.run',side_effect=ValueError('Studio connection needs attention')):
            self.submit(review);result=self.wait()
        self.assertEqual(result['status'],'needs_review')
        self.assertIn('Scheduling stopped:',result['messages'][-1]['text'])
        self.assertIn('All 7 videos have saved private upload receipts',result['messages'][-1]['text'])
        self.assertIn('No new upload is needed',result['messages'][-1]['text'])

    def test_missing_remote_video_does_not_claim_that_receipt_proves_it_still_exists(self):
        from hinglish_app.assistant_schedule import UnavailableUploadError
        review=self.review()
        with patch.object(self.state.local_browser,'snapshot',return_value={'youtube_scheduling':True,'extension_version':'0.4.7'}),\
             patch('hinglish_app.assistant_schedule.run',side_effect=UnavailableUploadError('YouTube cannot find the saved video.')):
            self.submit(review);result=self.wait()
        self.assertEqual(result['status'],'needs_review')
        self.assertIn('No automatic re-upload',result['messages'][-1]['text'])
        self.assertNotIn('No new upload is needed',result['messages'][-1]['text'])

    def test_only_old_accidental_instagram_drafts_for_this_chat_batch_are_cancelled(self):
        campaign=json.loads((self.folder/'campaign.json').read_text('utf-8'))
        items=[{'platform':'instagram','profile':'gaming','kind':'short','video':c['video'],
                'fingerprint':c['fingerprint'],'metadata':c['metadata']} for c in campaign['clips']]
        old_ids=self.state.publisher.store.add_batch(items)
        unrelated=self.state.publisher.store.add_batch([{**items[0],'fingerprint':'unrelated'}])[0]
        self.assistant._message(self.session,'assistant','Old generic drafts',publish_ids=old_ids)
        review=self.review()
        self.assertEqual(len(review['ids']),7)
        self.assertTrue(all(self.state.publisher.store.get(i)['status']=='cancelled' for i in old_ids))
        self.assertEqual(self.state.publisher.store.get(unrelated)['status'],'draft')

    def test_old_video_from_other_campaign_is_never_handed_to_studio(self):
        from hinglish_app.assistant_schedule import run
        review=self.review();first=review['ids'][0]
        self.state.publisher.store.change(first,campaign='other-campaign',account_id=CHANNEL,
            remote={'id':'old00000001','privacy':'private'},status='uploaded_private')
        with patch.object(self.state.local_browser,'enqueue_youtube') as enqueue:
            with self.assertRaisesRegex(ValueError,'this campaign'):
                run(self.assistant,self.session,review)
        enqueue.assert_not_called()

    def test_all_new_uploads_precede_scheduling_and_only_verified_dates_complete(self):
        review=self.review();bridge=self.state.local_browser
        scheduled=set()
        def enqueue(channel,video,publish_at,session,authorized=False):
            self.assertEqual(len(self.calls),7)
            self.assertEqual(channel,CHANNEL);self.assertTrue(video.startswith('new'));self.assertTrue(authorized)
            self.events.append('schedule');scheduled.add(video)
            return {'id':video}
        def readback(root,job,date):
            if job['remote']['id'] not in scheduled:return None
            return {**job['remote'],'publish_at':date,'schedule_verified_at':time.time()}
        with patch.object(bridge,'snapshot',return_value={'youtube_scheduling':True}), \
             patch.object(bridge,'enqueue_youtube',side_effect=enqueue), \
             patch.object(bridge,'get',return_value={'status':'submitted','message':'Fake Studio submission'}), \
             patch('hinglish_app.assistant_schedule.verify',side_effect=readback):
            self.submit(review);result=self.wait()
        self.assertEqual(result['status'],'complete',result['stage'])
        self.assertEqual(self.events,['upload']*7+['schedule']*7)
        self.assertEqual(len(result['messages'][-1]['publish_results']),7)
        self.assertTrue(all(self.state.publisher.store.get(i)['status']=='scheduled' for i in review['ids']))
        self.submit(result['publishing_review'])
        self.assertEqual(len(self.calls),7)

    def test_youtube_readback_rejects_wrong_channel_copy_or_date(self):
        client=MagicMock();due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        job={'profile':'gaming','account_id':CHANNEL,'remote':{'id':'new00000001'},
             'metadata':{'title':'A title','description':'Actual description'}}
        item={'id':'new00000001','snippet':{'channelId':CHANNEL,**job['metadata']},
              'status':{'privacyStatus':'private','uploadStatus':'processed','publishAt':due}}
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':CHANNEL})):
            for changed in ({**item,'snippet':{**item['snippet'],'channelId':'wrong'}},
                            {**item,'snippet':{**item['snippet'],'title':'Wrong copy'}},
                            {**item,'status':{**item['status'],'publishAt':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()}}):
                client.videos.return_value.list.return_value.execute.return_value={'items':[changed]}
                with self.assertRaises(ValueError):verify(self.root,job,due)
            client.videos.return_value.list.return_value.execute.return_value={'items':[item]}
            self.assertEqual(verify(self.root,job,due)['publish_at'],due)

    def test_changed_schedules_reuse_same_uploads_for_arbitrary_future_dates(self):
        from hinglish_app.assistant_schedule import run
        old=self.review();bridge=self.state.local_browser
        for index,row in enumerate(old['rows']):
            self.state.publisher.store.change(row['id'],status='scheduled',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}',
                        'publish_at':row['publish_at'],'schedule_verified_at':time.time()})
        for first in ('2031-02-28','2032-02-29','2033-12-31'):
            stage_review(self.assistant,self.session,schedule=True,
                         schedule_spec={'first_date':first,'clock':'19:30','clip_indices':[1,2]})
            review=self.assistant.snapshot(self.session)['publishing_review'];submitted=set();handed=[];reads={}
            def readback(root,job,date,allow_reschedule=False):
                key=(job['remote']['id'],date)
                if key not in submitted:return None
                self.assertTrue(allow_reschedule)
                reads[key]=reads.get(key,0)+1
                if reads[key]==1:return None
                return {**job['remote'],'publish_at':date,'schedule_verified_at':time.time()}
            def enqueue(channel,video,date,session,*,authorized=False,allow_reschedule=False):
                self.assertTrue(authorized);self.assertTrue(allow_reschedule)
                self.assertEqual(channel,CHANNEL)
                submitted.add((video,date));handed.append(video);return {'id':video}
            with patch('hinglish_app.assistant_schedule.verify',side_effect=readback), \
                 patch.object(bridge,'enqueue_youtube',side_effect=enqueue), \
                 patch.object(bridge,'get',return_value={'status':'submitted','message':'Fixture'}), \
                 patch('hinglish_app.assistant_schedule.time.sleep'):
                run(self.assistant,self.session,review)
            final=self.assistant.snapshot(self.session)
            self.assertEqual(final['status'],'complete')
            self.assertEqual(final['publishing_review']['ids'],old['ids'][:2])
            self.assertEqual(handed,['new00000000','new00000001'])
            self.assertEqual(final['publishing_review']['rows'][0]['publish_at'][:10],first)
            self.assertFalse(self.calls)

    def test_transient_windows_save_lock_does_not_stop_remaining_schedules(self):
        from hinglish_app.assistant_schedule import run
        stage_review(self.assistant,self.session,schedule=True,schedule_spec={'clip_indices':[1,2]})
        review=self.assistant.snapshot(self.session)['publishing_review'];bridge=self.state.local_browser
        for index,key in enumerate(review['ids']):
            self.state.publisher.store.change(key,status='uploaded_private',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}','privacy':'private'})
        submitted=set();attempts=[];failures=[];original=Path.replace
        def locked(path,target):
            if Path(target).name==self.session+'.json' and len(failures)<3:
                failures.append(True);raise PermissionError('Windows sharing violation')
            return original(path,target)
        def enqueue(channel,video,due,session,**kwargs):
            attempts.append(video);submitted.add(video);return {'id':video}
        def readback(root,job,due,*args):
            if job['remote']['id'] not in submitted:return None
            return {**job['remote'],'publish_at':due,'schedule_verified_at':time.time()}
        with patch.object(Path,'replace',new=locked),patch('hinglish_app.assistant.time.sleep'), \
             patch('hinglish_app.assistant_schedule.verify',side_effect=readback), \
             patch.object(bridge,'enqueue_youtube',side_effect=enqueue), \
             patch.object(bridge,'get',return_value={'status':'submitted','message':'Fixture'}):
            run(self.assistant,self.session,review)
        self.assertEqual(len(failures),3);self.assertEqual(attempts,['new00000000','new00000001'])
        self.assertEqual(self.assistant.snapshot(self.session)['status'],'complete')
        saved=json.loads((self.assistant.folder/(self.session+'.json')).read_text('utf-8'))
        self.assertEqual(saved['status'],'complete');self.assertFalse(self.calls)

    def test_one_terminal_schedule_failure_does_not_skip_the_next_reviewed_video(self):
        from hinglish_app.assistant_schedule import run
        stage_review(self.assistant,self.session,schedule=True,schedule_spec={'clip_indices':[2,5]})
        review=self.assistant.snapshot(self.session)['publishing_review']
        for index,key in enumerate(review['ids']):
            self.state.publisher.store.change(key,status='uploaded_private',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}','privacy':'private'})
        second=self.state.publisher.store.get(review['ids'][1])
        remote={**second['remote'],'publish_at':review['rows'][1]['publish_at'],'schedule_verified_at':time.time()}
        with patch('hinglish_app.assistant_schedule.schedule_one',side_effect=[ValueError('First video unavailable'),remote]) as attempt:
            with self.assertRaisesRegex(ValueError,'First video unavailable'):
                run(self.assistant,self.session,review)
        self.assertEqual(attempt.call_count,2)
        self.assertEqual(self.state.publisher.store.get(review['ids'][1])['status'],'scheduled')
        self.assertEqual(len(self.assistant.snapshot(self.session)['publishing_review']['schedule_results']),1)

    def test_plain_resume_preserves_two_selected_clips_out_of_seven(self):
        stage_review(self.assistant,self.session,schedule=True,
            schedule_spec={'clip_indices':[2,5],'first_date':'2032-12-31','clock':'19:30'})
        before=self.assistant.snapshot(self.session)['publishing_review']
        stage_review(self.assistant,self.session,schedule=True)
        after=self.assistant.snapshot(self.session)['publishing_review']
        self.assertEqual(after['ids'],before['ids'])
        self.assertEqual([r['publish_at'] for r in after['rows']],[r['publish_at'] for r in before['rows']])

    def test_status_question_and_screenshot_use_partial_receipts_without_restarting_batch(self):
        stage_review(self.assistant,self.session,schedule=True,schedule_spec={'clip_indices':[1,2]})
        review=self.assistant.snapshot(self.session)['publishing_review'];bridge=self.state.local_browser
        for index,key in enumerate(review['ids']):
            self.state.publisher.store.change(key,status='scheduled',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}',
                        'privacy':'private','publish_at':(datetime.fromisoformat(review['rows'][index]['publish_at'])-timedelta(days=7)).isoformat(),
                        'schedule_verified_at':time.time()})
        task=bridge.enqueue_youtube(CHANNEL,'new00000000',review['rows'][0]['publish_at'],self.session,authorized=True,allow_reschedule=True)
        wire=bridge.claim('0.4.7',['youtube_schedule'])['job'];bridge.phase(wire['id'],wire['lease'],'sharing')
        bridge.finish(wire['id'],wire['lease'],{'status':'submitted',**{k:wire[k] for k in ('channel_id','video_id','publish_at')}})
        self.state.publisher.store.change(review['ids'][0],browser_schedule_id=task['id'])
        self.assistant._update(self.session,status='needs_review')
        image=self.root/'status.png';image.write_bytes(b'fixture screenshot')
        attachment=self.assistant.attach(self.session,image)
        with patch('hinglish_app.assistant.plan') as generic,patch('hinglish_app.assistant_publish.start') as start:
            self.assistant.send(self.session,'only 1 video date has changed what about other')
            result=self.wait();answer=result['messages'][-1]['text']
            self.assertIn('0 of 2 requested release dates',answer)
            self.assertIn('submitted to Studio; awaiting verification',answer)
            self.assertIn('not started for this request',answer)
            self.assertNotIn('Which video',answer)
            self.assistant.send(self.session,'see',attachment_ids=[attachment['id']])
            result=self.wait();self.assertIn('not started for this request',result['messages'][-1]['text'])
        generic.assert_not_called();start.assert_not_called();self.assertFalse(self.calls)

    def test_status_question_while_running_preserves_the_worker_and_steps(self):
        self.review();self.assistant._update(self.session,status='running',stage='Verifying first video',steps=[{'tool':'publish'}])
        with patch('hinglish_app.assistant_publish.start') as start:
            result=self.assistant.send(self.session,'what is the scheduling status?')
        self.assertEqual(result['status'],'running');self.assertEqual(result['stage'],'Verifying first video')
        self.assertEqual(result['steps'],[{'tool':'publish'}]);start.assert_not_called()

    def test_resume_after_first_submission_verifies_it_and_schedules_only_the_remaining_video(self):
        from hinglish_app.assistant_schedule import run
        path=self.folder/'campaign.json';campaign=json.loads(path.read_text('utf-8'))
        campaign['clips']=campaign['clips'][:2];path.write_text(json.dumps(campaign),'utf-8')
        first=(datetime.now(timezone.utc)+timedelta(days=12)).date().isoformat()
        stage_review(self.assistant,self.session,schedule=True,schedule_spec={'first_date':first,'clip_indices':[1,2]})
        original=self.assistant.snapshot(self.session)['publishing_review']
        for index,key in enumerate(original['ids']):
            self.state.publisher.store.change(key,status='scheduled',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}',
                        'privacy':'private','publish_at':(datetime.fromisoformat(original['rows'][index]['publish_at'])-timedelta(days=8)).isoformat(),
                        'schedule_verified_at':time.time()})
        self.assistant._update(self.session,status='needs_review')
        stage_review(self.assistant,self.session,schedule=True)
        review=self.assistant.snapshot(self.session)['publishing_review']
        self.assertTrue(review['allow_reschedule'])
        self.assertEqual(review['ids'],original['ids'])
        submitted={'new00000000'};handed=[]
        def readback(root,job,due,*args):
            if job['remote']['id'] not in submitted:return None
            return {**job['remote'],'publish_at':due,'schedule_verified_at':time.time()}
        def enqueue(channel,video,due,session,**kwargs):
            self.assertTrue(kwargs['allow_reschedule']);handed.append(video);submitted.add(video);return {'id':video}
        with patch('hinglish_app.assistant_schedule.verify',side_effect=readback), \
             patch.object(self.state.local_browser,'enqueue_youtube',side_effect=enqueue), \
             patch.object(self.state.local_browser,'get',return_value={'status':'submitted','message':'Fixture'}):
            run(self.assistant,self.session,review)
        self.assertEqual(handed,['new00000001']);self.assertFalse(self.calls)
        final=self.assistant.snapshot(self.session)
        self.assertEqual(final['status'],'complete');self.assertEqual(final['publishing_review']['scheduled_count'],2)

    def test_exact_followup_routes_local_model_to_existing_batch(self):
        from hinglish_app.assistant_campaign import followup
        brain=SimpleNamespace(name='Local fixture',json=Mock(return_value={'action':'schedule','campaign_id':'fixture','question':''}),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_app.assistant.plan') as generic:
            self.assistant.send(self.session,'you didnt scheduled the shorts on the yt channel ?? plzz do that')
            result=self.wait()
        self.assertEqual(result['status'],'needs_review',result['stage'])
        self.assertEqual(len(result['publishing_review']['rows']),7)
        generic.assert_not_called();self.assertFalse(self.calls)

    def test_misspelled_correction_reuses_seven_uploads_and_current_youtube_context(self):
        review=self.review()
        for index,row in enumerate(review['rows']):
            self.state.publisher.store.change(row['id'],status='uploaded_private',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}','privacy':'private'})
        self.assistant._message(self.session,'user','Upload these seven on my gaming YouTube channel.')
        self.assistant._message(self.session,'assistant','Private uploads completed.')
        self.assistant._update(self.session,status='idle')
        brain=SimpleNamespace(name='Local fixture',json=Mock(return_value={
            'action':'schedule','campaign_id':'fixture','question':'','first_date':'','clock':''}),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_app.assistant.plan') as generic,patch('hinglish_publish.campaign.prepare') as extract:
            self.assistant.send(self.session,'shedule them ... 1 video per day.. not all in a dat')
            result=self.wait()
        new=result['publishing_review']
        self.assertEqual(new['ids'],review['ids'])
        self.assertEqual(new['uploaded_count'],7)
        self.assertEqual(new['scheduled_count'],0)
        self.assertEqual(new.get('instagram_rows',[]),[])
        dates=[datetime.fromisoformat(r['publish_at']) for r in new['rows']]
        self.assertEqual([d-dates[0] for d in dates],[timedelta(days=i) for i in range(7)])
        data=brain.json.call_args.args[1]
        self.assertEqual(data['reference_campaign'],'fixture')
        self.assertEqual(data['active_task']['review']['youtube_count'],7)
        self.assertEqual(data['active_task']['review']['instagram_count'],0)
        self.assertIn('shedule them',data['active_task']['conversation'][-1]['text'])
        self.assertIn('7 already have upload receipts',result['messages'][-1]['text'])
        generic.assert_not_called();extract.assert_not_called();self.assertFalse(self.calls)

    def test_per_day_rebuilds_same_date_draft_into_seven_days(self):
        path=self.folder/'campaign.json';campaign=json.loads(path.read_text('utf-8'))
        for clip in campaign['clips']:clip['publish_at']=campaign['clips'][0]['publish_at']
        path.write_text(json.dumps(campaign),'utf-8')
        review=self.review()
        dates=[datetime.fromisoformat(r['publish_at']) for r in review['rows']]
        self.assertEqual(len({d.date() for d in dates}),7)
        self.assertEqual(len({d.time() for d in dates}),1)
        self.assertFalse(self.calls)

    def test_explicit_new_daily_time_preserves_uploaded_ids_and_sets_review_only(self):
        old=self.review();first=(datetime.now(timezone.utc)+timedelta(days=3)).date().isoformat()
        for index,row in enumerate(old['rows']):
            self.state.publisher.store.change(row['id'],status='uploaded_private',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}','privacy':'private'})
        stage_review(self.assistant,self.session,schedule=True,schedule_spec={'first_date':first,'clock':'19:00'})
        new=self.assistant.snapshot(self.session)['publishing_review']
        self.assertEqual(old['ids'],new['ids']);self.assertTrue(new['allow_reschedule'])
        self.assertTrue(all(datetime.fromisoformat(r['publish_at']).hour==19 for r in new['rows']))
        self.assertEqual(new['state'],'review');self.assertFalse(self.calls)

    def test_expired_first_day_needs_new_date_without_shifting_or_duplicating(self):
        path=self.folder/'campaign.json';campaign=json.loads(path.read_text('utf-8'))
        campaign['clips'][0]['publish_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        path.write_text(json.dumps(campaign),'utf-8')
        with self.assertRaisesRegex(ValueError,'new future start date'):
            self.review()
        self.assertFalse(self.state.publisher.store.list());self.assertFalse(self.calls)

    def test_unqualified_reference_rejects_model_switch_to_old_campaign(self):
        from hinglish_app.campaign_memory import catalog,decide
        cards=catalog(self.assistant)
        cards.append({**cards[0],'id':'older-cricket','source':'old.mp4'})
        snapshot=self.assistant.snapshot(self.session)
        brain=SimpleNamespace(json=Mock(side_effect=[
            {'action':'schedule','campaign_id':'older-cricket','question':''},
            {'action':'schedule','campaign_id':'fixture','question':''}]))
        answer=decide(brain,snapshot,'shedule them ... 1 video per day',cards,{
            'messages':[{'role':'user','text':'Exactly ONE cricket Short on two Instagram accounts on Oct 19.'}]})
        self.assertEqual(answer['campaign_id'],'fixture')
        self.assertEqual(brain.json.call_count,2)
        self.assertEqual(brain.json.call_args.args[2]['properties']['campaign_id']['enum'],['','fixture'])
        self.assertNotIn('messages',brain.json.call_args.args[1]['shared_memory'])
        self.assertFalse(self.calls)

    def test_literal_seven_pm_is_an_application_input_not_a_model_argument(self):
        from hinglish_app.campaign_memory import catalog,decide
        first=(datetime.now(timezone.utc)+timedelta(days=4)).date().isoformat()
        brain=SimpleNamespace(json=Mock(side_effect=[
            {'action':'schedule','campaign_id':'fixture','question':'','first_date':first,'clock':'18:00'},
            {'action':'schedule','campaign_id':'fixture','question':'','first_date':first,'clock':'19:00'}]))
        result=decide(brain,self.assistant.snapshot(self.session),
            f'Schedule these seven existing YouTube videos one per day from {first} at 7 p.m. India time.',
            catalog(self.assistant),{})
        self.assertEqual(result['clock'],'19:00');self.assertEqual(brain.json.call_count,1)
        self.assertNotIn('clock',brain.json.call_args.args[2]['properties'])
        self.assertFalse(self.calls)

    def test_inclusive_five_day_range_selects_five_and_keeps_two_uploads_untouched(self):
        old=self.review()
        for index,row in enumerate(old['rows']):
            self.state.publisher.store.change(row['id'],status='uploaded_private',account_id=CHANNEL,
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}','privacy':'private'})
        first=(datetime.now(timezone.utc)+timedelta(days=4)).date()
        spec={'first_date':first.isoformat(),'end_date':(first+timedelta(days=4)).isoformat(),
              'clock':'19:00','clip_indices':[1,2,3,4,5]}
        stage_review(self.assistant,self.session,schedule=True,schedule_spec=spec)
        review=self.assistant.snapshot(self.session)['publishing_review']
        self.assertEqual(review['ids'],old['ids'][:5]);self.assertEqual(review['uploaded_count'],5)
        self.assertEqual(review['rows'][-1]['publish_at'][:10],spec['end_date'])
        self.assertTrue(all(self.state.publisher.store.get(i)['status']=='uploaded_private' for i in old['ids'][5:]))
        self.assertFalse(self.calls)
        # Enforcing a range also happens before any remote operation if a
        # malformed model tries to smuggle all seven through the runner.
        with self.assertRaisesRegex(ValueError,'exceed the requested date range'):
            stage_review(self.assistant,self.session,schedule=True,schedule_spec={**spec,'clip_indices':[]})

    def test_plain_english_range_without_year_preserves_both_endpoints(self):
        from hinglish_app.assistant_publishing_context import schedule_literals
        year=datetime.now().year
        for text in ('from 20 october to 24 october, 1 video everyday',
                     'from 20 to 24 October, one per day',
                     'from 20 and 24 October, one per day'):
            spec=schedule_literals(text)
            self.assertEqual(spec['first_date'],f'{year}-10-20')
            self.assertEqual(spec['end_date'],f'{year}-10-24')

    def test_schedule_it_binds_current_batch_and_preserves_shared_month_dates(self):
        from hinglish_app.campaign_memory import catalog,decide
        cards=catalog(self.assistant)
        cards.append({**cards[0],'id':'older','source':'old.mp4'})
        brain=SimpleNamespace(json=Mock(return_value={'action':'schedule','campaign_id':'fixture',
            'question':'','clip_indices':[1,2], 'clock':'19:00:00+05:30',
            'first_date':'2030-10-22','end_date':'2030-10-23'}))
        result=decide(brain,self.assistant.snapshot(self.session),
            'schedule it for 21 and 22 october 2030',cards,{})
        self.assertEqual(result['first_date'],'2030-10-21')
        self.assertEqual(result['end_date'],'2030-10-22')
        self.assertEqual(result['clock'],'')
        self.assertEqual(brain.json.call_args.args[1]['reference_campaign'],'fixture')
        self.assertNotIn('clock',brain.json.call_args.args[2]['properties'])
        self.assertEqual(brain.json.call_count,1)
        self.assertFalse(self.calls)

    def test_explicit_scheduling_command_continues_previously_authorized_uploads(self):
        from hinglish_app.assistant_schedule import continue_uploaded
        review=self.review()
        for index,key in enumerate(review['ids']):
            self.state.publisher.store.change(key,status='uploaded_private',authorized_at=time.time(),
                made_for_kids=False,synthetic_media=False,account_id=CHANNEL,
                remote={'id':f'new{index:08d}','privacy':'private'})
        with patch('hinglish_app.assistant_publish.start') as start_upload:
            self.assertTrue(continue_uploaded(self.assistant,self.session,'I want you to schedule them one per day.'))
        self.assertEqual(start_upload.call_args.args[1]['review'],review['id'])
        self.assertIs(start_upload.call_args.args[1]['made_for_kids'],False)
        self.assertEqual(start_upload.call_args.kwargs,{'internal':True})
        self.assertFalse(self.calls)

    def test_scheduling_explanation_and_unapproved_uploads_stay_in_review(self):
        from hinglish_app.assistant_schedule import continue_uploaded
        self.review()
        with patch('hinglish_app.assistant_publish.start') as start_upload:
            for text in ('Explain how to schedule them.', 'Do not schedule them.', 'Schedule them as a draft only.',
                         'Schedule them one per day.'):
                self.assertFalse(continue_uploaded(self.assistant,self.session,text))
        start_upload.assert_not_called();self.assertFalse(self.calls)

    def test_seven_videos_five_days_asks_conflict_without_execution_arguments(self):
        from hinglish_app.campaign_memory import catalog,decide
        first=(datetime.now(timezone.utc)+timedelta(days=4)).date()
        question='Seven videos need seven days at one per day. Use only five, or extend the end date?'
        brain=SimpleNamespace(json=Mock(return_value={'action':'clarify','campaign_id':'fixture',
            'first_date':first.isoformat(),'end_date':(first+timedelta(days=4)).isoformat(),
            'clock':'18:00:00+05:30','clip_indices':[],'question':question}))
        result=decide(brain,self.assistant.snapshot(self.session),
            f'Schedule all seven videos from {first} to {first+timedelta(days=4)}, one per day.',catalog(self.assistant),{})
        self.assertEqual(result['action'],'clarify');self.assertEqual(result['campaign_id'],'')
        self.assertEqual(result['question'],question);self.assertEqual(result['clock'],'')
        self.assertFalse(self.calls)

    def test_new_chat_voice_request_cannot_recall_another_chats_exports(self):
        session=self.assistant.create()['id']
        failed=self.root/'output/campaigns/failed-attempt';failed.mkdir()
        self.assistant._update(session,campaign=str(failed))
        voice=self.root/'voice.webm';voice.write_bytes(b'voice fixture')
        attachment=self.assistant.attach(session,voice,kind='voice')
        text='the seven shorts that you have created for the gaming channel now please schedule it for the seven consecutive days'
        brain=SimpleNamespace(name='Local fixture',json=Mock(return_value={'action':'schedule','campaign_id':'fixture','question':''}),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_app.assistant_media.transcribe_voice',return_value=text), \
             patch('hinglish_publish.campaign.prepare') as extract,patch('hinglish_app.assistant.plan') as generic:
            self.assistant.send(session,'',voice_id=attachment['id'],profile='cricket')
            for _ in range(600):
                result=self.assistant.snapshot(session)
                if result['status'] not in ('planning','running','transcribing'):break
                time.sleep(.01)
        self.assertEqual(result['status'],'failed',result['stage'])
        self.assertEqual(result['campaign'],str(failed))
        self.assertFalse(result.get('publishing_review'))
        self.assertEqual(len(brain.json.call_args.args[1]['saved_campaigns']),0)
        extract.assert_not_called();generic.assert_not_called();self.assertFalse(self.calls)

    def test_unfinished_attempt_is_rejected_and_local_model_repairs_its_choice(self):
        from hinglish_app.assistant_campaign import followup
        failed=self.root/'output/campaigns/unfinished';failed.mkdir()
        draft=json.loads((self.folder/'campaign.json').read_text('utf-8'))
        draft['status']='planned';draft['source']='kkr final.mp4'
        for c in draft['clips']:c['video']=str(failed/Path(c['video']).name)
        (failed/'campaign.json').write_text(json.dumps(draft),'utf-8')
        brain=SimpleNamespace(name='Local fixture',json=Mock(side_effect=[
            {'action':'schedule','campaign_id':'unfinished','question':''},
            {'action':'schedule','campaign_id':'fixture','question':''}]),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_publish.campaign.prepare') as extract:
            followup(self.assistant,self.session,'the seven Shorts you created for gaming, schedule them',lambda _:None)
        result=self.assistant.snapshot(self.session)
        self.assertEqual(brain.json.call_count,2)
        self.assertEqual(result['campaign_memory_ref'],'fixture')
        self.assertEqual(len(result['publishing_review']['rows']),7)
        first=brain.json.call_args_list[0]
        self.assertEqual(first.args[1]['ready_campaign_ids'],['fixture'])
        self.assertIn('fixture',first.args[2]['properties']['campaign_id']['enum'])
        self.assertIn('validation_error',brain.json.call_args_list[1].args[1])
        extract.assert_not_called();self.assertFalse(self.calls)

    def test_explicit_missing_source_clarifies_instead_of_using_another_ready_video(self):
        from hinglish_app.campaign_memory import catalog,decide
        from hinglish_niche.profiles import CURRENT,use
        observed=[]
        def answer(*args,**kwargs):
            observed.append(CURRENT.get())
            return {'action':'clarify','campaign_id':'','question':'The KKR attempt has no exports. Do you mean the finished Mumbai Indians batch?'}
        brain=SimpleNamespace(json=Mock(side_effect=answer))
        with use({'profile':'cricket','feedback':'irrelevant editing preferences'}):
            result=decide(brain,{},'Schedule only the old KKR attempt, not Mumbai Indians.',catalog(self.assistant),{})
            self.assertEqual(CURRENT.get()['profile'],'cricket')
        self.assertEqual(result['action'],'clarify')
        self.assertEqual(observed,[{'profile':'general'}])
        self.assertFalse(self.calls)

    def test_repeated_invalid_model_choice_never_stages_or_uploads(self):
        from hinglish_app.assistant_campaign import followup
        brain=SimpleNamespace(name='Local fixture',json=Mock(return_value={
            'action':'schedule','campaign_id':'unknown','question':''}),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_app.assistant_campaign.stage_review') as stage:
            with self.assertRaisesRegex(ValueError,'could not select a ready saved batch'):
                followup(self.assistant,self.session,'Schedule the seven Shorts.',lambda _:None)
        stage.assert_not_called();self.assertFalse(self.calls)

    def test_four_complete_then_initial_rejection_resumes_only_remaining_three(self):
        from googleapiclient.errors import ResumableUploadError
        from httplib2 import Response
        from hinglish_publish.providers import YouTubeUploadRejected
        review=self.review();attempts=[]
        error=YouTubeUploadRejected(ResumableUploadError(Response({'status':'403'}),
            b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'))
        class Provider:
            def __init__(self,*args):pass
            def publish(self,job,checkpoint):
                attempts.append(job['id'])
                if len(attempts)==5:raise error
                index=review['ids'].index(job['id'])+1
                remote={'id':f'new{index:08d}','url':f'https://www.youtube.com/watch?v=new{index:08d}','privacy':'private'}
                checkpoint(remote);return remote,'uploaded_private'
        self.state.publisher.providers['youtube']=Provider
        with patch.object(self.state.local_browser,'snapshot',return_value={'youtube_scheduling':True}), \
             patch('hinglish_app.assistant_schedule.run') as schedule:
            self.submit(review);failed=self.wait()
            schedule.assert_not_called()
            resumed=failed['publishing_review']
            self.assertEqual(resumed['uploaded_count'],4);self.assertTrue(resumed['retryable'])
            self.assertEqual(resumed['scheduled_count'],0)
            self.assertEqual(self.state.publisher.store.get(review['ids'][4])['status'],'blocked')
            self.assertIn('upload limit',failed['messages'][-1]['text'])
            # Run synchronously so fake scheduling can expose a terminal snapshot.
            def finished(*args):self.assistant._update(self.session,status='complete')
            schedule.side_effect=finished
            self.submit(resumed);result=self.wait()
            self.assertEqual(result['status'],'complete')
            schedule.assert_called_once()
        self.assertEqual(attempts[:5],review['ids'][:5])
        self.assertEqual(attempts[5:],review['ids'][4:])
        self.assertTrue(all(attempts.count(i)==1 for i in review['ids'][:4]))

    def test_legacy_initial_error_reopens_review_but_ambiguous_errors_do_not(self):
        review=self.review();rows=review['rows'];results=[]
        for row in rows[:4]:
            remote={'id':'new00000001','url':'https://www.youtube.com/watch?v='+row['id'][:11],'privacy':'private'}
            self.state.publisher.store.change(row['id'],status='uploaded_private',remote=remote,account_id=CHANNEL,
                made_for_kids=False,synthetic_media=False)
            results.append({'url':remote['url']})
        self.state.publisher.store.change(rows[4]['id'],status='needs_review',account_id=CHANNEL,
            error='Check YouTube before retrying; the saved remote ID is preserved.')
        review['state']='needs_review';self.assistant._update(self.session,publishing_review=review)
        self.assistant._message(self.session,'assistant','Publishing stopped: ResumableUploadError. Check the saved YouTube result before retrying.',
            publish_results=results,error=True)
        presented=self.assistant.snapshot(self.session)['publishing_review']
        self.assertTrue(presented['retryable']);self.assertEqual(presented['uploaded_count'],4)
        self.assertIs(presented['made_for_kids'],False);self.assertIs(presented['synthetic_media'],False)
        self.assertTrue(all(row['url'] for row in presented['rows'][:4]))
        self.assistant._message(self.session,'assistant','Publishing stopped: TimeoutError. Check the saved result.',
            publish_results=results,error=True)
        self.assertFalse(self.assistant.snapshot(self.session)['publishing_review']['retryable'])
        # A later ambiguous attempt must prevent reuse of an older rejection.
        self.state.publisher.store.change(rows[4]['id'],upload_failure={'phase':'transferring','safe_retry':False})
        self.assertFalse(self.assistant.snapshot(self.session)['publishing_review']['retryable'])


class QueueScheduleTests(unittest.TestCase):
    def test_reschedule_authority_is_scoped_to_exact_video_and_instant(self):
        from hinglish_publish.local_browser import LocalBrowser
        with tempfile.TemporaryDirectory() as temp:
            bridge=LocalBrowser(Path(temp));first=datetime.now(timezone.utc)+timedelta(days=10)
            ordinary=bridge.enqueue_youtube(CHANNEL,'new00000001',first.isoformat(),'s',authorized=True)
            changed=bridge.enqueue_youtube(CHANNEL,'new00000001',first.isoformat(),'s',authorized=True,allow_reschedule=True)
            later=bridge.enqueue_youtube(CHANNEL,'new00000001',(first+timedelta(days=20)).isoformat(),'s',authorized=True,allow_reschedule=True)
            self.assertFalse(ordinary['allow_reschedule']);self.assertTrue(changed['allow_reschedule'])
            self.assertEqual(len({ordinary['id'],changed['id'],later['id']}),3)
            self.assertEqual(changed['video_id'],ordinary['video_id'])
            with self.assertRaises(ValueError):
                bridge.enqueue_youtube(CHANNEL,'new00000001',first.isoformat(),'s',authorized=True,allow_reschedule='true')

    def test_preview_isolated_from_scheduling_and_never_crosses_submission_boundary(self):
        from hinglish_publish.local_browser import LocalBrowser
        with tempfile.TemporaryDirectory() as temp:
            bridge=LocalBrowser(Path(temp));due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
            preview=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True,preview=True)
            self.assertIsNone(bridge.claim('0.4.1',['youtube_schedule','youtube_preview'])['job'])
            task=bridge.claim('0.4.7',['youtube_schedule','youtube_preview'])['job']
            with self.assertRaises(ValueError):bridge.phase(task['id'],task['lease'],'sharing')
            with self.assertRaises(ValueError):bridge.media(task['id'],task['lease'],0)
            result={'status':'complete','controls_verified':True,'driver_version':'0.4.7',
                    **{k:task[k] for k in ('video_id','channel_id','publish_at')}}
            with self.assertRaises(ValueError):bridge.finish(task['id'],task['lease'],{**result,'video_id':'wrong000001'})
            done=bridge.finish(task['id'],task['lease'],result)
            self.assertEqual(done['status'],'complete');self.assertFalse(done['submission_started'])
            actual=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)
            self.assertNotEqual(actual['id'],preview['id'])

    def test_explicit_retry_reuses_exact_pre_submission_task_and_invalidates_old_lease(self):
        from hinglish_publish.local_browser import LocalBrowser
        with tempfile.TemporaryDirectory() as temp:
            bridge=LocalBrowser(Path(temp));due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
            original=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)
            claimed=bridge.claim('0.4.1',['youtube_schedule'])['job']
            bridge.finish(original['id'],claimed['lease'],{'status':'needs_review','message':'Studio sign-in is required.'})
            retried=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)
            self.assertEqual(retried['id'],original['id']);self.assertEqual(retried['status'],'queued')
            self.assertEqual(len(retried['attempts']),1)
            with self.assertRaises(ValueError):bridge.phase(original['id'],claimed['lease'],'running')
            next_claim=bridge.claim('0.4.1',['youtube_schedule'])['job']
            self.assertEqual(next_claim['video_id'],'new00000001')

    def test_ambiguous_schedule_submission_is_never_requeued(self):
        from hinglish_publish.local_browser import LocalBrowser
        with tempfile.TemporaryDirectory() as temp:
            bridge=LocalBrowser(Path(temp));due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
            original=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)
            claimed=bridge.claim('0.4.1',['youtube_schedule'])['job']
            bridge.phase(original['id'],claimed['lease'],'sharing')
            bridge.finish(original['id'],claimed['lease'],{'status':'needs_review','message':'Connection lost after Schedule'})
            retried=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)
            self.assertEqual(retried['status'],'needs_review');self.assertTrue(retried['submission_started'])
            self.assertIsNone(bridge.claim('0.4.1',['youtube_schedule'])['job'])

    def test_only_new_extension_with_studio_permission_claims_exact_receipt(self):
        from hinglish_publish.local_browser import LocalBrowser
        with tempfile.TemporaryDirectory() as temp:
            bridge=LocalBrowser(Path(temp));due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
            with self.assertRaises(ValueError):bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session')
            job=bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)
            self.assertIsNone(bridge.claim('0.3.0')['job'])
            self.assertIsNone(bridge.claim('0.4.0')['job'])
            claimed=bridge.claim('0.4.0',['youtube_schedule'])['job']
            self.assertEqual(claimed['video_id'],'new00000001')
            with self.assertRaises(ValueError):bridge.media(job['id'],claimed['lease'],0)
            result={'status':'submitted',**{k:claimed[k] for k in ('channel_id','video_id','publish_at')}}
            with self.assertRaises(ValueError):bridge.finish(job['id'],claimed['lease'],result)
            bridge.phase(job['id'],claimed['lease'],'sharing')
            with self.assertRaises(ValueError):bridge.finish(job['id'],claimed['lease'],{**result,'video_id':'old00000001'})
            self.assertEqual(bridge.finish(job['id'],claimed['lease'],result)['status'],'submitted')
            self.assertEqual(bridge.enqueue_youtube(CHANNEL,'new00000001',due,'session',authorized=True)['id'],job['id'])

