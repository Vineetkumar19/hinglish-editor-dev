import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hinglish_app.server import AppState
from hinglish_app.assistant_publish import request, start, confirmation

TEXT = 'upload any random video (in private) on my both youtube channel. 1 long and 1 shorts. do this on my both channel. and also add titles and description'


class ChatPublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = AppState(self.root)
        self.assistant = self.state.assistant
        self.session = self.assistant.create()['id']
        source = self.root / 'library'
        source.mkdir()
        for name in ('a-long', 'b-long', 'c-short', 'd-short'):
            p = source / (name + '.mp4')
            p.write_bytes(name.encode())
            os.utime(p, (time.time()-60, time.time()-60))
        self.state.publisher.settings({'source_root': str(source)})
        self.calls = []
        owner = self
        class Provider:
            def __init__(self, root, config): pass
            def publish(self, job, checkpoint):
                owner.calls.append(job)
                remote = {'id': f'fake{len(owner.calls):07d}',
                          'url': f'https://www.youtube.com/watch?v=fake{len(owner.calls):07d}', 'privacy': 'private'}
                checkpoint(remote)
                return remote, 'uploaded_private'
        self.state.publisher.providers['youtube'] = Provider
        self.accounts = patch.object(self.state.publisher, 'accounts', side_effect=lambda profile='general':
            {'youtube': {'connected': True, 'id': profile, 'name': profile.title()}})
        self.accounts.start()
        self.addCleanup(self.accounts.stop)

    def wait(self):
        for _ in range(400):
            snapshot = self.assistant.snapshot(self.session)
            if snapshot['status'] not in ('planning', 'running', 'transcribing'):
                return snapshot
            time.sleep(.01)
        self.fail('Chat did not finish')

    def prepare(self):
        def facts(path):
            short = 'short' in str(path)
            # Cache filenames lose the source's shape words; preparation gets
            # dimensions again after copying, which is irrelevant to this fixture.
            return SimpleNamespace(duration=15 if short else 90,
                                   width=64 if short else 96, height=96 if short else 64)
        meta = {'title': 'Actual cricket story', 'description': 'Cricket story. #Cricket #IPL #History',
                'tags': ['Cricket'], 'instagram_caption': 'Cricket story.'}
        with patch('hinglish_shorts.source.open_video', side_effect=facts), \
             patch('hinglish_app.assistant_publish.transcripts'), \
             patch('hinglish_publish.metadata.generate_youtube', return_value=(meta, 'Local model fixture')), \
             patch('hinglish_app.assistant.plan') as planner:
            self.assistant.send(self.session, TEXT)
            snapshot = self.wait()
        planner.assert_not_called()  # Saved workflow, not another planning inference.
        self.assertEqual(snapshot['status'], 'needs_review', snapshot['stage'])
        self.assertEqual(len(snapshot['publishing_review']['rows']), 4)
        return snapshot['publishing_review']

    def payload(self, review):
        return {'session': self.session, 'review': review['id'], 'made_for_kids': False, 'synthetic_media': False}

    def test_local_campaign_clarification_resumes_with_original_source_and_new_destination(self):
        from unittest.mock import Mock
        from hinglish_app.assistant_campaign import context
        source=self.root/'library'/'final videos'
        source.mkdir()
        (source/'one source.mp4').write_bytes(b'owner supplied video')
        text=f'Choose one long cricket video from {source}, different from previous video extract seven standalone Shorts below 60 seconds, and schedule one daily on Fantasy Legends at 6 p.m. India time from 20 to 26 October 2030.\n\nand upload on my gaming channel with title n description'
        evidence=context(self.assistant,text)
        folder=next(f for f in evidence['folders'] if f['path']==str(source.resolve()))
        plan={'action':'clarify','reply':'I can prepare the Shorts locally; final public scheduling needs Studio.',
              'question':'Fantasy Legends, gaming, or both?', 'source_folder_id':folder['id'],'source_topic':'cricket',
              'targets':[],'first_date':'2030-10-20','clock':'18:00','count':7,
              'max_seconds_exclusive':60,'different_source':True}
        brain=SimpleNamespace(name='Local decision fixture',json=Mock(return_value=plan),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain), \
             patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_app.assistant.plan') as general, \
             patch('hinglish_publish.campaign.prepare') as prepare:
            self.assistant.send(self.session,text)
            first=self.wait()
        self.assertEqual(first['status'],'idle',first['stage'])
        self.assertEqual(first['campaign_pending'],plan)
        self.assertEqual(first['messages'][-1]['text'],plan['reply']+'\n\n'+plan['question'])
        self.assertEqual(first['brain'],'Local decision fixture')
        prepare.assert_not_called()
        general.assert_not_called()
        chosen={**plan,'action':'prepare','question':'','targets':['gaming'],'reply':'Preparing for gaming.'}
        brain.json=Mock(return_value=chosen)
        result={'clips':[{'video':str(self.root/'result.mp4'),'publish_at':'2030-10-20T18:00:00+05:30'}]}
        with patch('hinglish_visuals.brain.open_brain',return_value=brain), \
             patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_app.assistant.plan') as general, \
             patch('hinglish_publish.campaign.prepare',return_value=result) as prepare, \
             patch('hinglish_publish.campaign.word_refine',return_value=result), \
             patch('hinglish_publish.campaign.review',return_value=result), \
             patch('hinglish_publish.campaign.finish_copy',return_value=result), \
             patch('hinglish_publish.campaign.quality'), \
             patch('hinglish_app.assistant_campaign.stage_review') as staged:
            self.assistant.send(self.session,'Gaming only, keep the other details.')
            final=self.wait()
        self.assertEqual(final['status'],'needs_review',final['stage'])
        staged.assert_called_once_with(self.assistant,self.session,schedule=True)
        general.assert_not_called()
        model_input=brain.json.call_args.args[1]
        self.assertEqual(model_input['user_turns'],[text,'Gaming only, keep the other details.'])
        self.assertNotIn('pending_plan',model_input)
        spec=prepare.call_args.args[4]
        self.assertEqual(spec['targets'][0]['profile'],'gaming')
        self.assertEqual(prepare.call_args.args[1],source.resolve())
        self.assertEqual(spec['max_seconds_exclusive'],60)
        self.assertEqual(spec['count'],7)
        self.assertEqual(spec['first_date'],'2030-10-20')
        self.assertIsNone(final['campaign_pending'])
        self.assertFalse(self.calls)

    def test_local_campaign_preview_and_cancellation_never_start_an_edit(self):
        from unittest.mock import Mock
        base={'action':'preview','reply':'No editing or posting will start.', 'question':'',
              'source_folder_id':0,'source_topic':'cricket','targets':['cricket'],
              'first_date':'2030-10-20','clock':'18:00','count':7,'max_seconds_exclusive':50,'different_source':False}
        brain=SimpleNamespace(name='Local decision fixture',json=Mock(return_value=base),close=Mock())
        with patch('hinglish_visuals.brain.open_brain',return_value=brain), \
             patch('hinglish_cut.gpu_lock.gpu_lock'), \
             patch('hinglish_publish.campaign.prepare') as prepare:
            for text in ('Explain how to schedule cricket Shorts, do not execute.', 'Do not schedule cricket clips.'):
                self.assistant.send(self.session,text)
                snapshot=self.wait()
                self.assertEqual(snapshot['status'],'idle',snapshot['stage'])
        prepare.assert_not_called()
        self.assertFalse(self.calls)

    def test_campaign_stages_all_seven_for_the_existing_review_and_upload_tool(self):
        import json
        from hinglish_app.assistant_campaign import stage_review
        from hinglish_publish.store import fingerprint
        folder=self.root/'output/campaigns/test'
        folder.mkdir(parents=True)
        clips=[]
        for i in range(7):
            video=folder/f'short-{i}.mp4'
            video.write_bytes(f'distinct-campaign-video-{i}'.encode())
            clips.append({'index':i+1,'video':str(video),'fingerprint':fingerprint(video),'duration':35,
                'metadata':{'title':f'Cricket moment {i+1}','description':'Actual cricket. #Cricket #IPL #History',
                            'instagram_caption':'Actual cricket.','tags':['Cricket']}})
        (folder/'campaign.json').write_text(json.dumps({'status':'reviewed','channel_id':'cricket',
            'source':'original.mp4','model':'Local model fixture','clips':clips}),'utf-8')
        self.assistant._update(self.session,campaign=str(folder))
        stage_review(self.assistant,self.session)
        snapshot=self.assistant.snapshot(self.session)
        review=snapshot['publishing_review']
        self.assertEqual(review['state'],'review')
        self.assertEqual(len(review['rows']),7)
        self.assertIn('publishing_review',snapshot['messages'][-1])
        self.assertEqual(self.calls,[])
        start(self.assistant,self.payload(review))
        result=self.wait()
        self.assertEqual(result['status'],'complete',result['stage'])
        self.assertEqual(len(self.calls),7)
        self.assertTrue(all(c['profile']=='cricket' and c['visibility']=='private' for c in self.calls))

    def test_screenshot_command_selects_both_channels_and_both_formats(self):
        parsed = request(TEXT)
        self.assertEqual(parsed['profiles'], ['cricket', 'gaming'])
        self.assertEqual(parsed['kinds'], ['long', 'short'])
        self.assertTrue(parsed['any'])
        self.assertEqual(parsed['visibility'], 'private')
        self.assertIsNotNone(request('Can you upload any video privately to both YouTube channels?'))
        self.assertEqual(request('Upload any video privately to YouTube with both title and description', 'gaming')['profiles'], ['gaming'])
        for message in ('How do I upload random videos to YouTube?', 'Do not upload any YouTube video',
                        'Schedule random videos on YouTube'):
            self.assertIsNone(request(message))

    def test_chat_prepares_four_then_uploads_once_without_scheduled_worker(self):
        review = self.prepare()
        self.assertFalse(self.calls)
        self.assertTrue(all(self.state.publisher.store.get(j)['status'] == 'draft' for j in review['ids']))
        self.assertTrue(all(Path(self.state.publisher.store.get(j)['video']).is_relative_to(self.root / 'cache') for j in review['ids']))
        start(self.assistant, self.payload(review))
        snapshot = self.wait()
        self.assertEqual(snapshot['status'], 'complete', snapshot['stage'])
        self.assertEqual(len(self.calls), 4)
        self.assertEqual({(j['profile'], j['kind']) for j in self.calls},
                         {('cricket', 'long'), ('cricket', 'short'), ('gaming', 'long'), ('gaming', 'short')})
        self.assertTrue(all(j['visibility'] == 'private' and j['account_id'] == j['profile'] for j in self.calls))
        self.assertEqual(len(snapshot['messages'][-1]['publish_results']), 4)
        start(self.assistant, self.payload(review))
        self.assertEqual(len(self.calls), 4)
        self.assertFalse(self.state.publisher.settings()['enabled'])

    def test_declarations_and_review_are_bound_to_the_prepared_batch(self):
        review = self.prepare()
        for payload in ({'session': self.session, 'review': review['id']},
                        {**self.payload(review), 'review': 'invented'},
                        {**self.payload(review), 'metadata': {'other-job': {}}}):
            with self.assertRaises(ValueError):
                start(self.assistant, payload)
        self.assertFalse(self.calls)

    def test_changed_channel_is_not_silently_rebound(self):
        review = self.prepare()
        with patch.object(self.state.publisher, 'accounts', return_value={'youtube': {'connected': True, 'id': 'other'}}):
            with self.assertRaisesRegex(ValueError, 'channel changed'):
                start(self.assistant, self.payload(review))
        self.assertFalse(self.calls)

    def test_review_edits_are_kept_in_the_receipt(self):
        review = self.prepare()
        first = review['ids'][0]
        payload = self.payload(review)
        payload['metadata'] = {first: {'title': 'Creator corrected title'}}
        start(self.assistant, payload)
        snapshot = self.wait()
        self.assertEqual(snapshot['status'], 'complete')
        self.assertEqual(self.calls[0]['metadata']['title'], 'Creator corrected title')
        self.assertEqual(snapshot['publishing_review']['rows'][0]['metadata']['title'], 'Creator corrected title')

    def test_changed_media_stops_before_authorizing_any_upload(self):
        review = self.prepare()
        Path(self.state.publisher.store.get(review['ids'][0])['video']).write_bytes(b'changed after review')
        start(self.assistant, self.payload(review))
        self.assertEqual(self.wait()['status'], 'needs_review')
        self.assertFalse(self.calls)
        self.assertTrue(all(self.state.publisher.store.get(j)['status']=='draft' for j in review['ids']))

    def test_ambiguous_existing_remote_is_never_presented_as_a_completed_private_upload(self):
        review = self.prepare()
        self.state.publisher.store.change(review['ids'][0], status='needs_review', remote={'id': 'accepted001'})
        with self.assertRaisesRegex(ValueError, 'earlier upload needs verification'):
            start(self.assistant, self.payload(review))
        self.assertFalse(self.calls)

    def test_failed_upload_keeps_remote_id_and_never_replays(self):
        review = self.prepare()
        owner = self
        class Failed:
            def __init__(self, *args): pass
            def publish(self, job, checkpoint):
                owner.calls.append(job)
                checkpoint({'id': 'accepted001', 'url': 'https://www.youtube.com/watch?v=accepted001'})
                raise ConnectionError('Lost confirmation')
        self.state.publisher.providers['youtube'] = Failed
        start(self.assistant, self.payload(review))
        snapshot = self.wait()
        self.assertEqual(snapshot['status'], 'needs_review')
        self.assertEqual(self.state.publisher.store.get(review['ids'][0])['remote']['id'], 'accepted001')
        with self.assertRaisesRegex(ValueError,'unverified outcome'):
            start(self.assistant, self.payload(review))
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(all(self.state.publisher.store.get(j)['status']=='draft' for j in review['ids'][1:]))

    def test_typed_declarations_continue_the_same_review(self):
        review = self.prepare()
        self.assertIsNone(confirmation('How do I choose not made for kids?', review))
        self.assertIsNone(confirmation('upload these', review))
        value = confirmation('Upload these privately, not made for kids, no synthetic media', review)
        self.assertEqual(value, {'review': review['id'], 'made_for_kids': False, 'synthetic_media': False})
        self.assistant.send(self.session, 'Upload these privately, not made for kids, no synthetic media')
        self.assertEqual(self.wait()['status'], 'complete')
        self.assertEqual(len(self.calls), 4)

    def test_storylens_chat_can_resume_its_exact_failed_review_with_confirmed_choices(self):
        review=self.prepare()
        review.update(state='needs_review',made_for_kids=False,synthetic_media=False,declarations_confirmed=True)
        self.assistant._update(self.session,publishing_review=review,status='needs_review')
        for text in ('Continue editing the video','Resume tomorrow','Why did this fail?'):
            self.assertIsNone(confirmation(text,review))
        self.assertIsNone(confirmation('Continue',{**review,'declarations_confirmed':False}))
        self.assistant.send(self.session,'Continue')
        result=self.wait()
        self.assertEqual(result['status'],'complete',result['stage'])
        self.assertEqual(len(self.calls),4)
        self.assertTrue(result['publishing_review']['declarations_confirmed'])

    def test_instagram_any_video_uses_the_same_authorized_library(self):
        from hinglish_app.assistant_plan import quick_plan
        parsed = quick_plan('Upload any video to my cricket Instagram account')
        self.assertEqual(parsed['steps'][0], {'tool': 'instagram', 'options': {'instagram_action': 'reel', 'instagram_profile': 'cricket'}})
        from hinglish_app.assistant_social import execute
        bridge = self.state.local_browser
        bridge.bind('general', 'my_account')
        bridge.seen = time.time()
        bridge.worker_version = '0.3.0'
        facts = SimpleNamespace(duration=15, width=64, height=96)
        with patch('hinglish_shorts.source.open_video', return_value=facts), \
             patch('hinglish_publish.metadata.generate_instagram', return_value=(
                 {'instagram_caption': 'Cricket history. #Cricket #IPL #History'}, 'Local model fixture')), \
             patch('hinglish_app.assistant_social.monitor'):
            execute(self.assistant, self.session, 'Upload any video to Instagram', [],
                    self.assistant.snapshot(self.session), {'instagram_action': 'reel'}, lambda text: None)
        jobs = bridge.snapshot()['jobs']
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['account'], 'my_account')
        self.assertEqual(jobs[0]['action'], 'reel')
        self.assertTrue(Path(bridge.get(jobs[0]['id'])['video']).is_relative_to(self.root / 'cache'))


if __name__ == '__main__':
    unittest.main()
