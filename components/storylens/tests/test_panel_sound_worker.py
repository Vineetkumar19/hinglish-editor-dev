"""Worker dispatch fixtures only; no actual local analysis/mix/host actions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PanelSoundWorkerTests(unittest.TestCase):
    def test_normal_chat_staged_single_file_is_passed_to_analysis_not_the_upload_folder(self):
        from hinglish_app.panel_sound_worker import execute
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();staged=root/'cache/job/media';staged.mkdir(parents=True)
            source=staged/'0000-actual-source.mp4';source.write_bytes(b'controller fixture, not actual media')
            script=root/'reference.txt';script.write_text('Exact ASR reference');creator=root/'creator.json';creator.write_text('{"profile":"gaming"}')
            output=root/'output/sound-recommendations/fixture';output.mkdir(parents=True)
            result={'status':'no_match','folder':str(output),'manifest':str(output/'manifest.json'),'rendered':False}
            with patch('hinglish_sound.recommendation_pipeline.run',return_value=result) as run:
                execute(root,staged,script,creator,'actual-job','medium')
            self.assertEqual(run.call_args.args[1],source)

    def test_normal_application_manual_mode_never_starts_the_full_mix_or_quality_retry(self):
        import sys,threading
        from unittest.mock import Mock
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();output=root/'output/sound-recommendations/fixture';output.mkdir(parents=True)
            manifest=output/'manifest.json';manifest.write_text('{}');page=output/'report.html';page.write_text('Fixture review')
            (output/'result.json').write_text(json.dumps({'status':'ready','manifest':str(manifest),'rendered':False}))
            source=root/'source.mp4';source.write_bytes(b'NOT ACTUAL VIDEO; PROCESS MOCK ONLY')
            state=AppState.__new__(AppState);state.root=root;state.engine_root=root;state.python_executable=Path(sys.executable)
            state.license_client=None;state.lock=threading.Lock();state.jobs={'job-one':{'id':'job-one','mode':'sound','status':'running','logs':[]}}
            state._stage_sources=Mock(return_value=None)
            process=Mock();process.stdout=iter(['Results: '+str(page)+'\n']);process.wait.return_value=0;process.poll.return_value=0
            payload={'mode':'sound','panel_sound_action':'recommend','format':'instagram_vertical','profile':'gaming','_creator_context':{'profile':'gaming','feedback':'FULL'},'quality_check':True}
            with patch('hinglish_app.server.subprocess.Popen',return_value=process) as launch:
                state._execute_job('job-one',payload,[],source,'Exact shared script')
            command=launch.call_args.args[0]
            self.assertIn('hinglish_app.panel_sound_worker',command);self.assertNotIn('hinglish_eval',command)
            self.assertNotIn('--format',command,'Audio-only suggestions do not accept video canvas conversion flags')
            result=state.jobs['job-one']['result'];self.assertTrue(result['review_required'])
            self.assertEqual(result['sound_recommendations']['status'],'ready')
            self.assertEqual(result['xml_files'],[])

    def test_manual_command_uses_recommendation_worker_and_bound_context(self):
        from hinglish_app.panel_sound_worker import command
        args=command('root','timeline.xml','exact-script.txt','creator.json','job-one','medium')
        self.assertEqual(args[:2],['-m','hinglish_app.panel_sound_worker'])
        self.assertIn('creator.json',args);self.assertIn('job-one',args)
        self.assertNotIn('hinglish_sound',args)

    def test_actual_adapter_receives_exact_script_profile_and_suite_resource_lease(self):
        from hinglish_app.panel_sound_worker import execute
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder).resolve();work=root/'cache/job';work.mkdir(parents=True)
            source=work/'timeline.xml';source.write_text('fixture timeline')
            script=work/'script.txt';script.write_text('Exact Hindi / English 14 words.\nKeep this line.',encoding='utf-8')
            profile={'profile':'gaming','feedback':'Full saved owner guidance','extra':{'keep':['all']}}
            creator=work/'creator.json';creator.write_text(json.dumps(profile),encoding='utf-8')
            output=root/'output/sound-recommendations/real-adapter-result';output.mkdir(parents=True)
            manifest=output/'manifest.json';manifest.write_text('{}')
            result={'status':'ready','folder':str(output),'manifest':str(manifest),'notice':'Ready for review','rendered':False}
            with patch('hinglish_sound.recommendation_pipeline.run',return_value=result) as run, \
                 patch('hinglish_cut.model_preferences.preferences',return_value={'planning_model':'local-plan','vision_model':'local-vision','embedding_model':'local-embed'}):
                page=execute(root,source,script,creator,'owned-lease','medium')
            call=run.call_args
            self.assertEqual(call.args[2],script.read_text('utf-8'));self.assertEqual(call.args[3],profile)
            self.assertTrue(call.kwargs['execute_local']);self.assertEqual(call.kwargs['resource_lease'],'owned-lease')
            self.assertEqual(call.kwargs['expected_models']['vision'],'local-vision')
            self.assertEqual(page,output/'report.html');self.assertTrue(page.is_file())

    def test_missing_script_stops_before_any_local_model_call(self):
        from hinglish_app.panel_sound_worker import execute
        with tempfile.TemporaryDirectory(dir='cache') as folder:
            root=Path(folder);script=root/'script.txt';script.write_text(' ');creator=root/'creator.json';creator.write_text('{}')
            with patch('hinglish_sound.recommendation_pipeline.run') as run:
                with self.assertRaisesRegex(ValueError,'script'):execute(root,'source.mp4',script,creator,'lease','medium')
            run.assert_not_called()
