"""Clock/queue contracts. These simulate time, not real YouTube outcomes."""
import copy
import unittest
from unittest.mock import Mock,patch

from tests import test_prepare_post as fixtures
from hinglish_publish.weekly_seo import Plans,WEEK
from hinglish_publish.weekly_seo_plan import validate,generate,V8_MODEL
from hinglish_publish.local_browser import LocalBrowser


def variants(n=4):
    return [{'week':i,'angle':['search','comparison','cause','takeaway'][i-1],'title':'Cricket '+topic+' Analysis',
        'description':'An analysis of cricket '+topic.lower()+'.\n#Cricket #IPL #Analysis',
        'tags':['Cricket','IPL',topic],'reason':'A distinct supported '+topic.lower()+' angle',
        'evidence_id':'e0001',
        'thumbnail':{'text':topic.upper()+' MATTERS','subject':'Cricket analysis',
            'composition':'One clear focal subject','style':'Team colours and readable contrast'}}
        for i,topic in enumerate(['Form','Brand','Identity','Consistency'][:n],1)]


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        fixtures.PreparePostTests.setUp(self)
        self.publisher.accounts.return_value['youtube']['id']='UC'+'a'*22
        binding=patch('hinglish_publish.weekly_seo.current_channel',return_value='UC'+'a'*22)
        binding.start();self.addCleanup(binding.stop)
        self.bridge=LocalBrowser(self.root)
        self.publisher.browser=self.bridge
        d=self.service.create({'profile':'cricket','mode':'long','video':str(self.video),'request_id':'weekly-test'})
        self.draft=self.service.run(d['id'],'cricket')
        self.draft['stages']['speech']['transcript']='Cricket and IPL analysis cover form, brand, identity and consistency.'
        self.draft['stages']['copy:youtube:1']['weekly_seo']={'status':'ready','weeks':4,
            'variants':variants(),'revision':'proposal-v1','model':'Ollama '+V8_MODEL}
        self.service._save(self.draft)
        self.plans=Plans(self.root)

    def enable(self,**extra):
        return self.plans.enable(self.service,'cricket',{'id':self.draft['id'],
            'revision':'proposal-v1','authorize':True,'change_thumbnails':False,**extra})

    def publish_fixture(self):
        job=self.service.queue(self.draft['id'],'cricket','youtube')[0]
        self.publisher.store.change(job['id'],status='published',remote={
            'id':'video000001','publication_verified_at':900,'privacy':'public'})
        return job

    def claim(self,now,supports=None):
        with patch('time.time',return_value=now),patch('hinglish_publish.providers.youtube_client',side_effect=AssertionError('Weekly flow must never call the YouTube API')):
            return self.bridge.claim('0.4.38',['youtube_weekly_metadata'] if supports is None else supports)['job']

    def finish(self,job,now):
        with patch('time.time',return_value=now):
            self.bridge.phase(job['id'],job['lease'],'sharing')
            return self.bridge.finish(job['id'],job['lease'],{'status':'complete','channel_id':job['channel_id'],
                'video_id':job['video_id'],'metadata':job['metadata'],'visibility':'Public',
                'save_disabled':True,'reloaded':True,'thumbnail_saved':False})

    def test_requires_explicit_review_and_matching_v8_revision(self):
        for changes in ({'authorize':False},{'revision':'changed'}):
            with self.assertRaises(ValueError):self.enable(**changes)
        self.assertEqual(self.plans.list(),[])
        self.draft['stages']['copy:youtube:1']['weekly_seo']['model']='Native V14'
        self.service._save(self.draft)
        with self.assertRaisesRegex(ValueError,'V8'):self.enable()

    def test_awaits_exact_verified_public_receipt_and_cannot_enable_twice(self):
        p=self.enable();self.assertIsNone(self.claim(1000));self.assertEqual(self.bridge.data['jobs'],[])
        with self.assertRaisesRegex(ValueError,'already has'):self.enable()
        self.publish_fixture();job=self.claim(1000)
        self.assertEqual(job['video_id'],'video000001');self.assertEqual(job['week'],1)
        self.assertEqual(len(self.bridge.data['jobs']),4)
        self.assertEqual(self.plans.get(p['id'])['status'],'active')

    def test_four_week_boundaries_are_idempotent_and_keep_last_set(self):
        p=self.enable();self.publish_fixture();previous=None
        for index in range(4):
            now=1000+index*(WEEK+1);job=self.claim(now)
            self.assertEqual(job['week'],index+1)
            if previous:self.assertEqual(job['expected_metadata'],previous)
            self.finish(job,now+1);previous=job['metadata']
            self.assertIsNone(self.claim(now+2))
            self.assertEqual(len(self.bridge.data['jobs']),4)
        self.assertIsNone(self.claim(1004+4*WEEK))
        self.assertEqual(self.plans.get(p['id'])['status'],'complete')
        self.assertEqual(self.bridge.data['jobs'][-1]['metadata'],previous)
        self.assertEqual(len(self.publisher.store.list()),1)

    def test_sleep_runs_oldest_due_set_and_shifts_later_sets_without_burst(self):
        p=self.enable();self.publish_fixture()
        # The supported connector binds all tasks, but an offline interval
        # occurs before it ever claims week one.
        self.bridge.worker_supports=['youtube_weekly_metadata']
        with patch('time.time',return_value=1000):
            from hinglish_publish.weekly_seo import sync
            sync(self.bridge)
        job=self.claim(1000+2*WEEK+1)
        self.assertEqual(job['week'],1)
        self.assertFalse(any(j.get('skipped_offline') for j in self.bridge.data['jobs']))
        now=1000+2*WEEK+1
        self.finish(job,now+5)
        self.assertIsNone(self.claim(now+6))
        self.assertIsNone(self.claim(now+5+WEEK-1))
        self.assertEqual(self.claim(now+5+WEEK)['week'],2)
        self.assertEqual(job['expected_metadata']['title'],'Cricket analysis')

    def test_pause_stops_before_next_browser_save_and_wrong_receipt_is_rejected(self):
        p=self.enable();self.publish_fixture();job=self.claim(1000)
        with patch('time.time',return_value=1000):self.bridge.phase(job['id'],job['lease'],'sharing')
        with self.assertRaisesRegex(ValueError,'not verified'):
            self.bridge.finish(job['id'],job['lease'],{'status':'complete','reloaded':True})
        self.plans.pause(p['id'],'cricket',self.bridge)
        self.assertTrue(self.bridge.phase(job['id'],job['lease'],'sharing')['stop'])
        self.assertTrue(all(j['status']=='cancelled' for j in self.bridge.data['jobs'][1:]))

    def test_failed_week_prevents_future_changes_and_original_receipt_is_preserved(self):
        p=self.enable();original=self.publish_fixture();job=self.claim(1000)
        self.bridge.finish(job['id'],job['lease'],{'status':'needs_review','message':'Manual text changed; nothing overwritten.'})
        self.assertIsNone(self.claim(1000+WEEK))
        self.assertEqual(self.plans.get(p['id'])['status'],'needs_review')
        self.assertEqual(self.publisher.store.get(original['id'])['remote']['id'],'video000001')

    def test_thumbnail_opt_in_requires_one_real_image_for_every_week(self):
        with self.assertRaisesRegex(ValueError,'every week'):
            self.enable(change_thumbnails=True,thumbnails=['one.jpg'])
        self.assertEqual(self.plans.list(),[])

    def test_approved_thumbnails_are_frozen_separately_from_the_reused_normalization_cache(self):
        p=self.enable(change_thumbnails=True,thumbnails=[str(self.thumb)]*4)
        paths=[image['prepared']['path'] for image in p['thumbnails']]
        self.assertEqual(len(set(paths)),4)
        self.assertTrue(all(p['id'] in path for path in paths))
        self.thumb.write_bytes(b'a later unrelated thumbnail normalization')
        from hinglish_publish.prepare_post import verify_identity
        for image in p['thumbnails']:verify_identity(image['prepared'])

    def test_changed_channel_stops_future_updates_without_touching_original_post(self):
        p=self.enable();self.publish_fixture()
        with patch('hinglish_publish.weekly_seo.current_channel',return_value='UC'+'b'*22):
            self.assertIsNone(self.claim(1000))
        self.assertEqual(self.plans.get(p['id'])['status'],'needs_review')
        self.assertEqual(self.bridge.data['jobs'],[])

    def test_old_extension_keeps_plan_waiting_without_claiming_new_actions(self):
        p=self.enable();self.publish_fixture();self.assertIsNone(self.claim(1000,supports=[]))
        self.assertEqual(self.plans.get(p['id'])['status'],'waiting_extension')
        self.assertEqual(self.bridge.data['jobs'],[])

    def test_replacement_plan_uses_last_verified_week_as_its_starting_text(self):
        p=self.enable();self.publish_fixture();job=self.claim(1000);self.finish(job,1001)
        self.plans.pause(p['id'],'cricket',self.bridge)
        second=self.enable();next_job=self.claim(1010)
        self.assertEqual(next_job['expected_metadata'],job['metadata'])
        self.assertNotEqual(next_job['plan_id'],p['id'])
        self.assertEqual(next_job['plan_id'],second['id'])
        self.assertEqual(len(self.publisher.store.list()),1)

    def test_restart_does_not_replay_an_uncertain_weekly_save(self):
        p=self.enable();self.publish_fixture();job=self.claim(1000)
        with patch('time.time',return_value=1000):self.bridge.phase(job['id'],job['lease'],'sharing')
        restarted=LocalBrowser(self.root)
        self.assertEqual(restarted.get(job['id'])['status'],'needs_review')
        self.assertIn('YouTube',restarted.get(job['id'])['message'])
        self.bridge=restarted
        self.assertIsNone(self.claim(1000+WEEK))
        self.assertEqual(self.plans.get(p['id'])['status'],'needs_review')

    def test_restart_before_save_automatically_waits_and_resumes_the_same_task(self):
        p=self.enable();self.publish_fixture();job=self.claim(1000)
        with patch('time.time',return_value=1002):self.bridge=LocalBrowser(self.root)
        self.assertEqual(self.bridge.get(job['id'])['status'],'queued')
        self.assertIsNone(self.claim(1061))
        resumed=self.claim(1062)
        self.assertEqual(resumed['id'],job['id'])
        self.assertEqual(self.plans.get(p['id'])['status'],'active')

    def test_readiness_failure_retries_without_expiring_or_blocking_future_weeks(self):
        self.enable();self.publish_fixture();job=self.claim(1000)
        with patch('time.time',return_value=1001):
            self.bridge.finish(job['id'],job['lease'],{'status':'queued','message':'Studio has unsaved manual changes. Waiting.'})
        self.assertIsNone(self.claim(1060))
        resumed=self.claim(1061)
        self.assertEqual(resumed['id'],job['id'])
        # Crossing the old calendar window while loading cannot stop a Save.
        with patch('time.time',return_value=1000+2*WEEK):
            self.assertFalse(self.bridge.phase(resumed['id'],resumed['lease'],'running')['stop'])
            self.bridge.phase(resumed['id'],resumed['lease'],'sharing')
            with self.assertRaisesRegex(ValueError,'submitted weekly Save'):
                self.bridge.finish(resumed['id'],resumed['lease'],{'status':'queued'})

    def test_reconnected_worker_recovers_a_stale_pre_save_lease(self):
        self.enable();self.publish_fixture();job=self.claim(1000)
        self.assertIsNone(self.claim(1091))
        self.assertEqual(self.bridge.get(job['id'])['status'],'queued')
        self.assertEqual(self.claim(1151)['id'],job['id'])


