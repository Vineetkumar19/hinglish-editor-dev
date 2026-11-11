import tempfile
import time
import unittest
from pathlib import Path
from tests.test_cinematic import make_shot
from hinglish_app.downloader import probe,export_timeline
from hinglish_app.editor_handoff import start,snapshot

class FourDestinationTests(unittest.TestCase):
 def test_plain_download_has_aftereffects_composition_script(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);folder=root/'output/downloads/test/video';folder.mkdir(parents=True)
   video=folder/'downloaded-video.mp4';make_shot(video,seconds=1)
   export_timeline(video,probe(video),'video')
   job=start(root,{'editor':'aftereffects','folder':str(folder)})
   end=time.monotonic()+5
   while job['status']=='running' and time.monotonic()<end:time.sleep(.01);job=snapshot(job['id'])
   self.assertEqual(job['status'],'complete',job.get('error'))
   script=Path(job['scripts'][0]).read_text('utf-8')
   self.assertIn('downloaded-video.mp4',script)
   self.assertIn('storylensPanelImport',script)
