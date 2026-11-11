"""Queue, section and automatic-save contracts (no remote/model calls)."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_app.downloader import DownloadService, validate_request


class DownloadQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.root = Path(self.temp.name)
        self.service = DownloadService(self.root)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def wait(self, id):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            job = self.service.snapshot(id)
            if job['status'] not in ('queued', 'running'):
                return job
            time.sleep(.01)
        self.fail('queue did not finish')

    def test_enqueue_while_running_fifo_failure_does_not_block_next(self):
        entered = threading.Event(); release = threading.Event(); order = []
        def run(id):
            order.append(id)
            self.service._save(id, status='running')
            if len(order) == 1:
                entered.set(); release.wait(3)
            self.service._save(id, status='failed' if len(order) == 2 else 'complete')
        with patch.object(self.service, '_run', side_effect=run):
            first = self.service.start({'url': 'https://youtu.be/one'})
            self.assertTrue(entered.wait(1))
            second = self.service.start({'url': 'https://youtu.be/two'})
            third = self.service.start({'url': 'https://www.facebook.com/reel/123'})
            self.assertEqual(self.service.snapshot(second['id'])['status'], 'queued')
            release.set(); self.wait(third['id'])
        self.assertEqual(order, [first['id'], second['id'], third['id']])
        self.assertEqual(self.service.snapshot(second['id'])['status'], 'failed')

    def test_submission_id_is_idempotent_and_cannot_bind_another_link(self):
        with patch.object(self.service, '_run'):
            payload = {'url': 'https://youtu.be/one', 'submission_id': 'same-click-1'}
            first = self.service.start(payload)
            self.assertEqual(self.service.start(payload)['id'], first['id'])
            with self.assertRaises(ValueError):
                self.service.start({**payload, 'url': 'https://youtu.be/two'})

    def test_invalid_batch_queues_nothing(self):
        with self.assertRaises(ValueError):
            self.service.enqueue({'requests':[{'url':'https://youtu.be/one'}, {'url':'https://localhost/no'}]})
        self.assertEqual(self.service.history(),[])

    def test_conflicting_batch_identities_do_not_partially_start(self):
        with self.assertRaises(ValueError):
            self.service.enqueue({'requests':[{'url':'https://youtu.be/one','submission_id':'same'},
                                              {'url':'https://youtu.be/two','submission_id':'same'}]})
        self.assertEqual(self.service.history(),[])

    def test_old_finished_history_does_not_clutter_new_queue(self):
        with patch.object(self.service,'_run'):
            job=self.service.start({'url':'https://youtu.be/old'})
            self.service._save(job['id'],status='complete',queue_version=None)
        self.assertEqual(self.service.queue(),[])
        self.assertEqual(len(self.service.history()),1)

    def test_cancel_waiting_entry_is_immediate(self):
        gate=threading.Event()
        with patch.object(self.service, '_run', side_effect=lambda id:gate.wait(3)):
            self.service.start({'url': 'https://youtu.be/running'})
            job = self.service.start({'url': 'https://youtu.be/one'})
            self.assertEqual(self.service.cancel(job['id'])['status'], 'cancelled')
            gate.set()

    def test_saved_destination_is_reused_but_each_job_keeps_its_destination(self):
        one = self.root / 'one'; one.mkdir()
        two = self.root / 'two'; two.mkdir()
        self.service.settings({'destination': str(one)})
        with patch.object(self.service, '_run'):
            first = self.service.start({'url': 'https://youtu.be/one'})
            self.service.settings({'destination': str(two)})
            second = self.service.start({'url': 'https://youtu.be/two'})
        self.assertEqual(first['request']['destination'], str(one.resolve()))
        self.assertEqual(second['request']['destination'], str(two.resolve()))

    def test_automatic_save_copies_bytes_without_overwriting_existing_file(self):
        target = self.root / 'downloads'; target.mkdir()
        source = self.root / 'source.mp4'; source.write_bytes(b'original media')
        with patch.object(self.service, '_run'):
            job = self.service.start({'url': 'https://youtu.be/a', 'destination': str(target)})
        path = self.service.save_asset(job['id'], source, 'A title', 'video', threading.Event())
        self.assertEqual(path.read_bytes(), source.read_bytes())
        self.assertEqual(path.parent, target)
        self.assertEqual(self.service.save_asset(job['id'], source, 'A title', 'video', threading.Event()), path)
        self.assertEqual(len(list(target.glob('*.mp4'))), 1)

    def test_restart_preserves_pending_queue_for_explicit_resume(self):
        with patch.object(self.service, '_run'):
            job = self.service.start({'url': 'https://youtu.be/one'})
        other = DownloadService(self.root)
        try:
            self.assertEqual(other.snapshot(job['id'])['status'], 'interrupted')
            self.assertEqual(other.history()[0]['id'], job['id'])
        finally:
            other.close()


class DownloadSectionTests(unittest.TestCase):
    def test_section_uses_remote_input_seek_and_only_selected_duration(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp') as temp:
            service = DownloadService(temp)
            info = {'duration':3000,'title':'Long video','url':'https://media.example/video.mp4',
                    'vcodec':'h264','acodec':'aac','http_headers':{'User-Agent':'test'}}
            try:
                def ffmpeg(args, event, **kwargs):
                    self.assertEqual(args[args.index('-ss')+1], '170.0')
                    self.assertLess(args.index('-ss'),args.index('-i'))
                    self.assertEqual(args[args.index('-t')+1], '20.0')
                    Path(args[-1]).write_bytes(b'only requested section')
                request = validate_request({'url':'https://youtu.be/a','start_time':'2:50','end_time':'3:10'})
                with patch.object(service,'_ffmpeg',side_effect=ffmpeg):
                    path = service._section_transfer(request,info,Path(temp),lambda *a:None,threading.Event(),lambda url:None)
                self.assertTrue(path.is_file())
                with self.assertRaises(ValueError):
                    service._section_transfer(request,{**info,'duration':175},Path(temp),lambda *a:None,threading.Event(),lambda url:None)
            finally: service.close()

    def test_exact_timestamp_fields_and_youtube_only(self):
        request = validate_request({'url': 'https://youtu.be/a', 'start_time': '2:50', 'end_time': '3:10'})
        self.assertEqual(request['section'], {'start': 170.0, 'end': 190.0})
        for extra in ({'start_time': '2:50'}, {'start_time': '3:10', 'end_time': '2:50'},
                      {'start_time': '1:99', 'end_time': '3:10'}, {'start_time': True, 'end_time': 30},
                      {'start_time': 'nan', 'end_time': 'inf'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_request({'url': 'https://youtu.be/a', **extra})
        with self.assertRaises(ValueError):
            validate_request({'url': 'https://instagram.com/reel/a', 'start_time': '0:10', 'end_time': '0:20'})

    def test_facebook_single_videos_and_shortlinks(self):
        for url in ('https://www.facebook.com/watch/?v=123', 'https://fb.watch/abc/',
                    'https://www.facebook.com/user/videos/123/', 'https://www.facebook.com/share/r/abc/'):
            self.assertEqual(validate_request({'url': url})['platform'], 'facebook')
        with self.assertRaises(ValueError):
            validate_request({'url': 'https://facebook.com/someone/'})


if __name__ == '__main__':
    unittest.main()
