from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_cut.model import Media, Word, Transcript
from hinglish_cut.demo import create_demo_media
from hinglish_cut.media import probe, extract_audio
from hinglish_semantic.core import (SemanticSettings, Span, spans_for, script_ideas, fact_concerns,
                                   choose_sequence, cleanup_proposals, cleanup_verdict, verified)
from hinglish_semantic.cleanup import assess_cleanup, cleanup_cuts, verify_cleanup_audio
from hinglish_semantic.models import parse_verdict
from hinglish_semantic.pipeline import emit_assembly, portable_sources, apply_choices
from hinglish_semantic.assembly import verify_candidates


PASS = {'equivalent': True, 'complete': True, 'contradiction': False, 'confidence': .98,
        'safe_to_remove': True, 'reason': 'Test fixture approval'}


def transcript(parts):
    words = []
    for start, text in parts:
        for i, word in enumerate(text.split()):
            words.append(Word(word, start + i * .35, start + i * .35 + .20, .9, True))
    m = Media('a', 'test.mp4', 120, '30', 320, 180, 1, 48000)
    return Transcript(m, words, [(w.start, w.end) for w in words], [])


def candidate(id, media, start, end, score=.9):
    return {'span': Span(id, media, start, end, float(start), float(end), 'spoken words', 'context', True),
            'score': score, 'similarity': score, 'eligible': True, 'issues': []}


