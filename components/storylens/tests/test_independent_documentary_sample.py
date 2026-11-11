import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tools.independent_documentary_sample import speech_onset,render


class IndependentSampleTests(unittest.TestCase):
    def test_sport_format_does_not_trigger_twenty_centuries_caption(self):
        self.assertEqual(speech_onset([{'text':'T20Is','at':1.0},{'text':'20','at':2.0}], '20'), 2.0)

    def test_spelled_number_matches_actual_first_spoken_word(self):
        self.assertEqual(speech_onset([{'text':'seventy','at':2.0},{'text':'five','at':2.4}], '75'), 2.0)
        self.assertEqual(speech_onset([{'text':'Sri','at':3.0},{'text':'Lanka','at':3.3}], 'Sri Lanka'), 3.0)

    def test_unmatched_label_has_no_fabricated_word_onset(self):
        self.assertIsNone(speech_onset([{'text':'cricket','at':1.0}], '97'))

    def test_changed_or_substituted_voice_is_rejected_before_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'voice').mkdir()
            photo=root/'photo.jpg';Image.new('RGB',(400,400),'blue').save(photo)
            asset={'id':'image-01','file':str(photo),'sha256':hashlib.sha256(photo.read_bytes()).hexdigest(),
                'purpose':'production','derived_from_reference':False,'rights':'licensed',
                'source_url':'https://example.org/photo','license':'CC BY 3.0','permission_evidence':'source licence page'}
            (root/'asset-provenance.json').write_text(json.dumps({'assets':[asset]}))
            (root/'local-plan.json').write_text(json.dumps({'scenes':[{'narration':'Fresh local narration'}]}))
            (root/'voice-receipt.json').write_text(json.dumps({'scenes':[{'purpose':'fresh-production-narration','text':'Fresh local narration','sha256':'wrong'}]}))
            (root/'voice'/'01.wav').write_bytes(b'substituted audio')
            with patch('tools.independent_documentary_sample.OUT',root),patch('hinglish_motion.render.SceneRenderer') as browser:
                with self.assertRaisesRegex(ValueError,'Fresh narration provenance'):
                    render()
                browser.assert_not_called()
