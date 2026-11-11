import unittest
from unittest.mock import patch

from tools import finish_model_upgrade as upgrade


class SpeechCandidateHandoffTests(unittest.TestCase):
    def test_coordinator_waits_until_replacement_is_adopted(self):
        state={'models':{'asr':{'path':'rejected'}}}
        for status in ('downloading','downloaded','validating','adopted'):
            with self.subTest(status=status), patch.object(upgrade.Path,'is_file',return_value=True), \
                 patch.object(upgrade,'read',return_value={'path':'replacement','status':status}):
                self.assertTrue(upgrade.pending_speech_candidate(state))

    def test_matching_selection_can_proceed_without_another_worker(self):
        state={'models':{'asr':{'path':'replacement'}}}
        with patch.object(upgrade.Path,'is_file',return_value=True), \
             patch.object(upgrade,'read',return_value={'path':'replacement','status':'adopted'}):
            self.assertFalse(upgrade.pending_speech_candidate(state))

    def test_failed_candidate_keeps_old_configuration_and_reports_failure(self):
        state={'models':{'asr':{'path':'rejected'}}}
        with patch.object(upgrade.Path,'is_file',return_value=True), \
             patch.object(upgrade,'read',return_value={'path':'replacement','status':'needs_attention',
                                                      'error':'script edit failed'}):
            with self.assertRaisesRegex(RuntimeError,'script edit failed'):
                upgrade.pending_speech_candidate(state)


if __name__=='__main__': unittest.main()
