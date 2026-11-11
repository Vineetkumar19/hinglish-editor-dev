import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hinglish_captions.core import CaptionWord, correct_with_reference
from hinglish_publish import metadata
from hinglish_publish.memory import CreatorMemory, correct_text, correct_words
from hinglish_publish.service import Publisher

META = {'title': 'Original title', 'description': 'Spoken content.',
        'instagram_caption': 'A real moment. #Example', 'tags': ['example']}


class FakeBrain:
    name = 'Test local brain'
    def json(self, system, data, schema, **kwargs):
        if 'filename' in data:
            self.system, self.data = system, data
        else:
            self.final_system, self.final_data = system, data
        return META
    def close(self):
        self.closed = True


class CreatorMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.memory = CreatorMemory(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_feedback_survives_restart_and_duplicate_is_not_added(self):
        data = {'scope': 'title', 'want': 'Short Roman Hinglish titles', 'avoid': 'Hype'}
        first = self.memory.add(data)
        again = CreatorMemory(self.root)
        self.assertEqual(first, again.add(data))
        self.assertEqual(len(again.list()), 1)

    def test_disabled_memory_leaves_future_context_and_can_be_restored(self):
        record = self.memory.add({'scope': 'description', 'want': 'Two short paragraphs'})
        self.memory.set_active(record, False)
        self.assertEqual(self.memory.writing_context(), [])
        self.assertEqual(len(self.memory.list()), 1)
        self.memory.set_active(record, True)
        self.assertEqual(len(self.memory.writing_context()), 1)

    def test_recent_feedback_is_first_and_context_is_bounded(self):
        for number in range(25):
            self.memory.add({'scope': 'title', 'want': 'Preference ' + str(number)})
        context = self.memory.writing_context()
        self.assertEqual(len(context), 16)
        self.assertEqual(context[0]['want'], 'Preference 24')
        self.assertEqual(len(self.memory.list()), 25)

    def test_model_context_and_cache_input_change_after_feedback(self):
        brain = FakeBrain()
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            metadata.generate(self.root, self.root / 'clip.mp4', transcript='Actual speech')
            before = dict(brain.data)
            self.memory.add({'scope': 'instagram_caption', 'want': 'Three relevant hashtags only'})
            _, origin = metadata.generate(self.root, self.root / 'clip.mp4', transcript='Actual speech')
        self.assertNotEqual(before, brain.data)
        self.assertEqual(brain.data['creator_preferences'][0]['scope'], 'instagram_caption')
        self.assertIn('1 learned preferences', origin)
        self.assertTrue(brain.closed)

    def test_spelling_is_exact_and_preserves_punctuation_and_timings(self):
        self.memory.add({'scope': 'subtitle_spelling', 'before': 'shari', 'after': 'sharir'})
        words = [CaptionWord('Shari,', 1.25, 1.55), CaptionWord('sharif', 2.0, 2.5)]
        corrected, changes = correct_words(self.root, words)
        self.assertEqual([word.text for word in corrected], ['sharir,', 'sharif'])
        self.assertEqual([(w.start, w.end) for w in words], [(w.start, w.end) for w in corrected])
        self.assertEqual(len(changes), 1)
        self.assertEqual(correct_text(self.root, 'shari\nsharif'), 'sharir\nsharif')

    def test_latest_spelling_wins_and_current_reference_can_override(self):
        self.memory.add({'scope': 'subtitle_spelling', 'before': 'vazan', 'after': 'vajan'})
        self.memory.add({'scope': 'subtitle_spelling', 'before': 'vazan', 'after': 'wazan'})
        words, _ = correct_words(self.root, [CaptionWord('vazan', 0, 1)])
        self.assertEqual(words[0].text, 'wazan')
        explicit, _ = correct_with_reference([CaptionWord('vazan', 0, 1)], 'vajan')
        explicit, _ = correct_words(self.root, explicit, 'vajan')
        self.assertEqual(explicit[0].text, 'vajan')
        protected, _ = correct_words(self.root, [CaptionWord('vazan', 0, 1)], 'vazan')
        self.assertEqual(protected[0].text, 'vazan')

    def test_spelling_feedback_cannot_insert_a_sentence(self):
        with self.assertRaises(ValueError):
            self.memory.add({'scope': 'subtitle_spelling', 'before': 'shari', 'after': 'a new sentence'})
        with self.assertRaises(ValueError):
            self.memory.add({'scope': 'unknown', 'want': 'anything'})

    def test_edit_only_learns_when_explicitly_selected(self):
        publisher = Publisher(self.root)
        item = {'platform': 'youtube', 'kind': 'long', 'fingerprint': 'demo', 'video': 'clip.mp4',
                'metadata': META, 'visibility': 'public'}
        job_id = publisher.store.add_batch([item])[0]
        publisher.edit({'id': job_id, 'metadata': {**META, 'title': 'A corrected title'}})
        self.assertEqual(self.memory.list(), [])
        publisher.edit({'id': job_id, 'remember': True, 'metadata': {**META, 'title': 'My preferred title'}})
        saved = self.memory.list()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['before'], 'A corrected title')
        self.assertEqual(saved[0]['after'], 'My preferred title')
        self.assertEqual(publisher.store.get(job_id)['status'], 'draft')

    def test_creator_sidecar_is_not_changed_by_preferences(self):
        video = self.root / 'clip.mp4'
        video.with_suffix('.publish.json').write_text(json.dumps({'metadata_language': 'en', 'metadata': META}))
        self.memory.add({'scope': 'title', 'want': 'A different title style'})
        self.assertEqual(metadata.generate(self.root, video)[0], META)


    def test_english_rule_overrides_hinglish_source_notes_and_saved_examples(self):
        self.memory.add({'scope': 'all', 'want': 'Write in Roman Hinglish',
                         'after': '7000 RPM par ek khaas ehsaas.'})
        brain = FakeBrain()
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            output, _ = metadata.generate(self.root, self.root / 'short.mp4',
                transcript='Jab sab dhundhala ho jaata hai.', notes='Use Hindi for this video.')
        self.assertEqual(output, META)
        self.assertTrue(brain.system.endswith(metadata.ENGLISH_RULE))
        self.assertIn('including Shorts', brain.system)
        self.assertIn('every Instagram Reel caption', brain.system)
        self.assertIn('all tags/hashtags in proper, natural English', brain.system)
        self.assertEqual(brain.data['transcript'], 'Jab sab dhundhala ho jaata hai.')

    def test_final_english_pass_receives_only_the_draft_not_foreign_examples(self):
        brain = FakeBrain()
        self.memory.add({'scope': 'title', 'want': 'Write in Roman Hinglish', 'after': 'Kaun ho tum?'})
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            metadata.generate(self.root, self.root / 'clip.mp4', transcript='Kaun ho tum?')
        self.assertEqual(brain.final_data['output_language'], 'English')
        self.assertEqual(brain.final_data['draft'], META)
        self.assertNotIn('creator_preferences', brain.final_data)
        self.assertIn('Never return Hindi or Roman Hinglish', brain.final_system)

    def test_video_relevance_rule_reaches_both_writing_passes_without_learning_upload_notes(self):
        brain=FakeBrain()
        transcript='Mumbai Indians team journey in IPL 2020.'
        notes='Private Storylens upload test for Fantasy Legends; verify channel routing.'
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            metadata.generate(self.root,self.root/'clip.mp4',transcript=transcript,notes=notes)
        self.assertIn(metadata.CONTENT_RULE,brain.system)
        self.assertIn(metadata.CONTENT_RULE,brain.final_system)
        self.assertEqual(brain.data['creator_notes'],notes)
        self.assertEqual(brain.final_data['video_context'],transcript)
        self.assertNotIn('creator_notes',brain.final_data)
        self.assertEqual(self.memory.list(),[])

    def test_content_rule_also_applies_to_non_english_sidecar_conversion(self):
        video=self.root/'clip.mp4'
        video.with_suffix('.publish.json').write_text(json.dumps({'metadata':META}))
        brain=FakeBrain()
        with patch('hinglish_visuals.brain.open_brain',return_value=brain):
            metadata.generate(self.root,video)
        self.assertIn(metadata.CONTENT_RULE,brain.final_system)

    def test_detailed_youtube_preference_survives_both_passes_and_older_short_style(self):
        self.memory.add({'scope': 'description', 'want': 'Two short paragraphs'})
        self.memory.add({'scope': 'description', 'want': 'Long, detailed YouTube descriptions with relevant hashtags'})
        brain = FakeBrain()
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            metadata.generate(self.root, self.root / 'clip.mp4', transcript='Source facts only.')
        self.assertEqual(brain.data['creator_preferences'][0]['want'],
                         'Long, detailed YouTube descriptions with relevant hashtags')
        for system in (brain.system, brain.final_system):
            self.assertIn(metadata.SEO_RULE, system)
            self.assertIn('Do not insert unrelated popular/trending keywords', system)
            self.assertIn('separate natural\nInstagram caption under 2000', system)
        self.assertNotIn('Keep descriptions concise', brain.system)
        self.assertEqual(brain.final_data['video_context'], 'Source facts only.')

    def test_long_description_is_not_truncated_or_forced_into_instagram_caption(self):
        description = 'Source-supported detail about the video. ' * 70 + '\n\n#Cricket #IPL #MumbaiIndians'
        draft = {**META, 'description': description, 'instagram_caption': 'A brief caption. #Cricket'}
        brain = FakeBrain()
        brain.json = lambda *args, **kwargs: draft
        self.assertEqual(metadata.english_copy(brain, draft, 'Source-supported detail.'), draft)
        self.assertLess(len(draft['instagram_caption']), 100)
        with self.assertRaises(ValueError):
            metadata.validate({**draft, 'description': 'x' * 5001})

    def test_undeclared_sidecar_runs_english_conversion_without_transcribing(self):
        video = self.root / 'clip.mp4'
        supplied = {**META, 'title': 'Ek khaas ehsaas', 'description': 'Kaun ho tum?'}
        video.with_suffix('.publish.json').write_text(json.dumps({'metadata': supplied}))
        brain = FakeBrain()
        with patch('hinglish_visuals.brain.open_brain', return_value=brain):
            result, origin = metadata.generate(self.root, video)
        self.assertEqual(result, META)
        self.assertEqual(brain.final_data['draft'], supplied)
        self.assertEqual(brain.final_data['output_language'], 'English')
        self.assertIn('translated creator sidecar', origin)
        self.assertTrue(brain.closed)
