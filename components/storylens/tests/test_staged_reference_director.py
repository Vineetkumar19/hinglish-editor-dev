import unittest
from unittest.mock import patch
from tools.direct_first_reference_staged import choose_clock,legacy_choose_clock

class StagedClockTests(unittest.TestCase):
 def setUp(self):
  self.words=[{'id':f'w{i}','start':i*5.,'end':i*5.+.5,'text':'spoken word'} for i in range(12)]
  self.review={'intervals':[{'start':0,'observations':{'reusable_lessons':['Measured source example.']}}]}
 def test_local_choices_are_sorted_without_inserting_new_boundaries(self):
  with patch('tools.direct_first_reference_staged.ask',return_value={'middle_start_words':['w6','w3'],'final_start_word':'w9','reason':'Local choice.'}),patch('tools.direct_first_reference_staged.load',return_value=self.review),patch('tools.direct_first_reference_staged.guidance',return_value={}),patch('tools.direct_first_reference_staged.save'):
   self.assertEqual(legacy_choose_clock(self.words),['w0','w3','w6','w9'])
 def test_duplicate_local_boundaries_fail_instead_of_receiving_invented_times(self):
  with patch('tools.direct_first_reference_staged.ask',return_value={'middle_start_words':['w3','w3'],'final_start_word':'w9','reason':'Local choice.'}),patch('tools.direct_first_reference_staged.load',return_value=self.review),patch('tools.direct_first_reference_staged.guidance',return_value={}),patch('tools.direct_first_reference_staged.save'):
   with self.assertRaises(ValueError):legacy_choose_clock(self.words)
 def test_sequential_boundaries_are_real_local_choices(self):
  answers=[{'next_start_word':word,'reason':'Spoken topic boundary.'} for word in ['w3','w6','w9','DONE']]
  with patch('tools.direct_first_reference_staged.ask',side_effect=answers),patch('tools.direct_first_reference_staged.guidance',return_value={}),patch('tools.direct_first_reference_staged.save'):
   self.assertEqual(choose_clock(self.words),['w0','w3','w6','w9'])
 def test_sequential_duplicate_is_rejected_without_replacement(self):
  with patch('tools.direct_first_reference_staged.ask',return_value={'next_start_word':'w0','reason':'Invalid repeat.'}),patch('tools.direct_first_reference_staged.guidance',return_value={}):
   with self.assertRaises(ValueError):choose_clock(self.words)

if __name__=='__main__':unittest.main()
