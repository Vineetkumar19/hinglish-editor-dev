import copy
import json
from pathlib import Path
import unittest

from hinglish_sound.teacher_memory import context
from hinglish_sound.reference_memory import inject, MARKER
from hinglish_cut.model_preferences import configure_request

ROOT=Path(__file__).resolve().parents[1]


class SoundTeachingMemoryTests(unittest.TestCase):
    def test_cards_keep_valid_source_evidence(self):
        guide=json.loads((ROOT/'hinglish_app/knowledge/sound_design_teaching.json').read_text('utf-8'))
        sources={s['id']:s for s in guide['sources']}
        original=json.loads((ROOT/'output/sound-training/20261030-revision2/sound_design_teaching.before.json').read_text('utf-8'))
        self.assertTrue({s['id'] for s in original['sources']} <= set(sources))
        for card in guide['lessons']:
            self.assertTrue(card['evidence'])
            for e in card['evidence']:
                if e.get('source')=='owner-direction-20261030':
                    self.assertIn('Teacher design guidance',e['kind'])
                    self.assertIn('hypotheses',e['kind'])
                    manifest=json.loads((ROOT/e['measured_artifacts']/'manifest.json').read_text('utf-8'))
                    self.assertEqual(set(e['files']),{r['sha256'] for r in manifest})
                    self.assertNotIn('start',e)
                    continue
                self.assertTrue(0<=e['start']<e['end']<=sources[e['source']]['seconds'])

    def test_relevant_retrieval_is_bounded_and_keeps_full_library(self):
        memory=context(ROOT,'music key pitch semitone tonal')
        self.assertIn('tonal-key-match',[x['id'] for x in memory['lessons']])
        self.assertLess(len(json.dumps(memory,ensure_ascii=False)),9000)
        self.assertTrue((ROOT/memory['complete_knowledge']).is_file())

    def test_sound_planner_and_vision_requests_keep_payload_and_schema(self):
        for model in ('storylens-meaning:14b','storylens-planner:9b-q6'):
            payload={'time':1.5,'creator_profile':{'name':'Owner','full':'Preserve the complete guidance'}}
            before=copy.deepcopy(payload)
            system=inject('Describe only observed pixels; return the required schema.',payload,ROOT,feature='sound')
            schema={'type':'object','properties':{'setting':{'type':'string'}}}
            body={'model':model,'format':schema,'messages':[{'role':'system','content':system},
                {'role':'user','content':json.dumps(payload),'images':['unchanged-image-data']}]}
            configure_request(ROOT,body)
            self.assertIn('Reviewed teaching reference retrieval',body['messages'][0]['content'])
            self.assertEqual(payload,before)
            self.assertEqual(body['format'],schema)
            self.assertEqual(body['messages'][1]['images'],['unchanged-image-data'])
            self.assertEqual(inject(system,payload,ROOT,feature='sound'),system)

    def test_unrelated_caption_request_stays_scoped(self):
        system=inject('Tool inventory includes Sound Design and Captions.',{'question':'Change my caption font'},ROOT)
        self.assertNotIn(MARKER,system)


if __name__=='__main__':unittest.main()
