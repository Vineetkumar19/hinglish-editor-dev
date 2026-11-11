"""Editable scene extraction must preserve the real renderer's geometry."""
import unittest
from pathlib import Path
from PIL import Image
from hinglish_captions import scene_capture
from hinglish_captions.project import cues_from_data
from hinglish_captions.renderer import draw_editor_caption
from hinglish_captions.styles import SELECTABLE_TEMPLATES,template
from hinglish_app.caption_scene import build


class CaptionSceneCaptureTests(unittest.TestCase):
    def test_additional_styles_export_settling_zoom_and_editable_words(self):
        for style in ('kinetic_documentary','documentary_outline','typography_3','typography_4'):
            with self.subTest(style=style):
                p=self.project(style);p['media']['duration']=3;p['cues'][0]['end']=3
                for word in p['cues'][0]['words']:word.update(start=.1,end=3)
                rows=build(p)
                self.assertEqual({r['text'].casefold() for r in rows},{'the','taj','mahal'})
                for row in rows:
                    frames=[f for f in row['animation'] if f['alpha']>.95 and f['time']>=.45]
                    self.assertGreater(frames[0]['sx'],1.07)
                    self.assertAlmostEqual(frames[-1]['sx'],1,delta=.02)
                    self.assertTrue(Path(row['font_path']).is_file())

    def test_documentary_echo_zoom_moves_text_and_outline_as_one_group(self):
        p=self.project('documentary_echo')
        p['media']['duration']=3
        p['cues'][0]['end']=3
        for word in p['cues'][0]['words']:
            word['start']=.1
            word['end']=3
        rows=build(p)
        self.assertTrue(any(row['outline'] for row in rows))
        initial=[];settled=[]
        for row in rows:
            frames=[f for f in row['animation'] if f['alpha']>.01]
            first,last=frames[0],frames[-1]
            self.assertGreater(first['sx'],1.15)
            self.assertAlmostEqual(last['sx'],1,places=5)
            self.assertAlmostEqual(first['sx'],first['sy'],places=5)
            initial.append(first['sx']);settled.append(last['sx'])
            scales=[f['sx'] for f in frames]
            self.assertTrue(all(a>=b-1e-6 for a,b in zip(scales,scales[1:])))
        self.assertLess(max(initial)-min(initial),1e-6)

    def project(self,style):
        return {'width':360,'height':640,'media':{'duration':1.3,'fps':'30000/1001'},
          'style':style,'font':'template','word_visibility':'phrase',
          'cues':[{'start':.1,'end':1.25,'words':[
            {'text':'The','start':.1,'end':.3},{'text':'Taj','start':.3,'end':.5},
            {'text':'Mahal','start':.5,'end':1.1}]}]}

    def test_all_selectable_styles_keep_real_fonts_and_every_word(self):
        for style in SELECTABLE_TEMPLATES:
            with self.subTest(style=style):
                rows=build(self.project(style))
                self.assertEqual({r['text'].casefold() for r in rows},{'the','taj','mahal'})
                self.assertTrue(all(Path(r['font_path']).is_file() for r in rows))
                self.assertTrue(all(r['animation'] and 0<=r['start']<r['end']<=1.3 for r in rows))
                self.assertTrue(all(r['design']==style for r in rows))

    def test_capture_does_not_change_preview_pixels_or_later_normal_renders(self):
        for style in SELECTABLE_TEMPLATES:
            with self.subTest(style=style):
                project=self.project(style);cue=cues_from_data(project['cues'])[0]
                placement={'x':.45,'y':template(style).get('default_position',.7),'size':.9}
                def render():return draw_editor_caption(360,640,cue,.81,style,'template',placement,'phrase')
                before=render().tobytes()
                with scene_capture.capture():captured=render()
                self.assertEqual(before,captured.tobytes())
                self.assertEqual(before,render().tobytes())
                if style!='caption_1':self.assertTrue(scene_capture.words(captured))

    def test_spoken_caption_one_uses_word_visibility_and_manual_placement(self):
        project=self.project('caption_1');project['word_visibility']='spoken'
        project['cue_layouts']=[{'x':.3,'y':.6,'size':.8}]
        rows=build(project)
        self.assertEqual(len(rows),3)
        for row in rows:
            self.assertAlmostEqual(row['animation'][-1]['x'],108,delta=1)
            self.assertLess(row['end']-row['start'],.65)


    def test_favorite_styles_scale_and_move_with_saved_layout(self):
        import copy
        for style in ('caption_1','caption_2','caption_3','caption_4','caption_5','typography_5','documentary_echo'):
            p=self.project(style);p['cue_layouts']=[{'x':.5,'y':.5,'size':1}]
            original=build(p)
            p['cue_layouts']=[{'x':.3,'y':.4,'size':.5}]
            small=build(p)
            for a,b in zip(original,small):
                with self.subTest(style=style,word=a['text']):
                    fa,fb=a['animation'][-1],b['animation'][-1]
                    self.assertAlmostEqual(b['size_px']*fb.get('sx',1),a['size_px']*fa.get('sx',1)*.5,delta=2)
                    self.assertAlmostEqual(fb['x'],108+(fa['x']-180)*.5,delta=2)
                    self.assertAlmostEqual(fb['y'],256+(fa['y']-320)*.5,delta=2)
