import unittest
from unittest.mock import Mock, patch

from hinglish_cut import ollama_runtime


class OllamaRuntimeTests(unittest.TestCase):
    def test_json_schema_and_sampling_contract_survive_endpoint_conversion(self):
        schema = {'type': 'object', 'properties': {'ids': {'type': 'array', 'items': {'type': 'integer'}}},
                  'required': ['ids'], 'additionalProperties': False}
        original = {'messages': [{'role': 'user', 'content': 'untrusted evidence'}],
                    'temperature': 0, 'seed': 0, 'max_tokens': 300,
                    'response_format': {'type': 'json_object', 'schema': schema}}
        converted = ollama_runtime.completion({'ollama_model': 'storylens-meaning:4b'}, original)
        self.assertEqual(converted['model'], 'storylens-meaning:4b')
        self.assertEqual(converted['messages'], original['messages'])
        self.assertEqual(converted['max_tokens'], 300)
        self.assertEqual(converted['temperature'], 0)
        self.assertEqual(converted['seed'], 0)
        self.assertEqual(converted['response_format']['type'], 'json_schema')
        self.assertEqual(converted['response_format']['json_schema']['schema'], schema)
        self.assertTrue(converted['response_format']['json_schema']['strict'])
        self.assertEqual(original['response_format']['type'], 'json_object')

    def test_missing_import_fails_without_falling_back_to_another_model(self):
        session = Mock()
        session.get.return_value.json.return_value = {'models': [{'name': 'qwen3.5:9b'}]}
        with patch.object(ollama_runtime.requests, 'Session', return_value=session):
            with self.assertRaisesRegex(ValueError, 'missing'):
                ollama_runtime.start({'ollama_model': 'storylens-meaning:4b'})
        self.assertFalse(session.trust_env)
        session.close.assert_called_once()

    def test_cloud_tag_is_rejected_before_connecting(self):
        with patch.object(ollama_runtime.requests, 'Session') as session:
            with self.assertRaises(ValueError):
                ollama_runtime.start({'ollama_model': 'qwen:cloud'})
            session.assert_not_called()

    def test_closing_unloads_only_the_imported_model(self):
        session = Mock()
        ollama_runtime.close(session, {'ollama_model': 'storylens-meaning:4b'})
        session.post.assert_called_once_with('http://127.0.0.1:11434/api/generate',
            json={'model': 'storylens-meaning:4b', 'keep_alive': 0}, timeout=60)


if __name__ == '__main__':
    unittest.main()
