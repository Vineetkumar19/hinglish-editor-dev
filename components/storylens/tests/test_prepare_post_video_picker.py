"""Read-only local chooser tests; no copies, generation or posting."""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from hinglish_publish.prepare_post_picker import browse,native_pick,_native_lock


class VideoPickerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'Videos').mkdir()
        (self.root / 'Videos' / 'Clip 2.mp4').write_bytes(b'original')
        (self.root / 'Videos' / 'Clip 10.mp4').write_bytes(b'original ten')
        (self.root / 'Videos' / 'notes.txt').write_text('not a video')

    def test_browses_folders_and_returns_exact_video_paths_in_natural_order(self):
        top = browse(self.root)
        self.assertEqual(top['folders'][0]['path'], str((self.root / 'Videos').resolve()))
        listing = browse(top['folders'][0]['path'])
        self.assertEqual([v['name'] for v in listing['videos']], ['Clip 2.mp4', 'Clip 10.mp4'])
        self.assertEqual(listing['parent'], str(self.root.resolve()))

    def test_file_selection_and_search_preserve_the_original_bytes(self):
        path = self.root / 'Videos' / 'Clip 2.mp4'
        listing = browse(path, query='Clip 2')
        self.assertEqual(listing['path'], str(path.parent.resolve()))
        self.assertEqual(listing['videos'][0]['path'], str(path.resolve()))
        self.assertEqual(path.read_bytes(), b'original')

    def test_missing_folder_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, 'Check'):
            browse(self.root / 'missing')

    def test_native_selection_uses_direct_windows_dialog_and_keeps_media(self):
        path=self.root/'Videos'/'Clip 2.mp4'
        with patch('hinglish_publish.prepare_post_picker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=str(path),stderr='')) as run:
            self.assertEqual(native_pick(self.root,str(path)),str(path.resolve()))
        command=run.call_args.args[0]
        self.assertIn('hinglish_publish.prepare_post_picker_native',command)
        self.assertNotIn('powershell.exe',' '.join(command).lower())
        self.assertEqual(path.read_bytes(),b'original');self.assertFalse(_native_lock.locked())

    def test_cancellation_and_failure_always_release_chooser(self):
        with patch('hinglish_publish.prepare_post_picker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')):
            self.assertEqual(native_pick(self.root),'')
        self.assertFalse(_native_lock.locked())
        with patch('hinglish_publish.prepare_post_picker.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='Native COM diagnostics')):
            with self.assertRaisesRegex(ValueError,'chooser stopped'):native_pick(self.root)
        self.assertFalse(_native_lock.locked())
        with patch('hinglish_publish.prepare_post_picker.subprocess.run',side_effect=OSError('cannot launch')):
            with self.assertRaises(OSError):native_pick(self.root)
        self.assertFalse(_native_lock.locked())

    def test_thumbnail_chooser_accepts_only_one_supported_image(self):
        image=self.root/'chosen.jpg';image.write_bytes(b'image')
        with patch('hinglish_publish.prepare_post_picker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=str(image),stderr='')) as run:
            self.assertEqual(native_pick(self.root,kind='thumbnail'),str(image.resolve()))
        self.assertIn('thumbnail',run.call_args.args[0])
        with patch('hinglish_publish.prepare_post_picker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=str(self.root/'Videos'/'Clip 2.mp4'),stderr='')):
            with self.assertRaisesRegex(ValueError,'image'):native_pick(self.root,kind='thumbnail')
        self.assertFalse(_native_lock.locked())


if __name__ == '__main__': unittest.main()
