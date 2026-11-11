import random
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from hinglish_broll.phrases import Phrase
from hinglish_cut.model import Cut, Media, Word
from hinglish_cut.xml_export import export_xml
from hinglish_zoom.curve import ZoomEvent, build_curve, ease_in_out, quantize
from hinglish_zoom.events import ZoomMoment, build_events, jump_cut_baseline, locate_word, schedule
from hinglish_zoom.planner import validate
from hinglish_zoom.settings import ZoomSettings, profile_for
from hinglish_zoom.xml_apply import Sequence, TrackClip, apply_curve, motion_values


def media(path, seconds=20, width=1080, height=1920):
    return Media(Path(path).stem, str(path), seconds, '30', width, height, 2, 48000)


class CurveTests(unittest.TestCase):
    def test_smooth_zoom_is_eased_monotonic_and_lands_on_the_word(self):
        e = ZoomEvent('smooth', 1.0, 1.45, 3.0, 3.4, 1.15)
        curve = build_curve([e], 150, 30)
        self.assertEqual(curve[29], 1.0)                      # before start
        self.assertAlmostEqual(curve[round(1.45 * 30)], 1.15)  # full zoom exactly on the stressed word
        ramp = curve[30:44]
        self.assertTrue(np.all(np.diff(ramp) >= 0))
        # eased: slow start, faster middle, slow landing
        steps = np.diff(curve[30:45])
        self.assertLess(steps[0], steps[6]); self.assertLess(steps[-1], steps[6])
        self.assertTrue(np.all(np.diff(curve[90:103]) <= 0))  # zoom-out goes back down
        self.assertEqual(curve[103], 1.0)

    def test_no_jitter_frame_to_frame_change_is_bounded(self):
        from hinglish_zoom.events import make_event
        words = [Word('Paanch', 10.0, 10.4), Word('hazaar', 10.45, 10.9)]
        phrase = Phrase(0, 10.0, 10.9, 'Paanch hazaar')
        for fps in (24, 30, 60):
            for duration in (60, 1500):
                for strength in ('subtle', 'medium', 'strong'):
                    level = ZoomSettings(strength=strength).level
                    e = make_event(ZoomMoment(0, 'hazaar', 2, 'emphasis'), phrase, words[1], 'smooth', level,
                                   profile_for(duration))
                    steps = np.diff(build_curve([e], 20 * fps, fps))
                    # comfortable peak speed at any frame rate: Reels <= 70 %/s, YouTube <= 50 %/s
                    limit = .70 if duration <= 180 else .50
                    self.assertLessEqual(np.abs(steps).max() * fps, limit, (fps, duration, strength))
                    # one clean rise then one clean fall: no back-and-forth wobble
                    signs = np.sign(steps[np.abs(steps) > 1e-12])
                    self.assertEqual(np.count_nonzero(np.diff(signs)), 1, (fps, duration, strength))

    def test_punch_is_instant_and_impact_overshoots_then_settles(self):
        punch = build_curve([ZoomEvent('punch', 1, 1, 2, 2, 1.2)], 90, 30)
        self.assertEqual((punch[29], punch[30], punch[59], punch[60]), (1.0, 1.2, 1.2, 1.0))
        impact = build_curve([ZoomEvent('impact', 1, 1, 2.5, 2.5, 1.2, settle=.3)], 90, 30)
        self.assertGreater(impact[30], 1.2)
        self.assertAlmostEqual(impact[45], 1.2)
        self.assertTrue(np.all(np.diff(impact[30:40]) <= 0))

    def test_reveal_starts_zoomed_and_eases_out(self):
        c = build_curve([ZoomEvent('reveal', 1, 1, 1, 2, 1.2)], 90, 30)
        self.assertAlmostEqual(c[30], 1.2)
        self.assertTrue(np.all(np.diff(c[30:60]) <= 0))
        self.assertEqual(c[60], 1.0)

    def test_rounding_never_freezes_a_frame_inside_an_ease(self):
        self.assertEqual([round(v, 4) for v in quantize([1.00049, 1.12344])], [1.0005, 1.1234])
        self.assertAlmostEqual(ease_in_out(.5), .5)
        # a subtle 8% zoom easing in over 0.8 s at 30 fps: every frame must move (a held frame = stutter)
        ramp = quantize(build_curve([ZoomEvent('smooth', 1.0, 1.8, 3.0, 3.8, 1.08)], 150, 30))[31:54]
        self.assertTrue(np.all(np.diff(ramp) > 0), ramp)


