import json
from pathlib import Path
import tempfile
import unittest

from hinglish_app.assistant_visuals_source import catalog, choose, requested


class Brain:
    def __init__(self, selected):
        self.selected = selected

    def json(self, system, data, schema, **kwargs):
        self.data = data
        return {'id': self.selected, 'reason': 'Named cricket player in the saved transcript.'}


class SourceSelectionTests(unittest.TestCase):
    def test_only_actual_files_are_selectable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'real.mp4').write_bytes(b'video')
            (folder / 'real.txt').write_text('Gautam Gambhir and KKR', encoding='utf-8')
            (folder / 'library.json').write_text(json.dumps({'shorts': [
                {'file': 'missing.mp4', 'title': 'Invented'},
                {'file': 'real.mp4', 'title': 'KKR', 'duration': 14}]}), encoding='utf-8')
            rows = catalog(folder)
            self.assertEqual([r['name'] for r in rows], ['real.mp4'])
            brain = Brain(0)
            path, receipt = choose(folder, 'Choose one cricket video for Smart Visuals from ' + str(folder), print,
                                   {'all_saved_guidance': 'keep this'}, brain=brain)
            self.assertEqual(path, folder / 'real.mp4')
            self.assertEqual(brain.data['creator_profile'], {'all_saved_guidance': 'keep this'})
            self.assertEqual(receipt['evidence']['transcript_excerpt'], 'Gautam Gambhir and KKR')
            with self.assertRaisesRegex(ValueError, 'could not find'):
                choose(folder, 'Choose one for Smart Visuals from ' + str(folder), print, {}, brain=Brain(20))

    def test_selection_is_narrowly_requested(self):
        self.assertTrue(requested('Choose one cricket video for Smart Visuals'))
        self.assertFalse(requested('Choose one video to upload'))
        self.assertFalse(requested('Smart Visuals on every video'))

    def test_second_window_history_does_not_overwrite_running_owner(self):
        from hinglish_app.assistant import Assistant
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = {'id': '1234567890abcdef', 'status': 'running', 'job_id': 'active-job'}
            path = folder / (source['id'] + '.json')
            path.write_text(json.dumps(source), encoding='utf-8')
            reader = Assistant.__new__(Assistant)
            reader.folder, reader.sessions = folder, {}
            self.assertEqual(reader._get(source['id'])['status'], 'interrupted')
            self.assertEqual(json.loads(path.read_text('utf-8')), source)


if __name__ == '__main__':
    unittest.main()
