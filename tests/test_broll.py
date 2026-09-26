import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

from hinglish_cut.model import Cut, Media, Word
from hinglish_cut.xml_export import export_xml
from hinglish_broll.phrases import build_phrases
from hinglish_broll.placement import Moment, place
from hinglish_broll.settings import (load_settings, profile_for, public_settings,
                                     save_user_settings)
from hinglish_broll.timeline import parse_xmeml, path_from_pathurl, path_key, timeline_words
from hinglish_broll.xml_export import export_broll_xml


def media(path, seconds=20, width=1080, height=1920, fps='30'):
    return Media(Path(path).stem, str(path), seconds, fps, width, height, 2, 48000)


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def edited_sequence(self):
        a, b = media(self.dir / 'take a.mp4'), media(self.dir / 'take_b.mp4')
        xml = self.dir / 'EDITED.xml'
        # a 2s-5s, then b 10s-12s, then a 1s-2s  -> sequence 0-3, 3-5, 5-6
        export_xml(xml, [Cut(a.id, 60, 150, 0), Cut(b.id, 300, 360, 1), Cut(a.id, 30, 60, 2)],
                   {a.id: a, b.id: b}, 'instagram_vertical')
        return xml, a, b

    def test_pathurl_variants_become_windows_paths(self):
        self.assertEqual(path_from_pathurl('file://localhost/E:/My%20Clips/a.mp4'), str(Path('E:/My Clips/a.mp4')))
        self.assertEqual(path_from_pathurl('file:///E:/x/b.mov'), str(Path('E:/x/b.mov')))
        self.assertEqual(path_from_pathurl('file://localhost/E%3a/x/c.mp4'), str(Path('E:/x/c.mp4')))

    def test_parse_sequence_reads_canvas_rate_and_clip_times(self):
        xml, a, b = self.edited_sequence()
        timeline = parse_xmeml(xml)
        self.assertEqual((timeline.width, timeline.height, timeline.fps), (1080, 1920, Fraction(30)))
        self.assertEqual(timeline.orientation, 'portrait')
        self.assertAlmostEqual(timeline.duration, 6)
        spans = [(round(c.start, 2), round(c.end, 2), round(c.source_in, 2), Path(c.path).name) for c in timeline.clips]
        self.assertEqual(spans, [(0, 3, 2, 'take a.mp4'), (3, 5, 10, 'take_b.mp4'), (5, 6, 1, 'take a.mp4')])
        self.assertEqual(len(timeline.sources()), 2)

    def test_source_words_are_moved_to_sequence_time_and_cut_words_dropped(self):
        xml, a, b = self.edited_sequence()
        timeline = parse_xmeml(xml)
        words = {path_key(a.path): [Word('removed', 0.2, 0.5), Word('pehle', 2.1, 2.4), Word('Madurai', 4.5, 4.9),
                                    Word('intro', 1.2, 1.5)],
                 path_key(b.path): [Word('Rapido', 10.5, 11.0), Word('gone', 13, 13.5)]}
        placed = timeline_words(timeline, words)
        self.assertEqual([w.text for w in placed], ['pehle', 'Madurai', 'Rapido', 'intro'])
        self.assertAlmostEqual(placed[0].start, .1)
        self.assertAlmostEqual(placed[2].start, 3.5)
        self.assertAlmostEqual(placed[3].start, 5.2)

    def test_broll_track_is_inserted_as_v2_with_exact_frames(self):
        xml, a, b = self.edited_sequence()
        timeline = parse_xmeml(xml)
        clip = self.dir / 'broll-01.mp4'
        out = export_broll_xml(timeline, [{'path': str(clip), 'start': 1.0, 'end': 2.5, 'name': 'temple'}],
                               self.dir / 'BROLL_SEQUENCE.xml')
        root = ET.parse(out).getroot()
        self.assertTrue(root.find('sequence/name').text.endswith('_BROLL'))
        tracks = root.findall('sequence/media/video/track')
        self.assertEqual(len(tracks), 2)
        item = tracks[1].find('clipitem')
        self.assertEqual([item.findtext(t) for t in ('start', 'end', 'in', 'out')], ['30', '75', '0', '45'])
        self.assertIn('broll-01.mp4', item.find('file/pathurl').text)
        # The talking head is untouched and still first.
        self.assertIn('take', tracks[0].find('clipitem/name').text)
        self.assertEqual(parse_xmeml(out).clips[0].path, timeline.clips[0].path)

    def test_broll_goes_below_existing_caption_track(self):
        xml, a, b = self.edited_sequence()
        tree = ET.parse(xml)
        video = tree.getroot().find('sequence/media/video')
        captions = ET.SubElement(video, 'track'); ET.SubElement(captions, 'clipitem', id='caption-overlay-1')
        tree.write(xml)
        timeline = parse_xmeml(xml)
        out = export_broll_xml(timeline, [{'path': str(self.dir / 'x.mp4'), 'start': 1, 'end': 2}], self.dir / 'o.xml')
        tracks = ET.parse(out).getroot().findall('sequence/media/video/track')
        self.assertEqual(tracks[1].find('clipitem').get('id'), 'broll-clip-1')
        self.assertEqual(tracks[2].find('clipitem').get('id'), 'caption-overlay-1')


