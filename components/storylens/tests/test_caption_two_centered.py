import json
from pathlib import Path
import subprocess
import unittest

import numpy as np

from hinglish_captions.caption_one import font, text_metrics
from hinglish_captions.caption_two import composition, profile, render, page_ranges, paginate_cue, group_scale
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.scene_capture import capture, words as captured_words
from hinglish_captions.template_patterns import pattern_context

ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=[
    'Paste your text, choose a template,',
    'duration and format, then press Create preview.',
    'and template back for another check.',
    'Rebuilt the upward blurred entrances, tight',
    'English preview,',
    'Downloaded and installed the matched fonts.',
    'anything I want to do.',
    'the and to',
    'Apni kahani ko duniya tak pahunchao',
]


def cue_for(text,slot=0):
    return CaptionCue(tuple(CaptionWord(w,i*.15,(i+1)*.15) for i,w in enumerate(text.split())),0,3,text,slot)


class CaptionTwoCenteredTests(unittest.TestCase):
    def test_content_emphasis_and_balanced_reference_keep_every_word(self):
        for slot,text in enumerate(EXAMPLES):
            cue=cue_for(text,slot)
            with pattern_context(cue):plan=composition(text.split())
            self.assertEqual([i for row in plan['rows'] for i in row['words']],list(range(len(cue.words))))
            self.assertTrue(plan['balanced_reference'])
            self.assertLessEqual(len(plan['rows']),4)
            self.assertFalse(plan['strike']);self.assertFalse(plan['record']);self.assertFalse(plan['plane'])
            self.assertFalse(any(row['role']=='card' for row in plan['rows']))
            for row in plan['rows']:
                if row['role']=='main':
                    self.assertTrue(any(''.join(c for c in cue.words[i].text.lower() if c.isalnum()) not in profile()['keyword_stop_words'] for i in row['words']))
                self.assertTrue(all(''.join(c for c in cue.words[i].text.lower() if c.isalnum()) not in profile()['keyword_stop_words'] for i in row.get('green',[])))
            if text=='the and to':self.assertFalse(any(row['role']=='main' for row in plan['rows']))

    def test_complete_group_is_balanced_with_no_collisions_or_red(self):
        for slot,text in enumerate(EXAMPLES):
            cue=cue_for(' '.join(text.split()[:5]),slot)
            with pattern_context(cue):plan=composition(cue.text.split())
            for seconds in (.1,.3,.65,1.1,2.5):
                with pattern_context(cue),capture():image=render(360,640,cue,seconds,position=.65)
                marks=captured_words(image);boxes=[]
                for row in plan['rows']:
                    bounds=[]
                    for mark in marks:
                        if mark['index'] not in row['words'] or mark['alpha']<.05:continue
                        selected=font(mark['font_path'],mark['size_px'])
                        _,left,right=text_metrics(selected.path,selected.size,mark['text'],mark['tracking'])
                        glyphs=[selected.getbbox(c) for c in mark['text'] if not c.isspace()]
                        offsets=[selected.getlength(mark['text'][:j])+j*selected.size*mark['tracking'] for j,c in enumerate(mark['text']) if not c.isspace()]
                        bbox_left=min(b[0]+x for b,x in zip(glyphs,offsets));bbox_right=max(b[2]+x for b,x in zip(glyphs,offsets))
                        cx=mark['x']+((left+right-bbox_left-bbox_right)/2)*mark['sx']
                        w=(right-left)*mark['sx'];h=(max(b[3] for b in glyphs)-min(b[1] for b in glyphs))*mark['sy']
                        bounds.append((cx-w/2,mark['y']-h/2,cx+w/2,mark['y']+h/2))
                    if bounds:
                        box=(min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds));boxes.append(box)
                        self.assertGreater(box[0],10);self.assertLess(box[2],350)
                # Split headers occupy the same band; their horizontal gap
                # replaces a vertical gap. Only judge settled complete text.
                if seconds==2.5 and boxes:
                    self.assertAlmostEqual((min(b[0] for b in boxes)+max(b[2] for b in boxes))/2,180,delta=.8,msg=text)
                    for i,a in enumerate(boxes):
                        for b in boxes[i+1:]:
                            self.assertTrue(a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1],(text,boxes))
                pixels=np.asarray(image).astype(int)
                red=(pixels[:,:,0]>pixels[:,:,1]*1.5)&(pixels[:,:,0]>120)&(pixels[:,:,3]>100)
                self.assertFalse(red.any(),(text,seconds))

    def test_long_saved_cues_keep_every_word_with_five_word_pages(self):
        for count in range(1,41):
            text=' '.join('word'+str(i) for i in range(count));cue=cue_for(text,4)
            pages=paginate_cue(cue)
            self.assertTrue(all(1<=len(page.words)<=5 for page in pages))
            self.assertEqual([w for page in pages for w in page.words],list(cue.words))
            self.assertTrue(all(page.template_source==text and page.template_slot==4 for page in pages))
            self.assertTrue(all(a.end==b.start for a,b in zip(pages,pages[1:])))
            if count>5:self.assertGreaterEqual(min(len(page.words) for page in pages),3)

    def test_function_word_replacement_retains_split_header_design(self):
        cue=cue_for('Updated and saved Caption 2',0)
        with pattern_context(cue):plan=composition(cue.text.split())
        self.assertEqual([r.get('align','main') for r in plan['rows']],['top_left','main','top_right','bottom'])
        self.assertEqual(next(r['words'] for r in plan['rows'] if r['role']=='main'),[2])
        self.assertEqual(profile()['visible_ink_gap'],2.7)

    def test_reference_type_hierarchy_and_entrance_directions_survive(self):
        for recipe in profile()['recipes']:
            plan=composition(recipe['text'].split())
            self.assertEqual(plan['main_size'],recipe['main_size'])
            self.assertEqual([r.get('size') for r in plan['rows']],[r.get('size') for r in recipe['rows']])
            self.assertEqual([r.get('enter_y') for r in plan['rows']],[r.get('enter_y') for r in recipe['rows']])
            self.assertEqual([r.get('regular') for r in plan['rows']],[r.get('regular') for r in recipe['rows']])
            self.assertEqual(plan['motion'],recipe['motion'])

    def test_measured_camera_keeps_growing_and_shrinking_patterns_distinct(self):
        shrink=composition('If the Prospects have to meet you'.split())
        grow=composition('to Understand your value'.split())
        self.assertGreater(group_scale(shrink,0),group_scale(shrink,1))
        self.assertLess(group_scale(grow,0),group_scale(grow,1))
        cue=cue_for('Learn what your audience values',1)
        with pattern_context(cue):changed=composition(cue.text.split())
        self.assertEqual(changed['camera_keys'],grow['camera_keys'])

    def test_preview_and_export_choose_identical_rows_for_every_slot(self):
        code=(ROOT/'hinglish_captions/caption_two.js').read_text('utf-8')
        functions=code[code.index('  const normalize='):code.index('  const canvas=')]
        pattern=(ROOT/'hinglish_captions/template_patterns.js').read_text('utf-8')
        cases=[dict(words=text.split(),slot=slot,source=text) for slot in range(9) for text in EXAMPLES]
        script="const input=JSON.parse(require('fs').readFileSync(0,'utf8')),config=input.config;let cues=[],video={currentTime:1};"+pattern+functions+"console.log(JSON.stringify(input.cases.map(c=>{cues=[{start:0,end:3,template_source:c.source,template_slot:c.slot}];return {plan:planFor(c.words),pages:pageRanges(c.words)}})));"
        result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script],input=json.dumps(dict(config=profile(),cases=cases)),capture_output=True,text=True,check=True)
        expected=[]
        for case in cases:
            with pattern_context(cue_for(case['source'],case['slot'])):expected.append(dict(plan=composition(case['words']),pages=[list(r) for r in page_ranges(case['words'])]))
        self.assertEqual(json.loads(result.stdout),expected)


if __name__=='__main__':unittest.main()
