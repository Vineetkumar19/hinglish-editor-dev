from pathlib import Path
import tempfile
import threading
import unittest
from hinglish_cut.gpu_lock import gpu_lock


class GpuLockTests(unittest.TestCase):
    def test_separate_handles_serialize_work_and_release_after_errors(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
            entered=threading.Event();attempted=threading.Event()
            def worker():
                attempted.set()
                with gpu_lock(folder):entered.set()
            with gpu_lock(folder):
                thread=threading.Thread(target=worker);thread.start()
                self.assertTrue(attempted.wait(2))
                self.assertFalse(entered.wait(.25))
            self.assertTrue(entered.wait(2));thread.join(2)
            with self.assertRaises(RuntimeError):
                with gpu_lock(folder):raise RuntimeError('inference failed')
            with gpu_lock(folder):pass


if __name__=='__main__':unittest.main()
