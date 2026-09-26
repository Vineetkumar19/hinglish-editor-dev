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


class QuoteTests(unittest.TestCase):
    def test_quote_moves_a_moment_to_the_line_it_really_describes(self):
        # Real case: the model gave the "school geography" line's id for an idea about the company line.
        phrases = [Phrase(4, 9.5, 11.7, 'aur tamilnaadu mein kahaan? Madhu rahi.'),
                   Phrase(5, 13.5, 15.7, 'Jab tumne apne school ke geography mein padha'),
                   Phrase(6, 16.3, 18.0, 'Mere company ne mujhe yahin fenk diya hai')]
        raw = {'moments': [
            {'id': 5, 'quote': 'company ne mujhe', 'visual': 'office building', 'queries': ['office'], 'priority': 2},
            {'id': 4, 'quote': 'tamilnaadu mein kahaan', 'visual': 'india map', 'queries': ['india map'], 'priority': 3},
            {'id': 5, 'quote': 'something never said', 'visual': 'x y', 'queries': ['x y'], 'priority': 2}]}
        moments = validate_moments(raw, {4, 5, 6}, phrases)
        self.assertEqual([(m.phrase_id, m.visual) for m in moments], [(6, 'office building'), (4, 'india map')])


class StockTests(unittest.TestCase):
    def test_pick_file_prefers_smallest_that_fills_canvas(self):
        files = [(3840, 2160, '4k'), (1920, 1080, 'hd'), (1280, 720, 'sd')]
        self.assertEqual(pick_file(files, 1920, 1080)[2], 'hd')
        self.assertEqual(pick_file(files, 1080, 1920)[2], '4k')      # 9:16 crop needs 1920 height
        self.assertEqual(pick_file([(640, 360, 'small')], 1920, 1080)[2], 'small')

    def test_cached_names_are_flat_and_unique_for_library_paths(self):
        from hinglish_broll.stock import cached_name
        a = Candidate('library', r'library:e:\madurai series\clip one.mp4@12.0', 't', 5, 1080, 1920)
        b = Candidate('library', r'library:e:\madurai series\clip one.mp4@30.0', 't', 5, 1080, 1920)
        name = cached_name(a, 'thumb')
        self.assertTrue(name.endswith('.jpg'))
        self.assertNotRegex(name, r'[\\/:]')
        self.assertNotEqual(name, cached_name(b, 'thumb'))
        self.assertEqual(cached_name(Candidate('pexels', 'pexels:7', 't', 5, 1080, 1920)), 'pexels-7-1080x1920.mp4')

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
            with self.assertRaisesRegex(PermissionError, 'B-roll settings'):
                PixabayClient('BAD', temp, session).search('x', 'landscape', 1920, 1080)

    def test_rejected_key_skips_that_site_but_keeps_the_others(self):
        from hinglish_broll.pipeline import gather_candidates
        from hinglish_broll.timeline import Timeline
        slot = Slot(Moment(0, 'temple', ['temple india', 'temple'], 3), 3, 5, 'x')
        bad, good = MagicMock(), MagicMock()
        bad.name, good.name = 'pexels', 'pixabay'
        bad.search.side_effect = PermissionError('Pexels rejected the API key.')
        good.search.return_value = [Candidate('pixabay', 'pixabay:1', 't', 20, 1080, 1920)]
        clients, notes = [bad, good], []
        timeline = Timeline('t', Fraction(30), 1080, 1920, 60, [])
        found = gather_candidates(slot, None, None, clients, 'portrait', timeline, 8, None, notes.append)
        self.assertEqual([c.id for c in found], ['pixabay:1'])
        self.assertEqual([c.name for c in clients], ['pixabay'])      # later moments skip Pexels
        self.assertTrue(any('Skipping Pexels' in n for n in notes))

    def test_pixabay_keeps_both_orientations_for_the_ranker(self):
        data = {'hits': [{'id': 1, 'duration': 10, 'tags': 'dosa, food', 'pageURL': 'p', 'user': 'u',
                          'videos': {'large': {'url': 'l.mp4', 'width': 1920, 'height': 1080, 'thumbnail': 't1'},
                                     'medium': {'url': 'm.mp4', 'width': 1280, 'height': 720, 'thumbnail': 't2'}}},
                         {'id': 2, 'duration': 10, 'videos': {'large': {'url': 'v.mp4', 'width': 1080, 'height': 1920}}}]}
        with tempfile.TemporaryDirectory() as temp:
            session = MagicMock(); session.get.return_value = response(data)
            found = PixabayClient('K', temp, session).search('dosa', 'landscape', 1920, 1080)
            # Pixabay has few vertical videos: wide ones are kept (centre-cropped later, ranked a bit lower)
            self.assertEqual([(c.id, c.download_url, c.thumb) for c in found],
                             [('pixabay:1', 'l.mp4', 't2'), ('pixabay:2', 'v.mp4', '')])


