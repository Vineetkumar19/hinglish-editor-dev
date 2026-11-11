import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class SoundOutputHTTPTests(unittest.TestCase):
    def test_generated_sound_report_and_range_audio_are_scoped(self):
        from hinglish_app.server import serve
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            output=root/'output/sound/session'; output.mkdir(parents=True)
            (output/'report.html').write_text('<b>Sound result</b>')
            (output/'preview.mp4').write_bytes(b'0123456789')
            (output/'layer.wav').write_bytes(b'abcdefghij')
            (output/'no.py').write_text('not media')
            (root/'private.txt').write_text('private')
            server,state=serve(root,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{state.port}'
            try:
                with urlopen(base+'/sound-output/session/report.html') as r:
                    self.assertIn(b'Sound result',r.read())
                for filename in ('preview.mp4','layer.wav'):
                    with urlopen(Request(base+'/sound-output/session/'+filename,headers={'Range':'bytes=2-5'})) as r:
                        self.assertEqual(r.status,206)
                        self.assertEqual(len(r.read()),4)
                for path in ('/sound-output/%2e%2e/%2e%2e/private.txt','/sound-output/session/no.py'):
                    with self.assertRaises(HTTPError):urlopen(base+path)
                with self.assertRaises(HTTPError) as denied:
                    urlopen(Request(base+'/api/bridge',headers={'Origin':'null'}))
                self.assertEqual(denied.exception.code,403)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
