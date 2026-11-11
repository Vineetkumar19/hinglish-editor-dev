"""Regression checks for soundtrack selection, measured timing and editable export."""
from fractions import Fraction
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave
import xml.etree.ElementTree as ET

import numpy as np

from hinglish_broll.phrases import Phrase
from hinglish_eval.model_rules import sound_analysis, sound_pick
from hinglish_sound.cues import Cue, keep_musical, place_cue, word_time
from hinglish_sound.events import choose, normalize, project_events
from hinglish_sound.mix import mix, write_wav
from hinglish_sound.music import passage
from hinglish_sound.pipeline import _rank, music_sections
from hinglish_sound.xml_export import _frame_aligned, export_sound_xml


class SoundTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_missing_and_repeated_words_do_not_guess(self):
        words = [SimpleNamespace(start=i, end=i+.5, text=t) for i, t in enumerate(('go', 'now', 'go'))]
        phrase = Phrase(0, 0, 3, 'go now go')
        self.assertIsNone(word_time(phrase, words, 'gone'))
        self.assertIsNone(word_time(phrase, words, 'go'))
        self.assertEqual(word_time(phrase, words, 'go', 2), 2)
        self.assertEqual(word_time(phrase, words, 'now!'), 1)

    def test_peak_before_timeline_is_trimmed_not_shifted(self):
        asset = SimpleNamespace(duration=1., path='sound.wav', peak_time=.4, loudness=-20)
        with patch('hinglish_sound.cues.exact_peak_time', return_value=.4):
            cue = place_cue(asset, .1, 'impact', 'reveal')
        self.assertEqual(cue.time, 0.)
        self.assertAlmostEqual(cue.source_offset, .3)
        self.assertAlmostEqual(cue.time + .4 - cue.source_offset, cue.target)

    def test_start_alignment_has_no_arbitrary_preroll(self):
        asset = SimpleNamespace(duration=1., path='sound.wav', peak_time=.2, loudness=-20)
        self.assertEqual(place_cue(asset, 1.5, 'foley', 'door').time, 1.5)

    def test_rejected_music_is_allowed_and_stays_rejected(self):
        for invalid in (-1, None, True, '0', 4):
            self.assertEqual(_rank(invalid, 2), [])
        check = sound_pick([], [], [{}], [[{}, {}]])
        self.assertEqual(check({'effects': [], 'music': [{'section':0, 'choice':-1}]}), [])
        check = sound_analysis([Phrase(0,0,1,'hello')], 0, [], [], True)
        self.assertEqual(check({'lines':[{'id':0}], 'music':[], 'moments':[]}), [])

    def test_event_validation_keeps_only_bounded_measured_times(self):
        rows = normalize([{'kind':'motion','time':1,'end':5,'label':'title'},
                          {'kind':'motion','time':1,'end':5,'label':'title'},
                          {'kind':'zoom','time':float('nan')}, {'kind':'foley','time':-1},
                          {'kind':'ambience','time':3}, 'bad'], 3)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['end'],3)

    def test_sampled_frames_cannot_become_precise_foley(self):
        events = normalize([{'kind':'ambience','time':2,'end':5,'label':'rain','precision':'sampled'}], 10)
        class Brain:
            def ask(self, *args, **kwargs):
                return {'cues':[{'id':events[0]['id'],'type':'foley','intent':'footstep'},
                                {'id':'invented','type':'ambience','intent':'rain'}]}
        self.assertEqual(choose(Brain(),events,'walk','serious',2,['foley','ambience']),[])

    def test_motion_sidecar_retains_real_stagger_times(self):
        (self.root/'motion-project.json').write_text(json.dumps({'scenes':[{
            'start':2,'duration':4,'template':'asset_hero',
            'sound_events':[{'time':.77,'phase':'landing','label':'second object'}]}]}))
        event = next(e for e in project_events(self.root) if e['label']=='second object')
        self.assertAlmostEqual(event['time'],2.77)

    def test_cinematic_cuts_use_frame_rate_not_guessed_seconds(self):
        (self.root/'reel-plan.json').write_text(json.dumps({'fps':'30000/1001','shots':[
            {'start_frame':30,'end_frame':60,'path':'city.mp4'}]}))
        event=project_events(self.root)[0]
        self.assertEqual(event['kind'],'transition')
        self.assertAlmostEqual(event['time'],1.001)

    def test_all_event_sounds_share_budget_and_ambience_does_not_stack(self):
        cues = [Cue(i*3,i*3,'x','impact',1,-4,-20,'',source='motion') for i in range(6)]
        self.assertEqual(len(keep_musical(cues,12,6,1)),2)
        cues = [Cue(i*3,i*3,'x','ambience',10,-18,-20,'',source='ambience') for i in range(3)]
        self.assertEqual(len(keep_musical(cues,15,1,1)),1)

    def test_passage_can_skip_a_quiet_intro(self):
        rate=8000
        x=np.sin(2*np.pi*220*np.arange(rate*20)/rate).astype(np.float32)
        x[:rate*10] *= .01
        x[rate*10:] *= .5
        path=write_wav(self.root/'music.wav',x,rate)
        self.assertGreaterEqual(passage(path,4,3)['source_offset'],10)

    def test_short_silent_music_is_rejected_before_looping(self):
        path=write_wav(self.root/'silent.wav',np.zeros(8000,np.float32),8000)
        with self.assertRaisesRegex(ValueError,'Sound music file is silent'):
            passage(path,4)

    def test_music_turn_can_be_tense_not_only_happy(self):
        lines=[Phrase(0,0,15,'calm'),Phrase(1,15,30,'danger')]
        rows=music_sections([{'from_id':0,'mood':'neutral'},
                             {'from_id':1,'mood':'tense'}],lines,30,['neutral','tense'])
        self.assertEqual([s['mood'] for s in rows],['neutral','tense'])
        self.assertEqual(music_sections([],lines,30,['neutral']),[])

    def test_xml_padding_preserves_subframe_onset_and_silent_sequence(self):
        path=write_wav(self.root/'effect.wav',np.ones((2,4800),np.float32)*.25)
        effect={'path':str(path),'start':.035,'length':.1,'category':'foley'}
        fps=Fraction(30000,1001)
        aligned=_frame_aligned(effect,fps)
        with wave.open(aligned['path'],'rb') as f:
            samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
        onset=np.flatnonzero(samples[:,0])[0]/48000+aligned['start']
        self.assertLessEqual(abs(onset-effect['start']),1/48000)
        original=self.root/'sequence.xml'
        original.write_text('<xmeml><sequence id="s"><name>Silent</name><media><video/></media></sequence></xmeml>')
        target=export_sound_xml(original,fps,{'effects':[effect]},self.root/'SOUND.xml')
        tree=ET.parse(target)
        self.assertEqual(len(tree.findall('.//media/audio/track/clipitem')),2)

    def test_silent_video_mix_is_finite_and_audible(self):
        t=np.arange(24000)/48000
        source=write_wav(self.root/'foley.wav',.1*np.sin(2*np.pi*400*t))
        cue=Cue(.5,.5,str(source),'foley',.5,-10,-20,'door')
        result=mix(np.zeros(96000,np.float32),[],[cue],self.root)
        self.assertTrue(np.isfinite(result['master']).all())
        self.assertGreater(np.max(np.abs(result['master'])),.01)
        self.assertEqual(len(result['stems']['effects']),1)
        self.assertFalse(result['speech'].any())

    def test_unconfigured_freesound_makes_no_network_request(self):
        from hinglish_sound.providers import fetch
        with patch('hinglish_sound.providers.requests.Session', side_effect=AssertionError('Unexpected network')):
            self.assertEqual(fetch(self.root,'rain','ambience'),[])

    def test_error_catalog_keeps_diagnostics_separate(self):
        from hinglish_app.user_messages import problem
        p=problem(RuntimeError('Sound vision unavailable: local model is missing'))
        self.assertEqual(p['code'],'sound_vision_unavailable')
        self.assertNotIn('RuntimeError',p['message'])
        self.assertIn('local model is missing',p['details'])


if __name__=='__main__':
    unittest.main()
