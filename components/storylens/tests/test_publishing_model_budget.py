import copy,json,tempfile,unittest
from pathlib import Path
from hinglish_cut import model_preferences as prefs

class PublishingModelBudgetTests(unittest.TestCase):
    def root(self):
        folder=Path('output/publisher-retry-repair-20261029/test-temp');folder.mkdir(parents=True,exist_ok=True)
        tmp=tempfile.TemporaryDirectory(dir=folder);self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        (root/'config.models.local.json').write_text(json.dumps({'context_limit':12288,'planning_model':'selected-local:14b'}))
        return root

    def body(self):
        return {'model':'selected-local:14b','messages':[{'role':'system','content':'Full creator guidance stays here.'},{'role':'user','content':'Choose one exact ID.'}],
                'format':{'type':'object'},'options':{'num_ctx':12288,'num_predict':1000}}

    def test_scoped_publishing_budget_preserves_payload_and_reserves_gpu_headroom(self):
        root=self.root();body=self.body();messages=copy.deepcopy(body['messages'])
        with prefs.publishing_memory_budget():prefs.configure_request(root,body)
        self.assertEqual(body['messages'],messages);self.assertEqual(body['model'],'selected-local:14b')
        self.assertEqual(body['options']['num_gpu'],28);self.assertEqual(body['options']['num_ctx'],4096)
        ordinary=self.body();prefs.configure_request(root,ordinary)
        self.assertEqual(ordinary['options']['num_ctx'],12288);self.assertNotIn('num_gpu',ordinary['options'])

    def test_larger_guidance_expands_context_instead_of_truncating_it(self):
        root=self.root();body=self.body();body['messages'][0]['content']='Owner exact guidance. '*700
        original=copy.deepcopy(body['messages'])
        with prefs.publishing_memory_budget():prefs.configure_request(root,body)
        self.assertEqual(body['messages'],original);self.assertGreater(body['options']['num_ctx'],4096)
        self.assertLessEqual(body['options']['num_ctx'],12288)

    def test_oversized_required_payload_stops_instead_of_dropping_saved_guidance(self):
        root=self.root();body=self.body();body['messages'][0]['content']='Required owner knowledge '*3000
        with prefs.publishing_memory_budget(),self.assertRaisesRegex(ValueError,'preserved'):
            prefs.configure_request(root,body)
