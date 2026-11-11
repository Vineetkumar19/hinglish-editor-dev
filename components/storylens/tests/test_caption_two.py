import json
from pathlib import Path
import shutil
import subprocess
import unittest

import numpy as np

from hinglish_captions.caption_two import composition,profile,motion_state,group_scale,sample_cues,reference_cues,render,page_ranges,paginate_cue,normalize
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.renderer import draw_editor_caption

ROOT=Path(__file__).resolve().parents[1]


class CaptionTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Preserve the previous approved-layout checks against its saved fixture.
        from unittest.mock import patch
        cls.original_profile=globals()['profile']
        legacy=json.loads((ROOT/'docs/caption-two-before-reframe-2026-10-23.json').read_text('utf-8'))
        globals()['profile']=lambda:legacy
        cls.legacy_patch=patch('hinglish_captions.caption_two.profile',return_value=legacy)
        cls.legacy_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.legacy_patch.stop()
        globals()['profile']=cls.original_profile

    def test_main_and_footer_have_their_own_animation_after_camera_settles(self):
        from hinglish_captions.scene_capture import capture,words
        cue=CaptionCue(tuple(CaptionWord(w,t,t+.5) for w,t in zip(('The','white','marble','glows'),(0,.5,1.5,2.5))),0,4)
        for index,onset in ((2,1.5),(3,2.5)):
            values=[]
            for age in (.1,.6):
                with capture():
                    image=render(360,640,cue,onset+age)
                    row=next(r for r in words(image) if r['index']==index)
                    values.append(row['sx'])
            self.assertGreater(values[0],1.04)
            self.assertAlmostEqual(values[1],1)

    def test_two_word_header_and_single_main_preserve_all_source_words(self):
        for original in sample_cues():
            for a,b in page_ranges([w.text for w in original.words]):
                tokens=[w.text for w in original.words[a:b]]
                plan=composition(tokens)
                main=next(r for r in plan['rows'] if r['role']=='main')
                self.assertEqual(len(main['words']),1)
                if len(tokens)>=3:
                    header=next(r for r in plan['rows'] if r.get('align')=='top_left')
                    self.assertGreaterEqual(len(header['words']),2)
                self.assertEqual(sorted(i for r in plan['rows'] for i in r['words']),list(range(len(tokens))))

    def test_shared_zoom_starts_on_first_word_and_does_not_restart_on_main(self):
        from hinglish_captions.scene_capture import capture,words
        cue=CaptionCue((CaptionWord('The',0,.2),CaptionWord('beautiful',.2,.8),CaptionWord('marble',.8,2)),0,2)
        scales=[]
        for t in (.25,.6,.85,1.2):
            with capture():
                frame=render(360,640,cue,t)
                row=next(r for r in words(frame) if r['index']==0)
                scales.append(row['sx'])
        self.assertGreater(scales[0],scales[1])
        self.assertTrue(all(a>=b for a,b in zip(scales,scales[1:])))
        self.assertAlmostEqual(scales[-1],1)
        self.assertEqual(profile()['line_gap'],6)

    def test_owner_limits_keep_all_words_in_order_and_long_main_has_no_footer(self):
        examples=[r['text'].split() for r in profile()['recipes']+profile()['demo_phrases']]+[
            'One two three four five six seven eight nine ten eleven twelve'.split(),
            'Look at extraordinary architecture in this beautiful place today'.split()]
        for words in examples:
            pages=[words[a:b] for a,b in page_ranges(words)]
            self.assertEqual([w for page in pages for w in page],words)
            for page in pages:
                self.assertLessEqual(len(page),7)
                plan=composition(page)
                main=next(r for r in plan['rows'] if r['role']=='main')
                if any(len(normalize(page[i]))>8 for i in main['words']):
                    self.assertLessEqual(len(plan['rows']),2)
                    self.assertFalse(any(r.get('align')=='bottom' for r in plan['rows']))
                self.assertTrue(all(r.get('align') in ('top_left','bottom') for r in plan['rows'] if r['role']=='support'))

    def test_overflow_starts_at_original_word_time_without_losing_colors_or_words(self):
        words='the balanced gardens and the reflections in the water'.split()
        cue=CaptionCue(tuple(CaptionWord(w,i*.4,(i+1)*.4) for i,w in enumerate(words)),0,4)
        pages=paginate_cue(cue)
        self.assertEqual([p.text for p in pages],['the balanced gardens and the reflections','in the water'])
        self.assertEqual(pages[0].end,pages[1].start)
        self.assertEqual(pages[1].start,cue.words[6].start)
        self.assertEqual([w for p in pages for w in p.words],list(cue.words))

    def test_right_edge_alignment_and_zoom_safe_bounds(self):
        tokens='the balanced gardens and the reflections'.split()
        cue=CaptionCue(tuple(CaptionWord(w,0,2) for w in tokens),0,2)
        colors=['#1677FF']*5+[None]
        for time in (.15,1.5):
            p=np.asarray(render(720,1280,cue,time,word_colors=colors))
            blue=(p[:,:,2]>200)&(p[:,:,0]<80)&(p[:,:,3]>60)
            lime=(p[:,:,1]>200)&(p[:,:,0]>150)&(p[:,:,2]<130)&(p[:,:,3]>60)
            bx=np.where(blue)[1];mx=np.where(lime)[1]
            if time>1:self.assertLess(abs(int(bx.min())-int(mx.min())),8)
            self.assertGreater(min(bx.min(),mx.min()),10)
            self.assertLess(max(bx.max(),mx.max()),710)

    def test_full_narration_is_visible_with_its_original_word_times(self):
        from hinglish_captions.demo import SCRIPT
        timing=json.loads((ROOT/'hinglish_captions/caption_one_taj_words.json').read_text('utf8'))['words']
        cues=sample_cues()
        self.assertEqual(' '.join(q.text for q in cues),SCRIPT)
        self.assertEqual([dict(text=w.text,start=w.start,end=w.end) for q in cues for w in q.words],timing)
        self.assertEqual(sum(len(q.words) for q in cues),65)
        for q in cues:
            plan=composition([w.text for w in q.words])
            self.assertEqual(sorted(i for row in plan['rows'] for i in row['words']),list(range(len(q.words))))
            for w in q.words:self.assertGreater(motion_state(q.end-.001-w.start)[0],0)

    def test_reference_rows_never_omit_or_repeat_words_and_cards_are_replaced(self):
        for recipe in profile()['recipes']:
            self.assertEqual(sorted(i for row in recipe['rows'] for i in row['words']),list(range(len(recipe['text'].split()))))
            self.assertEqual(len(recipe['starts']),len(recipe['text'].split()))
        for recipe in profile()['recipes']+profile()['demo_phrases']:
            self.assertFalse(recipe.get('plane'))
            self.assertNotIn('card',[r['role'] for r in recipe['rows']])
            self.assertEqual(sum(r['role']=='main' for r in recipe['rows']),1)
        self.assertEqual([q.start for q in reference_cues()],[0,50/30,94/30,245/30,305/30,444/30])

    def test_floating_headers_fit_without_overlapping_each_other(self):
        from hinglish_captions.caption_one import font,text_metrics
        from hinglish_captions.renderer import _font_path
        path=_font_path('Inter-Bold.otf')
        for recipe in profile()['recipes']+profile()['demo_phrases']:
            words=recipe['text'].split()
            def width(row):
                main=row['role']=='main';size=row.get('size',recipe.get('main_size',profile()['main_size']) if main else recipe.get('support_size',profile()['support_size']))
                selected=font(path,size);tracking=recipe.get('tracking',profile()['tracking']) if main else profile()['support_tracking']
                texts=[words[i] for i in row['words']]
                if main and texts:texts[0]=texts[0][0].upper()+texts[0][1:]
                return sum(text_metrics(selected.path,selected.size,t,tracking)[0] for t in texts)+size*(.17 if main else .21)*max(0,len(texts)-1)
            left=next((r for r in recipe['rows'] if r.get('align')=='top_left'),None)
            right=next((r for r in recipe['rows'] if r.get('align')=='top_right'),None)
            if left and right:
                main=next(r for r in recipe['rows'] if r['role']=='main');w=width(main)
                self.assertLessEqual(w*recipe.get('header_fraction',.12)+width(left),w*.88-width(right),recipe['text'])

    def test_reveal_starts_on_each_word_and_ends_without_a_late_caption(self):
        cue=CaptionCue((CaptionWord('Monument',1,2),),1,3)
        self.assertIsNone(render(240,426,cue,.99).getbbox())
        self.assertIsNone(render(240,426,cue,1).getbbox())
        self.assertIsNotNone(render(240,426,cue,1.1).getbbox())
        self.assertIsNone(render(240,426,cue,3).getbbox())
        self.assertIsNone(render(240,426,cue,2.2,visibility='styled_spoken').getbbox())

    def test_every_slide_starts_zoomed_and_settles_smaller_without_growing_again(self):
        for plan in profile()['recipes']+profile()['demo_phrases']+[composition(['A','new','story','begins'])]:
            scales=[group_scale(plan,i/60) for i in range(180)]
            self.assertGreater(scales[0],1.2)
            self.assertEqual(scales[60],1)
            self.assertTrue(all(a>=b for a,b in zip(scales,scales[1:])))
        self.assertEqual(motion_state(-1),(0,0,16,7))
        self.assertEqual(motion_state(1,True,True),(1,0,0,0))
        self.assertTrue(all(motion_state(i/30,True,True)[1]>=motion_state((i+1)/30,True,True)[1] for i in range(20)))

    def test_main_text_exports_to_real_pixels_without_warning_cards(self):
        for cue in reference_cues():
            self.assertIsNotNone(render(360,640,cue,cue.end-.02).getbbox(),cue.text)
        card=reference_cues()[4]
        p=np.asarray(render(360,640,card,14.3))
        red=(p[:,:,0]>100)&(p[:,:,0].astype(int)>p[:,:,1].astype(int)*2)&(p[:,:,3]>180)
        self.assertEqual(int(red.sum()),0)

    def test_main_entrance_is_a_fade_with_the_approved_shared_zoom(self):
        self.assertEqual(profile()['motion']['main_entrance'],'rise_pop_settle')
        self.assertEqual(profile()['motion']['text_seconds'],.42)
        self.assertEqual(profile()['motion']['fade_seconds'],.24)
        self.assertEqual(motion_state(.2,True,True)[1],0)
        self.assertEqual(motion_state(.4,True,True)[1],0)

    def test_footer_has_clear_ink_gap_on_every_narrated_slide(self):
        for original in sample_cues():
            q=CaptionCue(tuple(CaptionWord(w.text,0,3) for w in original.words),0,3)
            plan=composition([w.text for w in q.words]);colors=[None]*len(q.words)
            if not any(r.get('align')=='bottom' for r in plan['rows']):continue
            for row in plan['rows']:
                for i in row['words']:
                    if row['role']!='main' and row.get('align')!='bottom':colors[i]='#1677FF'
            pixels=np.asarray(render(720,1280,q,2,word_colors=colors))
            green=(pixels[:,:,1]>240)&(pixels[:,:,0]>180)&(pixels[:,:,2]<120)&(pixels[:,:,3]>220)
            green[780:]=False  # The paper-plane decoration is below the text.
            white=(pixels[:,:,:3].min(axis=2)>240)&(pixels[:,:,3]>220)
            main_y=np.where(green)[0];footer_y=np.where(white)[0]
            self.assertGreater(len(footer_y),0,q.text)
            overlap=main_y.max()-footer_y.min()
            self.assertLess(overlap,-5,q.text)
            self.assertGreater(footer_y.min(),1280*profile()['position']+plan.get('main_offset',0),q.text)
            self.assertLess(overlap,(main_y.max()-main_y.min())*.4,q.text)

    def test_manual_size_position_and_color_remain_editable(self):
        cue=CaptionCue((CaptionWord('Monument',0,.5),),0,2)
        normal=draw_editor_caption(360,640,cue,1,'caption_2','template',{'x':.5,'y':profile()['position'],'size':1},'phrase')
        small=draw_editor_caption(360,640,cue,1,'caption_2','template',{'x':.4,'y':.3,'size':.65},'phrase',['#F04444'])
        self.assertLess(small.getbbox()[2]-small.getbbox()[0],normal.getbbox()[2]-normal.getbbox()[0])
        a=np.asarray(small);self.assertGreater(int(((a[:,:,0]>150)&(a[:,:,1]<100)&(a[:,:,3]>180)).sum()),30)

    @unittest.skipUnless(shutil.which('node'),'Node required for preview/export clock comparison')
    def test_preview_and_export_share_compositions_and_every_native_motion_frame(self):
        source=(ROOT/'hinglish_captions/caption_two.js').read_text('utf8')
        code=source[source.index('  const normalize='):source.index('  const canvas=')]
        examples=[r['text'].split() for r in profile()['recipes']+profile()['demo_phrases']]+[['hello'],[],['A','new','story','begins']]
        states=[[i/60,main,slide] for i in range(-2,110) for main in (False,True) for slide in (False,True)]
        groups=[[recipe,i/30] for recipe in profile()['recipes'] for i in range(-2,90)]
        footers=[[450,[-83,0],[-33,9]],[450,[-83,22],[-33,0]],[230,[-41,-1],[-16,0]]]
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;"+(ROOT/'hinglish_captions/template_patterns.js').read_text('utf-8')+code+"console.log(JSON.stringify({wordScales:input.states.map(a=>wordScale(a[0])),pages:input.examples.map(pageRanges),plans:input.examples.map(planFor),states:input.states.map(a=>motionState(...a)),groups:input.groups.map(([p,t])=>groupScale(p,t)),footers:input.footers.map(a=>footerBaseline(...a))}));"
        result=subprocess.run(['node','-e',script],input=json.dumps(dict(config=profile(),examples=examples,states=states,groups=groups,footers=footers)),capture_output=True,text=True,check=True)
        actual=json.loads(result.stdout)
        from hinglish_captions.caption_two import word_scale
        self.assertTrue(np.allclose(actual['wordScales'],[word_scale(a[0]) for a in states],rtol=0,atol=1e-12))
        self.assertEqual(actual['pages'],[[list(r) for r in page_ranges(w)] for w in examples])
        self.assertEqual(actual['plans'],[composition(w) for w in examples])
        self.assertTrue(np.allclose(actual['states'],[motion_state(*a) for a in states],rtol=0,atol=1e-12))
        self.assertTrue(np.allclose(actual['groups'],[group_scale(*a) for a in groups],rtol=0,atol=1e-12))
        from hinglish_captions.caption_two import footer_baseline
        self.assertTrue(np.allclose(actual['footers'],[footer_baseline(*a) for a in footers],rtol=0,atol=1e-12))


if __name__=='__main__':unittest.main()
