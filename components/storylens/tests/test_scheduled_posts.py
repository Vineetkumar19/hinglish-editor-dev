import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from hinglish_app.server import AppState
from hinglish_app.scheduled_posts import edited_metadata,revision,pending_in_panel,failed_in_panel


class ScheduledPostsTests(unittest.TestCase):
    def test_failed_cancel_is_not_counted_as_a_future_schedule(self):
        from unittest.mock import patch
        job=self._youtube_cancel_job()
        store=self.state.publisher.store
        store.change(job['id'],scheduled_action={'action':'cancel','status':'failed','message':'The exact video could not be read.'})
        with patch.object(self.manager,'refresh_published'):
            row=next(p for p in self.manager.snapshot()['posts'] if p['id']=='youtube:'+job['id'])
        self.assertEqual(row['bucket'],'failed');self.assertTrue(row['can_delete']);self.assertFalse(row['can_edit'])
        self.assertEqual(row['message'],'The exact video could not be read.')
        still_scheduled={**job,'scheduled_action':{'action':'save','status':'failed'}}
        self.assertTrue(pending_in_panel('youtube',still_scheduled))
        self.assertFalse(failed_in_panel('youtube',still_scheduled))

    def test_delete_failed_youtube_persists_but_keeps_receipt_source_and_duplicate_guard(self):
        from unittest.mock import patch
        from hinglish_app.scheduled_posts import ScheduledPosts
        job=self._youtube_cancel_job();store=self.state.publisher.store
        store.change(job['id'],status='needs_review',error='Receipt needs checking.')
        saved=store.get(job['id']);key='youtube:'+job['id']
        with patch.object(self.bridge,'enqueue_youtube') as enqueue:
            self.manager.act({'id':key,'revision':revision(saved),'action':'delete'})
        enqueue.assert_not_called();kept=store.get(job['id'])
        self.assertEqual(kept['remote'],saved['remote']);self.assertEqual(kept['status'],'needs_review');self.assertTrue(self.video.is_file())
        snap=ScheduledPosts(self.state).snapshot()
        self.assertNotIn(key,[p['id'] for p in snap['posts']]);self.assertIn(key,snap['deleted_ids'])
        self.assertEqual(store.add_batch([saved]),[saved['id']])

    def test_delete_failed_instagram_and_pending_publisher_entries_stay_hidden(self):
        with self.bridge.lock:
            job=next(j for j in self.bridge.data['jobs'] if j['id']==self.job['id'])
            job.update(status='needs_review',submission_started=True)
        key='instagram:'+job['id']
        self.manager.act({'id':key,'revision':revision(job),'action':'delete'})
        self.assertEqual(self.bridge.get(job['id'])['status'],'needs_review')
        self.assertIn(key,self.manager.snapshot()['deleted_ids']);self.assertEqual(self.manager.snapshot()['posts'],[])
        store=self.state.publisher.store
        identity=store.add_batch([{'platform':'instagram','profile':'gaming','kind':'short','video':str(self.video),
            'fingerprint':'failed-local','prepare_post_id':'a'*32,'metadata':{'instagram_caption':'A short #Gaming'}}])[0]
        store.change(identity,status='blocked',authorized_at=time.time())
        local=store.get(identity);key='instagram:'+identity
        self.manager.act({'id':key,'revision':revision(local),'action':'delete'})
        self.assertNotIn(key,[p['id'] for p in self.manager.snapshot()['posts']])

    def test_delete_rejects_stale_revision_future_schedule_and_active_action(self):
        job=self._youtube_cancel_job();store=self.state.publisher.store;key='youtube:'+job['id']
        with self.assertRaisesRegex(ValueError,'Only a failed'):
            self.manager.act({'id':key,'revision':revision(job),'action':'delete'})
        store.change(job['id'],status='needs_review',scheduled_action={'action':'cancel','status':'working'})
        current=store.get(job['id'])
        with self.assertRaisesRegex(ValueError,'changed'):
            self.manager.act({'id':key,'revision':revision(job),'action':'delete'})
        with self.assertRaisesRegex(ValueError,'Only a failed'):
            self.manager.act({'id':key,'revision':revision(current),'action':'delete'})
        self.assertNotIn('scheduled_panel_deleted_at',store.get(job['id']))

    def test_already_private_unscheduled_youtube_cancel_removes_entry_without_sending_action(self):
        from unittest.mock import Mock,patch
        job=self._youtube_cancel_job();client=Mock()
        private={'id':job['remote']['id'],'snippet':{'channelId':job['account_id'],'title':'Changed outside Storylens'},
                 'status':{'privacyStatus':'private','uploadStatus':'processed'}}
        client.videos.return_value.list.return_value.execute.return_value={'items':[private]}
        operation={'id':'cancel','status':'working','action':'cancel','browser_ids':[]}
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':job['account_id']})),patch.object(self.bridge,'enqueue_youtube') as enqueue:
            self.manager._youtube(job,job['metadata'],False,operation)
        enqueue.assert_not_called();saved=self.state.publisher.store.get(job['id'])
        self.assertEqual(saved['status'],'cancelled')
        self.assertIn('youtube:'+job['id'],self.manager.snapshot()['cancelled_ids'])
        self.assertNotIn('youtube:'+job['id'],[p['id'] for p in self.manager.snapshot()['posts']])

    def test_readback_reconciles_previous_cancel_failure_when_private_is_confirmed(self):
        from unittest.mock import Mock,patch
        job=self._youtube_cancel_job();store=self.state.publisher.store
        store.change(job['id'],scheduled_action={'action':'cancel','status':'failed','browser_ids':[]})
        job=store.get(job['id']);client=Mock()
        client.videos.return_value.list.return_value.execute.return_value={'items':[{'id':job['remote']['id'],
            'snippet':{'channelId':job['account_id']},'status':{'privacyStatus':'private'}}]}
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':job['account_id']})):
            self.manager._refresh_youtube([job])
        self.assertEqual(store.get(job['id'])['status'],'cancelled')

    def _youtube_cancel_job(self):
        from hinglish_publish.store import fingerprint
        meta=edited_metadata({}, {**self.fields,'description':'A saved cricket clip.'})
        identity=self.state.publisher.store.add_batch([{'platform':'youtube','profile':'cricket','kind':'short',
            'video':str(self.video),'fingerprint':fingerprint(self.video),'metadata':meta}])[0]
        self.state.publisher.store.change(identity,status='scheduled',account_id='UC'+'c'*22,authorized_at=time.time(),
            remote={'id':'abcdefghijk','publish_at':self.job['publish_at'],'privacy':'private'})
        self.bridge.claim('0.4.36',['youtube_private'])
        return self.state.publisher.store.get(identity)

    def test_cancel_instagram_browser_schedule_preserves_file_and_does_not_post(self):
        result=self.manager.act({'id':'instagram:'+self.job['id'],'revision':revision(self.job),'action':'cancel'})
        saved=self.bridge.get(self.job['id'])
        self.assertEqual(saved['status'],'cancelled');self.assertTrue(saved['stop']);self.assertTrue(self.video.is_file())
        self.assertIn('cancelled',result['message'])
        snap=self.manager.snapshot();self.assertNotIn('instagram:'+saved['id'],[p['id'] for p in snap['posts']])
        self.assertIn('instagram:'+saved['id'],snap['cancelled_ids'])

    def test_cancel_exact_pending_prepare_post_reel_without_changing_others(self):
        store=self.state.publisher.store
        ids=store.add_batch([{'platform':'instagram','profile':'gaming','kind':'short','video':str(self.video),
            'fingerprint':'pending-'+str(i),'prepare_post_id':'a'*32,'metadata':{'instagram_caption':'A clip #Gaming #Play #Highlights'}} for i in range(2)])
        for key in ids:store.change(key,status='ready',authorized_at=time.time())
        job=store.get(ids[0]);row=next(p for p in self.manager.snapshot()['posts'] if p['id']=='instagram:'+job['id'])
        self.assertTrue(row['can_cancel']);self.assertFalse(row['can_edit'])
        self.manager.act({'id':row['id'],'revision':row['revision'],'action':'cancel'})
        self.assertEqual(store.get(ids[0])['status'],'cancelled');self.assertEqual(store.get(ids[1])['status'],'ready')

    def test_cancel_cannot_overtake_instagram_upload_claim(self):
        with self.bridge.lock:
            row=next(j for j in self.bridge.data['jobs'] if j['id']==self.job['id']);row.update(status='running',submission_started=True)
        current=self.bridge.get(self.job['id'])
        with self.assertRaisesRegex(ValueError,'started'):
            self.manager.act({'id':'instagram:'+current['id'],'revision':revision(current),'action':'cancel'})
        self.assertEqual(self.bridge.get(current['id'])['status'],'running')

    def test_youtube_cancel_uses_existing_private_capability_and_same_upload(self):
        from unittest.mock import patch
        job=self._youtube_cancel_job()
        with patch('hinglish_app.scheduled_posts_cancel.threading.Thread') as worker:
            self.manager.act({'id':'youtube:'+job['id'],'revision':revision(job),'action':'cancel'})
        args=worker.call_args.kwargs['args'];self.assertEqual(args[0]['remote']['id'],job['remote']['id'])
        self.assertEqual(args[3]['action'],'cancel');self.assertEqual(len(self.state.publisher.store.list()),1)

    def test_youtube_cancel_requires_private_no_release_date_readback(self):
        from unittest.mock import Mock,patch
        job=self._youtube_cancel_job();client=Mock()
        original={'id':job['remote']['id'],'snippet':{'channelId':job['account_id'],**{k:job['metadata'][k] for k in ('title','description')}},
            'status':{'privacyStatus':'private','uploadStatus':'processed','publishAt':job['remote']['publish_at']}}
        private=copy.deepcopy(original);private['status'].pop('publishAt')
        client.videos.return_value.list.return_value.execute.side_effect=[{'items':[original]},{'items':[private]}]
        op={'id':'cancel','status':'working','action':'cancel','browser_ids':[]}
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':job['account_id']})), \
                patch.object(self.manager,'snapshot',return_value={'posts':[]}), \
                patch.object(self.bridge,'enqueue_youtube',return_value={'id':'b'*16}) as enqueue, \
                patch.object(self.bridge,'get',return_value={'status':'submitted','submission_started':True}):
            self.manager._youtube(job,job['metadata'],False,op)
        self.assertTrue(enqueue.call_args.kwargs['private_only'])
        saved=self.state.publisher.store.get(job['id']);self.assertEqual(saved['status'],'cancelled')
        self.assertEqual(saved['remote']['privacy'],'private');self.assertEqual(saved['remote']['publish_at'],'')
        self.assertIn('cancellation_verified_at',saved['remote']);client.videos.return_value.delete.assert_not_called()

    def test_youtube_cancel_never_claims_success_without_removed_release_date(self):
        from unittest.mock import Mock,patch
        job=self._youtube_cancel_job();client=Mock()
        original={'id':job['remote']['id'],'snippet':{'channelId':job['account_id'],**{k:job['metadata'][k] for k in ('title','description')}},
            'status':{'privacyStatus':'private','uploadStatus':'processed','publishAt':job['remote']['publish_at']}}
        client.videos.return_value.list.return_value.execute.return_value={'items':[original]}
        op={'id':'cancel','status':'working','action':'cancel','browser_ids':[]}
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':job['account_id']})), \
                patch.object(self.manager,'snapshot',return_value={'posts':[]}), \
                patch.object(self.bridge,'enqueue_youtube',return_value={'id':'b'*16}), \
                patch.object(self.bridge,'get',return_value={'status':'submitted','submission_started':True}), \
                patch('hinglish_app.scheduled_posts.time.sleep'):
            self.manager._youtube(job,job['metadata'],False,op)
        saved=self.state.publisher.store.get(job['id'])
        self.assertEqual(saved['status'],'scheduled');self.assertEqual(saved['scheduled_action']['status'],'needs_review')
        self.assertNotIn('cancellation_verified_at',saved['remote'])

    def test_prepare_post_reels_use_instagram_and_remain_read_only(self):
        store=self.state.publisher.store
        ids=store.add_batch([{'platform':platform,'profile':'cricket','kind':'short',
            'video':str(self.video),'fingerprint':'prepared-'+str(n),
            'prepare_post_id':'a'*32,'account_id':'fantasy_legends91' if platform=='instagram' else 'channel',
            'metadata':{'title':'Cricket clip','instagram_caption':'Cricket moment\n\n#Cricket #IPL #Highlights'}}
            for platform in ('youtube','instagram') for n in range(5)])
        for identity in ids:
            job=store.get(identity)
            store.change(identity,status='scheduled' if job['platform']=='youtube' else 'ready',authorized_at=time.time())
        before=copy.deepcopy(store.list())
        rows=[row for row in self.manager.snapshot()['posts'] if row['id'].split(':')[1] in ids]
        self.assertEqual(sum(r['platform']=='youtube' for r in rows),5)
        self.assertEqual(sum(r['platform']=='instagram' for r in rows),5)
        reel=next(r for r in rows if r['platform']=='instagram')
        self.assertFalse(reel['can_edit']);self.assertEqual(reel['prepare_post_id'],'a'*32)
        self.assertEqual(self.manager._job(reel['id'])[1]['platform'],'instagram')
        with self.assertRaisesRegex(ValueError,'Prepare & post'):
            self.manager.act({'id':reel['id'],'revision':reel['revision'],'action':'publish_now','fields':self.fields})
        self.assertEqual(store.list(),before)

    def test_other_platform_is_never_counted_as_youtube(self):
        job={'platform':'instagram','status':'ready','due':time.time()+86400}
        self.assertFalse(pending_in_panel('youtube',job))
        self.assertFalse(failed_in_panel('youtube',{**job,'status':'blocked'}))

    def test_prepare_post_handoff_does_not_show_same_reel_twice(self):
        identity=self.state.publisher.store.add_batch([{'platform':'instagram','profile':'cricket','kind':'short',
            'video':str(self.video),'fingerprint':'prepared','prepare_post_id':'a'*32,
            'metadata':{'instagram_caption':'Cricket moment\n\n#Cricket #IPL #Highlights'}}])[0]
        self.state.publisher.store.change(identity,status='processing',authorized_at=time.time(),remote={'browser_job_id':self.job['id']})
        self.assertEqual([r['id'] for r in self.manager.snapshot()['posts']],['instagram:'+self.job['id']])

    def test_old_failed_attempts_and_expired_youtube_slots_do_not_appear_as_schedules(self):
        now=1792593300
        for state in ('needs_review','blocked','published','cancelled'):
            with self.subTest(state=state):
                self.assertFalse(pending_in_panel('instagram',{'action':'reel','status':state},now))
        self.assertFalse(pending_in_panel('instagram',{'action':'reel','status':'needs_review','publish_at':'2026-10-21T17:32:00+05:30'},now))
        self.assertFalse(pending_in_panel('youtube',{'status':'scheduled','due':now-60},now))
        self.assertFalse(pending_in_panel('youtube',{'status':'needs_review','due':now-60},now))
        self.assertTrue(pending_in_panel('youtube',{'status':'scheduled','due':now+60},now))

    def test_hiding_expired_entries_never_discards_live_instagram_catch_up(self):
        now=time.time()
        job={'action':'reel','status':'queued','publish_at':'2026-01-01T19:00:00+05:30','submission_started':False}
        self.assertTrue(pending_in_panel('instagram',job,now))
        self.assertFalse(pending_in_panel('instagram',{**job,'stop':True},now))
        self.assertTrue(pending_in_panel('instagram',{**job,'status':'sharing','submission_started':True},now))

    def test_failed_attempts_have_a_separate_read_only_bucket(self):
        with self.bridge.lock:
            row=next(j for j in self.bridge.data['jobs'] if j['id']==self.job['id'])
            row.update(status='needs_review',message='Publication is uncertain.',submission_started=True)
        result=self.manager.snapshot()['posts'][0]
        self.assertEqual(result['bucket'],'failed');self.assertFalse(result['can_edit'])
        self.assertEqual(result['message'],'Publication is uncertain.')
        self.assertEqual(self.bridge.get(self.job['id'])['status'],'needs_review')
        with self.assertRaisesRegex(ValueError,'source chat'):
            self.manager.act({'id':result['id'],'revision':result['revision'],'action':'publish_now','fields':self.fields})
        self.assertTrue(failed_in_panel('youtube',{'status':'scheduled','due':100},now=200))
        self.assertFalse(failed_in_panel('youtube',{'status':'published','due':100},now=200))

    def setUp(self):
        folder=Path(__file__).resolve().parents[1]/'tmp';folder.mkdir(exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=folder);self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.state=AppState(self.root);self.bridge=self.state.local_browser
        self.video=self.root/'video.mp4';self.video.write_bytes(b'finished')
        self.due=time.time()+86400
        from datetime import datetime
        from hinglish_publish.store import IST
        self.job=self.bridge.enqueue('reel','cricket',str(self.video),'Original cricket title\n\n#Cricket #IPL #Highlights',
            authorized=True,publish_at=datetime.fromtimestamp(self.due,IST).isoformat(),reference='exact-reel')
        self.manager=self.state.scheduled_posts
        self.fields={'title':'Updated cricket title','hashtags':'#Cricket #IPL #MatchHighlights'}

    def test_opening_list_is_read_only_and_preserves_source_identity(self):
        before=copy.deepcopy(self.bridge.data)
        rows=self.manager.snapshot()['posts']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['id'],'instagram:'+self.job['id'])
        self.assertEqual(rows[0]['account'],'cricket');self.assertTrue(rows[0]['can_edit'])
        self.assertEqual(rows[0]['profile'],'cricket')
        self.assertEqual(self.bridge.data,before)

    def test_verified_instagram_post_leaves_panel_but_keeps_duplicate_guard_receipt(self):
        with self.bridge.lock:
            row=next(j for j in self.bridge.data['jobs'] if j['id']==self.job['id'])
            row.update(status='published',url='https://www.instagram.com/cricket/reel/verified/')
        self.assertEqual(self.manager.snapshot()['posts'],[])
        self.assertEqual(self.bridge.get(self.job['id'])['status'],'published')

    def test_only_remote_publication_on_exact_youtube_channel_removes_saved_schedule(self):
        from unittest.mock import Mock,patch
        fields={**self.fields,'description':'A cricket match highlight.'}
        meta=edited_metadata({},fields)
        identity=self.state.publisher.store.add_batch([{'platform':'youtube','profile':'cricket','kind':'short',
            'video':str(self.video),'fingerprint':'same-file','metadata':meta}])[0]
        self.state.publisher.store.change(identity,status='scheduled',account_id='UC'+'c'*22,
            remote={'id':'abcdefghijk','publish_at':self.job['publish_at'],'privacy':'private'})
        client=Mock();remote={'id':'abcdefghijk','snippet':{'channelId':'wrong-channel'},
            'status':{'privacyStatus':'public','uploadStatus':'processed'}}
        client.videos.return_value.list.return_value.execute.return_value={'items':[remote]}
        with patch('hinglish_publish.providers.youtube_client',return_value=(client,{'channel_id':'UC'+'c'*22})):
            self.manager._refresh_youtube([self.state.publisher.store.get(identity)])
            self.assertEqual(self.state.publisher.store.get(identity)['status'],'scheduled')
            remote['snippet']['channelId']='UC'+'c'*22
            self.manager._refresh_youtube([self.state.publisher.store.get(identity)])
        self.assertEqual(self.state.publisher.store.get(identity)['status'],'published')
        self.assertNotIn('youtube:'+identity,[r['id'] for r in self.manager.snapshot()['posts']])

    def test_save_caption_keeps_due_time_and_same_job_and_rejects_stale_edit(self):
        result=self.manager.act({'id':'instagram:'+self.job['id'],'revision':revision(self.job),'action':'save','fields':self.fields})
        saved=self.bridge.get(self.job['id'])
        self.assertAlmostEqual(saved['not_before'],self.due,places=5);self.assertEqual(saved['reference'],'exact-reel')
        self.assertIn('#MatchHighlights',saved['caption']);self.assertIn('unchanged',result['message'])
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),1)
        with self.assertRaisesRegex(ValueError,'changed'):self.manager.act({'id':'instagram:'+self.job['id'],'revision':revision(self.job),'action':'publish_now','fields':self.fields})

    def test_publish_now_retimes_exact_existing_job_without_new_upload(self):
        result=self.manager.act({'id':'instagram:'+self.job['id'],'revision':revision(self.job),'action':'publish_now','fields':self.fields})
        saved=self.bridge.get(self.job['id'])
        self.assertEqual(saved['publish_at'],'');self.assertEqual(saved['not_before'],0)
        self.assertEqual(saved['status'],'queued');self.assertFalse(saved['submission_started'])
        self.assertIn('not verified',result['message'])
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),1)

    def test_share_boundary_blocks_text_edit_and_immediate_replay(self):
        with self.bridge.lock:
            row=next(j for j in self.bridge.data['jobs'] if j['id']==self.job['id'])
            row.update(status='sharing',submission_started=True)
        current=self.bridge.get(self.job['id'])
        with self.assertRaisesRegex(ValueError,'already started'):
            self.manager.act({'id':'instagram:'+current['id'],'revision':revision(current),'action':'publish_now','fields':self.fields})
        self.assertEqual(self.bridge.get(current['id'])['status'],'sharing')

    def test_invalid_fields_never_remove_mandatory_post_text(self):
        for fields in ({'title':'','hashtags':'#One #Two #Three'}, {'title':'Good','hashtags':''}, {'title':False,'hashtags':'#One #Two #Three'}):
            with self.assertRaises(ValueError):edited_metadata({},fields)

    def test_youtube_action_is_bound_to_existing_upload_and_is_not_an_upload_request(self):
        from unittest.mock import patch
        from hinglish_publish.store import fingerprint
        fields={**self.fields,'description':'A cricket match highlight from the finished clip.'}
        metadata=edited_metadata({},fields)
        identity=self.state.publisher.store.add_batch([{'platform':'youtube','profile':'cricket','kind':'short',
            'video':str(self.video),'fingerprint':fingerprint(self.video),'metadata':metadata}])[0]
        self.state.publisher.store.change(identity,status='scheduled',account_id='UC'+'c'*22,authorized_at=time.time(),
            remote={'id':'abcdefghijk','publish_at':self.job['publish_at'],'privacy':'private'})
        self.bridge.claim('0.4.35',['youtube_schedule','youtube_publish','youtube_metadata'])
        job=self.state.publisher.store.get(identity)
        with patch('hinglish_app.scheduled_posts.threading.Thread') as worker:
            self.manager.act({'id':'youtube:'+identity,'revision':revision(job),'action':'publish_now','fields':fields})
        self.assertEqual(worker.call_args.kwargs['args'][0]['remote']['id'],'abcdefghijk')
        self.assertEqual(len(self.state.publisher.store.list()),1)
        self.assertEqual(self.state.publisher.store.get(identity)['status'],'scheduled')
