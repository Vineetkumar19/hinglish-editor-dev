"""Final request budgeting and saved exact-quote reduction, without inference."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from hinglish_publish.prepare_post_budget import PublishingBudget, ContextBudgetError, request_budget


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.brain = SimpleNamespace(model='fixture', name='fixture')
        self.recorder = Mock(name='recorder')
        self.recorder.name = 'fixture'
        self.recorder.json.side_effect = lambda system,data,schema,**kw: {'sentence_ids': list(range(min(2,len(data['sentences']))))}
        self.guard = PublishingBudget(self.root,self.brain,self.root,self.recorder,counter=lambda text:len(text)//2)
        def configure(root,body):
            body['options']['num_ctx'] = 4096
            # Verify the legacy estimate is replaced only inside this scope.
            from hinglish_cut.model_preferences import _publishing_budget
            self.assertFalse(_publishing_budget.get())
        patches = [patch('hinglish_aigen.direct.image_planning_context',side_effect=lambda root,s,d,sc,n:(s,d)),
                   patch('hinglish_niche.profiles.inject',side_effect=lambda s,d,root:(s+' full injected guidance',{**d,'creator_profile':{'all':'retained'}})),
                   patch('hinglish_cut.model_preferences.preferences',return_value={}),
                   patch('hinglish_cut.model_preferences.configure_request',side_effect=configure)]
        for p in patches:p.start();self.addCleanup(p.stop)

    def test_schema_reply_and_framing_count_against_the_same_context(self):
        body={'messages':[{'role':'user','content':'Hindi हिन्दी English'}],'format':{'enum':['exact','schema']},'options':{'num_ctx':1000,'num_predict':200}}
        seen=[]
        result=request_budget(body,lambda text:seen.append(text) or 401,framing=512)
        self.assertFalse(result['fits']);self.assertEqual(result['total_reserved'],1113)
        self.assertIn('हिन्दी',seen[0]);self.assertIn('schema',seen[0])

    def test_preview_counts_injected_profile_without_altering_caller_data(self):
        data={'spoken_content':'Exact speech.','creator_profile':{'saved':'original'}};before=deepcopy(data)
        budget=self.guard.preview('Write',data,{'type':'object'},{'max_tokens':1800,'think':False})
        self.assertEqual(budget['output_reserved'],1800);self.assertEqual(budget['context_limit'],4096)
        self.assertEqual(data,before)

    def test_oversized_final_body_is_blocked_before_transport(self):
        body={'messages':[{'role':'user','content':'x'*10000}],'format':{'type':'object'},'options':{'num_ctx':4096,'num_predict':1800}}
        with self.assertRaises(ContextBudgetError):self.guard(body)
        receipt=json.loads((self.root/'final-request-budget.json').read_text())
        self.assertFalse(receipt['fits']);self.assertEqual(body['options']['num_ctx'],4096)

    def test_oversized_source_reduces_through_saved_sentence_ids_and_reuses_them(self):
        speech='\n'.join(f'Source section {i} '+('word '*36)+'.' for i in range(70))
        data={'spoken_content':speech,'creator_profile':{'permanent':'keep'},'writing_preferences':{'all':'keep'}}
        options={'max_tokens':1000,'think':False};schema={'type':'object'}
        result=self.guard.prepare('Write',data,schema,options)
        self.assertLess(len(result['spoken_content']),len(speech))
        self.assertTrue(self.guard.preview('Write',result,schema,options)['fits'])
        self.assertEqual(result['creator_profile'],data['creator_profile'])
        self.assertEqual(result['writing_preferences'],data['writing_preferences'])
        original_lines=set(speech.splitlines())
        self.assertTrue(all(line in original_lines for line in result['spoken_content'].splitlines()))
        artifacts=list((self.root/'budget-source').rglob('source-context-v2-*.json'))
        self.assertGreater(len(artifacts),1)
        calls=self.recorder.json.call_count
        self.assertEqual(self.guard.prepare('Write',data,schema,options),result)
        self.assertEqual(self.recorder.json.call_count,calls)
        self.assertEqual(data['spoken_content'],speech)

    def test_guidance_alone_too_large_is_kept_and_no_reduction_call_is_started(self):
        data={'spoken_content':'Exact speech.','writing_preferences':{'complete':'x'*10000}}
        with self.assertRaisesRegex(ContextBudgetError,'guidance, schema and reply alone'):
            self.guard.prepare('Write',data,{'type':'object'},{'max_tokens':1000,'think':False})
        self.recorder.json.assert_not_called();self.assertEqual(len(data['writing_preferences']['complete']),10000)

    def test_nonmetadata_oversize_never_silently_truncates_inputs(self):
        data={'sentences':['x'*12000]}
        with self.assertRaises(ContextBudgetError):self.guard.prepare('Select',data,{'type':'object'},{'max_tokens':200,'think':False})
        self.assertEqual(len(data['sentences'][0]),12000);self.recorder.json.assert_not_called()

    def test_nonposting_service_boundary_reuses_engine_without_starting_delivery(self):
        from hinglish_app import prepare_post_http as http
        engine=SimpleNamespace(delivery_running=False,start_delivery=Mock())
        engine.start_delivery.side_effect=lambda:setattr(engine,'delivery_running',True)
        state=SimpleNamespace(publisher=SimpleNamespace(store=SimpleNamespace(list=lambda:[{'prepare_post_id':'saved','authorized_at':1,'status':'ready'}])))
        with patch.object(http,'PreparePost',return_value=engine):
            self.assertIs(http.service(state,recover_delivery=False),engine)
            self.assertIs(http.service(state,recover_delivery=False),engine)
            engine.start_delivery.assert_not_called()
            self.assertIs(http.service(state),engine);engine.start_delivery.assert_called_once()
        http._services.pop(id(state),None)

    def test_final_ollama_guard_runs_before_gpu_transport(self):
        from hinglish_visuals.brain import OllamaBrain
        brain=OllamaBrain.__new__(OllamaBrain)
        brain.root=self.root;brain.model='fixture';brain.name='fixture';brain.cache=self.root
        brain.cache_enabled=False;brain.session=Mock();brain.url='http://local';brain.progress=lambda _:None
        brain.request_guard=self.guard
        with patch('hinglish_visuals.brain.gpu_ollama_post') as transport:
            with self.assertRaises(ContextBudgetError):
                brain.json('Write',{'spoken_content':'x'*12000},{'type':'object'},max_tokens=1000,think=False)
            transport.assert_not_called()

    def test_fitting_final_payload_keeps_injected_guidance_schema_and_output_reserve(self):
        from hinglish_visuals.brain import OllamaBrain
        brain=OllamaBrain.__new__(OllamaBrain)
        brain.root=self.root;brain.model='fixture';brain.name='fixture';brain.cache=self.root
        brain.cache_enabled=False;brain.session=Mock();brain.url='http://local';brain.progress=lambda _:None
        brain.request_guard=self.guard
        response=Mock(status_code=200)
        response.json.return_value={'message':{'content':'{"title":"Exact"}'},'prompt_eval_count':100,'eval_count':10}
        schema={'type':'object','required':['title'],'properties':{'title':{'type':'string'}}}
        with patch('hinglish_visuals.brain.gpu_ollama_post',return_value=response) as transport:
            self.assertEqual(brain.json('Write',{'spoken_content':'Exact speech'},schema,max_tokens=1800,think=False),{'title':'Exact'})
        body=transport.call_args.kwargs['json']
        self.assertIn('full injected guidance',body['messages'][0]['content'])
        self.assertEqual(json.loads(body['messages'][1]['content'])['creator_profile'],{'all':'retained'})
        self.assertEqual(body['format'],schema);self.assertEqual(self.guard.last['output_reserved'],1800)
        self.assertTrue(self.guard.last['fits'])

