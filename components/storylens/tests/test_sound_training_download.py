import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s=importlib.util.spec_from_file_location('ranges',ROOT/'tools/sound_training/download.py')
        cls.m=importlib.util.module_from_spec(s);s.loader.exec_module(cls.m)
    def test_ranges_cover_remaining_bytes_once(self):
        self.assertEqual(self.m.ranges(13,3,4),[(3,6),(7,10),(11,12)])
    def test_wrong_range_rejected(self):
        with self.assertRaises(ValueError):self.m.check_range(206,'bytes 0-3/20',4,7,20,4)
    def test_truncated_range_rejected(self):
        with self.assertRaises(ValueError):self.m.check_range(206,'bytes 4-7/20',4,7,20,3)
    def test_full_response_not_accepted_as_range(self):
        with self.assertRaises(ValueError):self.m.check_range(200,'bytes 4-7/20',4,7,20,4)
if __name__=='__main__':unittest.main()