class EventTests(unittest.TestCase):
    def setUp(self):
        self.words = [Word('Bhai', 5.0, 5.3), Word('AC', 5.4, 5.8), Word('nahin', 5.9, 6.3), Word('tha.', 6.35, 6.6),
                      Word('Paanch', 22.0, 22.4), Word('hazaar', 22.45, 22.9), Word('rupaye!', 23.0, 23.5)]
        self.phrases = [Phrase(0, 5.0, 6.6, 'Bhai AC nahin tha.'), Phrase(1, 22.0, 23.5, 'Paanch hazaar rupaye!')]

    def test_zoom_lands_on_the_stressed_word(self):
        self.assertEqual(locate_word(self.phrases[0], self.words, 'nahin').start, 5.9)
        self.assertEqual(locate_word(self.phrases[1], self.words, 'hazaar,').start, 22.45)
        self.assertEqual(locate_word(self.phrases[1], self.words, 'missing').text, 'Paanch')

    def test_mixed_style_uses_different_zoom_types(self):
        settings = ZoomSettings(style='mixed')
        moments = [ZoomMoment(0, 'nahin', 2, 'emphasis'), ZoomMoment(1, 'hazaar', 3, 'emphasis')]
        events = build_events(moments, self.phrases, self.words, settings, profile_for(60), 60,select=False)
        self.assertEqual(list(dict.fromkeys(e.kind for e in events)), ['smooth', 'impact'])
        self.assertAlmostEqual(events[0].word, 5.9)
        level = 1 + .12 * .85                          # strength 2 = 85% of the chosen zoom
        self.assertAlmostEqual(events[0].start, 5.9 - profile_for(60).ramp_in * (.8 + (level - 1) * 2))
        self.assertAlmostEqual(events[-1].level, 1.12)

    def test_zoom_word_given_with_the_wrong_line_is_found_in_the_right_line(self):
        from hinglish_zoom.events import owner_phrase
        moment = ZoomMoment(0, 'hazaar', 3, 'emphasis')           # word is really in phrase 1
        self.assertEqual(owner_phrase(self.phrases, self.words, moment).id, 1)

    def test_word_is_never_borrowed_from_a_far_away_line(self):
        from hinglish_zoom.events import owner_phrase
        phrases = [Phrase(i, i * 3.0, i * 3.0 + 2, f'line {i}') for i in range(20)]
        words = [Word('kahaan', 12.5, 12.9)]                          # "kahaan" only in line 4
        phrases[4] = Phrase(4, 12.0, 14.0, 'tamilnaadu mein kahaan')
        moment = ZoomMoment(17, 'kahaan', 2, until_id=18)             # model meant line 17
        self.assertEqual(owner_phrase(phrases, words, moment).id, 17)

    def test_repeated_word_reference_keeps_its_exact_spoken_time(self):
        from unittest.mock import Mock
        from hinglish_zoom.word_candidates import plan_candidates
        phrase = Phrase(0, 1, 4, 'price market price rises')
        words = [Word(text, t, t+.4) for text,t in [('price',1),('market',2),('price',3),('rises',3.5)]]
        llm = Mock()
        llm.json.side_effect = lambda system,data,schema,**kwargs: {'choices':[
            {'choice':i,'strength':3,'reason':'A supported key statement'}
            for i in schema['properties']['choices']['items']['properties']['choice']['enum']]}
        moments = plan_candidates(llm,[phrase],profile_for(30),lambda _:None,{},words)
        self.assertEqual(moments[2].word_time,3)
        events = build_events([moments[2]],[phrase],words,ZoomSettings(),profile_for(30),30)
        self.assertEqual(events[0].word,3)
        self.assertEqual(llm.json.call_args.args[2]['properties']['choices']['items']['properties']['choice']['enum'],[0,1,2,3])

    def test_smooth_default_never_jumps(self):
        moments = [ZoomMoment(0, 'nahin', 3, 'reveal'), ZoomMoment(1, 'hazaar', 3, 'emphasis')]
        events = build_events(moments, self.phrases, self.words, ZoomSettings(), profile_for(60), 60)
        self.assertEqual(ZoomSettings().style, 'smooth')
        self.assertTrue(all(e.kind in ('smooth', 'push') for e in events))

    def test_zooms_are_used_sparingly(self):
        self.assertEqual(profile_for(45).cadence_min,0)         # important points need not wait ten seconds
        self.assertEqual(profile_for(45).cadence_max,10)
        self.assertEqual(profile_for(45).hook_deadline,3)
        self.assertGreaterEqual(profile_for(1500).spacing, 20)

    def test_smooth_zoom_keeps_in_and_out_movement_at_shot_changes(self):
        from hinglish_zoom.events import fit_to_shots
        shots = [(0, 8.3), (8.3, 12.2), (12.2, 20)]
        crossing = ZoomEvent('smooth', 9.2, 10.0, 14.0, 14.7, 1.12)          # point continues after a cut
        first, = fit_to_shots([crossing], shots)
        self.assertEqual(first, crossing)  # a cut cannot shorten the four-second close hold
        self.assertEqual(first.hold_end-first.word,4)
        just_after_cut = ZoomEvent('smooth', 7.9, 8.4, 10, 10.7, 1.12)        # no room to ease in after the cut
        piece, = fit_to_shots([just_after_cut], shots)
        self.assertAlmostEqual(piece.start, 7.9)
        self.assertAlmostEqual(piece.word, 8.4)                           # actual word stays at its source time
        self.assertGreater(piece.end, piece.hold_end)
        too_late = ZoomEvent('smooth', 11.2, 12.0, 13, 13.7, 1.12)            # only 0.2 s before the cut
        piece, = fit_to_shots([too_late], shots)
        self.assertAlmostEqual(piece.word, 12.0)                         # continuous movement across the cut
        self.assertAlmostEqual(piece.end-piece.hold_end, .7)
        self.assertEqual(fit_to_shots([too_late], [(0,12.2),(12.2,13.5)]), [])

    def test_zoom_stays_in_for_the_whole_point(self):
        from hinglish_zoom.events import make_event
        words = [Word('Flat', 30.0, 30.3), Word('milna', 30.35, 30.7), Word('impossible', 30.8, 31.5)]
        start, end = Phrase(10, 30.0, 31.6, 'Flat milna impossible'), Phrase(12, 33.0, 35.4, 'PG bhi nahin')
        e = make_event(ZoomMoment(10, 'impossible', 3, until_id=12), start, words[2], 'smooth', 1.12,
                       profile_for(600), until=end)
        self.assertAlmostEqual(e.word, 30.8)
        self.assertAlmostEqual(e.hold_end, 35.55)                           # through the end of the point
        self.assertGreater(e.end, e.hold_end)                               # then eases back to wide

    def test_short_cadence_uses_spread_highlights_and_long_has_no_timer(self):
        short = profile_for(60)
        candidates = [ZoomEvent('smooth',t-.8,t,t+3,t+3.7,1.18,strength=3,text=f'Key point at {t}')
                      for t in (1.5,10,18.5,27,35.5,44,52.5)]
        selected = schedule(candidates, short, 60)
        self.assertEqual([e.word for e in selected],[1.5,10,18.5,27,35.5,44,52.5])
        self.assertEqual((short.cadence_min,short.cadence_max),(0,10))
        self.assertTrue(all(3 <= b.start-a.end <= 5 for a,b in zip(selected,selected[1:])))
        # Two real long-video key points can be close together; no 25-second timer.
        long = profile_for(600)
        self.assertEqual(long.cadence_max, 0)
        self.assertEqual(len(schedule([candidates[0], candidates[2]], long, 600)), 2)

    def test_one_zoom_is_not_a_cadence_pass_for_a_minute_short(self):
        from dataclasses import asdict
        from hinglish_eval.specs import zoom_checks
        plan = {'settings': asdict(ZoomSettings(face=False)), 'profile': asdict(profile_for(60)),
                'fps': 30, 'curve': [1.0]*1800,
                'events': [dict(kind='smooth', start=4.2, word=5, hold_end=7, end=7.7,
                                level=1.12, text='important point', word_text='important', strength=3)]}
        check = next(c for c in zoom_checks(Path('missing'), plan) if c.rule == 'zoom.cadence')
        self.assertTrue(check.hard)
        self.assertFalse(check.passed)

    def test_hook_must_land_within_three_seconds(self):
        from dataclasses import asdict
        from hinglish_eval.specs import zoom_checks
        plan={'settings':asdict(ZoomSettings(face=False)),'profile':asdict(profile_for(20)),
              'fps':30,'curve':[1.0]*600,'events':[]}
        for first,expected in [(1.5,True),(4.0,False)]:
            plan['events']=[dict(kind='smooth',start=max(0,t-.8),word=t,hold_end=t+1,end=t+1.7,
                                text='Important statement',word_text='Important',strength=3) for t in (first,first+9)]
            check=next(c for c in zoom_checks(Path('missing'),plan) if c.rule=='zoom.hook')
            self.assertEqual(check.passed,expected)

    def test_real_episode_cut_does_not_compress_gentle_ramps(self):
        from hinglish_zoom.events import fit_to_shots
        from hinglish_eval.specs import zoom_checks
        from dataclasses import asdict
        event = ZoomEvent('smooth', 5.534, 6.224, 9.224, 9.822, 1.06,
                          text='das baje', word_text='das')
        shots = [(0, 5.733), (5.733, 8.367), (8.367, 12)]
        piece, = fit_to_shots([event], shots)
        self.assertAlmostEqual(piece.start, 5.534)
        self.assertAlmostEqual(piece.word - piece.start, .690)
        self.assertAlmostEqual(piece.end - piece.hold_end, .598)
        settings, profile = ZoomSettings(strength='subtle', face=False), profile_for(35.6)
        plan = {'settings': asdict(settings), 'profile': asdict(profile),
                'events': [asdict(piece)], 'shots': shots, 'fps': 30,
                'curve': quantize(build_curve([piece], 360, 30)).tolist()}
        checks = {c.rule: c for c in zoom_checks(Path(self._testMethodName), plan)}
        self.assertTrue(checks['zoom.no_jumps'].passed)
        self.assertTrue(checks['zoom.eased'].passed)
        # Previously a static crop at a cut was incorrectly accepted as smooth.
        plan['events'] = [dict(asdict(piece), word=piece.start, hold_end=piece.end)]
        self.assertFalse({c.rule: c for c in zoom_checks(Path('missing'), plan)}['zoom.eased'].passed)
        # A cut is no exception to the owner's minimum settled hold.
        short = dict(asdict(piece), start=7.2, word=7.5,end=8.367,hold_end=8.0)
        plan['events'] = [short]
        self.assertFalse({c.rule: c for c in zoom_checks(Path('missing'), plan)}['zoom.hold'].passed)
        plan['events'][0] = dict(short, end=8.2, hold_end=8.0)
        self.assertFalse({c.rule: c for c in zoom_checks(Path('missing'), plan)}['zoom.hold'].passed)

    def test_each_zoom_uses_its_own_face_position(self):
        from hinglish_zoom.pipeline import anchors_for
        a = ZoomEvent('smooth', 1, 1.5, 2, 2.5, 1.12)
        b = ZoomEvent('smooth', 10, 10.5, 11, 11.5, 1.12)
        anchors = anchors_for([a, b], [(10.0, -300.0, 1080, 1920), (-50.0, 400.0, 1080, 1920)], 400, 30)
        self.assertEqual(anchors[40], (10.0, -300.0, 1080, 1920))
        self.assertEqual(anchors[310], (-50.0, 400.0, 1080, 1920))
        self.assertIsNone(anchors[150])

    def test_schedule_keeps_spacing_and_skips_zooms_under_broll(self):
        profile = profile_for(60)
        events = [ZoomEvent('smooth', t - .45, t, t + 1, t + 1.4, 1.15, strength=2) for t in (3, 4, 9, 20)]
        chosen = schedule(events, profile, 60, blocked=[(19, 22)])
        words = [e.word for e in chosen]
        self.assertNotIn(20, words)
        for a, b in zip(chosen, chosen[1:]):
            self.assertGreaterEqual(b.word - a.word, profile.spacing - 1e-6)
            self.assertGreaterEqual(b.start, a.end + profile.gap - 1e-6)

    def test_long_form_is_calmer_than_reels(self):
        short, long = profile_for(60), profile_for(1500)
        self.assertGreater(long.spacing, short.spacing)
        self.assertGreater(long.ramp_in, short.ramp_in)
        self.assertLessEqual(profile_for(60,'low').cadence_max,10)
        self.assertEqual(profile_for(60,'high').cadence_max,10)  # frequency cannot squeeze 3-5 s holds

    def test_continuous_hold_changes_verified_anchor_only_at_the_cut(self):
        from hinglish_zoom.pipeline import anchors_for,verified_shot_segments
        event=ZoomEvent('smooth',1,1.8,5.8,6.5,1.18)
        left,right=(0,-200,540,960),(30,-100,540,960)
        shots=[(0,4,left,'face'),(4,8,right,'speaker')]
        parts=verified_shot_segments(event,shots)
        anchors=anchors_for([event],[parts],240,30)
        self.assertEqual(anchors[119],left)
        self.assertEqual(anchors[120],right)
        self.assertIsNone(verified_shot_segments(event,[(0,4,left,'face'),(4,8,None,None)]))
        self.assertEqual(profile_for(60).hold_min,3)
        self.assertEqual(profile_for(60).hold_max,5)
        self.assertEqual((profile_for(60).gap,profile_for(60).wide_max),(3,5))

    def test_jump_cut_framing_alternates_on_adjacent_cuts(self):
        base = jump_cut_baseline([(0, 60), (60, 120), (120, 130), (130, 200), (250, 300)], 300, 30, 1.15)
        self.assertEqual([round(base[f], 4) for f in (0, 60, 125, 140, 260)], [1.0, 1.09, 1.09, 1.0, 1.0])

    def test_planner_output_is_validated(self):
        raw = {'zooms': [{'id': 0, 'word': 'nahin', 'strength': 3, 'kind': 'emphasis'},
                         {'id': 0, 'word': 'dup', 'strength': 2, 'kind': 'emphasis'},
                         {'id': 7, 'word': 'x', 'strength': 2, 'kind': 'emphasis'},
                         {'id': 1, 'word': 'hazaar', 'strength': 9, 'kind': 'weird'}]}
        moments = validate(raw, {p.id: p for p in self.phrases})
        self.assertEqual([(m.phrase_id, m.strength, m.kind) for m in moments], [(0, 3, 'emphasis'), (1, 2, 'emphasis')])


