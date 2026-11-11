import hashlib
import importlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from tools import ranged_download


DATA = bytes(range(256)) * 100


class RangeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        start, end = map(int, self.headers['Range'].removeprefix('bytes=').split('-'))
        self.send_response(206)
        self.send_header('Content-Range', f'bytes {start}-{end}/{len(DATA)}')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        self.wfile.write(DATA[start:end + 1])


class RangedDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ranged_download.ROOT / 'tmp')
        self.path = Path(self.temp.name).resolve() / 'fixture.incomplete'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), RangeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/fixture'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def test_resumes_unaligned_prefix_and_verifies_final_hash(self):
        prefix = 5701
        self.path.write_bytes(DATA[:prefix])
        with self.path.open('r+b') as stream, patch.object(ranged_download, 'CHUNK', 4096):
            ranged_download.ranged_get(self.url, stream, len(DATA), resume=prefix, workers=2,
                                       expected_sha256=hashlib.sha256(DATA).hexdigest())
        self.assertEqual(self.path.read_bytes(), DATA)

    def test_invalid_checksum_does_not_leave_a_complete_looking_file(self):
        with self.path.open('w+b') as stream, patch.object(ranged_download, 'CHUNK', 4096):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                ranged_download.ranged_get(self.url, stream, len(DATA), workers=2, expected_sha256='0' * 64)
        self.assertEqual(self.path.stat().st_size, 0)

    def test_preserves_partial_bytes_inside_a_range_after_a_reset(self):
        parts = self.path.with_name(self.path.name + '.ranges')
        parts.mkdir()
        (parts/'part-0-4096.tmp').write_bytes(DATA[:1733])
        with self.path.open('w+b') as stream, patch.object(ranged_download, 'CHUNK', 4096):
            ranged_download.ranged_get(self.url, stream, len(DATA), workers=2,
                                      expected_sha256=hashlib.sha256(DATA).hexdigest())
        self.assertEqual(self.path.read_bytes(), DATA)

    def test_small_lfs_tokenizer_uses_ranges_and_its_published_hash(self):
        module = importlib.import_module('huggingface_hub.file_download')
        digest = 'a' * 64
        temporary = SimpleNamespace(name=str(self.path.parent / ('opaque=.' + digest + '.incomplete')))
        original = Mock()
        with patch.object(module, 'http_get', original), patch.object(ranged_download, 'ranged_get') as ranges:
            ranged_download.patch_huggingface()
            module.http_get('https://example.test/tokenizer', temporary, expected_size=16*1024*1024, resume_size=17)
            original.assert_not_called()
            self.assertEqual(ranges.call_args.kwargs['expected_sha256'], digest)
            self.assertEqual(ranges.call_args.args[3], 17)

    def test_small_git_metadata_keeps_the_normal_download_path(self):
        module = importlib.import_module('huggingface_hub.file_download')
        temporary = SimpleNamespace(name=str(self.path.parent / ('b'*40 + '.incomplete')))
        original = Mock()
        with patch.object(module, 'http_get', original), patch.object(ranged_download, 'ranged_get') as ranges:
            ranged_download.patch_huggingface()
            module.http_get('https://example.test/metadata', temporary, expected_size=2*1024*1024)
            original.assert_called_once()
            ranges.assert_not_called()


if __name__ == '__main__':
    unittest.main()
