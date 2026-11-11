import unittest
from tools.study_one_cricaddict_review import complete_observations,FIELDS

class ReferenceReviewQualityTests(unittest.TestCase):
 def setUp(self):self.answer={key:['The available evidence does not establish this detail.'] for key in FIELDS}
 def test_explicit_uncertainty_is_a_valid_complete_observation(self):self.assertTrue(complete_observations(self.answer))
 def test_cut_typography_and_audio_label_cannot_become_memory(self):
  self.answer['typography_and_texture']=['The text '];self.answer['audio_relationship_candidates']=['music']
  self.assertFalse(complete_observations(self.answer))
 def test_omitted_domain_cannot_pass_the_review(self):
  del self.answer['uncertainties'];self.assertFalse(complete_observations(self.answer))

if __name__=='__main__':unittest.main()
