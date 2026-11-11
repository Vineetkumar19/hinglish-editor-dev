import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

from hinglish_captions.caption_one import composition,profile,motion_state,motion_for,phase_at,paginate_cue,paginate_cues
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.demo import caption_one_sample_cues
from hinglish_captions.editing import apply_timings
from hinglish_captions.project import cues_to_data
from hinglish_captions.renderer import draw_caption,draw_editor_caption,render_overlay
from hinglish_captions.styles import SELECTABLE_TEMPLATES

ROOT=Path(__file__).resolve().parents[1]


class CaptionOneTests(unittest.TestCase):
    def test_owner_spacing_keeps_equal_ink_gaps_on_both_sides_of_main_word(self):
        from hinglish_captions.caption_one import layout
        for width,height in ((720,1280),(1080,1920)):
            for text in ('Its white marble glows softly','The Taj Mahal stands beside','the balanced gardens and the reflections'):
                geometry=layout(width,height,text.split())
                bounds={}
                for run in geometry['words']:
                    font=run['font'];box=font.getbbox(run['text']);baseline=run['baseline']
                    key='main' if run['row'].get('blue') else 'bottom' if run['row']['align']=='right' else 'top'
                    top=baseline+box[1]-font.getmetrics()[0];bottom=baseline+box[3]-font.getmetrics()[0]
                    a,b=bounds.get(key,(float('inf'),float('-inf')));bounds[key]=(min(a,top),max(b,bottom))
                gap=9*geometry['scale']
                if 'top' in bounds:self.assertAlmostEqual(bounds['main'][0]-bounds['top'][1],gap)
                if 'bottom' in bounds:self.assertAlmostEqual(bounds['bottom'][0]-bounds['main'][1],gap)

    def cue(self,text='love the challenge of taking'):
        return CaptionCue(tuple(CaptionWord(word,i*.4,i*.4+.12) for i,word in enumerate(text.split())),0,2.5)

    def test_reference_font_geometry_and_blue_emphasis(self):
        cue=self.cue('love the challenge')
        image=np.asarray(draw_caption(720,1280,cue,2.3,'caption_1',position=.6234375))
        r,g,b=[image[:,:,i].astype(float) for i in range(3)]
        blue=(b>130)&(g>100)&(b>r*1.6)&(g>r*1.3)&(image[:,:,3]>150)
        ys,xs=np.where(blue)
        # Settled video-1 CHALLENGE bounds measured at native 720x1280.
        for actual,expected in zip((xs.min(),ys.min(),xs.max()+1,ys.max()+1),(148,737,575,798)):
            self.assertAlmostEqual(actual,expected,delta=4)
        upper=np.median(image[746][blue[746]][:,:3],axis=0)
        lower=np.median(image[789][blue[789]][:,:3],axis=0)
        self.assertGreater(upper[1],lower[1]+20)
        self.assertEqual(SELECTABLE_TEMPLATES['caption_1']['name'],'Caption 1')

    def test_all_reference_words_survive_composition(self):
        for row in profile()['recipes']:
            cue=self.cue(row['text'])
            pages=paginate_cue(cue)
            self.assertEqual(tuple(w for page in pages for w in page.words),cue.words)
            for page in pages:
                plan=composition([w.text for w in page.words])
                self.assertFalse(plan['hidden'])
                self.assertEqual(sorted(i for line in plan['rows'] for i in line['words']),list(range(len(page.words))))

    def test_every_taj_word_is_in_a_visible_row_before_its_slide_ends(self):
        from hinglish_captions.demo import SCRIPT
        visible=[]
        for cue in caption_one_sample_cues():
            plan=composition([w.text for w in cue.words])
            self.assertFalse(plan['hidden'],cue.text)
            shown=phase_at(plan,cue.words,cue.end-.001,cue.end)['indices']
            self.assertEqual(shown,list(range(len(cue.words))),cue.text)
            self.assertEqual([i for row in plan['rows'] if row['size']==80 for i in row['words']],[plan['hero']])
            for row in plan['rows']:
                self.assertEqual(row['size'],80 if row.get('blue') else 46)
                motion=motion_for(plan,row,row['words'][0])
                alpha,_,_=motion_state(cue.end-.001-cue.words[motion['start_word']].start,motion)
                self.assertGreater(alpha,.05,cue.text)
            visible.extend(cue.words[i].text for i in shown)
        # Checking the saved transcript alone missed the previous regression:
        # every word must actually belong to a row that becomes visible.
        self.assertEqual(visible,SCRIPT.split())
        self.assertEqual(len(visible),65)

    @unittest.skipUnless(shutil.which('node'),'Node needed for browser pagination comparison')
    def test_browser_pagination_keeps_all_demo_words_like_export(self):
        from hinglish_captions.caption_one import text_metrics
        from hinglish_captions.renderer import _font_path
        examples=[row['text'].split() for row in profile()['demo_phrases']]
        examples=[[word.strip('.,!?:;') for word in words] for words in examples]
        metrics={}
        for main in (False,True):
            path=_font_path('Inter-Bold.otf' if main else 'Inter-Medium.otf')
            metrics['main' if main else 'support']={word:text_metrics(path,80 if main else 46,
                word.upper() if main else word,profile()['tracking' if main else 'support_tracking'])
                for words in examples for word in words}
        source=(ROOT/'hinglish_captions/caption_one.js').read_text('utf-8')
        code=source[source.index('  const normalize='):source.index('  const canvas=')]
        script="""const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;
        function measure(words,indices,main){
          let cursor=0,left=Infinity,right=-Infinity;
          for(const i of indices){const [advance,a,b]=input.metrics[main?'main':'support'][words[i]];
            left=Math.min(left,cursor+a);right=Math.max(right,cursor+b);cursor+=advance+80*config.word_gap}
          return indices.length?right-left:0;
        }
        """+code+"console.log(JSON.stringify(input.examples.map(words=>splitFor(words,measure).map(p=>words.slice(p.start,p.end)))));"
        result=subprocess.run(['node','-e',script],input=json.dumps(dict(config=profile(),metrics=metrics,examples=examples)),capture_output=True,text=True,check=True)
        expected=[[list(w.text for w in page.words) for page in paginate_cue(self.cue(' '.join(words)))] for words in examples]
        self.assertEqual(json.loads(result.stdout),expected)

    def test_motion_decelerates_smoothly_and_is_slower_than_the_reference(self):
        plan=composition('love the challenge of taking'.split())
        motion=motion_for(plan,plan['rows'][1],2)
        self.assertGreaterEqual(motion['duration'],.7)
        states=[motion_state(i/60,motion) for i in range(48)]
        self.assertTrue(all(a[2]>=b[2] for a,b in zip(states,states[1:])))
        steps=[a[2]-b[2] for a,b in zip(states,states[1:])]
        self.assertGreater(max(steps),steps[0]*20)
        self.assertLess(steps[-1],.01)
        self.assertTrue(any(abs(s[2]-round(s[2]))>.1 for s in states))
        self.assertEqual(motion_state(-.1,motion),(0,0,12))
        self.assertEqual(motion_state(1,motion),(1,0,0))

    def test_main_word_rises_without_resizing_and_stops_then_cuts(self):
        cue=self.cue('love the challenge')
        def blue_box(t):
            p=np.asarray(draw_caption(720,1280,cue,t,'caption_1',position=.6234375))
            mask=(p[:,:,2].astype(float)>p[:,:,0]*1.6)&(p[:,:,3]>15)
            y,x=np.where(mask)
            return (x.min(),y.min(),x.max(),y.max())
        early,late=blue_box(.9),blue_box(1.7)
        self.assertAlmostEqual(early[0],late[0],delta=1);self.assertAlmostEqual(early[2],late[2],delta=1)
        self.assertGreater(early[1],late[1]+8)
        self.assertIsNone(draw_caption(720,1280,cue,cue.end,'caption_1').getbbox())

    def test_three_lines_accumulate_and_hold_until_the_next_group(self):
        cue=self.cue('love the climb of it')
        plan=composition([w.text for w in cue.words])
        self.assertEqual(phase_at(plan,cue.words,.1,cue.end)['indices'],[0,1])
        self.assertEqual(phase_at(plan,cue.words,.9,cue.end)['indices'],[0,1,2])
        self.assertEqual(phase_at(plan,cue.words,1.3,cue.end)['indices'],[0,1,2,3,4])
        self.assertEqual(phase_at(plan,cue.words,2.49,cue.end)['indices'],[0,1,2,3,4])
        self.assertEqual(phase_at(plan,cue.words,1.7,cue.end,'styled_spoken')['indices'],[4])
        for recipe in profile()['recipes']:
            plan=composition(recipe['text'].split())
            big=[i for row in plan['rows'] if row.get('size',0)>46 for i in row['words']]
            self.assertEqual(big,[plan['hero']])
            self.assertLessEqual(len(plan['rows']),3)
        for cue in caption_one_sample_cues():
            plan=composition([w.text for w in cue.words])
            self.assertEqual(len(plan['rows']),2 if plan['two_line'] or plan['hero']==len(cue.words)-1 else 3)
            self.assertEqual(phase_at(plan,cue.words,cue.end-.01,cue.end)['indices'],sorted(i for row in plan['rows'] for i in row['words']))
            self.assertLess(cue.words[plan['rows'][-1]['words'][0]].start,cue.end-.1)

    def test_word_gaps_hide_future_words_and_manual_color_and_size_work(self):
        cue=self.cue('hello')
        self.assertIsNone(draw_editor_caption(360,640,cue,.14,'caption_1','template',{'x':.5,'y':.5,'size':1},'styled_spoken').getbbox())
        self.assertIsNotNone(draw_editor_caption(360,640,cue,.14,'caption_1','template',{'x':.5,'y':.5,'size':1},'phrase').getbbox())
        original=draw_editor_caption(360,640,cue,.5,'caption_1','template',{'x':.5,'y':.5,'size':1},'phrase')
        small=draw_editor_caption(360,640,cue,.5,'caption_1','template',{'x':.5,'y':.5,'size':.7},'phrase',['#F04444'])
        self.assertLess(small.getbbox()[2]-small.getbbox()[0],original.getbbox()[2]-original.getbbox()[0])
        p=np.asarray(small);self.assertGreater(np.count_nonzero((p[:,:,0]>150)&(p[:,:,2]<100)&(p[:,:,3]>150)),50)

    def test_taj_demo_matches_narration_words_and_has_valid_nonuniform_timings(self):
        import hashlib,wave
        from hinglish_captions.demo import SCRIPT
        cues=caption_one_sample_cues()
        self.assertEqual(' '.join(c.text for c in cues),SCRIPT)
        timing=json.loads((ROOT/'hinglish_captions/caption_one_taj_words.json').read_text())
        audio=ROOT/'hinglish_captions'/timing['audio']
        self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(),timing['audio_sha256'])
        with wave.open(str(audio)) as wav:self.assertAlmostEqual(wav.getnframes()/wav.getframerate(),30,places=2)
        actual=[{'text':w.text,'start':w.start,'end':w.end} for c in cues for w in c.words]
        self.assertEqual(actual,timing['words'])
        starts=[w['start'] for w in actual]
        self.assertGreater(max(np.diff(starts))-min(np.diff(starts)),.4)
        self.assertEqual(apply_timings(cues,cues_to_data(cues),30),cues)
        self.assertTrue(all(0<=w['start']<w['end']<=30 for w in actual))

    def test_eight_letter_cutoff_named_edits_and_footer_ink_alignment(self):
        self.assertTrue(composition('Imagine a monument that changes with the light'.split())['two_line'])
        self.assertFalse(composition('Every detail invites you to slow down'.split())['two_line'])
        expected={'MARBLE':'glows softly','CLOSER':'at the','SHINES':'beneath',
                  'INVITES':'you to','PLACES':'are more','STORIES':'that the'}
        for cue in caption_one_sample_cues():
            words=[w.text.strip('.,!?:;') for w in cue.words];plan=composition(words)
            p=np.asarray(draw_caption(720,1280,cue,cue.end-.03,'caption_1',position=.6234375))
            r,g,b=[p[:,:,i].astype(float) for i in range(3)]
            blue=(b>r*1.6)&(g>r*1.3)&(p[:,:,3]>150)
            y,x=np.where(blue);main_left,main_right=x.min(),x.max()
            footer=(p[:,:,0]>180)&(p[:,:,1]>180)&(p[:,:,2]>180)&(p[:,:,3]>180)&(np.arange(1280)[:,None]>800)
            fy,fx=np.where(footer)
            if not any(row['align']=='right' for row in plan['rows']):
                self.assertEqual(len(fx),0)
            else:
                self.assertGreater(len(fx),0)
                self.assertGreaterEqual(fx.min(),main_left-2)
                row=plan['rows'][-1]
                motion=motion_for(plan,row,row['words'][0])
                _,dx,_=motion_state(cue.end-.03-cue.words[motion['start_word']].start,motion)
                self.assertAlmostEqual(fx.max()-dx,main_right,delta=2)
            hero=words[plan['hero']].upper()
            if hero in expected:
                self.assertEqual(' '.join(words[i] for i in plan['rows'][-1]['words']),expected[hero])
            if hero in ('INVITES','PLACES','STORIES'):
                # Overflow continues on another timed slide, retaining the
                # regular support font and close gap on the original slide.
                from hinglish_captions.caption_one import font
                from hinglish_captions.renderer import _font_path
                regular=font(_font_path('Inter-Medium.otf'),46)
                box=regular.getbbox(' '.join(words[i] for i in row['words']))
                self.assertAlmostEqual(fy.max()-fy.min()+1,box[3]-box[1],delta=2)
                self.assertGreaterEqual(fy.min()-y.max()-1,6)
                self.assertLessEqual(fy.min()-y.max()-1,10)

    def test_overflow_words_get_new_timed_slides_without_loss_or_shrinking(self):
        timing=json.loads((ROOT/'hinglish_captions/caption_one_taj_words.json').read_text())['words']
        words=tuple(CaptionWord(w['text'],w['start'],w['end']) for w in timing)
        expected=[('Every detail invites you to','slow down.'),
                  ('Some places are more','than buildings.'),
                  ('They become stories that the','world remembers.')]
        for phrase,parts in zip(profile()['demo_phrases'][-3:],expected):
            tokens=phrase['text'].split()
            start=next(i for i,w in enumerate(words) if w.text==tokens[0] and [x.text for x in words[i:i+len(tokens)]]==tokens)
            group=words[start:start+len(tokens)]
            cue=CaptionCue(group,group[0].start,30 if start+len(tokens)==len(words) else words[start+len(tokens)].start)
            pages=paginate_cue(cue)
            self.assertEqual(tuple(p.text for p in pages),parts)
            self.assertEqual(tuple(w for p in pages for w in p.words),cue.words)
            self.assertEqual(pages[0].end,pages[1].start)
            self.assertEqual(pages[1].start,pages[1].words[0].start)
            self.assertEqual(paginate_cues(pages),list(pages))
            self.assertTrue(all(not composition([w.text for w in p.words])['hidden'] for p in pages))
            # Internal pagination of old projects matches explicit new slides,
            # including custom colors attached to their original word indices.
            from hinglish_captions.renderer import WORD_COLOR_CHOICES
            palette=list(WORD_COLOR_CHOICES)
            colors=[palette[i%len(palette)] for i in range(len(cue.words))]
            offset=0
            for p in pages:
                t=p.end-.02
                old=draw_caption(720,1280,cue,t,'caption_1',word_colors=colors)
                new=draw_caption(720,1280,p,t,'caption_1',word_colors=colors[offset:offset+len(p.words)])
                self.assertTrue(np.array_equal(np.asarray(old),np.asarray(new)))
                offset+=len(p.words)

    @unittest.skipUnless(shutil.which('node'),'Node needed for browser planner comparison')
    def test_browser_uses_the_same_recipes_and_generic_composition(self):
        s=(ROOT/'hinglish_captions/caption_one.js').read_text('utf-8')
        code=s[s.index('  const normalize='):s.index('  const canvas=')]
        examples=[r['text'].split() for r in profile()['recipes']]+['Imagine a monument that'.split(),['hello'],[]]
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;"+code+"console.log(JSON.stringify(input.examples.map(planFor)));"
        result=subprocess.run(['node','-e',script],input=json.dumps({'config':profile(),'examples':examples}),capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout),[composition(words) for words in examples])

    @unittest.skipUnless(shutil.which('node'),'Node needed for browser motion comparison')
    def test_browser_and_export_share_motion_at_every_native_frame(self):
        s=(ROOT/'hinglish_captions/caption_one.js').read_text('utf-8')
        code=s[s.index('  const normalize='):s.index('  const canvas=')]
        examples=[];expected=[]
        for recipe in profile()['recipes']:
            plan=composition(recipe['text'].split())
            for row in plan['rows']:
                for index in row['words']:
                    m=motion_for(plan,row,index)
                    for frame in range(-1,20):
                        elapsed=frame*1001/30000
                        examples.append([plan,row,index,elapsed])
                        expected.append(motion_state(elapsed,m))
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;"+code+"console.log(JSON.stringify(input.examples.map(([p,r,i,t])=>motionState(t,motionFor(p,r,i)))));"
        result=subprocess.run(['node','-e',script],input=json.dumps({'config':profile(),'examples':examples}),capture_output=True,text=True,check=True)
        self.assertTrue(np.allclose(json.loads(result.stdout),expected,rtol=0,atol=1e-12))

    @unittest.skipUnless(shutil.which('node'),'Node needed for browser phase comparison')
    def test_browser_three_line_stack_matches_export_at_every_demo_frame(self):
        s=(ROOT/'hinglish_captions/caption_one.js').read_text('utf-8')
        code=s[s.index('  const normalize='):s.index('  const canvas=')]
        examples=[];expected=[]
        for cue in caption_one_sample_cues():
            plan=composition([w.text for w in cue.words])
            words=[{'text':w.text,'start':w.start,'end':w.end} for w in cue.words]
            for t in np.arange(cue.start,cue.end,1/60):
                examples.append([plan,words,float(t),cue.end])
                expected.append(phase_at(plan,cue.words,float(t),cue.end))
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;"+code+"console.log(JSON.stringify(input.examples.map(([p,w,t,e])=>phaseAt(p,w,t,e))));"
        result=subprocess.run(['node','-e',script],input=json.dumps({'config':profile(),'examples':examples}),capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout),expected)

    def test_movie_export_keeps_exact_transparency_and_pixels(self):
        import av
        temp=ROOT/'tmp/caption-tests';temp.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp) as folder:
            path=Path(folder)/'caption1.mov';cue=self.cue()
            render_overlay(path,[cue],240,426,.4,60,'caption_1',lambda _:None,position=.6234375)
            with av.open(str(path)) as movie:
                frames=list(movie.decode(video=0))
                self.assertEqual(len(frames),24)
                for i,frame in enumerate(frames):
                    expected=np.asarray(draw_caption(240,426,cue,i/60,'caption_1',position=.6234375))
                    self.assertTrue(np.array_equal(frame.to_ndarray(format='rgba'),expected))


if __name__=='__main__':unittest.main()
