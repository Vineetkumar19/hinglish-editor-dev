"""Keyword banks are not finished automatic edits with one-second cut minimums."""
import copy,tempfile,unittest
from pathlib import Path
from hinglish_eval.specs import broll_checks

class ReviewQualityTests(unittest.TestCase):
    def test_subsecond_spoken_word_is_valid_for_bank_but_not_automatic_cut(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-review-quality';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            folder=Path(temporary);(folder/'clip.mp4').write_bytes(b'unit fixture, not native footage')
            project={'timeline':{'duration':50},'review_options':True,'summary':{},'slots':[
              {'start':16.24,'end':16.54,'text':'bed','visual':'bed','queries':['bed'],'clip':'clip.mp4',
               'source_duration':7,'source_in':3,'chosen':{'id':'bed','kind':'video','source':'pixabay','score':.9},
               'checks':[{'id':'bed','passed':True}]}]}
            def line(value):return next(c for c in broll_checks(folder,value) if c.rule=='broll.line_length')
            self.assertTrue(line(project).passed)
            ordinary=copy.deepcopy(project);ordinary['review_options']=False
            self.assertFalse(line(ordinary).passed)
            for start,end in ((16.54,16.24),(-.1,.2),(49.,51.)):
                broken=copy.deepcopy(project);broken['slots'][0].update(start=start,end=end)
                self.assertFalse(line(broken).passed)

if __name__=='__main__':unittest.main()
