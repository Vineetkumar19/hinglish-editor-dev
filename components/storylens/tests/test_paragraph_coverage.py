"""Regression checks for paragraph loss, duplicated takes and actual exports."""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import av
import numpy as np

from hinglish_cut.model import Media, Word, Transcript
from hinglish_cut.demo import create_demo_media
from hinglish_cut.media import probe, extract_audio
from hinglish_semantic.core import SemanticSettings, cleanup_verdict, fact_concerns, choose_sequence
from hinglish_semantic.coverage import arrange_paragraphs, normalized, clauses, span, retain_contextual_passages
from hinglish_semantic.paragraph_export import emit_paragraphs, cuts_for_rows
from hinglish_semantic.pipeline import portable_sources, apply_choices


def speech(media_id, parts):
    words = [Word(w, start + i * .35, start + i * .35 + .20, .9, True)
             for start, text in parts for i, w in enumerate(text.split())]
    return Transcript(Media(media_id, media_id + '.mp4', 120, '30', 320, 180, 1, 48000),
                      words, [(w.start, w.end) for w in words], [])


class ParagraphCoverageTests(unittest.TestCase):
    def arrange(self, text, sources, encoder=None):
        return arrange_paragraphs(text, sources, SemanticSettings(), encoder, lambda _: None)

    def test_touching_words_share_one_rounded_frame_boundary(self):
        t = speech('a', [])
        t.words = [Word('sahi hai', 3.24, 4.38, .9, True), Word('sirf ek', 4.38, 4.86, .9, True)]
        t.speech = [(3.24, 4.86)]
        rows = [{'index': i, 'idea': w.text, 'selected': {'span': span(t, i, i + 1)}}
                for i, w in enumerate(t.words)]
        cuts, _ = cuts_for_rows(rows, [t], SemanticSettings(pacing='tight'))
        self.assertEqual(cuts[0].end_frame, 131)
        self.assertEqual(cuts[0].end_frame, cuts[1].start_frame)
        self.assertAlmostEqual(sum(c.duration for c in cuts) / 30, 1.8666666667)

    def test_natural_pacing_keeps_room_between_clips_and_longer_paragraph_breaks(self):
        a = speech('a', [(1, 'Pehla sentence.')])
        b = speech('b', [(1, 'Doosra sentence.')])
        rows = [{'index': i, 'paragraph_index': 0, 'idea': 'sentence',
                 'selected': {'span': span(t, 0, 2)}} for i, t in enumerate([a, b])]
        tight, _ = cuts_for_rows(rows, [a, b], SemanticSettings(pacing='tight'))
        natural, _ = cuts_for_rows(rows, [a, b], SemanticSettings())
        self.assertGreater(sum(c.duration for c in natural), sum(c.duration for c in tight))
        pause = natural[0].end_frame / 30 - a.words[-1].end + b.words[0].start - natural[1].start_frame / 30
        self.assertGreaterEqual(pause, .53)
        rows[1]['paragraph_index'] = 1
        paragraph, _ = cuts_for_rows(rows, [a, b], SemanticSettings())
        pause = paragraph[0].end_frame / 30 - a.words[-1].end + b.words[0].start - paragraph[1].start_frame / 30
        self.assertGreaterEqual(pause, .8)

    def test_natural_padding_does_not_restore_discarded_neighbor_speech(self):
        t = speech('a', [(1, 'Keep this.'), (1.8, 'Discard this.')])
        rows = [{'index': 0, 'idea': 'Keep this.', 'selected': {'span': span(t, 0, 2)}}]
        cuts, _ = cuts_for_rows(rows, [t], SemanticSettings(pacing='relaxed'))
        self.assertLessEqual(cuts[-1].end_frame / 30, t.words[2].start)
        self.assertGreaterEqual(cuts[-1].end_frame / 30, t.words[1].end)

    def test_attached_sentence_ending_is_preserved_without_swallowing_next_take(self):
        t = speech('a', [])
        t.words = [Word('scam', 1, 1.3, .9, True), Word('bataunga.', 1.36, 1.8, .9, True),
                   Word('Bhai', 2.3, 2.5, .9, True)]
        t.speech = [(1, 1.8), (2.3, 2.5)]
        rows = [{'index': 0, 'idea': 'scam', 'selected': {'span': span(t, 0, 1)}}]
        cuts, _ = cuts_for_rows(rows, [t], SemanticSettings())
        self.assertEqual(rows[0]['restored_ending'], 'bataunga.')
        self.assertGreaterEqual(cuts[-1].end_frame / 30, 1.8)
        self.assertLessEqual(cuts[-1].end_frame / 30, 2.3)

    def test_coarse_overlapping_word_times_are_not_scheduled_twice(self):
        t = speech('a', [])
        t.words = [Word('first', 1, 4, 0, False), Word('second', 1, 4, 0, False)]
        pools = [[{'span': span(t, i, i + 1), 'eligible': True, 'score': .9}] for i in range(2)]
        chosen, _ = choose_sequence(pools, SemanticSettings())
        self.assertEqual(sum(c is not None for c in chosen), 1)

    def test_context_recovery_is_anchored_and_explicitly_unverified(self):
        t = speech('a', [(1, 'Python hai nahin.'), (3, 'Washing machine nahin.')])
        alternative = {'span': span(t, 0, 3), 'similarity': .86, 'issues': []}
        rows = [{'index': 0, 'paragraph_index': 0, 'idea': 'Wi-Fi? Nahi', 'selected': None,
                 'alternatives': [alternative], 'issues': ['sentence_not_matched']},
                {'index': 1, 'paragraph_index': 0, 'idea': 'Washing machine? Nahi',
                 'selected': {'span': span(t, 3, 6)}, 'alternatives': [], 'issues': []}]
        retain_contextual_passages(rows, [t])
        self.assertEqual(rows[0]['selection_status'], 'unverified_context_passage')
        self.assertIn('Uncertain transcript', rows[0]['issues'][0])
        rows[0]['selected'] = None
        alternative['issues'] = ['negation_needs_review']
        retain_contextual_passages(rows, [t])
        self.assertIsNone(rows[0]['selected'])
        alternative['issues'] = []
        rows[1]['paragraph_index'] = 1
        retain_contextual_passages(rows, [t])
        self.assertIsNone(rows[0]['selected'])

    def test_questions_keep_distinct_negative_answers_and_quote_boundaries(self):
        units = clauses('Wi-Fi? Nahi. Washing machine? Nahi. Fridge? Nahi. AC room? Milega, par jugaad se.')
        self.assertEqual([u['idea'] for u in units],
                         ['Wi-Fi? Nahi', 'Washing machine? Nahi', 'Fridge? Nahi', 'AC room?', 'Milega par jugaad se.'])
        quoted = clauses('“Main yahaan nahi rehna chahta.” Chair?')
        self.assertEqual(len(quoted), 2)
        self.assertEqual(quoted[1]['idea'], 'Chair?')
        t = speech('a', [(1, 'Wifi nahi.'), (4, 'Washing machine nahi.'), (8, 'Fridge nahi.')])
        rows = self.arrange('Wifi? Nahi. Washing machine? Nahi. Fridge? Nahi.', [t])
        self.assertTrue(all(r['selected'] is not None for r in rows))
        self.assertEqual([r['selected']['span'].start for r in rows], [1, 4, 8])

    def test_one_paragraph_assembles_multiple_files_in_script_order(self):
        a = speech('a', [(1, 'Camera kholke Instagram reels banata hoon.')])
        b = speech('b', [(1, 'Street light off. Dukanein band.')])
        rows = self.arrange('Dukanein band. Camera kholke Instagram reels banata hoon.', [a, b])
        self.assertEqual([r['selected']['span'].media_id for r in rows], ['b', 'a'])
        self.assertEqual([r['paragraph_index'] for r in rows], [0, 0])

    def test_partial_paragraph_does_not_cover_missing_clause(self):
        a = speech('a', [(1, 'Koi club nahi.')])
        rows = self.arrange('Koi club nahi. Camera kholke Instagram reels banata hoon.', [a])
        self.assertIsNotNone(rows[0]['selected'])
        self.assertIsNone(rows[1]['selected'])

    def test_later_complete_attempt_wins_over_earlier_and_incomplete_last(self):
        phrase = 'Camera kholke Instagram reels banata hoon.'
        a = speech('a', [(1, phrase), (7, phrase), (13, 'Camera kholke...')])
        rows = self.arrange(phrase, [a])
        self.assertEqual(rows[0]['selected']['span'].start, 7)
        cuts, _ = cuts_for_rows(rows, [a], SemanticSettings())
        self.assertTrue(all(6.7 <= c.start_frame / 30 < c.end_frame / 30 < 10 for c in cuts))

    def test_written_and_spoken_number_range_match_but_changed_number_does_not(self):
        expected = 'Highway pe 10–11 baje'
        self.assertFalse(fact_concerns(' '.join(normalized(expected)), ' '.join(normalized('Highway pe das gyaarah baje'))))
        self.assertIn('numbers_need_review', fact_concerns(' '.join(normalized(expected)), ' '.join(normalized('Highway pe das baarah baje'))))

    def test_high_embedding_similarity_alone_cannot_approve_missing_content(self):
        class Encoder:
            def encode(self, texts, progress): return np.ones((len(texts), 1))
        rows = self.arrange('Aaj hum editing ke basics seekhenge.',
                            [speech('a', [(1, 'Is video mein main aapko montage banana sikhaunga.')])], Encoder())
        self.assertIsNone(rows[0]['selected'])
        self.assertTrue(any('meaning_only_candidate_listen_and_choose' in c['issues'] for c in rows[0]['alternatives']))

    def test_explicit_cleanup_veto_is_not_overridden(self):
        verdict = {'equivalent': True, 'complete': True, 'contradiction': False,
                   'confidence': 1, 'safe_to_remove': False}
        self.assertFalse(cleanup_verdict('filler', verdict, SemanticSettings(), target='um'))
        self.assertFalse(cleanup_verdict('retake', verdict, SemanticSettings(), earlier='same words', later='same words'))

    def test_export_and_review_apply_keep_actual_preview_and_xml_in_sync(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            transcripts, wavs = [], {}
            for i, text in enumerate(['Camera kholna hai.', 'Dukaanen band hain.']):
                path = root / f'raw{i}.mp4'
                create_demo_media(path, 3)
                m = probe(path)
                wav = root / f'raw{i}.wav'
                extract_audio(m, wav)
                t = speech(m.id, [(.4, text)])
                t.media = m
                transcripts.append(t); wavs[m.id] = wav
            rows = self.arrange('Dukaanen band hain. Camera kholna hai.', transcripts)
            out = root / 'output' / 'phase2' / 'test'
            out.mkdir(parents=True)
            wavs = portable_sources(out, transcripts, wavs)
            report = emit_paragraphs(out, rows, transcripts, wavs, SemanticSettings(), 'instagram_vertical', [], root,
                                     lambda _: None, replay=False)
            self.assertEqual(report['placed_sentences'], 2)
            xml = ET.parse(out / 'EDITED_SEQUENCE.xml')
            expected = int(xml.findtext('.//sequence/duration'))
            with av.open(str(out / 'preview.mp4')) as video:
                self.assertEqual(sum(1 for _ in video.decode(video=0)), expected)
            choices = root / 'choices.json'
            choices.write_text(json.dumps({'kind': 'assemble', 'project': str(out / 'project.json'), 'choices': {}}))
            reviewed, result = apply_choices(root, choices, lambda _: None)
            self.assertEqual(result['placed_sentences'], 2)
            self.assertTrue((reviewed / 'EDITED_SEQUENCE.xml').exists())
            self.assertTrue((reviewed / 'preview.mp4').exists())
            self.assertNotEqual(reviewed, out)


if __name__ == '__main__':
    unittest.main()
