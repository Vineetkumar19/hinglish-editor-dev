import json,tempfile,unittest
from pathlib import Path
class ComputeRoutingTests(unittest.TestCase):
 def test_gpu_profile_keeps_quality_and_cpu_remains_explicit(self):
  from hinglish_cut.compute_policy import h264_profile,ffmpeg_h264
  self.assertEqual(h264_profile('cuda',18),('h264_nvenc',{'preset':'p5','cq':'18','b':'0'}))
  self.assertEqual(h264_profile('cpu',18),('libx264',{'preset':'fast','crf':'18'}))
  self.assertIn('h264_nvenc',ffmpeg_h264('cuda',18));self.assertNotIn('-crf',ffmpeg_h264('cuda',18))
  with self.assertRaises(ValueError):h264_profile('auto',18)
 def test_speech_settings_follow_existing_device_without_changing_models(self):
  from hinglish_cut.compute_policy import speech_options
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
   self.assertEqual(speech_options(folder),{'device':'cpu','compute_type':'int8'})
   Path(folder,'config.models.local.json').write_text(json.dumps({'device':'cuda','planning_model':'preserved:14b'}))
   self.assertEqual(speech_options(folder),{'device':'cuda','compute_type':'int8_float16'})
   self.assertEqual(json.loads(Path(folder,'config.models.local.json').read_text())['planning_model'],'preserved:14b')
 def test_gpu_lock_can_be_nested_in_same_thread_and_still_excludes_other_threads(self):
  import threading
  from hinglish_cut.gpu_lock import gpu_lock
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
   entered=threading.Event()
   with gpu_lock(folder):
    with gpu_lock(folder):pass
    worker=threading.Thread(target=lambda:self._enter(folder,entered));worker.start()
    self.assertFalse(entered.wait(.1))
   self.assertTrue(entered.wait(2));worker.join(2)
 def _enter(self,folder,event):
  from hinglish_cut.gpu_lock import gpu_lock
  with gpu_lock(folder):event.set()
from unittest.mock import patch
class HeavyOnlyPolicyTests(unittest.TestCase):
 def test_legacy_native_cpu_setting_cannot_bypass_heavy_gpu_policy(self):
  from hinglish_app.caption_compute import options_for
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
   Path(folder,'config.models.local.json').write_text(json.dumps({'device':'cuda','heavy_workloads_gpu_only':True}))
   Path(folder,'config.caption-native.local.json').write_text(json.dumps({'device':'cpu','compute_type':'int8'}))
   self.assertEqual(options_for(folder),{'device':'cuda','compute_type':'int8_float16'})
 def test_saved_cpu_choice_is_rerouted_and_small_explicit_cpu_helpers_remain_available(self):
  from hinglish_cut.compute_policy import heavy_device,h264_profile
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
   Path(folder,'config.models.local.json').write_text(json.dumps({'device':'cuda','heavy_workloads_gpu_only':True}))
   self.assertEqual(heavy_device(folder,'cpu'),'cuda')
   self.assertEqual(h264_profile('cpu')[0],'libx264') # Only an explicit low-level support operation, not a heavy root-routed request.
 def test_renderer_flags_request_gpu_and_keep_cpu_mode_explicit_for_other_projects(self):
  from hinglish_cut.compute_policy import hyperframes_flags
  self.assertEqual(hyperframes_flags('cuda'),['--gpu','--browser-gpu'])
  self.assertEqual(hyperframes_flags('cpu'),['--no-browser-gpu'])
 def test_eye_contact_does_not_fall_back_or_cache_a_transient_gpu_failure(self):
  from hinglish_eyecontact import media
  from unittest.mock import Mock,patch
  with patch('hinglish_cut.model_preferences.preferences',return_value={'heavy_workloads_gpu_only':True}),patch.object(media,'_ENCODERS',{}):
   with patch.object(media.av.codec.CodecContext,'create',side_effect=RuntimeError('busy')) as create:
    with self.assertRaisesRegex(RuntimeError,'no CPU fallback'):media.encoder_name()
    self.assertEqual([c.args[0] for c in create.call_args_list],['h264_nvenc'])
   codec=Mock()
   with patch.object(media.av.codec.CodecContext,'create',return_value=codec):self.assertEqual(media.encoder_name(),'h264_nvenc')

if __name__=='__main__':unittest.main()
