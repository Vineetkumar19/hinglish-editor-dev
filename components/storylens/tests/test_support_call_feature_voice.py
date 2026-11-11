import unittest
from hinglish_app.support_call_fast_help import answer
from hinglish_app.support_call_knowledge import FEATURES
from hinglish_app.support_call_speech import recognition_terms

class FeatureVoiceRegressionTests(unittest.TestCase):
    def test_all_feature_names_survive_current_button_hints(self):
        words=recognition_terms(['Choose video','Render engine'])
        for label,_,_ in FEATURES.values():
            self.assertIn(label,words)
        self.assertIn('Photo Collector',words)
        self.assertIn('Voice Clone',words)

    def test_owner_confirmed_misrecognitions_use_real_feature_guides(self):
        for question,label in [
            ('Explained Auto Connector Feature','Photo Collector'),
            ('What is the feature of Photo Collector?','Photo Collector'),
            ('And what about voice flow?','Voice Clone'),
            ('What does AI Agents do?','AI Agents'),
        ]:
            with self.subTest(question=question):
                response=answer(question,'captions','en')
                self.assertTrue(response.startswith(label))
                self.assertNotIn('not listed',response)
        self.assertTrue(answer('What does AI Agents do?','captions','hi'))

    def test_finance_and_agents_have_distinct_bilingual_guides(self):
        for question, expected in (
            ('What is Pocket Tracker?', ('phone alerts', 'budget')),
            ('How does the financial tracker work?', ('recorded net worth', 'missing prices')),
            ('Compare Pocket Tracker and Financial Tracker', ('phone alerts', 'recorded net worth')),
            ('What agents do we have?', ('Comment replies', 'SaaS sales', 'Development clients')),
            ('Which agents are under developer tools?', ('Community', 'All workflows')),
            ('What does the Editing Clients agent do?', ('editing gigs', 'proposals')),
            ('How do I use Demand research?', ('SaaS sales', 'public product link')),
            ('Tell me about Pocket Tracker, Financial Tracker and AI Agents',
             ('phone alerts', 'recorded net worth', 'Comment replies')),
        ):
            with self.subTest(question=question):
                response = answer(question, 'captions', 'en')
                for term in expected:
                    self.assertIn(term, response)
        for question, expected in (
            ('पॉकेट ट्रैकर क्या करता है?', 'खर्च'),
            ('Pocket Tracker क्रेकर क्या करता है?', 'खर्च'),
            ('फाइनेंशियल ट्रैकर कैसे काम करता है?', 'कर्ज़'),
            ('एजेंट सेक्शन क्या है?', 'स्पॉन्सरशिप्स'),
        ):
            self.assertIn(expected, answer(question, 'captions', 'hi'))
        self.assertEqual('', answer('Open Pocket Tracker', 'captions', 'en'))
        self.assertIn('Pocket Tracker', recognition_terms(['Choose video']))
        self.assertIn('Financial Tracker', recognition_terms(['Choose video']))

    def test_uncertain_name_is_not_silently_assigned_to_a_feature(self):
        self.assertEqual(answer('What is the feature of Reve Reveal?','captions','en'),'')