class WeeklyGeneration(unittest.TestCase):
    def test_exact_counts_unique_angles_source_grounding_and_v8_only(self):
        speech='Cricket and IPL analysis cover form, brand, identity and consistency.'
        self.assertEqual(len(validate({'variants':variants()},4,speech)),4)
        for count in (0,5,True):
            with self.assertRaises(ValueError):validate({'variants':variants()},count,speech)
        bad=variants();bad[1]['title']=bad[0]['title']
        with self.assertRaisesRegex(ValueError,'distinct'):validate({'variants':bad},4,speech)
        bad=variants();bad[2]['angle']='search'
        with self.assertRaisesRegex(ValueError,'distinct angle'):validate({'variants':bad},4,speech)
        bad=variants();bad[0]['evidence_id']='e9999'
        with self.assertRaisesRegex(ValueError,'evidence ID'):validate({'variants':bad},4,speech)
        with self.assertRaisesRegex(ValueError,'EXACT verbatim'):
            validate({'variants':variants()},4,speech,[{'id':'e0001','quote':'An invented quote that was never spoken.'}])
        labelled=variants(1);labelled[0]['description']='Week 1: '+labelled[0]['description']
        self.assertFalse(validate({'variants':labelled},1,speech)[0]['description'].startswith('Week 1:'))
        bad=variants(1);bad[0]['description']='Punjab Kings have not produced a consistent performer. #Cricket #IPL #Analysis'
        with self.assertRaisesRegex(ValueError,'unsupported player-production'):validate({'variants':bad},1,speech)
        bad[0]['description']='Punjab Kings have not had a single standout performer since their inception. #Cricket #IPL #Analysis'
        with self.assertRaisesRegex(ValueError,'unsupported player-production'):validate({'variants':bad},1,speech)
        brain=Mock();brain.name='Native V14'
        with self.assertRaisesRegex(ValueError,'V8'):generate(brain,'.',speech,{}, {},[],4,lambda _:None)
        brain.json.assert_not_called()

    def test_full_creator_profile_and_all_packages_are_in_grounding_review(self):
        brain=Mock();brain.name='Ollama '+V8_MODEL
        brain.json.side_effect=[{'variants':variants()},{'approved':True,'issues':[]}]
        speech='Cricket and IPL analysis cover form, brand, identity and consistency.'
        result=generate(brain,'.',speech,{}, {'profile':'general','guidance':'keep all'},['voice notes'],4,lambda _:None)
        self.assertEqual(result['weeks'],4)
        self.assertEqual(brain.json.call_args_list[0].args[1]['creator_profile']['guidance'],'keep all')
        self.assertIn('Consistency',brain.json.call_args_list[1].args[1]['draft']['title'])

    def test_identified_bad_claim_repairs_only_its_row_before_grounding(self):
        brain=Mock();brain.name='Ollama '+V8_MODEL
        bad=variants();bad[2]['description']='Punjab Kings have not had a single standout performer since their inception. #Cricket #IPL #Analysis'
        brain.json.side_effect=[{'variants':bad},{'variant':variants()[2]},{'approved':True,'issues':[]}]
        speech='Cricket and IPL analysis cover form, brand, identity and consistency.'
        result=generate(brain,'.',speech,{}, {'profile':'general','guidance':'keep all'},[],4,lambda _:None)
        self.assertEqual(result['variants'][2]['description'].split(),variants()[2]['description'].split())
        self.assertEqual(brain.json.call_args_list[1].args[1]['invalid_variant']['week'],3)
        self.assertEqual(brain.json.call_args_list[1].args[1]['creator_profile']['guidance'],'keep all')


if __name__=='__main__':unittest.main()
