import json
import tempfile
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pathlib import Path
from unittest.mock import patch
from hinglish_app.server import serve
from hinglish_app.downloader import service
from tests.test_cinematic import make_shot

class DownloaderHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.server,self.state=serve(self.root,0);self.base='http://127.0.0.1:'+str(self.state.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.downloads=service(self.root)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.downloads.close();self.tmp.cleanup()
    def req(self,path,body=None,token=True,headers=None):
        h={'X-Hinglish-Token':self.state.token} if token else {}
        h.update(headers or {})
        return urlopen(Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=h),timeout=15)
    def test_routes_are_private_and_invalid_inputs_do_not_start(self):
        for path,body in [('/api/downloader/history',None),('/api/downloader/start',{}),('/api/downloader/cancel',{})]:
            with self.subTest(path=path),self.assertRaises(HTTPError) as caught:self.req(path,body,False)
            self.assertEqual(caught.exception.code,403)
        with self.assertRaises(HTTPError) as caught:self.req('/api/downloader/start',{'url':'https://example.org/'})
        self.assertEqual(caught.exception.code,400)
        self.assertEqual(self.downloads.history(),[])
        with self.req('/downloader.html') as r:
            html=r.read().decode();self.assertNotIn('__APP_TOKEN__',html);self.assertIn('4K',html);self.assertIn('Video + separate audio',html)

    def test_queue_folder_and_section_http_contract(self):
        destination=self.root/'Saved videos';destination.mkdir()
        with self.req('/api/downloader/settings',{'destination':str(destination)}) as r:
            self.assertEqual(json.load(r)['destination'],str(destination.resolve()))
        gate=threading.Event()
        with patch.object(self.downloads,'_run',side_effect=lambda id:gate.wait(3)):
            with self.req('/api/downloader/enqueue',{'requests':[
                {'url':'https://youtu.be/one','start_time':'2:50','end_time':'3:10','submission_id':'batch-1'},
                {'url':'https://fb.watch/abcd/','submission_id':'batch-2'}]}) as r:
                jobs=json.load(r)['jobs']
            self.assertEqual(len(jobs),2)
            self.assertEqual(jobs[0]['request']['section'],{'start':170.0,'end':190.0})
            with self.req('/api/downloader/history') as r: self.assertEqual(len(json.load(r)['jobs']),2)
            with self.req('/api/downloader/cancel',{'id':jobs[1]['id']}) as r:self.assertEqual(json.load(r)['status'],'cancelled')
            gate.set()
        with self.assertRaises(HTTPError):self.req('/api/downloader/settings',{'destination':'relative-path'})
    def test_actual_http_job_media_range_and_all_editor_handoffs(self):
        fixture=self.root/'fixture.mp4';make_shot(fixture,seconds=1)
        def transfer(request,folder,progress,cancel):
            import shutil
            dest=folder/'source.mp4';shutil.copy2(fixture,dest);return dest,{'title':'HTTP integration clip'}
        with patch.object(self.downloads,'transfer',side_effect=transfer):
            with self.req('/api/downloader/start',{'url':'https://youtu.be/fixture','quality':'720'}) as r:job=json.load(r)
            deadline=time.monotonic()+15
            while job['status'] in ('queued','running') and time.monotonic()<deadline:
                time.sleep(.04)
                with self.req('/api/downloader/job?id='+job['id']) as r:job=json.load(r)
        self.assertEqual(job['status'],'complete',job)
        url='/api/downloader/media?id='+job['id']+'&kind=video'
        with self.assertRaises(HTTPError):self.req(url,token=False)
        with self.req(url+'&token='+self.state.token,token=False,headers={'Range':'bytes=0-31'}) as r:
            self.assertEqual(r.status,206);self.assertEqual(len(r.read()),32)
        with self.assertRaises(HTTPError) as caught:self.req(url,headers={'Range':'bytes=999999999-0'})
        self.assertEqual(caught.exception.code,416)
        with self.req(url+'&download=1') as r:self.assertIn('attachment',r.headers['Content-Disposition'])
        (self.root/'config.editors.local.json').write_text(json.dumps({'capcut_home':str(self.root/'CapCut')}),encoding='utf-8')
        for editor in ('premiere','resolve','capcut'):
            with self.req('/api/editors/prepare',{'editor':editor,'folder':job['result']['assets']['video']['folder']}) as r:task=json.load(r)
            deadline=time.monotonic()+15
            while task['status']=='running' and time.monotonic()<deadline:
                time.sleep(.04)
                with self.req('/api/editors/task?id='+task['id']) as r:task=json.load(r)
            self.assertEqual(task['status'],'complete',task)
            self.assertTrue(task['files'])
