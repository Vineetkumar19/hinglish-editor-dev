import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hinglish_app.server import serve


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / 'output').mkdir()
        self.server, self.state = serve(self.root, 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, body=None, token=True):
        headers = {}
        if token:
            headers['X-Hinglish-Token'] = self.state.token
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        request = Request(f'http://127.0.0.1:{self.port}{path}', data=data, headers=headers)
        with urlopen(request) as response:
            return response.status, json.load(response)

    def test_dashboard_and_health_are_available(self):
        with urlopen(f'http://127.0.0.1:{self.port}/') as response:
            page = response.read().decode()
        self.assertIn('Smart Clean', page)
        self.assertNotIn('__APP_TOKEN__', page)
        self.assertIn('data-device="cpu"', page)
        (self.root / 'config.models.local.json').write_text('{"device":"cuda"}')
        with urlopen(f'http://127.0.0.1:{self.port}/') as response:
            self.assertIn('data-device="cuda"', response.read().decode())
        status, health = self.request('/api/health', token=False)
        self.assertEqual((status, health['ok']), (200, True))

    def test_editing_actions_require_local_token(self):
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/jobs', {'mode': 'clean'}, token=False)
        self.assertEqual(caught.exception.code, 403)

    def test_unexpected_service_exception_is_readable_and_server_stays_available(self):
        with patch.object(self.state,'aigen_status',side_effect=RuntimeError('internal renderer detail')):
            with self.assertRaises(HTTPError) as caught:self.request('/api/aigen/status')
        self.assertEqual(caught.exception.code,500)
        result=json.load(caught.exception)
        self.assertEqual(result['error_code'],'task_failed')
        self.assertIn('retrying',result['error']);self.assertIn('internal renderer detail',result['error_details'])
        self.assertTrue(self.request('/api/health')[1]['ok'])

    def test_all_pages_use_the_same_installed_error_catalog(self):
        with urlopen(f'http://127.0.0.1:{self.port}/feedback.js') as response:script=response.read().decode('utf-8')
        self.assertTrue(script.startswith('window.storylensErrorCatalog='))
        self.assertIn('transcript_unreliable',script)

    def test_missing_page_offers_a_way_back_and_missing_api_returns_json(self):
        with self.assertRaises(HTTPError) as caught:self.request('/api/not-a-real-feature')
        self.assertEqual(json.load(caught.exception)['error_code'],'not_found')
        with self.assertRaises(HTTPError) as caught:urlopen(f'http://127.0.0.1:{self.port}/missing-page.html')
        page=caught.exception.read().decode('utf-8')
        self.assertIn('Back to Storylens',page);self.assertIn('Technical details',page)

    def test_unrelated_uxp_plugin_cannot_read_the_bridge_token(self):
        request=Request(f'http://127.0.0.1:{self.port}/api/bridge',headers={'Origin':'uxp://unrelated.plugin'})
        with self.assertRaises(HTTPError) as caught:urlopen(request)
        self.assertEqual(caught.exception.code,403)

    def test_json_body_size_and_shape_are_bounded(self):
        for length,content,expected in ((str(1024**2+1),b'',413),('-1',b'',413),('2',b'[]',400)):
            request=Request(f'http://127.0.0.1:{self.port}/api/jobs',data=content,method='POST',
                            headers={'X-Hinglish-Token':self.state.token,'Content-Type':'application/json','Content-Length':length})
            with self.assertRaises(HTTPError) as caught:urlopen(request)
            self.assertEqual(caught.exception.code,expected)

    def test_creator_feedback_roundtrip_and_revocable_memory(self):
        status, saved = self.request('/api/publisher/feedback', {
            'scope': 'title', 'want': 'Short Roman Hinglish titles', 'avoid': 'Hype'})
        self.assertEqual(status, 200)
        status, state = self.request('/api/publisher')
        self.assertEqual(state['memory'][0]['id'], saved['id'])
        self.assertTrue(state['memory'][0]['active'])
        self.request('/api/publisher/memory-toggle', {'id': saved['id'], 'active': False})
        self.assertFalse(self.request('/api/publisher')[1]['memory'][0]['active'])
        with self.assertRaises(HTTPError):
            self.request('/api/publisher/feedback', {'scope': 'title', 'want': 'No hype'}, token=False)

    def test_publisher_page_and_protected_queue(self):
        with urlopen(f'http://127.0.0.1:{self.port}/publisher.html') as response:
            page = response.read().decode()
        self.assertIn('Publishing Studio', page)
        self.assertNotIn('__APP_TOKEN__', page)
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/publisher', token=False)
        self.assertEqual(caught.exception.code, 403)
        status, state = self.request('/api/publisher')
        self.assertEqual(status, 200)
        self.assertFalse(state['settings']['enabled'])
        self.assertEqual(state['settings']['daily_time'], '19:00')
        self.assertEqual(state['jobs'], [])
        status, folders = self.request('/api/publisher/folders', {})
        self.assertEqual(status, 200)
        self.assertTrue(Path(folders['long-youtube']).is_dir())

    def test_folder_picker_endpoint_returns_the_selected_path(self):
        selected = str(self.root / 'videos')
        with patch.object(self.state, 'pick', return_value=selected):
            status, result = self.request('/api/pick?kind=folder')
        self.assertEqual(status, 200)
        self.assertEqual(result['path'], selected)

    def test_picker_error_is_returned_as_json_instead_of_dropping_fetch(self):
        with patch.object(self.state, 'pick', side_effect=RuntimeError('picker failed')):
            with self.assertRaises(HTTPError) as caught:
                self.request('/api/pick?kind=folder')
        self.assertEqual(caught.exception.code, 400)
        self.assertIn('picker failed', caught.exception.read().decode('utf-8'))

    def test_browser_can_add_a_local_video_without_windows_picker(self):
        content = b'local video payload'
        request = Request(
            f'http://127.0.0.1:{self.port}/api/upload?batch=test-batch&name=take-01.mp4',
            data=content,
            headers={
                'X-Hinglish-Token': self.state.token,
                'Content-Type': 'application/octet-stream',
            },
            method='POST',
        )
        with urlopen(request) as response:
            result = json.load(response)
        saved = Path(result['path'])
        self.assertTrue(saved.is_file())
        self.assertEqual(saved.read_bytes(), content)
        self.assertTrue(saved.is_relative_to(self.root / 'cache' / 'app' / 'uploads'))

    def test_browser_upload_rejects_non_video_files(self):
        request = Request(
            f'http://127.0.0.1:{self.port}/api/upload?batch=test-batch&name=notes.exe',
            data=b'not a video',
            headers={'X-Hinglish-Token': self.state.token},
            method='POST',
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 400)

    def test_resolve_import_accepts_only_generated_xml(self):
        outside = self.root / 'outside.xml'
        outside.write_text('<xmeml/>')
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/import-resolve', {'xml_files': [str(outside)]})
        self.assertEqual(caught.exception.code, 400)

    def test_resolve_import_uses_open_project_adapter(self):
        xml = self.root / 'output' / 'timeline.xml'
        xml.write_text('<xmeml/>')
        with patch('hinglish_app.resolve_adapter.import_timelines', return_value=['Hinglish Edit']) as importer:
            status, result = self.request('/api/import-resolve', {'xml_files': [str(xml)]})
        self.assertEqual(status, 200)
        self.assertEqual(result['timelines'], ['Hinglish Edit'])
        importer.assert_called_once_with([str(xml.resolve())])

    def test_caption_editor_rebuilds_only_generated_projects(self):
        project = self.root / 'output' / 'captions' / 'run' / 'caption-project.json'
        project.parent.mkdir(parents=True)
        project.write_text('{}')
        expected = {'report': str(project.parent / 'report.html'), 'cues': 2}
        with patch('hinglish_captions.project.rebuild_project', return_value=expected) as rebuild:
            status, result = self.request('/api/captions/rebuild', {
                'project_path': str(project), 'texts': ['fixed words'], 'style': 'soft_focus'
            })
        self.assertEqual(status, 200)
        self.assertEqual(result['cues'], 2)
        rebuild.assert_called_once()

    def test_broll_settings_save_keys_but_never_return_them(self):
        status, shown = self.request('/api/broll/settings', {'pexels_key': 'secret-key-1234', 'use_pixabay': False})
        self.assertEqual(status, 200)
        self.assertNotIn('secret-key-1234', json.dumps(shown))
        status, again = self.request('/api/broll/settings')
        self.assertEqual(again['pexels_key'], shown['pexels_key'])
        self.assertFalse(again['use_pixabay'])
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/broll/settings', token=False)
        self.assertEqual(caught.exception.code, 403)

    def test_broll_rebuild_only_accepts_generated_projects(self):
        outside = self.root / 'broll-project.json'
        outside.write_text('{}')
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/broll/rebuild', {'project_path': str(outside), 'choices': {}})
        self.assertEqual(caught.exception.code, 400)
        project = self.root / 'output' / 'broll' / 'run' / '001-a' / 'broll-project.json'
        project.parent.mkdir(parents=True)
        project.write_text('{}')
        with patch('hinglish_broll.pipeline.rebuild_project', return_value={'xml_files': [], 'filled': 3}) as rebuild:
            status, result = self.request('/api/broll/rebuild', {'project_path': str(project), 'choices': {'0': ''}})
        self.assertEqual((status, result['filled']), (200, 3))
        rebuild.assert_called_once_with(project.resolve(), {'0': ''})

    def test_broll_job_uses_exported_timeline_xml(self):
        timeline = self.root / 'sequence.xml'
        timeline.write_text('<xmeml/>')
        started = threading.Event()
        with patch.object(self.state, '_run_job', side_effect=lambda *a: started.set()) as runner:
            status, job = self.request('/api/jobs', {'mode': 'broll', 'timeline_xml': str(timeline), 'density': 'high'})
            self.assertTrue(started.wait(5))
        self.assertEqual((status, job['mode']), (202, 'broll'))
        args = runner.call_args.args
        self.assertEqual(args[3], timeline.resolve())
        self.assertEqual(args[1]['input_path'], str(timeline.resolve()))
        with self.assertRaises(HTTPError):
            self.request('/api/jobs', {'mode': 'broll', 'timeline_xml': str(self.root / 'missing.xml')})

    def test_zoom_job_passes_style_choices_to_the_engine(self):
        timeline = self.root / 'sequence.xml'
        timeline.write_text('<xmeml/>')
        (self.root / 'output' / 'zoom' / 'r' / '001-a').mkdir(parents=True)
        page = self.root / 'output' / 'zoom' / 'r' / '001-a' / 'report.html'
        page.write_text('ok')
        launched = {}

        class FakeProcess:
            def __init__(self, command, **_):
                launched['command'] = command
                self.stdout = iter([f'Results: {page}\n'])
            def wait(self):
                return 0
        with patch('hinglish_app.server.subprocess.Popen', FakeProcess):
            status, job = self.request('/api/jobs', {'mode': 'zoom', 'timeline_xml': str(timeline),
                                                     'zoom_style': 'punch', 'zoom_strength': 'strong',
                                                     'zoom_frequency': 'high', 'zoom_face': False})
            for _ in range(50):
                if self.state.snapshot(job['id'])['status'] in ('complete', 'failed'): break
                threading.Event().wait(.05)
        command = launched['command']
        self.assertIn('hinglish_zoom', command)
        for flag, value in (('--style', 'punch'), ('--strength', 'strong'), ('--frequency', 'high')):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn('--no-face', command)
        self.assertNotIn('--no-jump-cuts', command)
        self.assertNotIn('--format', command)
        self.assertEqual(self.state.snapshot(job['id'])['status'], 'complete')

    def test_short_form_uses_requested_count_duration_and_optional_script_without_channel_overrides(self):
        video=self.root/'long-video.mp4';video.write_bytes(b'command routing fixture')
        page=self.root/'output'/'shorts'/'review'/'report.html'
        page.parent.mkdir(parents=True);page.write_text('ok')
        launched={}
        class FakeProcess:
            def __init__(self,command,**_):
                launched['command']=command;self.stdout=iter([f'Results: {page}\n'])
            def wait(self):return 0
        reference='Aaj hum Mumbai ki kahani samjhenge. Hindi and English context.'
        with patch('hinglish_app.server.subprocess.Popen',FakeProcess):
            _,job=self.request('/api/jobs',{'mode':'shorts','input_path':str(video),'script':reference,
                'shorts_count':'3','shorts_min':40,'shorts_max':45,'shorts_look':'template',
                'shorts_pieces':'2','shorts_brain':'auto','shorts_captions':True})
            for _ in range(50):
                if self.state.snapshot(job['id'])['status'] in ('complete','failed'):break
                threading.Event().wait(.05)
        command=launched['command']
        for flag,value in (('--count','3'),('--min','40'),('--max','45'),('--pieces','2')):
            self.assertEqual(command[command.index(flag)+1],value)
        self.assertEqual(Path(command[command.index('--script')+1]).read_text('utf-8'),reference)
        self.assertIn('--captions',command)
        self.assertFalse(any(flag in command for flag in ('--title','--handle','--cta','--start','--end')))
        self.assertEqual(self.state.snapshot(job['id'])['status'],'complete')

    def test_broll_script_is_passed_as_reference_context_with_five_video_choices(self):
        timeline=self.root/'sequence.xml';timeline.write_text('<xmeml/>')
        page=self.root/'output'/'broll'/'review'/'report.html'
        page.parent.mkdir(parents=True);page.write_text('ok')
        launched={}
        class FakeProcess:
            def __init__(self,command,**_):
                launched['command']=command;self.stdout=iter([f'Results: {page}\n'])
            def wait(self):return 0
        reference='Mumbai ki streets at night. Then we visit a quiet cafe.'
        with patch('hinglish_app.server.subprocess.Popen',FakeProcess):
            _,job=self.request('/api/jobs',{'mode':'broll','timeline_xml':str(timeline),
                'script':reference,'broll_review_options':True,'broll_options_per_moment':5})
            for _ in range(50):
                if self.state.snapshot(job['id'])['status'] in ('complete','failed'):break
                threading.Event().wait(.05)
        command=launched['command']
        self.assertIn('--review-options',command)
        self.assertEqual(command[command.index('--options-per-moment')+1],'5')
        self.assertEqual(Path(command[command.index('--reference-script')+1]).read_text('utf-8'),reference)
        self.assertNotIn('--brief',command);self.assertNotIn('--black-background',command)
        self.assertEqual(self.state.snapshot(job['id'])['status'],'complete')

    def test_visuals_job_passes_choices_and_rebuild_only_accepts_generated_projects(self):
        timeline = self.root / 'sequence.xml'
        timeline.write_text('<xmeml/>')
        page = self.root / 'output' / 'visuals' / 'r' / '001-a' / 'report.html'
        page.parent.mkdir(parents=True)
        page.write_text('ok')
        launched = {}

        class FakeProcess:
            def __init__(self, command, **_):
                launched['command'] = command
                launched['env'] = _.get('env',{})
                self.stdout = iter([f'Results: {page}\n'])
            def wait(self):
                return 0
        with patch('hinglish_app.server.subprocess.Popen', FakeProcess):
            status, job = self.request('/api/jobs', {'mode': 'visuals', 'timeline_xml': str(timeline),
                                                     'visuals_density': 'high', 'visuals_brain': 'local',
                                                     'visuals_popups': False, 'visuals_check': False})
            for _ in range(50):
                if self.state.snapshot(job['id'])['status'] in ('complete', 'failed'): break
                threading.Event().wait(.05)
        command = launched['command']
        self.assertIn('hinglish_visuals', command)
        self.assertEqual(command[command.index('--density') + 1], 'high')
        self.assertEqual(command[command.index('--brain') + 1], 'local')
        self.assertIn('--no-popups', command)
        self.assertEqual(command[command.index('--evaluator') + 1], 'off')
        self.assertEqual(command[command.index('--search-method') + 1],'website')
        self.assertNotIn('hinglish_eval',command)
        lease=json.loads(launched['env'].get('STORYLENS_GPU_CHILD_LEASE','{}'))
        self.assertEqual(Path(lease.get('root','')),self.root.resolve())
        self.assertIsInstance(lease.get('owner_pid'),int)
        self.assertEqual(self.state.snapshot(job['id'])['status'], 'complete')
        outside = self.root / 'visuals-project.json'
        outside.write_text('{}')
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/visuals/rebuild', {'project_path': str(outside), 'choices': {}})
        self.assertEqual(caught.exception.code, 400)
        project = page.parent / 'visuals-project.json'
        project.write_text('{}')
        with patch('hinglish_visuals.pipeline.rebuild_project', return_value={'xml_files': [], 'filled': 2}) as rebuild:
            status, result = self.request('/api/visuals/rebuild', {'project_path': str(project), 'choices': {'1': ''}})
        self.assertEqual((status, result['filled']), (200, 2))
        rebuild.assert_called_once_with(project.resolve(), {'1': ''})


if __name__ == '__main__':
    unittest.main()
