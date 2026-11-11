import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from hinglish_broll.phrases import Phrase
from hinglish_sound.cues import Cue
from hinglish_sound import spotting, processing


class SpottingTests(unittest.TestCase):
    lines = [Phrase(i, n*2, n*2+1.8, text) for n, (i, text) in enumerate(
        [(10, 'Here is the setup'), (20, 'Wait for it'), (30, 'No chance'), (40, 'Now we move on')])]

    def rows(self):
        return [dict(from_id=10,to_id=10,mode='music',mood='upbeat',energy=2,why='Opening momentum'),
                dict(from_id=20,to_id=20,mode='voice_only',mood='',energy=1,why='Let the pause land'),
                dict(from_id=30,to_id=30,mode='effects_only',mood='',energy=2,why='Dry comic answer'),
                dict(from_id=40,to_id=40,mode='music',mood='hopeful',energy=2,why='Release')]

    def test_explicit_sections_keep_music_gaps_and_real_line_order(self):
        spans = spotting.resolve_sections(self.rows(), self.lines, 8, ['upbeat','hopeful'])
        self.assertEqual([(s['start'],s['end'],s['mode']) for s in spans],
                         [(0,2,'music'),(2,4,'voice_only'),(4,6,'effects_only'),(6,8,'music')])
        from hinglish_sound.pipeline import music_sections
        self.assertEqual([(s['start'],s['end']) for s in music_sections(self.rows(),self.lines,8,['upbeat','hopeful'])],[(0,2),(6,8)])

    def test_guard_accepts_intentional_music_breaks_without_forcing_sparse_sections(self):
        from hinglish_eval.model_rules import sound_analysis
        answer = dict(lines=[dict(id=l.id,emotion='comedic') for l in self.lines], music=self.rows(), moments=[])
        problems = sound_analysis(self.lines,10,['upbeat','hopeful'],['impact'],True)(answer)
        self.assertFalse([p for p in problems if p.rule.startswith('sound.analysis.music')])

    def test_missing_overlap_unknown_and_invalid_modes_are_rejected(self):
        examples = [self.rows()[1:], self.rows()+[self.rows()[0]],
                    [dict(self.rows()[0],from_id=999)]+self.rows()[1:],
                    [dict(self.rows()[0],mode='mute_original')]+self.rows()[1:]]
        for rows in examples:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                spotting.resolve_sections(rows,self.lines,8,['upbeat','hopeful'])

    def test_voice_only_preserves_dialogue_but_blocks_effect_anchor_and_tails(self):
        spans = spotting.resolve_sections(self.rows(),self.lines,8,['upbeat','hopeful'])
        cue = Cue(1.5,1.8,'effect.wav','impact',2,-8,-20,'reveal',source_offset=.3)
        kept,dropped = spotting.mask_cues([cue,replace(cue,time=3,target=3.2)],spans)
        self.assertEqual(len(kept),1)
        self.assertAlmostEqual(kept[0].length,.5)
        self.assertEqual(cue.length,2)
        self.assertEqual(len(dropped),1)

    def test_entrance_trim_keeps_source_hit_at_same_timeline_time(self):
        spans = spotting.resolve_sections(self.rows(),self.lines,8,['upbeat','hopeful'])
        cue = Cue(3.7,4.1,'effect.wav','impact',1,-8,-20,'reveal',source_offset=.2)
        kept,_ = spotting.mask_cues([cue],spans)
        self.assertEqual(kept[0].time,4)
        self.assertAlmostEqual(kept[0].source_offset,.5)
        self.assertAlmostEqual(kept[0].time-kept[0].source_offset,cue.time-cue.source_offset)

    def test_music_crossfades_do_not_leak_across_voice_only_space(self):
        from hinglish_sound.mix import music_bed
        rate=48000
        spans=[dict(start=0,end=1,path='a.wav',strict_bounds=True),dict(start=2,end=3,path='b.wav',strict_bounds=True)]
        source=np.full((2,rate*4),.05,np.float32)
        with patch('hinglish_sound.mix.decode',return_value=source):
            audio=music_bed(spans,-20,np.zeros(rate*3),rate*3)
        self.assertGreater(np.max(np.abs(audio[:,:rate])),0)
        self.assertEqual(np.max(np.abs(audio[:,rate:rate*2])),0)

    def test_music_toggle_keeps_original_choices_and_source_excerpts(self):
        plan={'music':[dict(path='score.wav',start=2,end=8,source_offset=12.5,strict_bounds=True)]}
        self.assertEqual(spotting.music_for_remix(plan,False),[])
        plan['music']=[]
        restored=spotting.music_for_remix(plan,True)
        self.assertEqual(restored[0]['source_offset'],12.5)
        restored[0]['source_offset']=99
        self.assertEqual(plan['all_music'][0]['source_offset'],12.5)


