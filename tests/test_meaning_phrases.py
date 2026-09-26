import unittest
from hinglish_cut.model import Media, Transcript, Word
from hinglish_semantic.core import SemanticSettings, choose_sequence
from hinglish_semantic.coverage import span
from hinglish_semantic.meaning import meaning_units, phrase_spans, prefer_latest, apply_verdict, retrieve_phrases
from hinglish_semantic.local_judge import expand_result, validate_result


def source(parts):
    words = [Word(w, start + .2*i, start + .2*i + .12, .9, True)
             for start, text in parts for i, w in enumerate(text.split())]
    return Transcript(Media('source', 'source.mp4', 100, '30', 1920, 1080, 2, 48000), words,
                      [(w.start, w.end) for w in words], [])


class MeaningPhraseTests(unittest.TestCase):
    def test_emphatic_chain_and_conditional_are_not_four_unrelated_matches(self):
        units = meaning_units('Extra do, warna cancel. Har. Single. Ride. Pe.')
        self.assertEqual(len(units), 2)
        self.assertIn('warna cancel', units[0]['idea'])
        self.assertEqual(units[1]['idea'], 'Har Single Ride Pe.')

    def test_questions_and_answers_keep_their_context(self):
        units = meaning_units('Mana kar diya? Cancel. Doosra rider same scene.\nEnglish? Hindi? Bhool jao.')
        self.assertEqual(len(units), 3)
        self.assertEqual(units[0]['idea'], 'Mana kar diya? Cancel')
        self.assertTrue(units[2]['idea'].startswith('English? Hindi?'))

    def test_comma_fragments_stay_one_sentence_for_retake_selection(self):
        units = meaning_units('Socha chalo, PG mein toh basic cheezein hongi hi.')
        self.assertEqual([u['idea'] for u in units],
                         ['Socha chalo, PG mein toh basic cheezein hongi hi.'])

    def test_repeated_short_cue_stays_with_its_explanation(self):
        units = meaning_units('Chair? Chair ka character assassination nahi karunga. Bed. Bed mast hai.')
        self.assertEqual([u['idea'] for u in units], [
            'Chair? Chair ka character assassination nahi karunga',
            'Bed Bed mast hai.',
        ])

    def test_expressive_pauses_keep_complete_predicate_options(self):
        t = source([(1, 'Doosra rider same scene,'), (3, 'Teesra'), (4, 'same,'), (5, 'Chautha'), (6, 'same.')])
        texts = {s.text for s in phrase_spans(t)}
        self.assertIn('Teesra same,', texts)
        self.assertIn('Chautha same.', texts)
        self.assertIn('Doosra rider same scene,', texts)

    def test_phrase_boundaries_are_independent_of_script_words(self):
        t = source([(1, 'Booking a taxi is'), (2.5, 'a painful struggle.')])
        candidates = phrase_spans(t)
        self.assertIn('Booking a taxi is a painful struggle.', {s.text for s in candidates})
        self.assertNotIn('Booking a taxi', {s.text for s in candidates})

    def test_coarse_alignment_does_not_create_false_word_precision(self):
        t = source([])
        t.words = [Word(w, 0, 8, 0, False) for w in 'some uncertain speech. more speech'.split()]
        self.assertEqual(len(phrase_spans(t)), 1)

    def test_latest_complete_take_wins_and_incomplete_later_does_not(self):
        t = source([(1, 'Yahan ride book karna mushkil hai.'),
                    (8, 'Yahan ride book karna mushkil hai.'), (15, 'Yahan ride')])
        pool = [{'span': span(t, a, b), 'eligible': ok, 'source_order': 0, 'issues': [], 'score': .9}
                for a, b, ok in [(0, 6, True), (6, 12, True), (12, 14, False)]]
        prefer_latest([{'idea': 'Taxi ki booking kaafi difficult hoti hai.'}], [pool], SemanticSettings())
        self.assertFalse(pool[0]['eligible'])
        self.assertTrue(pool[1]['eligible'])
        self.assertFalse(pool[2]['eligible'])

    def test_last_complete_take_wins_across_separate_files(self):
        a = source([(1, 'Socha chalo PG mein basic cheezein hongi.')])
        b = source([(1, 'Socha PG mein basic cheezein hongi.')])
        b.media.id = 'later'; b.media.path = 'later.mp4'
        pools = [[{'span': span(a, 0, len(a.words)), 'eligible': True, 'source_order': 0,
                   'issues': [], 'score': .99},
                  {'span': span(b, 0, len(b.words)), 'eligible': True, 'source_order': 9,
                   'issues': [], 'score': .80}]]
        prefer_latest([{'idea': 'Socha chalo, PG mein basic cheezein hongi.'}], pools, SemanticSettings())
        self.assertFalse(pools[0][0]['eligible'])
        self.assertTrue(pools[0][1]['eligible'])

    def test_model_cannot_fabricate_source_id(self):
        with self.assertRaises(ValueError):
            expand_result({'complete': [6], 'partial': [], 'repeated': [], 'reason': 'x'}, 2)
        with self.assertRaises(ValueError):
            expand_result({'complete': [0], 'partial': [0], 'repeated': [], 'reason': 'x'}, 2)

    def test_unclear_spoken_amount_is_flagged_but_changed_amount_is_blocked(self):
        yes = {'status': 'complete', 'repeated': False, 'reason': 'x'}
        for text, allowed in [('Price saath rupe hai.', True), ('Price 40 rupees hai.', False)]:
            t = source([(1, text)])
            c = {'span': span(t, 0, len(t.words)), 'evidence': {'recall': .85}}
            apply_verdict('Price 60 rupees hai.', c, yes, SemanticSettings())
            self.assertEqual(c['eligible'], allowed)
            self.assertTrue(c['issues'])

    def test_emphatic_phrase_ending_in_preposition_is_not_filtered_out(self):
        import numpy as np
        class Encoder:
            def encode(self, texts, progress): return np.ones((len(texts), 4), dtype=np.float32) / 2
        t = source([(1, 'Her single ride par.')])
        pools = retrieve_phrases(meaning_units('Har. Single. Ride. Pe.'), [t], SemanticSettings(), Encoder(), lambda _: None)
        self.assertIn('Her single ride par.', [c['span'].text for c in pools[0]])

    def test_numbered_occurrence_cannot_replace_every_occurrence(self):
        t = source([(1, 'Doosra rider same scene.')])
        c = {'span': span(t, 0, len(t.words)), 'evidence': {'recall': .3}}
        apply_verdict('Har single ride pe.', c, {'status': 'complete', 'repeated': False}, SemanticSettings())
        self.assertFalse(c['eligible'])

    def test_unverified_and_overlapping_candidates_are_not_forced_into_sequence(self):
        t = source([(1, 'one two three four five')])
        a = {'span': span(t, 0, 4), 'eligible': True, 'score': .9}
        b = {'span': span(t, 3, 5), 'eligible': True, 'score': .8}
        c = {'span': span(t, 0, 1), 'eligible': False, 'score': 1}
        selected, _ = choose_sequence([[a], [b], [c]], SemanticSettings())
        self.assertEqual(sum(c is not None for c in selected), 1)

    def test_long_transcript_candidate_count_is_linear(self):
        t = source([(i*2, 'This is a complete thought.') for i in range(2000)])
        candidates = phrase_spans(t)
        self.assertLessEqual(len(candidates), 6*len(t.words))
        self.assertTrue(all(s.end - s.start <= 35 for s in candidates))


if __name__ == '__main__': unittest.main()
