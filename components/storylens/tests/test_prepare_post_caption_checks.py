"""Caption bounds and evidence attribution; live model validation is separate."""
import unittest
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_source import short_instagram, instagram_word_count, validate_conservative_youtube, instagram_from_words, recovery_themes, validate_caption_acronyms
from hinglish_publish.prepare_post_audit import citation_audit


class CaptionChecks(unittest.TestCase):
    def test_ten_prose_words_with_separate_hashtags_are_kept_exactly(self):
        prose = 'One two three four five six seven eight nine ten'
        result = short_instagram(prose + ' #Cricket #MumbaiIndians #IPL')
        self.assertEqual(result, prose + '\n\n#Cricket #MumbaiIndians #IPL')
        self.assertEqual(instagram_word_count(result), 10)

    def test_eleven_words_are_rejected_instead_of_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, '10 words'):
            short_instagram('One two three four five six seven eight nine ten eleven #Cricket #MI #IPL')

    def test_hashtag_only_draft_is_rejected(self):
        with self.assertRaises(ValueError):
            short_instagram('#Cricket #MI #IPL')

    def test_structured_words_cannot_hide_an_essay_in_one_array_item(self):
        with self.assertRaisesRegex(ValueError, 'single-word'):
            instagram_from_words({'caption_words':['An entire sentence hidden in one item'], 'instagram_hashtags':['Cricket','IPL','MI']})
        self.assertEqual(instagram_from_words({'caption_words':['Mumbai','Indians','take','the','field.'], 'instagram_hashtags':['Cricket','IPL','MI']}),
                         'Mumbai Indians take the field.\n\n#Cricket #IPL #MI')

    def test_noisy_speech_recovery_cannot_publish_garbled_names_or_record_claims(self):
        with self.assertRaisesRegex(ValueError, 'player names'):
            validate_conservative_youtube({'description': 'Karen Pollard played a crucial role.'})
        with self.assertRaisesRegex(ValueError, 'trophy totals'):
            validate_conservative_youtube({'description': 'Mumbai now has equal trophy totals.'})
        draft = {'title': 'Mumbai Indians and Chennai Super Kings', 'description': 'A look at the teams and their contrasting innings.', 'tags': ['MumbaiIndians','Cricket','IPL']}
        self.assertEqual(validate_conservative_youtube(draft), draft)

    def test_cut_off_generated_caption_requests_correction_without_trimming(self):
        for words in [['Netherlands','strategy','and'],['Cooperation','and','strategy','in']]:
            with self.subTest(words=words), self.assertRaisesRegex(ValueError,'complete caption'):
                instagram_from_words({'caption_words':words,'instagram_hashtags':['Cricket','Strategy','Teamwork']})
        # The owner may intentionally use a complete idiom in a manual edit.
        self.assertEqual(short_instagram('All in #Cricket #Strategy #Teamwork'),
                         'All in\n\n#Cricket #Strategy #Teamwork')

    def test_caption_recovery_reasks_local_model_and_preserves_evidence(self):
        from hinglish_publish.prepare_post_source import recover_instagram
        brain=Mock()
        tags=['Netherlands','Cricket','Strategy']
        brain.json.side_effect=[{'caption_words':['Strategy','and'],'instagram_hashtags':tags},
                                {'caption_words':['Strategy','and','communication'],'instagram_hashtags':tags}]
        topic={'title':'Netherlands strategy and communication','description':'The clip discusses strategy and communication.'}
        with patch('hinglish_publish.metadata.review_grounding'):
            result=recover_instagram(brain,topic,'This clip discusses Netherlands strategy and communication.',
                                     {'profile':'cricket'}, {}, lambda _:None)
        self.assertEqual(brain.json.call_count,2)
        data=brain.json.call_args.args[1]
        self.assertEqual(data['checked_topic'],topic)
        self.assertIn('complete caption',data['correction'])
        self.assertTrue(result['instagram_caption'].startswith('Strategy and communication\n'))

    def test_recovery_does_not_import_leadership_from_another_clip(self):
        themes=recovery_themes('CSK batting collapses. Malinga bowling in the final.')
        self.assertIn('batting performance',themes)
        self.assertNotIn('team leadership',themes)
        with self.assertRaisesRegex(ValueError,'does not support'):
            validate_conservative_youtube({'title':'CSK Leadership and Development'},themes)
        with self.assertRaisesRegex(ValueError,'CSP'):
            validate_caption_acronyms('Mumbai beat CSP. #IPL #MI #Cricket','Mumbai Indians and garbled CSP in IPL')

    def test_audit_preserves_source_and_guidance_and_quotes_only_actual_draft(self):
        brain = Mock()
        brain.json.return_value = {'approved': False, 'issues': [{'draft_id': 0, 'reason': 'Unsupported year.'}]}
        data = {'draft': {'title': 'A claim about 2099.', 'description': 'A broad theme.'},
                'speech': 'Exact original speech including garbled names.', 'creator_profile': {'all': 'kept'}}
        result = citation_audit(brain, data)
        sent = brain.json.call_args.args[1]
        self.assertEqual(sent['speech'], data['speech'])
        self.assertEqual(sent['creator_profile'], data['creator_profile'])
        self.assertIn('"A claim about 2099."', result['issues'][0])
        self.assertFalse(result['approved'])

    def test_audit_cannot_invent_an_absent_draft_sentence_or_ignore_issues(self):
        brain = Mock()
        data = {'draft': {'title': 'A supported theme.'}, 'speech': 'Original speech.'}
        brain.json.return_value = {'approved': True, 'issues': [{'draft_id': 99, 'reason': 'Absent name.'}]}
        with self.assertRaisesRegex(ValueError, 'actual draft'):
            citation_audit(brain, data)
        brain.json.return_value = {'approved': True, 'issues': [{'draft_id': 0, 'reason': 'Check theme.'}]}
        self.assertFalse(citation_audit(brain, data)['approved'])


if __name__ == '__main__':
    unittest.main()
