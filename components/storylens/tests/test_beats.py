import importlib.util
import io
import json
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import numpy as np
from hinglish_beats.detect import analyze, effect_plan, thin, number
from hinglish_beats.service import BeatService


def clicks(path, seconds=26, stereo=False):
    rate=16000
    values=np.zeros(seconds*rate, dtype=np.float32)
    for i, sec in enumerate(np.arange(.5, seconds-.5, .5)):
        count=480
        amp=(.9,.35,.55,.35)[i%4]
        index=round(sec*rate)
        values[index:index+count]=amp*np.exp(-np.arange(count)/70)*np.cos(2*np.pi*400*np.arange(count)/rate)
    if stereo: values=np.repeat(values[:,None],2,axis=1)
    with wave.open(str(path),'wb') as out:
        out.setparams((2 if stereo else 1,2,rate,0,'NONE','not compressed'))
        out.writeframes((values*32767).astype('<i2').tobytes())
    return path


class BeatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.music=clicks(self.root/'music.wav')
    def tearDown(self):self.temp.cleanup()

    def test_real_decoder_detects_attacks_within_one_frame(self):
        plan=analyze({'path':str(self.music),'density':'strong','fps':60})
        self.assertEqual(len(plan['beats']),50)
        for beat, expected in zip(plan['beats'],np.arange(.5,25.5,.5)):
            self.assertLessEqual(abs(beat['timeline_seconds']-expected),1/60)

    def test_three_nested_densities_and_optional_clip_budget(self):
        plans=[analyze({'path':str(self.music),'density':d}) for d in ('strong','medium','light')]
        self.assertEqual([len(p['beats']) for p in plans],[50,25,10])
        for a,b in zip(plans,plans[1:]):self.assertTrue({v['frame'] for v in b['beats']}<={v['frame'] for v in a['beats']})
        limited=analyze({'path':str(self.music),'density':'medium','target_count':7})
        self.assertEqual(len(limited['beats']),7)
        self.assertGreater(limited['beats'][-1]['timeline_seconds'],20)
        self.assertEqual(len(analyze({'path':str(self.music),'target_count':999})['beats']),25)

    def test_trim_placement_and_ntsc_frame_rounding(self):
        plan=analyze({'path':str(self.music),'source_in':5,'source_out':10,'timeline_start':12,'fps':30000/1001,'density':'strong'})
        self.assertTrue(plan['beats'])
        for beat in plan['beats']:
            self.assertAlmostEqual(beat['source_seconds'],5+beat['seconds'])
            self.assertLessEqual(abs(beat['timeline_seconds']-(12+beat['seconds'])),.5/plan['fps']+.00001)
            self.assertLess(beat['timeline_seconds'],17)

    def test_silence_never_produces_grid_or_effects(self):
        with wave.open(str(self.root/'silence.wav'),'wb') as out:
            out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(b'\x00\x00'*32000)
        self.assertEqual(analyze({'path':str(self.root/'silence.wav')})['beats'],[])

    def test_stereo_uses_mono_analysis_without_double_markers(self):
        stereo=clicks(self.root/'stereo.wav',stereo=True)
        self.assertEqual(len(analyze({'path':str(stereo),'density':'strong'})['beats']),50)

    def test_rejects_bad_timing_density_and_partial_range(self):
        for extra in ({'fps':float('nan')},{'source_in':-1},{'density':'lots'},{'target_count':2.4},{'source_in':3,'source_out':2},{'source_out':40}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):analyze({'path':str(self.music),**extra})

    def test_effects_separate_and_bounded(self):
        plan=analyze({'path':str(self.music),'sequence_id':'sequence-1'});plan['id']='abc'
        result=effect_plan(plan,{'style':'punch','amount':8})
        self.assertEqual(result['analysis_id'],'abc');self.assertEqual(result['beats'],plan['beats'])
        with self.assertRaises(ValueError):effect_plan(plan,{'style':'untrusted-preset'})
        with self.assertRaises(ValueError):effect_plan(plan,{'amount':200})

    def test_job_persists_timing_and_rejects_concurrent_work(self):
        service=BeatService(self.root)
        try:
            with service.work_lock:
                job=service.start({'path':str(self.music),'density':'light'})
                with self.assertRaises(ValueError):service.start({'path':str(self.music)})
            deadline=time.monotonic()+10
            while service.snapshot(job['id'])['status'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.02)
            result=service.snapshot(job['id'])
            self.assertEqual(result['status'],'complete',result)
            self.assertEqual(len(json.loads((Path(result['folder'])/'beat-plan.json').read_text())['beats']),10)
            self.assertFalse((Path(result['folder'])/'effect-plan.json').exists())
            service.effects({'id':job['id']})
            self.assertTrue((Path(result['folder'])/'effect-plan.json').is_file())
        finally:service.pool.shutdown(wait=True)

    def test_upload_rejects_scripts_traversal_partial_and_invalid_size(self):
        service=BeatService(self.root)
        try:
            for name,length in (('bad.py',10),('ok.wav',0),('ok.wav',2*1024**3+1)):
                with self.assertRaises(ValueError):service.save_upload(name,io.BytesIO(b''),length)
            with self.assertRaises(ValueError):service.save_upload('ok.wav',io.BytesIO(b'hi'),10)
            item=service.save_upload('../../music.wav',io.BytesIO(b'hi'),2)
            self.assertTrue(Path(item['path']).is_relative_to(self.root/'output/beats/music'))
            self.assertFalse(list(self.root.rglob('*.partial')))
        finally:service.pool.shutdown(wait=True)


