"""Regression coverage for the failed RCB brief; no model/media/platform runs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_runtime import RecordedBrain
from hinglish_publish.prepare_post_source import recover_youtube, recovery_subjects


class RejectedCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)
        self.raw=Mock(name='local-model');self.raw.name='fixture';self.raw.last_usage={}
        self.brain=RecordedBrain(self.raw,self.folder,{'profile':'cricket'})

    def test_rejected_answer_is_not_replayed_but_valid_answer_stays_cached(self):
        bad={'subject':'Virat Kohli'};good={'subject':'Royal Challengers Bangalore'}
        self.raw.json.side_effect=[bad,good]
        first=self.brain.json('Brief',{'speech':'RCB'},{});self.brain.reject_result(first,'Use a team, not a player')
        second=self.brain.json('Brief',{'speech':'RCB'},{});third=self.brain.json('Brief',{'speech':'RCB'},{})
        self.assertEqual(second,good);self.assertEqual(third,good);self.assertEqual(self.raw.json.call_count,2)
        archived=list(self.folder.glob('*-rejected-*.json'));self.assertEqual(len(archived),1)
        self.assertEqual(json.loads(archived[0].read_text())['result'],bad)

    def test_actual_rcb_brief_failure_is_corrected_before_it_reaches_writer(self):
        text='RCB team IPL league journey. The team develops through the league.'
        bad={'subject':'Virat Kohli','points':[{'point':'the team journey through the league','sentence_ids':[0]}]}
        good={**bad,'subject':'Royal Challengers Bangalore'}
        copy={'title':'Royal Challengers Bangalore in the IPL',
              'description':'Royal Challengers Bangalore and their journey through the league.\n\n#RCB #Cricket #IPL',
              'tags':['RCB','Cricket','IPL']}
        self.raw.json.side_effect=[bad,good,copy]
        with patch('hinglish_publish.metadata.review_grounding') as audit:
            result=recover_youtube(self.brain,text,self.folder,{'keep':'all guidance'},['English'],lambda _:None)
        self.assertEqual(result['title'],copy['title']);audit.assert_called_once()
        first=self.raw.json.call_args_list[0];second=self.raw.json.call_args_list[1]
        self.assertIn('Royal Challengers Bangalore',first.args[2]['properties']['subject']['enum'])
        self.assertNotIn('Virat Kohli',first.args[2]['properties']['subject']['enum'])
        self.assertIn('correction_history',second.args[1]);self.assertEqual(second.args[1]['creator_profile'],{'keep':'all guidance'})
        self.assertEqual(len(list(self.folder.glob('*-rejected-*.json'))),1)

    def test_rejecting_a_format_repaired_answer_invalidates_both_receipts(self):
        self.raw.json.side_effect=[json.JSONDecodeError('bad JSON','{',0),{'subject':'Virat Kohli'},{'subject':'Royal Challengers Bangalore'}]
        answer=self.brain.json('Brief',{},{});self.brain.reject_result(answer,'Use the supported team')
        self.assertEqual(len(list(self.folder.glob('*-rejected-*.json'))),2)
        self.assertEqual(self.brain.json('Brief',{},{}),{'subject':'Royal Challengers Bangalore'})
        self.assertEqual(self.raw.json.call_count,3)

    def test_subjects_do_not_import_a_team_or_player_from_destination_guidance(self):
        self.assertNotIn('Mumbai Indians',recovery_subjects('RCB discuss their IPL journey.'))
        self.assertEqual(recovery_subjects('DC power and game settings.'),['The discussion in this clip'])
        self.assertIn('Royal Challengers Bengaluru',recovery_subjects('Royal Challengers Bengaluru in the IPL.'))

    def test_a_model_ignoring_the_subject_enum_still_cannot_publish(self):
        self.raw.json.return_value={'subject':'Virat Kohli','points':[{'point':'the team journey through the league','sentence_ids':[0]}]}
        with self.assertRaisesRegex(ValueError,'subject'):
            recover_youtube(self.brain,'RCB IPL league discussion.',self.folder,{},[],lambda _:None)
        self.assertEqual(self.raw.json.call_count,3)
        self.assertEqual(len(list(self.folder.glob('*-rejected-*.json'))),3)


if __name__=='__main__':unittest.main()
