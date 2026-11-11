import unittest
from unittest.mock import Mock, patch
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
    def test_uroman_nasal_negation_is_preserved_but_removed_negation_is_blocked(self):
        from hinglish_semantic.core import fact_concerns
        self.assertNotIn('negation_needs_review',fact_concerns('Bhai nahi thi','bhaaii nahiim thii'))
        self.assertIn('negation_needs_review',fact_concerns('Bhai nahi thi','bhaaii thii'))
        self.assertNotIn('negation_needs_review',fact_concerns('Na hi karun toh better hai','nahiim karanaa to bettar hai'))
        self.assertIn('negation_needs_review',fact_concerns('Na hi karun','karun'))

    def test_spoken_initials_are_retrieved_without_a_scene_specific_word_list(self):
        from hinglish_semantic.coverage import word_similarity,text_evidence
        self.assertGreater(word_similarity('ac','esii'),.9)
        self.assertGreater(word_similarity('tv','ttiivii'),.9)
        self.assertGreater(word_similarity('pg','piijii'),.9)
        self.assertGreater(text_evidence('AC room','esii')['score'],
                           text_evidence('AC room','washing machine nahi')['score'])

    def test_short_answers_are_checked_individually_before_acceptance(self):
        from hinglish_semantic.meaning import arrange_meaning
        t=source([(1,'Fridge nahiim')])
        candidate={'span':span(t,0,len(t.words)),'eligible':False,'source_order':0,
                   'score':.8,'issues':[],'evidence':{'recall':.4,'precision':.4,'content':.4}}
        judge=Mock();judge.compare.side_effect=[
            [{'status':'complete','repeated':False}],
            [{'status':'different','repeated':False}]]
        with patch('hinglish_semantic.meaning.retrieve_phrases',return_value=[[candidate]]):
            rows=arrange_meaning('Wi-Fi? Nahi',[t],SemanticSettings(),Mock(),judge,lambda _:None)
        self.assertEqual(judge.compare.call_count,2)
        self.assertIsNone(rows[0]['selected'])

    def test_isolated_phonetic_cue_requires_local_model_approval(self):
        from hinglish_semantic.meaning import arrange_meaning
        t=source([(1,'baar')])
        for status,accepted in (('complete',True),('different',False)):
            with self.subTest(status=status):
                candidate={'span':span(t,0,1),'eligible':False,'source_order':0,'score':.8,
                           'issues':[],'evidence':{'recall':1.,'precision':1.,'content':1.}}
                judge=Mock();judge.compare.return_value=[{'status':status,'repeated':False}]
                with patch('hinglish_semantic.meaning.retrieve_phrases',return_value=[[candidate]]):
                    rows=arrange_meaning('Bar?',[t],SemanticSettings(),Mock(),judge,lambda _:None)
                self.assertEqual(rows[0]['selected'] is not None,accepted)
                judge.compare.assert_called_once_with('Bar?',['baar'],context='Bar?')

    def test_unrelated_isolated_word_cannot_be_promoted_by_topic(self):
        from hinglish_semantic.meaning import arrange_meaning
        t=source([(1,'car')])
        candidate={'span':span(t,0,1),'eligible':False,'source_order':0,'score':.8,
                   'issues':[],'evidence':{'recall':.3,'precision':1.,'content':.3}}
        judge=Mock()
        with patch('hinglish_semantic.meaning.retrieve_phrases',return_value=[[candidate]]):
            rows=arrange_meaning('Bar?',[t],SemanticSettings(),Mock(),judge,lambda _:None)
        self.assertIsNone(rows[0]['selected'])
        judge.compare.assert_not_called()

    def test_conflicting_batch_retakes_are_rechecked_before_preferring_latest(self):
        from hinglish_semantic.meaning import arrange_meaning
        t=source([(1,'The room felt different.'),(10,'The room felt different.')])
        pool=[{'span':span(t,a,b),'eligible':False,'source_order':0,'score':.8,
               'issues':[],'evidence':{'recall':.6,'precision':1.,'content':.6}}
              for a,b in ((0,4),(4,8))]
        for final_status,expected_first in (('complete',4),('partial',0)):
            with self.subTest(final_status=final_status):
                judge=Mock();judge.compare.side_effect=[
                    [{'status':'complete','repeated':False},{'status':'partial','repeated':False}],
                    [{'status':'complete','repeated':False}],
                    [{'status':final_status,'repeated':False}]]
                # Low reference recall deliberately avoids the existing lexical
                # recheck. The inconsistency between retakes is the trigger.
                candidates=[{**c,'evidence':dict(c['evidence']),'issues':[]} for c in pool]
                with patch('hinglish_semantic.meaning.retrieve_phrases',return_value=[candidates]):
                    rows=arrange_meaning('Looking back the room felt different',[t],
                                         SemanticSettings(),Mock(),judge,lambda _:None)
                self.assertEqual(judge.compare.call_count,3)
                self.assertEqual(rows[0]['selected']['span'].first,expected_first)

    def test_one_passage_can_cover_adjacent_clauses_only_after_joint_model_verification(self):
        from hinglish_semantic.shared_passages import verify_shared_passages
        t=source([(1,'Next episode. Watch closely.')])
        c={'span':span(t,0,len(t.words)),'eligible':True}
        rows=[{'index':0,'paragraph_index':0,'idea':'Next episode.','selected':c,'alternatives':[c],'issues':[]},
              {'index':1,'paragraph_index':0,'idea':'Watch closely.','selected':None,'alternatives':[c],'issues':['sentence_not_matched']}]
        for status,count in [('complete',1),('partial',2)]:
            judge=Mock();judge.compare.return_value=[{'status':status,'repeated':False}]
            result=verify_shared_passages(rows,judge,SemanticSettings())
            self.assertEqual(len(result),count)
            judge.compare.assert_called_once_with('Next episode. Watch closely.',[c['span'].text])
            if status=='complete':self.assertEqual(result[0]['joined_requirements'],['Next episode.','Watch closely.'])

    def test_reference_heading_and_camera_notes_are_not_spoken_requirements(self):
        text=('Season 1, Episode 3\nEpisode title\nApproximate reference; do not invent narration.\n'
              '[A-Cam, sarcastic tone]\n“Toh flat nahi mila, PG le liya.”\n'
              '[Cut to bed]\n“Bed. Bed mast hai.”')
        units=meaning_units(text)
        self.assertEqual([u['idea'] for u in units],['Toh flat nahi mila, PG le liya.','Bed Bed mast hai.'])

    def test_containing_passage_recovers_clause_only_after_joint_model_verification(self):
        from hinglish_semantic.shared_passages import verify_shared_passages
        t=source([(1,'Book a ride. Pay extra.')])
        whole={'span':span(t,0,len(t.words)),'eligible':True}
        for selected_left in (True,False):
            chosen={'span':span(t,0,3) if selected_left else span(t,3,len(t.words)),'eligible':True}
            rows=[{'index':0,'paragraph_index':0,'idea':'Book a ride.',
                   'selected':chosen if selected_left else None,'alternatives':[whole],
                   'issues':[] if selected_left else ['sentence_not_matched']},
                  {'index':1,'paragraph_index':0,'idea':'Pay extra.',
                   'selected':None if selected_left else chosen,'alternatives':[whole],
                   'issues':['sentence_not_matched'] if selected_left else []}]
            for status,count in (('complete',1),('partial',2)):
                with self.subTest(selected_left=selected_left,status=status):
                    judge=Mock();judge.compare.return_value=[{'status':status,'repeated':False}]
                    result=verify_shared_passages(rows,judge,SemanticSettings())
                    self.assertEqual(len(result),count)
                    judge.compare.assert_called_once_with('Book a ride. Pay extra.',[whole['span'].text])
                    if status=='complete':
                        self.assertEqual(result[0]['selected']['span'].id,whole['span'].id)
                        self.assertNotIn('sentence_not_matched',result[0]['issues'])

    def test_containing_passage_cannot_replay_words_selected_by_another_row(self):
        from hinglish_semantic.shared_passages import verify_shared_passages
        t=source([(1,'Open map. Book ride. Pay extra.')])
        whole={'span':span(t,0,6),'eligible':True}
        rows=[{'index':0,'paragraph_index':0,'idea':'Open map.','selected':None,
               'alternatives':[whole],'issues':['sentence_not_matched']},
              {'index':1,'paragraph_index':0,'idea':'Book ride.',
               'selected':{'span':span(t,2,4)},'alternatives':[],'issues':[]},
              {'index':2,'paragraph_index':0,'idea':'Pay extra.',
               'selected':{'span':span(t,4,6)},'alternatives':[],'issues':[]}]
        judge=Mock()
        result=verify_shared_passages(rows,judge,SemanticSettings())
        self.assertEqual(len(result),3)
        self.assertIsNone(result[0]['selected'])
        judge.compare.assert_not_called()

    def test_plain_script_and_unquoted_dialogue_after_camera_note_are_preserved(self):
        from hinglish_semantic.core import script_ideas
        self.assertEqual(script_ideas('Unquoted opening.\nUnquoted ending.'),['Unquoted opening.','Unquoted ending.'])
        self.assertEqual(script_ideas('[Camera]\n“Quoted opening.”\nUnquoted ending.'),['Quoted opening.','Unquoted ending.'])

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

    def test_unpunctuated_clauses_get_compact_candidates_without_losing_long_ones(self):
        t=source([(1,'The shop was not open'),(2.24,'please wait outside')])
        # A 0.32 s reliable pause must offer the independent positive clause;
        # including the previous negation used to block its verified match.
        texts={s.text for s in phrase_spans(t)}
        self.assertIn('please wait outside',texts)
        self.assertIn('The shop was not open please wait outside',texts)
        t=source([(1,'Ten fifteen minutes extra'),(1.88,'every order')])
        texts={s.text for s in phrase_spans(t)}
        self.assertIn('Ten fifteen minutes extra',texts)
        self.assertIn('every order',texts)
        self.assertIn('Ten fifteen minutes extra every order',texts)

    def test_hindi_spoken_counts_and_ranges_match_digits_but_changed_counts_do_not(self):
        from hinglish_semantic.core import fact_concerns
        self.assertNotIn('numbers_need_review',fact_concerns('2 call 3 call 4 call','Do call tin call chaar call'))
        self.assertNotIn('numbers_need_review',fact_concerns('10-15 minute extra','Das pandrah minute extra'))
        self.assertIn('numbers_need_review',fact_concerns('2 calls','Do orders and three calls'))
        self.assertIn('numbers_need_review',fact_concerns('Pay 40 extra','Pay 60 extra'))

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
