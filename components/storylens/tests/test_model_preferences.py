import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hinglish_cut.model_preferences import configure_request, resolve_model


class ModelPreferenceTests(unittest.TestCase):
    def test_assistant_uses_machine_device_while_unconfigured_projects_keep_cpu(self):
        from hinglish_app.assistant_plan import job_payload
        step = {'tool': 'captions', 'options': {'caption_style': 'typography_4'}}
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(job_payload(step, [], root=folder)['device'], 'cpu')
            Path(folder, 'config.models.local.json').write_text('{"device":"cuda"}')
            payload = job_payload(step, [], root=folder)
            self.assertEqual(payload['device'], 'cuda')
            self.assertEqual(payload['caption_style'], 'typography_4')

    def test_unconfigured_project_keeps_existing_model_and_request(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(resolve_model(folder, 'planning_model', 'qwen3:8b', 'qwen3:8b'), 'qwen3:8b')
            request = {'options': {'num_ctx': 12288}, 'messages': [{'content': 'keep this'}]}
            self.assertEqual(configure_request(folder, dict(request)), request)

    def test_project_choice_applies_without_overriding_explicit_model_or_embedding(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'config.models.local.json').write_text(json.dumps({
                'planning_model': 'qwen3.5:9b', 'vision_model': 'qwen3.5:9b'}))
            self.assertEqual(resolve_model(folder, 'planning_model', 'qwen3:8b', 'qwen3:8b'), 'qwen3.5:9b')
            self.assertEqual(resolve_model(folder, 'vision_model', 'custom-vision:latest', 'qwen2.5vl:7b'), 'custom-vision:latest')
            self.assertEqual(resolve_model(folder, 'embedding_model', 'fixed-e5', 'fixed-e5'), 'fixed-e5')

    def test_memory_cap_preserves_messages_schema_and_explicit_thinking(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'config.models.local.json').write_text('{"context_limit":8192,"keep_alive":"30s"}')
            messages = [{'role': 'user', 'content': 'evidence', 'images': ['pixels']}]
            schema = {'type': 'object'}
            body = configure_request(folder, {'model': 'qwen3.5:9b', 'messages': messages, 'format': schema,
                                              'think': True, 'options': {'num_ctx': 12288, 'seed': 7}})
            self.assertEqual(body['options'], {'num_ctx': 8192, 'seed': 7})
            self.assertIs(body['messages'], messages)
            self.assertIs(body['format'], schema)
            self.assertTrue(body['think'])
            self.assertEqual(body['keep_alive'], '30s')

    def test_cloud_model_is_not_selected_by_local_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'config.models.local.json').write_text('{"planning_model":"large:cloud"}')
            with self.assertRaises(ValueError):
                resolve_model(folder, 'planning_model', 'qwen3:8b', 'qwen3:8b')

    def test_text_planner_upgrade_preserves_separate_vision_role(self):
        from hinglish_cut.model_preferences import preferences
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'config.model_storage.local.json').write_text(json.dumps({'active':True,'roles':{
                'planner':{'ollama_model':'larger-text:14b'},'vision':{'ollama_model':'vision:9b'},
                'meaning':{'ollama_model':'larger-text:14b'}}}))
            prefs=preferences(folder)
            self.assertEqual(prefs['planning_model'],'larger-text:14b')
            self.assertEqual(prefs['vision_model'],'vision:9b')

    def test_cuda_handoff_unloads_only_project_models(self):
        from hinglish_cut.model_preferences import release_ollama
        calls = []
        class Response:
            def json(self):
                return {'models': [{'name': 'qwen3.5:9b'}, {'name': 'unrelated-model:latest'}]}
            def raise_for_status(self):
                pass
        class Session:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get(self, *args, **kwargs): return Response()
            def post(self, url, **kwargs):
                calls.append(kwargs['json'])
                return Response()
        fake_requests = SimpleNamespace(Session=Session, RequestException=RuntimeError)
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'config.models.local.json').write_text(json.dumps({
                'planning_model': 'qwen3.5:9b', 'release_ollama_before_cuda': True}))
            with patch.dict('sys.modules', {'requests': fake_requests}):
                release_ollama(folder)
        self.assertEqual(calls, [{'model': 'qwen3.5:9b', 'keep_alive': 0}])

    def test_repeated_requests_keep_current_model_but_release_other_project_models(self):
        from hinglish_cut.model_preferences import release_ollama
        calls=[]
        class Response:
            def json(self):
                return {'models':[{'name':'selected:14b'},{'name':'planner:9b'},
                                  {'name':'someone-elses-model:latest'}]}
            def raise_for_status(self): pass
        class Session:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def get(self,*args,**kwargs): return Response()
            def post(self,url,**kwargs):
                calls.append(kwargs['json']);return Response()
        fake=SimpleNamespace(Session=Session,RequestException=RuntimeError)
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
            Path(folder,'config.models.local.json').write_text(json.dumps({
                'meaning_model':'selected:14b','planning_model':'planner:9b',
                'release_ollama_before_cuda':True}))
            with patch.dict('sys.modules',{'requests':fake}):
                release_ollama(folder,keep='selected:14b')
        self.assertEqual(calls,[{'model':'planner:9b','keep_alive':0}])


if __name__ == '__main__':
    unittest.main()
