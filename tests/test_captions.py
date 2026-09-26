import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import av

from hinglish_captions.core import (CaptionCue, CaptionWord, build_cues,
                                    correct_with_reference, retime_cue_text, timed_words)
from hinglish_captions.report import write_report
from hinglish_captions.renderer import draw_caption, render_overlay
from hinglish_captions.subtitles import write_ass, write_srt
from hinglish_captions.xml_export import export_caption_xml
from hinglish_cut.model import Media, Word


class CaptionTests(unittest.TestCase):
    def test_coarse_hinglish_words_receive_individual_monotonic_times(self):
        source = [Word(text, 1, 3, 0, False) for text in ('aaj', 'hum', 'edit', 'karenge')]
        words = timed_words(source, 4)
        self.assertEqual([word.text for word in words], ['aaj', 'hum', 'edit', 'karenge'])
        self.assertTrue(all(a.end <= b.start + .011 for a, b in zip(words, words[1:])))
        self.assertAlmostEqual(words[0].start, 1)
        self.assertAlmostEqual(words[-1].end, 3)

    def test_caption_phrases_break_on_pause_and_stay_readable(self):
        words = [CaptionWord('Aaj', 0, .3), CaptionWord('hum', .31, .55),
                 CaptionWord('editing', .56, 1), CaptionWord('seekhenge.', 1.01, 1.5),
                 CaptionWord('Next', 2.2, 2.5)]
        cues = build_cues(words, max_words=4)
        self.assertEqual([cue.text for cue in cues], ['Aaj hum editing seekhenge.', 'Next'])

    def test_srt_keeps_roman_hinglish(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'captions.srt'
            cue = CaptionCue((CaptionWord('Yahaan', 0, .4), CaptionWord('Tamil', .4, .8)), 0, .9)
            write_srt(path, [cue])
            text = path.read_text(encoding='utf-8-sig')
            self.assertIn('Yahaan Tamil', text)
            self.assertIn('00:00:00,000 --> 00:00:00,900', text)

    def test_loose_script_corrects_spelling_without_replacing_different_words(self):
        words = [CaptionWord('Kamilaadu', 0, .4), CaptionWord('mera', .4, .7),
                 CaptionWord('home', .7, 1.0)]
        corrected, changes = correct_with_reference(
            words, '[A-Cam] Tamilnadu mein mera ghar hai. This line is only a guide.')
        self.assertEqual([word.text for word in corrected], ['Tamilnadu', 'mera', 'home'])
        self.assertEqual(changes[0]['heard'], 'Kamilaadu')
        short, _ = correct_with_reference(
            [CaptionWord(word, i, i + .5) for i, word in enumerate('Vah bas din mein'.split())],
            'Wah bus din mein')
        self.assertEqual([word.text for word in short], ['Wah', 'bus', 'din', 'mein'])

    def test_manual_caption_edit_retimes_every_replacement_word(self):
        cue = CaptionCue((CaptionWord('wrong', 1, 1.4), CaptionWord('words', 1.4, 2)), 1, 2)
        edited = retime_cue_text(cue, 'correct Roman Hinglish text')
        self.assertEqual(edited.text, 'correct Roman Hinglish text')
        self.assertEqual((edited.words[0].start, edited.words[-1].end), (1, 2))
        self.assertTrue(all(a.end <= b.start for a, b in zip(edited.words, edited.words[1:])))

    def test_ass_keeps_editable_font_position_size_and_template_colors(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'captions.ass'
            cue = CaptionCue((CaptionWord('Signal', 0, .4), CaptionWord('bar', .4, .8)), 0, .8)
            write_ass(path, [cue], 'signal_bar', 1080, 1920, 'segoe', .42, 1.25)
            text = path.read_text(encoding='utf-8-sig')
            self.assertIn('Style: Premium,Segoe UI', text)
            self.assertIn('\\pos(540,806)', text)
            self.assertIn('&H10F57D08', text)

    def test_report_is_an_on_video_editor_with_cinematic_templates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.html'
            cue = CaptionCue((CaptionWord('Go', 0, .3), CaptionWord('viral', .3, .7)), 0, .7)
            write_report(path, 'sample.mp4', 'media/source.mp4', [cue], 'flash_cut', [],
                         {'width': 1080, 'height': 1920, 'output_format': 'source'})
            text = path.read_text(encoding='utf-8')
            self.assertIn('<video id="video"', text)
            self.assertIn('<div id="caption">', text)
            self.assertIn('Text &amp; words', text)
            self.assertIn('Save &amp; rebuild', text)
            self.assertIn('Signal Bar', text)
            self.assertIn('Soft Focus', text)
            self.assertIn('Typography 1', text)

    def test_transparent_caption_movie_has_alpha(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'captions.mov'
            cue = CaptionCue((CaptionWord('Hinglish', 0, .18),), 0, .18)
            render_overlay(path, [cue], 320, 180, .2, fps=10, style_name='punch', progress=lambda _: None)
            with av.open(str(path)) as video:
                stream = video.streams.video[0]
                frame = next(video.decode(stream)).to_ndarray(format='rgba')
            self.assertEqual((stream.width, stream.height), (320, 180))
            self.assertLess(frame[:, :, 3].min(), 255)
            self.assertGreater(frame[:, :, 3].max(), 0)

    def test_typography_one_has_colored_strip_motion_blur_and_camera_change(self):
        cue = CaptionCue(tuple(CaptionWord(word, i * .3, (i + 1) * .3)
                               for i, word in enumerate('Madurai me Rapido booking struggle hai'.split())),
                         0, 2.2)
        entrance = draw_caption(540, 960, cue, .08, 'typography_1', position=.55)
        settled = draw_caption(540, 960, cue, .7, 'typography_1', position=.55)
        self.assertNotEqual(entrance.tobytes(), settled.tobytes())
        pixels = __import__('numpy').asarray(settled)
        opaque = pixels[:, :, 3] > 80
        saturated = pixels[:, :, :3].max(axis=2) - pixels[:, :, :3].min(axis=2) > 70
        self.assertGreater(int((opaque & saturated).sum()), 500)
        self.assertGreater(int(opaque.sum()), 2000)

    def test_caption_movie_keeps_fractional_source_frame_rate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'captions.mov'
            cue = CaptionCue((CaptionWord('Hinglish', 0, .08),), 0, .08)
            render_overlay(path, [cue], 160, 90, .1, fps='30000/1001',
                           style_name='minimal', progress=lambda _: None)
            with av.open(str(path)) as video:
                self.assertEqual(video.streams.video[0].average_rate.numerator, 30000)
                self.assertEqual(video.streams.video[0].average_rate.denominator, 1001)

    def test_xml_places_caption_overlay_above_original_video(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source, overlay, xml = folder / 'source.mp4', folder / 'captions.mov', folder / 'timeline.xml'
            source.write_bytes(b'source'); overlay.write_bytes(b'overlay')
            media = Media('m1', str(source), 2, '30', 1920, 1080, 2, 48000)
            export_caption_xml(xml, media, overlay)
            root = ET.parse(xml).getroot()
            tracks = root.findall('./sequence/media/video/track')
            self.assertEqual(len(tracks), 2)
            self.assertEqual(tracks[1].findtext('./clipitem/name'), 'captions.mov')
            self.assertEqual(root.findtext('./sequence/name'), 'CAPTIONED_source')


if __name__ == '__main__':
    unittest.main()
