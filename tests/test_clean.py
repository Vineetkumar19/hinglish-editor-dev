import json
from pathlib import Path
import tempfile
import unittest
import wave
from fractions import Fraction
from unittest.mock import patch
import xml.etree.ElementTree as ET

from hinglish_clean.detection import CleanSettings, detect_blocks, plan_cuts, removed_ranges, verify_plan
from hinglish_clean.pipeline import clean_one, select_inputs
from hinglish_clean.render import render_mp4
from hinglish_cut.demo import create_demo_media
from hinglish_cut.media import probe, extract_audio
from hinglish_cut.model import Media, Cut


class CleanTests(unittest.TestCase):
    def media(self, rate='30', duration=10):
        return Media('one', 'unused', duration, rate, 64, 48, 2, 48000)

    def test_speech_kept_padding_and_silence_removed(self):
        m = self.media()
        speech = [(1, 2), (2.1, 3), (5, 6)]
        cuts = plan_cuts(m, speech, CleanSettings())
        verify_plan(m, cuts, speech)
        self.assertEqual(len(cuts), 2)
        self.assertLess(cuts[0].start_frame, 30)
        self.assertGreater(cuts[0].end_frame, 90)
        removed = removed_ranges(m, cuts)
        self.assertEqual(len(removed), 3)
        self.assertEqual(sum(c.duration for c in cuts) + sum(b - a for a, b in removed), 300)

    def test_quiet_short_utterance_not_filtered_by_edit_planner(self):
        m = self.media()
        cuts = plan_cuts(m, [(4, 4.06)], CleanSettings())
        verify_plan(m, cuts, [(4, 4.06)])
        self.assertTrue(cuts)

    def test_validation_rejects_removed_speech_and_frame_reuse(self):
        m = self.media()
        with self.assertRaises(ValueError):
            verify_plan(m, [Cut(m.id, 0, 30, 0)], [(0, 2)])
        with self.assertRaises(ValueError):
            verify_plan(m, [Cut(m.id, 0, 100, 0), Cut(m.id, 50, 150, 1)], [])

    def test_whole_speech_and_empty_speech(self):
        m = self.media()
        self.assertEqual(plan_cuts(m, [], CleanSettings()), [])
        cuts = plan_cuts(m, [(0, 10)], CleanSettings())
        self.assertEqual([(c.start_frame, c.end_frame) for c in cuts], [(0, 300)])

    def test_ntsc_outward_rounding(self):
        m = self.media('30000/1001', 300 / (30000 / 1001))
        cuts = plan_cuts(m, [(0.01, 2.399), (4, 7)], CleanSettings())
        verify_plan(m, cuts, [(0.01, 2.399), (4, 7)])

    def test_invalid_settings(self):
        for data in ({'threshold': float('nan')}, {'post_padding': -1}, {'block_seconds': 0}):
            with self.assertRaises(ValueError):
                CleanSettings(**data)

    def test_phase1_folders_are_separate_and_reject_mixed_formats(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'input' / 'videos').mkdir(parents=True)
            (root / 'input' / 'videos' / 'old.mp4').touch()
            with self.assertRaises(ValueError):
                select_inputs(root)
            (root / 'input' / 'phase1' / 'videos' / 'new.mp4').touch()
            paths, fmt = select_inputs(root)
            self.assertEqual(paths[0].name, 'new.mp4')
            self.assertIsNone(fmt)
            (root / 'input' / 'phase1' / 'instagram-vertical' / 'reel.mp4').touch()
            with self.assertRaises(ValueError):
                select_inputs(root)

    def test_block_overlap_and_resume_without_model(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            settings = CleanSettings(block_seconds=10)
            lengths = []
            def fake_read(path, a, b):
                lengths.append((a, b))
                return np.zeros(round((b - a) * 16000), dtype=np.float32)
            with patch('hinglish_clean.detection.read_audio', fake_read):
                regions = detect_blocks('unused', 25, Path(d), settings,
                                        lambda samples: [(0, len(samples) / 16000)], lambda x: None)
            self.assertEqual(regions, [(0, 25)])
            self.assertEqual(lengths, [(0, 12), (8, 22), (18, 25)])
            with patch('hinglish_clean.detection.SpeechDetector', side_effect=AssertionError('must reuse cache')):
                self.assertEqual(detect_blocks('unused', 25, Path(d), settings, progress=lambda x: None), regions)

    def test_render_keeps_frame_order_stereo_and_duration(self):
        import av
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            create_demo_media(p / 'raw.mp4', 3, 440)
            m = probe(p / 'raw.mp4')
            cuts = [Cut(m.id, 5, 20, 0), Cut(m.id, 35, 60, 1)]
            result = render_mp4(m, cuts, p / 'clean.mp4', canvas=(80, 80), progress=lambda x: None)
            out = probe(p / 'clean.mp4')
            self.assertEqual((out.width, out.height, out.channels), (80, 80, 2))
            self.assertAlmostEqual(out.duration, 40 / 25)
            self.assertEqual(result['audio_samples'], 76800)
            with av.open(str(p / 'clean.mp4')) as f:
                times = [float(frame.pts * frame.time_base) for frame in f.decode(video=0)]
            self.assertEqual(len(times), 40)
            self.assertAlmostEqual(times[0], 0)
            with av.open(str(p / 'clean.mp4')) as f:
                audio = f.streams.audio[0]
                self.assertAlmostEqual(float(audio.duration * audio.time_base), 1.6, places=2)

    def test_end_to_end_without_script_and_preserve_source_after_input_deleted(self):
        from urllib.parse import unquote, urlparse
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            source = p / 'raw & file.mp4'
            create_demo_media(source, 3)
            result = clean_one(source, p, p / 'output', CleanSettings(),
                               detector=lambda samples: [(.5, 1), (2, 2.4)], progress=lambda x: None)
            self.assertEqual(result['status'], 'READY_FOR_REVIEW')
            self.assertTrue(result['mp4_created'])
            self.assertGreater(result['removed_seconds'], .7)
            source.unlink()
            self.assertTrue((p / 'output' / 'media' / 'source.mp4').exists())
            tree = ET.parse(p / 'output' / 'timeline.xml')
            url = tree.find('.//pathurl').text
            self.assertIn('/output/media/source.mp4', url)
            self.assertEqual(int(tree.find('.//sequence/duration').text),
                             result['render']['video_frames'])
            self.assertNotIn('script 1', (p / 'output' / 'timeline.xml').read_text())

    def test_no_speech_does_not_publish_blank_video(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            create_demo_media(p / 'raw.mp4', 2)
            result = clean_one(p / 'raw.mp4', p, p / 'output', CleanSettings(),
                               detector=lambda samples: [], progress=lambda x: None)
            self.assertEqual(result['status'], 'NO_SPEECH_DETECTED')
            self.assertFalse((p / 'output' / 'timeline.xml').exists())
            self.assertFalse((p / 'output' / 'cleaned.mp4').exists())
            self.assertTrue((p / 'output' / 'report.html').exists())

    def test_ntsc_many_cuts_do_not_accumulate_audio_drift(self):
        import av
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            fps = Fraction(30000, 1001)
            with av.open(str(p / 'ntsc.mp4'), 'w') as out:
                video = out.add_stream('libx264', rate=fps)
                video.width, video.height, video.pix_fmt = 64, 48, 'yuv420p'
                audio = out.add_stream('aac', rate=48000)
                audio.layout = 'mono'
                pos = 0
                for i in range(300):
                    f = av.VideoFrame.from_ndarray(np.full((48, 64, 3), i % 200, dtype=np.uint8), format='rgb24')
                    f.pts, f.time_base = i, 1 / fps
                    for packet in video.encode(f): out.mux(packet)
                    end = round(Fraction((i + 1) * 48000) / fps)
                    samples = np.sin(np.arange(pos, end) * 2 * np.pi * 440 / 48000).astype(np.float32)[None, :] * .1
                    af = av.AudioFrame.from_ndarray(samples, format='fltp', layout='mono')
                    af.sample_rate, af.pts, af.time_base = 48000, pos, Fraction(1, 48000)
                    for packet in audio.encode(af): out.mux(packet)
                    pos = end
                for stream in (video, audio):
                    for packet in stream.encode(): out.mux(packet)
            m = probe(p / 'ntsc.mp4')
            cuts = [Cut(m.id, start, start + 3, i) for i, start in enumerate(range(0, 296, 5))]
            result = render_mp4(m, cuts, p / 'out.mp4', progress=lambda x: None)
            total_frames = sum(c.duration for c in cuts)
            self.assertEqual(result['video_frames'], total_frames)
            self.assertEqual(result['audio_samples'], round(Fraction(total_frames * 48000) / fps))
            out_media = probe(p / 'out.mp4')
            self.assertEqual(out_media.rate, fps)
            self.assertAlmostEqual(out_media.duration, total_frames / float(fps))


if __name__ == '__main__':
    unittest.main()
