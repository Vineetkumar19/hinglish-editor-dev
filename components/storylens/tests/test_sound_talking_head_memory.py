import unittest
from pathlib import Path
from hinglish_sound.teacher_memory import context
ROOT=Path(__file__).resolve().parents[1]
class TalkingHeadMemoryTests(unittest.TestCase):
    def test_selective_caption_sound_guidance_is_retrieved(self):
        result=context(ROOT,'talking-head typography subtitles letters pop captions',limit=6)
        ids={r['id'] for r in result['lessons']}
        self.assertIn('talking-head-selective-accents-20261030',ids)
    def test_existing_teaching_guidance_is_preserved(self):
        import json
        saved=json.loads((ROOT/'hinglish_app/knowledge/sound_design_teaching.json').read_text(encoding='utf-8'))
        self.assertIn('negative-space',{x['id'] for x in saved['lessons']})
        row=next(x for x in saved['lessons'] if x['id']=='talking-head-selective-accents-20261030')
        self.assertIn('hypotheses',str(row['evidence']))
    def test_scene_facts_and_editorial_proposals_are_separate_in_shared_guidance(self):
        core=' '.join(context(ROOT,'sound layers')['core']).lower()
        self.assertIn('physical ambience',core)
        self.assertIn('editorial contrast',core)
        self.assertIn('event evidence',core)
    def test_new_timeline_reference_lessons_are_available_by_role(self):
        expected={
            'timeline overlapping staggered roles':'timeline-role-ensembles-20261030',
            'offset peak alignment source trim':'timeline-source-offset-20261030',
            'continuous ambience bridge cuts':'timeline-scene-continuity-20261030',
        }
        for query,identity in expected.items():
            self.assertIn(identity,{r['id'] for r in context(ROOT,query)['lessons']})
    def test_physical_action_duration_is_not_a_tail_cutoff(self):
        core=' '.join(context(ROOT,'foley tail')['core']).lower()
        self.assertIn('action duration is not the total clip limit',core)
        self.assertIn('no universal minimum duration',core)
    def test_gain_domains_keep_added_effects_independent(self):
        core=' '.join(context(ROOT,'mix original speech music separate Foley gain')['core']).lower()
        self.assertIn('original-source gain affects only that source',core)
        self.assertIn('master gain affects all routed layers',core)
if __name__=='__main__':unittest.main()
