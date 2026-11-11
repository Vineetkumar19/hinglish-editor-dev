import io
import json
import tempfile
import threading
import time
import unittest
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock
import numpy as np
from hinglish_cinematic.planner import assemble, best_window, inspect_shot, boundaries
from hinglish_cinematic.render import render, effect_options
from hinglish_cinematic.service import CinematicService


def shot_info(name='shot.mp4',duration=6,fps=30,motion=.3):
    return {'path':name,'name':name,'duration':duration,'fps':fps,'samples':[
        {'time':float(t),'quality':.1 if t<2.75 else .95,'motion':motion} for t in np.arange(0,duration,.25)]}


def music_plan(path='music.wav',duration=6):
    return {'id':'beat-fixture','path':str(path),'fps':30,'duration':duration,'source_in':0,'timeline_start':0,
            'speed':1,'beats':[{'frame':int(t*30),'timeline_seconds':float(t),'strength':.8} for t in np.arange(.5,duration,.5)]}


def make_music(path,seconds=8):
    t=np.arange(round(seconds*16000))/16000
    values=.2*np.sin(2*np.pi*220*t)+.1*np.sin(2*np.pi*440*t)
    for sec in np.arange(.5,seconds,.5):
        i=round(sec*16000);values[i:i+160]+=.5*np.exp(-np.arange(160)/25)
    with wave.open(str(path),'wb') as out:
        out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes((np.clip(values,-1,1)*32767).astype('<i2').tobytes())


def make_shot(path,seconds=6,fps=30,seed=0):
    import av
    with av.open(str(path),'w') as out:
        stream=out.add_stream('libx264',rate=fps);stream.width=320;stream.height=180;stream.pix_fmt='yuv420p'
        stream.options={'preset':'ultrafast','crf':'23','threads':'2'}
        yy,xx=np.mgrid[:180,:320]
        for n in range(round(seconds*fps)):
            image=np.zeros((180,320,3),dtype=np.uint8)
            if n/fps>=2:
                image[:,:,0]=(xx+seed*30)%200+25;image[:,:,1]=(yy*2+seed*12)%170+35;image[:,:,2]=110
                x=(n*3+seed*20)%260;image[35:145,x:x+60]=230
            frame=av.VideoFrame.from_ndarray(image,format='rgb24')
            for packet in stream.encode(frame):out.mux(packet)
        for packet in stream.encode():out.mux(packet)


class CinematicPlanningTests(unittest.TestCase):
    def test_best_three_seconds_are_not_automatically_the_first_three(self):
        chosen=best_window(shot_info(),3,.3,False,False,30)
        self.assertGreaterEqual(chosen['source_in'],2.75)
        self.assertLessEqual(chosen['source_out'],6)
        self.assertEqual(chosen['speed'],1)

    def test_slow_motion_requires_sufficient_source_fps(self):
        high=shot_info(duration=1,fps=60);low=shot_info(duration=1,fps=30)
        self.assertEqual(best_window(high,2,.2,True,False,30)['speed'],.5)
        self.assertIsNone(best_window(low,2,.2,True,False,30))

    def test_action_motion_can_select_a_faster_section(self):
        shot=shot_info(motion=.5)
        for sample in shot['samples']:sample['quality']=.9
        self.assertGreater(best_window(shot,2,.95,False,True,30)['speed'],1)

    def test_no_overlap_when_source_reuse_enabled(self):
        chosen=best_window(shot_info(),2,.3,False,False,30,used=[(2.5,6)])
        self.assertLessEqual(chosen['source_out'],2.5)

    def test_shot_intervals_cover_music_without_gaps_or_offbeat_internal_cuts(self):
        plan=assemble(music_plan(),[shot_info('one'),shot_info('two'),shot_info('three')],{'pace':'cinematic','allow_slow':False,'allow_fast':False})
        self.assertEqual(plan['cuts'],[0,60,120,180])
        self.assertEqual(sum(s['duration_frames'] for s in plan['shots']),180)
        self.assertEqual(len({s['path'] for s in plan['shots']}),3)
        for a,b in zip(plan['shots'],plan['shots'][1:]):self.assertEqual(a['end_frame'],b['start_frame'])
        self.assertEqual(plan['effects'],[])

    def test_insufficient_source_fails_instead_of_freezing_or_repeating(self):
        with self.assertRaises(ValueError):assemble(music_plan(duration=15),[shot_info('one')],{'max_shot':6})
        with self.assertRaises(ValueError):assemble(music_plan(),[shot_info('one',duration=1)],{'max_shot':10,'allow_slow':False,'allow_fast':False})

    def test_effect_list_and_strength_are_not_arbitrary_filter_code(self):
        self.assertEqual(effect_options({'effects':['punch','flash','punch']})[0],['punch','flash'])
        for options in ({'effects':['movie=http://bad']},{'effects':'flash'},{'effect_amount':float('nan')}):
            with self.assertRaises(ValueError):effect_options(options)

    def test_silent_music_and_retimed_music_rejected_for_reel(self):
        plan=music_plan();plan['beats']=[]
        with self.assertRaises(ValueError):assemble(plan,[shot_info()],{})
        plan=music_plan();plan['speed']=2
        with self.assertRaises(ValueError):assemble(plan,[shot_info()],{})


class CinematicRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.music=self.root/'music.wav';make_music(self.music)
        self.paths=[self.root/f'shot-{i}.mp4' for i in range(3)]
        for i,p in enumerate(self.paths):make_shot(p,seed=i)
    def tearDown(self):self.temp.cleanup()

    def test_real_video_selection_and_both_render_steps_keep_sync_audio_and_originals(self):
        import hashlib
        import av
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [self.music,*self.paths]}
        shots=[inspect_shot(p) for p in self.paths]
        self.assertTrue(all(len(s['samples'])>=20 for s in shots))
        plan=assemble(music_plan(self.music),shots,{'pace':'cinematic','allow_slow':False,'allow_fast':False,'split_music':True})
        self.assertTrue(all(s['source_in']>=2 for s in plan['shots']))
        base=render(plan,self.root/'base',{'resolution':'test','aspect':'16:9'},lambda *_:None,threading.Event())
        self.assertEqual(base['frames'],180);self.assertEqual(base['shot_count'],3)
        xml=ET.parse(base['xml_files'][0]);clips=xml.findall('.//media/video/track/clipitem')
        self.assertEqual([(int(c.findtext('start')),int(c.findtext('end'))) for c in clips],[(0,60),(60,120),(120,180)])
        for track in xml.findall('./sequence/media/audio/track'):
            self.assertEqual([(int(c.findtext('in')),int(c.findtext('out'))) for c in track],[(0,60),(60,120),(120,180)])
        with wave.open(str(self.root/'base/soundtrack.wav'),'rb') as file:
            sound=np.frombuffer(file.readframes(file.getnframes()),dtype='<i2').reshape(-1,2)/32768
            self.assertEqual(file.getnframes(),288000)
        for point in (2,4):self.assertGreater(float(np.sqrt(np.mean(sound[int((point-.01)*48000):int((point+.01)*48000)]**2))),.02)
        applied=render(json.loads(json.dumps(plan)),self.root/'effects',{'effects':['punch','flash','shake'],'effect_amount':8},lambda *_:None,threading.Event(),base['folder'])
        self.assertEqual(applied['frames'],180);self.assertEqual(applied['plan']['effects'],['punch','flash','shake'])
        self.assertNotEqual(Path(base['preview']).read_bytes(),Path(applied['preview']).read_bytes())
        for p,digest in hashes.items():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),digest)
        with av.open(applied['preview']) as video:self.assertEqual(sum(1 for _ in video.decode(video=0)),180)

    def test_cancelled_render_does_not_start_or_claim_completion(self):
        plan=assemble(music_plan(self.music),[inspect_shot(p) for p in self.paths],{'pace':'cinematic'})
        stop=threading.Event();stop.set()
        with self.assertRaisesRegex(RuntimeError,'cancelled'):render(plan,self.root/'cancelled',{'resolution':'test'},lambda *_:None,stop)
        self.assertFalse((self.root/'cancelled/CINEMATIC_REEL.mp4').exists())

    def test_actual_slow_motion_render_uses_source_duration_not_output_trim(self):
        import av
        path=self.root/'high-fps.mp4';make_shot(path,seconds=3,fps=60)
        plan=assemble(music_plan(self.music,duration=2),[inspect_shot(path)],{'pace':'cinematic','allow_fast':False,'fps':30})
        self.assertEqual(plan['shots'][0]['speed'],.5)
        result=render(plan,self.root/'slow',{'resolution':'test','aspect':'16:9'},lambda *_:None,threading.Event())
        self.assertEqual(result['frames'],60)
        with av.open(result['preview']) as video:self.assertEqual(sum(1 for _ in video.decode(video=0)),60)


class CinematicServiceTests(unittest.TestCase):
    def test_upload_limits_and_interrupted_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            service=CinematicService(temp,Mock())
            try:
                for name,length in (('payload.py',2),('clip.mp4',0)):
                    with self.assertRaises(ValueError):service.upload(name,io.BytesIO(b'hi'),length)
                with self.assertRaises(ValueError):service.upload('clip.mp4',io.BytesIO(b'hi'),5)
                self.assertFalse(list(Path(temp).rglob('*.partial')))
            finally:service.pool.shutdown(wait=True)
