import json,shutil,subprocess,unittest
from pathlib import Path
import numpy as np
from hinglish_captions.caption_five import composition,profile,sample_cues,layout,render,motion_state,paginate_cue
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.renderer import draw_editor_caption

ROOT=Path(__file__).resolve().parents[1]

class CaptionFiveTests(unittest.TestCase):
    def test_all_original_words_and_speech_times_survive(self):
        original=json.loads((ROOT/'hinglish_captions/caption_one_taj_words.json').read_text('utf8'))['words']
        self.assertEqual([dict(text=w.text,start=w.start,end=w.end) for q in sample_cues() for w in q.words],original)
        arrangements=set()
        for q in sample_cues():
            plan,lines,_=layout([w.text for w in q.words],720,1280);arrangements.add(plan['arrangement'])
            self.assertLessEqual(len(q.words),5);self.assertLessEqual(len(lines),3)
            self.assertEqual(sorted(r['i'] for l in lines for r in l['runs']),list(range(len(q.words))))
            self.assertTrue(all(l['width']<=720*profile()['safe_width']+1 for l in lines))
        self.assertEqual(arrangements,{'stack','flank'})

    def test_each_word_produces_visible_pixels_including_short_footer_words(self):
        for q in sample_cues():
            for i,w in enumerate(q.words):
                colors=['#1677FF']*len(q.words);colors[i]='#F04444'
                p=np.asarray(render(320,568,q,w.start+(q.end-w.start)*.6,word_colors=colors))
                red=(p[:,:,0]>180)&(p[:,:,1]<100)&(p[:,:,2]<100)&(p[:,:,3]>100)
                self.assertGreater(int(red.sum()),3,(q.text,w.text))

    def test_future_words_and_inactive_cues_stay_hidden(self):
        q=sample_cues()[1];colors=['#1677FF']*len(q.words);colors[-1]='#F04444'
        p=np.asarray(render(320,568,q,q.words[-1].start-.01,word_colors=colors))
        self.assertFalse(((p[:,:,0]>180)&(p[:,:,1]<100)&(p[:,:,3]>100)).any())
        self.assertIsNone(render(320,568,q,q.start-.01).getbbox());self.assertIsNone(render(320,568,q,q.end).getbbox())
        self.assertIsNone(render(320,568,q,q.words[-1].end+.01,visibility='styled_spoken').getbbox())

    def test_overflow_and_old_long_cues_preserve_every_word(self):
        tokens='A very long supporting phrase before the monument and all remaining words stay visible'.split()
        q=CaptionCue(tuple(CaptionWord(w,i*.3,(i+1)*.3) for i,w in enumerate(tokens)),0,len(tokens)*.3+.3);pages=paginate_cue(q)
        self.assertGreater(len(pages),1);self.assertEqual([w for page in pages for w in page.words],list(q.words))
        self.assertTrue(all(len(p.words)<=5 for p in pages))
        self.assertIsNotNone(render(320,568,q,pages[-1].words[-1].start+.15).getbbox())

    def test_landscape_reference_and_portrait_layouts_have_safe_compact_gaps(self):
        for width,height in [(720,1280),(714,408)]:
            for q in sample_cues():
                plan,lines,ratio=layout([w.text for w in q.words],width,height);main=next(l for l in lines if l['row']['role']=='main')
                for line in lines:
                    if line is main:continue
                    if plan['arrangement']=='flank':
                        a,b=(line,main) if line['row']['role']=='header' else (main,line)
                        gap=(b['x']+b['left'])-(a['x']+a['left']+a['width'])
                    else:
                        a,b=(line,main) if line['row']['role']=='header' else (main,line)
                        gap=(b['y']+b['top'])-(a['y']+a['bottom'])
                    self.assertAlmostEqual(gap,profile()['gap']*ratio,places=6)
                t=q.words[-1].start+(q.end-q.words[-1].start)*.65;box=render(width,height,q,t).getbbox()
                self.assertTrue(box and box[0]>0 and box[1]>0 and box[2]<width and box[3]<height,q.text)

    def test_number_and_condensed_entrances_use_the_measured_settle(self):
        number=composition('BHAI 4 mahine'.split());self.assertTrue(number['number'])
        self.assertEqual(motion_state(-1,1)[0],0);self.assertEqual(motion_state(1,1),(1,0,0,1))
        self.assertGreater(motion_state(.03,1,True)[2],25)
        self.assertEqual(motion_state(.4,1,True),(1,0,0,1))
        self.assertGreater(motion_state(.03,1,True,True)[1],20)
        self.assertEqual(motion_state(.03,1,True,True)[2],0)
        self.assertEqual(motion_state(.08,.08,True),(1,0,0,1))

    def test_horizontal_groups_keep_one_baseline_after_script_edits(self):
        from hinglish_captions.template_patterns import pattern_context
        for text in ('caption group, AND kept aligned',
                     'Both red BOXES, cursor/ click,',
                     'yeh bada WORD neeche gaya',
                     'Small EXTRAORDINARY words stay together'):
            words=text.split()
            cue=CaptionCue(tuple(CaptionWord(w,i*.4,(i+1)*.4) for i,w in enumerate(words)),
                           0,3,template_source='The Taj Mahal')
            with pattern_context(cue):
                for width,height in ((720,1280),(714,408),(320,568)):
                    plan,lines,_=layout(words,width,height)
                    self.assertEqual(plan['arrangement'],'flank',text)
                    self.assertEqual(len({line['y'] for line in lines}),1,text)
                    left=min(line['x']+line['left'] for line in lines)
                    right=max(line['x']+line['left']+line['width'] for line in lines)
                    self.assertAlmostEqual((left+right)/2,width/2,places=6)
                    self.assertGreaterEqual(left,width*.08-1)
                    self.assertLessEqual(right,width*.92+1)

    def test_manual_font_color_size_and_position_remain_editable(self):
        q=CaptionCue((CaptionWord('Monument',0,2.5),),0,3)
        normal=draw_editor_caption(360,640,q,1,'caption_5','template',dict(x=.5,y=.45,size=1),'phrase')
        custom=draw_editor_caption(360,640,q,1,'caption_5','arial',dict(x=.4,y=.3,size=.7),'phrase',['#F04444'])
        self.assertLess(custom.getbbox()[2]-custom.getbbox()[0],normal.getbbox()[2]-normal.getbbox()[0]);self.assertLess(custom.getbbox()[1],normal.getbbox()[1])
        p=np.asarray(custom);self.assertGreater(int(((p[:,:,0]>180)&(p[:,:,1]<100)&(p[:,:,3]>180)).sum()),50)

    @unittest.skipUnless(shutil.which('node'),'Node is required for preview/export motion parity')
    def test_browser_and_export_share_all_motion_frames_and_roles(self):
        source=(ROOT/'hinglish_captions/caption_five.js').read_text('utf8');code=source[source.index('  const normalize='):source.index('  const canvas=')]
        examples=[r['text'].split() for r in profile()['recipes']+profile()['demo_phrases']]+[[],['hello'],'Try it for 12 months'.split(),'A new story begins'.split()]
        states=[[i/60,available,main,condensed] for i in range(-2,121) for available in (.06,.1,1) for main in (False,True) for condensed in (False,True)]
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;"+code+"console.log(JSON.stringify({plans:input.examples.map(planFor),states:input.states.map(a=>motionState(...a))}));"
        result=subprocess.run(['node','-e',(Path(__file__).resolve().parents[1]/'hinglish_captions/template_patterns.js').read_text('utf-8')+'\n'+script],input=json.dumps(dict(config=profile(),examples=examples,states=states)),capture_output=True,text=True,check=True);actual=json.loads(result.stdout)
        self.assertEqual(actual['plans'],[composition(w) for w in examples]);self.assertTrue(np.allclose(actual['states'],[motion_state(*a) for a in states],atol=1e-12,rtol=0))

if __name__=='__main__':unittest.main()
