import unittest
from PIL import Image
from hinglish_photos.analysis import card_image

class PhotoAnalysisTests(unittest.TestCase):
    def test_each_model_image_has_a_unique_id_outside_unmodified_source_pixels(self):
        image=Image.new('RGB',(300,200),'blue')
        first=card_image(image,1);other=card_image(image,2)
        self.assertEqual(first.size,(300,234))
        self.assertEqual(first.getpixel((0,34)),(0,0,255))
        self.assertEqual(first.crop((0,34,300,234)).tobytes(),image.tobytes())
        self.assertNotEqual(first.crop((0,0,300,34)).tobytes(),other.crop((0,0,300,34)).tobytes())

if __name__=='__main__':unittest.main()
