"""Replacement-reference regressions; the former layout has a separate fixture."""
import unittest
import numpy as np
from hinglish_captions.caption_two import composition,profile,reference_cues,render,page_ranges,motion_state,group_scale
from hinglish_captions import scene_capture

class CaptionTwoReframeTests(unittest.TestCase):
    def test_reference_groups_keep_all_words_and_onsets(self):
        for recipe,cue in zip(profile()['recipes'],reference_cues()):
            words=cue.text.split();plan=composition(words)
            self.assertEqual(page_ranges(words),[(0,len(words))])
            self.assertEqual(sorted(i for row in plan['rows'] for i in row['words']),list(range(len(words))))
            self.assertEqual([w.start for w in cue.words],[n/30 for n in recipe['starts']])
        self.assertEqual([r.get('align') for r in composition(reference_cues()[0].text.split())['rows']],['top_left',None,'top_right','bottom'])
        self.assertFalse(any(row['role']=='card' for recipe in profile()['recipes'] for row in recipe['rows']))
        self.assertIn('what to say?',[q.text for q in reference_cues()])
        self.assertIn('how it turn to revenue?',[q.text for q in reference_cues()])

    def test_shadow_and_glow_survive_as_independent_decorations(self):
        from hinglish_captions.caption_two import decorations_only
        cue=reference_cues()[0]
        with scene_capture.capture(),decorations_only():
            effects=render(360,640,cue,1.5)
            self.assertEqual(scene_capture.words(effects),[])
        self.assertIsNotNone(effects.getbbox())
        a=np.asarray(effects);self.assertGreater(int(((a[:,:,3]>0)&(a[:,:,3]<100)).sum()),200)

    def test_cursor_removed_at_owners_request(self):
        self.assertEqual(profile()['cursor']['times'],[])
        self.assertFalse(any(r.get('plane') for r in profile()['recipes']))
        # This was the settled cursor's location underneath Understand.
        a=np.asarray(render(360,640,reference_cues()[1],3.05))[390:445,45:135]
        self.assertEqual(int(((a[:,:,1]>200)&(a[:,:,2]<150)&(a[:,:,3]>100)).sum()),0)

    def test_measured_source_lime_ink_bounds(self):
        a=np.asarray(render(720,1280,reference_cues()[0],1.5));m=(a[:,:,0]>170)&(a[:,:,1]>220)&(a[:,:,2]<150)&(a[:,:,3]>220);y,x=np.where(m)
        for actual,expected in zip((x.min(),y.min(),x.max()+1,y.max()+1),(113,656,607,752)):
            self.assertLessEqual(abs(int(actual)-expected),4)

    def test_predefined_main_color_remains_editable(self):
        with scene_capture.capture():
            image=render(360,640,reference_cues()[0],1.5,word_colors=[None,None,'#1677FF',None,None,None,None]);rows=scene_capture.words(image)
        main=next(r for r in rows if r['index']==2)
        self.assertEqual(main['text'],'Prospects');self.assertEqual(main['color'],'#1677FF')
        self.assertEqual({r['index'] for r in rows},set(range(7)))

    def test_word_reveal_and_group_camera(self):
        cue=reference_cues()[0]
        self.assertIsNone(render(240,426,cue,0).getbbox());self.assertIsNotNone(render(240,426,cue,.2).getbbox())
        self.assertIsNone(render(240,426,cue,cue.end).getbbox())
        self.assertLess(motion_state(.06)[0],motion_state(.16)[0]);self.assertGreater(motion_state(.06)[2],motion_state(.23)[2])
        scales=[group_scale(composition(cue.text.split()),t) for t in (0,.2,.5,1)]
        self.assertTrue(all(a>=b for a,b in zip(scales,scales[1:])));self.assertEqual(scales[-1],1)

    def test_all_reference_layouts_render_in_both_orientations(self):
        for width,height in ((360,640),(640,360)):
            for cue in reference_cues():
                image=render(width,height,cue,cue.end-.02)
                self.assertIsNotNone(image.getbbox(),cue.text);self.assertEqual(image.size,(width,height))
