import tempfile
from pathlib import Path
from threading import Event
import unittest
from tests import test_photo_collection_service as fixtures
from tests.test_photo_collector import ROOT

class PreviewTests(unittest.TestCase):
    def test_previews_are_available_before_model_analysis_and_remain_labelled(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-preview-') as tmp:
            service,data,_=fixtures.CollectionServiceTests().make_service(Path(tmp));gate=Event()
            original=service.analyser
            def delayed(*args,**kwargs):gate.wait(5);return original(*args,**kwargs)
            service.analyser=delayed
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id'],'previews':True})
            try:
                now=service.snapshot(job['id'])
                self.assertGreater(len(now['photos']),0)
                self.assertTrue(all(row['origin']=='screenshot-preview' for row in now['photos']))
                self.assertEqual(now['counts']['saved'],0)
                self.assertTrue(service.file(job['id'],'photo',now['photos'][0]['id']).is_file())
            finally:gate.set();service.wait(job['id'],10)

if __name__=='__main__':unittest.main()
