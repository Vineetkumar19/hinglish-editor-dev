import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('sound_training_corpus',ROOT/'tools/sound_training/corpus.py')
        cls.mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_each_row_has_supervised_target(self):
        rows,_=self.mod.build_corpus(ROOT)
        self.assertGreater(len(rows),100)
        for row in rows:
            self.assertEqual([m['role'] for m in row['messages']],['system','user','assistant'])
            self.assertTrue(all(m['content'].strip() for m in row['messages']))

    def test_all_instructional_pages_accounted_for(self):
        rows,coverage=self.mod.build_corpus(ROOT)
        self.assertEqual(len(coverage),40)
        self.assertTrue(all(c['status'] in ('included','reference_only') for c in coverage))
        self.assertTrue(all(c.get('reason') for c in coverage if c['status']=='reference_only'))
        for n in range(3,28):
            self.assertTrue(any(r['source_page']==n for r in rows))

    def test_no_operational_inventory_memorization(self):
        rows,_=self.mod.build_corpus(ROOT)
        answers='\n'.join(r['messages'][-1]['content'] for r in rows)
        self.assertNotIn('2,216 indexed SFX',answers)
        self.assertNotIn('9ade0cafcfa6',answers)

    def test_seed_contract_rejects_out_of_bounds(self):
        row=self.mod.load_seeds(ROOT)[0]
        target=json.loads(row['chosen'])
        target['cues'][0]['duration_s']=999
        row['chosen']=json.dumps(target)
        with self.assertRaises(ValueError):self.mod.validate_seed(row)

    def test_seed_contract_rejects_unknown_source(self):
        row=self.mod.load_seeds(ROOT)[0]
        target=json.loads(row['chosen']);target['cues'][0]['asset_id']='made_up'
        row['chosen']=json.dumps(target)
        with self.assertRaises(ValueError):self.mod.validate_seed(row)

    def test_seed_contract_rejects_boolean_time(self):
        row=self.mod.load_seeds(ROOT)[0]
        target=json.loads(row['chosen']);target['cues'][0]['timeline_start_s']=True
        row['chosen']=json.dumps(target)
        with self.assertRaises(ValueError):self.mod.validate_seed(row)

    def test_deterministic_unique_ids(self):
        a,_=self.mod.build_corpus(ROOT);b,_=self.mod.build_corpus(ROOT)
        self.assertEqual(a,b)
        self.assertEqual(len(a),len({r['id'] for r in a}))

    def test_seeds_remain_honestly_synthetic(self):
        rows,_=self.mod.build_corpus(ROOT)
        seeds=[r for r in rows if r['source_kind']=='synthetic_concept']
        self.assertEqual(len(seeds),12)
        self.assertTrue(all('fictional' in r['messages'][1]['content'] for r in seeds))
        self.assertTrue(all(not r['audio_quality_verified'] for r in seeds))

    def test_online_retrieval_lessons_are_not_price_memorization(self):
        rows,_=self.mod.build_corpus(ROOT)
        online=[r for r in rows if r['source_kind']=='online_retrieval_policy']
        self.assertGreaterEqual(len(online),8)
        answers=' '.join(r['messages'][-1]['content'] for r in online)
        self.assertIn('current provider status',answers)
        self.assertIn('license',answers)
        self.assertNotIn('10,000',answers)

if __name__=='__main__':unittest.main()
