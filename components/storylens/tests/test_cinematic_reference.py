import unittest
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.cinematic_reference import pages,render

class CinematicReferenceTests(unittest.TestCase):
    def test_aspect_limits_preserve_words_and_original_boundaries(self):
        words=tuple(CaptionWord(w,i*.4,(i+1)*.4) for i,w in enumerate('one two three four five six seven eight nine ten eleven'.split()))
        cue=CaptionCue(words,0,5)
        for width,height,limit in ((720,1280,4),(1280,720,7)):
            result=pages(cue,width,height)
            self.assertEqual([w for p in result for w in p.words],list(words))
            self.assertTrue(all(len(p.words)<=limit for p in result))
            self.assertTrue(all(a.end==b.start for a,b in zip(result,result[1:])))
    def test_both_local_export_engines_draw_and_end_cleanly(self):
        cue=CaptionCue((CaptionWord('Stories',0,1),CaptionWord('matter',.5,2)),0,2)
        for style in ('cinematic_mixed_draft','cinematic_clean_draft'):
            self.assertIsNotNone(render(640,360,cue,1,style).getbbox())
            self.assertIsNone(render(640,360,cue,2,style).getbbox())
