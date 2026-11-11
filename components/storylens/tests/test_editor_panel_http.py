import json,tempfile,threading,time,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from hinglish_app.server import serve
from tests import test_editor_panel as fixtures

class PanelHTTPTests(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.EditorPanelTests();self.fixture.setUp();self.root=self.fixture.root
  self.server,self.state=serve(self.root,0);self.url='http://127.0.0.1:'+str(self.state.port)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(2);self.fixture.tearDown()
 def request(self,path,body=None,token=True):
  headers={'X-Hinglish-Token':self.state.token} if token else {}
  with urlopen(Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)) as r:return json.load(r)
 def test_panel_is_served_with_token_and_private_routes(self):
  with urlopen(self.url+'/editor-panel.html') as r:
   page=r.read().decode();self.assertNotIn('__APP_TOKEN__',page);self.assertIn('sharedScript',page)
  with self.assertRaises(HTTPError):self.request('/api/panel/config',token=False)
  for action in ['context','run','import']:
   with self.subTest(action=action),self.assertRaises(HTTPError):self.request('/api/panel/'+action,{},token=False)
  config=self.request('/api/panel/config');self.assertEqual(config['choices'],{'long':2,'short':5});self.assertNotIn('resolve',config['hosts'])
 def test_native_context_to_real_xml_to_engine_to_import_manifest(self):
  context=self.request('/api/panel/context',{**self.fixture.context,'script':'Exact words'})
  source=self.root/'output/script/example';source.mkdir(parents=True)
  from hinglish_app.editor_panel import snapshot_xml
  import shutil
  xml=source/'EDITED_SEQUENCE.xml';shutil.copy2(snapshot_xml(self.root,self.fixture.context),xml)
  def engine(payload):
   self.assertEqual(payload['script'],'Exact words');self.assertTrue(Path(payload['timeline_xml']).is_file())
   self.state.jobs['fixture']={'id':'fixture','mode':'clean','status':'complete','progress':100,'stage':'Done','result':{'folder':str(source),'xml_files':[str(xml)]}}
   return self.state.jobs['fixture']
  with patch.object(self.state,'create_job',side_effect=engine):
   job=self.request('/api/panel/run',{'context_id':context['id'],'mode':'clean','script':'Exact words'})
   deadline=time.monotonic()+6
   while job['status'] in ('queued','running') and time.monotonic()<deadline:
    time.sleep(.03);job=self.request('/api/panel/job?id='+job['id'])
  self.assertEqual(job['status'],'complete',job);self.assertEqual(job['manifest']['type'],'layers')
  self.assertEqual(job['manifest']['expected']['sequence_id'],'comp-2')
 def test_import_rejects_outside_output_and_missing_context(self):
  for body in [{'host':'aftereffects','folder':str(self.root)},{'context_id':'../../outside','folder':str(self.root)}]:
   with self.subTest(body=body),self.assertRaises(HTTPError):self.request('/api/panel/import',body)
 def test_broll_saved_results_are_authenticated_and_output_scoped(self):
  folder=self.root/'output/broll/actual';folder.mkdir(parents=True)
  project=folder/'broll-project.json';project.write_text(json.dumps({'timeline':{'name':'Saved speech'},'collecting':False}))
  with self.assertRaises(HTTPError):self.request('/api/panel/broll-results',token=False)
  result=self.request('/api/panel/broll-results')
  self.assertEqual(result['results'][0]['folder'],str(folder.resolve()))
  self.assertEqual(result['results'][0]['name'],'Saved speech')
 def test_generated_broll_source_supports_ranges_and_stays_output_scoped(self):
  folder=self.root/'output/broll/saved-bank';folder.mkdir(parents=True)
  source=folder/'audio-only-source.mp4';data=b'EXISTING GENERATED SOURCE AUDIO';source.write_bytes(data)
  route='/broll-output/saved-bank/audio-only-source.mp4'
  with urlopen(Request(self.url+route,headers={'X-Hinglish-Token':self.state.token,'Range':'bytes=3-11'})) as response:
   self.assertEqual(response.status,206);self.assertEqual(response.read(),data[3:12])
   self.assertEqual(response.headers['Content-Range'],f'bytes 3-11/{len(data)}')
   self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
  with self.assertRaises(HTTPError):self.request('/broll-output/../../config.json')
 def test_broll_choice_uses_saved_context_host_not_supplied_host(self):
  context=self.request('/api/panel/context',{**self.fixture.context,'script':'Exact words'})
  with patch('hinglish_app.panel_broll_choices.select',return_value={'choice_saved':True,'manifest':None}) as select:
   result=self.request('/api/panel/broll-choice',{'context_id':context['id'],'host':'premiere','folder':'result','state':'no_broll'})
  self.assertTrue(result['choice_saved']);self.assertEqual(select.call_args.args[-1],'aftereffects')
  self.assertEqual(select.call_args.args[-2]['sequence_id'],'comp-2')
 def test_browser_native_connection_requires_token_and_real_timeline_lease(self):
  context=self.request('/api/panel/context',{**self.fixture.context,'script':'Exact words'})
  with self.assertRaises(HTTPError):self.request('/api/panel/broll-native',{'action':'register','context_id':context['id'],'client':'a'*32},token=False)
  connected=self.request('/api/panel/broll-native',{'action':'register','context_id':context['id'],'client':'a'*32})
  self.assertEqual(connected['context']['sequence_id'],'comp-2')
  result=self.request('/api/panel/broll-native',{'action':'connect','host':'aftereffects'})
  self.assertEqual(result['name'],self.fixture.context.get('name','comp-2'))
  result=self.request('/api/panel/broll-native',{'action':'poll','lease':connected['lease'],'client':'a'*32})
  self.assertIsNone(result['command'])
 def test_browser_ae_can_use_the_fixed_direct_script_transport_without_a_cep_panel(self):
  context=self.request('/api/panel/context',{**self.fixture.context,'transport':'aftereffects_script'})
  with patch('hinglish_app.broll_ae_direct.AfterEffectsDirect.capture',return_value=context):
   connected=self.request('/api/panel/broll-native',{'action':'connect','host':'aftereffects'})
  self.assertEqual(connected['context_id'],context['id']);self.assertEqual(connected['transport'],'aftereffects_script')
  with patch('hinglish_app.panel_broll_choices.report_request',return_value={'folder':'bank','state':'selected'}),patch('hinglish_app.broll_ae_direct.AfterEffectsDirect.deliver',return_value={'status':'confirmed','id':'operation'}) as deliver:
   result=self.request('/api/panel/broll-native',{'action':'select','host':'aftereffects','transport':connected['transport'],'context_id':context['id']})
  self.assertEqual(result['status'],'confirmed');self.assertEqual(deliver.call_args.args[-1],context['id'])
 def test_visual_source_route_is_authenticated_and_forwards_completed_job_identity(self):
  with self.assertRaises(HTTPError):self.request('/api/panel/visual-sources?job_id=job-a',token=False)
  with patch('hinglish_app.visual_source_transport.VisualSourceTransport.describe',return_value={'job_id':'job-a','banks':[]}) as describe:
   result=self.request('/api/panel/visual-sources?job_id=job-a')
  self.assertEqual(result['job_id'],'job-a');describe.assert_called_once_with('job-a',None)
 def test_saved_visual_list_uses_only_completed_application_results(self):
  folder=self.root/'output/visuals/actual';folder.mkdir(parents=True)
  (folder/'report.html').write_text('Fixture review')
  (folder/'visuals-project.json').write_text(json.dumps({'timeline':{'name':'Actual saved speech'}}))
  job={'id':'saved-visual','mode':'visuals','status':'complete','result':{'folder':str(folder),'page':str(folder/'report.html')}}
  with self.state.lock:self.state.jobs[job['id']]=job
  with self.assertRaises(HTTPError):self.request('/api/panel/visual-results',token=False)
  response=self.request('/api/panel/visual-results')
  self.assertEqual(response['results'][0]['job_id'],'saved-visual')
  self.assertEqual(response['results'][0]['name'],'Actual saved speech')
 def test_sound_review_and_audition_are_authenticated_saved_job_operations(self):
  with self.assertRaises(HTTPError):self.request('/api/panel/sound-review?job_id=sound-one',token=False)
  context=self.request('/api/panel/context',self.fixture.context)
  with patch('hinglish_app.panel_sound_review.describe',return_value={'groups':[]}) as describe:
   self.assertEqual(self.request('/api/panel/sound-review?job_id=sound-one')['groups'],[])
  describe.assert_called_once_with(self.state,'sound-one')
  with patch('hinglish_app.panel_sound_review.audition',return_value={'status':'ready','id':'audition-bound'}) as audition:
   result=self.request('/api/panel/sound-audition',{'context_id':context['id'],'job_id':'sound-one','candidate_id':'explicit','source':'C:/ignored.wav'})
  self.assertEqual(result['status'],'ready');audition.assert_called_once_with(self.state,'sound-one','explicit')
 def test_saved_sound_reviews_route_is_authenticated(self):
  with self.assertRaises(HTTPError):self.request('/api/panel/sound-results',token=False)
  with patch('hinglish_app.panel_sound_review.saved_results',return_value=[{'job_id':'actual-sound','name':'Saved alternatives'}]):
   result=self.request('/api/panel/sound-results')
  self.assertEqual(result['results'][0]['job_id'],'actual-sound')

 def test_sound_original_uses_current_context_and_never_a_client_path(self):
  context=self.request('/api/panel/context',self.fixture.context)
  with patch('hinglish_app.panel_sound_review.original',return_value={'manifest':{'type':'assets','insert':False,'paths':['checked-source.wav']}}) as original:
   result=self.request('/api/panel/sound-original',{'context_id':context['id'],'job_id':'sound-one','candidate_id':'explicit','source':'C:/ignored.wav'})
  self.assertFalse(result['manifest']['insert']);self.assertEqual(result['manifest']['paths'],['checked-source.wav'])
  self.assertEqual(original.call_args.args[-1]['sequence_id'],'comp-2')
 def test_sound_preview_is_authenticated_and_uses_only_the_prepared_job_identity(self):
  import hashlib
  from urllib.parse import urlencode
  folder=self.root/'output/sound-recommendations/fixture/auditions';folder.mkdir(parents=True)
  sound=folder/'audition.wav';data=b'CONTROLLER AUDIO ROUTE BYTES';sound.write_bytes(data)
  descriptor={'path':str(sound),'mime':'audio/wav','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
  query=urlencode({'job_id':'sound-one','audition_id':'prepared-id','source':'C:/ignored-private.wav'})
  route='/api/panel/sound-audition-media?'+query
  with self.assertRaises(HTTPError):self.request(route,token=False)
  with patch('hinglish_app.panel_sound_review.preview',return_value=descriptor) as preview:
   with urlopen(Request(self.url+route,headers={'X-Hinglish-Token':self.state.token})) as response:
    self.assertEqual(response.read(),data);self.assertEqual(response.headers['Content-Type'],'audio/wav')
    self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
  preview.assert_called_once_with(self.state,'sound-one','prepared-id')
 def test_visual_media_uses_offered_identity_and_verified_bytes(self):
  import hashlib
  from urllib.parse import urlencode
  folder=self.root/'output/visuals/result';folder.mkdir(parents=True)
  image=folder/'original.png';data=b'SYNTHETIC PNG ROUTE BYTES';image.write_bytes(data)
  descriptor={'path':str(image),'mime':'image/png','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
  query=urlencode({'job_id':'job-a','project_path':'bound-project','manifest_sha256':'baseline','asset_id':'offered-id','path':'C:/private.png'})
  with self.assertRaises(HTTPError):self.request('/api/panel/visual-source-media?'+query,token=False)
  with patch('hinglish_app.visual_source_transport.VisualSourceTransport.resolve_media',return_value=descriptor) as resolve:
   with urlopen(Request(self.url+'/api/panel/visual-source-media?'+query,headers={'X-Hinglish-Token':self.state.token})) as r:
    self.assertEqual(r.read(),data);self.assertEqual(r.headers['Content-Type'],'image/png')
  resolve.assert_called_once_with('job-a','bound-project','baseline','offered-id')
 def test_visual_selection_imports_only_explicit_requested_raw_images_without_inserting(self):
  context=self.request('/api/panel/context',self.fixture.context)
  selected={'banks':[{'slot_index':0,'choices':[{'media_id':'chosen','asset_id':'asset-chosen'}]}],
            'selected_sources':[{'media_id':'chosen','asset_id':'asset-chosen','path':'raw-image.png'},{'media_id':'earlier','asset_id':'asset-earlier','path':'earlier.png'}]}
  with patch('hinglish_app.visual_source_transport.VisualSourceTransport.select',return_value=selected):
   result=self.request('/api/panel/visual-source-choice',{'context_id':context['id'],'job_id':'job-a','choices':{'0':'chosen'},'import_selected':True})
  self.assertEqual(result['native_manifest']['paths'],['raw-image.png'])
  self.assertFalse(result['native_manifest']['insert'])
  self.assertEqual(result['native_manifest']['expected']['sequence_id'],'comp-2')
 def test_visual_media_identity_is_bound_to_explicit_slot_not_another_saved_selection(self):
  context=self.request('/api/panel/context',self.fixture.context)
  selected={'banks':[{'slot_index':0,'choices':[{'media_id':'same-provider-id','asset_id':'subject-a'}]},
                     {'slot_index':1,'choices':[{'media_id':'same-provider-id','asset_id':'subject-b'}]}],
            'selected_sources':[{'media_id':'same-provider-id','asset_id':'subject-a','path':'explicit.png'},
                                {'media_id':'same-provider-id','asset_id':'subject-b','path':'earlier.png'}]}
  with patch('hinglish_app.visual_source_transport.VisualSourceTransport.select',return_value=selected):
   result=self.request('/api/panel/visual-source-choice',{'context_id':context['id'],'job_id':'job-a','choices':{'0':'same-provider-id'},'import_selected':True})
  self.assertEqual(result['native_manifest']['paths'],['explicit.png'])
 def test_photo_manifest_keeps_unsaved_project_identity_separate_from_path(self):
  context=self.request('/api/panel/context',{'host':'aftereffects','project_id':'unsaved-session-1','project_path':'','sequence_id':'_project_'})
  with patch('hinglish_photos.editor_plugin.prepare',return_value={'type':'photos','photos':[]}) as prepare:
   result=self.request('/api/panel/photos',{'id':'collection','context_id':context['id']})
  self.assertEqual(result['panel_project_id'],'unsaved-session-1');self.assertEqual(prepare.call_args.args[3]['project_id'],'')
