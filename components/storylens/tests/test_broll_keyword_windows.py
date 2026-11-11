import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hinglish_broll.keyword_windows import speech_windows, discover_bounded
from hinglish_broll.phrases import build_phrases
from hinglish_broll.placement import Moment, Slot


def speech(n=3000):
    return [SimpleNamespace(text=f'word{i}', start=i*.3, end=i*.3+.25) for i in range(n)]


class KeywordWindowTests(unittest.TestCase):
    def test_fifteen_minutes_are_covered_without_large_prompts_or_rebased_times(self):
        words = speech()
        batches = list(speech_windows(words))
        self.assertEqual([w for b in batches for w in b], words)
        self.assertGreater(len(batches), 10)
        for batch in batches:
            self.assertLessEqual(len(batch), 180)
            self.assertLessEqual(sum(len(w.text)+1 for w in batch), 1800)
            self.assertLessEqual(batch[-1].end-batch[0].start, 60)
        calls = []
        def discover(llm, phrases, batch, summary, count, brief, progress):
            calls.append((batch, count))
            return [Slot(Moment(phrases[0].id, 'room', ['room']), batch[0].start,
                         batch[0].end, batch[0].text)]
        slots = discover_bounded(None, build_phrases(words), words, {'topic':'housing'}, discover=discover, progress=lambda _:None)
        self.assertEqual(len(slots), len(batches))
        self.assertGreater(slots[-1].start, 800)
        self.assertTrue(all(1 <= count <= 12 for _, count in calls))

    def test_interruption_resumes_only_unfinished_window_and_preserves_exact_slots(self):
        words = speech(400)
        calls = []
        fail = [True]
        def discover(llm, phrases, batch, summary, count, brief, progress):
            calls.append(batch[0].text)
            if len(calls) == 2 and fail[0]:
                raise TimeoutError('temporary inference interruption')
            return [Slot(Moment(phrases[0].id, 'room', ['room']), batch[0].start,
                         batch[0].end, batch[0].text)]
        temporary_root = Path(__file__).resolve().parents[1]/'cache/test-broll-windows'
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
            checkpoint = Path(directory)/'windows.json'
            args = (None, build_phrases(words), words, {'topic':'housing'})
            with self.assertRaises(TimeoutError):
                discover_bounded(*args, checkpoint=checkpoint, discover=discover, progress=lambda _:None)
            fail[0] = False
            result = discover_bounded(*args, checkpoint=checkpoint, discover=discover, progress=lambda _:None)
            self.assertEqual(calls.count('word0'), 1)
            self.assertEqual(result[0].start, 0)
            self.assertEqual(result[-1].start, list(speech_windows(words))[-1][0].start)
            before = len(calls)
            discover_bounded(*args, checkpoint=checkpoint, discover=discover, progress=lambda _:None)
            self.assertEqual(len(calls), before)
            discover_bounded(None, build_phrases(words), words, {'topic':'changed'},
                             checkpoint=checkpoint, discover=discover, progress=lambda _:None)
            self.assertGreater(len(calls), before)

    def test_explicit_total_is_distributed_instead_of_repeated_per_window(self):
        words = speech()
        budgets = []
        def discover(llm, phrases, batch, summary, count, brief, progress):
            budgets.append(count)
            return []
        discover_bounded(None, build_phrases(words), words, {}, count=30, discover=discover, progress=lambda _:None)
        self.assertEqual(sum(budgets), 30)


if __name__ == '__main__':
    unittest.main()
