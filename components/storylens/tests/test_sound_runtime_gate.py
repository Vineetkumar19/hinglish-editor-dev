import unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RuntimeGateTests(unittest.TestCase):
    def test_truncated_or_invalid_responses_cannot_pass_format(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'tools/sound_training/runtime_gate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertFalse(m.check_response({'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})['format_complete'])
        self.assertFalse(m.check_response({'choices':[{'finish_reason':'stop','message':{'content':'not json'}}]})['format_complete'])
        self.assertFalse(m.check_response({'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]})['format_complete'])
        import json
        answer={k:'a supported decision' for k in ('decision','timing','mix','uncertainty')}
        self.assertTrue(m.check_response({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]})['format_complete'])
    def test_cpu_only_runtime_is_rejected_before_loading_model(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'tools/sound_training/runtime_gate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertFalse(m.cuda_inventory_valid('Available devices: CPU'))
        self.assertTrue(m.cuda_inventory_valid('CUDA0: NVIDIA GeForce RTX 5070 Ti Laptop GPU'))
    def test_schema_and_adapter_are_bound_to_each_uncached_request(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'tools/sound_training/runtime_gate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        r=m.request_body('rules','new scene',0,1.0)
        self.assertEqual(r['response_format']['json_schema']['schema'],m.SCHEMA)
        self.assertFalse(r['cache_prompt'])
        self.assertEqual(r['lora'],[{'id':0,'scale':1.0}])
    def test_optional_reasoning_is_bounded_and_not_used_by_default(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'tools/sound_training/runtime_gate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertFalse(m.request_body('rules /no_think','scene',0,1)['chat_template_kwargs']['enable_thinking'])
        body=m.request_body('rules /no_think','scene',0,1,reasoning_budget=256)
        self.assertTrue(body['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('/no_think',body['messages'][0]['content'])
        self.assertEqual(body['max_tokens'],640)
        with self.assertRaises(ValueError):m.request_body('rules','scene',0,1,reasoning_budget=5000)
    def test_prompt_names_match_actual_required_schema_fields(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'tools/sound_training/runtime_gate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.FIELDS=('evidence','decision','timing','mix','uncertainty')
        text=m.system_prompt('Keep original instructions.')
        self.assertIn('evidence',text)
        self.assertNotIn('four fields',text)
        self.assertTrue(text.startswith('Keep original instructions.'))
    def test_baseline_comparison_is_retained_for_unseen_cases(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'tools/sound_training/runtime_gate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertEqual(m.variants('unseen',{'unseen'}),[('base',0.0),('adapter',1.0)])
        self.assertEqual(m.variants('trained',{'unseen'}),[('adapter',1.0)])
        self.assertEqual(m.variants('anything',None),[('base',0.0),('adapter',1.0)])
if __name__=='__main__':unittest.main()
