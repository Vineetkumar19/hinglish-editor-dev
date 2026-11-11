import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from hinglish_visuals.brain import OllamaBrain


class StructuredOutputTests(unittest.TestCase):
    def test_publishing_decoder_recovery_uses_generate_and_rejects_invalid_schema(self):
        from jsonschema import ValidationError
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as root:
            brain,_=self.brain(root,[]);brain.model='storylens-publishing:fixture';brain.cache_enabled=False
            response=Mock(status_code=200);response.json.return_value={'response':'{"shorts":[]}'}
            brain.session.post.side_effect=None;brain.session.post.return_value=response
            schema={'type':'object','required':['shorts'],'properties':{'shorts':{'type':'array'}}}
            data={'source':'exact','previous_format_error':'expected peg-native format'}
            self.assertEqual(brain.json('select',data,schema,think=False),{'shorts':[]})
            args=brain.session.post.call_args
            self.assertTrue(args.args[0].endswith('/api/generate'))
            self.assertIn('exact',args.kwargs['json']['prompt'])
            self.assertEqual(args.kwargs['json']['format'],'json')
            self.assertIn(json.dumps(schema),args.kwargs['json']['system'])
            response.json.return_value={'response':'{"shorts":"wrong"}'}
            with self.assertRaises(ValidationError):brain.json('select',data,schema,think=False)
            self.assertIn('Fix this validation error',brain.session.post.call_args.kwargs['json']['prompt'])

    def brain(self,root,contents):
        brain=object.__new__(OllamaBrain);brain.root=Path(root);brain.model='fixture';brain.url='http://localhost';brain.progress=lambda _:None
        brain.name='fixture-local';brain.cache=Path(root)/'cache';brain.cache.mkdir();brain.session=Mock()
        bodies=[]
        def post(*args,**kwargs):
            bodies.append(copy.deepcopy(kwargs['json']))
            response=Mock(status_code=200);response.json.return_value={'message':{'content':contents.pop(0)}}
            return response
        brain.session.post.side_effect=post
        return brain,bodies

    def test_missing_final_answer_retries_once_without_thinking_and_caches_only_complete_answer(self):
        with tempfile.TemporaryDirectory() as root:
            brain,bodies=self.brain(root,['','{"shorts":[]}'])
            schema={'type':'object','required':['shorts']}
            self.assertEqual(brain.json('select',{},schema,think=True),{'shorts':[]})
            self.assertEqual([b['think'] for b in bodies],[True,False])
            self.assertEqual(brain.json('select',{},schema,think=True),{'shorts':[]})
            self.assertEqual(len(bodies),2)

    def test_incomplete_old_cache_is_not_reused_or_treated_as_no_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            brain,bodies=self.brain(root,['{"shorts":[]}','{"shorts":[]}'])
            schema={'type':'object','required':['shorts']}
            brain.json('select',{},schema,think=True)
            next(brain.cache.glob('*.json')).write_text('{"_thinking":"unfinished"}')
            brain.json('select',{},schema,think=True)
            self.assertEqual([b['think'] for b in bodies],[True,False])

    def test_no_final_answer_is_an_error_and_is_never_cached(self):
        with tempfile.TemporaryDirectory() as root:
            brain,bodies=self.brain(root,['',''])
            with self.assertRaisesRegex(RuntimeError,'No empty result was accepted'):
                brain.json('select',{}, {'type':'object','required':['shorts']},think=True)
            self.assertFalse(list(brain.cache.glob('*.json')))

    def test_local_server_error_keeps_reason_and_never_caches_failed_plan(self):
        with tempfile.TemporaryDirectory() as root:
            brain,bodies=self.brain(root,[])
            response=Mock(status_code=400);response.json.return_value={'error':'invalid JSON schema'}
            brain.session.post.side_effect=None;brain.session.post.return_value=response
            with self.assertRaisesRegex(RuntimeError,'HTTP 400.*invalid JSON schema'):
                brain.json('select',{}, {'type':'object','required':['shorts']})
            self.assertFalse(list(brain.cache.glob('*.json')))
            self.assertEqual(brain.session.post.call_count,1)


if __name__=='__main__':unittest.main()
