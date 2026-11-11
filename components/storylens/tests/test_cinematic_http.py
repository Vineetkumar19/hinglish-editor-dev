import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import Mock
from hinglish_app.server import serve
from tests.test_cinematic import make_shot,make_music,music_plan


class CinematicHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.server,self.state=serve(self.root,0);self.url=f'http://127.0.0.1:{self.state.port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)
        if self.state._cinematic:self.state._cinematic.pool.shutdown(wait=True)
        if self.state._beats:self.state._beats.pool.shutdown(wait=True)
        self.temp.cleanup()
    def request(self,path,body=None,token=True,raw=None):
        headers={'X-Hinglish-Token':self.state.token} if token else {}
        headers['Content-Type']='application/octet-stream' if raw is not None else 'application/json'
        data=raw if raw is not None else json.dumps(body).encode() if body is not None else None
        with urlopen(Request(self.url+path,data=data,headers=headers)) as r:return json.load(r)
    def wait(self,job):
        deadline=time.monotonic()+30
        while job['status'] in ('queued','running') and time.monotonic()<deadline:
            time.sleep(.05);job=self.request('/api/cinematic/jobs/'+job['id'])
        self.assertEqual(job['status'],'complete',job);return job

    def test_music_to_assembly_effects_and_private_playback_through_actual_api(self):
        music=self.root/'music.wav';make_music(music,seconds=4)
        shots=[self.root/f'shot-{i}.mp4' for i in range(2)]
        for i,p in enumerate(shots):make_shot(p,seed=i)
        too_short=self.root/'accidental-short-clip.mp4';make_shot(too_short,seconds=.1)
        # Detect actual audio via the existing beat API, then build an actual MP4.
        beat=self.request('/api/beats/analyze',{'path':str(music),'density':'strong','source_in':.5,'source_out':3.5})
        deadline=time.monotonic()+10
        while beat['status'] in ('queued','running') and time.monotonic()<deadline:
            time.sleep(.03);beat=self.request('/api/beats/jobs/'+beat['id'])
        self.assertEqual(beat['status'],'complete',beat)
        job=self.wait(self.request('/api/cinematic/assemble',{'beat_id':beat['id'],'source_paths':[str(p) for p in [*shots,too_short]],
            'resolution':'test','aspect':'16:9','pace':'balanced','allow_fast':False,'effects':['flash']}))
        self.assertEqual(job['result']['plan']['effects'],[]) # never apply effects during assembly
        self.assertEqual(job['result']['frames'],90)
        self.assertTrue(any('accidental-short' in warning for warning in job['result']['plan']['warnings']))
        preview='/api/cinematic/video/'+job['id']
        with self.assertRaises(HTTPError):urlopen(self.url+preview)
        with urlopen(Request(self.url+preview+'?token='+self.state.token,headers={'Range':'bytes=0-31'})) as r:
            self.assertEqual(r.status,206);self.assertEqual(len(r.read()),32)
        with self.assertRaises(HTTPError):self.request('/api/cinematic/jobs/'+job['id'],token=False)
        clean=Path(job['result']['preview']).read_bytes()
        effected=self.wait(self.request('/api/cinematic/effects',{'id':job['id'],'effects':['flash','punch'],'effect_amount':8}))
        self.assertEqual(effected['base_id'],job['id']);self.assertEqual(Path(job['result']['preview']).read_bytes(),clean)
        manifest=self.request('/api/cinematic/import-manifest',{'host':'premiere'})
        self.assertEqual(manifest['id'],effected['id'])
        self.assertTrue(Path(manifest['result']['xml_files'][0]).is_file())
        from hinglish_cinematic.service import CinematicService
        reloaded=CinematicService(self.root,self.state.beats)
        try:
            self.assertEqual(reloaded.latest()['id'],effected['id'])
            self.assertEqual(reloaded.video(job['id']),Path(job['result']['preview']))
            with self.assertRaises(ValueError):reloaded.snapshot('../../private')
        finally:reloaded.close()

    def test_page_and_routes_require_the_right_token(self):
        with urlopen(self.url+'/cinematic.html') as r:page=r.read().decode()
        self.assertIn('Cinematic Reels',page);self.assertNotIn('__APP_TOKEN__',page)
        for path,body in (('/api/cinematic/assemble',{}),('/api/cinematic/effects',{}),('/api/cinematic/import-manifest',{}),('/api/cinematic/cancel',{}),('/api/cinematic/upload?name=x.mp4',{})):
            with self.subTest(path=path),self.assertRaises(HTTPError) as caught:self.request(path,body,token=False)
            self.assertEqual(caught.exception.code,403)
        with self.assertRaises(HTTPError):self.request('/api/cinematic/effects',{'id':'missing','effects':['flash']})
        with self.assertRaises(HTTPError):self.request('/api/cinematic/upload?name=bad.py',raw=b'ab')

    def test_plugin_edition_is_verified_before_cinematic_import(self):
        license=Mock();license.edition='plugins';license.ensure.side_effect=ValueError('Activate the plugin first')
        self.state.license_client=license;self.state.license_clients={'plugins':license}
        with self.assertRaises(HTTPError):self.request('/api/cinematic/import-manifest',{'host':'premiere'})
        license.ensure.assert_called_once_with('premiere');self.assertIsNone(self.state._cinematic)

    def test_plugin_upload_uses_plugin_activation_and_unknown_hosts_are_rejected(self):
        license=Mock();license.edition='plugins';self.state.license_client=license;self.state.license_clients={'plugins':license}
        result=self.request('/api/cinematic/upload?host=premiere&name=clip.mp4',raw=b'fixture')
        self.assertTrue(Path(result['path']).is_file());license.ensure.assert_called_once_with('premiere')
        with self.assertRaises(HTTPError):self.request('/api/cinematic/upload?host=untrusted&name=clip.mp4',raw=b'fixture')

    def test_cancel_queued_job_and_do_not_accept_second_active_job(self):
        with self.state.beats.lock:self.state.beats.jobs['fixture']={'id':'fixture','status':'complete','plan':music_plan()}
        with self.state.work_lock:
            job=self.request('/api/cinematic/assemble',{'beat_id':'fixture','source_paths':[]})
            with self.assertRaises(HTTPError):self.request('/api/cinematic/assemble',{'beat_id':'fixture','source_paths':[]})
            self.request('/api/cinematic/cancel',{'id':job['id']})
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            job=self.request('/api/cinematic/jobs/'+job['id'])
            if job['status']=='cancelled':break
            time.sleep(.02)
        self.assertEqual(job['status'],'cancelled')
