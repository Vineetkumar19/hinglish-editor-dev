import json
from pathlib import Path
import tempfile
import unittest
from hinglish_app.panel_download_delivery import prepare,accept

class PanelDownloadDeliveryTests(unittest.TestCase):
    def test_native_delivery_uses_only_saved_media_and_keeps_project_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);key='a'*32;folder=root/'output/downloads'/key;asset=folder/'video/downloaded-video.mp4';asset.parent.mkdir(parents=True);asset.write_bytes(b'fixture')
            (folder/'job.json').write_text(json.dumps({'id':key,'status':'complete','title':'Owner clip','result':{'assets':{'video':{'path':str(asset),'folder':str(asset.parent)}}}}))
            context={'host':'aftereffects','project_id':'owner.aep'}
            manifest=prepare(root,key,'video',context)
            self.assertEqual(manifest['folder'],'Downloader Video');self.assertEqual(manifest['path'],str(asset));self.assertNotIn('sequence_id',manifest)
            with self.assertRaises(ValueError):accept(root,key,'video',context,{'ok':True,'project_id':'other.aep'})
            self.assertTrue(asset.exists())
