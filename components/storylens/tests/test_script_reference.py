import unittest

from hinglish_cut.model import Word
from hinglish_visuals.script import apply_script


class ScriptReferenceTests(unittest.TestCase):
    def test_spoken_acronym_parts_merge_from_reference_script(self):
        words = [Word('saat', 0.0, 0.2), Word('hazaar', 0.22, 0.5),
                 Word('rp', 0.52, 0.64), Word('m.', 0.66, 0.78), Word('par', 0.8, 0.95)]

        fixed, changes = apply_script(words, 'Saat hazaar RPM par.')

        self.assertEqual([word.text for word in fixed], ['saat', 'hazaar', 'RPM.', 'par'])
        self.assertEqual((fixed[2].start, fixed[2].end), (0.52, 0.78))
        self.assertTrue(any(change['script_spelling'] == 'RPM' for change in changes))


if __name__ == '__main__':
    unittest.main()
