import json,tempfile,unittest,wave
from pathlib import Path
from fractions import Fraction
import numpy as np
import av
from hinglish_cut.model import Media,Cut
from hinglish_cut.xml_export import export_xml
from hinglish_sound.xml_export import export_sound_xml
from hinglish_sound.editors import capcut_spec
from hinglish_app.capcut_adapter import create_project,signature
from defusedxml import ElementTree as ET

class SoundEditorLayers(unittest.TestCase):
    def test_overlaps_dialogue_and_muted_source_survive_both_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'output/sound/test';folder.mkdir(parents=True)
            source=folder/'source.mp4'
            with av.open(str(source),'w') as container:
                stream=container.add_stream('mpeg4',rate=30);stream.width=64;stream.height=96;stream.pix_fmt='yuv420p'
                for _ in range(30):
                    for packet in stream.encode(av.VideoFrame.from_ndarray(np.zeros((96,64,3),np.uint8),format='rgb24')):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            stem=folder/'voice.wav'
            with wave.open(str(stem),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0'*48000*4)
            media=Media('v',str(source),1.,'30',64,96,2,48000)
            timeline=folder/'source-timeline.xml';export_xml(timeline,[Cut('v',0,30,0)],{'v':media})
            stems={'voice':str(stem),'music':str(stem),'effects':[dict(path=str(stem),start=.125,length=.5,category='poke',role='contact'),dict(path=str(stem),start=.135,length=.4,category='cute',role='detail')]}
            xml=export_sound_xml(timeline,Fraction(30),stems,folder/'SOUND_SEQUENCE.xml')
            sequence=ET.parse(xml).find('.//sequence')
            self.assertEqual(len(sequence.findall('./media/audio/track')),8)
            self.assertEqual(len(sequence.findall('./media/video/track/clipitem')),1)
            plan=folder/'sound-plan.json';plan.write_text(json.dumps(dict(timeline_xml=str(timeline),stems=stems)))
            spec=capcut_spec(plan)
            self.assertTrue(spec['mute_source_audio']);self.assertEqual(len({r['lane'] for r in spec['audio_layers']}),4)
            home=root/'CapCut';(root/'config.editors.local.json').write_text(json.dumps({'capcut_home':str(home)}))
            saved=create_project(root,source,'Sound layers','sound-layer-test',timeline=spec)
            draft=json.loads((Path(saved['folder'])/'draft_content.json').read_text('utf-8'))
            self.assertEqual([t['type'] for t in draft['tracks']],['video','audio','audio','audio','audio'])
            self.assertEqual(draft['tracks'][0]['segments'][0]['volume'],0)
            self.assertEqual(draft['tracks'][3]['segments'][0]['target_timerange']['start'],125000)
            self.assertEqual(draft['tracks'][4]['segments'][0]['target_timerange']['start'],135000)
            self.assertTrue(all(Path(a['path']).is_file() for a in draft['materials']['audios']))
            before=signature(source,timeline=spec)
            with stem.open('ab') as f:f.write(b'changed')
            self.assertNotEqual(signature(source,timeline=spec),before)
