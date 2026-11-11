import unittest
from hinglish_cinematic.footage import select_unique, candidates

def sample(t,code=0,q=.8):return {'time':t,'quality':q,'hash':code,'hist':[1,0,0,0]}
def candidate(id,source,code,score=.8):return {'id':id,'source':source,'start':0,'duration':5,'score':score,'signature':[{'hash':code,'hist':[1,0,0,0]}]*3}

class FootageTests(unittest.TestCase):
 def test_unique_across_different_files_and_extras(self):
  rows=[candidate('a','one',0,.9),candidate('b','two',0,.8),candidate('c','three',2**64-1,.7),candidate('d','three',0xaaaaaaaaaaaaaaaa,.6)]
  best,extra,duplicates=select_unique(rows,2)
  self.assertEqual([r['id'] for r in best],['a','c'])
  self.assertEqual([r['id'] for r in extra],['d'])
  self.assertEqual(duplicates,1)
 def test_windows_never_overlap_and_stay_within_source(self):
  rows=candidates([sample(i*.5,code=i*333333333) for i in range(40)],20,'source')
  self.assertTrue(rows)
  for row in rows:self.assertEqual(row['duration'],5);self.assertLessEqual(row['start']+5,20)
  for a,b in zip(sorted(rows,key=lambda r:r['start']),sorted(rows,key=lambda r:r['start'])[1:]):self.assertLessEqual(a['start']+5,b['start'])
 def test_short_clips_keep_actual_duration(self):
  rows=candidates([sample(0),sample(1),sample(2)],2.5,'short')
  self.assertEqual(rows[0]['duration'],2.5)
 def test_repetitive_overlapping_windows_are_not_extra_choices(self):
  rows=candidates([sample(i*.5) for i in range(40)],20,'same')
  best,extra,duplicates=select_unique(rows,20)
  self.assertEqual(len(best),1);self.assertEqual(extra,[])
