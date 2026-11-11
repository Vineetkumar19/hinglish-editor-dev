import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from hinglish_niche.reference_dna import VisualScan,audio_features,StyleDatabase
from hinglish_niche.style_memory import planning_examples,search
from hinglish_niche.profiles import use


class EditingDnaTests(unittest.TestCase):
 def test_every_frame_is_recorded_and_keyframes_belong_to_their_scene(self):
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory);scan=VisualScan(folder)
   previous=None
   for i in range(25):
    frame=np.zeros((144,256,3),np.uint8) if i<10 else np.full((144,256,3),210,np.uint8)
    delta=0 if previous is None else float(np.abs(frame.astype(float)-previous).mean())
    scan(frame,max(0,i*.1-.0000003),i,delta);previous=frame.astype(float)
   scenes=scan.close(2.5)
   self.assertEqual(sum(s['frames'] for s in scenes),25)
   self.assertEqual(len(scenes),2)
   self.assertAlmostEqual(scenes[0]['end'],1.0)
   for s in scenes:
    self.assertGreaterEqual(s['representative']['seconds'],s['start'])
    self.assertLess(s['representative']['seconds'],s['end'])
    self.assertTrue((folder/s['representative']['file']).is_file())
   self.assertEqual(len((folder/'visual-features.csv').read_text().splitlines()),26)

 def test_audio_keeps_tail_and_does_not_invent_beats_in_silence(self):
  audio=np.zeros(16001,np.float32);values,receipt=audio_features(audio)
  self.assertEqual(len(values),51)
  self.assertEqual(receipt['duration'],16001/16000)
  self.assertEqual(receipt['final_block_padding_samples'],319)
  self.assertEqual(receipt['onsets'],[])
  self.assertTrue(all(r['bpm_estimate'] is None for r in receipt['tempo_regions']))
  self.assertTrue(all(not r['beat_candidates_seconds'] for r in receipt['tempo_regions']))
  with self.assertRaises(ValueError):audio_features(np.array([],np.float32))

 def test_periodic_audio_has_a_candidate_grid_with_explicit_uncertainty(self):
  audio=np.zeros(16000*12,np.float32)
  for start in range(0,len(audio),8000):audio[start:start+160]=np.hanning(160)
  values,receipt=audio_features(audio)
  region=receipt['tempo_regions'][0]
  self.assertAlmostEqual(region['bpm_estimate'],120,delta=1)
  self.assertGreater(len(region['beat_candidates_seconds']),15)
  self.assertIn('not verified',region['status'])

 def test_vectors_are_style_isolated_and_replacement_cleans_fts(self):
  with tempfile.TemporaryDirectory() as directory:
   db=StyleDatabase(Path(directory)/'memory.sqlite3')
   for style in ['beneath-documentary-edit','crick-edit-editing-style']:
    db.replace_source(style,'ref',[{'kind':'scene','text':style,'vector':[1,0],'data':{'status':'candidate'}}])
   rows=db.search_vector('crick-edit-editing-style',[1,0])
   self.assertEqual(len(rows),1);self.assertIn('crick-edit',rows[0]['text'])
   db.replace_source('crick-edit-editing-style','ref',[{'kind':'scene','text':'new evidence','vector':[0,1]}])
   self.assertEqual(db.db.execute('SELECT COUNT(*) FROM search_index').fetchone()[0],2)
   self.assertEqual(db.search_vector('crick-edit-editing-style',[0,1])[0]['text'],'new evidence')
   db.close()

 def test_general_and_gaming_never_retrieve_documentary_examples(self):
  for profile in ['general','gaming']:
   with use({'profile':profile,'documentary_style':'crick-edit-editing-style'}):
    with patch('hinglish_niche.style_memory.search') as lookup:
     self.assertEqual(planning_examples('.', 'some narration'),[]);lookup.assert_not_called()
  with use({'profile':'cricket','documentary_style':'crick-edit-editing-style'}):
   with patch('hinglish_niche.style_memory.search',return_value=[{'source':'reference-04','start':2,'end':5,'text':'CRT archive','data':{'status':'candidate'}}]) as lookup:
    rows=planning_examples('.', 'historical match')
    self.assertEqual(rows[0]['source'],'reference-04')
    self.assertEqual(lookup.call_args.args[1],'crick-edit-editing-style')

 def test_sound_filter_does_not_retrieve_a_higher_scoring_visual_or_other_style(self):
  with tempfile.TemporaryDirectory() as directory:
   db=StyleDatabase(Path(directory)/'memory.sqlite3')
   db.replace_source('beneath-documentary-edit','ref',[
    {'kind':'scene-evidence','text':'visual','vector':[1,0]},
    {'kind':'audio-window','text':'sound','vector':[.9,.1]}])
   db.replace_source('crick-edit-editing-style','ref',[
    {'kind':'audio-window','text':'other style','vector':[1,0]}])
   rows=db.search_vector('beneath-documentary-edit',[1,0],kinds=['audio-window'])
   self.assertEqual([r['text'] for r in rows],['sound'])
   db.close()

 def test_sound_purpose_falls_back_for_older_scene_only_memories(self):
  with use({'profile':'cricket','documentary_style':'crick-edit-editing-style'}):
   with patch('hinglish_niche.style_memory.search',side_effect=[[],[
    {'source':'reference-04','start':2,'end':5,'text':'crowd and voice in scene','data':{}}]]) as lookup:
    rows=planning_examples('.', 'sound of a crowd',purpose='sound')
    self.assertEqual(rows[0]['reference'],'crowd and voice in scene')
    self.assertIn('audio-window',lookup.call_args_list[0].kwargs['kinds'])
    self.assertNotIn('kinds',lookup.call_args_list[1].kwargs)

 def test_invalid_style_and_empty_queries_are_rejected(self):
  with self.assertRaises(ValueError):search('.', '../outside','query')
  with self.assertRaises(ValueError):search('.', 'crick-edit-editing-style',' ')

 def test_reference_times_restore_original_video_pts_without_changing_raw_records(self):
  from tools.build_crick_edit_dna import aligned_scenes
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory)
   (folder/'frame-metrics.csv').write_text('frame,source_pts_seconds,relative_seconds\n0,0.033333,0\n')
   raw=[{'start':0,'end':1,'representative':{'seconds':.5},
         'camera_estimate':{'affine_motion_samples':[{'time':.2}]},'boundary_candidate':{'time':1}}]
   (folder/'scenes.json').write_text(json.dumps(raw))
   scenes,offset=aligned_scenes(folder)
   self.assertAlmostEqual(scenes[0]['start'],.033333)
   self.assertAlmostEqual(scenes[0]['representative']['seconds'],.533333)
   self.assertEqual(json.loads((folder/'scenes.json').read_text()),raw)

if __name__=='__main__':unittest.main()
