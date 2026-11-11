"""Regressions from the native Premiere panel's real short-camera check."""
import tempfile
import unittest
from pathlib import Path

from hinglish_captions.core import CaptionWord, build_cues
from hinglish_captions.subtitles import write_srt


class CaptionCueBoundaryTests(unittest.TestCase):
    def test_balanced_adjacent_slides_do_not_overlap_for_readability_hold(self):
        # The 80 ms visual hold used to overlap the next slide by 20 ms.
        words = [CaptionWord(text, start, end) for text, start, end in (
            ('Tribble', 5.20, 5.56), ('the', 5.56, 5.68),
            ('ability', 5.70, 6.08), ('to', 6.14, 6.26),
            ('defend', 6.28, 6.64), ('themselves.', 6.66, 7.04))]
        cues = build_cues(words)
        self.assertEqual([len(c.words) for c in cues], [3, 3])
        self.assertLessEqual(cues[0].end, cues[1].start)
        self.assertEqual([w for c in cues for w in c.words], words)
        self.assertGreaterEqual(cues[0].end, words[2].end)
        self.assertAlmostEqual(cues[-1].end, 7.12)

    def test_punctuation_split_exports_nonoverlapping_subtitles(self):
        words = [CaptionWord('Stay', 0, .20), CaptionWord('ready.', .21, .40),
                 CaptionWord('Move', .42, .60), CaptionWord('now.', .61, .80)]
        cues = build_cues(words)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'captions.srt'
            write_srt(path, cues)
            text = path.read_text(encoding='utf-8-sig')
        self.assertIn('00:00:00,000 --> 00:00:00,420', text)
        self.assertIn('00:00:00,420 --> 00:00:00,880', text)
        self.assertEqual([w for c in cues for w in c.words], words)

    def test_real_silence_keeps_the_existing_readability_hold(self):
        words = [CaptionWord('Stay', 0, .20), CaptionWord('ready.', .21, .40),
                 CaptionWord('Move', 1.0, 1.20), CaptionWord('now.', 1.21, 1.40)]
        cues = build_cues(words)
        self.assertAlmostEqual(cues[0].end, .48)
        self.assertAlmostEqual(cues[-1].end, 1.48)
