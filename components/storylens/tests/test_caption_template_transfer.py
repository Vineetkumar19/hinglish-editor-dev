"""New-script regression scenarios for approved caption templates."""
import unittest
from hinglish_captions.core import CaptionCue,CaptionWord,retime_cue_text
from hinglish_captions.project import cues_to_data,cues_from_data
from hinglish_captions.template_patterns import source_text,transfer,bind_patterns
from hinglish_captions import caption_one,caption_two,caption_three,caption_four,caption_five,kinetic_gold,serif_circle
from hinglish_captions.renderer import draw_editor_caption
from hinglish_captions.styles import SELECTABLE_TEMPLATES


def cue(text,original=''):
    words=text.split()
    return CaptionCue(tuple(CaptionWord(w,i*.08,(i+1)*.08) for i,w in enumerate(words)),0,3,original)


class CaptionTemplateTransferTests(unittest.TestCase):
    def test_overlapping_tail_cannot_steal_next_pattern(self):
        from dataclasses import replace
        first=replace(cue('First original phrase'),end=1.08)
        second=CaptionCue((CaptionWord('Second',1,1.4),CaptionWord('phrase',1.4,2)),1,2)
        frozen=bind_patterns([first,second])
        self.assertEqual(frozen[1].template_source,'Second phrase')
        self.assertEqual(frozen[1].template_slot,1)
        rebound=bind_patterns([second],frozen)
        self.assertEqual(rebound[0].template_slot,1)

    def test_script_edits_and_reopen_preserve_original_pattern(self):
        original=cue('to Understand your value')
        for text in ['apni Audience ko samjho','Understand why consistent storytelling really matters']:
            changed=retime_cue_text(original,text)
            reopened=cues_from_data(cues_to_data([changed]))[0]
            self.assertEqual(reopened.template_source,original.text)
            state=source_text.set(reopened.template_source)
            try:plan=caption_two.composition(reopened.text.split())
            finally:source_text.reset(state)
            self.assertEqual(plan['template_pattern'],original.text)
            self.assertEqual(plan['motion'],caption_two.profile()['recipes'][1]['motion'])
            self.assertTrue(plan['balanced_reference'])
            self.assertEqual(plan['main_size'],114)
            self.assertEqual(plan['header_fraction'],.16)
            self.assertTrue(all(''.join(c for c in reopened.words[i].text.lower() if c.isalnum()) not in caption_two.profile()['keyword_stop_words'] for row in plan['rows'] for i in row.get('green',[])))

    def test_reference_decorations_survive_english_and_hinglish(self):
        for module,flag in [(serif_circle,'decorations'),(kinetic_gold,'underline'),(kinetic_gold,'echo')]:
            recipe=next(r for r in module.profile()['recipes'] if r.get(flag))
            for text in ['apni kahani abhi share karo','Build better stories with confidence today']:
                state=source_text.set(recipe['text'])
                try:plan=module.recipe_for(text.split())
                finally:source_text.reset(state)
                if flag=='decorations':
                    self.assertEqual([{k:v for k,v in d.items() if k in ('kind','color','stroke','duration','linear','glow')} for d in plan[flag]],
                                     [{k:v for k,v in d.items() if k in ('kind','color','stroke','duration','linear','glow')} for d in recipe[flag]])
                    self.assertTrue(all(0<=d['trigger']<len(text.split()) for d in plan[flag]))
                else:self.assertEqual(plan[flag],recipe[flag])

    def test_edit_into_another_reference_phrase_keeps_saved_pattern(self):
        recipes=caption_two.profile()['recipes']
        original=next(r for r in recipes if r['text']=='to Understand your value')
        replacement=next(r for r in recipes if r['text']!=original['text'])
        changed=retime_cue_text(cue(original['text']),replacement['text'])
        state=source_text.set(changed.template_source)
        try:plan=caption_two.composition(changed.text.split())
        finally:source_text.reset(state)
        self.assertEqual(plan['template_pattern'],original['text'])
        self.assertEqual(plan['motion'],original['motion'])

    def test_long_clean_caption_width_fit_terminates(self):
        image=draw_editor_caption(360,640,cue('photographs responsibility unforgettable extraordinary'),1.8,
                                  'cinematic_clean_draft','template',{'x':.5,'y':.65,'size':1},'phrase')
        box=image.getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[0],0)
        self.assertLessEqual(box[2],360)

    def test_rebinding_keeps_every_word_once_at_different_lengths(self):
        for module in [caption_two,caption_three,caption_four,caption_five]:
            for count in [1,2,3,4,5,7,10]:
                words=('We create meaningful stories for your growing business every day'.split())[:count]
                with self.subTest(style=module.__name__,count=count):
                    plan=module.composition(words)
                    self.assertEqual(sorted(i for r in plan['rows'] for i in r['words']),list(range(count)))

    def test_saved_style_fields_are_not_replaced_by_plain_fallback(self):
        for module in [caption_two,caption_three]:
            recipes=module.profile()['recipes' if module is caption_two else 'demo_phrases']
            for recipe in recipes:
                state=source_text.set(recipe['text'])
                try:plan=transfer(['word']*len(recipe['text'].split()),recipes)
                finally:source_text.reset(state)
                self.assertEqual([r.get('align') for r in plan['rows']],[r.get('align') for r in recipe['rows']])
                self.assertEqual([r.get('reveal') for r in plan['rows']],[r.get('reveal') for r in recipe['rows']])
                self.assertEqual([r.get('size') for r in plan['rows']],[r.get('size') for r in recipe['rows']])

    def test_all_styles_share_starting_anchor_and_render_new_scripts(self):
        for style,spec in SELECTABLE_TEMPLATES.items():
            if style=='caption_1':continue
            self.assertEqual(spec['default_position'],.65)
            for text in ['Build your business today','apni kahani abhi banao']:
                with self.subTest(style=style,text=text):
                    image=draw_editor_caption(360,640,cue(text),2,style,'template',{'x':.5,'y':.65,'size':1},'phrase')
                    box=image.getbbox()
                    self.assertIsNotNone(box)
                    self.assertGreater(box[1],100)
                    self.assertLess(box[3],638)

    def test_caption_two_has_no_upper_screen_variant_or_large_halo(self):
        p=caption_two.profile()
        self.assertFalse(any('position' in r for r in p['recipes']))
        self.assertLessEqual(max(radius for radius,_ in p['appearance']['lime_glow']),4)
        self.assertFalse(p['cursor']['enabled'])


if __name__=='__main__':unittest.main()
