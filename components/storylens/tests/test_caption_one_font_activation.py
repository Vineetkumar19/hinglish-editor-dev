import unittest
from pathlib import Path
from unittest.mock import Mock
class ActivationTests(unittest.TestCase):
    def test_caption_six_activates_only_its_three_verified_fonts(self):
        from tools.activate_caption_one_fonts import activate
        calls=[]
        result=activate(Path.cwd(),lambda p:(calls.append(Path(p).name) or 1),lambda:calls.append('notify'),caption_six=True)
        self.assertEqual(calls,['StorylensCircleSans-SemiBold.ttf','PlayfairDisplay-BoldItalic.ttf','InterDisplay-SemiBoldItalic.ttf','notify'])
        self.assertEqual(len(result['fonts']),3)
    def test_caption_two_activates_the_hash_verified_regular_footer_face(self):
        from tools.activate_caption_one_fonts import activate
        calls=[]
        result=activate(Path.cwd(),lambda p:(calls.append(Path(p).name) or 1),lambda:calls.append('notify'),caption_two=True)
        self.assertEqual(calls,['Inter-Bold.otf','Inter-Medium.otf','StorylensInterCaption-Regular.ttf','notify'])
        self.assertEqual(len(result['fonts']),3)
    def test_caption_three_activates_its_verified_serif_and_handwritten_faces(self):
        from tools.activate_caption_one_fonts import activate
        calls=[]
        result=activate(Path.cwd(),lambda p:(calls.append(Path(p).name) or 1),lambda:calls.append('notify'),caption_three=True)
        self.assertEqual(calls,['CaptionThree-BoldItalic.ttf','CaptionThree-RegularItalic.ttf','CaptionThree-Playful.ttf','notify'])
        self.assertEqual(len(result['fonts']),3)
    def test_both_verified_faces_load_before_adobe_is_notified(self):
        from tools.activate_caption_one_fonts import activate
        calls=[]
        result=activate(Path.cwd(),lambda p:(calls.append(Path(p).name) or 1),lambda:calls.append('notify'))
        self.assertEqual(calls,['Inter-Bold.otf','Inter-Medium.otf','notify'])
        self.assertEqual(len(result['fonts']),2)
    def test_failed_activation_is_not_reported_as_available(self):
        from tools.activate_caption_one_fonts import activate
        notify=Mock()
        with self.assertRaises(ValueError):activate(Path.cwd(),lambda p:0,notify)
        notify.assert_not_called()
