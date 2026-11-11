import unittest
from unittest.mock import patch
from PIL import Image

class TemporalInputTests(unittest.TestCase):
    def test_temporal_sheet_keeps_frames_readable_and_times_inside_interval(self):
        from hinglish_sound.scenes import temporal_sheet
        with patch('hinglish_sound.scenes.frame_at',return_value=Image.new('RGB',(480,270),'red')):
            image,times=temporal_sheet(object(),2.,5.)
        self.assertEqual(len(times),6)
        self.assertEqual(times[0],2.)
        self.assertTrue(all(2<=t<5 for t in times))
        self.assertGreaterEqual(image.width//3,320)
        self.assertEqual(image.getpixel((100,100)),(255,0,0))

if __name__=='__main__':unittest.main()
