"""Caption 3's owner-selected serif replacement: saved slots and real geometry."""
import json,subprocess,unittest
from pathlib import Path
import numpy as np
from hinglish_captions.caption_three import composition,profile,sample_cues,reference_cues,layout,render,motion_state,camera_state,transition_state,font,metrics
from hinglish_captions.core import CaptionCue,CaptionWord,retime_cue_text
from hinglish_captions.template_patterns import pattern_context
from hinglish_captions.project import cues_to_data,cues_from_data
from hinglish_captions.renderer import draw_editor_caption
ROOT=Path(__file__).resolve().parents[1]

def cue(text,source='',slot=-1):
    words=text.split();return CaptionCue(tuple(CaptionWord(w,i*.12,i*.12+.1) for i,w in enumerate(words)),0,3,source,slot)

class CaptionThreeTests(unittest.TestCase):
    def test_reference_and_previous_profile_are_preserved(self):
        cfg=profile();self.assertEqual(cfg['layout_revision'],5)
        self.assertIn('924363892284327261',cfg['source_video'])
        self.assertTrue((ROOT/cfg['previous_profile']).is_file())
        self.assertEqual(cfg['position'],.65)
        self.assertIn('caption-three/',cfg['main_font'])
        self.assertTrue(all(not row.get('select') for r in cfg['recipes'] for row in r['rows']))

    def test_original_narration_words_and_times_survive(self):
        original=json.loads((ROOT/'hinglish_captions/caption_one_taj_words.json').read_text())['words']
        self.assertEqual([dict(text=w.text,start=w.start,end=w.end) for q in sample_cues() for w in q.words],original)

    def test_measured_reference_retains_varied_hierarchy_and_offsets(self):
        cfg=profile();self.assertGreaterEqual(len(cfg['recipes']),10)
        self.assertGreaterEqual(len({tuple(row['size'] for row in r['rows']) for r in cfg['recipes']}),8)
        self.assertEqual({r['motion'] for r in cfg['recipes']},{'in','out'})
        for q in reference_cues():
            with pattern_context(q):plan,lines,ratio,H=layout(q.text.split(),720,1280)
            self.assertEqual(sorted(r['i'] for l in lines for r in l['runs']),list(range(len(q.words))))
            self.assertEqual([r['text'] for l in lines for r in l['runs']],q.text.split())
            left=min(l['x']+l['left'] for l in lines);right=max(l['x']+l['left']+l['width'] for l in lines)
            self.assertAlmostEqual((left+right)/2,360)
            self.assertLess(right-left,720*cfg['safe_width'])

    def test_script_edits_and_reopen_keep_source_pattern_and_row_design(self):
        for r in profile()['recipes']:
            old=cue(r['text'],r['text'])
            for text in ['Apni kahani abhi share karo','Build your business with meaningful stories today','Extraordinarily unforgettable photographs transform ordinary moments completely']:
                q=cues_from_data(cues_to_data([retime_cue_text(old,text)]))[0]
                with pattern_context(q):plan=composition(q.text.split())
                self.assertEqual(plan['template_pattern'],r['text'])
                self.assertEqual(plan['motion'],r['motion'])
                ids=[i for row in plan['rows'] for i in row['words']]
                self.assertEqual(sorted(ids),list(range(len(q.words))))
                for row in plan['rows']:
                    self.assertTrue(any(all(row.get(k)==source.get(k) for k in ('size','font','font_override','tone_override','offset','role','gap_before')) for source in r['rows']))

    def test_independent_row_fitting_does_not_shrink_support_with_main(self):
        r=profile()['recipes'][0]
        with pattern_context(cue(r['text'])):
            _,short,_,_=layout("Let's suppose hope not feeling well".split(),720,1280)
            _,long,_,_=layout("Let's suppose extraordinarily not feeling well".split(),720,1280)
        self.assertEqual(short[0]['runs'][0]['size'],long[0]['runs'][0]['size'])
        self.assertLess(long[1]['runs'][0]['size'],short[1]['runs'][0]['size'])
        self.assertEqual(short[2]['runs'][0]['size'],long[2]['runs'][0]['size'])

    def test_every_word_is_visible_and_slots_survive_pagination(self):
        from hinglish_captions.caption_three import paginate_cue
        q=cue('We create meaningful stories for your growing business every single day with confidence',profile()['recipes'][0]['text'],0)
        pages=paginate_cue(q);self.assertEqual([w for p in pages for w in p.words],list(q.words))
        self.assertTrue(all(len(p.words)<=5 for p in pages))
        self.assertTrue(all(p.template_source==q.template_source and p.template_slot==q.template_slot for p in pages))
        for page in pages:
            for i,w in enumerate(page.words):
                colors=[None]*len(page.words);colors[i]='#F04444'
                pixels=np.asarray(render(360,640,page,w.start+(page.end-w.start)*.65,word_colors=colors))
                red=(pixels[:,:,0]>170)&(pixels[:,:,1]<100)&(pixels[:,:,3]>60)
                self.assertGreater(int(red.sum()),2,(page.text,w.text))

    def test_timing_visibility_and_manual_position_size_color(self):
        q=cue('Stories')
        self.assertIsNone(render(360,640,q,-.1).getbbox());self.assertIsNone(render(360,640,q,3).getbbox())
        normal=draw_editor_caption(360,640,q,1.5,'caption_3','template',dict(x=.5,y=.65,size=1),'phrase')
        custom=draw_editor_caption(360,640,q,1.5,'caption_3','arial',dict(x=.4,y=.3,size=.7),'phrase',['#F04444'])
        self.assertLess(custom.getbbox()[2]-custom.getbbox()[0],normal.getbbox()[2]-normal.getbbox()[0])
        self.assertLess(custom.getbbox()[1],normal.getbbox()[1])
        self.assertIsNone(render(360,640,q,2,visibility='styled_spoken').getbbox())

    def test_browser_and_renderer_share_all_motion_clocks(self):
        js=(ROOT/'hinglish_captions/caption_three.js').read_text('utf-8-sig');code=js[js.index('  const normalize='):js.index('  const canvas=')]
        states=[[i/60,remaining,1.7,main,.08] for i in range(-2,121) for remaining in (0,.04,.16,1) for main in (True,False)]
        ages=[i/60 for i in range(-2,181)]
        examples=[q.text.split() for q in reference_cues()]+['Apni kahani abhi share karo'.split(),['Story']]
        script=(ROOT/'hinglish_captions/template_patterns.js').read_text()+'\nconst input=JSON.parse(require("fs").readFileSync(0,"utf8")),config=input.config;'+code+'console.log(JSON.stringify({states:input.states.map(s=>motionState(...s)),plans:input.examples.map(planFor),ins:input.ages.map(t=>cameraState(t,"in")),outs:input.ages.map(t=>cameraState(t,"out")),transitions:input.ages.map(t=>transitionState(t,"slide_left"))}));'
        result=subprocess.run(['node','-e',script],input=json.dumps(dict(config=profile(),states=states,ages=ages,examples=examples)),text=True,capture_output=True,check=True)
        data=json.loads(result.stdout);self.assertEqual(data['plans'],[composition(w) for w in examples])
        self.assertTrue(np.allclose(data['states'],[motion_state(*s) for s in states],atol=1e-12))
        self.assertTrue(np.allclose(data['ins'],[camera_state(t,'in') for t in ages],atol=1e-12))
        self.assertTrue(np.allclose(data['outs'],[camera_state(t,'out') for t in ages],atol=1e-12))
        self.assertTrue(np.allclose(data['transitions'],[transition_state(t,'slide_left') for t in ages],atol=1e-12))

    def test_comparison_is_two_slides_in_old_saved_cues(self):
        from hinglish_captions.caption_three import paginate_cue
        spread=profile()['legacy_spreads'][0];q=cue(spread['text'],spread['text'],3)
        pages=paginate_cue(q)
        self.assertEqual([p.text for p in pages],spread['page_sources'])
        self.assertEqual([w for p in pages for w in p.words],list(q.words))
        self.assertEqual(pages[0].end,pages[1].start)
        for p,kind in zip(pages,['playful','blue']):
            with pattern_context(p):plan=composition(p.text.split())
            self.assertEqual(len(plan['rows']),2)
            self.assertEqual(plan['rows'][-1]['font_override'],kind)
            self.assertEqual(p.template_slot,3)
        blue=lambda im:int(((np.asarray(im)[:,:,2]>100)&(np.asarray(im)[:,:,0]<80)&(np.asarray(im)[:,:,3]>80)).sum())
        self.assertEqual(blue(render(360,640,q,pages[0].end-.3)),0)
        self.assertGreater(blue(render(360,640,q,q.end-.3)),20)

    def test_ten_new_captions_and_replacements_keep_the_two_page_pattern(self):
        from hinglish_captions.caption_three import paginate_cue
        spread=profile()['legacy_spreads'][0]
        scripts=['Hum apni kahani naye andaaz mein sabke saamne lekar aaye hain',
                 'Thoughtful stories help people understand your ideas and build lasting trust',
                 'Aaj ek nayi direction lo aur apne creative ideas clearly share karo',
                 'Every extraordinary moment gives another meaningful reason to keep creating']
        old=cue(spread['text'],spread['text'],3)
        for index in range(10):
            text=scripts[index%len(scripts)]
            for changed in [retime_cue_text(old,text),cue(text,text,3)]:
                pages=paginate_cue(changed)
                self.assertEqual(len(pages),2)
                reopened=cues_from_data(cues_to_data(pages))
                for page,source,kind in zip(reopened,spread['page_sources'],['playful','blue']):
                    self.assertEqual(page.template_source,source)
                    again=retime_cue_text(page,'Nayi kahani sabke saath share karo')
                    with pattern_context(again):plan=composition(again.text.split())
                    self.assertEqual(plan['template_pattern'],source)
                    self.assertEqual(plan['rows'][-1]['font_override'],kind)
                    self.assertEqual(plan['motion'],'in')
                    self.assertEqual(len(plan['rows']),2)

    def test_browser_and_export_use_identical_page_boundaries_and_sources(self):
        from hinglish_captions.caption_three import paginate_cue
        js=(ROOT/'hinglish_captions/caption_three.js').read_text('utf-8-sig');code=js[js.index('  const normalize='):js.index('  const canvas=')]
        spread=profile()['legacy_spreads'][0];cases=[cue(spread['text'],spread['text'],3)]
        for n in [1,2,5,8,10,16,17,30,80]:
            text=' '.join('word'+str(i) for i in range(n))
            cases += [cue(text,spread['text'],3),cue(text,text,3),cue(text,spread['page_sources'][1],3)]
        inputs=[dict(words=q.text.split(),context=dict(template_source=q.template_source,template_slot=q.template_slot)) for q in cases]
        script='const input=JSON.parse(require("fs").readFileSync(0,"utf8")),config=input.config;'+code+'console.log(JSON.stringify(input.cases.map(c=>splitRanges(c.words,c.context))));'
        result=subprocess.run(['node','-e',script],input=json.dumps(dict(config=profile(),cases=inputs)),text=True,capture_output=True,check=True)
        expected=[]
        for q in cases:
            ranges=[];start=0
            for page in paginate_cue(q):
                ranges.append(dict(start=start,count=len(page.words),template_source=page.template_source,template_slot=page.template_slot));start+=len(page.words)
            expected.append(ranges)
        self.assertEqual(json.loads(result.stdout),expected)

if __name__=='__main__':unittest.main()
