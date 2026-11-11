"""Stored negative-verdict replay only; no actual frame/model acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from hinglish_broll.verify import Checker, CheckUnavailable


FIXTURES=Path(__file__).parent/'fixtures/broll-residential-criteria'


class ResidentialVerdictReplayTests(unittest.TestCase):
    def setUp(self):
        self.observed=json.loads((FIXTURES/'actual-input.json').read_text(encoding='utf-8'))
        self.raw=json.loads((FIXTURES/'raw-local-verdict.json').read_text(encoding='utf-8'))

    def replay(self,answer=None,slot=None,unavailable=False):
        checker=Checker.__new__(Checker)
        # Avoid the constructor, provider discovery, cache, model and real media.
        checker.model=Mock()
        checker.model.name='stored-negative-fixture-only'
        checker.model.look=Mock(return_value=copy.deepcopy(self.raw if answer is None else answer))
        if unavailable:checker.model.look.side_effect=TimeoutError('synthetic unavailable local checker')
        interval=self.observed['interval']
        synthetic=Image.new('RGB',(27,48),'black')
        frames=[(interval['start']+n*.1,synthetic) for n in range(3)]
        with patch('hinglish_broll.library.read_frames',return_value=frames):
            result=checker.check(Path('synthetic-not-read.mp4'),interval['start'],
                interval['end']-interval['start'],copy.deepcopy(slot or self.observed['slot']),'video')
        return checker,result

    def test_raw_negative_verdict_bytes_match_captured_cache(self):
        self.assertEqual(hashlib.sha256((FIXTURES/'raw-local-verdict.json').read_bytes()).hexdigest(),
                         self.observed['raw_cache_sha256'])
        stored=self.observed['stored_postprocessed_verdict']
        self.assertEqual(self.raw['seen'],stored['seen'])
        self.assertTrue(stored['reason'].endswith(self.raw['reason']))

    def test_actual_negative_answer_remains_rejected_without_manual_relabeling(self):
        checker,result=self.replay()
        self.assertFalse(result['passed'])
        self.assertEqual(result['frame_checks'],self.raw['frame_checks'])
        self.assertEqual(result['context_compatible'],False)
        self.assertEqual(checker.model.look.call_count,1)

    def test_current_request_retains_source_context_and_all_frame_requirements(self):
        checker,_=self.replay()
        _,prompt,schema=checker.model.look.call_args.args
        self.assertIn(self.observed['slot']['context'],prompt)
        self.assertIn(self.observed['slot']['meaning'],prompt)
        self.assertIn(self.observed['slot']['direction'],prompt)
        self.assertIn('identity_compatible',schema['required'])
        self.assertEqual(schema['properties']['frame_checks']['minItems'],3)
        self.assertIn('subject_visible',schema['properties']['frame_checks']['items']['required'])

    def test_top_level_positives_cannot_override_negative_per_frame_evidence(self):
        mutated=copy.deepcopy(self.raw)
        # Synthetic negative-control mutation, never a successful footage answer.
        mutated.update(related=True,context_compatible=True,identity_compatible=True)
        _,result=self.replay(mutated)
        self.assertFalse(result['passed'])
        self.assertTrue(all(not f['subject_visible'] for f in result['frame_checks']))

    def test_explicit_named_identity_is_still_sent_to_local_checker(self):
        slot=copy.deepcopy(self.observed['slot']);slot['subject']='Buckingham Palace'
        checker,result=self.replay(slot=slot)
        self.assertIn('Buckingham Palace',checker.model.look.call_args.args[1])
        self.assertFalse(result['passed'])

    def test_unavailable_model_remains_an_error_not_an_approved_option(self):
        with self.assertRaises(CheckUnavailable):self.replay(unavailable=True)


if __name__=='__main__':
    unittest.main()