def resolve_panel():
    path=Path(__file__).resolve().parents[1]/'editor_plugins/davinci-resolve-studio/Hinglish Editor.py'
    spec=importlib.util.spec_from_file_location('resolve_beat_panel',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class ResolveBeatTests(unittest.TestCase):
    def test_markers_relative_to_nonzero_start_preserve_user_marks(self):
        panel=resolve_panel();timeline=Mock();project=Mock();project.GetCurrentTimeline.return_value=timeline
        timeline.GetUniqueId.return_value='one';timeline.GetSetting.return_value='30'
        timeline.GetMarkers.side_effect=[{4:{'customData':'user'},5:{'customData':'StorylensBeat:old'}},{4:{'customData':'user'}}]
        plan={'sequence_id':'one','id':'new','fps':30,'density':'medium','beats':[{'frame':4},{'frame':30}]}
        with patch.object(panel,'beat_checkpoint') as checkpoint:
            message=panel.mark_music_beats(Mock(),project,Path('.'),plan)
        timeline.DeleteMarkerAtFrame.assert_called_once_with(5)
        timeline.AddMarker.assert_called_once_with(30,'Cyan','Beat 2','Storylens medium',1,'StorylensBeat:new')
        self.assertIn('1 existing user',message);self.assertEqual(checkpoint.call_count,2)

    def test_changed_timeline_cannot_receive_old_plan(self):
        panel=resolve_panel();project=Mock();project.GetCurrentTimeline().GetUniqueId.return_value='other'
        with self.assertRaises(RuntimeError):panel.beat_timeline(project,{'sequence_id':'old','fps':30})

    def test_effects_duplicate_and_add_keyframes_at_beat_not_ten_seconds_later(self):
        panel=resolve_panel();project=Mock();original=project.GetCurrentTimeline.return_value
        original.GetUniqueId.return_value='one';original.GetSetting.return_value='30'
        original.GetName.return_value='My edit'
        original.GetTrackCount.return_value=1
        timeline=original.DuplicateTimeline.return_value;timeline.GetStartFrame.return_value=108000
        timeline.GetTrackCount.return_value=1;timeline.GetIsTrackLocked.return_value=False
        clip=Mock();clip.GetStart.return_value=108000;clip.GetEnd.return_value=108300;clip.GetFusionCompCount.return_value=0
        timeline.GetItemListInTrack.return_value=[clip]
        comp=clip.AddFusionComp.return_value;comp.GetAttrs.return_value={'COMPN_RenderStart':0}
        comp.GetToolList.side_effect=[{1:Mock()},{1:Mock()}]
        plan={'sequence_id':'one','fps':30,'style':'punch','amount':8,'duration':.24,'beats':[{'frame':60}]}
        with patch.object(panel,'beat_checkpoint'):
            message=panel.apply_music_effects(Mock(),project,Path('.'),plan)
        keys=comp.BezierSpline.return_value.SetKeyFrames.call_args.args[0]
        self.assertAlmostEqual(keys[60][1],1.08)
        self.assertIn('1 zoom pulses',message);original.DuplicateTimeline.assert_called_once();comp.Unlock.assert_called_once()


class BeatHTTPTests(unittest.TestCase):
    def setUp(self):
        from hinglish_app.server import serve
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.music=clicks(self.root/'music.wav')
        self.server,self.state=serve(self.root,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.state.port)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)
        if self.state._beats:self.state._beats.pool.shutdown(wait=True)
        self.temp.cleanup()

    def request(self,path,body=None,token=True):
        headers={'X-Hinglish-Token':self.state.token} if token else {}
        headers['Content-Type']='application/json'
        with urlopen(Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)) as response:
            return json.load(response)

    def test_page_token_and_both_actions_end_to_end(self):
        with urlopen(self.url+'/beats.html') as response:page=response.read().decode()
        self.assertIn('Beat Studio',page);self.assertNotIn('__APP_TOKEN__',page)
        job=self.request('/api/beats/analyze',{'path':str(self.music),'density':'medium','target_count':25})
        deadline=time.monotonic()+10
        while job['status'] in ('queued','running') and time.monotonic()<deadline:
            time.sleep(.02);job=self.request('/api/beats/jobs/'+job['id'])
        self.assertEqual(job['status'],'complete',job);self.assertEqual(len(job['plan']['beats']),25)
        self.assertFalse((Path(job['folder'])/'effect-plan.json').exists())
        effect=self.request('/api/beats/effects',{'id':job['id'],'video_track':2})
        self.assertEqual(effect['video_track'],2);self.assertEqual(len(effect['beats']),25)

    def test_local_token_required_on_analysis_results_effects_and_upload(self):
        for path,body in (('/api/beats/analyze',{}),('/api/beats/effects',{}),('/api/beats/jobs/missing',None),('/api/beats/upload?name=music.wav',{})):
            with self.subTest(path=path),self.assertRaises(HTTPError) as caught:self.request(path,body,token=False)
            self.assertEqual(caught.exception.code,403)

    def test_plugin_license_enforced_before_queueing_analysis(self):
        client=Mock();client.edition='plugins';client.ensure.side_effect=ValueError('Subscription required')
        self.state.license_client=client;self.state.license_clients={'plugins':client}
        with self.assertRaises(HTTPError) as caught:
            self.request('/api/beats/analyze',{'path':str(self.music),'host':'premiere'})
        self.assertEqual(caught.exception.code,400);client.ensure.assert_called_once_with('premiere')
        self.assertIsNone(self.state._beats)
