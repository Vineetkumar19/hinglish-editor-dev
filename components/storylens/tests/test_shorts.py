import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from hinglish_broll.phrases import Phrase
from hinglish_cut.model import Word
from hinglish_shorts.find import Short, find_shorts, make_lines, plan_repair, plan_rules, select, snap
from hinglish_shorts.render import frame_plan, render_short, template_overlay
from hinglish_shorts.settings import ShortsSettings, parse_time
from hinglish_shorts.source import open_video


def speech(sentences, gap=.6, word=.35):
    """Timed words for sentences (each ends with a full stop), `gap` seconds of pause between sentences."""
    words, t = [], 0.0
    for sentence in sentences:
        tokens = sentence.split()
        for n, token in enumerate(tokens):
            text = token + ('.' if n == len(tokens) - 1 else '')
            words.append(Word(text, round(t, 3), round(t + word, 3)))
            t += word + .05
        t += gap
    return words


def make_video(path, seconds=8, size=(640, 360), fps=30):
    with av.open(str(path), 'w') as out:
        v = out.add_stream('libx264', rate=fps)
        v.width, v.height, v.pix_fmt = size[0], size[1], 'yuv420p'
        a = out.add_stream('aac', rate=48000)
        a.layout = 'stereo'
        for i in range(seconds * fps):
            img = np.zeros((size[1], size[0], 3), np.uint8)
            img[:, :, 0] = (i * 4) % 255
            img[size[1] // 3:size[1] // 2, size[0] // 3:size[0] // 2] = 255
            frame = av.VideoFrame.from_ndarray(img, format='rgb24')
            frame.pts = i
            for p in v.encode(frame):
                out.mux(p)
        t = np.arange(seconds * 48000) / 48000
        tone = (.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        for n in range(0, len(tone), 1024):
            part = np.stack([tone[n:n + 1024]] * 2)
            frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(part), format='fltp', layout='stereo')
            frame.sample_rate, frame.pts = 48000, n
            for p in a.encode(frame):
                out.mux(p)
        for p in v.encode():
            out.mux(p)
        for p in a.encode():
            out.mux(p)


class RuleTests(unittest.TestCase):
    def test_duration_cap_trims_only_padding_and_never_spoken_words(self):
        from hinglish_shorts.find import cap_padding
        words=[Word('hook',.1,5),Word('payoff',25,49.9)]
        pieces=cap_padding(words,[(0,50.3)],50)
        self.assertAlmostEqual(sum(e-s for s,e in pieces),50)
        self.assertLessEqual(pieces[0][0],words[0].start)
        self.assertGreaterEqual(pieces[0][1],words[-1].end)
        with self.assertRaisesRegex(ValueError,'spoken moment exceeds'):
            cap_padding([Word('complete',0,51)],[(0,51.3)],50)

    def test_missing_model_answer_is_not_an_empty_selection(self):
        checker=plan_rules([],[],ShortsSettings())
        self.assertTrue(any(p.hard for p in checker({})))
        self.assertEqual(checker({'shorts':[]}),[])

    def setUp(self):
        self.words = speech([f'line number {n} says something big about the team' for n in range(40)])
        self.lines = make_lines(self.words)
        self.settings = ShortsSettings(min_length=10, max_length=20)

    def test_lines_are_sentences_with_ids(self):
        self.assertEqual(len(self.lines), 40)
        self.assertEqual([l.id for l in self.lines[:3]], [0, 1, 2])

    def test_rules_catch_connector_start_length_and_call_to_action(self):
        words = speech(['aur phir unhone kaha yeh', 'subscribe karo channel ko abhi'] + ['normal line here'] * 30)
        lines = make_lines(words)
        check = plan_rules(lines, words, self.settings)
        problems = check({'shorts': [{'title': 'A real good title', 'pieces': [[0, 1]], 'why': '', 'score': 7}]})
        rules = {p.rule for p in problems if p.hard}
        self.assertIn('shorts.hook_start', rules)
        self.assertIn('shorts.no_cta', rules)
        self.assertIn('shorts.length', rules)       # two lines are far below 10 s

    def test_rules_reject_bad_ids_overlapping_pieces_and_generic_titles(self):
        check = plan_rules(self.lines[:10], self.words, self.settings)
        bad_ids = check({'shorts': [{'title': 'Good title here', 'pieces': [[0, 30]], 'score': 5}]})
        self.assertEqual(bad_ids[0].rule, 'shorts.ids')
        overlap = check({'shorts': [{'title': 'Good title here', 'pieces': [[0, 3], [2, 5]], 'score': 5}]})
        self.assertIn('shorts.order', {p.rule for p in overlap})
        generic = check({'shorts': [{'title': 'Highlight', 'pieces': [[0, 4]], 'score': 5}]})
        self.assertIn('shorts.title', {p.rule for p in generic})

    def test_repair_trims_too_long_extends_too_short_and_drops_broken(self):
        part = self.lines[:30]
        repair = plan_repair(part, self.words, self.settings)
        check = plan_rules(part, self.words, self.settings)
        fixed, notes = repair({'shorts': [
            {'title': 'Way too long short', 'pieces': [[0, 20]], 'score': 6},
            {'title': 'Way too short one', 'pieces': [[22, 22]], 'score': 6},
            {'title': 'Broken ids short', 'pieces': [[5, 99]], 'score': 6}]})
        self.assertEqual(len(fixed['shorts']), 2)
        self.assertFalse([p for p in check(fixed) if p.hard])
        self.assertTrue(any('dropped' in n for n in notes))

    def test_repair_skips_a_connector_start(self):
        words = speech(['toh yeh hua'] + [f'story line {n} with enough words in it' for n in range(20)])
        lines = make_lines(words)
        repair = plan_repair(lines, words, self.settings)
        fixed, _ = repair({'shorts': [{'title': 'The story line starts', 'pieces': [[0, 6]], 'score': 8}]})
        self.assertEqual(fixed['shorts'][0]['pieces'][0][0], 1)


class TimingTests(unittest.TestCase):
    def test_padding_stays_inside_source_without_trimming_selected_speech(self):
        duration=830.4333333333333
        words=[Word('final',825,825.3),Word('spoken',829.996,830.416)]
        line=Phrase(0,825,830.416,'final spoken')
        start,end=snap(words,line,line,source_duration=duration)
        self.assertEqual(end,duration)
        self.assertGreaterEqual(end,words[-1].end)
        self.assertLessEqual(start,words[0].start)
        with self.assertRaises(ValueError):
            snap(words,line,line,source_duration=830)

    def test_snap_cuts_between_words_never_inside(self):
        words = [Word('a', 1.0, 1.4), Word('b.', 1.45, 1.9), Word('c', 2.5, 2.8), Word('d.', 2.85, 3.3), Word('e', 3.35, 3.6)]
        start, end = snap(words, Phrase(0, 2.5, 3.3, 'c d.'), Phrase(0, 2.5, 3.3, 'c d.'))
        self.assertGreaterEqual(start, 1.9)
        self.assertLessEqual(start, 2.5)
        self.assertGreaterEqual(end, 3.3)
        self.assertLessEqual(end, 3.35)              # stops before the next word starts

    def test_select_keeps_best_without_overlap_in_video_order(self):
        a = Short('A title here', [(10, 40)], [(0, 1)], score=9)
        b = Short('B title here', [(15, 45)], [(0, 1)], score=7)       # same moment as A
        c = Short('C title here', [(100, 130)], [(0, 1)], score=8)
        chosen = select([a, b, c], 5)
        self.assertEqual([s.title for s in chosen], ['A title here', 'C title here'])
        self.assertEqual(len(select([a, b, c], 1)), 1)

    def test_frame_plan_and_times(self):
        self.assertEqual(frame_plan([(1.0, 2.0), (3.5, 4.0)], Fraction(30)), [(30, 30), (105, 15)])
        self.assertEqual(parse_time('1:02:03'), 3723)
        self.assertEqual(parse_time('4:05'), 245)
        self.assertIsNone(parse_time(''))

    def test_settings_targets(self):
        s = ShortsSettings()
        self.assertEqual(s.target(15 * 60), 8)
        self.assertEqual(ShortsSettings(count='3').target(15 * 60), 3)
        self.assertEqual(ShortsSettings(count='high', min_length=30, max_length=60).target(90), 1)
        with self.assertRaises(ValueError):
            ShortsSettings(min_length=60, max_length=30)


class FakeBrain:
    name = 'fake'

    def __init__(self, pick):
        self.pick = pick

    def json(self, system, data, schema, max_tokens=0, think=False):
        if 'main_points' in json.dumps(schema):
            return {'topic': 'Team journey', 'audience': 'fans', 'main_points': ['start', 'titles']}
        return self.pick(data)


class FindTests(unittest.TestCase):
    def test_final_spoken_moment_survives_campaign_bounds_validation(self):
        from hinglish_publish.campaign import valid_picks
        words=speech(['opening moment explains the team journey',
                      'closing moment delivers the final result and the winning team celebrates'])
        duration=words[-1].end+.017
        settings=ShortsSettings(count='1',min_length=5,max_length=15,pieces=1)
        def pick(data):
            import re
            ids=[int(i) for i in re.findall(r'^\[(\d+)\]',data['transcript'],re.M)]
            return {'shorts':[{'title':'The final winning moment','why':'A complete result',
                              'pieces':[[ids[0],ids[-1]]],'score':9}]}
        shorts,_,_=find_shorts(FakeBrain(pick),words,settings,lambda _:None,
                               source_duration=duration,max_overlap=0)
        self.assertEqual(len(shorts),1)
        self.assertEqual(shorts[0].pieces[-1][1],duration)
        self.assertGreaterEqual(shorts[0].pieces[-1][1],words[-1].end)
        self.assertEqual(len(valid_picks([s.to_dict() for s in shorts],duration)),1)

    def test_unavailable_speech_is_not_offered_to_the_model(self):
        words=speech(['available complete moment has a hook and a payoff',
                      'unavailable secret words go beyond the end of this source'])
        first_end=make_lines(words)[0].end
        seen=[]
        settings=ShortsSettings(count='1',min_length=5,max_length=15,pieces=1)
        def pick(data):
            seen.append(data['transcript'])
            return {'shorts':[]}
        find_shorts(FakeBrain(pick),words,settings,lambda _:None,source_duration=first_end)
        self.assertTrue(seen)
        self.assertTrue(all('unavailable secret' not in text for text in seen))

    def test_find_uses_rules_and_keeps_non_overlapping_best(self):
        words = speech([f'big moment {n} changed the whole team forever' for n in range(60)])
        settings = ShortsSettings(count='2', min_length=10, max_length=25, pieces=2)

        def pick(data):
            import re
            ids = [int(i) for i in re.findall(r'^\[(\d+)\]', data['transcript'], re.M)]
            return {'shorts': [
                {'why': 'hook', 'title': 'The moment that changed all', 'pieces': [[ids[0], ids[4]]], 'score': 9},
                {'why': 'same moment again', 'title': 'Same moment other title', 'pieces': [[ids[1], ids[5]]], 'score': 6},
                {'why': 'later', 'title': 'Second big turning point', 'pieces': [[ids[10], ids[12]], [ids[14], ids[15]]],
                 'score': 8}]}
        shorts, summary, lines = find_shorts(FakeBrain(pick), words, settings, progress=lambda m: None)
        self.assertEqual(len(shorts), 2)
        self.assertEqual(summary['topic'], 'Team journey')
        self.assertTrue(all(10 - 1.6 <= s.duration <= 25 + 1.6 for s in shorts))
        self.assertTrue(all(s.pieces == sorted(s.pieces) for s in shorts))


class RenderTests(unittest.TestCase):
    def test_template_and_face_shorts_render_with_sound_and_editable_sequence(self):
        from hinglish_eval.specs import check_xml
        from hinglish_broll.timeline import parse_xmeml
        from hinglish_shorts.xml import export_short_xml
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_video(tmp / 'long.mp4', seconds=8)
            video = open_video(tmp / 'long.mp4')
            self.assertEqual(video.short_fps, 30)
            pieces = [(1.0, 3.0), (5.0, 6.5)]
            overlay = template_overlay('Test title here', '@me', 'WATCH FULL VIDEO ON', video.width, video.height)
            facts = render_short(video, pieces, 'template', tmp / 'short.mp4', tmp / 'assets', 1, overlay,
                                 progress=lambda m: None)
            with av.open(str(tmp / 'short.mp4')) as c:
                v = c.streams.video[0]
                self.assertEqual((v.codec_context.width, v.codec_context.height), (1080, 1920))
                self.assertTrue(c.streams.audio)
                self.assertAlmostEqual(float(c.duration) / av.time_base, 3.5, delta=.15)
            self.assertTrue(Path(facts['layers']['overlay']).is_file())
            self.assertTrue(Path(facts['layers']['background']).is_file())
            xml = export_short_xml(tmp / 'SHORT_01.xml', 'Test (short 1)', video, facts['frames'], 'template',
                                   facts['layers'])
            self.assertTrue(all(c.passed for c in check_xml(xml)))
            seq = parse_xmeml(xml)
            self.assertEqual((seq.width, seq.height), (1080, 1920))
            source = [c for c in seq.clips if Path(c.path).name == 'long.mp4']
            self.assertEqual([(round(c.source_in, 2), round(c.source_out, 2)) for c in source], [(1.0, 3.0), (5.0, 6.5)])
            face = render_short(video, pieces, 'face', tmp / 'face.mp4', tmp / 'assets', 2, progress=lambda m: None)
            self.assertNotIn('background', face['layers'])


if __name__ == '__main__':
    unittest.main()
