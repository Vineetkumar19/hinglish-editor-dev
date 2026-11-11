import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from hinglish_cut.gpu_lock import gpu_lock,child_environment,held_by_current_thread,LEASE_ENV


class ChildLeaseTests(unittest.TestCase):
 def root(self):
  temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(temp.cleanup)
  return Path(temp.name)
 def child(self,root,env):
  return subprocess.run([sys.executable,'-c',
    'import sys;from hinglish_cut.gpu_lock import gpu_lock;\nwith gpu_lock(sys.argv[1]):print("GPU_CHILD_ENTERED")',str(root)],
    cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=8)
 def test_awaited_child_uses_its_parents_reservation_without_deadlock(self):
  root=self.root()
  with gpu_lock(root):
   self.assertTrue(held_by_current_thread(root))
   env=child_environment(root)
   result=self.child(root,env)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('GPU_CHILD_ENTERED',result.stdout)
  self.assertFalse(held_by_current_thread(root))
  self.assertFalse((root/'cache/app/gpu-work-lease.json').exists())
  self.assertNotIn(LEASE_ENV,os.environ)
 def test_a_forged_or_expired_lease_cannot_bypass_the_queue(self):
  root=self.root()
  with gpu_lock(root):
   env=child_environment(root);bad=json.loads(env[LEASE_ENV]);bad['token']='forged'
   env[LEASE_ENV]=json.dumps(bad)
   result=self.child(root,env)
   self.assertNotEqual(result.returncode,0)
   self.assertNotIn('GPU_CHILD_ENTERED',result.stdout)
   expired=child_environment(root)
  result=self.child(root,expired)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('reservation expired',result.stderr)
 def test_an_unrelated_thread_cannot_delegate_the_current_owners_slot(self):
  import threading
  root=self.root();denied=[]
  def attempt():
   try:child_environment(root)
   except RuntimeError:denied.append(True)
  with gpu_lock(root):
   worker=threading.Thread(target=attempt);worker.start();worker.join(2)
   self.assertEqual(denied,[True])


if __name__=='__main__':unittest.main()
