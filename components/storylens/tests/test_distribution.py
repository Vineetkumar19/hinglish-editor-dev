import json
from pathlib import Path
import tempfile
import time
from datetime import datetime,timedelta
import unittest
from unittest.mock import patch,Mock

from hinglish_app.server import AppState
from hinglish_app.assistant_distribution import stage,decision,WORKFLOW,IST
from hinglish_app.assistant_publish import start
from hinglish_publish.store import fingerprint
from hinglish_publish.local_browser import LocalBrowser


class DistributionTests(unittest.TestCase):
    def test_post_now_followup_reuses_both_queued_reels_without_another_source_or_model_call(self):
        from hinglish_app.assistant_distribution import arm
        from hinglish_app.assistant_post_now import followup
        (self.root/'config.workflow.local.json').write_text(json.dumps({**WORKFLOW,'publishing_defaults':{'made_for_kids':False,'synthetic_media':False}}),'utf-8')
        stage(self.a,self.session,{**self.spec(['instagram']),'campaign_ids':['cricket'],'clip_indices':[1,2]})
        review=self.a.snapshot(self.session)['publishing_review'];arm(self.a,self.session,review)
        before=[(r['id'],r['browser_job_id'],r['video'],r['caption']) for r in review['instagram_rows']]
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertTrue(followup(self.a,self.session,'i dont want to schedule .. post now',self.a.snapshot(self.session)))
            start.assert_called_once()
        updated=self.a.snapshot(self.session)['publishing_review']
        self.assertTrue(updated['allow_reschedule'])
        self.assertTrue(all(r['immediate'] and not r['publish_at'] for r in updated['instagram_rows']))
        self.assertEqual(before,[(r['id'],r['browser_job_id'],r['video'],r['caption']) for r in updated['instagram_rows']])
        arm(self.a,self.session,updated)
        reels=[j for j in self.bridge.data['jobs'] if j['action']=='reel']
        self.assertEqual(len(reels),2)
        self.assertTrue(all(not j['publish_at'] and not j['not_before'] for j in reels))

    def test_post_now_review_only_does_not_move_queue_and_sharing_is_not_replayed(self):
        from hinglish_app.assistant_distribution import arm
        from hinglish_app.assistant_post_now import followup
        import copy
        stage(self.a,self.session,{**self.spec(['instagram']),'campaign_ids':['cricket'],'clip_indices':[1,2]})
        review=self.a.snapshot(self.session)['publishing_review'];arm(self.a,self.session,review)
        before=copy.deepcopy(self.bridge.data['jobs'])
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertTrue(followup(self.a,self.session,'i dont want to schedule .. post now. Review first. Do not publish or queue.',self.a.snapshot(self.session)))
            start.assert_not_called()
        self.assertEqual(self.bridge.data['jobs'],before)
        reel=next(j for j in self.bridge.data['jobs'] if j['action']=='reel')
        reel.update(status='sharing',submission_started=True)
        current=copy.deepcopy(self.bridge.data['jobs'])
        with patch('hinglish_app.assistant_publish.start') as start:
            self.assertTrue(followup(self.a,self.session,'post now',self.a.snapshot(self.session)))
            start.assert_not_called()
        self.assertEqual(self.bridge.data['jobs'],current)
        self.assertIn('uncertain',self.a.snapshot(self.session)['messages'][-1]['text'])

    def test_default_evening_times_are_separate_per_platform_and_stable_on_restage(self):
        policy={'enabled':True,'start':'17:00','end':'21:00'}
        (self.root/'config.workflow.local.json').write_text(json.dumps({**WORKFLOW,'short_release_window':policy}),'utf-8')
        spec={**self.spec(['youtube','instagram']),'campaign_ids':['cricket'],'clip_indices':[1,2],
              'request':f'Review first. Schedule 2 clips on YouTube and Instagram on {self.first} and the following day.'}
        stage(self.a,self.session,spec)
        first=self.a.snapshot(self.session)['publishing_review']
        instants=[r['publish_at'] for r in first['rows']+first['instagram_rows']]
        self.assertEqual(len(instants),4)
        self.assertEqual(len({v[11:16] for v in instants}),4)
        self.assertTrue(all('17:00'<=v[11:16]<='21:00' for v in instants))
        self.assertEqual([v[:10] for v in instants[:2]],[self.first,(datetime.fromisoformat(self.first)+timedelta(days=1)).date().isoformat()])
        stage(self.a,self.session,spec)
        second=self.a.snapshot(self.session)['publishing_review']
        self.assertEqual(instants,[r['publish_at'] for r in second['rows']+second['instagram_rows']])
        self.assertFalse(self.bridge.data['jobs'])
        explicit={**spec,'request':f'Schedule 2 clips on YouTube and Instagram from {self.first} at 6:15 pm. Review first.','clock':'18:15'}
        stage(self.a,self.session,explicit)
        review=self.a.snapshot(self.session)['publishing_review']
        self.assertTrue(all(r['publish_at'][11:16]=='18:15' for r in review['rows']+review['instagram_rows']))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.state=AppState(self.root);self.a=self.state.assistant
        self.session=self.a.create()['id'];self.first=(datetime.now(IST)+timedelta(days=2)).date().isoformat()
        self.ids=[];self.bridge=self.state.local_browser
        self.bridge.bind('cricket','cricket_handle');self.bridge.bind('gaming','gaming_handle')
        self.bridge.claim('0.4.7',['youtube_schedule','youtube_preview'])
        self.accounts=patch.object(self.state.publisher,'accounts',side_effect=lambda profile:
            {'youtube':{'connected':True,'name':profile,'id':'UC'+('c' if profile=='cricket' else 'g')*22}})
        self.accounts.start();self.addCleanup(self.accounts.stop)
        for profile in ('cricket','gaming'):
            folder=self.root/'output/campaigns'/profile;folder.mkdir(parents=True)
            clips=[]
            for i in range(7):
                path=folder/f'short-{i}.mp4';path.write_bytes(f'{profile}-{i}'.encode())
                clips.append({'index':i+1,'video':str(path),'fingerprint':fingerprint(path),'duration':30,
                    'publish_at':(datetime.now(IST)+timedelta(days=2+i)).isoformat(),
                    'metadata':{'title':f'{profile} moment {i}','description':'Actual video. #Story #Shorts #Highlights',
                        'tags':['Story'],'instagram_caption':f'{profile} moment {i}. #Story #Shorts #Highlights'}})
            long=folder/'long.mp4';long.write_bytes(profile.encode())
            (folder/'campaign.json').write_text(json.dumps({'status':'reviewed','source':profile+'.mp4','model':'local fixture',
                'targets':[{'profile':profile,'id':'UC'+('c' if profile=='cricket' else 'g')*22}],
                'clips':clips,'long_videos':[{**clips[0],'video':str(long),'fingerprint':fingerprint(long),'duration':900}]}),'utf-8')
            self.ids.append(profile)
    def spec(self,platforms):
        return {'campaign_ids':self.ids,'platforms':platforms,'first_date':self.first,'clock':'19:00'}
    def wait(self):
        for _ in range(500):
            s=self.a.snapshot(self.session)
            if s['status'] not in ('running','planning'):return s
            time.sleep(.01)
        self.fail('Agent did not complete fixture task')

    def test_four_accounts_share_daily_slots_and_long_videos_only_go_to_youtube(self):
        stage(self.a,self.session,{**self.spec(['youtube','instagram']),'include_longform':True})
        r=self.a.snapshot(self.session)['publishing_review']
        self.assertEqual(len(r['rows']),16);self.assertEqual(len(r['instagram_rows']),14)
        for reel in r['instagram_rows']:
            self.assertEqual(reel['account'],reel['profile']+'_handle')
            paired=next(y for y in r['rows'] if y['profile']==reel['profile'] and y['fingerprint']==reel['fingerprint'])
            self.assertEqual(paired['publish_at'],reel['publish_at'])
            self.assertEqual(datetime.fromisoformat(reel['publish_at']).hour,19)
            self.assertEqual(reel['kind'],'short')
        self.assertFalse(self.bridge.data['jobs']) # review does not arm tasks

    def test_model_campaign_catalog_is_scoped_to_open_chat(self):
        from hinglish_app.campaign_memory import catalog
        self.a._update(self.session,campaign=str(self.root/'output/campaigns/gaming'))
        second=self.a.create()['id']
        self.a._update(second,campaign=str(self.root/'output/campaigns/cricket'))
        self.assertEqual([c['id'] for c in catalog(self.a,self.session)],['gaming'])
        self.assertEqual([c['id'] for c in catalog(self.a,second)],['cricket'])
        self.assertEqual(catalog(self.a,self.a.create()['id']),[])

    def test_current_context_uses_live_receipts_without_searching_other_chats(self):
        from unittest.mock import patch
        self.a._message(self.session,'user','Keep this task local to this chat.')
        other=self.a.create()['id']
        self.a._message(other,'user','UNRELATED_CHAT_SECRET')
        self.a._update(self.session,publishing_review={'id':'review','ids':[],'rows':[],
            'instagram_rows':[{'id':'clip','account':'cricket_handle','status':'published',
                'url':'https://www.instagram.com/cricket_handle/reel/VERIFIED/','metadata':{'title':'Saha'}}]})
        with patch.object(self.a.memory,'retrieve',side_effect=AssertionError('Archive search must not run')):
            context=self.a.context_memory('What was published?',self.session)
        self.assertNotIn('UNRELATED_CHAT_SECRET',json.dumps(context))
        self.assertEqual(context['active_task']['instagram_rows'][0]['status'],'published')
        self.assertEqual(context['active_task']['instagram_rows'][0]['title'],'Saha')

    def test_daily_end_date_blocks_excess_exports_before_writing_any_drafts(self):
        end=(datetime.fromisoformat(self.first)+timedelta(days=1)).date().isoformat()
        with self.assertRaisesRegex(ValueError,'exceed the requested date range'):
            stage(self.a,self.session,{**self.spec(['youtube']),'end_date':end})
        self.assertFalse(self.state.publisher.store.list())

    def test_legacy_verified_schedule_receipt_is_recalled_only_for_its_video(self):
        from hinglish_app.campaign_memory import catalog
        path=self.root/'output/campaigns/cricket/campaign.json'
        data=json.loads(path.read_text('utf-8'));clip=data['clips'][0]
        clip.update(remote={'id':'abcdefghijk'},scheduled_verified_at=123,
                    remote_status={'publishAt':'2030-01-01T13:30:00Z'})
        path.write_text(json.dumps(data),'utf-8')
        self.assertTrue(next(c for c in catalog(self.a) if c['id']=='cricket')['clips'][0]['schedule_verified'])
        with patch.object(self.state.publisher.store,'list',return_value=[{
                'campaign':str(path.parent),'fingerprint':clip['fingerprint'],
                'platform':'youtube','remote':{'id':'differentid'}}]):
            self.assertFalse(next(c for c in catalog(self.a) if c['id']=='cricket')['clips'][0]['schedule_verified'])

    def test_instagram_only_arms_persistent_queue_and_never_calls_youtube(self):
        stage(self.a,self.session,self.spec(['instagram']))
        r=self.a.snapshot(self.session)['publishing_review'];self.assertFalse(r['ids'])
        provider=Mock();self.state.publisher.providers['youtube']=provider
        start(self.a,{'session':self.session,'review':r['id'],'made_for_kids':False,'synthetic_media':False})
        s=self.wait();r=s['publishing_review']
        self.assertEqual(r['state'],'queued');self.assertEqual(r['instagram_queued_count'],14)
        self.assertEqual(r['instagram_published_count'],0);provider.assert_not_called()
        self.assertFalse(self.state.publisher.store.list())
        self.assertIsNone(self.bridge.claim('0.4.0')['job'])
        restarted=LocalBrowser(self.root);self.assertEqual(len([j for j in restarted.data['jobs'] if j['status']=='queued' and j['action']=='reel']),14)
        self.assertEqual(len([j for j in restarted.data['jobs'] if j['action']=='inspect']),14)
        first=min(j['not_before'] for j in restarted.data['jobs'] if j['action']=='reel')
        with patch('hinglish_publish.local_browser.time.time',return_value=first+1):
            published=0
            for _ in range(4):
                j=restarted.claim('0.4.0')['job'];self.assertIsNotNone(j)
                if j['action']=='inspect':
                    restarted.finish(j['id'],j['lease'],{'status':'complete','account':j['account']});continue
                restarted.phase(j['id'],j['lease'],'sharing')
                restarted.finish(j['id'],j['lease'],{'status':'published','account':j['account'],
                    'url':f'https://www.instagram.com/{j["account"]}/reel/proof{_}/'})
                published+=1
            self.assertEqual(published,2)
            self.assertIsNone(restarted.claim('0.4.0')['job']) # next day still future

    def test_same_single_cricket_clip_can_be_queued_for_both_instagram_profiles(self):
        stage(self.a,self.session,{**self.spec(['instagram']),'campaign_ids':['cricket'],
            'clip_indices':[2],'destination_profiles':['cricket','gaming']})
        r=self.a.snapshot(self.session)['publishing_review']
        self.assertEqual(len(r['instagram_rows']),2);self.assertFalse(r['ids'])
        self.assertEqual({x['account'] for x in r['instagram_rows']},{'cricket_handle','gaming_handle'})
        self.assertEqual(len({x['video'] for x in r['instagram_rows']}),1)
        self.assertTrue(all(x['video'].endswith('short-1.mp4') for x in r['instagram_rows']))
        self.assertEqual(len({x['publish_at'] for x in r['instagram_rows']}),1)
        start(self.a,{'session':self.session,'review':r['id'],'made_for_kids':False,'synthetic_media':False})
        self.assertEqual(self.wait()['publishing_review']['state'],'queued')
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),2)
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='inspect']),2)
        self.assertIsNone(self.bridge.claim('0.4.0')['job'])
        self.assertFalse(self.state.publisher.store.list())

    def test_invalid_single_clip_or_youtube_destination_override_cannot_queue_anything(self):
        for extra in ({'clip_indices':[99]}, {'destination_profiles':['cricket','gaming'],'platforms':['youtube','instagram']}):
            with self.assertRaises(ValueError):
                stage(self.a,self.session,{**self.spec(['instagram']),'campaign_ids':['cricket'],**extra})
        self.assertFalse(self.bridge.data['jobs']);self.assertFalse(self.state.publisher.store.list())

    def test_missed_unstarted_slot_remains_due_after_reconnection(self):
        stage(self.a,self.session,self.spec(['instagram']))
        r=self.a.snapshot(self.session)['publishing_review']
        from hinglish_app.assistant_distribution import arm
        arm(self.a,self.session,r);old=self.bridge.get(r['instagram_rows'][0]['browser_job_id'])
        with patch('hinglish_publish.local_browser.time.time',return_value=old['not_before']+1000):
            check=self.bridge.claim('0.4.0')['job']
            self.assertEqual(check['id'],old['preflight_id'])
            self.bridge.finish(check['id'],check['lease'],{'status':'complete','account':old['account']})
            claimed=self.bridge.claim('0.4.0')['job']
            self.assertEqual(claimed['id'],old['id'])
            self.assertEqual(self.bridge.get(old['id'])['publish_at'],old['publish_at'])

    def test_new_slot_for_published_reel_is_not_a_second_upload(self):
        stage(self.a,self.session,self.spec(['instagram']))
        from hinglish_app.assistant_distribution import arm
        r=self.a.snapshot(self.session)['publishing_review'];arm(self.a,self.session,r)
        old=self.bridge.get(r['instagram_rows'][0]['browser_job_id'])
        with patch('hinglish_publish.local_browser.time.time',return_value=old['not_before']+1):
            check=self.bridge.claim('0.4.0')['job'];self.bridge.finish(check['id'],check['lease'],{'status':'complete','account':check['account']})
            job=self.bridge.claim('0.4.0')['job'];self.bridge.phase(job['id'],job['lease'],'sharing')
            self.bridge.finish(job['id'],job['lease'],{'status':'published','account':job['account'],'url':'https://www.instagram.com/reel/proof/'})
        with self.assertRaisesRegex(ValueError,'already started or finished'):
            self.bridge.enqueue('reel',old['account'],old['video'],old['caption'],authorized=True,
                publish_at=(datetime.now(IST)+timedelta(days=10)).isoformat())

    def test_trial_gap_keeps_published_first_reel_and_retimes_same_queued_second(self):
        from hinglish_app.assistant_distribution import arm
        from hinglish_app.distribution_schedule import contract
        spec={**self.spec(['instagram']),'campaign_ids':['cricket'],'clip_indices':[1,2],'immediate_first':True}
        stage(self.a,self.session,spec)
        original=self.a.snapshot(self.session)['publishing_review'];arm(self.a,self.session,original)
        for _ in range(3):
            job=self.bridge.claim('0.4.0')['job'];self.assertIsNotNone(job)
            if job['action']=='inspect':
                self.bridge.finish(job['id'],job['lease'],{'status':'complete','account':job['account']});continue
            self.bridge.phase(job['id'],job['lease'],'sharing')
            self.bridge.finish(job['id'],job['lease'],{'status':'published','account':job['account'],
                'url':'https://www.instagram.com/reel/firstreceipt/'})
            break
        first=self.bridge.get(original['instagram_rows'][0]['browser_job_id'])
        second=self.bridge.get(original['instagram_rows'][1]['browser_job_id'])
        self.assertEqual(first['status'],'published');self.assertEqual(second['status'],'queued')
        wording='for trail version i want u to upload both video at once after 2 min gap between the video'
        before=time.time()
        stage(self.a,self.session,{**spec,**contract(wording,WORKFLOW),'request':wording})
        review=self.a.snapshot(self.session)['publishing_review'];arm(self.a,self.session,review)
        self.assertTrue(review['instagram_rows'][0]['previously_published'])
        self.assertFalse(review['instagram_rows'][1]['previously_published'])
        after=time.time()
        changed=self.bridge.get(second['id'])
        self.assertEqual(self.bridge.get(first['id']),first)
        self.assertEqual(changed['status'],'queued');self.assertEqual(changed['caption'],second['caption'])
        self.assertGreaterEqual(changed['not_before'],before+120)
        self.assertLessEqual(changed['not_before'],after+120)
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),2)
        self.assertFalse(self.state.publisher.store.list())

    def test_explicit_gap_and_both_now_create_no_daily_slots(self):
        from hinglish_app.assistant_distribution import arm
        from hinglish_app.distribution_schedule import contract
        base={**self.spec(['instagram']),'campaign_ids':['cricket'],'clip_indices':[1,2,3]}
        before=time.time()
        stage(self.a,self.session,{**base,**contract('Post all three reels now, 2 min apart',WORKFLOW)})
        review=self.a.snapshot(self.session)['publishing_review']
        self.assertTrue(review['instagram_rows'][0]['immediate'])
        times=[datetime.fromisoformat(r['publish_at']).timestamp() for r in review['instagram_rows'][1:]]
        self.assertGreaterEqual(times[0],before+120);self.assertAlmostEqual(times[1]-times[0],120)
        stage(self.a,self.session,{**base,**contract('Post all three reels now on Instagram',WORKFLOW)})
        review=self.a.snapshot(self.session)['publishing_review'];arm(self.a,self.session,review)
        self.assertTrue(all(r['immediate'] and not r['publish_at'] for r in review['instagram_rows']))
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),3)

    def test_instagram_failure_does_not_describe_nonexistent_youtube_uploads(self):
        from hinglish_app.user_messages import instagram_failure
        message=instagram_failure({'instagram_rows':[{'status':'published'},{'status':'queued'}]},'Cannot safely change this Reel’s time.')
        self.assertIn('1 Instagram video is already posted',message)
        self.assertNotIn('private upload',message);self.assertNotIn('YouTube',message)

    def test_past_dates_fail_before_any_drafts_or_browser_tasks(self):
        with self.assertRaisesRegex(ValueError,'release time has passed'):
            stage(self.a,self.session,{**self.spec(['youtube','instagram']),'first_date':'2020-01-01'})
        self.assertFalse(self.state.publisher.store.list());self.assertFalse(self.bridge.data['jobs'])

    def test_rebinding_an_account_pauses_only_its_future_slots(self):
        stage(self.a,self.session,self.spec(['instagram']))
        from hinglish_app.assistant_distribution import arm
        arm(self.a,self.session,self.a.snapshot(self.session)['publishing_review'])
        self.bridge.bind('gaming','other_gaming')
        self.assertEqual(sum(j['status']=='needs_review' for j in self.bridge.data['jobs']),7)
        self.assertTrue(all(j['status']=='queued' for j in self.bridge.data['jobs'] if j['account']=='cricket_handle'))

    def test_local_model_repairs_unready_choice_and_uses_instagram_only(self):
        from hinglish_app.campaign_memory import catalog
        cards=catalog(self.a);brain=Mock()
        good={'action':'prepare','campaign_ids':self.ids,'platforms':['instagram'],'first_date':self.first,'clock':'19:00','question':''}
        brain.json.side_effect=[{**good,'campaign_ids':['unknown']},good]
        answer=decision(brain,'Schedule both saved batches on Instagram only, daily at 7 p.m.',cards,{},WORKFLOW)
        from hinglish_app.distribution_schedule import contract
        self.assertEqual(answer,{**good,**contract('Schedule both saved batches on Instagram only, daily at 7 p.m.',WORKFLOW)})
        self.assertEqual(brain.json.call_count,2)

    def test_second_channel_handle_is_one_destination_and_old_login_error_is_not_current_state(self):
        from hinglish_app.campaign_memory import catalog
        brain=Mock();cards=catalog(self.a)
        good={'action':'prepare','campaign_ids':[self.ids[1]],'platforms':['instagram'],
              'clip_indices':[2],'destination_profiles':['cricket'],'question':'','reply':''}
        brain.json.side_effect=[{**good,'action':'clarify','destination_profiles':['cricket','gaming'],
            'question':'The account is not signed in. Switch accounts first.'},good]
        result=decision(brain,'Use only the second Short. Post it now on my other Instagram @fantasy_legends91.',
            cards,{'old_error':'Switch accounts first'},WORKFLOW)
        self.assertEqual(result['action'],'prepare')
        self.assertEqual(result['clip_indices'],[2])
        self.assertEqual(result['destination_profiles'],['cricket'])
        self.assertTrue(brain.json.call_args.args[1]['executor_capabilities']['switch_configured_instagram_accounts'])
        self.assertEqual(brain.json.call_args.args[1]['explicit_instagram_profiles'],['cricket'])
        brain.json.side_effect=None
        brain.json.return_value={**good,'destination_profiles':['gaming']}
        with self.assertRaisesRegex(ValueError,'could not resolve'):
            decision(brain,'Post it now on Instagram @fantasy_legends91.',cards,{},WORKFLOW)
        brain.json.return_value=good
        result=decision(brain,'Schedule clip 2 on @fantasy_legends91. The other copy is already published on @vineet_editz19; leave it unchanged.',
                        cards,{},WORKFLOW)
        self.assertEqual(result['destination_profiles'],['cricket'])
        self.assertEqual(brain.json.call_args.args[1]['explicit_instagram_profiles'],['cricket'])

    def test_explicit_second_account_post_does_not_ask_same_authorization_again(self):
        from hinglish_app.campaign_memory import catalog
        good={'action':'prepare','campaign_ids':[self.ids[1]],'platforms':['instagram'],
              'clip_indices':[2],'destination_profiles':['cricket'],'question':'','reply':''}
        brain=Mock()
        brain.json.side_effect=[{**good,'action':'clarify','question':'Is the request to post clip 2 now on your second channel correct?'},good]
        answer=decision(brain,'Post only the second Short now on Instagram @fantasy_legends91.',
                        catalog(self.a),{},WORKFLOW)
        self.assertEqual(answer['action'],'prepare')
        self.assertEqual(brain.json.call_count,2)
        brain.json.side_effect=[{**good,'action':'clarify','question':'Are you confirming this schedule?'},good]
        answer=decision(brain,'Schedule only clip 2 on Instagram @fantasy_legends91 for 21 October 2030 at 19:00.',
                        catalog(self.a),{},WORKFLOW)
        self.assertEqual(answer['action'],'prepare')
        self.assertEqual(answer['first_date'],'2030-10-21')

    def test_distribution_keeps_current_receipts_without_reinjecting_archived_chat(self):
        from hinglish_app.campaign_memory import catalog
        memory={'messages':[{'text':'old request '*5000}],
                'active_task':{'current_campaign':'gaming','conversation':[{'text':'old reply '*5000}],
                               'schedule_rows':[{'id':'saved','verified_publish_at':'2030-06-15T19:00:00+05:30'}]},
                'saved_media':[{'description':'archived '*5000}]}
        good={'action':'prepare','campaign_ids':['gaming'],'platforms':['instagram'],
              'clip_indices':[2],'destination_profiles':['cricket'],'question':'','reply':''}
        brain=Mock();brain.json.return_value=good
        decision(brain,'Post the second Short now on Instagram @fantasy_legends91.',catalog(self.a),memory,WORKFLOW)
        supplied=brain.json.call_args.args[1]['shared_memory']
        self.assertNotIn('messages',supplied)
        self.assertNotIn('saved_media',supplied)
        self.assertNotIn('conversation',supplied['active_task'])
        self.assertEqual(supplied['active_task']['schedule_rows'],memory['active_task']['schedule_rows'])
        self.assertEqual(supplied['active_task']['current_campaign'],'gaming')
        self.assertIn('messages',memory)

    def test_read_only_status_uses_receipts_and_does_not_echo_question(self):
        from hinglish_app.campaign_memory import catalog
        good={'action':'status','campaign_ids':['gaming'],'platforms':['instagram'],
              'clip_indices':[2],'destination_profiles':['cricket'],'question':'',
              'reply':'The second clip is published; its receipt is saved.'}
        brain=Mock();brain.json.side_effect=[{**good,'action':'clarify','reply':'','question':'What is its status?'},good]
        answer=decision(brain,'What is the verified publishing status on Instagram @fantasy_legends91? Do not upload anything.',
                        catalog(self.a),{},WORKFLOW)
        self.assertEqual(answer['action'],'status')
        self.assertEqual(brain.json.call_count,2)
        self.assertEqual(brain.json.call_args.args[2]['properties']['action']['enum'],['status'])

    def test_quota_failure_does_not_cancel_approved_instagram_queue(self):
        stage(self.a,self.session,self.spec(['youtube','instagram']))
        r=self.a.snapshot(self.session)['publishing_review']
        class Provider:
            def __init__(self,*args):pass
            def publish(self,*args):raise RuntimeError('YouTube upload limit fixture')
        self.state.publisher.providers['youtube']=Provider
        start(self.a,{'session':self.session,'review':r['id'],'made_for_kids':False,'synthetic_media':False})
        s=self.wait();self.assertEqual(s['status'],'needs_review')
        self.assertEqual(s['publishing_review']['instagram_queued_count'],14)
        self.assertTrue(all(j['status']=='queued' for j in self.bridge.data['jobs']))

    def test_local_edit_planner_repairs_missing_dates_duration_and_wrong_count_before_editing(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_plan import plan
        bad={'reply':'Preparing.','question':'','combine':False,'steps':[
            {'tool':'gaming','options':{'target_minutes':15}},
            {'tool':'shorts','options':{'count':10}},
            {'tool':'distribute','options':{'distribution_platforms':'paired','include_longform':True}}]}
        good=json.loads(json.dumps(bad));good['steps'][1]['options'].update(count=7,max_seconds=50)
        good['steps'][2]['options'].update(first_date='2026-10-20',clock='19:00',distribution_profile='gaming')
        brain=SimpleNamespace(name='local fixture',json=Mock(side_effect=[bad,good]),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            result,_=plan(self.root,'Create gaming highlights and seven standalone portrait Shorts from those highlights, then schedule both platforms from 20 October 2026 at 7 p.m.',[],[],True)
        self.assertEqual(result,good);self.assertEqual(brain.json.call_count,2)
        feedback=brain.json.call_args_list[1].args[1]['validation_error']
        self.assertIn('shorts.count',feedback);self.assertIn('shorts.max_seconds',feedback);self.assertIn('first_date',feedback)

    def test_gaming_recipe_distinguishes_youtube_only_highlights_from_paired_shorts(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_distribution import gaming_recipe
        good={'action':'edit','reply':'Preparing the local workflow.','target_minutes':15,'shorts_count':7,'max_seconds':50,
            'destination_profile':'gaming','shorts_platforms':'paired','first_date':'2026-10-20','clock':'19:00','include_longform':True}
        brain=SimpleNamespace(json=Mock(side_effect=[{**good,'shorts_platforms':'youtube'},good]))
        result=gaming_recipe(brain,self.root,'Use my livestream for highlights on YouTube only, then seven Shorts from those highlights on BOTH YouTube and Instagram starting 20 October 2026 at 7 p.m.',[],{})
        self.assertEqual(brain.json.call_count,2)
        self.assertEqual([s['tool'] for s in result['steps']],['gaming','shorts','distribute'])
        self.assertEqual(result['steps'][-1]['options']['distribution_platforms'],'paired')
        self.assertTrue(result['steps'][-1]['options']['include_longform'])

    def test_highlights_only_negated_shorts_and_upload_are_not_the_full_recipe(self):
        from hinglish_app.assistant_distribution import gaming_recipe_requested,gaming_highlights_requested,validate_edit_plan,eligible
        text='Create 10-15 minute gaming livestream highlights. Do not create portrait Shorts, add memes, upload or schedule.'
        self.assertFalse(gaming_recipe_requested(text))
        self.assertFalse(eligible(text+' Do not change Instagram schedules.'))
        self.assertTrue(gaming_highlights_requested('Use D:\\Gaming and cut the main entertaining parts into a 10-15 minute video.'))
        self.assertFalse(gaming_highlights_requested('Make a gaming highlights compilation of 20 minutes.'))
        good={'steps':[{'tool':'gaming','options':{'target_minutes':15,'memes':False}}]}
        validate_edit_plan(good,text,WORKFLOW)
        for tool in ('shorts','distribute','publish','instagram'):
            with self.assertRaises(ValueError):validate_edit_plan({'steps':good['steps']+[{'tool':tool,'options':{}}]},text,WORKFLOW)
        with self.assertRaisesRegex(ValueError,'memes'):
            validate_edit_plan({'steps':[{'tool':'gaming','options':{}}]},text,WORKFLOW)

    def test_local_planner_repairs_extra_steps_for_a_highlights_only_request(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_plan import plan
        good={'reply':'Preparing the local highlights edit.','question':'','combine':False,
              'steps':[{'tool':'gaming','options':{'target_minutes':15,'memes':False}}]}
        bad={**good,'steps':good['steps']+[{'tool':'shorts','options':{'count':7}}]}
        brain=SimpleNamespace(name='local fixture',json=Mock(side_effect=[bad,good]),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            answer,_=plan(self.root,'Cut the attached recording into entertainment highlights between 10 and 15 minutes. Do not create portrait Shorts, add memes, upload or schedule.',[],[{'name':'stream.mp4','kind':'.mp4'}],False)
        self.assertEqual(answer,good);self.assertEqual(brain.json.call_count,2)
        self.assertIn('excluded portrait Shorts',brain.json.call_args_list[1].args[1]['validation_error'])

    def test_compact_highlights_only_plan_repairs_excluded_memes_and_keeps_one_tool(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_distribution import gaming_highlights
        good={'action':'edit','reply':'Creating local highlights.','target_minutes':12,'memes':False}
        brain=SimpleNamespace(json=Mock(side_effect=[{**good,'memes':True},good]))
        result=gaming_highlights(brain,self.root,'Create gaming highlights from this livestream. Do not add memes or create portrait Shorts or upload.',[],{})
        self.assertEqual(brain.json.call_count,2)
        self.assertEqual(result['steps'],[{'tool':'gaming','options':{'target_minutes':12,'memes':False}}])

    def test_three_actual_shorts_remain_three_and_transcription_loads_once_for_the_batch(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_distribution import from_outputs
        folder=self.root/'output/campaigns/gaming'
        videos=[str(folder/f'short-{i}.mp4') for i in range(3)]
        self.a._update(self.session,profile='gaming',shorts_paths=videos,highlights_paths=[str(folder/'long.mp4')],original_paths=[str(folder/'long.mp4')])
        meta=json.loads((folder/'campaign.json').read_text())['clips'][0]['metadata']
        with patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(width=1080,height=1920,duration=30)), \
             patch('hinglish_app.assistant_publish.transcripts') as transcribe, \
             patch('hinglish_app.assistant_distribution.prepare_copy',return_value=(meta,'local fixture')):
            from_outputs(self.a,self.session,{'distribution_profile':'gaming','distribution_platforms':'instagram',
                'include_longform':True,'first_date':self.first,'clock':'19:00'},'Prepare the finished gaming content.',lambda _:None)
        review=self.a.snapshot(self.session)['publishing_review']
        self.assertEqual(len(review['instagram_rows']),3)
        self.assertEqual(len(review['rows']),1);self.assertEqual(review['rows'][0]['kind'],'long')
        transcribe.assert_called_once();self.assertEqual(len(transcribe.call_args.args[1]),4)
        self.assertFalse(self.bridge.data['jobs']);self.assertTrue(all(Path(p).exists() for p in videos))

    def test_youtube_only_new_outputs_never_require_instagram_caption_generation(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_distribution import from_outputs
        source=self.root/'output/campaigns/gaming/short-0.mp4'
        self.a._update(self.session,profile='gaming',shorts_paths=[str(source)],original_paths=[str(source)])
        meta=json.loads((source.parent/'campaign.json').read_text())['clips'][0]['metadata']
        with patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(width=1080,height=1920,duration=30)),\
             patch('hinglish_app.assistant_publish.transcripts'),\
             patch('hinglish_publish.metadata.generate_youtube',return_value=(meta,'local fixture')) as youtube,\
             patch('hinglish_publish.metadata.generate_instagram',side_effect=AssertionError('Instagram must not block YouTube')) as instagram:
            from_outputs(self.a,self.session,{'distribution_profile':'gaming','distribution_platforms':'youtube',
                'first_date':self.first,'clock':'19:00'},'Post these on my gaming channel',lambda _:None)
        youtube.assert_called_once();instagram.assert_not_called()
        review=self.a.snapshot(self.session)['publishing_review']
        self.assertEqual(len(review['rows']),1);self.assertFalse(review.get('instagram_rows'))

    def test_instagram_followup_posts_first_now_and_queues_second_tomorrow_without_touching_youtube(self):
        (self.root/'config.workflow.local.json').write_text(json.dumps({
            **WORKFLOW,'publishing_defaults':{'made_for_kids':False,'synthetic_media':False}}),'utf-8')
        self.a._update(self.session,profile='gaming',campaign=str(self.root/'output/campaigns/gaming'))
        stage(self.a,self.session,{**self.spec(['youtube']),'campaign_ids':['gaming'],'clip_indices':[1,2]})
        original=[(j['id'],j['status'],j['due']) for j in self.state.publisher.store.list()]
        brain=Mock();brain.name='local fixture'
        brain.json.return_value={'action':'prepare','campaign_ids':['gaming'],'clip_indices':[1,2],
            'destination_profiles':['gaming'],'platforms':['instagram'],'question':'','reply':'',
            'first_date':'2026-10-20T19:00:00+05:30','clock':'2026-10-20T17:40:55+05:30'}
        brain.json.side_effect=[{**brain.json.return_value,'clip_indices':[1]},brain.json.return_value]
        with patch('hinglish_visuals.brain.open_brain',return_value=brain), \
             patch.object(self.state,'create_job') as render:
            self.a.send(self.session,'okay so now post this shorts on my instagram gaming page , one video now and 2nd tommorow 7 pm. Do not upload or schedule anything on YouTube.',profile='gaming')
            snapshot=self.wait()
        self.assertEqual(snapshot['status'],'complete',snapshot['stage'])
        self.assertEqual(brain.json.call_count,2)
        self.assertIn('2 clip releases',brain.json.call_args.args[1]['validation_error'])
        review=snapshot['publishing_review']
        self.assertEqual(review['ids'],[])
        self.assertEqual(len(review['instagram_rows']),2)
        first,second=review['instagram_rows']
        self.assertTrue(first['immediate']);self.assertEqual(first['publish_at'],'')
        tomorrow=(datetime.now(IST)+timedelta(days=1)).replace(hour=19,minute=0,second=0,microsecond=0)
        self.assertEqual(datetime.fromisoformat(second['publish_at']),tomorrow)
        self.assertEqual(first['video'],str(self.root/'output/campaigns/gaming/short-0.mp4'))
        self.assertEqual(second['video'],str(self.root/'output/campaigns/gaming/short-1.mp4'))
        self.assertEqual([(j['id'],j['status'],j['due']) for j in self.state.publisher.store.list()],original)
        render.assert_not_called()
        claimed=self.bridge.claim('0.4.7',['youtube_schedule'])['job']
        self.assertEqual(claimed['id'],first['browser_job_id'])
        self.bridge.phase(claimed['id'],claimed['lease'],'sharing')
        self.bridge.finish(claimed['id'],claimed['lease'],{'status':'published','account':'gaming_handle',
            'url':'https://www.instagram.com/reel/fixtureFirst/'})
        self.assertIsNone(self.bridge.claim('0.4.7',['youtube_schedule'])['job'])
        from hinglish_app.assistant_distribution import arm
        arm(self.a,self.session,review)
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),2)
        restarted=LocalBrowser(self.root)
        with patch('hinglish_publish.local_browser.time.time',return_value=tomorrow.timestamp()):
            check=restarted.claim('0.4.7')['job']
            self.assertEqual(check['action'],'inspect')
            restarted.finish(check['id'],check['lease'],{'status':'complete','account':'gaming_handle'})
            self.assertEqual(restarted.claim('0.4.7')['job']['id'],second['browser_job_id'])

    def test_saved_declarations_apply_without_turning_platform_requests_into_old_review_approval(self):
        from hinglish_app.assistant_publish import confirmation
        (self.root/'config.workflow.local.json').write_text(json.dumps({
            'publishing_defaults':{'made_for_kids':False,'synthetic_media':False}}),'utf-8')
        stage(self.a,self.session,self.spec(['youtube']))
        review=self.a.snapshot(self.session)['publishing_review']
        self.assertTrue(review['declaration_defaults_saved'])
        self.assertFalse(review['made_for_kids']);self.assertFalse(review['synthetic_media'])
        self.assertEqual(confirmation('confirm',review,self.root),{
            'review':review['id'],'made_for_kids':False,'synthetic_media':False})
        self.assertIsNone(confirmation('now post these on Instagram tomorrow',review,self.root))
        self.assertIsNone(confirmation('change it to 30 October',review,self.root))
        self.assertEqual(confirmation('made for kids, contains synthetic media',review,self.root)['made_for_kids'],True)

    def test_owner_short_terminology_overrides_older_paired_default(self):
        from hinglish_app.assistant_edit_workflow import constraints
        workflow={**WORKFLOW,'default_short_platforms':'paired'}
        for text,expected in [
            ('extract 2 shorts and post on gaming channel','youtube'),
            ('extract 2 shorts and upload to YouTube','youtube'),
            ('extract 2 shorts and post on YouTube only','youtube'),
            ('extract 2 shorts and post on my gaming channel, Instagram only','instagram'),
            ('extract 2 shorts and post on YouTube without Instagram','youtube')]:
            with self.subTest(text=text):
                self.assertEqual(constraints(text,[],workflow)['platforms'],expected)

    def test_distribution_calendar_supports_mixed_now_slots_and_literal_dates(self):
        from hinglish_app.distribution_schedule import contract,enumerated_slots
        now=datetime(2031,12,31,23,50,tzinfo=IST)
        result=contract('one clip now and the second tommorow at 12:05 am',WORKFLOW,now)
        self.assertEqual(result,{'first_date':'2032-01-01','clock':'00:05','immediate_first':True})
        self.assertFalse(contract('now schedule these for 5 March 2032 at 7:30 pm',WORKFLOW,now)['immediate_first'])
        self.assertEqual(contract('match the YouTube dates',WORKFLOW,now)['first_date'],'')
        self.assertEqual(enumerated_slots('one video now and 2nd tommorow 7 pm'),2)
        self.assertEqual(enumerated_slots('first now, second tomorrow, third next Monday'),3)
        self.assertEqual(enumerated_slots('first now, 12th video on 14 December'),12)
        self.assertEqual(enumerated_slots('post the first video now'),0)

    def test_youtube_placeholder_gets_real_instagram_copy_once(self):
        from hinglish_app.assistant_distribution import ensure_instagram_copy
        manifest=self.root/'output/campaigns/gaming/campaign.json'
        campaign=json.loads(manifest.read_text('utf-8'))
        campaign['clips'][0]['metadata']['instagram_caption']='Placeholder title'
        manifest.write_text(json.dumps(campaign),'utf-8')
        spec={**self.spec(['instagram']),'campaign_ids':['gaming'],'clip_indices':[1]}
        with patch('hinglish_app.assistant_publish.transcripts'), \
             patch('hinglish_publish.metadata.generate_instagram',return_value=(
                 {'instagram_caption':'Actual story. #Story #Cricket #Shorts'},'local fixture')) as generate:
            ensure_instagram_copy(self.a,spec,lambda _:None)
            ensure_instagram_copy(self.a,spec,lambda _:None)
        generate.assert_called_once()
        self.assertEqual(json.loads(manifest.read_text('utf-8'))['clips'][0]['metadata']['instagram_caption'],
                         'Actual story. #Story #Cricket #Shorts')

    def test_youtube_check_only_never_uploads_and_arms_instagram(self):
        from types import SimpleNamespace
        from hinglish_app.assistant_distribution import from_outputs
        folder=self.root/'output/campaigns/gaming'
        videos=[str(folder/f'short-{i}.mp4') for i in range(2)]
        self.a._update(self.session,profile='gaming',shorts_paths=videos,original_paths=[videos[0]])
        meta=json.loads((folder/'campaign.json').read_text())['clips'][0]['metadata']
        tomorrow=(datetime.now(IST)+timedelta(days=1)).date().isoformat()
        with patch('hinglish_shorts.source.open_video',return_value=SimpleNamespace(width=1080,height=1920,duration=30)), \
             patch('hinglish_app.assistant_publish.transcripts'), \
             patch('hinglish_app.assistant_distribution.prepare_copy',return_value=(meta,'local fixture')):
            from_outputs(self.a,self.session,{'distribution_profile':'gaming','distribution_platforms':'paired',
                'first_date':tomorrow,'clock':'19:00'},
                'Extract 2 Shorts. YouTube check only. Post on Instagram one video now and second tomorrow at 7 pm.',lambda _:None)
        review=self.a.snapshot(self.session)['publishing_review']
        self.assertTrue(review['youtube_check_only'])
        self.assertEqual(review['instagram_rows'][0]['publish_at'],'')
        self.assertEqual(review['instagram_rows'][1]['publish_at'][:10],tomorrow)
        self.assertTrue(all(row['publish_at'] for row in review['rows']))
        client=Mock()
        channel_id=review['accounts']['gaming']['id']
        client.channels.return_value.list.return_value.execute.return_value={'items':[{'id':channel_id}]}
        forbidden=Mock(side_effect=AssertionError('YouTube upload forbidden'))
        self.state.publisher.providers['youtube']=forbidden
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':channel_id})):
            start(self.a,{'session':self.session,'review':review['id'],'made_for_kids':False,'synthetic_media':False})
            snapshot=self.wait()
        self.assertEqual(snapshot['status'],'complete',snapshot['stage'])
        self.assertEqual(len(snapshot['publishing_review']['youtube_checks']),2)
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),2)
        self.assertTrue(all(j['status']=='draft' for j in self.state.publisher.store.list()))
        forbidden.assert_not_called()
        client.videos.assert_not_called()

    def test_first_now_accepts_implicit_video_noun_and_future_date(self):
        from hinglish_app.distribution_schedule import contract
        now=datetime(2031,12,31,21,0,tzinfo=IST)
        for wording in ('publish the first now','post one now','upload first video right now','publish 1st now'):
            result=contract(wording+' and queue the second tomorrow at 7 pm',WORKFLOW,now)
            self.assertTrue(result['immediate_first'],wording)
            self.assertEqual(result['first_date'],'2032-01-01')
            self.assertEqual(result['clock'],'19:00')
