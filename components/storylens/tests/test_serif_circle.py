import unittest
from hinglish_captions.serif_circle import render,sample_cues,pages,decorations_only
from hinglish_captions.project import cues_to_data
from hinglish_captions.editing import apply_timings
from hinglish_captions import scene_capture

class SerifCircleTests(unittest.TestCase):
    def test_every_annotation_uses_an_open_reference_path(self):
        from hinglish_captions.serif_circle import profile,decoration_points
        import math
        for recipe in profile()['recipes']:
            for spec in recipe.get('decorations',[]):
                self.assertIn('path',spec,recipe['text'])
                points=decoration_points(spec,1)
                self.assertGreater(math.dist(points[0],points[-1]),20,recipe['text'])
                self.assertNotEqual(decoration_points(spec,.3),points)

    def test_frozen_source_wins_over_another_demo_and_keeps_inline_rows(self):
        from hinglish_captions.core import CaptionCue,CaptionWord
        from hinglish_captions.template_patterns import pattern_context
        from hinglish_captions.serif_circle import recipe_for,row_bounds
        words='Your audience needs more.'.split()
        cue=CaptionCue(tuple(CaptionWord(w,i*.5,(i+1)*.5) for i,w in enumerate(words)),0,2,'middle and bottom funnel.',16)
        with pattern_context(cue):result=recipe_for(words)
        self.assertEqual(result['template_pattern'],cue.template_source)
        self.assertEqual(result['rows'][0]['band'],result['rows'][1]['band'])
        left,right=[row_bounds(row,words) for row in result['rows'][:2]]
        self.assertGreaterEqual(right[0]-left[2],7.8)
        self.assertEqual(result['decorations'][0]['color'],'#21E890')

    def test_new_scripts_select_source_patterns_instead_of_plain_demo_fallbacks(self):
        from hinglish_captions.core import CaptionCue,CaptionWord
        from hinglish_captions.template_patterns import pattern_context
        from hinglish_captions.serif_circle import recipe_for,profile
        known={r['text'] for r in profile()['recipes'] if r.get('reference_pattern')}
        for slot in range(24):
            words='Nayi kahani aage badhe'.split()
            cue=CaptionCue(tuple(CaptionWord(w,i*.5,(i+1)*.5) for i,w in enumerate(words)),0,2,'New original script here',slot)
            with pattern_context(cue):result=recipe_for(words)
            self.assertIn(result['template_pattern'],known)
            self.assertAlmostEqual((result['bounds'][0]+result['bounds'][2])/2,360)
            self.assertAlmostEqual((result['bounds'][1]+result['bounds'][3])/2,0)

    def test_revealing_later_words_never_moves_settled_words(self):
        from hinglish_captions.core import CaptionCue,CaptionWord
        words='Your next story matters'.split()
        cue=CaptionCue(tuple(CaptionWord(w,i*.6,(i+1)*.6) for i,w in enumerate(words)),0,2.4,'Why one single post',12)
        with scene_capture.capture():
            early=scene_capture.words(render(720,1280,cue,.55))
            late=scene_capture.words(render(720,1280,cue,2.35))
        old=next(r for r in early if r['index']==0);new=next(r for r in late if r['index']==0)
        self.assertEqual((old['x'],old['y'],old['size_px']),(new['x'],new['y'],new['size_px']))

    def test_underline_height_does_not_stretch_with_longer_script(self):
        from hinglish_captions.core import CaptionCue,CaptionWord
        from hinglish_captions.template_patterns import pattern_context
        from hinglish_captions.serif_circle import recipe_for,decoration_points
        heights=[]
        for text in ('Your audience needs more.','Extraordinary experiences create opportunities'):
            words=text.split();cue=CaptionCue(tuple(CaptionWord(w,i*.5,(i+1)*.5) for i,w in enumerate(words)),0,2,'Your audience needs more.',14)
            with pattern_context(cue):recipe=recipe_for(words)
            points=decoration_points(recipe['decorations'][0],1)
            heights.append(max(y for x,y in points)-min(y for x,y in points))
        self.assertAlmostEqual(*heights)

    def test_short_and_long_replacements_keep_fonts_pattern_and_all_words_after_save(self):
        from hinglish_captions.core import retime_cue_text
        from hinglish_captions.project import cues_from_data
        from hinglish_captions.template_patterns import pattern_context,bind_patterns
        from hinglish_captions.serif_circle import recipe_for
        original=next(c for c in sample_cues() if c.text=='Why one single post')
        for count in (1,2,3,6,19,101):
            text=' '.join(('kahani' if i%2 else 'story') for i in range(count))
            edited=retime_cue_text(original,text)
            reopened=cues_from_data(cues_to_data([edited]))[0]
            self.assertEqual(reopened.template_source,original.text)
            chunks=pages(reopened,360,640)
            self.assertEqual(' '.join(p.text for _,p in chunks),text)
            for _,page in chunks:
                with pattern_context(page):result=recipe_for([w.text for w in page.words])
                self.assertEqual(result.get('template_pattern',result['text']),original.text)
                self.assertTrue(any(row.get('face')=='serif' for row in result['rows']))
            rebound=bind_patterns([p for _,p in chunks],[reopened])
            self.assertTrue(all(q.template_source==original.text for q in rebound))

    def test_replacement_cut_words_share_one_ink_center(self):
        from hinglish_captions.core import CaptionCue,CaptionWord
        words='New script keeps rhythm'.split()
        cue=CaptionCue(tuple(CaptionWord(w,i*.5,(i+1)*.5) for i,w in enumerate(words)),0,2,'insta flopado',4)
        centers=[]
        for i in range(4):
            with scene_capture.capture():captured=scene_capture.words(render(720,1280,cue,i*.5+.25))
            self.assertEqual(len(captured),1)
            centers.append(captured[0]['x'])
        self.assertLess(max(centers)-min(centers),1)

    def test_project_save_keeps_the_original_pattern_and_owner_position(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from hinglish_captions.project import rebuild_project,cues_from_data
        from hinglish_captions.template_patterns import pattern_context
        from hinglish_captions.serif_circle import recipe_for
        original=next(c for c in sample_cues() if c.text=='Why one single post')
        data={'media':{'id':'serif-test','path':'silent.mp4','duration':60,'fps':'30','width':360,'height':640,'channels':2,'sample_rate':48000},
              'source_relative':'silent.mp4','style':'serif_circle_draft','script_preview':True,'cues':cues_to_data([original])}
        workspace=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=workspace/'tmp',prefix='serif-circle-save-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(workspace.resolve()))
            path=Path(folder)/'caption-project.json';path.write_text(json.dumps(data),'utf8')
            with patch('hinglish_captions.project.write_report'),patch('hinglish_captions.project.render_overlay'):
                rebuild_project(path,{'save_project_only':True,'texts':['Nayi kahani apne andaaz mein aaj sabko sunao'],'size':1.15,'cue_layouts':[{'x':.43,'y':.58,'size':1.15}]})
            saved=json.loads(path.read_text('utf8'));reopened=cues_from_data(saved['cues'])[0]
            self.assertTrue(saved['script_preview'])
            self.assertEqual(saved['cue_layouts'][0],{'x':.43,'y':.58,'size':1.15})
            self.assertEqual(reopened.template_source,original.text)
            with pattern_context(reopened):result=recipe_for([w.text for w in reopened.words])
            self.assertEqual(result['template_pattern'],original.text)

    def test_new_english_and_hinglish_text_keep_format_limits(self):
        from hinglish_captions.core import CaptionCue,CaptionWord
        for text in ('Your next story deserves a beautiful beginning','Har nayi kahani ko ek naya mauka'):
            words=text.split();cue=CaptionCue(tuple(CaptionWord(w,i*.4,(i+1)*.4) for i,w in enumerate(words)),0,len(words)*.4)
            for w,h in ((360,640),(640,360)):
                for _,page in pages(cue,w,h):
                    self.assertLessEqual(len(page.words),4 if h>=w else 7)
                    box=render(w,h,cue,page.end-.01).getbbox()
                    self.assertTrue(box)
                    self.assertGreater(box[0],0)
                    self.assertLess(box[2],w)

    def test_reference_timings_survive_editor_save(self):
        cues=sample_cues()
        self.assertEqual(apply_timings(cues,cues_to_data(cues),cues[-1].end),cues)

    def test_all_reference_pages_fit_and_retain_every_word(self):
        for w,h in ((360,640),(640,360)):
            for cue in sample_cues():
                chunks=pages(cue,w,h)
                self.assertEqual([word for _,page in chunks for word in page.words],list(cue.words))
                for _,page in chunks:
                    self.assertLessEqual(len(page.words),4 if h>=w else 7)
                    for t in (page.start+.01,(page.start+page.end)/2,page.end-.001):
                        box=render(w,h,cue,t).getbbox()
                        if box:
                            self.assertGreater(box[0],0,(cue.text,t,box))
                            self.assertLess(box[2],w,(cue.text,t,box))
                            self.assertGreater(box[1],0,(cue.text,t,box))
                            self.assertLess(box[3],h,(cue.text,t,box))

    def test_native_word_color_override_and_separate_annotation(self):
        cue=next(c for c in sample_cues() if c.text=='Why one single post')
        final=cue.end-.02
        with scene_capture.capture():
            rows=scene_capture.words(render(720,1280,cue,final,colors=[None,None,'#FF0000',None]))
        self.assertEqual([r['text'] for r in rows],['Why','one','single','post'])
        self.assertEqual(rows[2]['color'],'#FF0000')
        with decorations_only():
            early=render(360,640,cue,cue.words[2].start+.01);late=render(360,640,cue,final)
        self.assertTrue(late.getbbox())
        self.assertNotEqual(early.tobytes(),late.tobytes())

if __name__=='__main__':unittest.main()
