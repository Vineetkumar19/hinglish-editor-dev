import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock

import av
import numpy as np

from hinglish_broll.conform import crop_box, make_clip
from hinglish_broll.phrases import Phrase
from hinglish_broll.placement import Moment, Slot
from hinglish_broll.planner import validate_moments
from hinglish_broll.ranker import choose
from hinglish_broll.report import write_report
from hinglish_broll.stock import Candidate, PexelsClient, PixabayClient, pick_file


def fake_video(path, seconds=3, fps=25, width=320, height=180):
    with av.open(str(path), 'w') as out:
        stream = out.add_stream('libx264', rate=fps)
        stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
        for i in range(int(seconds * fps)):
            pixels = np.zeros((height, width, 3), np.uint8)
            pixels[:, :, 0] = (i * 7) % 255
            pixels[:, width // 2:, 1] = 200
            frame = av.VideoFrame.from_ndarray(pixels, format='rgb24'); frame.pts = i
            for packet in stream.encode(frame): out.mux(packet)
        for packet in stream.encode(): out.mux(packet)


def response(data, status=200):
    r = MagicMock(); r.status_code = status; r.json.return_value = data; r.headers = {}
    r.raise_for_status = MagicMock()
    return r


class PlannerValidationTests(unittest.TestCase):
    def test_unknown_duplicate_and_empty_moments_are_dropped(self):
        raw = {'moments': [
            {'id': 1, 'visual': 'Meenakshi temple towers', 'queries': ['meenakshi temple', 'temple "india"'], 'priority': 3},
            {'id': 1, 'visual': 'again', 'queries': ['x y'], 'priority': 2},
            {'id': 99, 'visual': 'not in window', 'queries': ['q q'], 'priority': 2},
            {'id': 2, 'visual': 'चाय', 'queries': ['चाय'], 'priority': 2},
            {'id': 3, 'visual': 'rupee notes counting', 'queries': ['counting money'], 'priority': 7}]}
        moments = validate_moments(raw, {1, 2, 3})
        self.assertEqual([m.phrase_id for m in moments], [1, 3])
        self.assertEqual(moments[0].queries, ['meenakshi temple', 'temple india'])
        self.assertEqual(moments[1].priority, 2)


class StockTests(unittest.TestCase):
    def test_pick_file_prefers_smallest_that_fills_canvas(self):
        files = [(3840, 2160, '4k'), (1920, 1080, 'hd'), (1280, 720, 'sd')]
        self.assertEqual(pick_file(files, 1920, 1080)[2], 'hd')
        self.assertEqual(pick_file(files, 1080, 1920)[2], '4k')      # 9:16 crop needs 1920 height
        self.assertEqual(pick_file([(640, 360, 'small')], 1920, 1080)[2], 'small')

    def test_pexels_results_are_parsed_and_cached(self):
        data = {'videos': [{'id': 7, 'width': 1080, 'height': 1920, 'duration': 12, 'url': 'page', 'image': 'thumb.jpg',
                            'user': {'name': 'Asha'}, 'video_files': [
                                {'file_type': 'video/mp4', 'width': 1080, 'height': 1920, 'link': 'hd.mp4'},
                                {'file_type': 'video/mp4', 'width': 540, 'height': 960, 'link': 'sd.mp4'}]},
                           {'id': 8, 'width': 1920, 'height': 1080, 'duration': 9, 'video_files': []}]}
        with tempfile.TemporaryDirectory() as temp:
            session = MagicMock(); session.get.return_value = response(data)
            client = PexelsClient('KEY', temp, session)
            found = client.search('temple india', 'portrait', 1080, 1920)
            again = client.search('temple india', 'portrait', 1080, 1920)
            self.assertEqual(session.get.call_count, 1)
            self.assertEqual([(c.id, c.download_url, c.author) for c in found], [('pexels:7', 'hd.mp4', 'Asha')])
            self.assertEqual(again[0].id, 'pexels:7')
            self.assertEqual(session.get.call_args.kwargs['headers'], {'Authorization': 'KEY'})

    def test_rejected_key_gives_a_clear_message(self):
        with tempfile.TemporaryDirectory() as temp:
            session = MagicMock(); session.get.return_value = response({}, 401)
            with self.assertRaisesRegex(PermissionError, 'Settings'):
                PixabayClient('BAD', temp, session).search('x', 'landscape', 1920, 1080)

    def test_pixabay_filters_orientation_itself(self):
        data = {'hits': [{'id': 1, 'duration': 10, 'tags': 'dosa, food', 'pageURL': 'p', 'user': 'u',
                          'videos': {'large': {'url': 'l.mp4', 'width': 1920, 'height': 1080, 'thumbnail': 't1'},
                                     'medium': {'url': 'm.mp4', 'width': 1280, 'height': 720, 'thumbnail': 't2'}}},
                         {'id': 2, 'duration': 10, 'videos': {'large': {'url': 'v.mp4', 'width': 1080, 'height': 1920}}}]}
        with tempfile.TemporaryDirectory() as temp:
            session = MagicMock(); session.get.return_value = response(data)
            found = PixabayClient('K', temp, session).search('dosa', 'landscape', 1920, 1080)
            self.assertEqual([(c.id, c.download_url, c.thumb) for c in found], [('pixabay:1', 'l.mp4', 't2')])


class RankerTests(unittest.TestCase):
    def slot(self, start, priority=2, length=2.0):
        return Slot(Moment(0, 'temple', ['temple'], priority), start, start + length, 'text')

    def cand(self, cid, score, source='pexels', duration=10, width=1080, height=1920):
        return Candidate(source, cid, cid, duration, width, height, score=score, path='p' if source == 'library' else '')

    def test_best_clip_is_used_once_and_weak_matches_are_skipped(self):
        a, b = self.slot(3, 3), self.slot(9, 2)
        shared = self.cand('pexels:1', .31)
        picks = choose([(a, [shared, self.cand('pexels:2', .25)]),
                        (b, [shared, self.cand('pexels:3', .12)])], 'portrait', .22)
        self.assertEqual(picks[0][0].id, 'pexels:1')
        self.assertIsNone(picks[1][0])              # its only good clip was already used

    def test_library_bonus_and_orientation_penalty(self):
        s = self.slot(3)
        own = self.cand('library:x', .29, 'library')
        wide = self.cand('pexels:w', .31, width=1920, height=1080)
        picks = choose([(s, [wide, own])], 'portrait', .2)
        self.assertEqual(picks[0][0].id, 'library:x')
        self.assertEqual(picks[0][1][0].id, 'pexels:w')

    def test_too_short_clips_are_not_used(self):
        picks = choose([(self.slot(3, length=5), [self.cand('pexels:s', .4, duration=3)])], 'portrait', .2)
        self.assertIsNone(picks[0][0])


class ConformTests(unittest.TestCase):
    def test_crop_fills_vertical_canvas_from_landscape(self):
        self.assertEqual(crop_box(1920, 1080, 1080, 1920), (656, 0, 608, 1080))
        self.assertEqual(crop_box(1080, 1920, 1080, 1920), (0, 0, 1080, 1920))

    def test_clip_has_exact_size_rate_frames_and_no_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 'stock.mp4', Path(temp) / 'broll.mp4'
            fake_video(source, seconds=3, fps=25)
            make_clip(source, 0.5, 1.5, 108, 192, Fraction(30000, 1001), target)
            with av.open(str(target)) as clip:
                v = clip.streams.video[0]
                frames = sum(1 for _ in clip.decode(v))
                self.assertEqual((v.width, v.height), (108, 192))
                self.assertEqual(v.average_rate, Fraction(30000, 1001))
                self.assertEqual(len(clip.streams.audio), 0)
            self.assertEqual(frames, round(1.5 * 30000 / 1001))
            self.assertFalse(any(p.name.endswith('.partial.mp4') for p in Path(temp).iterdir()))

    def test_short_source_holds_last_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 's.mp4', Path(temp) / 'b.mp4'
            fake_video(source, seconds=1, fps=25)
            make_clip(source, 0, 2, 64, 64, 30, target)
            with av.open(str(target)) as clip:
                self.assertEqual(sum(1 for _ in clip.decode(video=0)), 60)


class ReportTests(unittest.TestCase):
    def test_report_lists_moments_alternatives_and_credits_safely(self):
        with tempfile.TemporaryDirectory() as temp:
            chosen = {'id': 'pexels:1', 'source': 'pexels', 'title': 'temple', 'score': .31,
                      'report_thumb': 'thumbs/pexels-1.jpg', 'author': 'Asha'}
            project = {'timeline': {'name': 'Madurai <vlog>', 'width': 1080, 'height': 1920},
                       'summary': {'topic': 'Madurai trip'}, 'profile': 'short', 'density': 'medium',
                       'slots': [{'index': 0, 'start': 2.5, 'end': 5, 'text': 'Meenakshi temple famous hai',
                                  'visual': 'temple towers', 'queries': ['meenakshi temple'], 'chosen': chosen,
                                  'clip': 'media/broll-01.mp4',
                                  'alternatives': [chosen, dict(chosen, id='pixabay:2', source='pixabay', author='')]},
                                 {'index': 1, 'start': 8, 'end': 10, 'text': '</script>', 'visual': 'x',
                                  'queries': ['x'], 'chosen': None, 'clip': None, 'alternatives': []}]}
            page = Path(temp) / 'report.html'
            write_report(page, project)
            text = page.read_text(encoding='utf-8')
            self.assertIn('Meenakshi temple famous hai', text)
            self.assertIn('data-id="pixabay:2"', text)
            self.assertIn('Asha (Pexels)', text)
            self.assertIn('Madurai &lt;vlog&gt;', text)
            self.assertNotIn('</script>"', text)
            self.assertIn('1 of 2 moments have B-roll', text)


if __name__ == '__main__':
    unittest.main()
