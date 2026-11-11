import json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from hinglish_app.server import serve


class StockHTTPTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-stock-http';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.root=Path(self.tmp.name)
        self.server,self.state=serve(self.root,0);self.url='http://127.0.0.1:'+str(self.state.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(2);self.tmp.cleanup()
    def request(self,path,value=None,headers=None):
        h={'Content-Type':'application/json',**(headers or {})}
        with urlopen(Request(self.url+path,data=json.dumps(value).encode() if value is not None else None,headers=h)) as r:return json.load(r)
    def test_pairing_is_private_worker_key_cannot_access_other_app_routes(self):
        with self.assertRaises(HTTPError):self.request('/api/stock-browser/pairing')
        data=self.request('/api/stock-browser/pairing',headers={'X-Hinglish-Token':self.state.token})
        self.assertIn('key',data)
        with self.assertRaises(HTTPError):self.request('/api/panel/config',headers={'X-Storylens-Stock':data['key']})
    def test_authenticated_request_to_scoped_extension_receipt_round_trip(self):
        auth={'X-Hinglish-Token':self.state.token}
        pair=self.request('/api/stock-browser/pairing',headers=auth)
        worker={'X-Storylens-Stock':pair['key'],'Origin':'chrome-extension://'+'a'*32}
        self.request('/api/stock-browser/worker/hello',{'client':'client-one','version':'1.0','providers':['pexels']},worker)
        job=self.request('/api/stock-browser/request',{'provider':'pexels','query':'bed','orientation':'vertical','limit':6},auth)
        task=self.request('/api/stock-browser/worker/claim',{'client':'client-one'},worker)['task']
        self.assertEqual(task['id'],job['id'])
        self.request('/api/stock-browser/worker/finish',{'client':'client-one','id':job['id'],'lease':task['lease'],'results':[]},worker)
        result=self.request('/api/stock-browser/job?id='+job['id'],headers=auth)
        self.assertEqual(result['status'],'complete')

    def test_broll_subprocess_client_receives_a_real_http_browser_receipt(self):
        import time
        from hinglish_broll.stock_browser_client import BrowserSearch
        auth={'X-Hinglish-Token':self.state.token}
        pair=self.request('/api/stock-browser/pairing',headers=auth)
        worker={'X-Storylens-Stock':pair['key'],'Origin':'chrome-extension://'+'b'*32}
        self.request('/api/stock-browser/worker/hello',{'client':'client-integration','version':'0.1','providers':['pixabay']},worker)
        folder=self.root/'output/broll/run/001';folder.mkdir(parents=True)
        found=[];errors=[]
        def search():
            try:found.extend(BrowserSearch(folder).search('pixabay','bed','vertical'))
            except Exception as error:errors.append(str(error))
        thread=threading.Thread(target=search);thread.start();task=None
        for _ in range(50):
            task=self.request('/api/stock-browser/worker/claim',{'client':'client-integration'},worker)['task']
            if task:break
            time.sleep(.02)
        self.assertIsNotNone(task)
        row={'page_url':'https://pixabay.com/videos/bed-123/','media_url':'https://cdn.pixabay.com/video/123-large.mp4','title':'Bed','width':720,'height':1280,'duration':9}
        self.request('/api/stock-browser/worker/finish',{'client':'client-integration','id':task['id'],'lease':task['lease'],'results':[row]},worker)
        thread.join(3);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(len(found),1);self.assertEqual(found[0].source,'pixabay_browser')

    def test_provider_scoped_http_claims_allow_two_live_jobs(self):
        auth={'X-Hinglish-Token':self.state.token};pair=self.request('/api/stock-browser/pairing',headers=auth)
        worker={'X-Storylens-Stock':pair['key'],'Origin':'chrome-extension://'+'c'*32}
        self.request('/api/stock-browser/worker/hello',{'client':'parallel-client','version':'0.1.2','providers':['pexels','pixabay']},worker)
        for provider in ('pexels','pixabay'):
            self.request('/api/stock-browser/request',{'provider':provider,'query':'bed','orientation':'vertical','limit':6},auth)
        tasks=[self.request('/api/stock-browser/worker/claim',{'client':'parallel-client','provider':provider},worker)['task'] for provider in ('pexels','pixabay')]
        self.assertEqual([t['provider'] for t in tasks],['pexels','pixabay'])
        for task in tasks:
            self.assertEqual(self.request('/api/stock-browser/job?id='+task['id'],headers=auth)['status'],'running')
            self.assertIsNone(self.request('/api/stock-browser/worker/claim',{'client':'parallel-client','provider':task['provider']},worker)['task'])

if __name__=='__main__':unittest.main()