class PlaceTests(unittest.TestCase):
    """Real mistakes from madurai_1: foreign stock chosen for an Indian story."""

    def test_clips_from_other_countries_are_rejected_for_an_indian_video(self):
        from hinglish_broll.places import conflicts, video_country
        country = video_country({'country': 'India', 'places': ['Delhi', 'Madurai'], 'visual_world': 'Indian city'})
        self.assertEqual(country, 'india')
        self.assertTrue(conflicts('colonial, street, colombia https://pixabay.com/videos/street-1/', country))
        self.assertTrue(conflicts('new york city, manhattan, traffic', country))
        self.assertTrue(conflicts('seoul, traffic, cars, city', country))
        self.assertTrue(conflicts('china, map, globe, earth', country))
        self.assertFalse(conflicts('india, shiva, map, asia', country))           # the good India map
        self.assertFalse(conflicts('crosswalk, crowd, people, walking', country))  # no place: allowed
        self.assertFalse(conflicts('https://www.pexels.com/video/busy-delhi-market-123/', country))

    def test_editing_templates_are_not_used_as_broll(self):
        from hinglish_broll.places import is_template
        self.assertTrue(is_template('television, mock-up, tv, apartment, green screen'))   # real pick from madurai_1
        self.assertTrue(is_template('https://pixabay.com/videos/chroma-key-phone-123/'))
        self.assertFalse(is_template('india, people, asia, street'))

    def test_country_is_added_to_the_first_search(self):
        from hinglish_broll.places import with_country
        self.assertEqual(with_country(['delhi street night', 'city night'], 'india'),
                         ['delhi street night india', 'delhi street night', 'city night'])
        self.assertEqual(with_country(['india map', 'map'], 'india'), ['india map', 'map'])
        self.assertEqual(with_country(['street'], ''), ['street'])

    def test_unclear_country_turns_the_filter_off(self):
        from hinglish_broll.places import video_country
        self.assertEqual(video_country({'country': '', 'places': ['Paris', 'Delhi']}), '')


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

    def test_same_library_file_is_avoided_when_another_is_nearly_as_good(self):
        first, second = self.slot(3, 3), self.slot(12, 2)
        a1 = Candidate('library', 'library:a@0', 'a', 30, 1080, 1920, path='a.mp4', offset=0, score=.32)
        a2 = Candidate('library', 'library:a@20', 'a', 30, 1080, 1920, path='a.mp4', offset=20, score=.32)
        b = Candidate('library', 'library:b@0', 'b', 30, 1080, 1920, path='b.mp4', offset=0, score=.31)
        picks = choose([(first, [a1]), (second, [a2, b])], 'portrait', .2)
        self.assertEqual(picks[1][0].id, 'library:b@0')

    def test_clip_that_fits_another_moment_better_is_rejected(self):
        from hinglish_broll.ranker import add_specificity
        room, van = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
        room_clip = Candidate('library', 'library:room', 'room', 30, 1080, 1920, path='r.mp4', score=.25)
        room_clip.vector = np.array([.9, .3, .1]) / np.linalg.norm([.9, .3, .1])
        van_clip = Candidate('pixabay', 'pixabay:van', 'van', 30, 1920, 1080, score=.27)
        van_clip.vector = np.array([.2, .95, .1]) / np.linalg.norm([.2, .95, .1])
        van_slot, room_slot = self.slot(20), self.slot(40)
        pairs = [(van_slot, [room_clip, van_clip]), (room_slot, [])]
        add_specificity(pairs, [van, room], [])
        self.assertLess(room_clip.specific, 0)          # the room clip really belongs to the room moment
        picks = choose(pairs, 'portrait', .22)
        self.assertEqual(picks[0][0].id, 'pixabay:van')   # wide stock clip wins over an unrelated own clip

    def test_acceptance_rule_matches_real_numbers_from_madurai_video(self):
        from hinglish_broll.ranker import acceptable
        def c(score, specific):
            x = Candidate('library', 'l', 't', 10, 1080, 1920, score=score); x.specific = specific; return x
        self.assertTrue(acceptable(c(.336, -.012)))    # room clip for "crowded PG room": strong match
        self.assertTrue(acceptable(c(.268, .015)))     # decent and specific
        self.assertFalse(acceptable(c(.252, .02)))     # "city, scroll, day" for "confused in a new city": too weak
        self.assertFalse(acceptable(c(.264, -.028)))   # room clip for "geography textbook"
        self.assertFalse(acceptable(c(.281, -.027)))   # room clip for "Zomato app screen"
        self.assertFalse(acceptable(c(.252, -.093)))   # room clip for "delivery van"

    def test_similar_moments_do_not_reject_each_others_clips(self):
        from hinglish_broll.ranker import add_specificity
        alone = np.array([1.0, .1, 0]) / np.linalg.norm([1.0, .1, 0])
        crowded = np.array([1.0, .2, 0]) / np.linalg.norm([1.0, .2, 0])     # nearly the same idea
        clip = Candidate('library', 'library:room', 'room', 30, 1080, 1920, path='r.mp4', score=.33)
        clip.vector = alone
        pairs = [(self.slot(10), [clip]), (self.slot(30), [])]
        add_specificity(pairs, [crowded, alone], [])
        self.assertFalse(hasattr(clip, 'specific') and clip.specific < 0)

    def test_library_takes_of_the_same_video_are_skipped(self):
        from hinglish_broll.library import Library
        lib = Library.__new__(Library)
        same = np.array([[1.0, 0, 0], [.99, .1, 0]], np.float32)            # raw take of the talking head
        mixed = np.array([[1.0, 0, 0], [0, 1.0, 0], [0, .9, .1], [0, .8, .2]], np.float32)  # 1 of 4 look-alike
        lib.entries = [('take.mp4', 10, 1080, 1920, np.array([1.0, 3.0]), same),
                       ('street.mp4', 10, 1080, 1920, np.array([1.0, 3.0, 5.0, 7.0]), mixed)]
        removed = lib.exclude_lookalikes(np.array([[1.0, 0, 0]], np.float32))
        self.assertEqual(removed, 1)
        self.assertEqual([e[0] for e in lib.entries], ['street.mp4'])
        self.assertEqual(list(lib.entries[0][4]), [3.0, 5.0, 7.0])           # only non-duplicate moments remain

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
            # Save & rebuild talks to the DEV engine port, never the original app's 8765
            self.assertIn("fetch('http://127.0.0.1:8766/api/bridge')", text)
            self.assertNotIn('8765', text)


if __name__ == '__main__':
    unittest.main()
