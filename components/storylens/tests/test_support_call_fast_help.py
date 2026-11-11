import unittest
from unittest.mock import patch
from hinglish_app.support_call_fast_help import answer, answer_parts, corpus, _HI
from hinglish_app.support_call_knowledge import FEATURES, TOPICS
from hinglish_app.support_call_controls import option_command

class FastHelpTests(unittest.TestCase):
    def test_every_feature_has_bilingual_fixed_purpose(self):
        self.assertEqual(set(_HI),set(FEATURES))
        self.assertEqual(len(corpus()), 2*(len(FEATURES) + sum('voice' in row for row in TOPICS)))
        for key,(label,_,_) in FEATURES.items():
            for language in ('en','hi'):
                with self.subTest(feature=key,language=language):
                    text=answer('What does '+label+' do?','',language)
                    self.assertTrue(text)
                    self.assertIn((text,language),corpus())

    def test_plain_questions_and_current_feature(self):
        for text in ('What is Smart Clean?', 'What is Smart Clean used for?',
                     'Tell me about Smart Clean', 'Explain Smart Clean',
                     'What does this feature do?', 'What is the purpose of Smart Clean?'):
            self.assertEqual(answer_parts(text,'clean'),answer_parts('What does Smart Clean do?'))
        for text in ('स्मार्ट क्लीन क्या करता है?', 'स्मार्ट क्लीन किस काम आता है?',
                     'Smart Clean kya karta hai?', 'ये फीचर किसलिए है?'):
            self.assertEqual(answer(text,'clean','hi'),_HI['clean'])

    def test_comparison_is_two_existing_clips(self):
        for text in ('What is the difference between Smart Clean and Smart Edit?',
                     'Compare Smart Clean with Smart Edit',
                     'How is Smart Clean different from Smart Edit?',
                     'Smart Clean and Smart Edit difference',
                     'स्मार्ट क्लीन और स्मार्ट एडिट में क्या अंतर है?',
                     'Smart Clean aur Smart Edit mein kya fark hai'):
            parts=answer_parts(text,'','hi')
            self.assertEqual(parts,(_HI['clean'],_HI['script']))
            self.assertTrue(all((part,'hi') in corpus() for part in parts))

    def test_nuanced_questions_and_action_requests_never_get_canned_purpose(self):
        for text in ('Open Smart Clean', 'How do I use Smart Clean?',
                     'Why is Smart Clean not working?',
                     'What does Smart Clean do when it crashes?',
                     'Explain Smart Clean settings', 'What is the price of activation?',
                     'Tell me about Smart Clean and then open it',
                     'Compare Smart Clean with Smart Edit for a silent film',
                     'How is Smart Clean different from Smart Edit in performance?',
                     '"What does Smart Clean do?"', 'Do not explain Smart Clean',
                     'What is my activation status?', 'What does Smart Clean cost?'):
            with self.subTest(text=text):
                self.assertEqual(answer(text,'clean'),'')

    def test_informational_asr_tolerance_is_strict_and_context_bound(self):
        self.assertEqual(answer('Smart Plein क्या करता है।', 'clean', 'hi'), _HI['clean'])
        self.assertEqual(answer('What does Smart Cleen do?', '', 'hi'), _HI['clean'])
        self.assertEqual(answer('What does Smart Plein do?', 'motion', 'hi'), '')
        for text in ('What does Quasar Banana do?', 'What is Smart Clean cost?',
                     'Explain Smart Clean error', 'Open Smart Cleen'):
            self.assertEqual(answer(text, 'clean'), '')
        with patch('hinglish_app.support_call_fast_help._TERMS',
                   {'smart clean': {'clean'}, 'smart cleat': {'script'}}):
            self.assertEqual(answer('What does Smart Cleen do?', 'clean'), '')

    def test_grounded_asr_suffix(self):
        self.assertEqual(option_command('Hyper Frame Cardo','motion')['value'],'hyperframes')
        self.assertIsNone(option_command('Imaginary tool cardo','motion'))
        self.assertIsNone(option_command('What does Hyper Frame Cardo mean','motion'))

if __name__=='__main__':
    unittest.main()
