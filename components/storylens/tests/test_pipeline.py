import json
import tempfile
import unittest
from pathlib import Path
from hinglish_cut.backends import bounded_windows, parse_judgment
from hinglish_cut.pipeline import finish_project, select_video_input
from hinglish_cut.demo import create_demo_media
from hinglish_cut.media import probe, extract_audio
from hinglish_cut.model import Transcript, Word, Settings


class PipelineTests(unittest.TestCase):
    def test_vertical_folder_selects_the_reel_output_format(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            folder=root/'input'/'instagram-vertical'
            folder.mkdir(parents=True)
            (folder/'take.mp4').touch()
            paths,output_format=select_video_input(root)
            self.assertEqual(paths,[folder/'take.mp4'])
            self.assertEqual(output_format,'instagram_vertical')

    def test_no_match_still_produces_review_report_without_empty_xml(self):
        with tempfile.TemporaryDirectory() as d:
            result=finish_project(['missing line'],[],{},Path(d),Settings(),lambda p:'',progress=lambda x:None)
            self.assertEqual(result['cut_count'],0)
            self.assertEqual(result['status'],'REVIEW_REQUIRED')
            self.assertFalse((Path(d)/'draft.xml').exists())
            self.assertTrue((Path(d)/'report.html').exists())

    def test_invalid_judge_result_does_not_pass(self):
        for text in ('{}','{"intent_preserved":"true","entity_preservation":1,"reason":"ok"}',
                     '{"intent_preserved":true,"entity_preservation":NaN,"reason":"ok"}'):
            with self.assertRaises(ValueError): parse_judgment(text)

    def test_valid_judge_result(self):
        self.assertTrue(parse_judgment('{"intent_preserved":true,"entity_preservation":1,"reason":"same meaning"}')['intent_preserved'])

    def test_speech_windows_bounded_and_nonoverlapping(self):
        windows=bounded_windows([(0,70)],70,25)
        self.assertTrue(all(0<b-a<=25 for a,b,_ in windows))
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(windows,windows[1:])))

    def test_short_phrase_pauses_preserve_asr_context(self):
        speech=[(1.6,2.7),(3.1,4.9)]
        original=list(speech)
        windows=bounded_windows(speech,6,25)
        self.assertEqual(len(windows),1)
        self.assertAlmostEqual(windows[0][0],1.42)
        self.assertAlmostEqual(windows[0][1],5.08)
        self.assertEqual(speech,original)

    def test_context_does_not_bridge_long_silence(self):
        self.assertEqual(len(bounded_windows([(1,2),(6,7)],10,25)),2)

    def test_context_cannot_exceed_maximum_or_overlap_at_split(self):
        windows=bounded_windows([(0,24.8),(25.3,50.5),(51,52)],53,25)
        # Decimal timestamps can differ by a few binary floating-point bits;
        # one nanosecond is well below the audio's sample resolution.
        self.assertTrue(all(0<b-a<=25+1e-9 for a,b,_ in windows))
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(windows,windows[1:])))

    def test_draft_reports_missing_line_and_no_semantic_judge(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); create_demo_media(p/'raw.mp4',3)
            m=probe(p/'raw.mp4'); extract_audio(m,p/'raw.wav')
            transcript=Transcript(m,[Word(w,.3+i*.4,.6+i*.4,.99) for i,w in enumerate('aaj hum editing seekhenge'.split())],[(.3,1.8)],[])
            report=finish_project(['aaj hum editing seekhenge','quantum physics explained'],[transcript],
                {m.id:p/'raw.wav'},p/'out',Settings(),lambda wav:'aaj hum editing seekhenge',progress=lambda x:None)
            self.assertEqual(report['status'],'REVIEW_REQUIRED')
            self.assertTrue((p/'out'/'draft.xml').exists())
            self.assertFalse((p/'out'/'timeline.xml').exists())
            self.assertIn('missing_script_line',report['lines'][1]['issues'])
            self.assertIn('semantic_not_checked',report['lines'][0]['issues'])
            self.assertIn('quantum physics explained',(p/'out'/'report.html').read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
