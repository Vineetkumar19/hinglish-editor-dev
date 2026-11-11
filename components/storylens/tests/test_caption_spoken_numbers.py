import unittest
from uroman import Uroman
from hinglish_app.template_text_model import speech_normal


class SpokenNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.roman=Uroman()
    def norm(self,t):return speech_normal(self.roman.romanize_string(t,lcode='hin'))

    def test_hindi_number_range_retains_both_real_spoken_spans(self):
        from hinglish_app.caption_native_timing import align_words
        observed=[{'text':t,'start':i,'end':i+.4,'probability':.9} for i,t in enumerate(['तीन','चार','cancellation','normal','hai'])]
        words=align_words('3–4 cancellation normal hai',observed,6,self.norm)
        self.assertEqual([w['text'] for w in words],['3–4','cancellation','normal','hai'])
        self.assertEqual((words[0]['start'],words[0]['end']),(0,1.4))

    def test_written_and_spoken_numbers_are_equivalent_but_conflicting_values_are_not(self):
        from hinglish_app.caption_audio_alignment import check_relation
        tokens=['Pay','40','rupees','for','3–4','rides']
        anchors=[{'script_index':i,'alignment':'matched'} for i in range(len(tokens))]
        check_relation(tokens,anchors,[{'text':t} for t in ['Pay','चालीस','rupees','for','तीन','चार','rides']],self.norm)
        with self.assertRaises(ValueError):
            check_relation(tokens,anchors,[{'text':t} for t in ['Pay','fifty','rupees','for','three','four','rides']],self.norm)

    def test_range_is_not_integer_or_decimal(self):
        from hinglish_app.caption_numbers import comparison_key
        self.assertNotEqual(comparison_key('3–4',self.norm),comparison_key('34',self.norm))
        self.assertNotEqual(comparison_key('3.4',self.norm),comparison_key('34',self.norm))
        self.assertEqual(comparison_key('three',self.norm),comparison_key('3',self.norm))

    def test_compound_spoken_numbers_use_the_complete_phrase(self):
        from hinglish_app.caption_native_timing import align_words
        from hinglish_app.caption_audio_alignment import check_relation
        for script,heard in [('pay 21 rupees','pay twenty one rupees'),('pay 205 rupees','pay two hundred five rupees'),('pay 2300 rupees','pay two thousand three hundred rupees')]:
            observed=[{'text':t,'start':i,'end':i+.4,'probability':.9} for i,t in enumerate(heard.split())]
            words=align_words(script,observed,10,self.norm)
            check_relation(script.split(),words,observed,self.norm)
            self.assertEqual(words[1]['start'],1)
            self.assertEqual(words[1]['end'],len(heard.split())-2+.4)

    def test_punctuation_joined_words_can_be_compared_without_changing_display_text(self):
        from hinglish_app.caption_native_timing import align_words
        observed=[{'text':t,'start':i,'end':i+.4,'probability':.9} for i,t in enumerate(['pata','chala','Bhaiya','extra','do'])]
        words=align_words('pata chala—“Bhaiya, extra do',observed,6,self.norm)
        self.assertEqual(words[1]['text'],'chala—“Bhaiya,')
        self.assertEqual((words[1]['start'],words[1]['end']),(1,2.4))


if __name__=='__main__':unittest.main()
