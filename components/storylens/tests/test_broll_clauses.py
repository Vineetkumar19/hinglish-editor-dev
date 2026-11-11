import unittest
from unittest.mock import Mock
from dataclasses import replace

from hinglish_broll.clauses import semantic_phrases,boundary_check
from hinglish_broll.placement import Moment,place
from hinglish_broll.settings import profile_for
from hinglish_cut.model import Word


class ClauseTimingTests(unittest.TestCase):
    def test_sleeping_and_lounge_in_one_asr_chunk_get_separate_real_times(self):
        words=[Word(w,13+i*.25,13+i*.25+.2) for i,w in enumerate(
            'Log soch chuke hote hain koi launch nahin koi club nahin'.split())]
        llm=Mock()
        llm.json.return_value={'clauses':[
            {'end_word':4,'meaning':'People have already gone to sleep.'},
            {'end_word':10,'meaning':'There is no lounge or club.'}]}
        phrases=semantic_phrases(llm,words,{},progress=lambda _:None)
        self.assertEqual([p.text for p in phrases],['Log soch chuke hote hain','koi launch nahin koi club nahin'])
        self.assertEqual(phrases[1].start,words[5].start)
        profile=replace(profile_for(33,'high'),hook=0,tail=0,min_gap=0,min_spacing=0)
        slots=place([Moment(0,'person asleep',['person sleeping'],3,quote='Log soch chuke'),
                     Moment(1,'bar counter',['bar counter'],3,quote='koi launch')],phrases,profile,33,phrases)
        self.assertEqual(len(slots),2)
        self.assertEqual(slots[1].start,14.25)
        self.assertEqual(slots[0].end,14.2)
        self.assertNotIn('Log soch',slots[1].text)

    def test_bad_boundary_ids_and_incomplete_coverage_fail_validation(self):
        checker=boundary_check(0,10)
        for ends in ([4,4,10],[4,11],[4],[-1,10]):
            self.assertTrue(checker({'clauses':[{'end_word':i,'meaning':'meaning'} for i in ends]}))
        self.assertEqual(checker({'clauses':[{'end_word':4,'meaning':'sleeping'},
                                            {'end_word':10,'meaning':'no lounge'}]}),[])
        tiny=boundary_check(0,110)({'clauses':[{'end_word':i,'meaning':'fragment'} for i in list(range(1,110,2))+[110]]})
        self.assertTrue(any(p.rule=='broll.clauses.fragments' for p in tiny))

    def test_clause_translation_is_reused_without_losing_negative_meaning(self):
        from hinglish_broll.phrases import Phrase
        from hinglish_broll.planner import translate_phrases
        llm=Mock()
        result=translate_phrases(llm,[Phrase(0,13,14,'Log soch chuke hote hain','People have gone to sleep')],lambda _:None)
        self.assertEqual(result,[{'ids':[0],'english':'People have gone to sleep'}])
        llm.json.assert_not_called()

    def test_consecutive_audio_only_clauses_can_be_planned_without_face_spacing(self):
        from hinglish_broll.phrases import Phrase
        from hinglish_broll.planner import plan_moments
        from unittest.mock import patch
        profile=replace(profile_for(33,'high'),hook=0,tail=0,min_gap=0,min_spacing=0)
        clauses=[Phrase(0,13,14.2,'Log so chuke hote hain','People have gone to sleep')]
        with patch('hinglish_broll.planner.guard.ask_checked',return_value={'moments':[]}), \
             patch('hinglish_broll.planner.review_moments',return_value={'moments':[]}):
            self.assertEqual(plan_moments(Mock(),clauses,{},profile,'portrait',lambda _:None,5,'Match the actions'),[])