class PlacementTests(unittest.TestCase):
    def words(self, seconds, every=.5):
        return [Word(f'w{i}', i * every, i * every + .4) for i in range(int(seconds / every))]

    def test_phrases_break_on_pause_and_length(self):
        words = [Word('Aaj', 0, .3), Word('hum', .35, .6), Word('Madurai', .65, 1.1), Word('gaye.', 1.15, 1.5),
                 Word('Wahan', 2.5, 2.8), Word('ka', 2.85, 3.0), Word('temple', 3.05, 3.4), Word('dekha', 3.45, 3.8)]
        self.assertEqual([p.text for p in build_phrases(words)], ['Aaj hum Madurai gaye.', 'Wahan ka temple dekha'])

    def test_fragments_join_a_neighbour_so_meaning_survives(self):
        words = [Word('Bhai', 0, .3), Word('nahin', .35, .6), Word('thi.', .65, .9),
                 Word('Washing', 1.3, 1.7), Word('machine', 1.75, 2.1), Word('bhi', 2.15, 2.3), Word('nahin.', 2.35, 2.7),
                 Word('Haan', 6, 6.2), Word('ji.', 6.25, 6.4)]
        phrases = build_phrases(words)
        self.assertEqual([p.text for p in phrases], ['Bhai nahin thi. Washing machine bhi nahin.', 'Haan ji.'])
        self.assertEqual([p.id for p in phrases], [0, 1])

    def test_short_profile_protects_hook_and_respects_spacing(self):
        profile = profile_for(60)
        self.assertEqual(profile.name, 'short')
        phrases = build_phrases(self.words(60))
        moments = [Moment(p.id, 'visual', ['q'], 2) for p in phrases]
        slots = place(moments, phrases, profile, 60)
        self.assertGreater(len(slots), 5)
        self.assertGreaterEqual(slots[0].start, profile.hook)
        self.assertLessEqual(slots[-1].end, 60 - profile.tail)
        for a, b in zip(slots, slots[1:]):
            self.assertGreaterEqual(b.start - a.end, profile.min_gap - 1e-6)
            self.assertGreaterEqual(b.start - a.start, profile.min_spacing - 1e-6)
        for s in slots:
            self.assertTrue(profile.min_len - 1e-6 <= s.duration <= profile.max_len + 1e-6)
        self.assertLessEqual(sum(s.duration for s in slots), profile.max_coverage * 60 + 1e-6)

    def test_long_form_uses_youtube_rules_and_prefers_high_priority(self):
        profile = profile_for(1200)
        self.assertEqual(profile.name, 'long')
        phrases = build_phrases(self.words(120))
        moments = [Moment(p.id, 'v', ['q'], 3 if p.id == 13 else 1) for p in phrases]
        slots = place(moments, phrases, profile, 120)
        self.assertIn(13, [s.moment.phrase_id for s in slots])
        self.assertTrue(all(s.duration >= 3 - 1e-6 for s in slots))

    def test_an_early_weak_moment_does_not_block_two_better_ones(self):
        from hinglish_broll.phrases import Phrase
        profile = profile_for(60)
        # "Bhai nahin thi." then "Python nahin. Washing machine nahin. Fridge nahin. AC." then later phrase.
        phrases = [Phrase(0, 25.5, 26.2, 'Bhai nahin thi.'),
                   Phrase(1, 26.9, 33.0, 'Python nahin. Washing machine nahin. Fridge nahin. AC.'),
                   Phrase(2, 38.2, 39.5, 'Milega par jugaad se.')]
        moments = [Moment(0, 'v', ['q'], 3), Moment(1, 'v', ['q'], 3), Moment(2, 'v', ['q'], 3)]
        # Greedy-in-time would keep 0 and lose the richer list phrase 1; they cannot both fit.
        self.assertEqual([s.moment.phrase_id for s in place(moments, phrases, profile, 60)], [1, 2])

    def test_broll_lasts_exactly_as_long_as_its_spoken_line(self):
        from hinglish_broll.phrases import Phrase
        lines = [Phrase(0, 10.0, 13.0, 'Jab tumne apne school ke geography mein padha'),
                 Phrase(1, 13.1, 15.0, 'Mere company ne mujhe bheja'),
                 Phrase(2, 16.0, 16.6, 'Haan ji'),
                 Phrase(3, 18.0, 20.0, 'Flat milna impossible hai')]
        merged = [Phrase(0, 10.0, 15.0, 'Jab tumne apne school ke geography mein padha Mere company ne mujhe bheja'),
                  Phrase(1, 16.0, 16.6, 'Haan ji'), Phrase(2, 18.0, 20.0, 'Flat milna impossible hai')]
        moments = [Moment(0, 'india map', ['india map'], 3, quote='school ke geography'),
                   Moment(1, 'nodding', ['nod'], 2, quote='Haan ji')]
        slots = place(moments, merged, profile_for(60), 60, lines)
        self.assertEqual((slots[0].start, slots[0].end), (10.0, 13.0))     # the geography line only
        self.assertIn('geography', slots[0].text)
        self.assertNotIn('company', slots[0].text)                          # never runs into the next line
        self.assertEqual((slots[1].start, slots[1].end), (16.0, 17.0))     # short line: extends into silence only

    def test_density_changes_amount(self):
        phrases = build_phrases(self.words(60))
        moments = [Moment(p.id, 'v', ['q']) for p in phrases]
        counts = [len(place(moments, phrases, profile_for(60, d), 60)) for d in ('low', 'medium', 'high')]
        self.assertLess(counts[0], counts[1]); self.assertLess(counts[1], counts[2])


class SettingsTests(unittest.TestCase):
    def test_keys_are_saved_locally_and_never_returned(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'footage'; folder.mkdir()
            shown = save_user_settings(temp, {'pexels_key': 'abcdef123456', 'library_folders': [str(folder)]})
            self.assertNotIn('abcdef123456', json.dumps(shown))
            self.assertTrue(shown['pexels_key'].endswith('3456'))
            # Saving an empty key keeps the previous one.
            save_user_settings(temp, {'pexels_key': '', 'use_pixabay': False})
            settings = load_settings(temp, density='high')
            self.assertEqual(settings.pexels_key, 'abcdef123456')
            self.assertEqual(settings.density, 'high')
            self.assertEqual(settings.sources(), ['library', 'pexels'])
            self.assertEqual(public_settings(temp)['library_folders'], [str(folder)])

    def test_missing_library_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                save_user_settings(temp, {'library_folders': [str(Path(temp) / 'nope')]})


if __name__ == '__main__':
    unittest.main()
