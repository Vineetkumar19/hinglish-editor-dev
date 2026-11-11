from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch
from hinglish_publish.metadata import generate

class CopyReviewTests(TestCase):
 def test_editorial_transcript_description_is_revised_using_same_actual_speech(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);video=root/'short.mp4';video.write_bytes(b'fixture')
   good={'title':'A clean cut shot','description':'A player cuts the ball past point. #Cricket #Batting #CutShot','instagram_caption':'A clean cut past point. #Cricket','tags':['Cricket','Batting','CutShot']}
   bad={**good,'description':'The transcript discusses a player and does not include match details.'}
   brain=Mock(name='local');brain.name='local-fixture';brain.json.side_effect=[bad,good]
   with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_publish.metadata.english_copy',side_effect=lambda b,data,*args:data),patch('hinglish_publish.metadata.review_grounding') as audit:
    result,_=generate(root,video,transcript='A player cuts the ball past point.',progress=lambda _:None)
   self.assertEqual(result['title'],good['title']);self.assertNotIn('transcript',result['description'])
   self.assertEqual(brain.json.call_count,2);audit.assert_called_once();brain.close.assert_called_once()
