import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from hinglish_app.server import serve

class WorkbenchHTTPTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.root=Path(self.temp.name)
  self.server,self.state=serve(self.root,0,publish_bridge=False);self.base='http://127.0.0.1:'+str(self.state.port)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join(2)
  if hasattr(self.state,'workbench_jobs'):self.state.workbench_jobs.pool.shutdown(wait=True,cancel_futures=True)
  self.temp.cleanup()
 def request(self,path,body=None,authorized=True):
  return urlopen(Request(self.base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json',**({'X-Hinglish-Token':self.state.token} if authorized else {})}),timeout=5)
 def test_real_pages_receive_token_and_catalogue_is_complete(self):
  for path in ('/cinematic-footage.html','/color-grade.html','/editor-panel.html?browser=1&host=aftereffects&tool=templateImport'):
   with self.request(path) as response:text=response.read().decode()
   self.assertIn(self.state.token,text);self.assertNotIn('__APP_TOKEN__',text)
  with self.request('/') as response:text=response.read().decode()
  for name in ('Smart Edit','Cinematic Footage','Color Grade','Import Template','Template Aligner','Reel Recreate','Voice Clone'):self.assertIn(name,text)
 def test_auth_and_native_missing_connection(self):
  with self.assertRaises(HTTPError) as denied:self.request('/api/native-tools/connections',authorized=False)
  self.assertEqual(denied.exception.code,403)
  with self.request('/api/native-tools/connections') as response:self.assertEqual(json.load(response)['connections'],[])
  with self.assertRaises(HTTPError):self.request('/api/native-tools/command',{'action':'templateAlign','request_id':'one','payload':{}})
 def test_native_http_command_receipt_round_trip(self):
  with self.request('/api/native-tools/register',{'client':'test','host':'aftereffects','project_id':'A'}) as response:identity=json.load(response)
  with self.request('/api/native-tools/command',{'action':'templateAlign','request_id':'one','payload':{}}) as response:command=json.load(response)
  with self.request('/api/native-tools/poll',identity) as response:self.assertEqual(json.load(response)['command']['id'],command['id'])
  with self.request('/api/native-tools/receipt',{**identity,'id':command['id'],'result':{'ok':True}}) as response:self.assertEqual(json.load(response)['status'],'confirmed')
 def test_verified_grade_template_download(self):
  with self.request('/api/workbench/grade-template') as response:
   self.assertEqual(response.status,200);self.assertGreater(len(response.read()),90000)
 def test_library_catalogue_without_editor_and_native_actions_rejected(self):
  from unittest.mock import patch
  with patch('hinglish_app.native_catalogue.read',return_value={'ok':True,'total':122,'tree':{}}) as reader:
   with self.request('/api/native-tools/catalog',{'action':'animationPresets','payload':{'action':'catalog'}}) as response:self.assertEqual(json.load(response)['total'],122)
   reader.assert_called_once_with('animationPresets',{'action':'catalog'})
  from hinglish_app.native_catalogue import read
  with self.assertRaises(ValueError):read('presetLibrary',{'action':'insertChoice'})
 def test_media_token_range_and_auth_boundaries(self):
  from hinglish_app.workbench_jobs import service
  key='a'*32;folder=self.root/'output/workbench'/key;folder.mkdir(parents=True)
  (folder/'shot.mp4').write_bytes(b'0123456789')
  jobs=service(self.state);jobs.rows[key]={'id':key,'status':'complete','result':{'assets':[{'id':'shot','path':str(folder/'shot.mp4')}]}};jobs.save(key)
  url='/api/workbench/media?id='+key+'&asset=shot&token='+self.state.token
  with urlopen(Request(self.base+url,headers={'Range':'bytes=3-6'}),timeout=5) as response:
   self.assertEqual(response.status,206);self.assertEqual(response.read(),b'3456');self.assertEqual(response.headers['Content-Range'],'bytes 3-6/10')
  with self.assertRaises(HTTPError) as denied:self.request('/api/workbench/media?id='+key+'&asset=shot',authorized=False)
  self.assertEqual(denied.exception.code,403)
  with self.assertRaises(HTTPError) as denied:self.request('/api/workbench/job?id='+key+'&token='+self.state.token,authorized=False)
  self.assertEqual(denied.exception.code,403)
