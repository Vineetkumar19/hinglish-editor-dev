import unittest,json,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DecisionsTests(unittest.TestCase):
    def module(self):
        s=importlib.util.spec_from_file_location('decisions',ROOT/'tools/sound_training/decisions.py')
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
    def test_original_lessons_preserved_and_decisions_structured(self):
        m=self.module();rows,coverage=m.build(ROOT)
        self.assertEqual(sum(r['source_kind']=='revision_original' for r in rows),304)
        self.assertEqual(len(coverage),40)
        applied=[r for r in rows if r['source_kind']=='decision_curriculum']
        self.assertGreaterEqual(len({r['curriculum_case'] for r in applied}),44)
        for r in applied:
            self.assertEqual(set(json.loads(r['messages'][-1]['content'])),{'decision','timing','mix','uncertainty'})
            self.assertFalse(r['audio_quality_verified'])
    def test_fresh_gate_is_disjoint_and_requires_grounded_timing(self):
        m=self.module();rows,_=m.build(ROOT);questions={r['messages'][-2]['content'] for r in rows}
        self.assertEqual(len(m.GATE),8)
        self.assertTrue(all(q not in questions for _,q,_,_ in m.GATE))
        self.assertIn('relative',m.SYSTEM.lower())
        self.assertIn('decay',m.SYSTEM.lower())
if __name__=='__main__':unittest.main()
