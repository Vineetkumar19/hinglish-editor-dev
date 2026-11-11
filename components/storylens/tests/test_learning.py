import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from hinglish_semantic.learning import LearningMemory


def candidate(identifier, text):
    return {'span': {'id': identifier, 'text': text}}


class LearningMemoryTests(unittest.TestCase):
    def test_review_correction_becomes_relevant_local_example(self):
        with TemporaryDirectory() as folder:
            memory = LearningMemory(folder)
            rows = [{'index': 0, 'idea': 'PG mein basic cheezein hongi',
                     'selected_id': 'old',
                     'alternatives': [candidate('old', 'saari cheezein hongi'),
                                      candidate('new', 'basic cheezein hongi')]}]
            self.assertEqual(memory.record_review(rows, {'0': 'new'}, 'project-a'), 1)
            example = memory.examples_for('PG mein basic facilities hongi')[0]
            self.assertEqual(example['human_approved_spoken'], 'basic cheezein hongi')
            self.assertEqual(example['human_rejected_spoken'], 'saari cheezein hongi')

    def test_same_review_is_not_learned_twice(self):
        with TemporaryDirectory() as folder:
            memory = LearningMemory(folder)
            rows = [{'index': 2, 'idea': 'latest take', 'selected_id': 'a',
                     'alternatives': [candidate('a', 'first'), candidate('b', 'second')]}]
            self.assertEqual(memory.record_review(rows, {'2': 'b'}, 'project-a'), 1)
            self.assertEqual(memory.record_review(rows, {'2': 'b'}, 'project-a'), 0)
            self.assertEqual(len(memory._records()), 1)

    def test_unrelated_review_is_not_injected(self):
        with TemporaryDirectory() as folder:
            memory = LearningMemory(folder)
            rows = [{'index': 0, 'idea': 'Rapido ride booking', 'selected_id': 'a',
                     'alternatives': [candidate('a', 'ride book karo')]}]
            memory.record_review(rows, {'0': 'a'}, 'project-a')
            self.assertEqual(memory.examples_for('Bed mast hai'), [])


if __name__ == '__main__':
    unittest.main()