class SemanticTests(unittest.TestCase):
    def test_newline_ideas_keep_emphasis_together(self):
        self.assertEqual(script_ideas('Har. Single. Ride.\n\nRider asks extra.'),
                         ['Har. Single. Ride.', 'Rider asks extra.'])

    def test_new_settings_have_no_old_script_specific_aliases(self):
        aliases = SemanticSettings().speech_settings().aliases
        self.assertNotIn('saath', aliases)
        self.assertNotIn('se', aliases)
        self.assertNotIn('do', aliases)

    def test_numbers_and_negation_guard(self):
        self.assertIn('numbers_need_review', fact_concerns('Price 60 rupees', 'Price 40 rupees'))
        self.assertNotIn('numbers_need_review', fact_concerns('Price 60 rupees', 'Price sixty rupees'))
        self.assertIn('negation_needs_review', fact_concerns('Main nahi jaunga', 'Main jaunga'))
        self.assertEqual(fact_concerns('mere saath aao', 'come with me'), [])
        self.assertEqual(fact_concerns('2 baar', 'do baar'), [])
        self.assertIn('negation_needs_review', fact_concerns('मैं नहीं जाऊँगा', 'मैं जाऊँगा'))
        self.assertIn('negation_needs_review', fact_concerns("I don't edit videos", 'I edit videos'))

    def test_protected_terms_not_substring_matched(self):
        self.assertIn('protected_term_missing:Ram', fact_concerns('Ram paid', 'Ramesh paid', ['Ram']))

    def test_changed_pronoun_roles_require_review(self):
        for expected, actual in [
            ('Rider mujhse paise maangta hai', 'Main rider se paise maangta hoon'),
            ('She called me', 'I called her'),
            ('Ravi aapko paise deta hai', 'Aap Ravi ko paise dete hain'),
        ]:
            self.assertIn('participant_roles_need_review', fact_concerns(expected, actual))
        self.assertEqual(fact_concerns('Log mujhse sawal karte hain', 'Log mujhe poochhate hain'), [])

    def test_cleanup_safety_gate_keeps_reactions_and_incomplete_retakes(self):
        settings = SemanticSettings()
        self.assertTrue(cleanup_verdict('filler', PASS, settings, target='um'))
        self.assertFalse(cleanup_verdict('filler', PASS, settings, target='oh'))
        self.assertTrue(cleanup_verdict('retake', PASS, settings, earlier='aaj hum editing seekhenge',
                                        later='aaj hum editing seekhenge'))
        self.assertFalse(cleanup_verdict('retake', PASS, settings,
                                         earlier='editing aur color correction seekhenge',
                                         later='editing aur...'))
        self.assertFalse(cleanup_verdict('retake', PASS, settings,
                                         earlier='rider paise maangta aur ride cancel karta hai',
                                         later='rider paise maangta hai'))

    def test_strict_verifier_does_not_turn_bad_json_into_approval(self):
        for value in ('{}', '```oops```', json.dumps({**PASS, 'equivalent': 'true'}),
                      json.dumps({**PASS, 'reason': ''}),
                      json.dumps({**PASS, 'confidence': float('nan')})):
            with self.assertRaises((ValueError, TypeError)):
                parse_verdict(value)

    def test_high_similarity_cannot_override_negation_or_rejection(self):
        pool = [[candidate('a', 'a', 0, 6)]]
        pool[0][0]['issues'] = ['negation_needs_review']
        class Fake:
            def check(self, *a, **k): return PASS
        verify_candidates(['nahi'], pool, Fake(), SemanticSettings(), lambda x: None)
        self.assertFalse(pool[0][0]['eligible'])

    def test_single_video_must_progress_forward(self):
        pools = [[candidate('late', 'a', 50, 60)], [candidate('early', 'a', 0, 10)]]
        chosen, _ = choose_sequence(pools, SemanticSettings(), single_source=True)
        self.assertEqual(sum(c is not None for c in chosen), 1)

    def test_chunks_can_reorder_across_files(self):
        pools = [[candidate('b', 'b', 50, 60)], [candidate('a', 'a', 0, 10)]]
        chosen, _ = choose_sequence(pools, SemanticSettings(), single_source=False)
        self.assertEqual([c['span'].id for c in chosen], ['b', 'a'])

    def test_same_source_words_cannot_be_reused(self):
        pools = [[candidate('same', 'a', 0, 8)], [candidate('same', 'a', 0, 8)]]
        chosen, _ = choose_sequence(pools, SemanticSettings())
        self.assertEqual(sum(c is not None for c in chosen), 1)

    def test_distinct_repeated_occurrences_are_flagged(self):
        chosen, ambiguous = choose_sequence([[candidate('one', 'a', 0, 5), candidate('two', 'a', 30, 35)]], SemanticSettings())
        self.assertEqual(ambiguous, [0])

    def test_whole_sequence_resolves_wrong_occurrence(self):
        pools = [[candidate('too-late', 'a', 80, 90, .91), candidate('right', 'a', 0, 10, .90)],
                 [candidate('next', 'a', 20, 30, .9)]]
        chosen, _ = choose_sequence(pools, SemanticSettings(), True)
        self.assertEqual(chosen[0]['span'].id, 'right')

    def test_spans_keep_original_times_and_coarse_word_group(self):
        t = transcript([(0, 'aaj hum editing seekhenge.'), (8, 'ab project kholna hai.')])
        s = spans_for(t)
        self.assertTrue(any(x.start == 8 for x in s))
        t.words = [Word('a', 0, 25, 0, False), Word('b', 0, 25, 0, False)]
        s = spans_for(t)
        self.assertEqual((s[0].first, s[0].last, s[0].aligned), (0, 2, False))

    def test_meaningful_oh_and_shh_are_review_only(self):
        t = transcript([(0, 'oh tum yahan ho shh chup raho')])
        proposals = cleanup_proposals(t, SemanticSettings())
        self.assertEqual(len(proposals), 2)
        self.assertTrue(all(not p['eligible'] for p in proposals))

    def test_unaligned_filler_cannot_be_deleted(self):
        t = transcript([(0, 'aaj um hum editing seekhenge')])
        t.words[1].aligned = False
        self.assertFalse(cleanup_proposals(t, SemanticSettings())[0]['eligible'])

    def test_three_confirmed_retakes_keep_last(self):
        text = 'aaj hum video editing ka kaam seekhenge.'
        t = transcript([(0, text), (4, text), (8, text)])
        class Fake:
            def check(self, *a, **k): return PASS
        proposals = assess_cleanup(t, SemanticSettings(), Fake(), lambda x: None)
        accepted = [p for p in proposals if p['approved']]
        self.assertEqual(len(accepted), 2)
        base, cuts = cleanup_cuts(t, SemanticSettings(), proposals)
        self.assertTrue(cuts)
        self.assertTrue(any(c.start_frame / 30 <= 8 and c.end_frame / 30 > 10 for c in cuts))
        self.assertFalse(any(c.start_frame / 30 <= 1 < c.end_frame / 30 for c in cuts))
        self.assertEqual(len(cuts), 1)

    def test_same_idea_later_is_not_automatically_a_retake(self):
        text = 'aaj hum video editing ka kaam seekhenge.'
        t = transcript([(0, text), (70, text)])
        self.assertEqual(cleanup_proposals(t, SemanticSettings()), [])

    def test_cached_json_speech_can_mix_with_word_boundaries(self):
        t = transcript([(0, 'aaj hum video editing seekhenge.')])
        t.speech = json.loads(json.dumps(t.speech))
        base, cuts = cleanup_cuts(t, SemanticSettings(), [])
        self.assertTrue(cuts)
        self.assertEqual(base, cuts)

    def test_short_emphasis_not_a_retake(self):
        t = transcript([(0, 'har single ride.'), (3, 'har single ride.')])
        self.assertEqual(cleanup_proposals(t, SemanticSettings()), [])

    def test_incomplete_last_take_is_kept_for_review(self):
        text = 'aaj hum video editing ka kaam seekhenge.'
        t = transcript([(0, text), (4, text)])
        class Fake:
            def check(self, *a, **k): return {**PASS, 'complete': False}
        proposals = assess_cleanup(t, SemanticSettings(), Fake(), lambda x: None)
        self.assertFalse(any(p['approved'] for p in proposals))

    def test_assembly_exports_portable_xml_and_manual_alternative(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            create_demo_media(root / 'raw.mp4', 3)
            m = probe(root / 'raw.mp4')
            extract_audio(m, root / 'raw.wav')
            t = Transcript(m, [Word('hello', .3, .7, .9), Word('world', 1, 1.4, .9)], [(.3, .7), (1, 1.4)], [])
            c = {'span': Span('first', m.id, 0, 2, .3, 1.4, 'hello world', 'hello world', True),
                 'score': .9, 'similarity': .9, 'eligible': True, 'issues': [], 'verdict': PASS}
            rows = [{'index': 0, 'idea': 'greeting', 'selected': c, 'alternatives': [c], 'issues': []}]
            output = root / 'output' / 'phase2' / 'test'
            output.mkdir(parents=True)
            wavs = portable_sources(output, [t], {m.id: root / 'raw.wav'})
            result = emit_assembly(output, rows, [t], wavs, SemanticSettings(), 'youtube_horizontal', [],
                                   lambda x: None, replay=False, root=root)
            self.assertTrue((output / 'draft.xml').exists())
            self.assertIn('Save reviewed choices', (output / 'report.html').read_text())
            choices = root / 'choices.json'
            choices.write_text(json.dumps({'project': str(output / 'project.json'), 'kind': 'assemble', 'choices': {'0': 'first'}}))
            second, _ = apply_choices(root, choices, lambda x: None)
            self.assertTrue((second / 'reviewed.xml').exists())
            self.assertNotEqual(second, output)


if __name__ == '__main__':
    unittest.main()
