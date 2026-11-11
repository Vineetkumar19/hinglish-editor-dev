import unittest
from pathlib import Path
from tools.sound_training import timeline_curriculum as curriculum
from tools.sound_training.train import validate_split

ROOT=Path(__file__).resolve().parents[1]

class TimelineCurriculumTests(unittest.TestCase):
    def test_new_lessons_preserve_rehearsal_and_have_distinct_evaluation(self):
        rows,holdout=curriculum.build(ROOT)
        validate_split(rows,holdout)
        self.assertGreaterEqual(len(curriculum.CASES),12)
        self.assertGreaterEqual(len(holdout),6)
        self.assertTrue(any(x.get('rehearsal') for x in rows))
        new=[x for x in rows if x.get('source_kind')=='timeline_teacher_example']
        self.assertTrue(all(x['synthetic'] and not x['audio_quality_verified'] for x in new))
        self.assertTrue(all(len(x['reference_sha256'])==3 for x in new))
        self.assertNotIn('fixed five-layer template',' '.join(x['messages'][-1]['content'] for x in new))

    def test_timestamp_calculation_and_negative_examples_are_present(self):
        rows,_=curriculum.build(ROOT)
        cases={x.get('case_id'):x for x in rows if 'case_id' in x}
        self.assertIn('9.55',cases['attack_alignment']['messages'][-1]['content'])
        for identity in ['same_scene_bridge','five_not_quota','mixed_source_once','uncertain_labels','voice_masking','water_context','cricket_context']:
            self.assertIn(identity,cases)
