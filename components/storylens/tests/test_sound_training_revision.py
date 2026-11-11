import unittest
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
class RevisionTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('revision',ROOT/'tools/sound_training/revision.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def test_every_original_teaching_row_is_preserved(self):
        m=self.module();rows,coverage=m.build(ROOT)
        self.assertEqual(sum(r['source_kind']=='revision_original' for r in rows),304)
        self.assertEqual(len(coverage),40)
    def test_complete_decisions_are_majority_of_added_scenarios(self):
        m=self.module();rows,_=m.build(ROOT)
        scenarios=[r for r in rows if r['source_kind']=='revision_scenario']
        self.assertGreaterEqual(len(scenarios),25)
        for row in scenarios:
            answer=row['messages'][-1]['content']
            for field in ('Evidence:', 'Choice:', 'Timing:', 'Mix:', 'Check:'):
                self.assertIn(field,answer)
    def test_reference_hypotheses_are_not_taught_as_heard_facts(self):
        m=self.module();rows,_=m.build(ROOT)
        for r in rows:self.assertFalse(r['audio_quality_verified'])
        self.assertTrue(all(r['source_kind']!='reference_audio_fact' for r in rows))
    def test_fresh_gate_not_in_training(self):
        m=self.module();rows,_=m.build(ROOT)
        questions={r['messages'][-2]['content'] for r in rows}
        self.assertGreaterEqual(len(m.GATE),8)
        self.assertTrue(all(q not in questions for _,q,_,_ in m.GATE))
if __name__=='__main__':unittest.main()
