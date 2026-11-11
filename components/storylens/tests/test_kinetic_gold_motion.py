import unittest
from hinglish_captions.kinetic_gold import decorations_only,render,sample_cues,pages,stripe_points,plan,ink,profile,recipe_for
from hinglish_captions import scene_capture
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.template_patterns import pattern_context

class KineticGoldMotionTests(unittest.TestCase):
    def cue(self,text):
        return next(q for q in sample_cues() if q.text==text)

    def test_confidence_and_shadow_fit_both_orientations_during_motion(self):
        cue=self.cue('Confidence')
        for width,height in [(368,207),(207,368)]:
            for age in [.03,.12,.25,.45,.75,min(1.1,cue.end-cue.start-.01)]:
                box=render(width,height,cue,cue.start+age).getbbox()
                self.assertGreater(box[0],width*.04)
                self.assertLess(box[2],width*.96)

    def test_shadow_is_separate_and_keeps_moving_after_foreground_settles(self):
        cue=self.cue('Clarity')
        with decorations_only():
            first=render(368,207,cue,cue.start+.30)
            last=render(368,207,cue,cue.start+.80)
        self.assertNotEqual(first.tobytes(),last.tobytes())
        self.assertLessEqual(last.getchannel('A').getextrema()[1],46)
        with scene_capture.capture():
            rows=scene_capture.words(render(368,207,cue,cue.start+.80))
        self.assertEqual([r['text'] for r in rows],['Clarity'])
        self.assertAlmostEqual(rows[0]['alpha'],1)

    def test_stripe_reveal_keeps_existing_curve_fixed(self):
        early=stripe_points(.12);late=stripe_points(.48)
        self.assertLess(max(x for x,y in early),max(x for x,y in late))
        self.assertEqual(early[0],late[0])
        self.assertTrue(all(y>=218 for x,y in late))

    def test_portrait_preserves_underlined_hero_without_extra_words(self):
        cue=self.cue('kaam shuru karne ke Baad aati hai')
        self.assertEqual([p.text for _,p in pages(cue,207,368)],[cue.text])
        with decorations_only():
            before=render(207,368,cue,cue.start+.2)
            after=render(207,368,cue,cue.words[4].start+.5)
        self.assertIsNone(before.getbbox())
        self.assertIsNotNone(after.getbbox())

    def test_vertical_inline_caption_and_stripe_are_readable_and_centered(self):
        cue=self.cue('kaam shuru karne ke Baad aati hai');now=cue.end-.05
        image=render(414,736,cue,now)
        with decorations_only():stripe=render(414,736,cue,now)
        box=image.getbbox();line=stripe.getbbox()
        self.assertGreater(box[2]-box[0],414*.70)
        self.assertLess(box[2]-box[0],414*.90)
        self.assertGreater((line[0]+line[2])/2,207)
        self.assertGreater(line[0],box[0])
        self.assertLessEqual(line[2],box[2])
        self.assertGreater(line[2]-line[0],(box[2]-box[0])*.5)

    def test_source_slots_keep_fonts_and_offset_relationships(self):
        for recipe in profile()['recipes']:
            runs=plan(recipe['text'].split(),lambda t,f,s:ink(t,f,s)[0])
            for run,source in zip(runs,recipe['runs']):
                self.assertEqual(run['font'],source['font'])
                self.assertEqual(run['size'],source['size'])
                self.assertAlmostEqual(run['x']-runs[0]['x'],source['x']-recipe['runs'][0]['x'])
                self.assertAlmostEqual(run['y']-runs[0]['y'],source['y']-recipe['runs'][0]['y'])

    def test_saved_pattern_survives_word_count_change_and_other_demo_words(self):
        original=profile()['recipes'][2]  # Inline reference, not a stack.
        for text in ['Updated and saved Caption','Par Reality simple hai']:
            cue=CaptionCue(tuple(CaptionWord(w,i*.5,(i+1)*.5) for i,w in enumerate(text.split())),0,3,original['text'],2)
            with pattern_context(cue):
                self.assertEqual(recipe_for(text.split())['text'],original['text'])
                runs=plan(text.split(),lambda t,f,s:ink(t,f,s)[0])
            self.assertEqual(len(set(r['row'] for r in runs)),1)
            with scene_capture.capture():
                words=scene_capture.words(render(368,207,cue,2.9))
            self.assertEqual([w['text'] for w in words],text.split())

    def test_reveal_never_changes_existing_word_positions(self):
        cue=self.cue('content banana maine START kar diya')
        with scene_capture.capture():
            first=scene_capture.words(render(736,414,cue,cue.words[1].start-.01))
            last=scene_capture.words(render(736,414,cue,cue.end-.01))
        self.assertAlmostEqual(first[0]['x'],last[0]['x'])
        self.assertAlmostEqual(first[0]['y'],last[0]['y'])

    def test_three_future_scripts_retain_saved_pattern_after_round_trip(self):
        from hinglish_captions.project import cues_to_data,cues_from_data
        from hinglish_captions.core import retime_cue_text
        from hinglish_captions.template_patterns import bind_patterns
        original=self.cue('content banana maine START kar diya')
        original=CaptionCue(original.words,original.start,original.end,original.text,2)
        for text in ['Small ideas become powerful stories every single day',
                     'Aaj hum apne sapno ki taraf pehla kadam badhayenge',
                     'Keep creating because your voice deserves to be heard']:
            cue=bind_patterns([retime_cue_text(original,text)],[original])[0]
            saved=cues_from_data(cues_to_data([cue]))[0]
            self.assertEqual(saved.template_source,original.template_source)
            self.assertEqual(saved.template_slot,2)
            for offset,page in pages(saved,207,368):
                with pattern_context(saved):runs=plan([w.text for w in page.words],None,True,[w.text for w in saved.words],offset)
                self.assertEqual(len(set(r['row'] for r in runs)),1)
                self.assertEqual([r['text'] for r in runs],[w.text for w in page.words])

    def test_shorter_inline_script_keeps_normal_spaces(self):
        recipe=profile()['recipes'][2];text='Small ideas inspire people'
        cue=CaptionCue(tuple(CaptionWord(w,i,i+1) for i,w in enumerate(text.split())),0,4,recipe['text'],2)
        with pattern_context(cue):runs=plan(text.split(),None)
        for a,b in zip(runs,runs[1:]):
            gap=b['x']-b['width']/2-a['x']-a['width']/2
            self.assertGreaterEqual(gap,7.9)
            self.assertLessEqual(gap,12)

    def test_old_saved_editor_refreshes_profile_with_current_script(self):
        from pathlib import Path
        from hinglish_app.presentation import caption_html
        source=b'<html><head></head><body><script>const project={};</script><script>// First reference draft:\noldGold();</script></body></html>'
        result=caption_html(source,Path('output/captions/kinetic-gold-reference-rebuild'),'test-only').decode('utf-8')
        self.assertIn('project.kinetic_gold_profile=',result)
        self.assertIn('"reference_compound": true',result)
        self.assertNotIn('oldGold();',result)
        self.assertIn('let profileLoading=null',result)

if __name__=='__main__':unittest.main()
