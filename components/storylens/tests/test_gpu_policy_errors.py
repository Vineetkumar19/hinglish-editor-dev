import unittest
from hinglish_app.user_messages import problem,catalog


class GpuPolicyErrorTests(unittest.TestCase):
 def setUp(self):catalog.cache_clear()
 def test_gpu_offload_has_specific_recovery_without_model_substitution(self):
  error=problem(RuntimeError('The selected model could not be confirmed fully in GPU memory. CPU offload is blocked.'),feature='Smart Visuals')
  self.assertEqual(error['code'],'gpu_only_memory')
  self.assertIn('will not run on CPU',error['message'])
  self.assertNotIn('smaller local model',error['message'])
  self.assertIn('CPU offload',error['details'])
 def test_unsupported_alpha_format_does_not_suggest_repeated_retry(self):
  error=problem(RuntimeError('Transparent caption MOV export has no GPU encoder in this path. CPU fallback is disabled.'))
  self.assertEqual(error['code'],'gpu_only_export')
  self.assertIn('MP4',error['message'])
 def test_expired_child_reservation_keeps_progress(self):
  error=problem(RuntimeError('The parent GPU reservation expired or could not be verified.'))
  self.assertEqual(error['code'],'gpu_reservation')
  self.assertIn('saved',error['message'].lower())


if __name__=='__main__':unittest.main()
