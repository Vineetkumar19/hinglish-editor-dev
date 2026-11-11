import copy
import json
from unittest.mock import patch
from tests.base import SuiteCase
from core.workflow_service import WorkflowService
from core.workflow_brain import plan, validate_plan
from core.llm import LLMError


GOOD = {'summary':'Review selected evidence','steps':[{'description':'Proposed lab','source_quote':''}],
    'questions':[],'draft_reply':'','exercise':'Compare two local outputs and retain hashes.','limitations':[]}


class BrainBoundaryTests(SuiteCase):
    def task(self):
        service=WorkflowService(self.store)
        return service,service.create('learning_evidence','Source-backed lab',
            {'goal':'Review contracts','period':'Today','_brain':'chatgpt','entries':[
                {'description':'Read the exact-payload contract','stage':'reading','context':'personal_lab','source_ref':'fixture:reading'}]},'brain-case')

    def test_proposed_step_empty_quote_is_valid(self):
        self.assertEqual(validate_plan(copy.deepcopy(GOOD)),GOOD)

    def test_missing_evidence_quote_fails_without_fallback(self):
        _,task=self.task()
        invalid=copy.deepcopy(GOOD); invalid['steps'][0]['source_quote']='Invented payment of 50000'
        with patch('core.workflow_brain.ChatGPTProvider.complete',return_value=(json.dumps(invalid),(10,20))), patch('core.workflow_brain.OllamaProvider') as local:
            with self.assertRaises(LLMError): plan(self.store,task,'chatgpt')
            local.assert_not_called()

    def test_plan_cache_does_not_execute_tools_or_call_model_again(self):
        _,task=self.task()
        with patch('core.workflow_brain.ChatGPTProvider.complete',return_value=(json.dumps(GOOD),(10,20))) as complete:
            first=plan(self.store,task,'chatgpt'); second=plan(self.store,task,'chatgpt')
            self.assertTrue(second['reused_saved_plan']); self.assertEqual(complete.call_count,1)
            self.assertEqual(first['external_actions'],0)
        self.assertEqual(self.store.query('SELECT * FROM suite_actions'),[])

    def test_planning_failure_is_visible_and_does_not_create_approval(self):
        service,task=self.task()
        with patch('core.workflow_brain.ChatGPTProvider.complete',side_effect=LLMError('Sign-in expired')):
            result=service.prepare(task['task_id'])
        self.assertEqual(result['state'],'failed')
        self.assertIn('Sign-in expired',result['result']['error'])
        self.assertEqual(self.store.query('SELECT * FROM suite_reviews'),[])

    def test_reading_remains_reading_after_brain_plan(self):
        service,task=self.task()
        with patch('core.workflow_brain.ChatGPTProvider.complete',return_value=(json.dumps(GOOD),(10,20))):
            result=service.prepare(task['task_id'])
        self.assertEqual(result['state'],'waiting_for_review')
        self.assertEqual(result['result']['prepared']['entries'][0]['stage'],'reading')
        self.assertFalse(result['result']['prepared']['client_experience_claim'])
