import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

from hinglish_app.assistant_sources import named_sources
from hinglish_app.assistant_publishing_context import schedule_literals
from hinglish_app.assistant_edit_workflow import constraints,plan,requested
from hinglish_app.assistant_distribution import WORKFLOW,validate_edit_plan
from hinglish_app.assistant_plan import validate_plan


class EditPublishWorkflowTests(unittest.TestCase):
    def test_live_full_video_three_shorts_with_alternate_account_navigation(self):
        text=('Schedule the full long-form video on my cricket YouTube channel Fantasy Legends for 22 October 2031 at 7 pm IST. '
              'Extract exactly 3 Shorts and upload to Fantasy Legends on 22, 23 and 24 October 2031. '
              'Schedule the same 3 Shorts on Instagram @fantasy_legends91. '
              'For testing switch to my gaming account and then back to cricket before uploading. '
              'Publish only on Fantasy Legends and @fantasy_legends91.')
        facts=constraints(text,[],WORKFLOW)
        self.assertEqual((facts['profile'],facts['capacity'],facts['first_date'],facts['end_date']),
                         ('cricket',3,'2031-10-22','2031-10-24'))
        self.assertTrue(facts['include_longform']);self.assertTrue(facts['verify_account_switches'])

    def test_cricket_insta_page_is_a_destination_not_the_active_edit_profile(self):
        for text in ('extract 1 short n upload on my cricket insta page',
                     'create a clip and post on my cricket Instagram account'):
            facts=constraints(text,[],WORKFLOW)
            self.assertEqual(facts['profile'],'cricket')
            self.assertEqual(facts['platforms'],'instagram')

    def test_upload_it_resumes_checkpoint_without_requesting_new_clock_or_edit(self):
        import time
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=AppState(root);a=state.assistant;sid=a.create()['id']
            clip=root/'finished.mp4';clip.write_bytes(b'finished')
            options={'distribution_profile':'cricket','distribution_platforms':'instagram',
                     'first_date':'2030-10-21','clock':'19:00','include_longform':False}
            a._update(sid,profile='gaming',status='failed',shorts_paths=[str(clip)],last_paths=[str(clip)],steps=[],
                edit_publish_checkpoint={'profile':'gaming','result':{'folder':str(root/'new-edit')},
                    'steps':[{'tool':'shorts','options':{'count':1}},{'tool':'distribute','options':options}]})
            def prepared(*args):a._update(sid,status='needs_review')
            with patch('hinglish_app.assistant_media.outputs',return_value=[str(clip)]),\
                 patch('hinglish_app.assistant_distribution.from_outputs',side_effect=prepared) as handoff,\
                 patch('hinglish_app.assistant.plan',side_effect=AssertionError('No new model editing plan')) as planner,\
                 patch.object(state,'create_job') as renderer:
                a.send(sid,'upload it on my cricket insta page',profile='gaming')
                for _ in range(300):
                    current=a.snapshot(sid)
                    if current['status'] not in ('planning','running'):break
                    time.sleep(.01)
            self.assertEqual(current['status'],'needs_review',current['stage'])
            self.assertEqual(handoff.call_args.args[2],options)
            renderer.assert_not_called();planner.assert_not_called()

    def test_spoken_clock_and_requests_without_clock(self):
        self.assertEqual(schedule_literals('21 October and 22 October 7 30 p.m.'),
            {'first_date':'2026-10-21','end_date':'2026-10-22','clock':'19:30'})
        self.assertNotIn('clock',schedule_literals('21 October and 22 October'))
        self.assertNotIn('clock',schedule_literals('30 p.m.'))
        self.assertEqual(schedule_literals('one video on 21 October and one video on 22 October')['end_date'],'2026-10-22')

    def test_current_explicit_folder_chooses_named_video_not_parent_or_old_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'low size final';target.mkdir()
            (root/'wrong.mp4').touch();(target/'mi.mp4').touch();rcb=target/'rcb final.mp4';rcb.touch()
            result=named_sources(f'use the RCB final clip from this path {target} and extract shorts and upload on my gaming channel')
            self.assertEqual(result,[rcb.resolve()])
            self.assertEqual(named_sources('use RCB final clip and extract shorts',[rcb]),[rcb.resolve()])
            with self.assertRaisesRegex(ValueError,'multiple videos'):
                named_sources(f'use a clip from {target} and upload')
            self.assertEqual(named_sources(f'choose any video from {target}, extract shorts'),[])
            with self.assertRaisesRegex(ValueError,'not found'):
                named_sources(f'use {root}/missing folder and upload')

    def test_local_planner_returns_connected_two_day_workflow_with_and_without_time(self):
        for suffix,clock in [('',WORKFLOW['daily_time']),(' 7 30 p.m.','19:30')]:
            text='use the RCB final clip extract to short form video and upload on my gaming channel and schedule to 21 October and 22 October'+suffix
            facts=constraints(text,[],WORKFLOW)
            self.assertEqual((facts['capacity'],facts['profile'],facts['platforms']),(2,'gaming','youtube'))
            brain=Mock();brain.json.return_value={'action':'edit','reply':'Preparing the RCB Shorts.',
                'count':2,'max_seconds':50,'profile':'gaming','platforms':'youtube',
                'first_date':'2026-10-21','clock':clock,'captions':False}
            result=validate_plan(plan(brain,text,[],[{'name':'rcb final.mp4','kind':'.mp4'}],WORKFLOW))
            validate_edit_plan(result,text,WORKFLOW)
            self.assertEqual([s['tool'] for s in result['steps']],['shorts','distribute'])
            self.assertEqual(result['steps'][1]['options']['end_date'],'2026-10-22')
            self.assertEqual(result['steps'][1]['options']['clock'],clock)
            self.assertNotIn('think',brain.json.call_args.kwargs)

    def test_folder_first_resolves_following_name_without_matching_directory_or_gaming(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'rcb final';target.mkdir()
            mi=target/'mi.mp4';mi.touch();(target/'rcb final.mp4').touch()
            for text in (f'{target}\ntake the mi video from this path and extract 2 shorts and post on my gaming channel.',
                         f'{target} and take the MI video and extract 2 shorts and post on my gaming channel.',
                         f'From "{target}" take mi.mp4 and extract two shorts.'):
                with self.subTest(text=text):self.assertEqual(named_sources(text),[mi.resolve()])
            with self.assertRaisesRegex(ValueError,'multiple videos'):
                named_sources(f'{target}\nextract 2 shorts with good timing and post on my gaming channel')
            with self.assertRaisesRegex(ValueError,'More than one video'):
                named_sources(f'{target}\ntake mi and rcb final')
            self.assertEqual(named_sources(f'{target}\nchoose any video',[mi]),[])

    def test_post_command_reaches_local_workflow_with_requested_count_cap(self):
        from hinglish_app.assistant_plan import plan as router,quick_plan
        text='D:\\Editing\\documentry edit\\low size final\ntake the mi video from this path and extract 2 shorts and post on my gaming channel.'
        self.assertTrue(requested(text));self.assertIsNone(quick_plan(text))
        facts=constraints(text,[],WORKFLOW)
        self.assertEqual((facts['capacity'],facts['profile'],facts['platforms']),(2,'gaming','youtube'))
        brain=Mock();brain.name='local fixture'
        answer={'action':'edit','reply':'Preparing.','count':2,'max_seconds':50,
                'profile':'gaming','platforms':'youtube','first_date':facts['first_date'],
                'clock':facts['clock'],'captions':True}
        brain.json.side_effect=[dict(answer,count=7),answer]
        with tempfile.TemporaryDirectory() as folder,patch('hinglish_visuals.brain.open_brain',return_value=brain):
            result,name=router(folder,text,[],[{'name':'mi.mp4','kind':'.mp4'}],False)
        self.assertEqual(name,'local fixture');self.assertEqual(brain.json.call_count,2)
        self.assertEqual(brain.json.call_args.args[2]['properties']['count']['maximum'],2)
        self.assertEqual([s['tool'] for s in result['steps']],['shorts','distribute'])
        self.assertEqual(result['steps'][0]['options']['count'],2)
        self.assertEqual(result['steps'][1]['options']['distribution_profile'],'gaming')

    def test_folder_first_chat_passes_new_source_through_edit_and_publish_handoff(self):
        import time
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);media=root/'low size final';media.mkdir()
            mi=media/'mi.mp4';mi.write_bytes(b'fixture source');(media/'rcb final.mp4').touch()
            old=root/'old-short.mp4';old.write_bytes(b'old output')
            state=AppState(root);assistant=state.assistant;sid=assistant.create()['id']
            assistant._update(sid,last_paths=[str(old)])
            text=f'{media}\ntake the mi video from this path and extract 2 shorts and post on my gaming channel.'
            facts=constraints(text,[],WORKFLOW);brain=Mock();brain.name='local fixture'
            brain.json.return_value={'action':'edit','reply':'Preparing.','count':2,'max_seconds':50,
                'profile':'gaming','platforms':'youtube','first_date':facts['first_date'],
                'clock':facts['clock'],'captions':True}
            clips=[root/'new-short-1.mp4',root/'new-short-2.mp4']
            for clip in clips:clip.write_bytes(b'fixture export')
            def create(payload):
                job={'id':'fixture','status':'complete','stage':'Done',
                     'result':{'folder':str(root),'previews':list(map(str,clips))}}
                state.jobs[job['id']]=job;return job
            def staged(*args):assistant._update(sid,status='needs_review')
            # Fixtures exercise the real chat/router, with every media execution
            # and publishing handoff replaced. No account/network work runs.
            with patch('hinglish_visuals.brain.open_brain',return_value=brain),\
                 patch.object(state,'create_job',side_effect=create) as runner,\
                 patch('hinglish_app.assistant_media.outputs',return_value=list(map(str,clips))),\
                 patch('hinglish_app.assistant_distribution.from_outputs',side_effect=staged) as handoff,\
                 patch('hinglish_app.assistant_distribution.followup') as old_distribution,\
                 patch('hinglish_app.assistant_campaign.followup') as old_campaign:
                assistant.send(sid,text,profile='gaming')
                for _ in range(300):
                    current=assistant.snapshot(sid)
                    if current['status'] not in ('planning','running'):break
                    time.sleep(.01)
            self.assertEqual(current['status'],'needs_review',current.get('stage'))
            runner.assert_called_once();handoff.assert_called_once()
            self.assertEqual(runner.call_args.args[0]['source_paths'],[str(mi.resolve())])
            self.assertEqual(runner.call_args.args[0]['shorts_count'],'2')
            self.assertEqual(brain.json.call_args.args[1]['attached_media'],[{'name':'mi.mp4','kind':'.mp4'}])
            self.assertEqual(handoff.call_args.args[2]['distribution_profile'],'gaming')
            self.assertEqual(current['shorts_paths'],list(map(str,clips)))
            old_distribution.assert_not_called();old_campaign.assert_not_called()

    def test_invalid_local_plan_never_dispatches_or_coerces_clock(self):
        brain=Mock();brain.json.return_value={'action':'edit','count':7,'max_seconds':60,'clock':'invalid'}
        with self.assertRaisesRegex(ValueError,'could not validate'):
            plan(brain,'extract shorts and upload on gaming channel 21 October and 22 October',[],[],WORKFLOW)
        self.assertEqual(brain.json.call_count,2)

    def test_model_duration_cap_is_valid_for_the_real_shorts_tool(self):
        from hinglish_shorts.settings import ShortsSettings
        brain=Mock();brain.json.return_value={'action':'edit','reply':'Preparing.','count':2,'max_seconds':25,
            'profile':'gaming','platforms':'youtube','first_date':'2026-10-21','clock':'19:00','captions':False}
        result=plan(brain,'extract shorts and upload on gaming channel 21 October and 22 October',[],[],WORKFLOW)
        options=result['steps'][0]['options']
        ShortsSettings(min_length=options['min_seconds'],max_length=options['max_seconds'])

    def test_new_source_route_uses_bounded_model_plan(self):
        from hinglish_app.assistant_plan import plan as router
        brain=Mock();brain.name='local fixture'
        brain.json.return_value={'action':'edit','reply':'Preparing.','count':2,'max_seconds':50,
            'profile':'gaming','platforms':'youtube','first_date':'2026-10-21','clock':'19:00','captions':False}
        with tempfile.TemporaryDirectory() as folder,patch('hinglish_visuals.brain.open_brain',return_value=brain):
            result,name=router(folder,'extract shorts from RCB and upload on gaming channel and schedule to 21 October and 22 October',
                [],[{'name':'rcb final.mp4','kind':'.mp4'}],True,memory_context={'editing_sources':[{'id':'unrelated'}]})
        self.assertEqual([s['tool'] for s in result['steps']],['shorts','distribute'])
        self.assertEqual(name,'local fixture')
        self.assertEqual(brain.json.call_count,1)

    def test_explanation_and_exclusions_do_not_execute(self):
        self.assertFalse(requested('why cannot you extract shorts and upload?'))
        self.assertFalse(requested('extract shorts but do not upload'))
        self.assertFalse(requested('extract shorts but do not post'))

    def test_oversized_context_retries_without_changing_foreground_or_source_ids(self):
        from hinglish_app.assistant_plan_context import ask
        brain=Mock();brain.json.side_effect=[RuntimeError('HTTP 400: request exceeds the available context size'),{'steps':[]}]
        data={'request':'RCB, 21 and 22 October','attachments':[{'name':'rcb final.mp4'}],
            'shared_memory':{'editing_sources':[{'id':'real-source'}],'messages':['unrelated']},'conversation':[{'text':str(n)} for n in range(12)]}
        self.assertEqual(ask(brain,'system',data,{}),{'steps':[]})
        retry=brain.json.call_args.args[1]
        self.assertEqual(retry['request'],data['request']);self.assertEqual(retry['attachments'],data['attachments'])
        self.assertEqual(retry['shared_memory']['editing_sources'],data['shared_memory']['editing_sources'])
        self.assertNotIn('messages',retry['shared_memory']);self.assertIn('messages',data['shared_memory'])
        brain.json.side_effect=RuntimeError('HTTP 400: invalid schema')
        with self.assertRaisesRegex(RuntimeError,'invalid schema'):ask(brain,'system',data,{})

    def test_normal_chat_resume_keeps_the_completed_outputs_and_publishing_options(self):
        import time
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=AppState(root);assistant=state.assistant;sid=assistant.create()['id']
            clip=root/'clip.mp4';clip.touch();options={'distribution_profile':'gaming','first_date':'2026-10-21','clock':'19:00'}
            assistant._update(sid,profile='gaming',status='failed',last_paths=[str(clip)],shorts_paths=[str(clip)],
                steps=[{'tool':'shorts','options':{}},{'tool':'distribute','options':options}],last_result={'folder':str(root)})
            def staged(*args):assistant._update(sid,status='needs_review')
            with patch('hinglish_app.assistant_media.outputs',return_value=[str(clip)]) as outputs,\
                 patch('hinglish_app.assistant_distribution.from_outputs',side_effect=staged) as stage,\
                 patch.object(state,'create_job') as create:
                assistant.send(sid,'Resume the existing workflow',profile='gaming')
                for _ in range(200):
                    current=assistant.snapshot(sid)
                    if current['status'] not in ('running','planning'):break
                    time.sleep(.01)
            self.assertEqual(current['status'],'needs_review',current.get('stage'))
            create.assert_not_called();outputs.assert_called_once()
            self.assertEqual(stage.call_args.args[2],options)

    def test_upload_these_prefers_unfinished_new_edit_over_stale_review_and_old_batch(self):
        import time
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=AppState(root);a=state.assistant;sid=a.create()['id']
            fresh=[str(root/'new-1.mp4'),str(root/'new-2.mp4')]
            stale=[str(root/f'old-{i}.mp4') for i in range(7)]
            for video in fresh+stale:Path(video).touch()
            options={'distribution_profile':'gaming','distribution_platforms':'youtube','first_date':'2026-10-25','clock':'19:00'}
            a._update(sid,profile='gaming',status='needs_review',shorts_paths=stale,last_paths=stale,
                campaign='old-campaign',publishing_review={'id':'old','state':'needs_review','ids':['old-receipt'],'rows':[{'id':'old-receipt'}]},
                edit_publish_checkpoint={'profile':'gaming','result':{'folder':str(root/'new-edit')},
                    'steps':[{'tool':'shorts','options':{'count':2}},{'tool':'distribute','options':options}]})
            def staged(*args):a._update(sid,status='needs_review')
            with patch('hinglish_app.assistant_media.outputs',return_value=fresh) as outputs,\
                 patch.object(state.publisher.store,'get',return_value={'status':'uploaded_private','remote':{'id':'old-video','privacy':'private'}}),\
                 patch('hinglish_app.assistant_distribution.from_outputs',side_effect=staged) as handoff,\
                 patch('hinglish_app.assistant_publish.start') as publish,\
                 patch('hinglish_app.assistant_campaign.followup') as campaigns,\
                 patch.object(state,'create_job') as extract:
                a.send(sid,'upload and shedule these videos on my gaming channel',profile='gaming')
                for _ in range(300):
                    current=a.snapshot(sid)
                    if current['status'] not in ('planning','running'):break
                    time.sleep(.01)
            self.assertEqual(current['status'],'needs_review',current.get('stage'))
            outputs.assert_called_once();handoff.assert_called_once()
            self.assertEqual(current['shorts_paths'],fresh)
            self.assertIsNone(current['publishing_review']);self.assertIsNone(current['campaign'])
            self.assertEqual(handoff.call_args.args[2],options)
            extract.assert_not_called();publish.assert_not_called();campaigns.assert_not_called()


if __name__=='__main__':unittest.main()
