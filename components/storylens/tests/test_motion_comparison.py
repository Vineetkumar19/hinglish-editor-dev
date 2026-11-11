import unittest
from hinglish_motion.comparison import timed_lines
from hinglish_motion.native_engines import scene_graph

class ComparisonTests(unittest.TestCase):
    def test_exact_requested_clock_preserves_words(self):
        sections=[{'spoken':'Ek do teen.','direction':'Camera'},{'spoken':'One more full line.','direction':'Wide'}]
        lines=timed_lines(sections,50)
        self.assertEqual(lines[0].start,0);self.assertEqual(lines[-1].end,50)
        self.assertEqual(lines[0].end,lines[1].start)
        self.assertEqual([l.text for l in lines],[s['spoken'] for s in sections])
    def test_source_caption_has_its_own_band(self):
        s={'template':'motion_title','duration':8,'data':{'title':'Madurai nightlife','label':'Ten at night','source_caption':'Log mujhe poochte hain bhai Madurai mein nightlife kaisi hai?'}}
        graph=scene_graph(s,360,640,30)
        cap=next(n for n in graph['nodes'] if n['id']=='source-caption')
        self.assertEqual(cap['text'].replace('\n',' '),s['data']['source_caption'])
        self.assertTrue(all(n['y']+n['h']<=cap['y'] for n in graph['nodes'] if n['id']!='source-caption' and not n.get('parent')))

if __name__=='__main__':unittest.main()
