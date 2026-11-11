import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_app.assistant import Assistant
from hinglish_app.assistant_plan import job_payload, quick_plan, validate_plan, plan, TOOLS
from hinglish_app.server import AppState


def request_plan(*tools, **kw):
    return {'reply': 'Starting your edit.', 'question': '', 'combine': kw.get('combine', False),
            'steps': [{'tool': t, 'options': {}} for t in tools]}


class PlannerTests(unittest.TestCase):
    def test_multistep_model_cannot_replace_explicit_typography_number(self):
        class Brain:
            name = 'fixture'
            def json(self, *args, **kwargs):
                return {'reply': 'Starting.', 'question': '', 'combine': True,
                        'steps': [{'tool': 'clean', 'options': {}},
                                  {'tool': 'captions', 'options': {'caption_style': 'typography_1'}}]}
            def close(self): pass
        with tempfile.TemporaryDirectory() as folder, patch('hinglish_visuals.brain.open_brain', return_value=Brain()):
            value, _ = plan(folder, 'Clean my clips, then add Typography 4 captions.', [], [], False)
        self.assertEqual(value['steps'][1]['options']['caption_style'], 'typography_4')

    def test_negated_or_multiple_templates_are_not_rebound(self):
        class Brain:
            name = 'fixture'
            def json(self, *args, **kwargs):
                return {'reply': 'Starting.', 'question': '', 'combine': False,
                        'steps': [{'tool': 'captions', 'options': {'caption_style': 'typography_3'}}]}
            def close(self): pass
        with tempfile.TemporaryDirectory() as folder:
            for text in ('Do not use Typography 4; use Typography 3 instead.', 'Avoid Typography 4. Use another suitable style.'):
                with patch('hinglish_visuals.brain.open_brain', return_value=Brain()):
                    value, _ = plan(folder, text, [], [], False)
                self.assertEqual(value['steps'][0]['options']['caption_style'], 'typography_3')

    def test_typography_number_selects_exact_style(self):
        for n in range(1, 6):
            plan = quick_plan(f'Add captions using Typography {n}')
            self.assertEqual(plan['steps'][0], {'tool': 'captions', 'options': {'caption_style': f'typography_{n}'}})

    def test_shots_in_long_form_request_and_short_caption_options(self):
        p = quick_plan('Extract 10 shots from my long video')
        self.assertEqual(p['steps'][0]['tool'], 'shorts')
        self.assertEqual(p['steps'][0]['options']['count'], 10)
        p = quick_plan('Make 8 shorts with captions using typography 3')
        opts = job_payload(p['steps'][0], ['local.mp4'])
        self.assertEqual(opts['shorts_count'], '8')
        self.assertTrue(opts['shorts_captions'])
        self.assertEqual(opts['caption_style'], 'typography_3')

    def test_question_negation_and_multiple_edits_need_context(self):
        for text in ('How do I add captions?', 'Do not add captions', 'Clean and add captions',
                     'Use Typography 4 instead', 'Add captions in a specific font'):
            self.assertIsNone(quick_plan(text))

    def test_clean_join_in_order_is_requested(self):
        self.assertTrue(quick_plan('Clean these clips and combine them into one video')['combine'])

    def test_unknown_tools_and_options_and_paths_are_rejected(self):
        for tool, options in [('shell', {}), ('clean', {'source_paths': ['secret.mp4']}),
                              ('shorts', {'count': 0}), ('shorts', {'count': True}),
                              ('captions', {'caption_style': 'imaginary'}), ('clean', {'format': 'delete'})]:
            with self.assertRaises(ValueError):
                validate_plan({'reply': '', 'question': '', 'steps': [{'tool': tool, 'options': options}]})

    def test_question_prevents_execution_and_mixed_publication_rejected(self):
        p = request_plan('clean', question='Which video?')
        p['question'] = 'Which video?'
        self.assertEqual(validate_plan(p)['steps'], [])
        with self.assertRaises(ValueError):
            validate_plan(request_plan('clean', 'publish'))

    def test_local_llm_receives_context_and_always_closes(self):
        class Brain:
            name = 'Test local model'
            def json(self, system, data, schema, **_):
                self.data = data
                return request_plan('script')
            def close(self): self.closed = True
        with tempfile.TemporaryDirectory() as root:
            brain = Brain()
            with patch('hinglish_visuals.brain.open_brain', return_value=brain):
                p, name = plan(root, 'Arrange these takes by meaning', [{'role': 'user', 'text': 'My outline'}],
                               [{'name': 'take.mp4'}], False)
            self.assertEqual(p['steps'][0]['tool'], 'script')
            self.assertEqual(brain.data['conversation'][0]['text'], 'My outline')
            self.assertEqual(set(brain.data['tools']), set(TOOLS))
            self.assertTrue(brain.closed)

    def test_help_answer_cannot_dispatch_a_model_generated_edit(self):
        class Brain:
            name = 'Local help model'
            def json(self, system, data, schema, **_):
                return {'reply': 'Attach your long video and ask for ten Shorts.',
                        'steps': [{'tool': 'shorts', 'options': {'count': 10}}]}
            def close(self): self.closed = True
        with tempfile.TemporaryDirectory() as root:
            b = Brain()
            with patch('hinglish_visuals.brain.open_brain', return_value=b):
                p, _ = plan(root, 'How would I make Shorts?', [], [], False)
            self.assertEqual(p['steps'], [])
            self.assertIn('Attach', p['reply'])
            self.assertTrue(b.closed)


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.state = AppState(self.root)
        self.assistant = self.state.assistant
        self.session = self.assistant.create()['id']
        self.video = self.root / 'take.mp4'
        self.video.write_bytes(b'video')

    def tearDown(self): self.temp.cleanup()

    def wait(self):
        for _ in range(200):
            s = self.assistant.snapshot(self.session)
            if s['status'] not in ('planning', 'running', 'transcribing'): return s
            time.sleep(.01)
        self.fail('Assistant did not finish')

    def fake_job(self, payload):
        self.payloads.append(payload)
        folder = self.root / 'output' / payload['mode']
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'report.html').write_text('Review')
        video = folder / 'edited.mp4'
        video.write_bytes(b'result')
        job = {'id': str(len(self.payloads)), 'status': 'complete', 'progress': 100, 'mode': payload['mode'],
               'stage': 'Complete', 'result': {'page': str(folder / 'report.html'), 'folder': str(folder),
                                             'quality_summary': None, 'xml_files': [], 'previews': [str(video)]}}
        self.state.jobs[job['id']] = job
        return job

    def test_missing_video_asks_then_attachment_continues_saved_plan(self):
        self.assistant.send(self.session, 'Add captions using Typography 4')
        s = self.wait()
        self.assertEqual(s['status'], 'idle')
        self.assertEqual(s['pending']['steps'][0]['options']['caption_style'], 'typography_4')
        a = self.assistant.attach(self.session, self.video)
        self.payloads = []
        with patch.object(self.state, 'create_job', self.fake_job), patch('hinglish_app.assistant_media.outputs', side_effect=lambda *a: a[2]['previews']):
            self.assistant.send(self.session, 'Start', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'complete')
        self.assertEqual(self.payloads[0]['caption_style'], 'typography_4')

    def test_chain_and_followup_use_the_edited_output_and_keep_original(self):
        a = self.assistant.attach(self.session, self.video)
        self.payloads = []
        with patch('hinglish_app.assistant.plan', return_value=(request_plan('clean', 'captions'), 'Local model')), \
             patch.object(self.state, 'create_job', self.fake_job), \
             patch('hinglish_app.assistant_media.outputs', side_effect=lambda *a: a[2]['previews']):
            self.assistant.send(self.session, 'Clean, then caption', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'complete')
        self.assertEqual(self.payloads[1]['source_paths'], [str(self.root / 'output/clean/edited.mp4')])
        def followup_plan(*args, **kwargs):
            p = request_plan('zoom')
            p['source_id'] = next(c['id'] for c in kwargs['memory_context']['editing_sources'] if c['current_chat'] and c['latest_in_chat'])
            return p, 'Local model'
        with patch('hinglish_app.assistant.plan', side_effect=followup_plan), patch.object(self.state, 'create_job', self.fake_job), patch('hinglish_app.assistant_media.outputs', side_effect=lambda *a: a[2]['previews']):
            self.assistant.send(self.session, 'Add zoom')
            s = self.wait()
        self.assertEqual(self.payloads[-1]['source_paths'], [str(self.root / 'output/captions/edited.mp4')])
        self.assertTrue(self.video.exists())

    def test_gaming_bundle_and_publication_keep_original_and_prepared_shorts(self):
        a=self.assistant.attach(self.session,self.video);self.payloads=[]
        with patch.object(self.state,'create_job',self.fake_job), patch('hinglish_app.assistant_media.outputs',side_effect=lambda *a:a[2]['previews']):
            self.assistant.send(self.session,'Make 12 Shorts from my gaming stream, then create a 15-minute gaming highlights compilation.',[a['id']],profile='gaming')
            s=self.wait()
        self.assertEqual(s['status'],'complete')
        self.assertEqual([p['mode'] for p in self.payloads],['shorts','gaming'])
        self.assertEqual(self.payloads[1]['source_paths'],[str(self.video)])
        self.assertEqual(s['original_paths'],[str(self.video)])
        with patch('hinglish_app.assistant.plan',return_value=({'reply':'Prepare drafts','question':'','combine':False,'steps':[{'tool':'publish','options':{'make_shorts':True}}]},'Local')), patch.object(self.state.publisher,'prepare_file',return_value={'job_ids':['draft']}) as prepare:
            self.assistant.send(self.session,'Prepare highlights and Shorts for my gaming channels',profile='gaming')
            s=self.wait()
        self.assertEqual(s['status'],'complete')
        self.assertEqual(prepare.call_count,2)
        calls=prepare.call_args_list
        self.assertFalse(calls[0].args[1]['make_shorts'])
        self.assertEqual(calls[0].args[1]['shorts_source'],str(self.video))
        self.assertEqual(calls[1].args[0]['kind'],'short')
        self.assertEqual(calls[1].args[1]['profile'],'gaming')

    def test_paired_gaming_workflow_uses_highlights_as_shorts_source_then_reviews_distribution(self):
        a=self.assistant.attach(self.session,self.video);self.payloads=[]
        parsed=request_plan('gaming','shorts','distribute')
        def review(assistant,session_id,options,text,progress):
            assistant._update(session_id,status='needs_review',stage='Fixture paired review')
        with patch('hinglish_app.assistant.plan',return_value=(parsed,'local fixture')), \
             patch.object(self.state,'create_job',self.fake_job), \
             patch('hinglish_app.assistant_media.outputs',side_effect=lambda *args:args[2]['previews']), \
             patch('hinglish_app.assistant_distribution.from_outputs',side_effect=review) as distribute:
            self.assistant.send(self.session,'Make gaming stream highlights, then Shorts from those highlights, and schedule both YouTube and Instagram.',[a['id']],profile='gaming')
            s=self.wait()
        self.assertEqual(s['status'],'needs_review',s['stage'])
        self.assertEqual([p['mode'] for p in self.payloads],['gaming','shorts'])
        self.assertEqual(self.payloads[1]['source_paths'],[str(self.root/'output/gaming/edited.mp4')])
        self.assertEqual(s['highlights_paths'],[str(self.root/'output/gaming/edited.mp4')])
        distribute.assert_called_once();self.assertTrue(self.video.exists())

    def test_new_gaming_file_path_never_reuses_old_shorts_or_old_original(self):
        old=self.root/'old-short.mp4';old.write_bytes(b'old short')
        self.assistant._update(self.session,last_paths=[str(old)],original_paths=[str(old)])
        self.payloads=[];parsed=request_plan('gaming','shorts','distribute')
        def review(assistant,session_id,*args):assistant._update(session_id,status='needs_review')
        text=f'Use {self.video} as my gaming livestream recording. Make highlights then seven Shorts from those highlights and schedule YouTube and Instagram.'
        with patch('hinglish_app.assistant.plan',return_value=(parsed,'local fixture')), \
             patch('hinglish_app.assistant_distribution.followup') as reuse,patch('hinglish_app.assistant_campaign.followup') as campaign, \
             patch.object(self.state,'create_job',self.fake_job),patch('hinglish_app.assistant_media.outputs',side_effect=lambda *args:args[2]['previews']), \
             patch('hinglish_app.assistant_distribution.from_outputs',side_effect=review):
            self.assistant.send(self.session,text,profile='gaming');s=self.wait()
        self.assertEqual(s['status'],'needs_review',s['stage'])
        self.assertEqual(self.payloads[0]['source_paths'],[str(self.video)])
        self.assertEqual(self.payloads[1]['source_paths'],[str(self.root/'output/gaming/edited.mp4')])
        reuse.assert_not_called();campaign.assert_not_called()

    def test_named_gaming_folder_attaches_its_single_recording_before_local_planning(self):
        self.state.publisher.settings({'source_root':str(self.root)},profile='gaming')
        self.payloads=[]
        text=f'Create local gaming livestream highlights from {self.root}. Do not create Shorts or upload to Instagram.'
        with patch('hinglish_app.assistant.plan',return_value=(request_plan('gaming'),'local fixture')) as planner, \
             patch('hinglish_app.assistant_distribution.followup') as distribution, \
             patch('hinglish_app.assistant_campaign.followup') as campaign, \
             patch.object(self.state,'create_job',self.fake_job), \
             patch('hinglish_app.assistant_media.outputs',side_effect=lambda *args:args[2]['previews']):
            self.assistant.send(self.session,text,profile='gaming');result=self.wait()
        self.assertEqual(result['status'],'complete',result['stage'])
        self.assertEqual(self.payloads[0]['source_paths'],[str(self.video)])
        self.assertEqual(planner.call_args.args[3],[{'name':self.video.name,'kind':'.mp4'}])
        distribution.assert_not_called();campaign.assert_not_called()

    def test_stop_keeps_current_result_and_skips_remaining_steps(self):
        a = self.assistant.attach(self.session, self.video)
        self.payloads = []
        def run(payload):
            self.assistant.stop(self.session)
            return self.fake_job(payload)
        with patch('hinglish_app.assistant.plan', return_value=(request_plan('clean', 'captions'), 'Local')), \
             patch.object(self.state, 'create_job', run), patch('hinglish_app.assistant_media.outputs', side_effect=lambda *a: a[2]['previews']):
            self.assistant.send(self.session, 'Clean then caption', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'stopped')
        self.assertEqual(len(self.payloads), 1)
        self.assertTrue(s['last_paths'])

    def test_failed_quality_does_not_start_next_tool(self):
        a = self.assistant.attach(self.session, self.video)
        self.payloads = []
        def run(payload):
            j = self.fake_job(payload)
            j['result']['quality_summary'] = {'passed': False, 'failed': ['Speech lost']}
            return j
        with patch('hinglish_app.assistant.plan', return_value=(request_plan('clean', 'captions'), 'Local')), patch.object(self.state, 'create_job', run):
            self.assistant.send(self.session, 'Clean then caption', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'needs_review')
        self.assertEqual(len(self.payloads), 1)

    def test_missing_gpu_is_a_clear_setup_error_no_job_started(self):
        a = self.assistant.attach(self.session, self.video)
        with patch('hinglish_app.assistant.plan', return_value=(request_plan('aivideo'), 'Local')), \
             patch('hinglish_aigen.engine.doctor', return_value={'cuda': False, 'problem': 'RTX setup required'}), \
             patch.object(self.state, 'create_job') as create:
            self.assistant.send(self.session, 'Generate AI video', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'failed')
        self.assertIn('RTX setup required', s['stage'])
        create.assert_not_called()

    def test_reloaded_session_preserves_history_but_never_restarts_work(self):
        self.assistant._message(self.session, 'user', 'Edit my video')
        self.assistant._update(self.session, status='running', last_paths=[str(self.video)])
        recovered = Assistant(self.state).snapshot(self.session)
        self.assertEqual(recovered['status'], 'interrupted')
        self.assertEqual(recovered['messages'][0]['text'], 'Edit my video')
        self.assertEqual(recovered['last_paths'], [str(self.video)])

    def test_upload_session_and_file_boundaries_and_partial_transfer(self):
        with self.assertRaises(ValueError):
            self.assistant.save_upload('../escape', 'video.mp4', io.BytesIO(b'x'), 1)
        with self.assertRaises(ValueError):
            self.assistant.save_upload(self.session, 'run.exe', io.BytesIO(b'x'), 1)
        with self.assertRaises(ValueError):
            self.assistant.save_upload(self.session, 'video.mp4', io.BytesIO(b'x'), 10)
        a = self.assistant.save_upload(self.session, '../../outside.mp4', io.BytesIO(b'video'), 5)
        self.assertTrue(Path(a['path']).is_relative_to(self.assistant.folder / 'uploads' / self.session))
        self.assertFalse(list(self.assistant.folder.rglob('*.partial')))
        other = self.assistant.create()['id']
        with self.assertRaises(ValueError):
            self.assistant.send(other, 'Clean', [a['id']])

    def test_script_edit_asks_for_outline_not_guesses(self):
        a = self.assistant.attach(self.session, self.video)
        with patch('hinglish_app.assistant.plan', return_value=(request_plan('script'), 'Local')), patch.object(self.state, 'create_job') as create:
            self.assistant.send(self.session, 'Arrange by meaning', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'idle')
        self.assertIn('script', s['messages'][-1]['text'])
        create.assert_not_called()

    def test_stage_sources_preserves_attachment_order(self):
        second = self.root / 'aaa.mp4'
        second.write_bytes(b'2')
        folder = self.state._stage_sources('order', [self.video, second, self.video])
        self.assertEqual((folder / '0000-take.mp4').read_bytes(), b'video')
        self.assertEqual((folder / '0001-aaa.mp4').read_bytes(), b'2')

    def test_attached_outline_continues_pending_script_using_original_takes(self):
        a = self.assistant.attach(self.session, self.video)
        with patch('hinglish_app.assistant.plan', return_value=(request_plan('script'), 'Local')):
            self.assistant.send(self.session, 'Arrange by meaning', [a['id']])
            self.wait()
        outline = self.root / 'outline.txt'
        outline.write_text('My actual narration outline')
        b = self.assistant.attach(self.session, outline)
        self.payloads = []
        with patch.object(self.state, 'create_job', self.fake_job), patch('hinglish_app.assistant_media.outputs', side_effect=lambda *a: a[2]['previews']):
            self.assistant.send(self.session, 'Start', [b['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'complete')
        self.assertEqual(self.payloads[0]['script'], 'My actual narration outline')
        self.assertEqual(self.payloads[0]['source_paths'], [str(self.video)])

    def test_publishing_prepares_attached_file_without_authorizing(self):
        a = self.assistant.attach(self.session, self.video)
        with patch.object(self.state.publisher, 'prepare_file', return_value={'job_ids': ['draft1']}) as prepare, \
             patch.object(self.state.publisher, 'authorize') as authorize:
            self.assistant.send(self.session, 'Upload this on YouTube', [a['id']])
            s = self.wait()
        self.assertEqual(s['status'], 'complete')
        self.assertEqual(prepare.call_args.args[0]['video'], str(self.video))
        self.assertEqual(s['messages'][-1]['publish_ids'], ['draft1'])
        self.assertEqual(s['messages'][-1]['navigate'], 'publisher')
        authorize.assert_not_called()

    def test_voice_transcript_uses_the_same_dispatch_flow(self):
        a = self.assistant.save_upload(self.session, 'voice.webm', io.BytesIO(b'audio'), 5, 'voice')
        with patch('hinglish_app.assistant_media.transcribe_voice', return_value='Add captions using Typography 2'):
            self.assistant.send(self.session, '', [], a['id'])
            s = self.wait()
        self.assertTrue(s['messages'][0]['voice'])
        self.assertEqual(s['pending']['steps'][0]['options']['caption_style'], 'typography_2')

    def test_user_message_is_saved_before_any_worker_runs(self):
        text='Upload 2 saved Shorts from my folder'
        with patch('hinglish_app.assistant.threading.Thread') as worker:
            snapshot=self.assistant.send(self.session,text)
            self.assertEqual(snapshot['messages'][0]['text'],text)
            worker.return_value.start.assert_called_once()
        saved=json.loads((self.assistant.folder/(self.session+'.json')).read_text('utf-8'))
        self.assertEqual(saved['messages'][0]['role'],'user')
        self.assertEqual(saved['messages'][0]['text'],text)

    def test_new_delivery_does_not_display_previous_workflow_complete(self):
        self.assistant._update(self.session,publishing_review={
            'id':'old','created':time.time()-100,'ids':[],'rows':[],
            'instagram_rows':[{'id':str(i),'account':'gaming','status':'published',
                'url':'https://www.instagram.com/reel/old/'} for i in range(2)]})
        self.assertEqual(self.assistant.snapshot(self.session)['workflow_status']['published_count'],2)
        with patch('hinglish_app.assistant.threading.Thread'):
            state=self.assistant.send(self.session,'upload 3 videos on my cricket insta page without scheduling')
        self.assertFalse(state['workflow_status']['complete'])
        self.assertEqual(state['workflow_status']['delivery_count'],0)
        self.assertEqual(state['previous_workflow_status']['published_count'],2)
        self.assertEqual(state['publishing_review']['id'],'old')

    def test_folder_resolution_failure_retains_original_prompt_once(self):
        folder=self.root/'sources';folder.mkdir()
        (folder/'first.mp4').write_bytes(b'one');(folder/'second.mp4').write_bytes(b'two')
        text=f'{folder}\nextract 2 shorts from an unnamed source'
        with patch.object(self.state,'create_job') as job:
            self.assistant.send(self.session,text)
            snapshot=self.wait()
        self.assertEqual(snapshot['status'],'failed')
        self.assertEqual([m['text'] for m in snapshot['messages'] if m['role']=='user'],[text])
        self.assertIn('multiple videos',snapshot['messages'][-1]['text'])
        job.assert_not_called()

    def test_folder_video_upload_reaches_saved_selector_without_source_filename_error(self):
        folder=self.root/'remove silence'/'All Shorts';folder.mkdir(parents=True)
        (folder/'Shorts 1.mp4').write_bytes(b'one');(folder/'Shorts 2.mp4').write_bytes(b'two')
        text=f'{folder}\nupload 2 videos on my cricket insta page and add title and hastags'
        def selected(assistant,session,text,progress):
            assistant._update(session,status='idle',stage='Reached saved-media selector')
            return True
        with patch('hinglish_app.assistant_saved_reels.followup',side_effect=selected) as selector, \
             patch('hinglish_app.workflow_memory.configuration',return_value={'enabled':False}), \
             patch('hinglish_app.assistant_sources.named_sources',side_effect=AssertionError('Single-file source resolution must not run')):
            self.assistant.send(self.session,text,profile='cricket')
            snapshot=self.wait()
        selector.assert_called_once()
        self.assertEqual(snapshot['stage'],'Reached saved-media selector')
        self.assertEqual([m['text'] for m in snapshot['messages'] if m['role']=='user'],[text])
        self.assertFalse(self.state.local_browser.data['jobs'])


if __name__ == '__main__': unittest.main()
