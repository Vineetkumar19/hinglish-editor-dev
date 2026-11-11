import hashlib,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from hinglish_publish.source_context import saved_transcript
from unittest.mock import patch

class SourceContextTests(TestCase):
 def test_only_the_exact_export_words_are_recovered_not_title_or_neighbouring_speech(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);folder=root/'All Shorts';folder.mkdir();original=root/'output/shorts/one';original.mkdir(parents=True)
   video=folder/'Shorts 2.mp4';video.write_bytes(b'exact export');source=original/'result.mp4';source.write_bytes(video.read_bytes())
   digest=hashlib.sha256(video.read_bytes()).hexdigest()
   (folder/'library.json').write_text(json.dumps({'shorts':[{'file':video.name,'sha256':digest,'title':'Untrusted unrelated title','original_paths':[str(source)]}]}))
   (original/'shorts-project.json').write_text(json.dumps({'shorts':[{'mp4':source.name,'pieces':[[1,5]]}],'words':[['Omit',0,.5],['Kid',1,2],['plays',2,3],['PUBG',3,4],['Omit',7,8]]}))
   text,receipt=saved_transcript(root,video)
   self.assertEqual(text,'Kid plays PUBG');self.assertEqual(receipt['sha256'],digest)
   source.write_bytes(b'changed original');self.assertEqual(saved_transcript(root,video),('',None))

 def test_recorded_context_precedes_asr_but_explicit_script_and_sidecar_win(self):
  from hinglish_publish.source_context import spoken_context
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);video=root/'clip.mp4';video.write_bytes(b'fixture')
   with patch('hinglish_publish.source_context.saved_transcript',return_value=('Recorded speech',{'method':'saved'})),patch('hinglish_shorts.source.transcribe') as asr:
    self.assertEqual(spoken_context(root,video,None,lambda _:None)[0],'Recorded speech')
    self.assertEqual(spoken_context(root,video,'Supplied script',lambda _:None)[0],'Supplied script')
    video.with_suffix('.txt').write_text('Creator transcript')
    self.assertEqual(spoken_context(root,video,None,lambda _:None)[0],'Creator transcript')
    asr.assert_not_called()
