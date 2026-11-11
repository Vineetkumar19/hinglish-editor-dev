import io
import unittest
from PIL import Image
from hinglish_app.image_clipboard import read_image,image_address

class ImageClipboardTests(unittest.TestCase):
    def test_one_explicit_read_preserves_clipboard_pixels(self):
        source=Image.new('RGBA',(150,100),(12,34,56,78));calls=[]
        def reader():calls.append(True);return source
        data=read_image(reader)
        with Image.open(io.BytesIO(data)) as result:
            self.assertEqual(result.size,source.size)
            self.assertEqual(result.convert('RGBA').tobytes(),source.tobytes())
        self.assertEqual(len(calls),1)
    def test_text_and_explorer_file_lists_are_not_silently_treated_as_images(self):
        for value in (None,['C:/private/file.png'],'some text'):
            with self.assertRaises(ValueError):read_image(lambda:value)
    def test_copied_chrome_image_markup_uses_only_its_exact_src(self):
        self.assertEqual(image_address('<img src="https://photos.example/exact.jpg"><script>ignored()</script>'),'https://photos.example/exact.jpg')
        with self.assertRaises(ValueError):image_address('<img src="https://photos.example/a.jpg"><img src="https://photos.example/b.jpg">')
