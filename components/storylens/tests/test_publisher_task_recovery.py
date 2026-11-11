import threading,time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock
from hinglish_publish.service import Publisher

class TaskRecoveryTests(TestCase):
 def wait(self,pub,key):
  for _ in range(200):
   task=pub.tasks[key]
   if task['status'] not in ('working','stopping'):return task
   time.sleep(.01)
  self.fail('Preparation did not reach a saved terminal state')
 def test_completed_preparation_and_request_survive_service_recreation(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   pub=Publisher(tmp);request={'video_path':'owner-export.mp4','profile':'cricket'}
   job=pub.task(lambda progress:{'job_ids':['exact-draft']},request=request)
   self.assertEqual(self.wait(pub,job['id'])['status'],'done')
   restored=Publisher(tmp);self.assertEqual(restored.tasks[job['id']]['result']['job_ids'],['exact-draft'])
   self.assertEqual(restored.tasks[job['id']]['request'],request)
 def test_stop_at_checkpoint_preserves_request_without_running_next_step(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   pub=Publisher(tmp);started=threading.Event();resume=threading.Event();next_step=Mock()
   def work(progress):started.set();resume.wait(2);progress('Checkpoint');next_step()
   key=pub.task(work,request={'video_path':'owner-export.mp4'})['id'];self.assertTrue(started.wait(1))
   pub.stop_task(key);resume.set();self.assertEqual(self.wait(pub,key)['status'],'stopped');next_step.assert_not_called()
   self.assertEqual(pub.resume_request(key)['video_path'],'owner-export.mp4')
