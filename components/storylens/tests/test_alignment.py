import unittest
import numpy as np
from hinglish_cut.alignment import ctc_path, align_tokens, ctc_blank


class CtcTests(unittest.TestCase):
    def test_explicit_blank_precedes_tokenizer_padding(self):
        self.assertEqual(ctc_blank({'<blank>':0,'<pad>':1,'a':2},1),0)

    def test_repeated_letters_need_a_blank(self):
        emissions=np.full((5,3),-10.,dtype=np.float32)
        for t,label in enumerate([0,1,0,1,0]):
            emissions[t,label]=0
        spans=ctc_path(emissions,[1,1],0)
        self.assertEqual([(s[0],s[1]) for s in spans],[(1,2),(3,4)])

    def test_impossible_alignment_is_rejected(self):
        with self.assertRaises(ValueError):
            ctc_path(np.zeros((2,3)),[1,1],0)

    def test_unknown_digits_are_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            align_tokens(np.zeros((10,3)),['3000'],['3000'],{'a':1,'b':2},0,.02)

    def test_a_number_between_words_keeps_the_window_aligned(self):
        # "a 3722 b": the number has no letters in the model; it gets the time between its neighbours,
        # score 0 (uncertain), and the real words keep their exact timing
        emissions=np.full((8,3),-10.)
        for t,label in enumerate([0,1,0,0,0,0,2,0]):
            emissions[t,label]=0
        words=align_tokens(emissions,['a','3722','b'],['a','3722','b'],{'a':1,'b':2},0,.02)
        self.assertEqual([w.text for w in words],['a','3722','b'])
        self.assertAlmostEqual(words[0].end,.04)
        self.assertAlmostEqual(words[1].start,.04)
        self.assertAlmostEqual(words[1].end,words[2].start)
        self.assertEqual(words[1].score,0.0)
        self.assertGreater(words[2].score,.9)

    def test_words_keep_original_text_and_timing(self):
        emissions=np.full((5,3),-10.)
        for t,label in enumerate([0,1,0,2,0]):
            emissions[t,label]=0
        words=align_tokens(emissions,['a','b'],['A','B'],{'a':1,'b':2},0,.02)
        self.assertEqual([w.text for w in words],['A','B'])
        self.assertAlmostEqual(words[1].start,.06)


if __name__=='__main__':
    unittest.main()
