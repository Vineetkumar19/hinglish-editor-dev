"""Feature budgets must not leak into the protected publishing workflow."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class FeatureContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.policy = {'version': 1, 'models': {'text': 'local:14b', 'vision': 'local:9b'},
            'model_limits': {'text': 40960, 'vision': 32768},
            'deferred_features': ['assistant', 'shorts', 'gaming'],
            'features': {'broll': {'text': 40960}, 'visuals': {'text': 40960},
                'sound': {'text': 40960, 'vision': 16384},
                'thumbnail': {'text': 16384, 'text_max': 32768, 'vision': 16384},
                'assistant': {'text': 40960}, 'shorts': {'text': 40960}}}
        self.save()

    def save(self):
        (self.root/'config.context.local.json').write_text(json.dumps(self.policy))

    def body(self, model='local:14b'):
        return {'model': model, 'messages': [{'role': 'user', 'content': 'exact source and guidance'}],
            'format': {'type': 'object'}, 'options': {'num_ctx': 12288, 'num_predict': 2400}}

    def test_feature_changes_context_only_and_preserves_all_evidence(self):
        from hinglish_cut.feature_context import configure
        body = self.body(); before = copy.deepcopy(body)
        receipt = configure(self.root, body, 'broll', counter=lambda _: 20000)
        self.assertEqual(body['options']['num_ctx'], 40960)
        before['options']['num_ctx'] = 40960
        self.assertEqual(body, before)
        self.assertEqual(receipt['total_reserved'], 22912)

    def test_sound_only_model_override_keeps_other_models_and_large_request_capacity(self):
        from hinglish_cut.feature_context import configure,limits,ContextBudgetError
        self.policy['features']['sound'].update(text_model='trained:14b',text=12288,text_max=40960)
        self.save()
        self.assertEqual(limits(self.root,'sound'),(12288,40960,'trained:14b'))
        self.assertEqual(limits(self.root,'broll')[2],'local:14b')
        self.assertEqual(limits(self.root,'sound','vision')[2],'local:9b')
        body=self.body('trained:14b')
        self.assertEqual(configure(self.root,body,'sound',counter=lambda _: 19000)['context_limit'],40960)
        with self.assertRaises(ContextBudgetError):configure(self.root,self.body(),'sound',counter=lambda _:100)

    def test_deferred_and_unrelated_calls_remain_identical(self):
        from hinglish_cut.feature_context import configure
        for feature in (None, 'assistant', 'shorts', 'gaming', 'motion'):
            body = self.body(); before = copy.deepcopy(body)
            self.assertIsNone(configure(self.root, body, feature, counter=lambda _: 999999))
            self.assertEqual(body, before)

    def test_small_feature_expands_only_when_required(self):
        from hinglish_cut.feature_context import configure
        body = self.body()
        configure(self.root, body, 'thumbnail', counter=lambda _: 18000)
        self.assertEqual(body['options']['num_ctx'], 32768)

    def test_opted_in_sound_allocates_only_required_space_without_truncation(self):
        from hinglish_cut.feature_context import configure,ContextBudgetError
        self.policy['features']['sound'].update(text=12288,text_max=40960,adaptive_context=True)
        self.save()
        body=self.body();before=copy.deepcopy(body)
        receipt=configure(self.root,body,'sound',counter=lambda _:16000)
        self.assertEqual(body['options']['num_ctx'],20480)
        self.assertGreaterEqual(body['options']['num_ctx'],receipt['total_reserved'])
        self.assertEqual(body['messages'],before['messages'])
        self.assertEqual(body['format'],before['format'])
        self.assertEqual(body['options']['num_predict'],before['options']['num_predict'])
        self.assertEqual(configure(self.root,self.body(),'broll',counter=lambda _:16000)['context_limit'],40960)
        with self.assertRaises(ContextBudgetError):configure(self.root,self.body(),'sound',counter=lambda _:40500)

    def test_oversized_required_input_is_never_sent_or_truncated(self):
        from hinglish_cut.feature_context import configure, ContextBudgetError
        body = self.body(); messages = copy.deepcopy(body['messages'])
        with self.assertRaisesRegex(ContextBudgetError, 'context'):
            configure(self.root, body, 'broll', counter=lambda _: 40500)
        self.assertEqual(body['messages'], messages)

    def test_vision_is_explicit_and_unavailable_for_broll_visuals(self):
        from hinglish_cut.feature_context import configure
        for feature in ('broll', 'visuals'):
            with self.assertRaisesRegex(ValueError, 'vision'):
                configure(self.root, self.body('local:9b'), feature, kind='vision')
        body = self.body('local:9b')
        body['messages'][0]['images'] = ['actual-pixels']
        receipt = configure(self.root, body, 'sound', kind='vision')
        self.assertEqual(body['options']['num_ctx'], 16384)
        self.assertEqual(receipt['count_basis'], 'vision capacity; image token usage measured by runtime')

    def test_wrong_model_and_unverified_yarn_are_rejected(self):
        from hinglish_cut.feature_context import configure
        with self.assertRaisesRegex(ValueError, 'model'):
            configure(self.root, self.body('different:14b'), 'broll', counter=lambda _: 1)
        self.policy['features']['broll']['text'] = 131072; self.save()
        with self.assertRaisesRegex(ValueError, 'verified'):
            configure(self.root, self.body(), 'broll', counter=lambda _: 1)

    def test_activation_after_completion_enables_assistant(self):
        from hinglish_cut.feature_context import configure
        self.policy['deferred_features'] = []; self.save()
        body = self.body()
        configure(self.root, body, 'assistant', counter=lambda _: 20000)
        self.assertEqual(body['options']['num_ctx'], 40960)

    def planner(self):
        from tests.test_brain_structured_output import StructuredOutputTests
        brain, bodies = StructuredOutputTests().brain(self.root, ['{"ok":true}'])
        brain.model = 'local:14b'; brain.name = 'Ollama local:14b'; brain.context_feature = 'broll'
        return brain, bodies

    def test_real_planner_transport_receives_feature_budget_and_usage(self):
        brain, bodies = self.planner()
        with patch('hinglish_cut.feature_context.token_counter', return_value=lambda _: 20000):
            brain.json('Follow all instructions.', {'script': 'exact original'}, {'required': ['ok']})
        self.assertEqual(bodies[0]['options']['num_ctx'], 40960)
        self.assertEqual(brain.last_context_budget['feature'], 'broll')

    def test_real_planner_blocks_overflow_before_transport(self):
        from hinglish_cut.feature_context import ContextBudgetError
        brain, bodies = self.planner()
        with patch('hinglish_cut.feature_context.token_counter', return_value=lambda _: 50000):
            with self.assertRaises(ContextBudgetError):
                brain.json('Instructions', {'script': 'keep this'}, {'required': ['ok']})
        self.assertEqual(bodies, [])

    def test_registered_publishing_guard_always_takes_precedence(self):
        from types import SimpleNamespace
        brain, bodies = self.planner()
        brain.request_guard = SimpleNamespace(configure=lambda b: b['options'].update(num_ctx=40960))
        with patch('hinglish_cut.feature_context.token_counter', side_effect=AssertionError('protected workflow')):
            brain.json('Instructions', {}, {'required': ['ok']})
        self.assertEqual(bodies[0]['options']['num_ctx'], 40960)

    def test_sound_transport_has_full_source_and_reply_space(self):
        from tests.test_sound_brain_runtime import BrainRuntimeTests
        from types import SimpleNamespace
        fixture=BrainRuntimeTests()
        response=SimpleNamespace(status_code=200,json=lambda:{'message':{'content':'{"answer":"ok"}'}})
        brain=fixture.brain(self.root,response);brain.model='local:14b'
        with patch('hinglish_cut.feature_context.token_counter', return_value=lambda _: 23000):
            brain.ask('Sound direction',{'script':'entire story'}, {'type':'object'},think=False)
        self.assertEqual(fixture.calls[0]['options']['num_ctx'],40960)
        self.assertIn('entire story',fixture.calls[0]['messages'][1]['content'])

    def test_error_catalog_explains_overflow_without_raw_diagnostics(self):
        from hinglish_app.user_messages import problem,catalog
        from hinglish_cut.feature_context import ContextBudgetError
        catalog.cache_clear()
        result=problem(ContextBudgetError('This broll step needs 50,000 tokens including its reply, beyond its context.'))
        self.assertEqual(result['code'],'feature_context_full')
        self.assertIn('saved',result['message'].lower())

    def test_new_chat_history_retains_long_messages_only_after_activation(self):
        from hinglish_cut.feature_context import history_options
        self.assertEqual(history_options(self.root),{})
        self.policy['deferred_features']=[];self.save()
        self.assertEqual(history_options(self.root),{'exchanges':20,'text_limit':None})

    def test_long_source_summary_covers_all_source_characters(self):
        from hinglish_cut.source_context import complete_summary
        from types import SimpleNamespace
        seen=[]
        def ask(system,data,schema,**kw):
            seen.append(data['source']);return {'summary':'Reviewed section '+str(len(seen))}
        brain=SimpleNamespace(root=self.root,model='local:14b',json=ask,context_feature='broll')
        original=''.join(f'Line {i}: exact event and its result.\n' for i in range(5000))
        with patch('hinglish_cut.source_context.token_counter',return_value=lambda text: len(text)//2):
            result=complete_summary(brain,original,lambda _:None)
        self.assertEqual(''.join(seen),original)
        self.assertIn('Reviewed section',result)

    def test_normal_source_summary_keeps_full_original(self):
        from hinglish_cut.source_context import complete_summary
        from types import SimpleNamespace
        brain=SimpleNamespace(root=self.root,model='local:14b',context_feature='broll',json=lambda *a: self.fail('unneeded generation'))
        with patch('hinglish_cut.source_context.token_counter',return_value=lambda _: 100):
            self.assertEqual(complete_summary(brain,'Every original word.',lambda _:None),'Every original word.')


if __name__ == '__main__': unittest.main()
