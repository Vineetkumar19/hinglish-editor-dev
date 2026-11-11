import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
from hinglish_app.editor_panel import PanelContexts,job_payload,snapshot_xml,caption_manifest,asset_choices,layer_manifest,PanelService

class EditorPanelTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  from tests.test_cinematic import make_shot
  self.clip=self.root/'clip.mp4';silent=self.root/'silent.mp4';make_shot(silent,seconds=2)
  from tests.test_cinematic import make_music
  music=self.root/'music.wav';make_music(music,seconds=2)
  import subprocess,imageio_ffmpeg
  subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(silent),'-i',str(music),'-c:v','copy','-c:a','aac','-shortest',str(self.clip)],check=True,capture_output=True)
  self.context={'host':'aftereffects','project_id':'project-one','sequence_id':'comp-2','name':'Owner comp','width':320,'height':180,'fps':30,'duration':2,'clips':[{'path':str(self.clip),'start':0,'end':2,'source_in':0,'kind':'video','track':0}]}
 def tearDown(self):self.tmp.cleanup()
 def test_shared_script_is_project_scoped_and_persistent(self):
  contexts=PanelContexts(self.root)
  saved=contexts.save({**self.context,'script':'Exact shared words 2026','content_format':'long'})
  self.assertEqual(PanelContexts(self.root).load(saved['id'])['script'],'Exact shared words 2026')
  other=contexts.save({**self.context,'sequence_id':'another','script':'Other script'})
  self.assertNotEqual(other['id'],saved['id']);self.assertEqual(contexts.load(saved['id'])['script'],'Exact shared words 2026')
 def test_host_and_format_are_validated(self):
  for change in [{'host':'resolve'},{'content_format':'bogus'},{'script':['bad']}]:
   with self.subTest(change=change),self.assertRaises(ValueError):PanelContexts(self.root).save({**self.context,**change})
 def test_every_semantic_tool_receives_one_shared_script(self):
  context=PanelContexts(self.root).save({**self.context,'script':'The player makes a comeback.'})
  for mode in ['script','captions','broll','visuals','zoom','sound']:
   with self.subTest(mode=mode):
    payload=job_payload(self.root,context,mode,{})
    self.assertEqual(payload['script'],context['script']);self.assertEqual(payload['caption_reference'],context['script'])
 def test_long_and_short_choices_are_two_and_five(self):
  for format,count in [('long',2),('short',5)]:
   context=PanelContexts(self.root).save({**self.context,'script':'Reference','content_format':format})
   for mode in ['broll','visuals']:
    payload=job_payload(self.root,context,mode,{})
    self.assertEqual(payload['broll_options_per_moment'] if mode=='broll' else payload['visuals_options_per_moment'],count)
    self.assertTrue(payload[mode+'_review_options']);self.assertFalse(payload.get('visuals_popups',False))
 def test_script_required_once_except_silence_clean(self):
  context=PanelContexts(self.root).save(self.context)
  self.assertEqual(job_payload(self.root,context,'clean',{})['mode'],'clean')
  with self.assertRaises(ValueError):job_payload(self.root,context,'zoom',{})
 def test_sound_has_explicit_recommend_and_auto_modes(self):
  context=PanelContexts(self.root).save({**self.context,'script':'A ball hits the ground.'})
  recommend=job_payload(self.root,context,'sound',{'sound_action':'recommend'})
  automatic=job_payload(self.root,context,'sound',{'sound_action':'auto'})
  self.assertFalse(recommend['panel_auto_import']);self.assertTrue(automatic['panel_auto_import'])
  self.assertFalse(automatic['sound_remove_music'])
 def test_ae_straight_cuts_export_without_rendering(self):
  path=snapshot_xml(self.root,self.context)
  from hinglish_app.aftereffects_adapter import cut_manifest
  result=cut_manifest(path)
  self.assertEqual(result['duration'],2);self.assertEqual(result['clips'][0]['source_in'],0)
  self.assertEqual(len(result['clips']),2)
 def test_complex_ae_context_is_rejected_without_flattening(self):
  for changes in [{'unsupported':['Time remap']},{'clips':[{**self.context['clips'][0],'stretch':200}]}]:
   with self.subTest(changes=changes),self.assertRaises(ValueError):snapshot_xml(self.root,{**self.context,**changes})
 def test_snapshot_paths_and_bounds_are_checked(self):
  for change in [{'path':'https://example.org/movie.mp4'},{'source_in':-1},{'end':5},{'start':float('nan')}]:
   with self.subTest(change=change),self.assertRaises(ValueError):snapshot_xml(self.root,{**self.context,'clips':[{**self.context['clips'][0],**change}]})
 def test_asset_manifest_is_bounded_to_output_and_groups_keyword(self):
  folder=self.root/'output/broll/result';folder.mkdir(parents=True)
  (folder/'one.mp4').write_bytes(b'x');(folder/'two.mp4').write_bytes(b'x')
  project={'slots':[{'index':0,'text':'Virat','start':1,'end':2,'options':[{'id':'a','clip':'one.mp4'},{'id':'b','clip':'two.mp4'}]}]}
  (folder/'broll-project.json').write_text(json.dumps(project),encoding='utf-8')
  rows=asset_choices(self.root,folder,2)
  self.assertEqual(len(rows),2);self.assertTrue(all(r['keyword']=='Virat' for r in rows))
  with self.assertRaises(ValueError):asset_choices(self.root,self.root,2)
 def test_ae_caption_rows_keep_existing_geometry_and_animation(self):
  project={'width':320,'height':180,'media':{'duration':2,'fps':'30','path':str(self.clip)},'style':'caption_2','cues':[]}
  row={'text':'Exact','font_path':'font.ttf','size_px':40,'color':'#ffffff','tracking':0,'start':0,'end':1,'slot':0,'animation':[{'time':0,'x':120,'y':80,'sx':1,'sy':1,'alpha':0},{'time':.1,'x':130,'y':80,'sx':1,'sy':1,'alpha':1}]}
  with patch('hinglish_app.caption_scene.build',return_value=[row]),patch('hinglish_app.premiere_captions.font_name',return_value='ExactFont'):manifest=caption_manifest(project)
  self.assertEqual(manifest['type'],'captions');self.assertEqual(manifest['words'][0]['animation'],row['animation']);self.assertEqual(manifest['style'],'caption_2')
 def test_caption_manifest_uses_exact_postscript_font_names(self):
  project={'width':320,'height':180,'media':{'duration':2,'fps':'30','path':str(self.clip)},'style':'caption_2','cues':[]}
  with patch('hinglish_app.caption_scene.build',return_value=[{'font_path':'font.ttf'}]),patch('hinglish_app.premiere_captions.font_name',return_value='Exact-FontItalic'):
   self.assertEqual(caption_manifest(project)['words'][0]['font_name'],'Exact-FontItalic')
 def test_ae_snapshot_does_not_change_canvas(self):
  with self.assertRaisesRegex(ValueError,'composition'):
   snapshot_xml(self.root,{**self.context,'width':1080,'height':1920})
 def test_ae_layer_manifest_preserves_center_and_audio_gain(self):
  path=snapshot_xml(self.root,self.context);tree=ET.parse(path)
  from hinglish_cut.xml_export import add
  video=tree.find('.//media/video/track/clipitem');effect=add(add(video,'filter'),'effect');add(effect,'effectid','basic')
  param=add(effect,'parameter');add(param,'parameterid','center');value=add(param,'value');add(value,'horiz',.1);add(value,'vert',-.2)
  audio=tree.find('.//media/audio/track/clipitem');effect=add(add(audio,'filter'),'effect');add(effect,'effectid','audiolevels')
  param=add(effect,'parameter');add(param,'parameterid','level');add(param,'value',.5)
  tree.write(path)
  manifest=layer_manifest(path);self.assertEqual(manifest['clips'][0]['motion']['center']['value'],[.1,-.2])
  self.assertEqual(manifest['clips'][1]['motion']['level']['value'],.5)
 def test_ae_layer_manifest_rejects_unimplemented_effect_parameters(self):
  path=snapshot_xml(self.root,self.context);tree=ET.parse(path)
  from hinglish_cut.xml_export import add
  effect=add(add(tree.find('.//clipitem'),'filter'),'effect');add(effect,'effectid','basic')
  param=add(effect,'parameter');add(param,'parameterid','crop');add(param,'value',50);tree.write(path)
  with self.assertRaises(ValueError):layer_manifest(path)
 def test_plugin_license_is_checked_before_timeline_analysis(self):
  from unittest.mock import Mock
  state=Mock(root=self.root);state.license_client=Mock();state.license_for.return_value.ensure.side_effect=ValueError('Plugin access required')
  service=PanelService(state);context=service.contexts.save({**self.context,'script':'Exact'})
  with patch('hinglish_app.editor_panel.job_payload') as payload,self.assertRaisesRegex(ValueError,'Plugin access required'):
   service.start({'context_id':context['id'],'mode':'captions'})
  payload.assert_not_called();state.license_for.assert_called_once_with('plugins')
