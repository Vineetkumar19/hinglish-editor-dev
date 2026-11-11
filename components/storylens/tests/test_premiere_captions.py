"""Codec regressions against Source Text serialized by Premiere 2026."""
from pathlib import Path
import struct
import unittest
import gzip
import tempfile
import xml.etree.ElementTree as ET

from hinglish_app.premiere_captions import _text_data, export


class PremiereCaptionCodecTests(unittest.TestCase):
    def test_sequence_and_graphic_rates_follow_source_in_native_fields(self):
        from fractions import Fraction
        from hinglish_app.premiere_captions import TICKS
        root = Path(__file__).resolve().parents[1]
        for fps, display in ((30,104),('30000/1001',103),(25,101),(60,108)):
            with self.subTest(fps=fps), tempfile.TemporaryDirectory() as folder:
                project={'width':720,'height':1280,'style':'caption_1',
                    'media':{'path':str(Path(__file__).resolve()),'duration':2,'fps':fps}}
                output=Path(folder)/'rate.prproj'
                export(root/'hinglish_app/templates/premiere-caption-1.xml',
                       project,output,scene_rows=[])
                tree=ET.fromstring(gzip.decompress(output.read_bytes()))
                ticks=round(Fraction(TICKS)/Fraction(str(fps)))
                for tag in ('VideoTrackGroup','DataTrackGroup'):
                    group=tree.find(tag)
                    self.assertEqual(int(group.findtext('TrackGroup/FrameRate')),ticks)
                    self.assertIsNone(group.find('FrameRate'), 'Premiere ignores this sibling')
                seq=tree.find('Sequence')
                self.assertEqual(int(seq.findtext('Node/Properties/MZ.Sequence.VideoTimeDisplayFormat')),display)
                self.assertEqual(int(tree.find("VideoStream[@ObjectID='1168']").findtext('FrameRate')),ticks)

    def test_caption_one_adobe_faces_keep_exact_design_glyphs(self):
        from PIL import Image,ImageDraw,ImageFont
        from hinglish_app.premiere_captions import font_name,editor_font_path
        folder=Path(__file__).resolve().parents[1]/'hinglish_captions/fonts'
        for style in ('Bold','Medium'):
            original=folder/f'Inter-{style}.otf'
            self.assertEqual(font_name(original),'StorylensCaptionOne-'+style)
            def pixels(path):
                image=Image.new('L',(1200,200));font=ImageFont.truetype(str(path),96)
                ImageDraw.Draw(image).text((0,0),'MONUMENT Taj Mahal 123',font=font,fill=255)
                return image.tobytes(),font.getmetrics(),font.getlength('MONUMENT Taj Mahal 123')
            self.assertEqual(pixels(original),pixels(editor_font_path(original)))

    def test_shadow_is_explicit_and_matches_premiere_saved_toggle(self):
        root = Path(__file__).resolve().parents[1]
        def shadow(data):
            u=lambda p: struct.unpack_from('<I',data,p)[0]
            def field(t,i):
                v=t-struct.unpack_from('<i',data,t)[0]
                o=struct.unpack_from('<H',data,v+4+i*2)[0]
                return t+o if o else None
            r=12+u(12);p=field(r,0);d=p+u(p);p=field(d,11)
            return bool(data[p]) if p else False
        for state in (False,True):
            native=(root/f'tests/fixtures/premiere-shadow-{"on" if state else "off"}.bin').read_bytes()
            self.assertEqual(shadow(native),state)
            row={'text':'Changes','font_path':'Inter-Bold.otf','size_px':108,
                 'tracking':0,'color':'#62655F','shadow':state}
            data=_text_data((root/'hinglish_app/templates/premiere-source-text.bin').read_bytes(),row)
            self.assertEqual(shadow(data),state)

    def test_native_word_and_font_references_survive_long_unicode_text(self):
        original = (Path(__file__).parent / 'fixtures/premiere-caption-source-text.bin').read_bytes()
        row = {'text': 'Championship—विजय', 'font_path': 'Inter-Bold.otf',
               'size_px': 120, 'tracking': -.08125, 'box_width': 1080}
        data = _text_data(original, row)
        u = lambda p: struct.unpack_from('<I', data, p)[0]
        def field(table, index):
            vt = table - struct.unpack_from('<i', data, table)[0]
            return table + struct.unpack_from('<H', data, vt + 4 + index * 2)[0]
        def target(p):
            return p + u(p)
        def string(p):
            p = target(p)
            return data[p+4:p+4+u(p)].decode('utf-8')
        document = target(field(target(12), 0))
        fonts = target(field(document, 1))
        runs = target(field(document, 0))
        run = target(runs + 4)
        style = target(field(run, 1))
        self.assertEqual(string(fonts + 4), 'Inter-Bold')
        self.assertEqual(string(field(run, 0)), row['text'])
        self.assertEqual(struct.unpack_from('<f', data, field(style, 1))[0], 120)
        self.assertEqual(struct.unpack_from('<f', data, field(style, 8))[0], -81.25)
        self.assertEqual(struct.unpack_from('<f', data, field(document, 2))[0], 1080)
        self.assertEqual(u(0), len(data) - 12)
        self.assertEqual(len(data) % 4, 0)
        self.assertEqual(original, (Path(__file__).parent / 'fixtures/premiere-caption-source-text.bin').read_bytes())

    def test_descender_words_share_the_native_row_baseline(self):
        project = {'width': 1080, 'height': 1920, 'style': 'caption_1',
            'font': 'template', 'word_visibility': 'phrase',
            'media': {'path': str(Path(__file__).resolve()), 'duration': 2, 'fps': 60},
            'cues': [{'start': .1, 'end': 1.9, 'words': [
                {'text': 'The', 'start': .1, 'end': .4},
                {'text': 'Taj', 'start': .4, 'end': .7},
                {'text': 'Mahal', 'start': .7, 'end': 1.9}]}]}
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'captions.prproj'
            export(root / 'hinglish_app/templates/premiere-caption-1.xml', project, output)
            tree = ET.fromstring(gzip.decompress(output.read_bytes()))
            # The graphic SOURCE canvas must also match the 1080p sequence.
            # Updating only the sequence clipped long support lines in Premiere.
            graphic=tree.find("VideoStream[@ObjectID='1168']")
            self.assertEqual(graphic.findtext('FrameRect'),'0,0,1080,1920')
        ids = {n.get('ObjectID'): n for n in tree if n.get('ObjectID')}
        positions = {}
        for node in tree:
            if node.tag != 'VideoClipTrackItem' or node.get('ObjectID') in ('238', '251'):
                continue
            self.assertIsNone(node.find('ClipTrackItem/TrackItem/TrackIndex'))
            sub = ids[node.find('ClipTrackItem/SubClip').get('ObjectRef')]
            chain = ids[node.find('ClipTrackItem/ComponentOwner/Components').get('ObjectRef')]
            component = ids[chain.find('ComponentChain/Components/Component').get('ObjectRef')]
            params = [ids[p.get('ObjectRef')] for p in component.findall('Component/Params/Param')]
            position = next(p for p in params if p.findtext('Name') == 'Position')
            keys = position.findtext('Keyframes').strip(';').split(';')
            times = [int(k.split(',')[0]) for k in keys]
            self.assertEqual(times, sorted(set(times)))
            positions[sub.findtext('Name')] = float(keys[-1].split(',')[1].split(':')[1])
        # An ink-height based anchor makes Taj lower just because j descends.
        self.assertAlmostEqual(positions['The'], positions['Taj'], places=10)

    def test_native_gradient_preserves_all_three_saved_color_stops(self):
        original=(Path(__file__).resolve().parents[1]/'hinglish_app/templates/premiere-source-text.bin').read_bytes()
        row={'text':'MARBLE','font_path':'Inter-Bold.otf','size_px':120,'tracking':-.08125,
             'color':'#42C2F5','gradient':[[0,'#42C2F5'],[.22,'#57CFFF'],[1,'#0C8DFF']]}
        data=_text_data(original,row)
        u=lambda p:struct.unpack_from('<I',data,p)[0]
        def target(p):return p+u(p)
        def field(table,index):
            vt=table-struct.unpack_from('<i',data,table)[0]
            return table+struct.unpack_from('<H',data,vt+4+index*2)[0]
        doc=target(field(target(12),0));runs=target(field(doc,0));style=target(field(target(runs+4),1))
        self.assertEqual(u(field(style,20)),1)
        stops=target(field(target(field(style,21)),1))
        for i,(_,color) in enumerate(row['gradient']):
            rgb=target(field(target(stops+4+i*4),0))
            actual=bytes(data[field(rgb,j)] for j in range(3))
            self.assertEqual(actual,bytes.fromhex(color[1:]))

    def test_native_hollow_word_has_real_stroke_and_disabled_fill(self):
        original=(Path(__file__).resolve().parents[1]/'hinglish_app/templates/premiere-source-text.bin').read_bytes()
        row={'text':'HERO','font_path':'Inter-Bold.otf','size_px':120,'tracking':0,
             'color':'#F04444','outline':True,'stroke_width':3}
        data=_text_data(original,row);u=lambda p:struct.unpack_from('<I',data,p)[0]
        def target(p):return p+u(p)
        def field(t,i):
            v=t-struct.unpack_from('<i',data,t)[0]
            return t+struct.unpack_from('<H',data,v+4+i*2)[0]
        doc=target(field(target(12),0));runs=target(field(doc,0));style=target(field(target(runs+4),1))
        self.assertEqual(data[field(style,3)],0)
        self.assertEqual(data[field(style,5)],1)
        self.assertEqual(struct.unpack_from('<f',data,field(style,6))[0],3)

    def test_focus_animation_is_a_native_animated_blur_effect(self):
        from unittest.mock import patch
        root=Path(__file__).resolve().parents[1]
        row={'text':'Focus','font_path':str(root/'hinglish_captions/fonts/Inter-Bold.otf'),
            'size_px':80,'tracking':0,'color':'#FFFFFF','start':0,'end':1.5,'slot':0,
            'animation':[{'time':0,'x':540,'y':1000,'alpha':0,'blur':8},
                         {'time':.5,'x':540,'y':1000,'alpha':1,'blur':0}]}
        project={'width':1080,'height':1920,'style':'typography_3',
            'media':{'path':str(Path(__file__).resolve()),'duration':1.5,'fps':'30000/1001'}}
        with tempfile.TemporaryDirectory() as folder,patch('hinglish_app.caption_scene.build',return_value=[row]):
            path=Path(folder)/'focus.prproj'
            export(root/'hinglish_app/templates/premiere-caption-1.xml',project,path)
            tree=ET.fromstring(gzip.decompress(path.read_bytes()))
        blur=next(n for n in tree if n.findtext('Name')=='Blurriness')
        self.assertEqual(blur.findtext('IsTimeVarying'),'true')
        values=[float(k.split(',')[1]) for k in blur.findtext('Keyframes').strip(';').split(';')]
        self.assertGreater(values[0],0);self.assertEqual(values[-1],0)
        self.assertTrue(any(n.findtext('MatchName')=='AE.ADBE Gaussian Blur 2' for n in tree))
