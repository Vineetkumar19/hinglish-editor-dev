import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from tests.test_voiceover import recording


class VoiceoverHTTPTests(unittest.TestCase):
    def test_real_server_profile_job_download_auth_and_ui(self):
        from hinglish_app.server import serve
        from hinglish_voice.service import service
        Path('work/voiceover-tests').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir='work/voiceover-tests') as folder:
            root=Path(folder).resolve()
            server,state=serve(root,0,publish_bridge=False)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{state.port}'
            def call(path,body=None,token=True):
                headers={'Content-Type':'application/json'}
                if token:headers['X-Hinglish-Token']=state.token
                req=Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
                with urlopen(req,timeout=10) as r:return r.status,json.loads(r.read())
            try:
                with self.assertRaises(HTTPError) as denied:call('/api/voiceover/status',token=False)
                self.assertEqual(denied.exception.code,403)
                with self.assertRaises(HTTPError):call('/api/voiceover/voices',dict(name='denied'),token=False)
                req=Request(base+'/api/voiceover/upload?name=mine.wav',data=recording(),headers={'X-Hinglish-Token':state.token})
                with urlopen(req) as response:upload=json.loads(response.read())
                _,voice=call('/api/voiceover/voices',dict(upload_id=upload['id'],name='Mine',transcript='My own sample.',consent=True))
                local=service(root)
                with patch.object(local,'_launch'):
                    _,job=call('/api/voiceover/start',dict(voice_id=voice['id'],script='Exact script 123.'))
                _,saved=call('/api/voiceover/job?id='+job['id'])
                self.assertEqual(saved['script'],'Exact script 123.')
                with self.assertRaises(HTTPError):call('/api/voiceover/file?id='+job['id']+'&format=mp3')
                with self.assertRaises(HTTPError):call('/api/voiceover/job?id=..%2Fsecret')
                with self.assertRaises(HTTPError):call('/api/voiceover/start',dict(voice_id=voice['id'],script=''))
                _,status=call('/api/voiceover/status')
                self.assertEqual(status['voices'][0]['id'],voice['id'])
                self.assertEqual(len(status['jobs']),1)
                # Actual encoded audio is streamed by the real server only after completion.
                import soundfile as sf
                import numpy as np
                from hinglish_voice.audio import mp3
                output=local.base/job['id']
                sf.write(output/'narration.wav',np.sin(np.arange(24000)*.1)*.2,24000)
                mp3(output/'narration.wav',output/'narration.mp3')
                local._update(job['id'],status='complete',duration=1)
                for kind in ('mp3','wav'):
                    link=base+'/api/voiceover/file?id='+job['id']+'&format='+kind+'&download=1&token='+state.token
                    with urlopen(link) as response:
                        self.assertIn('attachment',response.headers['Content-Disposition'])
                        self.assertEqual(response.headers['Cache-Control'],'no-store')
                        self.assertEqual(response.read(),(output/('narration.'+kind)).read_bytes())
                with self.assertRaises(HTTPError):
                    urlopen(base+'/api/voiceover/file?id='+job['id']+'&format=mp3&token=wrong')
                # Static files are always served from the application, not the data root.
                with urlopen(base+'/voiceover.html') as response:
                    page=response.read().decode()
                    self.assertIn('Generate voiceover',page)
                    self.assertNotIn('__APP_TOKEN__',page)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
