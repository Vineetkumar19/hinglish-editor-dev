import tempfile
import unittest
from pathlib import Path
from hinglish_sound.library import Asset
from hinglish_sound.acoustic import candidate_slate


class CandidateVarietyTests(unittest.TestCase):
    def test_physical_identity_takes_priority_over_novelty(self):
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'foot.wav';a.write_bytes(b'foot')
            b=Path(temp)/'unknown.wav';b.write_bytes(b'unknown')
            foot=Asset(str(a),'sfx','foley','Forest footsteps','Footsteps walking on ground',6,-20,.1)
            unknown=Asset(str(b),'sfx','foley','Thud','unidentified thud',6,-20,.1)
            from hinglish_sound.acoustic import source_identity
            slate=candidate_slate([(foot,.8,''),(unknown,.9,'')],
                                  dict(type='foley',intent='walking through mud'),{source_identity(str(a)):99})
            self.assertEqual([row[0].path for row in slate],[str(a)])

    def test_unrelated_moments_get_more_than_the_same_six_files(self):
        with tempfile.TemporaryDirectory() as temp:
            hits=[]
            for n in range(18):
                path=Path(temp)/f'hit{n}.wav';path.write_bytes(bytes([n])*20)
                hits.append((Asset(str(path),'sfx','impact',path.stem,'low designed hit',.5,-20,.1),1-n*.01,'neutral'))
            history={}
            slates=[candidate_slate(hits,{'group_id':str(n)},history) for n in range(3)]
            self.assertEqual(len({a.path for slate in slates for a,_,_ in slate}),18)
            self.assertEqual(slates[0][0][0].path,hits[0][0].path)

    def test_duplicate_bytes_do_not_fill_distinct_candidate_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[Path(temp)/name for name in ('hit.wav','renamed.wav','other.wav')]
            for path,value in zip(paths,[b'same',b'same',b'other']):path.write_bytes(value)
            hits=[(Asset(str(p),'sfx','impact',p.stem,'hit',1,-20,.1),1,'neutral') for p in paths]
            self.assertEqual(len(candidate_slate(hits,{},{})),2)

    def test_declared_recurring_motif_keeps_ranked_choices_available(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'tick.wav';path.write_bytes(b'tick')
            asset=Asset(str(path),'sfx','poke','tick','dry tick',.2,-20,.05)
            moment=dict(group_id='first',type='poke',role='detail',reuse_key='list',reuse_reason='Recurring list punctuation')
            history={}
            a=candidate_slate([(asset,1,'neutral')],moment,history)
            b=candidate_slate([(asset,1,'neutral')],dict(moment,group_id='next'),history)
            self.assertEqual(a,b)


if __name__=='__main__':unittest.main()
