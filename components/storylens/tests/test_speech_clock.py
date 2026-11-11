import unittest
from hinglish_motion.speech_clock import compile_plan, frame_at, retimed_phase


class SpeechClockTests(unittest.TestCase):
    def setUp(self):
        self.words = [{'id':'a','start':0.,'text':'93'},
                      {'id':'b','start':3.011,'text':'Dale'},
                      {'id':'c','start':8.127,'text':'swing'}]

    def test_anchor_drives_scene_and_event_without_rounding_early(self):
        plan={'scenes':[{'start_word':'a','effect':'paper','photos':[{'word':'a','asset':'bowler'}],'sfx':'none'},
                        {'start_word':'b','effect':'hero','photos':[{'word':'b','asset':'portrait'}],'sfx':'impact','sfx_word':'b'},
                        {'start_word':'c','effect':'film','photos':[{'word':'c','asset':'bowler'}],'sfx':'none'}]}
        scenes=compile_plan(plan,self.words,{'paper':{},'hero':{},'film':{}},duration=12)
        self.assertEqual(scenes[1]['start_frame'],91)
        self.assertEqual(scenes[1]['photos'][0]['at'],0)
        self.assertAlmostEqual(scenes[1]['sfx_at'],3.011)
        self.assertTrue(0<=scenes[1]['photos'][0]['schedule_error_ms']<1000/30)
        self.assertEqual(sum(s['end_frame']-s['start_frame'] for s in scenes),360)

    def test_missing_or_outside_word_never_gets_an_evenly_spaced_fallback(self):
        with self.assertRaisesRegex(ValueError,'Unknown scene word'):
            compile_plan({'scenes':[{'start_word':'missing'}]},self.words,{'hero':{}})
        with self.assertRaisesRegex(ValueError,'outside scene'):
            compile_plan({'scenes':[{'start_word':'a','effect':'hero','photos':[{'word':'c'}]},
                                    {'start_word':'b','effect':'hero','photos':[]}]},self.words,{'hero':{}})

    def test_irregular_audio_onsets_map_to_native_reveal_points(self):
        self.assertAlmostEqual(retimed_phase(1.3,[1.3,5.8],[.9,3.2],7,10),.9)
        self.assertAlmostEqual(retimed_phase(5.8,[1.3,5.8],[.9,3.2],7,10),3.2)
        self.assertEqual(retimed_phase(0,[0],[1.25],7,10),1.25)
        with self.assertRaises(ValueError):
            retimed_phase(1,[2,4],[3,1],7,10)

    def test_invalid_onsets_rejected(self):
        for value in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):frame_at(value)


if __name__=='__main__':unittest.main()
