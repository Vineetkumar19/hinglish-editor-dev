import json
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import av
import numpy as np

from hinglish_zoom.curve import ZoomEvent
from hinglish_zoom.effects import soundtrack, write_wav
from hinglish_zoom.settings import ZoomSettings


class ZoomEffectsTests(TestCase):
    def test_sound_replacement_locks_existing_cut_overlays(self):
        from hinglish_zoom.effects import choose
        pool=[{'category':'whoosh','name':str(i),'heard':['whoosh'],'match':.8,'duration':.6} for i in range(6)]
        events=[ZoomEvent('cut_in',i*4,i*4+.8,i*4+4,i*4+4,1.18) for i in range(6)]
        locks=[{'event':1,'kind':'soft_flash','cut':4},{'event':3,'kind':'light_sweep_left','cut':12}]
        brain=Mock()
        def answer(system,data,schema,**kw):
            return {'choices':{key:{'event':p['properties']['event']['enum'][0],
                'asset':p['properties']['asset']['enum'][0],'overlay':p['properties']['overlay']['enum'][0],
                'reason':'Keep approved overlay; use whoosh'}
                for key,p in schema['properties']['choices']['properties'].items()}}
        brain.json.side_effect=answer
        with patch('hinglish_zoom.sound_policy.approved',return_value=None),patch('hinglish_zoom.effects.candidates',return_value=pool),patch('hinglish_broll.llm.LocalLLM',return_value=brain):
            choices,_=choose(Path.cwd(),events,ZoomSettings(sounds=True,overlays=True),lambda _:None,
                             cuts=[e.start for e in events],locked_overlays=locks)
        self.assertEqual([(r['event'],r['overlay']) for r in choices if r['overlay']!='none'],
                         [(1,'soft_flash'),(3,'light_sweep_left')])

    def test_missing_approved_sound_stops_instead_of_using_general_library(self):
        from hinglish_zoom.sound_policy import approved
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'config.zoom-sounds.local.json').write_text(json.dumps({'assets':[{'path':'missing-whoosh.wav'}]}))
            with self.assertRaisesRegex(ValueError,'missing-whoosh.wav'):approved(root)

    def test_missing_policy_does_not_reenable_old_library(self):
        from hinglish_zoom.sound_policy import approved
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'library/zoom-approved/whoosh').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,'settings are missing'):approved(root)

    def test_owner_allowlist_excludes_other_library_sounds_and_allows_one_file(self):
        from hinglish_zoom.effects import choose
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);file=root/'owner-whoosh.wav';file.write_bytes(b'fixture')
            (root/'config.zoom-sounds.local.json').write_text(json.dumps({'id':'owner-basic-whooshes',
                'assets':[{'path':file.name,'name':'My whoosh'}]}))
            pool=[{'category':'whoosh','path':str(file),'name':'My whoosh','heard':['whoosh'],'match':.8,'duration':.5},
                  {'category':'impact','path':'foreign-hit.wav','name':'Hit','heard':['hit'],'match':.8,'duration':.5},
                  {'category':'whoosh','path':'old-library-whoosh.wav','name':'Old whoosh','heard':['whoosh'],'match':.8,'duration':.5}]
            events=[ZoomEvent('cut_in',i*4,i*4+.8,i*4+4,i*4+4,1.18) for i in range(4)]
            brain=Mock()
            def answer(system,data,schema,**kw):
                self.assertEqual([a['name'] for a in data['sounds']],['My whoosh'])
                return {'choices':{key:{'event':p['properties']['event']['enum'][0],
                    'asset':p['properties']['asset']['enum'][0],'overlay':'none','reason':'Approved whoosh'}
                    for key,p in schema['properties']['choices']['properties'].items()}}
            brain.json.side_effect=answer
            with patch('hinglish_zoom.effects.candidates',return_value=pool),patch('hinglish_broll.llm.LocalLLM',return_value=brain):
                choices,actual=choose(root,events,ZoomSettings(sounds=True),lambda _:None)
            self.assertEqual(len(choices),4)
            self.assertEqual([a['path'] for a in actual],[str(file)])

    def test_choice_menu_bounds_heavy_effects_and_cut_overlay_density(self):
        from hinglish_zoom.effects import choose
        pool=[{'category':family,'name':str(i),'heard':['whoosh'],'match':.8,'duration':.6}
              for i,family in enumerate(['whoosh']*6+['impact','riser'])]
        events=[ZoomEvent('cut_in' if i%2==0 else 'cut_out',i*4,i*4+.8,i*4+4,i*4+4,1.18) for i in range(12)]
        brain=Mock()
        seen={}
        def answer(system,data,schema,**kw):
            fields=schema['properties']['choices']['properties'];seen.update(fields)
            rows={}
            for key,field in fields.items():
                p=field['properties'];i=p['event']['enum'][0]
                rows[key]={'event':i,'asset':p['asset']['enum'][0],
                           'overlay':next((x for x in p['overlay']['enum'] if x!='none'),'none'),
                           'reason':'Air movement on the cut'}
            return {'choices':rows}
        brain.json.side_effect=answer
        with patch('hinglish_zoom.sound_policy.approved',return_value=None),patch('hinglish_zoom.effects.candidates',return_value=pool),patch('hinglish_broll.llm.LocalLLM',return_value=brain):
            choices,_=choose(Path.cwd(),events,ZoomSettings(sounds=True,overlays=True),lambda _:None)
        for family in ('impact','riser'):
            allowed=sum(any(pool[i]['category']==family for i in f['properties']['asset']['enum']) for f in seen.values())
            self.assertLessEqual(allowed,2)
        overlay_times=[events[r['event']].start for r in choices if r['overlay']!='none']
        self.assertLessEqual(len(overlay_times),4);self.assertGreaterEqual(min(overlay_times),4)
        self.assertTrue(all(b-a>=6 for a,b in zip(overlay_times,overlay_times[1:])))

    def test_optional_flags_reach_runner_and_current_request_wins(self):
        from hinglish_app.assistant_zoom_plan import plan
        from hinglish_app.assistant_plan import job_payload
        opts={'zoom_style':'smooth','zoom_strength':'medium','zoom_frequency':'medium',
              'zoom_face':True,'zoom_jump_cuts':False,'zoom_sounds':True,'zoom_overlays':False}
        brain=Mock()
        brain.json.return_value={'reply':'Starting.','question':'','combine':False,
                                 'steps':[{'tool':'zoom','options':opts}]}
        result=plan(brain,'Run SmartZoom with sound effects, without cut overlays.',[],[],{})
        schema=brain.json.call_args.args[2]['properties']['steps']['items']['properties']['options']['properties']
        self.assertEqual(schema['zoom_sounds']['enum'],[True])
        self.assertEqual(schema['zoom_overlays']['enum'],[False])
        payload=job_payload(result['steps'][0],['approved.mp4'])
        self.assertTrue(payload['zoom_sounds']); self.assertFalse(payload['zoom_overlays'])
        self.assertFalse(ZoomSettings().sounds); self.assertFalse(ZoomSettings().overlays)

    def test_real_audio_peak_sync_voice_preserved_and_no_clipping(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);rate=48000
            t=np.arange(rate*8)/rate
            voice=(.3*np.sin(2*np.pi*180*t)).astype(np.float32)
            s=np.arange(rate)/rate
            effect=(np.sin(s*2*np.pi*800)*np.exp(-((s-.35)/.12)**2)).astype(np.float32)
            path=folder/'effect.wav';write_wav(path,effect)
            events=[ZoomEvent('cut_in',0,.8,4,4,1.18),ZoomEvent('cut_out',4,4.7,8,8,1.18)]
            choices=[{'event':i,'asset':0,'reason':'Air movement','overlay':'none'} for i in range(2)]
            mix,cues,stems,stats=soundtrack(voice,events,choices,[{'path':str(path),'category':'whoosh','name':'airy'}],folder)
            self.assertEqual(len(cues),2);self.assertEqual(len(mix),len(voice))
            self.assertLessEqual(np.max(abs(mix)),.981)
            for cue,event in zip(cues,events):
                self.assertEqual(cue['time'],event.start)
                self.assertAlmostEqual(cue['length'],event.word-event.start,places=6)
                self.assertLessEqual(cue['body_db_relative'],-21.99)
            with wave.open(str(folder/'sound/voice-only.wav'),'rb') as w:
                saved=np.frombuffer(w.readframes(w.getnframes()),'<i2').reshape(-1,2)[:,0]/32767
            np.testing.assert_allclose(saved,voice*stats['voice_gain'],atol=1/32767)
            self.assertLess(stats['effects_db_relative'],-6)

    def test_whoosh_fills_point_four_and_point_six_second_moves_at_quiet_level(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);rate=48000
            t=np.arange(rate*6)/rate;voice=(.3*np.sin(t*2*np.pi*200)).astype(np.float32)
            q=np.arange(rate//4)/rate;source=(np.sin(q*2*np.pi*850)*np.sin(np.linspace(0,np.pi,len(q)))**2).astype(np.float32)
            file=folder/'short-whoosh.wav';write_wav(file,source)
            events=[ZoomEvent('cut_in',1,1.4,3,3,1.18),ZoomEvent('cut_out',4,4.6,6,6,1.18)]
            rows=[{'event':i,'asset':0,'reason':'Movement','overlay':'none'} for i in range(2)]
            _,cues,_,stats=soundtrack(voice,events,rows,[{'path':str(file),'category':'whoosh','name':'basic'}],folder)
            for cue,count in zip(cues,(19200,28800)):
                with wave.open(cue['stem'],'rb') as w:self.assertEqual(w.getnframes(),count)
                self.assertLessEqual(cue['body_db_relative'],-21.99)
            self.assertEqual([c['time'] for c in cues],[1,4])
            self.assertLess(stats['effects_db_relative'],-18)

    def test_overlay_is_brief_transparent_and_has_no_camera_motion(self):
        from hinglish_zoom.overlays import render
        with tempfile.TemporaryDirectory() as name:
            for kind in ('soft_flash','light_sweep_left','light_sweep_right'):
                path=Path(name)/(kind+'.mov')
                render(path,64,96,Fraction(30),9,kind)
                with av.open(str(path)) as c:
                    frames=[f.to_ndarray(format='rgba') for f in c.decode(video=0)]
                self.assertEqual(len(frames),9)
                self.assertEqual(np.max(frames[0][:,:,3]),0)
                self.assertEqual(np.max(frames[-1][:,:,3]),0)
                self.assertLessEqual(max(np.max(f[:,:,3]) for f in frames),57)
                self.assertGreater(max(np.max(f[:,:,3]) for f in frames),15)

    def test_real_footage_transitions_preserve_endpoints_and_do_not_reframe(self):
        from hinglish_zoom.overlays import transition_frame,FOOTAGE_STYLES
        rng=np.random.default_rng(9)
        a=rng.integers(0,256,(96,64,3),dtype=np.uint8)
        b=rng.integers(0,256,(96,64,3),dtype=np.uint8)
        for kind in FOOTAGE_STYLES:
            np.testing.assert_array_equal(transition_frame(a,b,0,kind),a)
            np.testing.assert_array_equal(transition_frame(a,b,1,kind),b)
            # Identical flat footage must never acquire a camera shift or flash.
            plain=np.full_like(a,93)
            np.testing.assert_array_equal(transition_frame(plain,plain,.5,kind),plain)
            middle=transition_frame(a,b,.5,kind)
            self.assertEqual(middle.shape,a.shape)
            self.assertFalse(np.array_equal(middle,a))

    def test_transition_comparison_locks_first_video_sound_choices(self):
        from hinglish_zoom.effects import choose
        pool=[{'path':f'basic-{i}.wav','category':'whoosh','name':str(i),'heard':['whoosh'],'match':.8,'duration':.6} for i in range(6)]
        events=[ZoomEvent('cut_in' if i%2==0 else 'cut_out',i*4,i*4+.8,i*4+4,i*4+4,1.18) for i in range(12)]
        locked=[{'event':i,'path':pool[i%3]['path']} for i in range(12)]
        brain=Mock()
        def answer(system,data,schema,**kw):
            rows={}
            for key,f in schema['properties']['choices']['properties'].items():
                p=f['properties'];i=p['event']['enum'][0]
                self.assertEqual(p['asset']['enum'],[i%3])
                rows[key]={'event':i,'asset':i%3,'overlay':p['overlay']['enum'][-1],'reason':'Same sound, soft real cut transition'}
            return {'choices':rows}
        brain.json.side_effect=answer
        with patch('hinglish_zoom.sound_policy.approved',return_value=None),patch('hinglish_zoom.effects.candidates',return_value=pool),patch('hinglish_broll.llm.LocalLLM',return_value=brain):
            choices,_=choose(Path.cwd(),events,ZoomSettings(sounds=True,overlays=True),lambda _:None,
                             locked_sounds=locked,footage_source='approved.mp4')
        transitions=[r for r in choices if r['overlay']!='none']
        self.assertEqual(len(transitions),4)
        self.assertEqual({r['overlay'] for r in transitions},{'soft_dissolve','soft_wipe_left','soft_wipe_right'})

    def test_copied_approved_export_reuses_plan_and_detects_source_change(self):
        from hinglish_zoom.provenance import save,load
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);folder=root/'output/zoom/demo';folder.mkdir(parents=True)
            source=root/'original.mp4';source.write_bytes(b'original')
            seq=Mock(clips=[Mock(path=str(source))])
            plan={'timeline':'base.xml','framing':'fixed_focal','curve':[1,1.18]}
            path=folder/'zoom-plan.json';path.write_text(json.dumps(plan))
            video=root/'output/approved.mp4';video.write_bytes(b'export')
            with patch('hinglish_zoom.xml_apply.Sequence',return_value=seq):
                save(video,path)
                copied=root/'copied.mp4';copied.write_bytes(video.read_bytes())
                self.assertEqual(load(root,copied)['curve'],[1,1.18])
                staged=root/'job/media';staged.mkdir(parents=True)
                (staged/'0000-approved.mp4').write_bytes(video.read_bytes())
                self.assertEqual(load(root,staged)['curve'],[1,1.18])
                source.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'source has changed'):load(root,copied)
