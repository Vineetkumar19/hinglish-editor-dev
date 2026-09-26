import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from hinglish_cut.model import Word, Media, Transcript, Cut, Settings, Selection
from hinglish_cut.matching import arrange
from hinglish_cut.cutting import make_cuts, selection_limits, constrain_cuts
from hinglish_cut.evaluate import compare_text
from hinglish_cut.xml_export import export_xml


def transcript(name, text, start=1.0):
    words = [Word(t, start+i*.4, start+i*.4+.25, .95) for i,t in enumerate(text.split())]
    media = Media(name, str(Path(name).resolve()), 30, '25', 1920, 1080, 2, 48000)
    return Transcript(media, words, [(0, 29)], [])


class MatchingTests(unittest.TestCase):
    def test_phrase_alias_expands_a_fused_asr_word(self):
        """Whisper may write several spoken words as one fused Roman-Hindi word."""
        settings=Settings(aliases={'managardi':'mana kar diya'})
        choices=arrange(['Mana kar diya?'],[transcript('a.mp4','managardi')],settings)
        self.assertEqual(choices[0].media_id,'a.mp4')

    def test_near_complete_phrase_is_not_lost_when_its_last_word_is_unheard(self):
        settings=Settings(aliases={'ka mil':'tamil','chalta':'chalti'})
        choices=arrange(['Yahaan sirf Tamil chalti hai'],
                        [transcript('a.mp4','yahaan sirf ka mil chalta')],settings)
        self.assertEqual(choices[0].media_id,'a.mp4')

    def test_script_order_overrides_file_order_and_retake_is_selected(self):
        clips = [transcript('b.mp4', 'ab hum export karenge'),
                 transcript('bad.mp4', 'aaj hum galat bol rahe hain'),
                 transcript('a.mp4', 'aaj hum editing seekhenge')]
        choices = arrange(['aaj hum editing seekhenge', 'ab hum export karenge'], clips, Settings())
        self.assertEqual([x.media_id for x in choices], ['a.mp4', 'b.mp4'])

    def test_missing_line_is_explicit(self):
        choices = arrange(['quantum gravity black holes'], [transcript('a.mp4','aaj chai peete hain')], Settings())
        self.assertIsNone(choices[0].media_id)

    def test_same_source_words_cannot_fill_two_script_lines(self):
        choices = arrange(['aaj hum editing seekhenge']*2, [transcript('a.mp4','aaj hum editing seekhenge')], Settings())
        self.assertEqual(sum(x.media_id is not None for x in choices), 1)

    def test_distinct_repeated_takes_are_flagged_ambiguous(self):
        choices = arrange(['aaj hum editing seekhenge'], [transcript('a.mp4','aaj hum editing seekhenge'),transcript('b.mp4','aaj hum editing seekhenge')], Settings())
        self.assertTrue(choices[0].ambiguous)


class CuttingTests(unittest.TestCase):
    def test_adjacent_script_lines_do_not_repeat_padding_frames(self):
        t=transcript('a.mp4','hello world')
        t.words=[Word('hello',1,1.4,.9),Word('world',1.48,1.8,.9)]
        choices=[Selection(0,'hello','a.mp4',0,1),Selection(1,'world','a.mp4',1,2)]
        limits=selection_limits(choices,{'a.mp4':t})
        first=constrain_cuts(make_cuts(t,0,1,Settings()),limits[0])
        second=constrain_cuts(make_cuts(t,1,2,Settings()),limits[1])
        self.assertLessEqual(first[-1].end_frame,second[0].start_frame)
        self.assertGreaterEqual(first[-1].end_frame,35)
        self.assertLessEqual(second[0].start_frame,37)

    def test_remove_gap_and_preserve_whole_words(self):
        t = transcript('a.mp4','hello world')
        t.words = [Word('hello',1,1.4,.9),Word('world',3,3.4,.9)]
        t.speech = [(1.05,1.3),(3.05,3.3)]
        cuts = make_cuts(t,0,2,Settings())
        self.assertEqual(len(cuts),2)
        self.assertLessEqual(cuts[0].start_frame,25)
        self.assertGreaterEqual(cuts[0].end_frame,35)
        self.assertLessEqual(cuts[1].start_frame,75)

    def test_vad_speech_in_gap_is_not_deleted(self):
        t = transcript('a.mp4','hello world')
        t.words = [Word('hello',1,1.4,.9),Word('world',3,3.4,.9)]
        t.speech = [(1,3.4)]
        self.assertEqual(len(make_cuts(t,0,2,Settings())),1)

    def test_unaligned_word_retains_whole_span(self):
        t = transcript('a.mp4','hello world')
        t.words[0].aligned = False
        self.assertEqual(len(make_cuts(t,0,2,Settings())),1)


class EvaluationTests(unittest.TestCase):
    def test_missing_negation_fails_even_when_most_words_match(self):
        result = compare_text('aap ye kaam nahi kar sakte','aap ye kaam kar sakte',Settings())
        self.assertIn('negation_changed', result['issues'])

    def test_number_change_fails(self):
        result = compare_text('price 3000 rupees hai','price 300 rupees hai',Settings())
        self.assertIn('numbers_changed',result['issues'])

    def test_aliases_allow_spelling_variants(self):
        s = Settings(aliases={'nahin':'nahi','hain':'hai'})
        self.assertEqual(compare_text('ye nahin hain','ye nahi hai',s)['issues'],[])


class XmlTests(unittest.TestCase):
    def test_vertical_reel_canvas_fits_a_wide_video_without_cropping(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wide.mp4'; p.touch()
            media=Media('m',str(p),10,'30',1920,1080,1,48000)
            out=Path(d)/'vertical.xml'
            export_xml(out,[Cut('m',0,30,0)],{'m':media},output_format='instagram_vertical')
            root=ET.parse(out).getroot()
            sample=root.find('.//sequence/media/video/format/samplecharacteristics')
            self.assertEqual(sample.findtext('width'),'1080')
            self.assertEqual(sample.findtext('height'),'1920')
            self.assertEqual([node.text for node in root.findall('.//clipitem/filter/effect/parameter/value')],['56.25'])

    def test_xml_links_stereo_audio_and_escapes_paths(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'raw & clip.mp4'
            p.touch()
            media = Media('m',str(p),10,'30000/1001',1920,1080,2,48000)
            out = Path(d)/'timeline.xml'
            export_xml(out,[Cut('m',3,33,0),Cut('m',60,90,1)],{'m':media})
            root = ET.parse(out).getroot()
            self.assertEqual(root.tag,'xmeml')
            self.assertEqual(root.findtext('.//sequence/duration'),'60')
            self.assertEqual(root.findtext('.//rate/ntsc'),'TRUE')
            video = root.findall('.//sequence/media/video/track/clipitem')
            audio = root.findall('.//sequence/media/audio/track/clipitem')
            self.assertEqual(len(video),2)
            self.assertEqual(len(audio),4)
            self.assertEqual([v.findtext('start') for v in video],['0','30'])
            self.assertEqual(len(video[0].findall('link')),3)
            pathurl=root.findtext('.//pathurl')
            self.assertTrue(pathurl.startswith('file://localhost/'))
            self.assertIn('%26',pathurl)

    def test_mixed_rates_rejected(self):
        a=Media('a','a.mp4',10,'25',1920,1080,1,48000)
        b=Media('b','b.mp4',10,'30',1920,1080,1,48000)
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            export_xml(Path(d)/'x.xml',[Cut('a',0,10,0),Cut('b',0,10,1)],{'a':a,'b':b})


if __name__ == '__main__':
    unittest.main()
