import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch
from hinglish_publish.stream_intake import prepare_stream

class StreamIntakeTests(TestCase):
 def test_one_highlight_is_reused_and_shorts_always_take_that_finished_highlight(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);source=root/'stream.mp4';source.write_bytes(b'original stream');target=root/'output/gaming/one';target.mkdir(parents=True)
   highlights=target/'GAMING_HIGHLIGHTS.mp4';highlights.write_bytes(b'finished highlight')
   (target/'gaming-project.json').write_text(json.dumps({'source':str(source),'video':str(highlights),'moments':[{'transcript':'A supported funny reaction.'}]}))
   report=target/'report.html';report.write_text('review')
   pub=Mock(root=root);pub.prepare_file.return_value={'job_ids':['one']}
   request={'source_mode':'stream','profile':'gaming','video_path':str(source),'platforms':['youtube','instagram'],'daily_window':True}
   with patch('hinglish_niche.gaming.run',return_value=report) as gaming,patch('hinglish_cut.gpu_lock.gpu_lock'):
    first=prepare_stream(pub,request,progress=lambda _:None);second=prepare_stream(pub,request,progress=lambda _:None)
   gaming.assert_called_once();self.assertEqual(gaming.call_args.kwargs['minutes'],15)
   self.assertEqual(pub.prepare_file.call_args.args[0]['video'],str(highlights))
   payload=pub.prepare_file.call_args.args[1];self.assertEqual(payload['shorts_source'],str(highlights));self.assertTrue(payload['make_shorts'])
   self.assertEqual(payload['script'],'A supported funny reaction.');self.assertEqual(first['job_ids'],second['job_ids'])
 def test_cricket_or_unrelated_url_never_runs_gaming(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   pub=Mock(root=Path(tmp))
   for profile,url in [('cricket','some.mp4'),('gaming','https://other.example/stream')]:
    with self.assertRaises(ValueError):prepare_stream(pub,{'profile':profile,'video_path':url},progress=lambda _:None)
