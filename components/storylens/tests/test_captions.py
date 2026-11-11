import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import av

from hinglish_captions.core import (CaptionCue, CaptionWord, build_cues,
                                    correct_with_reference, hero_span,
                                    important_word_index, retime_cue_text, timed_words)
from hinglish_captions.report import write_report
from hinglish_captions.renderer import (_typography_five_anchor, draw_caption,
                                        render_overlay)
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

    def test_caption_frames_never_exceed_five_words(self):
        words = [CaptionWord(word, index * .2, (index + 1) * .2)
                 for index, word in enumerate('one two three four five six seven'.split())]
        cues = build_cues(words)
        self.assertTrue(all(len(cue.words) <= 5 for cue in cues))
        with self.assertRaisesRegex(ValueError, 'more than 5 words'):
            draw_caption(540, 960, CaptionCue(tuple(words[:6]), 0, 1.2), .5, 'typography_1')

    def test_connected_caption_frames_are_balanced_instead_of_orphaned(self):
        phrase = 'Wah bus din mein kitni baar chalti hai?'.split()
        words = [CaptionWord(word, index * .2, (index + 1) * .2)
                 for index, word in enumerate(phrase)]
        cues = build_cues(words)
        self.assertEqual([len(cue.words) for cue in cues], [4, 4])
        six = [CaptionWord(word, index * .2, (index + 1) * .2)
               for index, word in enumerate('Second take checked and manually editable'.split())]
        self.assertEqual([len(cue.words) for cue in build_cues(six)], [3, 3])

    def test_typography_hero_is_semantic_not_a_connector_word(self):
        examples = [
            ('Madurai alag hi struggle yahan'.split(), 'struggle'),
            ('WiFi fridge AC room jugaad'.split(), 'jugaad'),
            ('Character assassination na hi karun'.split(), 'assassination'),
            ('Second take checked and manually'.split(), 'checked'),
        ]
        for words, expected in examples:
            self.assertEqual(words[important_word_index(words)].casefold(), expected)
        self.assertEqual(hero_span('aur jo 1 percent milega'.split()), (2, 4))
        self.assertEqual(hero_span('usme kuch nahi hoga'.split()), (1, 3))
        words = 'aur tab tum wahaan reh'.split()
        self.assertEqual(words[important_word_index(words)], 'wahaan')

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
            self.assertNotIn('data-style="signal_bar"', text)
            self.assertNotIn('data-style="soft_focus"', text)
            self.assertIn('Typography 1', text)
            self.assertIn('Typography 2', text)
            self.assertIn('Typography 3', text)
            self.assertIn('Typography 4', text)
            self.assertIn('data-style="typography_5"', text)
            self.assertIn('Quiet Minimal', text)
            self.assertIn("font-family:'Great Vibes'",text)
            self.assertIn('data:font/ttf;base64,',text)
            self.assertIn('t4-custom', text)
            self.assertNotIn('.t4-accent[style]', text)
            self.assertIn('Select a word, then choose its color', text)
            for color in ('#F04444', '#FFD400', '#1677FF', '#0B2E8F', '#52C7FF', '#8B5CF6'):
                self.assertIn(color, text)

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
        start = 1 / 30
        cue = CaptionCue(tuple(CaptionWord(word, start + i * .3, start + (i + 1) * .3)
                               for i, word in enumerate('Madurai Rapido booking struggle hai'.split())),
                         start, start + 2.2)
        entrance = draw_caption(540, 960, cue, start + .08, 'typography_1', position=.55)
        settled = draw_caption(540, 960, cue, start + .7, 'typography_1', position=.55)
        self.assertNotEqual(entrance.tobytes(), settled.tobytes())
        pixels = __import__('numpy').asarray(settled)
        opaque = pixels[:, :, 3] > 80
        saturated = pixels[:, :, :3].max(axis=2) - pixels[:, :, :3].min(axis=2) > 70
        self.assertGreater(int((opaque & saturated).sum()), 500)
        self.assertGreater(int(opaque.sum()), 2000)

    def test_typography_one_holds_completed_group_until_its_end(self):
        cue = CaptionCue(tuple(CaptionWord(word, i * .25, (i + 1) * .25)
                               for i, word in enumerate('flat toh mil hi jayega'.split())),
                         0, 2)
        hold_a = draw_caption(540, 960, cue, 1.3, 'typography_1', position=.55)
        hold_b = draw_caption(540, 960, cue, 1.7, 'typography_1', position=.55)
        self.assertEqual(hold_a.tobytes(), hold_b.tobytes())
        exit_frame = draw_caption(540, 960, cue, 1.92, 'typography_1', position=.55)
        self.assertEqual(exit_frame.tobytes(),hold_a.tobytes())
        self.assertIsNone(draw_caption(540,960,cue,2,'typography_1',position=.55).getbbox())

    def test_typography_one_accepts_single_word_in_every_layout(self):
        for variant in range(8):
            start = variant / 30
            cue = CaptionCue((CaptionWord('Readable', start, start + 1),), start, start + 1)
            frame = draw_caption(540, 960, cue, start + .5, 'typography_1', position=.55)
            self.assertIsNotNone(frame.getbbox())

    def test_typography_two_matches_script_and_signal_bar_grammar(self):
        words = 'ek mukam ata hai'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .35, (index + 1) * .35)
                               for index, word in enumerate(words)), 0, 1.8)
        entrance = draw_caption(1280, 720, cue, .08, 'typography_2', position=.52)
        settled = draw_caption(1280, 720, cue, .9, 'typography_2', position=.52,
                               word_colors=[None, '#FFD400', None, None])
        self.assertNotEqual(entrance.tobytes(), settled.tobytes())
        pixels = __import__('numpy').asarray(settled)
        blue = ((pixels[:, :, 2] > 170) & (pixels[:, :, 0] < 60) &
                (pixels[:, :, 3] > 180))
        yellow = ((pixels[:, :, 0] > 190) & (pixels[:, :, 1] > 150) &
                  (pixels[:, :, 2] < 90) & (pixels[:, :, 3] > 100))
        self.assertGreater(int(blue.sum()), 1000)
        self.assertGreater(int(yellow.sum()), 100)

    def test_typography_two_default_palette_has_only_reference_colors(self):
        words = 'sab dhundhala ho jata hai'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .18, (index + 1) * .18)
                               for index, word in enumerate(words)), 0, 1.2)
        frame = draw_caption(1280, 720, cue, .72, 'typography_2', position=.52)
        pixels = __import__('numpy').asarray(frame)
        visible = pixels[:, :, 3] > 100
        blue = visible & (pixels[:, :, 2] > 170) & (pixels[:, :, 0] < 80)
        yellow = visible & (pixels[:, :, 0] > 170) & (pixels[:, :, 1] > 130) & \
                 (pixels[:, :, 2] < 100)
        self.assertGreater(int(blue.sum()), 1000)
        self.assertEqual(int(yellow.sum()), 0)

    def test_typography_two_two_word_scene_is_large_red_script_with_one_support(self):
        cue = CaptionCue((CaptionWord('jata', 0, .6), CaptionWord('hai', .6, 1.2)),
                         0, 1.2)
        frame = draw_caption(1280, 720, cue, .65, 'typography_2', position=.52)
        pixels = __import__('numpy').asarray(frame)
        red = ((pixels[:, :, 0] > 90) & (pixels[:, :, 0] > pixels[:, :, 1] * 1.6) &
               (pixels[:, :, 3] > 100))
        blue = ((pixels[:, :, 2] > 150) & (pixels[:, :, 0] < 80) &
                (pixels[:, :, 3] > 100))
        columns = __import__('numpy').where(red.any(axis=0))[0]
        self.assertGreater(columns[-1] - columns[0], 300)
        self.assertEqual(int(blue.sum()), 0)

    def test_typography_two_short_bar_moves_right_label_without_widening_box(self):
        words = 'toh bas ek shareer'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .2, (index + 1) * .2)
                               for index, word in enumerate(words)), 0, 1.0)
        frame = draw_caption(1280, 720, cue, .72, 'typography_2', position=.52)
        pixels = __import__('numpy').asarray(frame)
        blue = ((pixels[:, :, 2] > 170) & (pixels[:, :, 0] < 80) &
                (pixels[:, :, 3] > 150))
        blue_rows = __import__('numpy').where(blue.any(axis=1))[0]
        white_above = ((pixels[:, :, 0] > 180) & (pixels[:, :, 1] > 180) &
                       (pixels[:, :, 2] > 180) &
                       (__import__('numpy').indices(blue.shape)[0] < blue_rows[0]))
        occupied = __import__('numpy').where(white_above.any(axis=0))[0]
        gaps = occupied[1:] - occupied[:-1] - 1
        self.assertGreaterEqual(int(gaps.max()), 20)
        self.assertLessEqual(int(gaps.max()), 40)
        blue_columns = __import__('numpy').where(blue.any(axis=0))[0]
        self.assertGreater(occupied[-1] - occupied[0],
                           blue_columns[-1] - blue_columns[0])

    def test_typography_three_matches_measured_anchor_and_support_layout(self):
        words = 'ek khas ehasas jo kano'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .16, (index + 1) * .16)
                               for index, word in enumerate(words)), 0, 1.3)
        frame = draw_caption(720, 1280, cue, .9, 'typography_3', position=.235)
        box = frame.getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[2] - box[0], 220)
        self.assertLessEqual(box[2] - box[0], 245)
        self.assertGreaterEqual(box[3] - box[1], 110)
        self.assertLessEqual(box[3] - box[1], 125)
        pixels = __import__('numpy').asarray(frame)
        visible = pixels[:, :, 3] > 100
        chroma = pixels[:, :, :3].max(axis=2) - pixels[:, :, :3].min(axis=2)
        self.assertEqual(int((visible & (chroma > 25)).sum()), 0)

    def test_typography_three_has_reference_scale_blur_transition_and_word_colors(self):
        words = 'fir sawal uthata hai vahee'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .18, (index + 1) * .18)
                               for index, word in enumerate(words)), 0, 1.4)
        entrance = draw_caption(720, 1280, cue, .04, 'typography_3', position=.235)
        settled = draw_caption(720, 1280, cue, .95, 'typography_3', position=.235,
                               word_colors=[None, None, '#8B5CF6', None, None])
        self.assertNotEqual(entrance.tobytes(), settled.tobytes())
        self.assertLess(entrance.getbbox()[2] - entrance.getbbox()[0],
                        settled.getbbox()[2] - settled.getbbox()[0])
        pixels = __import__('numpy').asarray(settled)
        purple = ((pixels[:, :, 0] > 90) & (pixels[:, :, 2] > 120) &
                  (pixels[:, :, 3] > 80))
        self.assertGreater(int(purple.sum()), 100)

    def test_typography_three_holds_sharp_until_a_hard_cut(self):
        words = 'fir sawal uthata hai vahee'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .10, (index + 1) * .10)
                               for index, word in enumerate(words)), 0, 1.3)
        hold = draw_caption(720, 1280, cue, .85, 'typography_3', position=.235)
        final_frame = draw_caption(720, 1280, cue, 1.29, 'typography_3', position=.235)
        self.assertEqual(hold.tobytes(), final_frame.tobytes())

    def test_typography_four_matches_fixed_two_line_gradient_layout(self):
        words = 'fir sawal uthata hai'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .16, (index + 1) * .16)
                               for index, word in enumerate(words)), 0, 1.2)
        frame = draw_caption(720, 1280, cue, .9, 'typography_4', position=.235)
        box = frame.getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[2] - box[0], 320)
        self.assertLessEqual(box[2] - box[0], 370)
        self.assertGreaterEqual(box[3] - box[1], 75)
        self.assertLessEqual(box[3] - box[1], 95)
        pixels = __import__('numpy').asarray(frame)
        cyan = ((pixels[:, :, 2] > pixels[:, :, 0]) & (pixels[:, :, 0] < 180) &
                (pixels[:, :, 1] > 140) &
                (pixels[:, :, 3] > 80))
        white = ((pixels[:, :, 0] > 220) & (pixels[:, :, 1] > 220) &
                 (pixels[:, :, 2] > 220) & (pixels[:, :, 3] > 80))
        self.assertGreater(int(cyan.sum()), 100)
        self.assertGreater(int(white.sum()), 500)

    def test_typography_four_fades_linearly_at_final_position_and_hard_cuts(self):
        cue = CaptionCue((CaptionWord('Machine', 0, .8), CaptionWord('koi', .4, 1.2)),
                         0, 1.2)
        frames = [draw_caption(720, 1280, cue, moment, 'typography_4', position=.235)
                  for moment in (.04, .08, .12, .24)]
        alpha_sums = [int(__import__('numpy').asarray(frame)[:, :, 3].sum())
                      for frame in frames]
        self.assertTrue(all(a < b for a, b in zip(alpha_sums, alpha_sums[1:])))
        self.assertAlmostEqual(alpha_sums[1] / alpha_sums[0], 2, delta=.15)
        self.assertAlmostEqual(alpha_sums[2] / alpha_sums[0], 3, delta=.20)
        early_box = frames[0].getbbox()
        settled_box = frames[-1].getbbox()
        self.assertEqual((early_box[0], early_box[2]), (settled_box[0], settled_box[2]))
        hold = draw_caption(720, 1280, cue, .95, 'typography_4', position=.235)
        final_frame = draw_caption(720, 1280, cue, 1.19, 'typography_4', position=.235)
        self.assertEqual(hold.tobytes(), final_frame.tobytes())

    def test_typography_four_word_color_replaces_default_gradient(self):
        cue = CaptionCue((CaptionWord('rakhta', 0, .3), CaptionWord('hai', .3, .8)), 0, .8)
        frame = draw_caption(720, 1280, cue, .7, 'typography_4', position=.235,
                             word_colors=[None, '#8B5CF6'])
        pixels = __import__('numpy').asarray(frame)
        purple = ((pixels[:, :, 0] > 90) & (pixels[:, :, 2] > 120) &
                  (pixels[:, :, 3] > 80))
        cyan = ((pixels[:, :, 2] > pixels[:, :, 0]) & (pixels[:, :, 0] < 180) &
                (pixels[:, :, 1] > 140) &
                (pixels[:, :, 3] > 80))
        self.assertGreater(int(purple.sum()), 100)
        self.assertEqual(int(cyan.sum()), 0)

    def test_typography_five_rejects_short_leads_and_allows_long_first_word(self):
        self.assertEqual(_typography_five_anchor('ek mukam ata hai'.split()), 1)
        self.assertEqual(_typography_five_anchor('hai vo gayab ho jati'.split()), 2)
        self.assertEqual(_typography_five_anchor('Machine ka tab koi vajan'.split()), 0)

    def test_typography_five_reference_recipes_keep_all_words_and_the_measured_anchor(self):
        from unittest.mock import patch
        from PIL import ImageDraw
        from hinglish_captions.styles import template
        original=ImageDraw.ImageDraw.text
        for recipe in template('typography_5')['reference_recipes']:
            words=recipe['text'].split()
            self.assertEqual(_typography_five_anchor(words),recipe['hero'])
            cue=CaptionCue(tuple(CaptionWord(word,i*.1,(i+1)*.1) for i,word in enumerate(words)),0,2)
            painted=[]
            def record(draw,xy,text,*args,**kwargs):
                if kwargs.get('fill',(0,0,0,0))[3]>0:painted.append(text)
                return original(draw,xy,text,*args,**kwargs)
            with patch.object(ImageDraw.ImageDraw,'text',record):
                frame=draw_caption(720,1280,cue,1.9,'typography_5',position=.22)
            self.assertCountEqual(painted,words)
            bounds=frame.getbbox()
            self.assertIsNotNone(bounds)
            self.assertLess(bounds[3]-bounds[1],165,recipe['text'])

    def test_typography_five_matches_script_support_geometry_and_soft_reveal(self):
        words = 'vakt aur fasle ko par'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .12, (index + 1) * .12)
                               for index, word in enumerate(words)), 0, 1.2)
        early = draw_caption(720, 1280, cue, .27, 'typography_5', position=.22)
        settled = draw_caption(720, 1280, cue, .95, 'typography_5', position=.22)
        box = settled.getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[2] - box[0], 170)
        self.assertLessEqual(box[2] - box[0], 230)
        # The reference shares font origins: small text tucks into the
        # calligraphic ascenders/descenders instead of adding clearance.
        self.assertGreaterEqual(box[3] - box[1], 125)
        self.assertLessEqual(box[3] - box[1], 155)
        self.assertLess(__import__('numpy').asarray(early)[:, :, 3].sum(),
                        __import__('numpy').asarray(settled)[:, :, 3].sum())
        pixels = __import__('numpy').asarray(settled)
        red = ((pixels[:, :, 0] > 150) & (pixels[:, :, 0] > pixels[:, :, 1] * 1.5) &
               (pixels[:, :, 3] > 80))
        white = ((pixels[:, :, :3].min(axis=2) > 180) & (pixels[:, :, 3] > 80))
        self.assertGreater(int(red.sum()), 1000)
        self.assertGreater(int(white.sum()), 500)

    def test_typography_five_custom_word_color_overrides_script_red(self):
        words = 'ek khas ehasas jo kano'.split()
        cue = CaptionCue(tuple(CaptionWord(word, index * .10, (index + 1) * .10)
                               for index, word in enumerate(words)), 0, 1.0)
        frame = draw_caption(720, 1280, cue, .9, 'typography_5', position=.22,
                             word_colors=[None, None, '#8B5CF6', None, None])
        pixels = __import__('numpy').asarray(frame)
        purple = ((pixels[:, :, 0] > 90) & (pixels[:, :, 2] > 120) &
                  (pixels[:, :, 3] > 80))
        default_red = ((pixels[:, :, 0] > 150) &
                       (pixels[:, :, 0] > pixels[:, :, 1] * 1.5) &
                       (pixels[:, :, 3] > 80))
        self.assertGreater(int(purple.sum()), 500)
        self.assertEqual(int(default_red.sum()), 0)

    def test_typography_word_colors_work_in_typography_one(self):
        cue = CaptionCue(tuple(CaptionWord(word, index * .25, (index + 1) * .25)
                               for index, word in enumerate('flat toh mil jayega'.split())),
                         0, 1.6)
        frame = draw_caption(540, 960, cue, .8, 'typography_1', position=.55,
                             word_colors=['#8B5CF6', None, None, None])
        pixels = __import__('numpy').asarray(frame)
        purple = ((pixels[:, :, 0] > 90) & (pixels[:, :, 2] > 120) &
                  (pixels[:, :, 3] > 80))
        self.assertGreater(int(purple.sum()), 30)

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
