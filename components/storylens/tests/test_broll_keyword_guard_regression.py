"""Initial red reproductions for job 7c03db6fbd88; no real model or media calls.

Scripted answers exercise the real discovery/guard/receipt path. They are test
inputs, never generated footage decisions or evidence of runtime acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hinglish_broll.keywords import discover
from hinglish_broll.phrases import Phrase
from hinglish_cut.model import Word
from hinglish_eval import guard


FIXTURES = Path(__file__).parent / 'fixtures' / 'broll-keyword-guard'


class KeywordGuardRegressionTests(unittest.TestCase):
    def setUp(self):
        # These globals exist only in this isolated test process.
        self.old_journal = guard._journal
        guard._journal = []
        self.addCleanup(setattr, guard, '_journal', self.old_journal)

    def run_discovery(self, word, answers):
        words = [Word(word, 1., 1.4)]
        phrases = [Phrase(0, 1., 1.4, word)]
        llm = Mock()
        llm.json.side_effect = [copy.deepcopy(answer) for answer in answers]
        messages = []
        with patch.object(guard.tune, 'feedback', return_value=[]):
            slots = discover(llm, phrases, words, {}, 1, '', messages.append)
        temporary_root = (FIXTURES.parents[2] / 'output' / 'component-tests' /
                          'broll-keyword-guard').resolve()
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as folder:
            # Keep automatic recursive cleanup within this test-owned root.
            self.assertTrue(Path(folder).resolve().is_relative_to(temporary_root))
            guard.save(folder)
            reports = json.loads((Path(folder) / 'model-checks.json').read_text(encoding='utf-8'))
        return llm, slots, reports[-1], messages

    @staticmethod
    def answer(keyword, queries, meaning='Illustrative footage of the spoken venue.'):
        return {'keywords': [{'word_index': 0, 'keyword': keyword,
                              'queries': queries, 'identity': '', 'meaning': meaning}]}

    def test_observed_raw_model_fixture_is_preserved_verbatim(self):
        provenance = json.loads((FIXTURES / 'provenance.json').read_text(encoding='utf-8'))
        raw = (FIXTURES / 'observed-keyword-answer.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), provenance['source_sha256'])
        answer = json.loads(raw)
        wardrobe = next(r for r in answer['keywords'] if r['word_index'] == 52)
        self.assertEqual(wardrobe['keyword'], 'wardrobe missing')
        self.assertIn('lack of', wardrobe['meaning'])

    def test_physical_search_with_observed_absence_explanation_needs_no_retry(self):
        raw = json.loads((FIXTURES / 'observed-keyword-answer.json').read_text(encoding='utf-8'))
        row = copy.deepcopy(next(r for r in raw['keywords'] if r['word_index'] == 52))
        # Explicitly normalize the search fields only; preserve the model's
        # explanatory meaning. Test-local index is unrelated to source timing.
        row.update(word_index=0, keyword='wardrobe', queries=['wardrobe'])
        answer = {'keywords': [row]}
        llm, slots, report, messages = self.run_discovery('almaari', [answer] * 3)
        self.assertEqual([s.moment.visual for s in slots], ['wardrobe'])
        self.assertEqual(llm.json.call_count, 1,
                         'A valid physical query must not be retried for its explanation.')
        self.assertEqual(report['final_hard'], 0)
        self.assertFalse(any('broke' in m for m in messages))

    def test_actual_negative_keyword_is_returned_to_model_before_acceptance(self):
        bad = self.answer('no club', ['no club'])
        good = self.answer('nightclub interior', ['nightclub interior'])
        llm, slots, report, _ = self.run_discovery('club', [bad, good])
        self.assertEqual(llm.json.call_count, 2)
        correction = llm.json.call_args_list[1].args[1]
        self.assertTrue(correction['fix_these_problems'])
        self.assertEqual([s.moment.visual for s in slots], ['nightclub interior'])
        self.assertEqual(report['tries'][0]['hard'], 1)
        self.assertEqual(report['final_hard'], 0)

    def test_actual_negative_query_is_checked_even_when_keyword_is_physical(self):
        bad = self.answer('nightclub interior', ['lack of nightlife'])
        good = self.answer('nightclub interior', ['nightclub interior'])
        llm, slots, report, _ = self.run_discovery('club', [bad, good])
        self.assertEqual(llm.json.call_count, 2)
        self.assertEqual(report['tries'][0]['hard'], 1)
        self.assertEqual(report['final_hard'], 0)
        self.assertEqual(slots[0].moment.queries, ['nightclub interior', 'nightclub'])

    def test_final_receipt_validates_repaired_search_not_three_stale_explanations(self):
        # Synthetic stubborn response forces the existing bounded repair path.
        bad = self.answer('no club', ['no club'], 'The lack of nightlife in the area.')
        llm, slots, report, _ = self.run_discovery('club', [bad] * 3)
        self.assertEqual(llm.json.call_count, 3)
        self.assertEqual([s.moment.visual for s in slots], ['nightclub interior'])
        self.assertEqual([t['hard'] for t in report['tries']], [1, 1, 1])
        self.assertEqual(report['final_hard'], 0,
                         'Historical failures remain in tries, not as duplicate final errors.')
        self.assertEqual(report['final_problems'], [])

    def test_closed_shops_physical_state_remains_allowed(self):
        answer = self.answer('closed shops', ['closed shops', 'shop shutters closed'])
        llm, slots, report, _ = self.run_discovery('shops', [answer])
        self.assertEqual(llm.json.call_count, 1)
        self.assertEqual(slots[0].moment.visual, 'closed shops')
        self.assertEqual(report['final_hard'], 0)

    def test_household_list_pan_is_quarantined_until_model_resolves_its_sense(self):
        words=[Word(text,i*.4,i*.4+.3) for i,text in enumerate(['almaari','geyser','pan','fridge'])]
        phrases=[Phrase(0,0,1.5,'almaari geyser pan fridge')]
        bad=self.answer('pan',['pan','frying pan'],'A cooking utensil')
        good=self.answer('ceiling fan',['ceiling fan'],'A household fan; pan is a phonetic recognition error here.')
        bad['keywords'][0]['word_index']=good['keywords'][0]['word_index']=2
        llm=Mock();llm.json.side_effect=[bad,good]
        with patch.object(guard.tune,'feedback',return_value=[]):
            slots=discover(llm,phrases,words,{'topic':'rented housing'},1,progress=lambda _:None)
        self.assertEqual(llm.json.call_count,2)
        self.assertEqual([s.moment.visual for s in slots],['ceiling fan'])
        self.assertAlmostEqual(slots[0].start,.8)

    def test_unresolved_household_pan_never_becomes_a_cooking_video_search(self):
        words=[Word(text,i*.4,i*.4+.3) for i,text in enumerate(['almaari','geyser','pan','fridge'])]
        bad=self.answer('pan',['pan','frying pan']);bad['keywords'][0]['word_index']=2
        llm=Mock();llm.json.side_effect=[copy.deepcopy(bad) for _ in range(3)]
        with patch.object(guard.tune,'feedback',return_value=[]):
            slots=discover(llm,[Phrase(0,0,1.5,'almaari geyser pan fridge')],words,{},1,progress=lambda _:None)
        self.assertEqual(slots,[])

    def test_actual_cooking_pan_is_preserved(self):
        answer=self.answer('frying pan',['frying pan'],'A cooking utensil')
        llm,slots,_,_=self.run_discovery('pan',[answer])
        self.assertEqual(llm.json.call_count,1)
        self.assertTrue(slots)

    def test_wardrobe_search_keeps_three_physical_synonyms(self):
        from hinglish_broll.keywords import physical_keyword
        term,queries=physical_keyword({'keyword':'wardrobe','queries':['wardrobe','closet interior','clothes cupboard']},'almaari','no furniture in the room')
        self.assertEqual(term,'wardrobe')
        self.assertEqual(len(queries),3)
        self.assertIn('closet interior',queries)
        self.assertIn('clothes cupboard',queries)


if __name__ == '__main__':
    unittest.main()
