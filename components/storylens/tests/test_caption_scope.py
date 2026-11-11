import json,unittest
from pathlib import Path
from uroman import Uroman
from hinglish_app.template_text_model import speech_normal

class CaptionScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(Path('tests/fixtures/caption-native-short-composition.json').read_text('utf8'));cls.roman=Uroman()
    def norm(self,text):return speech_normal(self.roman.romanize_string(text,lcode='hin'))

    def test_new_video_short_composition_reports_truncation_not_different_speech(self):
        from hinglish_app.caption_scope import scope_problem
        f=self.fixture;message=scope_problem(f['script'],f['observed'],f['capture'],self.norm)
        self.assertIn('14.4',message);self.assertIn('35.7',message);self.assertNotIn('different speech',message)

    def test_an_unrelated_script_is_not_explained_as_a_duration_problem(self):
        from hinglish_app.caption_scope import scope_problem
        f=self.fixture
        self.assertIsNone(scope_problem('garden flowers watering plants blossom sunlight',f['observed'],f['capture'],self.norm))

    def test_matching_current_portion_or_full_source_does_not_trigger_duration_hint(self):
        from hinglish_app.caption_scope import scope_problem
        f=self.fixture
        self.assertIsNone(scope_problem(' '.join(f['script'].split()[:44]),f['observed'],f['capture'],self.norm))
        capture={**f['capture'],'duration':35.7,'clips':[{**f['capture']['clips'][0],'end':35.7}]}
        self.assertIsNone(scope_problem(f['script'],f['observed'],capture,self.norm))
