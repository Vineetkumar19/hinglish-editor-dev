import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from hinglish_app.image_download import ImageDownloads

class ExactImageDownloadTests(unittest.TestCase):
    def picture(self):
        stream=io.BytesIO();Image.new('RGB',(160,100),'red').save(stream,'JPEG');return stream.getvalue()
    def test_exact_bytes_are_saved_and_repeated_image_is_not_duplicated(self):
        data=self.picture()
        class Fetch:
            def get(self,url,**kwargs):return {'data':data,'url':url,'mime':'image/jpeg'}
        with tempfile.TemporaryDirectory() as folder:
            service=ImageDownloads(Path(folder),fetcher_factory=Fetch)
            first=service.download('https://photos.example/exact.jpg')
            second=service.download('https://photos.example/exact.jpg')
            self.assertEqual(first['id'],second['id'])
            self.assertEqual(service.file(first['id'],'original').read_bytes(),data)
            self.assertEqual(len(list(service.downloads.glob('*.jpg'))),1)
    def test_private_address_is_rejected_before_fetching(self):
        def forbidden():raise AssertionError('network should not start')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):ImageDownloads(Path(folder),fetcher_factory=forbidden).download('http://127.0.0.1/private')
    def test_a_page_cannot_be_imported_as_an_image(self):
        class Fetch:
            def get(self,url,**kwargs):return {'data':b'<html>not an image</html>','url':url,'mime':'image/jpeg'}
        with tempfile.TemporaryDirectory() as folder:
            service=ImageDownloads(Path(folder),fetcher_factory=Fetch)
            with self.assertRaises(ValueError):service.download('https://photos.example/page')
            self.assertFalse(service.downloads.exists())
    def test_changed_saved_image_is_rejected_before_native_import(self):
        data=self.picture()
        class Fetch:
            def get(self,url,**kwargs):return {'data':data,'url':url,'mime':'image/jpeg'}
        with tempfile.TemporaryDirectory() as folder:
            service=ImageDownloads(Path(folder),fetcher_factory=Fetch)
            row=service.download('https://photos.example/exact.jpg')
            service.file(row['id']).write_bytes(b'changed')
            with self.assertRaises(ValueError):service.manifest(row['id'],'owner.aep')