class ProcessingTests(unittest.TestCase):
    def test_invalid_saved_processing_stops_before_touching_preview_or_taste(self):
        import tempfile,json
        from pathlib import Path
        from hinglish_sound.pipeline import remix
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'output/sound/job/001';folder.mkdir(parents=True)
            preview=folder/'preview.mp4';preview.write_bytes(b'previous accepted preview')
            cue=Cue(0,.1,'a.wav','impact',.5,-8,-20,'reveal',processing={'pan':float('nan'),'why':'Invalid saved value'})
            plan={'cues':[cue.to_dict()],'music':[],'timeline_xml':'missing.xml','seconds':1,'settings':{}}
            file=folder/'sound-plan.json';file.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'Sound processing'):
                remix(file,[0])
            self.assertEqual(preview.read_bytes(),b'previous accepted preview')
            self.assertFalse((root/'cache/learning/sound-preferences.json').exists())

    def test_processing_failure_uses_shared_plain_language_error(self):
        from hinglish_app.user_messages import problem
        message=problem(ValueError('Sound processing contains unsupported settings'))
        self.assertEqual(message['code'],'sound_processing_invalid')
        self.assertIn('saved',message['message'].lower())

    def test_untrusted_processing_is_bounded_and_nonfinite_or_unknown_values_fail(self):
        for spec in [dict(pan=float('nan')),dict(pan=True),dict(lowpass_hz=20),dict(shell='delete'),dict(duck_db=-9)]:
            with self.subTest(spec=spec),self.assertRaises(ValueError):
                processing.validate(spec)

    def test_pan_and_filter_change_audio_without_length_or_channel_drift(self):
        rate=48000
        t=np.arange(rate)/rate
        audio=np.stack([.1*np.sin(2*np.pi*200*t)+.1*np.sin(2*np.pi*9000*t)]*2).astype(np.float32)
        out=processing.apply(audio,dict(pan=-.6,lowpass_hz=2000,why='Place the detail left and behind speech'))
        self.assertEqual(out.shape,audio.shape)
        self.assertTrue(np.isfinite(out).all())
        self.assertGreater(np.sum(out[0]**2),np.sum(out[1]**2)*2)
        spectrum=np.abs(np.fft.rfft(out[0]))
        self.assertLess(spectrum[9000],spectrum[200]*.1)

    def test_identity_processing_keeps_samples_and_rejects_unexplained_effects(self):
        audio=np.ones((2,100),np.float32)*.1
        np.testing.assert_array_equal(processing.apply(audio,{}),audio)
        with self.assertRaises(ValueError):processing.validate(dict(pan=.5))

    def test_processing_and_alternatives_survive_cue_save_reopen(self):
        cue=Cue(0,.1,'a.wav','impact',.5,-8,-20,'reveal',processing=dict(pan=.2,why='Follow the visible movement'),
                alternatives=[dict(path='b.wav',status='not_selected')])
        reopened=Cue(**cue.to_dict())
        self.assertEqual(reopened.processing,cue.processing)
        self.assertEqual(reopened.alternatives,cue.alternatives)

    def test_processed_stems_reconstruct_the_mix_with_real_overlap_and_quiet(self):
        import tempfile
        from pathlib import Path
        from hinglish_sound.mix import mix,write_wav
        from test_sound_editor_master import read,sum_stems
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rate=48000;t=np.arange(rate*3)/rate
            voice=(.15*np.sin(2*np.pi*300*t)).astype(np.float32)
            source=write_wav(root/'texture.wav',np.stack([voice[:rate]]*2))
            cues=[Cue(.2,.3,str(source),'impact',.8,-8,-20,'reveal',group_id='a',role='contact',
                      processing=dict(pan=-.5,lowpass_hz=3000,duck_db=3,why='Keep weight left and below speech')),
                  Cue(.25,.3,str(source),'whoosh',.5,-14,-20,'movement',group_id='a',role='travel')]
            result=mix(voice,[],cues,root,layered=True,composed=True)
            summed=sum_stems(result['stems'])
            self.assertLess(np.max(np.abs(summed-read(result['preview_mix']))),.0003)
            self.assertEqual(summed.shape,(2,rate*3))
            self.assertTrue(result['stems']['effects'][0]['processing_baked'])
            self.assertEqual(result['stems']['effects'][0]['speech_duck_db'],-3)

    def test_quality_check_respects_authored_speech_ducking_without_accepting_silence(self):
        import tempfile
        from pathlib import Path
        from hinglish_sound.mix import mix,write_wav
        from hinglish_sound.evaluator import mix_qa
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rate=48000;t=np.arange(rate*2)/rate
            voice=(.15*np.sin(2*np.pi*400*t)).astype(np.float32)
            source=write_wav(root/'weight.wav',np.stack([voice[:rate]]*2))
            cue=Cue(.2,.3,str(source),'impact',.8,-10,-20,'reveal',group_id='a',role='contact',
                    processing=dict(duck_db=12,why='Keep this sustained weight behind the words'))
            result=mix(voice,[],[cue],root,layered=True,composed=True)
            args=(voice,None,result['effects'],result['master'],result['speech'],[cue],2,.08)
            self.assertTrue(mix_qa(*args,layered=True,composed=True)[0]['passed'])
            result['effects'][0][1][:]=0
            self.assertFalse(mix_qa(*args,layered=True,composed=True)[0]['passed'])


if __name__=='__main__':unittest.main()
