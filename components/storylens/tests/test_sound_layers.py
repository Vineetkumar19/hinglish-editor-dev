"""Behavioral checks for motivated multilayer sound design."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from fractions import Fraction
import av

import numpy as np

from hinglish_sound.cues import Cue
from hinglish_sound.layers import plan_layers, select_layers, scene_events
from hinglish_sound.mix import mix, effect, write_wav


def cue(role, category, group='event-1', target=2., path=None):
    return Cue(target, target, path or role+'.wav', category, 1., -10., -20., 'test',
               group_id=group, role=role)


class SoundLayerTests(unittest.TestCase):
    def test_export_check_respects_bass_safety_cap_after_speech_ducking(self):
        from hinglish_eval.specs import sound_checks
        from hinglish_sound.mix import full_syllable_db
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            t=np.arange(192000)/48000
            voice=(.1*np.sin(t*220*2*np.pi)).astype(np.float32)
            source=write_wav(folder/'bass.wav',.1*np.sin(t[:48000]*35*2*np.pi))
            c=cue('contact','impact',path=str(source));c.offset_db=-2
            result=mix(voice,[],[c],folder,layered=True)
            plan=dict(settings={'layered':True,'music':False},cues=[c.to_dict()],
                      stems=result['stems'],words_db=result['words_db'],voice_peak=result['voice_peak'],
                      words_full_db=full_syllable_db(voice),lines=[{'end':4}],budget=1,gap=.65)
            checks={c.rule:c for c in sound_checks(folder,plan)}
            self.assertTrue(checks['sound.audible'].passed,checks['sound.audible'].value)
            write_wav(result['stems']['effects'][0]['path'],np.zeros((2,48000),np.float32))
            checks={c.rule:c for c in sound_checks(folder,plan)}
            self.assertFalse(checks['sound.audible'].passed)

    def test_final_export_check_understands_ducked_complementary_layers(self):
        from hinglish_eval.specs import sound_checks
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            t=np.arange(192000)/48000
            voice=(.1*np.sin(t*220*2*np.pi)).astype(np.float32)
            rows=[]
            for i,role in enumerate(('contact','detail','tail')):
                source=write_wav(folder/f'{role}.wav',.1*np.sin(t[:48000]*(300+i*80)*2*np.pi))
                rows.append(cue(role,'foley',path=str(source)))
            result=mix(voice,[],rows,folder,layered=True)
            plan=dict(settings={'layered':True,'music':False},cues=[c.to_dict() for c in rows],
                      stems=result['stems'],words_db=result['words_db'],voice_peak=result['voice_peak'],
                      lines=[{'end':4}],budget=1,gap=.65)
            checks={c.rule:c for c in sound_checks(folder,plan)}
            for key in ('sound.audible','sound.budget','sound.spacing'):
                self.assertTrue(checks[key].passed,(key,checks[key].value))
            # Deliberately inaudible output must still fail the same export check.
            for stem in result['stems']['effects']:
                write_wav(stem['path'],np.zeros((2,48000),np.float32))
            checks={c.rule:c for c in sound_checks(folder,plan)}
            self.assertFalse(checks['sound.audible'].passed)

    def test_ambience_limit_counts_layers_in_the_current_group(self):
        rows=[cue('bed','ambience','scene-1',0,'wind.wav'),
              cue('bed','ambience','scene-2',0,'rain.wav'),
              cue('texture','ambience','scene-2',0,'birds.wav')]
        for c in rows: c.length=6
        rows[0].strength=3
        kept=select_layers(rows,10,3,.65)
        self.assertEqual(len(kept),2)

    def test_malformed_model_identifier_and_role_are_ignored(self):
        valid=dict(event_id='cut',role='contact',type='impact',intent='soft hit',why='reveal',strength=2)
        class Brain:
            def ask(self,*args,**kwargs):
                return {'layers':[dict(valid,event_id=[]),dict(valid,role=[]),dict(valid,type=[]),valid]}
        rows=plan_layers(Brain(),[dict(id='cut',time=1,end=2,kind='transition',label='reveal')],
                         'reveal','serious',1,['impact'])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['event_id'],'cut')

    def test_layered_selection_mix_and_editable_export_keep_overlaps(self):
        from hinglish_sound.xml_export import export_sound_xml
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            rows=[]
            for i,(role,category) in enumerate([('bed','ambience'),('travel','whoosh'),('contact','impact')]):
                t=np.arange(48000)/48000
                source=write_wav(folder/f'{role}.wav',.08*np.sin(2*np.pi*(200+i*200)*t))
                rows.append(cue(role,category,'scene' if i==0 else 'reveal',1.,str(source)))
            selected=select_layers(rows,4.,1,.65)
            mixed=mix(np.zeros(192000,np.float32),[],selected,folder,layered=True)
            original=folder/'source.xml'
            original.write_text('<xmeml><sequence id="s"><name>Test</name><media><video/></media></sequence></xmeml>')
            target=export_sound_xml(original,Fraction(24),mixed['stems'],folder/'sound.xml')
            tree=ET.parse(target)
            clips=tree.findall('.//media/audio/track/clipitem')
            self.assertEqual(len(clips),8)  # Three overlapping stereo effects plus isolated dialogue.
            names=[c.findtext('name') for c in clips]
            self.assertTrue(any('contact' in n and 'reveal' in n for n in names))
            self.assertTrue(any('bed' in n and 'scene' in n for n in names))
            self.assertEqual(names.count('Dialogue'),2)
            self.assertEqual(len(tree.findall('.//media/audio/track')),8)

    def test_picker_batches_preserve_global_layer_indices(self):
        from hinglish_sound.director import pick
        calls=[]
        class Brain:
            def ask(self,system,data,schema,**kwargs):
                calls.append(data)
                return {'effects':[{'moment':m['moment'],'choice':0,'why':'fits'} for m in data['moments']],
                        'music':[{'section':s['section'],'choice':0,'why':'fits'} for s in data['music_sections']]}
        moments=[dict(line_text='reveal',word='reveal',type='impact',intent='soft hit',role='contact',group_id=str(i)) for i in range(19)]
        sections=[dict(mood='calm',why='reflective') for _ in range(5)]
        result=pick(Brain(),'story','serious',moments,[[{'doc':'hit'}]]*19,sections,[[{'doc':'music'}]]*5)
        self.assertEqual([r['moment'] for r in result['effects']],list(range(19)))
        self.assertEqual([r['section'] for r in result['music']],list(range(5)))
        self.assertTrue(all(len(c['moments'])<=8 and len(c['music_sections'])<=4 for c in calls))

    def test_bad_optional_action_uncertainty_does_not_crash_video_analysis(self):
        from hinglish_sound.events import normalize
        for invalid in ('unknown',None,float('nan'),float('inf'),-.5):
            rows=normalize([dict(time=1,end=2,kind='foley',precision='visual_interval',uncertainty=invalid)],3)
            self.assertEqual(rows[0]['uncertainty'],.5)

    def test_preview_retains_stereo_sound_layers(self):
        from hinglish_zoom.preview import render_preview
        with tempfile.TemporaryDirectory() as folder:
            seq=SimpleNamespace(fps=Fraction(24),frames=12,width=64,height=64,clips=[],path=Path(folder)/'x.xml')
            t=np.arange(24000)/48000
            stereo=np.stack([.1*np.sin(t*400*2*np.pi),.1*np.sin(t*900*2*np.pi)]).astype(np.float32)
            with patch('hinglish_zoom.preview.upper_layers',return_value=[]):
                out=render_preview(seq,np.ones(12),[None]*12,Path(folder)/'preview.mp4',audio=stereo)
            with av.open(str(out)) as media:
                self.assertEqual(media.streams.audio[0].codec_context.channels,2)
                audio=np.concatenate([f.to_ndarray() for f in media.decode(audio=0)],axis=1)
            self.assertGreater(np.mean(np.abs(audio[0]-audio[1])),.02)

    def test_environment_can_have_a_bed_and_a_distinct_texture(self):
        class Brain:
            def ask(self,*a,**k):
                return {'layers':[dict(event_id='scene',role=r,type='ambience',intent=i,why='forest',strength=1)
                    for r,i in [('bed','wind in forest'),('texture','distant birds')]]}
        events=[dict(id='scene',time=0,end=6,kind='ambience',precision='sampled',label='forest')]
        rows=plan_layers(Brain(),events,'walk','serious',1,['ambience'])
        self.assertEqual(len(rows),2)

    def test_one_event_can_have_complementary_layers_but_not_duplicates(self):
        event = dict(id='cut', time=2., end=3., kind='transition', precision='editor', label='reveal')
        class Brain:
            def ask(self, *args, **kwargs):
                return {'layers':[dict(event_id='cut', role=r, type=t, intent=r, why='reveal', strength=3)
                    for r,t in [('travel','whoosh'),('contact','impact'),('anticipation','riser'),
                                ('contact','impact'),('bed','ambience')]]}
        rows = plan_layers(Brain(),[event],'reveal','serious',1,['whoosh','impact','riser','ambience'])
        self.assertEqual({r['role'] for r in rows},{'travel','contact','anticipation'})
        self.assertTrue(all(r['target']==2 and r['group_id']=='cut' for r in rows))

    def test_single_still_cannot_authorize_contact_effect(self):
        class Brain:
            def ask(self,*a,**k):
                return {'layers':[dict(event_id='still',role='contact',type='foley',intent='step',why='walking',strength=2)]}
        rows=plan_layers(Brain(),[dict(id='still',time=1,end=5,kind='ambience',precision='sampled',label='forest')],
                         'walk','serious',2,['foley','ambience'])
        self.assertEqual(rows,[])

    def test_beds_do_not_consume_action_budget_or_reject_same_event_layers(self):
        rows=[cue('contact','impact'),cue('travel','whoosh'),cue('anticipation','riser'),
              cue('bed','ambience','scene',0),cue('detail','foley','event-2',2.1)]
        rows[-2].length=8
        kept=select_layers(rows,10,1,1)
        self.assertEqual({c.role for c in kept},{'contact','travel','anticipation','bed'})

    def test_exact_duplicate_asset_within_group_is_not_double_mixed(self):
        rows=[cue('contact','impact',path='same.wav'),cue('detail','foley',path='same.wav')]
        self.assertEqual(len(select_layers(rows,10,2,.5)),1)

    def test_repeated_actions_can_reuse_asset_in_separate_groups(self):
        rows=[cue('contact','foley','step1',1,'step.wav'),cue('contact','foley','step2',3,'step.wav')]
        self.assertEqual(len(select_layers(rows,10,3,.5)),2)

    def test_scene_event_indices_are_bounded_and_confidence_gated(self):
        answer={'events':[{'frame':2,'end_frame':3,'action':'scrubbing table','confidence':.92,
                          'action_kind':'continuous_physical_action','sound_evidence':'Brush repeatedly scrapes wood'},
                          {'frame':30,'end_frame':31,'action':'invented','confidence':1},
                          {'frame':1,'end_frame':2,'action':'uncertain','confidence':.2}]}
        rows=scene_events(answer,[4.,4.5,5.,5.5],6.)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['time'],5.)
        self.assertEqual(rows[0]['precision'],'visual_interval')
        self.assertEqual(rows[0]['uncertainty'],.5)

    def test_source_trim_does_not_shorten_requested_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            source=write_wav(Path(folder)/'source.wav',np.sin(np.arange(96000)*.07).astype(np.float32)*.1)
            c=cue('contact','foley',path=str(source)); c.time=0;c.source_offset=.6
            _,audio=effect(c,-18.,-6.,np.zeros(96000,np.float32),96000)
            self.assertEqual(audio.shape[1],48000)

    def test_group_mix_is_repeatable_and_export_retains_layer_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source=write_wav(Path(folder)/'source.wav',np.sin(np.arange(48000)*.07).astype(np.float32)*.1)
            cues=[cue('contact','impact',path=str(source)),cue('travel','whoosh',path=str(source))]
            result=mix(np.zeros(192000,np.float32),[],cues,folder,layered=True)
            self.assertEqual(len(result['stems']['effects']),2)
            self.assertEqual(result['stems']['effects'][0]['group_id'],'event-1')
            self.assertTrue(all(s['role'] for s in result['stems']['effects']))
            self.assertTrue(np.isfinite(result['master']).all())
            self.assertLess(np.max(np.abs(result['master'])),1)
            self.assertEqual([c.offset_db for c in cues],[-10.,-10.])


if __name__=='__main__': unittest.main()
