import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

class PronunciationTests(unittest.TestCase):
    def test_mixed_script_still_prepares_roman_hinglish(self):
        from hinglish_voice.pronunciation import needs_hindi
        self.assertTrue(needs_hindi('आज meri awaaz mein Google Translator बोलेगा.'))

    def test_mixed_script_tokens_keep_devanagari_vowel_marks(self):
        from hinglish_voice.pronunciation import WORDS, render
        text='मेरी आवाज़: meri awaaz mein Google Translator 123!'
        words=['मेरी','आवाज़','मेरी','आवाज़','में','Google','Translator','123']
        self.assertEqual(WORDS.findall(text),['मेरी','आवाज़','meri','awaaz','mein','Google','Translator','123'])
        self.assertEqual(render(text,words),'मेरी आवाज़: मेरी आवाज़ में Google Translator 123!')

    def test_existing_devanagari_is_not_rewritten(self):
        from hinglish_voice.pronunciation import render
        with self.assertRaises(ValueError):
            render('मेरा voice', ['मेरी','voice'])

    def test_only_validated_pronunciation_is_reused(self):
        from hinglish_voice.pronunciation import prepare
        Path('work/voiceover-tests').mkdir(parents=True,exist_ok=True)
        class Brain:
            name='test-local';model='test-local';calls=0;last_usage={};cache_enabled=True
            def json(self,*args,**kwargs):
                self.calls+=1
                return {'words':['मेरी','आवाज़','में']}
            def close(self):pass
        brain=Brain()
        with tempfile.TemporaryDirectory(dir='work/voiceover-tests') as folder:
            root=Path(folder);out=root/'job';out.mkdir()
            request={'script':'meri awaaz mein','transcript':'My sample.'}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain):
                first=prepare(root,request,out);second=prepare(root,request,out)
            self.assertEqual(first,second)
            self.assertEqual(brain.calls,1)
            self.assertFalse(brain.cache_enabled)
    def test_hindi_greeting_is_not_mistaken_for_a_persons_name(self):
        from hinglish_voice.pronunciation import seed_tokens
        self.assertEqual(seed_tokens(['Namaste','Vineet','123']),['नमस्ते','Vineet','123'])
    def test_detects_roman_hindi_but_keeps_english(self):
        from hinglish_voice.pronunciation import needs_hindi
        self.assertTrue(needs_hindi('Aaj ki kahani meri awaaz mein.'))
        self.assertFalse(needs_hindi('This is my voice. Let’s begin.'))
        self.assertFalse(needs_hindi('आज की कहानी मेरी आवाज में।'))

    def test_maps_phonetic_words_without_changing_spaces_punctuation_or_numbers(self):
        from hinglish_voice.pronunciation import render
        original='Aaj  ki kahani\n123!'
        self.assertEqual(render(original,['आज','की','कहानी','123']), 'आज  की कहानी\n123!')
        self.assertEqual(render('meri awaaz mein',['मेरी','आवाज़','में']), 'मेरी आवाज़ में')
        self.assertEqual(render('zindagi',['जिंदगी']), 'जिंदगी')

    def test_rejects_rewriting_dropped_words_and_changed_numbers(self):
        from hinglish_voice.pronunciation import render
        for words in (['कल','की','कहानी','123'],['आज','की','123'],['आज','की','कहानी','124'],['आज की','की','कहानी','123']):
            with self.assertRaises(ValueError):render('Aaj ki kahani 123!',words)

if __name__=='__main__':unittest.main()
