"""Detector/planner component fixtures only: no video encoder, service or host."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
import wave

import numpy as np

from hinglish_beats.detect import analyze
from hinglish_cinematic.planner import assemble, best_window, boundaries, _content_fingerprint


SALIENT_SECONDS = [4, 9.5, 15, 20, 24.5, 30, 35, 39.5, 45]


def song_plan(fps=30, split=True):
    return {
        'path': 'synthetic-song.wav', 'fps': fps, 'duration': 50.,
        'source_in': 12.5, 'source_out': 62.5, 'timeline_start': 100., 'speed': 1.,
        'beats': [
            {'timeline_seconds': 100.+t, 'strength': .98 if t in SALIENT_SECONDS else .04}
            for t in np.arange(.5, 50, .5)
        ],
    }


def sources(count=50):
    return [
        {'path': f'synthetic/clip-{i:02}.mp4', 'name': f'clip-{i:02}',
         'source_id': f'clip-{i:02}',
         'content_sha256': hashlib.sha256(f'fixture-content-{i}'.encode()).hexdigest(),
         'fps': 30., 'duration': 20.,
         'samples': [
             {'time': float(t), 'quality': .45+i*.01 if 6 <= t < 15 else .06,
              'motion': .35 if 6 <= t < 15 else .05}
             for t in np.arange(0, 20, .25)
         ]}
        for i in range(count)
    ]


def options(**changes):
    return {'fps': 30, 'max_shots': 10, 'min_shot': 3, 'max_shot': 6,
            'allow_slow': False, 'allow_fast': False, **changes}


def salient_song():
    plan = song_plan()
    plan['beats'] = [b for b in plan['beats'] if b['strength'] > .9]
    return plan


def golden_plan():
    return assemble(song_plan(), sources(), options())


class RequestedCinematicPlannerTests(unittest.TestCase):
    def test_50_sources_choose_best_10_and_salient_nonuniform_real_cuts(self):
        music, pool = song_plan(), sources()
        before = copy.deepcopy((music, pool))
        result = assemble(music, pool, options())
        expected = [0]+[round(s*30) for s in SALIENT_SECONDS]+[1500]
        self.assertEqual(result['cuts'], expected)
        self.assertEqual(len(result['shots']), 10)
        self.assertEqual({s['name'] for s in result['shots']}, {f'clip-{i:02}' for i in range(40, 50)})
        self.assertGreater(len({s['duration_frames'] for s in result['shots']}), 1)
        self.assertEqual(sum(s['duration_frames'] for s in result['shots']), 1500)
        self.assertEqual(result['effects'], [])
        self.assertEqual((music, pool), before)

    def test_40_candidates_and_budget_10_stay_in_best_in_bounds_sections(self):
        result = assemble(song_plan(), sources(40), options())
        self.assertEqual(len(result['shots']), 10)
        self.assertEqual(len({s['source_id'] for s in result['shots']}), 10)
        self.assertEqual({s['name'] for s in result['shots']}, {f'clip-{i:02}' for i in range(30, 40)})
        for shot in result['shots']:
            self.assertGreaterEqual(shot['source_in'], 6)
            self.assertLessEqual(shot['source_out'], 15)
            self.assertEqual(shot['speed'], 1)
            self.assertAlmostEqual(shot['source_out']-shot['source_in'], shot['duration_frames']/30)
        self.assertEqual(result['shots'][0]['start_frame'], 0)
        self.assertEqual(result['shots'][-1]['end_frame'], 1500)
        for a, b in zip(result['shots'], result['shots'][1:]):
            self.assertEqual(a['end_frame'], b['start_frame'])

    def test_content_copies_and_shared_source_ids_do_not_fake_diversity(self):
        pool = sources()
        # Three different paths form one source group through provenance/content.
        pool[48]['content_sha256'] = pool[49]['content_sha256']
        pool[47]['source_id'] = pool[49]['source_id']
        result = assemble(salient_song(), pool, options())
        selected = result['shots']
        self.assertEqual(len(selected), 10)
        self.assertEqual(len({s['content_sha256'] for s in selected}), 10)
        self.assertEqual(len({s['source_id'] for s in selected}), 10)
        self.assertEqual(sum(s['name'] in {'clip-47', 'clip-48', 'clip-49'} for s in selected), 1)
        self.assertIn('clip-49', {s['name'] for s in selected})

    def test_duplicate_content_cannot_fill_the_missing_source_budget(self):
        pool = sources()
        for source in pool:
            source['content_sha256'] = pool[0]['content_sha256']
        with self.assertRaisesRegex(ValueError, 'beat|source|shot'):
            assemble(salient_song(), pool, options())

    def test_same_frame_preserves_strongest_attack_during_output_fps_conversion(self):
        plan = {'duration': 12., 'timeline_start': 0., 'beats': [
            {'timeline_seconds': 3., 'strength': .4},
            {'timeline_seconds': 4., 'strength': .95},
            {'timeline_seconds': 4.001, 'strength': .01},
            {'timeline_seconds': 7., 'strength': .4},
            {'timeline_seconds': 8., 'strength': .8},
        ]}
        self.assertEqual(boundaries(plan, 30, 3, 3, 5), [0, 120, 240, 360])

    def test_no_beat_and_infeasible_real_beats_stop_without_five_second_grid(self):
        plan = song_plan()
        plan['beats'] = []
        with self.assertRaisesRegex(ValueError, 'beat'):
            assemble(plan, sources(), options())
        plan['beats'] = [{'timeline_seconds': 125., 'strength': 1.}]
        with self.assertRaisesRegex(ValueError, 'beat|shot'):
            assemble(plan, sources(), options())

    def test_mean_window_quality_blocks_a_mostly_unusable_shot(self):
        pool = sources(1)
        for sample in pool[0]['samples']:
            sample['quality'] = .9 if sample['time'] == 10 else .01
        plan = {'path': 'synthetic.wav', 'source_in': 0., 'source_out': 5.,
                'duration': 5., 'fps': 30, 'speed': 1., 'timeline_start': 0.,
                'beats': [{'timeline_seconds': 2.5, 'strength': .8}]}
        with self.assertRaisesRegex(ValueError, 'usable|quality|Cannot fill'):
            assemble(plan, pool, options(max_shots=1))

    def test_music_ranges_are_contiguous_original_time_not_rearranged_shot_audio(self):
        result = assemble(salient_song(), sources(), options())
        music = result['music']
        self.assertTrue(music['continuous'])
        self.assertEqual(music['speed'], 1)
        self.assertEqual(music['source_in'], 12.5)
        self.assertEqual(music['source_out'], 62.5)
        self.assertEqual(len(music['ranges']), 10)
        previous_frame, previous_source = 0, 12.5
        for segment in music['ranges']:
            self.assertEqual(segment['start_frame'], previous_frame)
            self.assertAlmostEqual(segment['source_in'], previous_source)
            self.assertAlmostEqual(segment['source_out']-segment['source_in'],
                                   (segment['end_frame']-segment['start_frame'])/30)
            previous_frame, previous_source = segment['end_frame'], segment['source_out']
        self.assertEqual((previous_frame, previous_source), (1500, 62.5))

    def test_unsplit_music_is_one_contiguous_original_range(self):
        result = assemble(salient_song(), sources(), options(split_music=False))
        self.assertEqual(len(result['music']['ranges']), 1)
        self.assertEqual(result['music']['ranges'][0],
                         {'start_frame': 0, 'end_frame': 1500, 'source_in': 12.5, 'source_out': 62.5})

    def test_fractional_output_frame_never_requires_music_after_selected_out_point(self):
        music = salient_song()
        music['fps'] = 30000/1001
        result = assemble(music, sources(), options(fps=30000/1001))
        self.assertLessEqual(result['duration'], 50)
        self.assertLess(50-result['duration'], 1001/30000)
        self.assertLessEqual(result['music']['source_out'], 62.5)
        self.assertEqual(result['music']['ranges'][-1]['end_frame'], result['frames'])

    def test_source_trim_limit_stops_instead_of_freezing_a_short_input(self):
        source = sources(1)[0]
        source['duration'] = 2
        source['samples'] = [s for s in source['samples'] if s['time'] < 2]
        self.assertIsNone(best_window(source, 6, .4, False, False, 30))
        with self.assertRaisesRegex(ValueError, 'Cannot fill|beat|shot'):
            assemble(song_plan(), [source], options(max_shots=1))

    def test_selected_music_out_point_is_a_real_bound(self):
        music = song_plan()
        music['source_out'] = 60.
        with self.assertRaisesRegex(ValueError, 'out point'):
            assemble(music, sources(), options())

    def test_assembly_does_not_automatically_add_other_feature_effects(self):
        result = assemble(salient_song(), sources(), options(effects=['flash'], captions=True, broll=True))
        self.assertEqual(result['effects'], [])
        self.assertNotIn('captions', result)
        self.assertNotIn('broll', result)


class SourceByteIdentityTests(unittest.TestCase):
    def test_byte_copies_share_identity_and_originals_are_unchanged(self):
        original = b'component-fixture-only-not-video'*100000
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder)/'first.bin', Path(folder)/'renamed-copy.bin'
            first.write_bytes(original)
            second.write_bytes(original)
            self.assertEqual(_content_fingerprint(first), _content_fingerprint(second))
            self.assertEqual(_content_fingerprint(first), hashlib.sha256(original).hexdigest())
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual(second.read_bytes(), original)

    def test_cancelled_identity_read_stops_without_changing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'original.bin'
            source.write_bytes(b'unchanged')
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                _content_fingerprint(source, cancelled)
            self.assertEqual(source.read_bytes(), b'unchanged')


class RequestedBeatDetectorTests(unittest.TestCase):
    def test_irregular_pcm_attacks_and_salience_are_measured_without_extra_grid(self):
        rate, duration = 16000, 4.
        times = [.3, .87, 1.62, 2.08, 2.91, 3.54]
        amplitudes = [.25, .85, .3, .9, .25, .8]
        pcm = np.zeros(round(duration*rate), dtype=np.float32)
        for instant, amplitude in zip(times, amplitudes):
            index = round(instant*rate)
            pulse = amplitude*np.exp(-np.arange(480)/70)*np.cos(2*np.pi*400*np.arange(480)/rate)
            pcm[index:index+len(pulse)] = pulse
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'irregular.wav'
            with wave.open(str(path), 'wb') as file:
                file.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                file.writeframes((pcm*32767).astype('<i2').tobytes())
            result = analyze({'path': str(path), 'density': 'strong', 'fps': 60})
        self.assertEqual(len(result['beats']), len(times))
        for beat, expected in zip(result['beats'], times):
            self.assertLessEqual(abs(beat['timeline_seconds']-expected), 1/60)
        strengths = [b['strength'] for b in result['beats']]
        self.assertGreater(min(strengths[i] for i in (1, 3, 5)), max(strengths[i] for i in (0, 2, 4)))
        self.assertIn('attack', result['notice'].lower())

    def test_silence_reports_zero_markers_and_planner_refuses_an_invented_grid(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'silent.wav'
            with wave.open(str(path), 'wb') as file:
                file.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                file.writeframes(b'\x00\x00'*32000)
            result = analyze({'path': str(path), 'density': 'strong', 'fps': 30})
        self.assertEqual(result['beats'], [])
        with self.assertRaisesRegex(ValueError, 'beat'):
            assemble(result, sources(4), options())


class ComponentGoldenFixtureTests(unittest.TestCase):
    def test_saved_golden_plan_matches_the_same_synthetic_case(self):
        path = Path(__file__).parent/'fixtures/beat_cinematic_component/golden_50s_10shots.json'
        saved = json.loads(path.read_text())
        self.assertTrue(saved['synthetic_only'])
        self.assertEqual(saved['plan'], golden_plan())
