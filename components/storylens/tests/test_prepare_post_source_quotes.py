"""Source-selection fixtures only; actual local-model acceptance is separate."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_source import source_quotes, recover_youtube


class SourceQuoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.brain = Mock()
        self.brain.name = 'fixture-local'
        self.text = 'Early seasons were difficult. A new captain joined. The team improved.'

    def test_model_selects_ids_and_only_exact_source_words_are_saved(self):
        self.brain.json.return_value = {'sentence_ids': [2, 0], 'facts': ['Invented final score 999']}
        result = source_quotes(self.brain, self.text, 1, self.folder)
        self.assertEqual(result['facts'], ['Early seasons were difficult.', 'The team improved.'])
        self.assertEqual(result['source_ids'], [0, 2])
        self.assertEqual(result['version'], 2)
        self.assertNotIn('999', str(result))

    def test_invalid_ids_are_revised_without_accepting_them(self):
        self.brain.json.side_effect = [{'sentence_ids':[99]}, {'sentence_ids':[1]}]
        result = source_quotes(self.brain, self.text, 2, self.folder)
        self.assertEqual(result['facts'], ['A new captain joined.'])
        self.assertIn('correction', self.brain.json.call_args_list[1].args[1])

    def test_saved_valid_quotes_resume_without_inference(self):
        self.brain.json.return_value = {'sentence_ids':[0]}
        first = source_quotes(self.brain, self.text, 1, self.folder)
        second = source_quotes(self.brain, self.text, 1, self.folder)
        self.assertEqual(first, second)
        self.assertEqual(self.brain.json.call_count, 1)

    def test_changed_source_does_not_reuse_old_quotes(self):
        self.brain.json.return_value = {'sentence_ids':[0]}
        source_quotes(self.brain, self.text, 1, self.folder)
        result = source_quotes(self.brain, 'Different supplied sentence.', 1, self.folder)
        self.assertEqual(result['facts'], ['Different supplied sentence.'])
        self.assertEqual(self.brain.json.call_count, 2)

    def test_boolean_and_duplicate_ids_are_rejected(self):
        self.brain.json.side_effect = [{'sentence_ids':[True]}, {'sentence_ids':[0,0]}, {'sentence_ids':[2]}]
        result = source_quotes(self.brain, self.text, 3, self.folder)
        self.assertEqual(result['source_ids'], [2])

    def test_overlong_cached_answer_is_rejected_before_fresh_selection(self):
        text=' '.join(f'Sentence {n}.' for n in range(20))
        stale={'sentence_ids':list(range(20))}
        self.brain.json.side_effect=[stale,{'sentence_ids':[1,5,9,12,15,19]}]
        result=source_quotes(self.brain,text,1,self.folder)
        self.assertEqual(result['source_ids'],[1,5,9,12,15,19])
        self.brain.reject_result.assert_called_once()
        self.assertIs(self.brain.reject_result.call_args.args[0],stale)
        self.assertIn('1 and 6',self.brain.json.call_args_list[1].args[1]['correction'])

    def test_recovery_preserves_guidance_and_cannot_turn_failed_audit_into_success(self):
        def reject(brain, text, progress, record):
            brain.json('Audit', {'speech': text}, {})
            record('concise_rejected', {'title': 'Unsupported claim'}, 'Audit rejected')
            raise ValueError('Audit rejected')
        context = {'saved_guidance': 'preserve all'}
        with patch('hinglish_publish.metadata.concise_youtube', side_effect=reject):
            with self.assertRaisesRegex(ValueError, 'Audit rejected'):
                recover_youtube(self.brain, self.text, self.folder, context, ['English'], lambda x: None)
        sent = self.brain.json.call_args.args[1]
        self.assertEqual(sent['creator_profile'], context)
        self.assertEqual(sent['writing_preferences'], ['English'])
        self.assertIn('Audit rejected', (self.folder/'youtube-recovery.json').read_text())


if __name__ == '__main__': unittest.main()
