import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import ImageDraw

from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.kinetic import composition, profile, highlight_color
from hinglish_captions.renderer import draw_caption, draw_editor_caption, render_overlay
from hinglish_captions.styles import SELECTABLE_TEMPLATES

ROOT = Path(__file__).resolve().parents[1]


class KineticCaptionTests(unittest.TestCase):
    def cue(self, words='Punjab ko IPL ki sabse'):
        return CaptionCue(tuple(CaptionWord(w, i*.25, i*.25+.18)
                                for i,w in enumerate(words.split())), 0, 1.6)

    def test_reference_composition_and_default_hold_are_selectable(self):
        chosen = SELECTABLE_TEMPLATES['kinetic_documentary']
        self.assertEqual(chosen['word_visibility'], 'phrase')
        self.assertEqual(chosen['font'], 'impact.ttf')
        self.assertEqual(composition('Punjab ko IPL ki sabse'.split())['hero'], [[4]])
        self.assertEqual(composition('kharaab team bola jae to'.split())['effect'], 'plain')
        self.assertEqual(composition('hai team to'.split())['hero'], [[1]])

    def test_every_recipe_has_one_hero_and_preserves_all_supporting_words(self):
        examples=[row['text'] for row in profile()['phrases']]+['world remembers','same same same','hello']
        for text in examples:
            words=text.split();plan=composition(words)
            with self.subTest(text=text):
                self.assertEqual(sum(map(len,plan['hero'])),1)
                self.assertEqual(plan['top']+plan['hero'][0]+plan['bottom'],list(range(len(words))))

    def test_reference_outline_echo_and_handwriting_are_distinct_and_kept(self):
        self.assertEqual(composition('Kolkatta se badla lene ke'.split())['effect'],'outline')
        self.assertEqual(composition('nahin paati hai aur tis'.split())['effect'],'echo')
        self.assertEqual(composition('Saha aur apne team ko'.split())['handwriting'],[0,1])
        original=ImageDraw.ImageDraw.text;baselines={}
        def record(draw,xy,text,*args,**kwargs):
            if text in ('Saha','aur'):baselines[text]=xy[1]
            return original(draw,xy,text,*args,**kwargs)
        with patch.object(ImageDraw.ImageDraw,'text',record):
            draw_caption(720,1280,self.cue('Saha aur apne team ko'),1.35,'kinetic_documentary',position=.86)
        self.assertEqual(baselines['Saha'],baselines['aur'])

    def test_letter_positions_remain_fixed_during_reveals(self):
        import numpy as np
        cue=self.cue('kharaab team bola jae to')
        positions=[];original=ImageDraw.ImageDraw.text
        for t in (.05,.1,.2):
            painted=[]
            def record(draw,xy,text,*args,**kwargs):
                if text=='KHARAAB':painted.append(xy)
                return original(draw,xy,text,*args,**kwargs)
            with patch.object(ImageDraw.ImageDraw,'text',record):
                draw_caption(360,640,cue,t,'kinetic_documentary')
            positions.append(painted)
        self.assertEqual(positions[0],positions[1]);self.assertEqual(positions[1],positions[2])
        # The requested group zoom settles after 2.1 seconds; words then hold.
        cue=CaptionCue(cue.words,0,3)
        frames=[np.asarray(draw_caption(360,640,cue,t,'kinetic_documentary')) for t in (2.2,2.3,2.5)]
        self.assertTrue(all(np.array_equal(frames[0],frame) for frame in frames[1:]))

    def test_default_is_ten_percent_smaller_and_reference_words_are_white(self):
        import numpy as np
        cue=self.cue('kharaab')
        config=profile()
        self.assertEqual(config['default_scale'],.9)
        self.assertEqual(highlight_color(['any','new','script']),'#FFFFFF')
        self.assertNotIn('hero_colors',config)
        small=draw_caption(720,1280,cue,.1,'kinetic_documentary').getbbox()
        with patch('hinglish_captions.kinetic.profile',return_value={**config,'default_scale':1}):
            original=draw_caption(720,1280,cue,.1,'kinetic_documentary').getbbox()
        self.assertAlmostEqual((small[2]-small[0])/(original[2]-original[0]),.9,delta=.025)
        for color in ('#FFFFFF','#F04444','#FFD400','#52C7FF'):
            image=np.asarray(draw_caption(360,640,cue,.3,'kinetic_documentary',word_colors=[color]))
            rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
            self.assertGreater(np.count_nonzero(np.all(image[:,:,:3]==rgb,axis=2)&(image[:,:,3]==255)),100)
        full=draw_editor_caption(360,640,cue,.1,'kinetic_documentary','template',{'x':.5,'y':.5,'size':1},'phrase').getbbox()
        reduced=draw_editor_caption(360,640,cue,.1,'kinetic_documentary','template',{'x':.5,'y':.5,'size':.7},'phrase').getbbox()
        self.assertLess(reduced[2]-reduced[0],(full[2]-full[0])*.75)

    def test_all_three_presets_have_no_colored_background_pixels(self):
        import numpy as np
        for style in ('kinetic_documentary','documentary_outline','documentary_echo'):
            for text in ('kharaab team bola jae to','Phir final vaala din aata','Saha aur apne team ko'):
                image=np.asarray(draw_caption(360,640,self.cue(text),1.35,style))
                opaque=image[:,:,3]>0
                self.assertTrue(opaque.any())
                self.assertTrue(np.all(image[:,:,0][opaque]==image[:,:,1][opaque]))
                self.assertTrue(np.all(image[:,:,1][opaque]==image[:,:,2][opaque]))

    def test_new_reference_presets_override_effect_and_preserve_editing(self):
        import numpy as np
        cue=self.cue('out ka pressure vah jhel')
        images=[]
        for style,effect in (('documentary_outline','outline'),('documentary_echo','echo')):
            self.assertIn(style,SELECTABLE_TEMPLATES)
            self.assertEqual(composition(cue.text.split(),effect)['effect'],effect)
            full=draw_editor_caption(360,640,cue,1.35,style,'template',{'x':.5,'y':.5,'size':1},'phrase')
            smaller=draw_editor_caption(360,640,cue,1.35,style,'template',{'x':.5,'y':.5,'size':.7},'phrase')
            self.assertLess(smaller.getbbox()[2]-smaller.getbbox()[0],full.getbbox()[2]-full.getbbox()[0])
            self.assertIsNone(draw_editor_caption(360,640,cue,.2,style,'template',{'x':.5,'y':.5,'size':1},'styled_spoken').getbbox())
            images.append(np.asarray(full))
        self.assertFalse(np.array_equal(*images))

    def test_no_future_words_and_completed_words_hold_through_silence(self):
        original = ImageDraw.ImageDraw.text
        cue = self.cue()
        for timestamp, expected in ((.1, {'PUNJAB'}), (.22, {'PUNJAB'}),
                                    (.62, {'PUNJAB','KO','IPL'}),
                                    (1.35, {'PUNJAB','KO','IPL','KI','SABSE'})):
            painted=[]
            def record(draw, xy, text, *args, **kwargs):
                if kwargs.get('fill',(0,0,0,0))[-1]>0: painted.append(text)
                return original(draw,xy,text,*args,**kwargs)
            with self.subTest(time=timestamp),patch.object(ImageDraw.ImageDraw,'text',record):
                draw_caption(360,640,cue,timestamp,'kinetic_documentary',position=.84)
            self.assertEqual(set(painted), expected)
        for timestamp in (-.01,cue.end,cue.end+.1):
            self.assertIsNone(draw_caption(360,640,cue,timestamp,'kinetic_documentary',position=.84).getbbox())

    def test_all_formats_fit_and_word_color_and_position_remain_editable(self):
        cue=self.cue('kharaab team bola jae to')
        for width,height in ((360,640),(640,360),(400,400)):
            with self.subTest(size=(width,height)):
                image=draw_caption(width,height,cue,.5,'kinetic_documentary',position=.84,
                                   word_colors=['#F04444',None,None,None,None])
                box=image.getbbox();self.assertIsNotNone(box)
                self.assertGreater(box[0],0);self.assertLess(box[2],width)
                self.assertGreater(box[1],0);self.assertLess(box[3],height)
        image=draw_editor_caption(360,640,cue,.5,'kinetic_documentary','template',
                                  {'x':.4,'y':.5,'size':.8},'phrase')
        self.assertLess(image.getbbox()[3],640*.7)

    @unittest.skipUnless(shutil.which('node'),'Node is needed to compare the actual browser planner')
    def test_browser_and_export_use_the_same_composition_for_new_words(self):
        source=(ROOT/'hinglish_captions/kinetic.js').read_text(encoding='utf-8')
        planner=source[source.index('  const normalize ='):source.index('  const canvas =')]
        examples=[row['text'].split() for row in profile()['phrases']]
        examples += [s.split() for s in ('Imagine a monument that','The Taj Mahal stands beside',
                     'world remembers','yeh ek naya din hai','AI edits at 60fps','same same same','hello')]
        program="const input=JSON.parse(require('fs').readFileSync(0,'utf8'));const config=input.config;"+planner
        program+="console.log(JSON.stringify(input.words.map(words=>[planFor(words),highlightColor(words)])));"
        result=subprocess.run(['node','-e',(Path(__file__).resolve().parents[1]/'hinglish_captions/template_patterns.js').read_text('utf-8')+'\n'+program],input=json.dumps({'config':profile(),'words':examples}),
                              capture_output=True,text=True,encoding='utf-8',check=True)
        self.assertEqual(json.loads(result.stdout),[[composition(words),highlight_color(words)] for words in examples])
        for effect in ('outline','echo'):
            overridden=program.replace('planFor(words),highlightColor(words)',f'planFor(words,"{effect}"),highlightColor(words)')
            result=subprocess.run(['node','-e',(Path(__file__).resolve().parents[1]/'hinglish_captions/template_patterns.js').read_text('utf-8')+'\n'+overridden],input=json.dumps({'config':profile(),'words':examples}),
                                  capture_output=True,text=True,encoding='utf-8',check=True)
            self.assertEqual(json.loads(result.stdout),[[composition(words,effect),highlight_color(words)] for words in examples])
        # Older running sessions can regenerate a report with the original profile.
        legacy={k:v for k,v in profile().items() if k not in ('hero_colors','default_scale')}
        result=subprocess.run(['node','-e',(Path(__file__).resolve().parents[1]/'hinglish_captions/template_patterns.js').read_text('utf-8')+'\n'+program],input=json.dumps({'config':legacy,'words':examples}),
                              capture_output=True,text=True,encoding='utf-8',check=True)
        self.assertEqual(json.loads(result.stdout),[[composition(words),highlight_color(words)] for words in examples])

    def test_actual_movie_keeps_alpha_and_exact_frame_renderer(self):
        import av
        import numpy as np
        temporary_root=ROOT/'tmp/caption-tests'
        temporary_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as folder:
            movie=Path(folder)/'kinetic.mov';cue=self.cue('kharaab team bola jae to')
            render_overlay(movie,[cue],240,426,.5,30,'kinetic_documentary',lambda _:None,position=.84)
            count=0
            with av.open(str(movie)) as stream:
                for i,frame in enumerate(stream.decode(video=0)):
                    expected=draw_caption(240,426,cue,i/30,'kinetic_documentary',position=.84)
                    self.assertTrue(np.array_equal(frame.to_ndarray(format='rgba'),np.asarray(expected)))
                    count+=1
            self.assertEqual(count,15)


if __name__=='__main__': unittest.main()
