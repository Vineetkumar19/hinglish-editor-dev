from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from hinglish_cut.model import Media,Cut
from hinglish_cut.xml_export import export_xml
from hinglish_app.timeline_cut import validate,remap
from hinglish_app.word_captions import words,srt
from hinglish_zoom.xml_apply import Sequence


class TimelineCutTests(unittest.TestCase):
    def audio_level_timeline(self,base,value='1',animated=False):
        source=base/'native-camera.mp4';source.write_bytes(b'camera')
        m=Media('cam',str(source),10,'30',640,360,2,48000)
        xml=base/'premiere.xml';export_xml(xml,[Cut('cam',0,300,0)],{'cam':m})
        tree=ET.parse(xml)
        for clip in tree.findall('.//media/audio/track/clipitem'):
            effect=ET.SubElement(ET.SubElement(clip,'filter'),'effect');ET.SubElement(effect,'effectid').text='audiolevels'
            parameter=ET.SubElement(effect,'parameter');ET.SubElement(parameter,'parameterid').text='level';ET.SubElement(parameter,'value').text=value
            if animated:ET.SubElement(parameter,'keyframe')
        tree.write(xml,encoding='utf-8');return xml

    def test_premiere_default_audio_level_is_not_a_changed_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(validate(self.audio_level_timeline(Path(tmp))).frames,300)

    def test_changed_or_animated_camera_audio_still_requires_review(self):
        for value,animated in [('0.5',False),('1',True)]:
            with self.subTest(value=value,animated=animated),tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):validate(self.audio_level_timeline(Path(tmp),value,animated))

    def test_cuts_map_across_existing_edit_boundary_with_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'camera.mp4';source.write_bytes(b'source')
            m=Media('cam',str(source),20,'30',720,1280,2,48000)
            original=base/'original.xml';export_xml(original,[Cut('cam',30,120,0),Cut('cam',240,390,1)],{'cam':m})
            analysis=base/'analysis.mp4';analysis.write_bytes(b'analysis')
            a=Media('analysis',str(analysis),8,'30',720,1280,2,48000)
            edit=base/'edit.xml';export_xml(edit,[Cut(a.id,60,150,0)],{a.id:a})
            result=base/'mapped.xml';remap(original,analysis,edit,result)
            seq=Sequence(result)
            self.assertEqual([(c.start,c.end,c.source_in) for c in seq.clips],[(0,30,90),(30,90,240)])
            self.assertEqual(seq.frames,90)
            ids={c.get('id') for c in seq.sequence.findall('.//clipitem')}
            for c in seq.sequence.findall('.//clipitem'):
                self.assertTrue(all(link.findtext('linkclipref') in ids for link in c.findall('link')))
            for track in seq.sequence.findall('./media/audio/track'):
                self.assertEqual([(int(c.findtext('start')),int(c.findtext('in'))) for c in track.findall('clipitem')],[(0,90),(30,240)])
            self.assertEqual(Sequence(original).frames,240)

    def test_gaps_stop_instead_of_dropping_timeline_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'cam.mp4';source.write_bytes(b'cam')
            m=Media('cam',str(source),10,'30',720,1280,1,48000)
            xml=base/'timeline.xml';export_xml(xml,[Cut('cam',0,60,0)],{'cam':m})
            xml.write_text(xml.read_text().replace('<start>0</start>','<start>10</start>'))
            with self.assertRaisesRegex(ValueError,'original timeline is kept'):validate(xml)

    def test_word_export_preserves_individual_intervals_and_unicode(self):
        project={'media':{'duration':3},'cues':[{'start':0,'end':3,'words':[
            {'text':'Hello','start':.12,'end':.6},{'text':'नमस्ते','start':1.2,'end':1.7}]}]}
        rows=words(project)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'WORDS.srt';srt(path,rows);text=path.read_text('utf-8-sig')
            self.assertIn('00:00:00,120 --> 00:00:00,600',text)
            self.assertIn('00:00:01,200 --> 00:00:01,700',text)
            self.assertIn('नमस्ते',text);self.assertTrue(text.endswith('\n\n'))
