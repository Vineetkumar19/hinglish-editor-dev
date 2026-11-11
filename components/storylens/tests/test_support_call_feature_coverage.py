import re
import unittest
from pathlib import Path
from hinglish_app.support_call_knowledge import FEATURES, TOPICS, guidance, topic_matches, _match, _normalize

STATIC=Path(__file__).resolve().parents[1]/'hinglish_app/static'

class FeatureCoverageTests(unittest.TestCase):
    def test_every_main_sidebar_feature_is_known(self):
        names=set(re.findall(r'data-mode="([A-Za-z][A-Za-z0-9]*)"',(STATIC/'index.html').read_text('utf8')))
        self.assertTrue(names)
        self.assertEqual(names-set(FEATURES),set())

    def test_every_voice_navigation_target_is_known(self):
        source=(STATIC/'support-call-actions.js').read_text('utf8')
        names=set()
        for block in ('tools','standalone'):
            body=source.split('const '+block+' = {',1)[1].split('};',1)[0]
            names.update(re.findall(r"\b(\w+):\s*(?:'|\[)",body))
        self.assertIn('aiAgents',names)
        self.assertEqual(names-set(FEATURES),set())

    def test_owner_confirmed_spoken_names_retrieve_correct_feature(self):
        for wording,key in [('Explain voice flow','voiceover'),('And what about voice flow?','voiceover'),
                            ('Explain photo connector feature','photos'),('Explained Auto Connector Feature','photos')]:
            with self.subTest(wording=wording):
                self.assertIn(key,_match(' '+_normalize(wording)+' '))
                self.assertIn(FEATURES[key][0],guidance(wording))
        self.assertNotIn('photos',_match(' '+_normalize('Reve Reveal')+' '))

    def test_nested_options_are_located_even_without_top_level_name(self):
        for term,wanted in [('Hyperframe','Render engine'),('3D2','Auto Captions'),
                            ('RealFilm V2','Color Grade 1'),('Quick Motion','Text Animations'),
                            ('comment replies','AI Agents')]:
            with self.subTest(term=term):
                self.assertIn(wanted,guidance('Explain '+term))
                self.assertTrue(topic_matches(term))

    def test_nested_sources_and_parent_targets_exist(self):
        for row in TOPICS:
            with self.subTest(topic=row['name']):
                self.assertTrue((STATIC/row['source']).is_file())
                self.assertTrue(set(row['features'])<=set(FEATURES))
                self.assertTrue(row['detail'])

    def test_hindi_sentence_punctuation_does_not_hide_feature(self):
        self.assertIn('voiceover',_match(' '+_normalize('वॉइस फ्लो।')+' '))

if __name__=='__main__': unittest.main()
