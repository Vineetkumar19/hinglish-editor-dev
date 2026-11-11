import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from tools.study_one_cricaddict_director import validate,repair_schema

class SingleReferenceDirectorTests(unittest.TestCase):
 def setUp(self):
  self.words=[{'id':f'w{i}','start':i*5+.011 if i else 0.,'end':i*5+.5,'text':'word'} for i in range(12)]
  self.plan={'scenes':[]}
  for i,key in enumerate(['crick-tv','crick-book','crick-paper','crick-film']):
   word=f'w{i*3}'
   photos=[{'asset':'source' if key in ('crick-tv','crick-film') else 'photo','word':word}]
   if key=='crick-paper':photos.append({'asset':'photo','word':f'w{i*3+1}'})
   self.plan['scenes'].append({'start_word':word,'effect':key,'headline':'Example','subline':'Example','caption':'Example',
    'name_first':'','name_last':'','motion_gain':2,'photos':photos,'notes':[],'sfx':'none','sfx_word':word})

 def test_valid_director_words_cover_exactly_sixty_seconds(self):
  errors,scenes=validate(self.plan,self.words)
  self.assertEqual(errors,[])
  self.assertEqual(sum(s['end_frame']-s['start_frame'] for s in scenes),1800)
  self.assertTrue(all(0<=p['schedule_error_ms']<1000/30 for s in scenes for p in s['photos']))

 def test_future_photo_cannot_leak_into_earlier_scene(self):
  self.plan['scenes'][0]['photos'][0]['word']='w5'
  errors,_=validate(self.plan,self.words)
  self.assertTrue(any('outside scene' in e for e in errors))

 def test_book_can_open_before_its_locally_chosen_photo_word(self):
  self.plan['scenes'][1]['photos'][0]['word']='w4'
  errors,_=validate(self.plan,self.words)
  self.assertEqual(errors,[])

 def test_other_rigs_must_show_subject_at_the_scene_start_cue(self):
  self.plan['scenes'][2]['photos'][0]['word']='w7'
  self.plan['scenes'][2]['photos'][1]['word']='w8'
  errors,_=validate(self.plan,self.words)
  self.assertTrue(any('first photo' in e for e in errors))

 def test_unrelated_previous_demo_subject_is_rejected(self):
  self.plan['scenes'][0]['name_first']='Dale';self.plan['scenes'][0]['name_last']='Steyn'
  errors,_=validate(self.plan,self.words)
  self.assertTrue(any('Dale Steyn' in e for e in errors))

 def test_internal_rig_labels_and_cut_phrases_do_not_reach_viewers(self):
  self.plan['scenes'][0]['headline']='Crick-Book'
  self.plan['scenes'][0]['subline']="India's history in"
  errors,_=validate(self.plan,self.words)
  self.assertTrue(any('internal rig name' in e for e in errors))
  self.assertTrue(any('unfinished English' in e for e in errors))

 def test_repair_preserves_local_boundaries_and_bounds_photo_words(self):
  schema,object_format=repair_schema(self.words,self.plan)
  self.assertTrue(object_format)
  first=schema['properties']['scene_1']['properties']
  self.assertEqual(first['start_word']['enum'],['w0'])
  self.assertEqual(first['photos']['items']['properties']['word']['enum'],['w0','w1','w2'])

 def test_repaired_source_photo_cannot_reuse_an_old_player_cutout(self):
  from PIL import Image
  from tools.render_one_cricaddict_sample import cached_isolation
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'scene-01-photo-1.jpg';Image.new('RGB',(32,32),'red').save(path)
   with patch('tools.render_one_cricaddict_sample.isolate',return_value=Image.new('RGBA',(32,32),(255,0,0,255))) as isolate:
    cached_isolation(path);cached_isolation(path)
    self.assertEqual(isolate.call_count,1)
    Image.new('RGB',(32,32),'blue').save(path)
    cached_isolation(path)
    self.assertEqual(isolate.call_count,2)

 def test_evidence_note_must_be_english_and_fit_its_visible_slot(self):
  self.plan['scenes'][0]['effect']='crick-evidence';self.plan['scenes'][0]['photos'][0]['asset']='photo'
  self.plan['scenes'][0]['notes']=[{'heading':'हिंदी','detail':'Example','word':'w0'},
   {'heading':'Example','detail':'Example','word':'w1'},{'heading':'Example','detail':'Example','word':'w2'}]
  errors,_=validate(self.plan,self.words)
  self.assertTrue(any('note heading' in error for error in errors))

if __name__=='__main__':unittest.main()
