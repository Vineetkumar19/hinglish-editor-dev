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
        events = build_events(moments, self.phrases, self.words, settings, profile_for(60), 60)
        self.assertEqual([e.kind for e in events], ['smooth', 'impact'])
        self.assertAlmostEqual(events[0].word, 5.9)
        level = 1 + .12 * .85                          # strength 2 = 85% of the chosen zoom
        self.assertAlmostEqual(events[0].start, 5.9 - profile_for(60).ramp_in * (.8 + (level - 1) * 2))
        self.assertAlmostEqual(events[1].level, 1.12)

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

    def test_smooth_default_never_jumps(self):
        moments = [ZoomMoment(0, 'nahin', 3, 'reveal'), ZoomMoment(1, 'hazaar', 3, 'emphasis')]
        events = build_events(moments, self.phrases, self.words, ZoomSettings(), profile_for(60), 60)
        self.assertEqual(ZoomSettings().style, 'smooth')
        self.assertTrue(all(e.kind in ('smooth', 'push') for e in events))

    def test_zooms_are_used_sparingly(self):
        self.assertGreaterEqual(profile_for(45).spacing, 6)      # at most ~6 zooms in a 45 s reel, not 10+
        self.assertGreaterEqual(profile_for(1500).spacing, 20)

    def test_zoomed_section_is_split_at_shot_changes_like_a_two_camera_edit(self):
        from hinglish_zoom.events import fit_to_shots
        shots = [(0, 8.3), (8.3, 12.2), (12.2, 20)]
        crossing = ZoomEvent('smooth', 9.2, 10.0, 14.0, 14.7, 1.12)          # point continues after a cut
        first, second = fit_to_shots([crossing], shots)
        self.assertEqual((first.start, first.word, first.hold_end, first.end), (9.2, 10.0, 12.2, 12.2))
        self.assertEqual((second.start, second.word, second.hold_end, second.end), (12.2, 12.2, 14.0, 14.7))
        just_after_cut = ZoomEvent('smooth', 7.9, 8.4, 10, 10.7, 1.12)        # no room to ease in after the cut
        piece, = fit_to_shots([just_after_cut], shots)
        self.assertEqual((piece.start, piece.word), (8.3, 8.3))              # the new shot simply starts zoomed
        too_late = ZoomEvent('smooth', 11.2, 12.0, 13, 13.7, 1.12)            # only 0.2 s before the cut
        piece, = fit_to_shots([too_late], shots)
        self.assertEqual((piece.start, piece.hold_end), (12.2, 13))          # zoom begins with the next shot

    def test_zoom_stays_in_for_the_whole_point(self):
        from hinglish_zoom.events import make_event
        words = [Word('Flat', 30.0, 30.3), Word('milna', 30.35, 30.7), Word('impossible', 30.8, 31.5)]
        start, end = Phrase(10, 30.0, 31.6, 'Flat milna impossible'), Phrase(12, 33.0, 35.4, 'PG bhi nahin')
        e = make_event(ZoomMoment(10, 'impossible', 3, until_id=12), start, words[2], 'smooth', 1.12,
                       profile_for(45), until=end)
        self.assertAlmostEqual(e.word, 30.8)
        self.assertAlmostEqual(e.hold_end, 35.55)                           # through the end of the point
        self.assertGreater(e.end, e.hold_end)                               # then eases back to wide

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
        self.assertGreater(profile_for(60, 'low').spacing, profile_for(60, 'high').spacing)

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
    def test_face_moves_toward_ideal_spot_and_edges_are_never_revealed(self):
        from hinglish_zoom.xml_apply import FACE_TARGET
        random.seed(1)
        for W, H in ((1080, 1920), (1920, 1080)):
            target = (FACE_TARGET[0] * W, FACE_TARGET[1] * H)
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
                # the face ends at least as close to the ideal spot as "keep the face fixed" would leave it
                fixed_x, fixed_y = dx, dy
                self.assertLessEqual(abs(cx + s * dx - target[0]), abs(fixed_x - target[0]) + 1e-6)
                self.assertLessEqual(abs(cy + s * dy - target[1]), abs(fixed_y - target[1]) + 1e-6)
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
