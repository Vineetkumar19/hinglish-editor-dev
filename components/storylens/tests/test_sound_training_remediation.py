import unittest,json,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RemediationTests(unittest.TestCase):
    def module(self):
        s=importlib.util.spec_from_file_location('remediation',ROOT/'tools/sound_training/remediation.py')
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
    def test_old_failures_are_explicit_training_not_claimed_holdout(self):
        m=self.module();rows,coverage=m.build(ROOT)
        self.assertEqual(sum(r['source_kind']=='revision_original' for r in rows),304)
        corrections=[r for r in rows if r['source_kind']=='supervised_correction']
        self.assertEqual(len({r['correction_id'] for r in corrections}),20)
        self.assertTrue(all(r['previously_evaluated'] for r in corrections))
        for r in corrections:
            a=json.loads(r['messages'][-1]['content'])
            self.assertEqual(set(a),{'evidence','decision','timing','mix','uncertainty'})
        for r in rows:
            if r['source_kind']=='decision_curriculum':
                self.assertIn('evidence',json.loads(r['messages'][-1]['content']))
    def test_new_gate_not_seen_in_any_training_row(self):
        m=self.module();rows,_=m.build(ROOT);q={r['messages'][-2]['content'] for r in rows}
        self.assertEqual(len(m.GATE),8)
        self.assertTrue(all(question not in q for _,question,_,_ in m.GATE))
if __name__=='__main__':unittest.main()