class MotionTests(unittest.TestCase):
    def test_turned_away_speaker_requires_visible_stable_local_vision_evidence(self):
        from unittest.mock import Mock, patch
        from PIL import Image
        from hinglish_zoom.subjects import SubjectLocator
        model = Mock()
        model.look.return_value = {'framing':'unclear_or_ambiguous',
            'head_centres':[{'x':.5,'y':.6}]*3,'reason':'No clearly identifiable speaker'}
        pictures = [(t,Image.new('RGB',(10,10))) for t in (0,1,2)]
        with patch('hinglish_visuals.evaluator.VisionModel',return_value=model), patch('hinglish_zoom.subjects.read_frames',return_value=pictures):
            subject = SubjectLocator(Path('missing'))
            self.assertIsNone(subject.head_during('clip.mp4',0,3))
            model.look.return_value = {'framing':'one_clear_speaker',
                'head_centres':[{'x':.45,'y':.65}]*3,'reason':'The same visible speaker facing a laptop'}
            self.assertEqual(subject.head_during('clip.mp4',4,7),(.45,.65))
            model.look.return_value['head_centres'] = [{'x':.2,'y':.6},{'x':.5,'y':.6},{'x':.8,'y':.6}]
            self.assertIsNone(subject.head_during('clip.mp4',8,11))
            subject.close()

    def test_face_stays_at_original_position_and_edges_are_never_revealed(self):
        random.seed(1)
        for W, H in ((1080, 1920), (1920, 1080)):
            for _ in range(400):
                clip = TrackClip(None, 'c', 0, 1, 0, Fraction(30), 'x', 1.0, (0.0, 0.0), True)
                sw, sh = W, H
                dx, dy = random.uniform(-sw / 2, sw / 2), random.uniform(-sh / 2, sh / 2)
                z = random.uniform(1.0, 1.3)
                scale, (h, v) = motion_values(clip, z, (dx, dy, sw, sh), W, H)
                s, cx, cy = scale / 100, h * W, v * H
                # scaled source still covers the whole canvas
                self.assertLessEqual(cx - s * sw / 2, -W / 2 + 1e-6); self.assertGreaterEqual(cx + s * sw / 2, W / 2 - 1e-6)
                self.assertLessEqual(cy - s * sh / 2, -H / 2 + 1e-6); self.assertGreaterEqual(cy + s * sh / 2, H / 2 - 1e-6)
                # No pull toward another screen position: the source focal
                # point stays stationary at EVERY intermediate zoom scale.
                self.assertAlmostEqual(cx+s*dx,dx)
                self.assertAlmostEqual(cy+s*dy,dy)
            # no zoom = the original framing exactly
            self.assertEqual(motion_values(clip, 1.0, (200.0, -300.0, sw, sh), W, H), (100.0, (0.0, 0.0)))

    def test_repositioned_clip_keeps_face_fixed(self):
        clip = TrackClip(None, 'c', 0, 1, 0, Fraction(30), 'x', 1.0, (50.0, 0.0), True)
        scale, (h, v) = motion_values(clip, 1.2, (100.0, 0.0, 1080, 1920), 1080, 1920)
        self.assertAlmostEqual(h * 1080 + 1.2 * 100, 50 + 100)

    def test_existing_fit_scale_is_multiplied(self):
        clip = TrackClip(None, 'c', 0, 1, 0, Fraction(30), 'x', .5625, (0.0, 0.0), True)
        scale, center = motion_values(clip, 1.2, (0.0, 0.0), 1080, 1920)
        self.assertAlmostEqual(scale, 67.5)
        self.assertEqual(center, (0.0, 0.0))


class XmlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        d = Path(self.temp.name)
        a, b = media(d / 'a.mp4'), media(d / 'b.mp4')
        self.xml = d / 'EDIT.xml'
        export_xml(self.xml, [Cut(a.id, 0, 90, 0), Cut(b.id, 30, 120, 1)], {a.id: a, b.id: b})  # 0-90, 90-180

    def tearDown(self):
        self.temp.cleanup()

    def test_zoom_splits_video_keeps_audio_and_frames_continuous(self):
        seq = Sequence(self.xml)
        curve = np.ones(seq.frames)
        curve[40:50] = np.linspace(1.01, 1.1, 10); curve[50:70] = 1.1
        target = Path(self.temp.name) / 'ZOOM.xml'
        anchors = [None] * seq.frames
        for f in range(40, 70):
            anchors[f] = (0.0, -300.0)                                     # legacy 2-value offset: face fixed
        pieces = apply_curve(seq, curve, anchors, target)
        self.assertEqual(pieces, 10)          # 9 ramp frames + 1 hold piece (the ramp's last value equals the hold)
        root = ET.parse(target).getroot()
        self.assertTrue(root.findtext('sequence/name').endswith('_ZOOM'))
        video = root.findall('sequence/media/video/track')[0].findall('clipitem')
        spans = [(int(c.findtext('start')), int(c.findtext('end')), int(c.findtext('in')), int(c.findtext('out'))) for c in video]
        for (s1, e1, i1, o1), (s2, e2, i2, o2) in zip(spans, spans[1:]):
            self.assertEqual(e1, s2)
        self.assertEqual(spans[0][:3], (0, 40, 0))
        # in-points follow the timeline exactly inside the first clip
        self.assertTrue(all(i - s == 0 for s, e, i, o in spans[:-1]))
        self.assertEqual(spans[-1], (90, 180, 30, 120))                       # second clip untouched
        zoomed = video[10]
        self.assertEqual(zoomed.find('.//parameter[parameterid="scale"]/value').text, '110')
        self.assertAlmostEqual(float(zoomed.find('.//parameter[parameterid="center"]/value/vert').text), 30 / 1920, places=6)
        self.assertIsNone(video[1].find('link'))
        # audio is not split and no longer links to removed video ids
        for track in root.findall('sequence/media/audio/track'):
            self.assertEqual(len(track.findall('clipitem')), 2)
            for link in track.iter('linkclipref'):
                self.assertNotEqual(link.text, 'v-1')
        # only the first piece carries the full file definition
        full = [f for f in root.iter('file') if f.get('id') == 'file-1' and len(f)]
        self.assertEqual(len(full), 1)

    def test_upper_track_broll_blocks_but_caption_layer_does_not(self):
        tree = ET.parse(self.xml)
        video = tree.getroot().find('sequence/media/video')
        broll = ET.SubElement(video, 'track')
        for cid, s, e in (('broll-clip-1', 30, 75), ('caption-overlay-1', 0, 180)):
            item = ET.SubElement(broll, 'clipitem', id=cid)
            ET.SubElement(item, 'start').text = str(s); ET.SubElement(item, 'end').text = str(e)
        tree.write(self.xml)
        self.assertEqual(Sequence(self.xml).blocked_seconds(), [(1.0, 2.5)])


if __name__ == '__main__':
    unittest.main()
