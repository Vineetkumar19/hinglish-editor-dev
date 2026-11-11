import os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

class WorkerLeaseTests(unittest.TestCase):
    def test_second_process_waits_and_os_releases_lease_when_owner_exits(self):
        from hinglish_broll.worker_lease import worker_lease
        base=Path(__file__).resolve().parents[1]/'cache/test-broll-lease';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            root=Path(tmp);code='from pathlib import Path; from hinglish_broll.worker_lease import worker_lease; import sys,time; root=Path(sys.argv[1]);\nwith worker_lease(root):\n (root/sys.argv[2]).write_text("acquired");time.sleep(float(sys.argv[3]))'
            from sys import executable
            first=subprocess.Popen([executable,'-c',code,str(root),'first','20'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            second=None
            try:
                deadline=time.monotonic()+8
                while not (root/'first').exists() and time.monotonic()<deadline:time.sleep(.03)
                self.assertTrue((root/'first').exists())
                second=subprocess.Popen([executable,'-c',code,str(root),'second','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                time.sleep(.35);self.assertFalse((root/'second').exists())
                first.terminate();first.communicate(timeout=5)
                out,err=second.communicate(timeout=8)
                self.assertEqual(second.returncode,0,err.decode());self.assertTrue((root/'second').exists())
            finally:
                for p in (first,second):
                    if p is not None and p.poll() is None:p.kill();p.communicate(timeout=5)

    def test_normal_cli_enters_worker_lease_before_pipeline_execution(self):
        from contextlib import contextmanager
        from hinglish_broll.__main__ import main
        seen=[]
        @contextmanager
        def lease(*args,**kwargs):
            seen.append('enter');yield;seen.append('leave')
        def run(*args,**kwargs):seen.append('run');return Path('report.html')
        with patch('sys.argv',['broll','--root','cache/test-broll-lease','--input','sample.mp4']),patch('hinglish_broll.worker_lease.worker_lease',lease),patch('hinglish_broll.__main__.run',run):
            self.assertEqual(main(),0)
        self.assertEqual(seen,['enter','run','leave'])

if __name__=='__main__':unittest.main()
