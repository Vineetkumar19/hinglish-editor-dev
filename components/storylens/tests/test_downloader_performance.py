"""Performance regressions without changing source resolution or editor codecs."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_app.downloader import DownloadService, validate_request


class DownloaderPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.root = Path(self.temp.name)
        self.service = DownloadService(self.root)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_transfer_is_bounded_parallel_and_progress_does_not_write_per_packet(self):
        options = {}; updates = []; folder = self.root
        class FakeDL:
            def __init__(self, opts): options.update(opts)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, url, download): return {'title':'Test', 'duration':10}
            def process_ie_result(self, info, download):
                hook = options['progress_hooks'][0]
                for i in range(1000):
                    hook({'status':'downloading','downloaded_bytes':i,'total_bytes':1000})
                hook({'status':'finished','downloaded_bytes':1000,'total_bytes':1000})
                (folder / 'source.mp4').write_bytes(b'media')
                return info
        with patch('yt_dlp.YoutubeDL', FakeDL):
            self.service.transfer(validate_request({'url':'https://youtu.be/test','quality':'2160'}),
                                  folder, lambda *args: updates.append(args), threading.Event())
        self.assertEqual(options['concurrent_fragment_downloads'], 6)
        self.assertFalse(options['skip_unavailable_fragments'])
        self.assertEqual(options['merge_output_format'], 'mp4/mkv')
        self.assertEqual(options['buffersize'], 64 * 1024)
        self.assertTrue(options['continuedl'])
        self.assertLess(len(updates), 10)
        self.assertEqual(updates[-1][1], 85)
        self.assertIn('height<=2160', options['format'])

    def test_cancel_is_checked_even_when_progress_is_throttled(self):
        from yt_dlp.utils import DownloadCancelled
        cancel = threading.Event(); options = {}; folder = self.root
        class FakeDL:
            def __init__(self, opts): options.update(opts)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, url, download): return {'duration':1}
            def process_ie_result(self, info, download):
                hook = options['progress_hooks'][0]
                hook({'status':'downloading','downloaded_bytes':1})
                cancel.set()
                hook({'status':'downloading','downloaded_bytes':2})
        with patch('yt_dlp.YoutubeDL', FakeDL), self.assertRaises(DownloadCancelled):
            self.service.transfer(validate_request({'url':'https://youtu.be/test'}),
                                  folder, lambda *a:None, cancel)

    def test_editor_ready_mp4_is_not_processed_again(self):
        from tests.test_downloader import DownloaderPipelineTests
        # Exercise actual H.264/AAC bytes, probe, XML and final saving through the job.
        case = DownloaderPipelineTests('test_real_media_processing_both_outputs_persistence_and_catalog')
        case.setUp()
        try:
            with patch.object(case.service, 'transfer', side_effect=case.transfer), \
                 patch.object(case.service, '_ffmpeg', side_effect=AssertionError('redundant media pass')):
                job = case.wait(case.service.start({'url':'https://youtu.be/test','mode':'video'}))
            self.assertEqual(job['status'], 'complete', job.get('error'))
            asset = job['result']['assets']['video']
            self.assertEqual(Path(asset['saved_path']).read_bytes(), case.clip.read_bytes())
            self.assertTrue(Path(asset['xml_files'][0]).is_file())
            self.assertIn('download_seconds', job['timings'])
            self.assertIn('total_seconds', job['timings'])
        finally:
            case.tearDown()

    def test_incompatible_codec_still_uses_gpu_conversion(self):
        from hinglish_app.downloader import probe
        from tests.test_downloader import DownloaderPipelineTests
        case = DownloaderPipelineTests('test_real_media_processing_both_outputs_persistence_and_catalog')
        case.setUp()
        try:
            def inspected(path):
                info = probe(path)
                if Path(path).name == 'source.mp4': info['video_codec'] = 'vp9'
                return info
            def convert(args, event, *, progress, duration):
                self.assertGreater(duration, 0)
                progress(.35)
                running = case.service.queue()[0]
                self.assertEqual(running['stage_progress'], 35)
                self.assertTrue(Path(running['source']).is_file())
                import shutil
                self.assertEqual(args[args.index('-c:v') + 1], 'h264_nvenc')
                self.assertNotIn('-vf', args)  # no scaling/lower resolution
                shutil.copy2(case.clip, args[-1])
            with patch.object(case.service, 'transfer', side_effect=case.transfer), \
                 patch('hinglish_app.downloader.probe', side_effect=inspected), \
                 patch('hinglish_cut.compute_policy.heavy_device', return_value='cuda'), \
                 patch.object(case.service, '_ffmpeg', side_effect=convert) as conversion:
                job = case.wait(case.service.start({'url':'https://youtu.be/test','mode':'video'}))
            self.assertEqual(job['status'], 'complete', job.get('error'))
            self.assertEqual(conversion.call_count, 1)
        finally:
            case.tearDown()


if __name__ == '__main__':
    unittest.main()
