import json,shutil,subprocess,unittest
from pathlib import Path
import numpy as np
from hinglish_captions.caption_four import composition,profile,sample_cues,layout,render,motion_state,camera_state,paginate_cue
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.renderer import draw_editor_caption

ROOT=Path(__file__).resolve().parents[1]

class CaptionFourTests(unittest.TestCase):
    def test_every_original_word_and_timestamp_survives_and_fits(self):
        original=json.loads((ROOT/'hinglish_captions/caption_one_taj_words.json').read_text('utf8'))['words']
        self.assertEqual([dict(text=w.text,start=w.start,end=w.end) for q in sample_cues() for w in q.words],original)
        for q in sample_cues():
            plan,lines,_=layout([w.text for w in q.words],720,1280)
            self.assertLessEqual(len(q.words),5);self.assertLessEqual(len(lines),3)
            self.assertEqual(sorted(i for row in plan['rows'] for i in row['words']),list(range(len(q.words))))
            self.assertTrue(all(line['width']<=720*profile()['safe_width']+1 for line in lines))

    def test_every_word_has_pixels_at_its_speech_time(self):
        for q in sample_cues():
            for i,w in enumerate(q.words):
                colors=[None]*len(q.words);colors[i]='#F04444';t=w.start+(q.end-w.start)*.6
                p=np.asarray(render(320,568,q,t,word_colors=colors))
                red=(p[:,:,0]>180)&(p[:,:,1]<100)&(p[:,:,2]<100)&(p[:,:,3]>100)
                self.assertGreater(int(red.sum()),3,(q.text,w.text))

    def test_future_words_and_inactive_cues_are_hidden(self):
        q=sample_cues()[1];colors=[None]*len(q.words);colors[-1]='#F04444'
        p=np.asarray(render(320,568,q,q.words[-1].start-.01,word_colors=colors))
        self.assertFalse(((p[:,:,0]>180)&(p[:,:,1]<100)&(p[:,:,3]>100)).any())
        self.assertIsNone(render(320,568,q,q.start-.01).getbbox());self.assertIsNone(render(320,568,q,q.end).getbbox())
        self.assertIsNone(render(320,568,q,q.words[-1].end+.01,visibility='styled_spoken').getbbox())

    def test_overflow_continues_without_losing_words_and_rows_fit_independently(self):
        tokens='A very long supporting phrase before the monument and every remaining word stays visible'.split()
        q=CaptionCue(tuple(CaptionWord(w,i*.3,(i+1)*.3) for i,w in enumerate(tokens)),0,len(tokens)*.3+.3);pages=paginate_cue(q)
        self.assertGreater(len(pages),1);self.assertEqual([w for page in pages for w in page.words],list(q.words))
        for page in pages:
            _,lines,_=layout([w.text for w in page.words],720,1280)
            self.assertLessEqual(len(page.words),5);self.assertLessEqual(len(lines),3)
            for line in lines:
                if line['row']['role']!='main':self.assertTrue(all(2<=r['size']<=profile()[line['row']['role']+'_size'] for r in line['runs']))
            left=min(line['x']+line['left'] for line in lines)
            right=max(line['x']+line['left']+line['width'] for line in lines)
            self.assertAlmostEqual((left+right)/2,360,delta=.01)
        self.assertIsNotNone(render(320,568,q,pages[-1].words[-1].start+.15).getbbox())

    def test_motion_starts_and_finishes_smoothly_at_60fps(self):
        self.assertEqual(motion_state(-.1,1,1)[0],0);self.assertEqual(motion_state(1,0,1)[0],0)
        self.assertEqual(motion_state(1,1,1),(1,0,0,1))
        for mode in ('in','out'):
            scales=[camera_state(i/60,mode)[0] for i in range(121)]
            self.assertLess(max(abs(b-a) for a,b in zip(scales,scales[1:])),.002)
            self.assertAlmostEqual(scales[-1],1.09 if mode=='in' else 1)
        # Short final words must read while all three lines remain in focus.
        q=next(q for q in sample_cues() if q.text=='Look closer at');t=q.words[-1].start+(q.end-q.words[-1].start)*.6
        leave=min(.12,max(.015,(q.end-q.words[-1].start)*.2))
        for w in q.words:self.assertEqual(motion_state(t-w.start,q.end-t,q.end-w.start,False,leave)[0],1)

    def test_short_headers_and_descenders_do_not_leave_odd_gaps(self):
        for text in ['glows softly at sunrise','to slow down.','and shines beneath the moon.','the world remembers.']:
            q=next(q for q in sample_cues() if q.text==text);plan=composition([w.text for w in q.words])
            colors={'header':'#F04444','main':'#1677FF','footer':'#8B5CF6'};word_colors=[None]*len(q.words)
            for row in plan['rows']:
                for i in row['words']:word_colors[i]=colors[row['role']]
            t=q.words[-1].start+(q.end-q.words[-1].start)*.65
            p=np.asarray(render(720,1280,q,t,word_colors=word_colors)).astype(int)
            masks={role:(np.abs(p[:,:,:3]-np.array([int(value[i:i+2],16) for i in (1,3,5)])).sum(axis=2)<25)&(p[:,:,3]>160) for role,value in colors.items()}
            main=masks['main'];ym,xm=np.where(main)
            for role in ('header','footer'):
                if not masks[role].any():continue
                ys,xs=np.where(masks[role]);gaps=[]
                # Retain the staggered design; balance the combined silhouette.
                foreground=np.logical_or.reduce(list(masks.values()))
                xx=np.where(foreground)[1]
                self.assertLessEqual(abs((xx.min()+xx.max())/2-360),3,text)
                for x in np.intersect1d(xm,xs):
                    a=np.where(main[:,x])[0];b=np.where(masks[role][:,x])[0]
                    gaps.append(a.min()-b.max() if role=='header' else b.min()-a.max())
                self.assertTrue(gaps,text);self.assertGreaterEqual(min(gaps),1,text);self.assertLessEqual(min(gaps),8,text)

    def test_manual_font_color_size_and_position_editing(self):
        q=CaptionCue((CaptionWord('Monument',0,2.5),),0,3)
        normal=draw_editor_caption(360,640,q,1,'caption_4','template',dict(x=.5,y=.42,size=1),'phrase')
        custom=draw_editor_caption(360,640,q,1,'caption_4','arial',dict(x=.4,y=.3,size=.7),'phrase',['#F04444'])
        self.assertLess(custom.getbbox()[2]-custom.getbbox()[0],normal.getbbox()[2]-normal.getbbox()[0]);self.assertLess(custom.getbbox()[1],normal.getbbox()[1])
        p=np.asarray(custom);self.assertGreater(int(((p[:,:,0]>180)&(p[:,:,1]<100)&(p[:,:,3]>180)).sum()),50)

    @unittest.skipUnless(shutil.which('node'),'Node is required for motion parity')
    def test_browser_and_export_share_each_motion_frame_and_word_role(self):
        source=(ROOT/'hinglish_captions/caption_four.js').read_text('utf8');code=source[source.index('  const normalize='):source.index('  const canvas=')]
        examples=[r['text'].split() for r in profile()['recipes']+profile()['demo_phrases']]+[[],['hello'],'A new story begins'.split()]
        states=[[i/60,left,available,main,leave] for i in range(-2,121) for left in (0,.03,.1,1) for available in (.08,1) for main in (False,True) for leave in (.015,.12)]
        cameras=[[i/60,mode] for i in range(-2,121) for mode in ('in','out')]
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;"+code+"console.log(JSON.stringify({plans:input.examples.map(planFor),states:input.states.map(a=>motionState(...a)),cameras:input.cameras.map(a=>cameraState(...a))}));"
        result=subprocess.run(['node','-e',(Path(__file__).resolve().parents[1]/'hinglish_captions/template_patterns.js').read_text('utf-8')+'\n'+script],input=json.dumps(dict(config=profile(),examples=examples,states=states,cameras=cameras)),capture_output=True,text=True,check=True);actual=json.loads(result.stdout)
        self.assertEqual(actual['plans'],[composition(w) for w in examples]);self.assertTrue(np.allclose(actual['states'],[motion_state(*a) for a in states],atol=1e-12,rtol=0));self.assertTrue(np.allclose(actual['cameras'],[camera_state(*a) for a in cameras],atol=1e-12,rtol=0))

if __name__=='__main__':unittest.main()
