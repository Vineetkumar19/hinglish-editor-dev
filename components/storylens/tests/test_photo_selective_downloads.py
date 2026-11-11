"""Regression contract prepared for owner-run testing; no live model/network calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from hinglish_photos.downloads import download_one,download_path
from hinglish_photos.service import PhotoService

class SelectiveDownloadTests(unittest.TestCase):
    def fixture(self,path):
        service=PhotoService(path);folder=service.base/'fixture';folder.mkdir()
        for name in ('originals','crops'): (folder/name).mkdir()
        image=Image.new('RGB',(1600,1000),'blue');image.save(folder/'originals/full.png');image.resize((296,185)).save(folder/'crops/001.png');image.resize((296,185)).save(folder/'crops/002.png')
        rows=[{'id':i,'status':'ready','file':'full.png','width':1600,'height':1000,'box':[0,0,296,185]} for i in (1,2)]
        service.jobs['0123456789ab']={'id':'0123456789ab','folder':'fixture','title':'Photos','status':'done','photos':rows}
        return service,folder
    @patch('hinglish_photos.core.similarity',return_value={'matched':True,'effective_width':1600,'effective_height':1000})
    def test_first_click_creates_download_folder_and_retries_reuse_same_file(self,_):
        with tempfile.TemporaryDirectory() as tmp:
            service,folder=self.fixture(Path(tmp));self.assertFalse((folder/'downloads').exists())
            download_one(service,'0123456789ab',2);download_one(service,'0123456789ab',2);download_one(service,'0123456789ab',1)
            self.assertEqual(sorted(p.name for p in (folder/'downloads').iterdir()),['Image 1.png','Image 2.png'])
            self.assertEqual(download_path(service,'0123456789ab',2).read_bytes(),(folder/'originals/full.png').read_bytes())
    def test_screenshot_preview_cannot_be_exported_as_hd(self):
        with tempfile.TemporaryDirectory() as tmp:
            service,folder=self.fixture(Path(tmp));service.jobs['0123456789ab']['photos'][0]['status']='preview'
            with self.assertRaisesRegex(ValueError,'original'):download_one(service,'0123456789ab',1)
            self.assertFalse((folder/'downloads').exists())
