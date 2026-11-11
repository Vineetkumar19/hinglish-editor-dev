"""Real HTTP handler + collection lifecycle with explicit fixture search/model adapters."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import requests
from hinglish_app.server import AppState,LocalHTTPServer,make_handler
from tests import test_photo_collection_service as fixtures
from tests.test_photo_collector import ROOT

class PhotoIntegrationTests(unittest.TestCase):
    def test_upload_collect_reopen_download_and_recover_through_real_routes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-http-') as tmp:
            root=Path(tmp);service,screenshot,_=fixtures.CollectionServiceTests().make_service(root)
            state=AppState(root,0);server=LocalHTTPServer(('127.0.0.1',0),make_handler(state))
            state.port=server.server_address[1]
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            client=requests.Session();client.trust_env=False;base='http://127.0.0.1:'+str(server.server_address[1])
            try:
                with patch('hinglish_app.photo_collector_http.service',return_value=service):
                    self.assertEqual(client.get(base+'/api/photos/history').status_code,403)
                    client.headers['X-Hinglish-Token']=state.token;client.headers['Origin']=base
                    bad=client.post(base+'/api/photos/upload',data=b'<html>not a screenshot</html>')
                    self.assertEqual(bad.status_code,400);self.assertEqual(bad.json()['error_code'],'photo_screenshot')
                    upload=client.post(base+'/api/photos/upload',data=screenshot);self.assertEqual(upload.status_code,201)
                    start=client.post(base+'/api/photos/start',json={'upload_id':upload.json()['upload_id'],'min_edge':0})
                    self.assertEqual(start.status_code,202);id=start.json()['id'];service.wait(id,10)
                    saved=client.get(base+'/api/photos/job',params={'id':id}).json()
                    self.assertEqual(saved['status'],'done');self.assertEqual(saved['counts']['found'],2);self.assertEqual(saved['counts']['saved'],0)
                    saved=client.post(base+'/api/photos/save',json={'id':id,'item':1}).json()
                    self.assertEqual(saved['counts']['saved'],1)
                    photo=client.get(base+'/api/photos/file',params={'id':id,'kind':'photo','item':1})
                    self.assertEqual(photo.status_code,200);self.assertEqual(photo.content,service.file(id,'photo',1).read_bytes())
                    package=client.get(base+'/api/photos/file',params={'id':id,'kind':'zip'})
                    self.assertEqual(package.status_code,200);self.assertIn('attachment',package.headers['Content-Disposition'])
                    archived=client.post(base+'/api/photos/archive',json={'id':id}).json();self.assertEqual(archived['status'],'archived')
                    restored=client.post(base+'/api/photos/restore',json={'id':id}).json();self.assertEqual(restored['status'],'done')
            finally:client.close();server.shutdown();server.server_close();thread.join(2)

if __name__=='__main__':unittest.main()
