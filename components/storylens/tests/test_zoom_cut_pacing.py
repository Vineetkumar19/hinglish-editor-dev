import copy
from dataclasses import asdict
from pathlib import Path
from unittest import TestCase

import numpy as np

from hinglish_eval.specs import zoom_checks
from hinglish_zoom.cut_pacing import cut_events
from hinglish_zoom.curve import build_curve, quantize
from hinglish_zoom.settings import ZoomSettings, profile_for


class CutPacingTests(TestCase):
    def make_plan(self, shots, fps=30):
        settings = ZoomSettings(face=True)
        profile = profile_for(shots[-1][1])
        events = cut_events(shots, settings, profile, fps)
        frames = round(shots[-1][1]*fps)
        return dict(pacing='cuts', settings=asdict(settings), profile=asdict(profile),
                    fps=fps, events=[asdict(e) for e in events], shots=shots,
                    curve=quantize(build_curve(events,frames,fps)).tolist(),
                    anchors=[[0,0,1080,1920]]*frames, anchor_kinds=['face']*frames)

    def test_unequal_shots_hold_to_cuts_even_at_eight_seconds_and_at_ending(self):
        plan=self.make_plan([(0,5),(5,13),(13,17),(17,23),(23,31)])
        checks=zoom_checks(Path('missing'),plan)
        self.assertTrue(all(c.passed for c in checks),[(c.rule,c.value) for c in checks])
        self.assertEqual([e['kind'] for e in plan['events']],['cut_in','cut_out','cut_in','cut_out','cut_in'])
        curve=np.array(plan['curve'])
        self.assertTrue(np.all(curve[24:150]==1.12))
        self.assertTrue(np.all(curve[171:390]==1))
        self.assertEqual(curve[-1],1.12)  # no forced closing zoom-out
        for cut in (150,390,510,690):
            self.assertAlmostEqual(curve[cut-1],curve[cut],places=4)

    def test_no_cut_means_no_timer_reversal(self):
        plan=self.make_plan([(0,50)])
        self.assertEqual(len(plan['events']),1)
        self.assertTrue(np.all(np.array(plan['curve'])[24:]==1.12))
        self.assertTrue(all(c.passed for c in zoom_checks(Path('missing'),plan)))

    def test_quality_rejects_an_in_shot_return_or_missing_cut(self):
        plan=self.make_plan([(0,8),(8,13)])
        wrong=copy.deepcopy(plan)
        wrong['curve'][120:180]=[1]*60
        checks={c.rule:c for c in zoom_checks(Path('missing'),wrong)}
        self.assertFalse(checks['zoom.cuts'].passed)
        self.assertFalse(checks['zoom.hold'].passed)
        missing=copy.deepcopy(plan)
        missing['events'].pop()
        self.assertFalse(next(c for c in zoom_checks(Path('missing'),missing) if c.rule=='zoom.cuts').passed)

    def test_restored_easing_is_monotonic_gentle_at_ends_and_safe_when_very_short(self):
        for fps in (24,30,60):
            plan=self.make_plan([(0,4),(4,10)],fps)
            event=plan['events'][0]
            self.assertAlmostEqual(event['word']-event['start'],.8,delta=1/fps)
            self.assertAlmostEqual(plan['events'][1]['word']-4,.7,delta=1/fps)
            samples=np.array(plan['curve'])[:round(event['word']*fps)+1]
            speed=np.diff(samples)
            self.assertTrue(np.all(speed>0))
            self.assertLess(speed[0],speed[len(speed)//2])
            self.assertLess(speed[-1],speed[len(speed)//2])
            self.assertTrue(all(c.passed for c in zoom_checks(Path('missing'),plan)))
        tiny=self.make_plan([(0,.2),(.2,1.2)])
        self.assertTrue(all(c.passed for c in zoom_checks(Path('missing'),tiny)))

    def test_actual_reported_shots_have_one_stationary_focal_point(self):
        from fractions import Fraction
        from hinglish_zoom.xml_apply import TrackClip,motion_values
        anchors=[(-10.8,-240),(-46.2066,-60.4108),(-176.5321,-76.8242),(-5.4,9.6)]
        clip=TrackClip(None,'one',0,300,0,Fraction(30),'source.mp4',1,(0,0),True)
        for dx,dy in anchors:
            for z in np.linspace(1,1.18,91):
                _,(cx,cy)=motion_values(clip,z,(dx,dy,540,960),540,960)
                self.assertAlmostEqual(cx*540+z*dx,dx,places=6)
                self.assertAlmostEqual(cy*960+z*dy,dy,places=6)

    def test_quality_rejects_an_extra_camera_pan_even_when_scale_is_smooth(self):
        plan=self.make_plan([(0,5),(5,10)])
        plan['framing']='fixed_focal'
        curve=np.array(plan['curve'])
        plan['camera_centres']=np.column_stack(((curve-1)*.2,(curve-1)*.1)).tolist()
        self.assertTrue(next(c for c in zoom_checks(Path('missing'),plan) if c.rule=='zoom.fixed_focal').passed)
        plan['camera_centres'][15][0]+=.01
        self.assertFalse(next(c for c in zoom_checks(Path('missing'),plan) if c.rule=='zoom.fixed_focal').passed)

    def test_new_short_policy_preserves_long_major_point_policy(self):
        self.assertEqual(profile_for(50).pacing,'cuts')
        self.assertEqual(profile_for(600).pacing,'keypoints')
