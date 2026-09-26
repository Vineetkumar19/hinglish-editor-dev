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
        self.root = Path(self.temp.name)
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
        status, health = self.request('/api/health', token=False)
        self.assertEqual((status, health['ok']), (200, True))

    def test_editing_actions_require_local_token(self):
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/jobs', {'mode': 'clean'}, token=False)
        self.assertEqual(caught.exception.code, 403)

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


if __name__ == '__main__':
    unittest.main()
