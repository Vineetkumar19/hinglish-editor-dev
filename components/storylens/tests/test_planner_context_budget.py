import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from hinglish_app.assistant_plan_context import ask,fit


class PlannerContextBudgetTests(unittest.TestCase):
    def test_oversized_edit_only_omits_unrelated_distribution_and_browser_background(self):
        brain=Mock();data={'request':'Run Smart Visuals on this attached video. Offer raw images for my choice.',
            'attachments':[{'name':'exact.mp4'}],'allowed_ids':['source-exact'],
            'distribution_workflow':{'optional_procedure':'old publishing workflow '*1800},
            'chrome_connection':{'background':'old browser setup '*1800},
            'shared_memory':{'editing_sources':[{'id':'source-exact'}],'active_task':{'source':'source-exact'}}}
        original=copy.deepcopy(data)
        bounded=fit(brain,'Select only supported tools.',data,{},900)
        self.assertNotIn('distribution_workflow',bounded);self.assertNotIn('chrome_connection',bounded)
        self.assertEqual(bounded['request'],data['request']);self.assertEqual(bounded['attachments'],data['attachments'])
        self.assertEqual(bounded['shared_memory']['active_task'],data['shared_memory']['active_task'])
        self.assertEqual(data,original)

    def test_publishing_or_account_request_keeps_exact_required_background(self):
        brain=Mock();data={'request':'Inspect my Instagram account then schedule the reviewed Reel.',
            'distribution_workflow':{'account_id':'exact-account','required':'x'*30000},
            'chrome_connection':{'account_id':'exact-account'}}
        with self.assertRaisesRegex(ValueError,'too much required'):
            fit(brain,'Select tools.',data,{},900)

    def test_small_edit_request_keeps_all_optional_background(self):
        brain=Mock();data={'request':'Run Smart Visuals.','distribution_workflow':{'procedure':'keep'},'chrome_connection':{'connected':True}}
        bounded=fit(brain,'Select tools.',data,{},100)
        self.assertEqual(bounded['distribution_workflow'],data['distribution_workflow'])
        self.assertEqual(bounded['chrome_connection'],data['chrome_connection'])

    def test_oversized_optional_knowledge_is_removed_without_changing_task_scope(self):
        brain=Mock();data={'request':'Two cricket Reels and two gaming Shorts on 27 October at 19:00',
            'attachments':[{'name':'source.mp4'}],'allowed_ids':['exact-source-id'],
            'shared_memory':{'editing_sources':[{'id':'exact-source-id'}],
                'workflow_knowledge':{'chunks':[{'text':'optional background '*5000}]}}}
        original=copy.deepcopy(data)
        bounded=fit(brain,'Select tool arguments.',data,{},900)
        self.assertEqual(bounded['request'],data['request']);self.assertEqual(bounded['allowed_ids'],data['allowed_ids'])
        self.assertEqual(bounded['attachments'],data['attachments'])
        self.assertEqual(bounded['shared_memory']['editing_sources'],data['shared_memory']['editing_sources'])
        self.assertNotIn('workflow_knowledge',bounded['shared_memory']);self.assertEqual(data,original)

    def test_router_preserves_creator_guidance(self):
        from hinglish_niche.profiles import use,CURRENT
        brain=Mock();brain.json.side_effect=lambda *a,**kw:CURRENT.get()
        profile={'profile':'cricket','documentary_style':'vineet documentry edit','feedback':'Preserve cricket names.'}
        with use(profile):
            result=ask(brain,'Select tools.',{'request':'Upload saved Reels.'},{},max_tokens=100)
            self.assertEqual(CURRENT.get(),profile)
        self.assertEqual(result,profile)

    def test_small_request_keeps_optional_guidance(self):
        brain=Mock();data={'request':'Upload one Reel.','preferences':{'language':'English'},
            'shared_memory':{'workflow_knowledge':{'chunks':[{'text':'Use verified receipts.'}]},
                'runtime_facts':{'account':'cricket'}}}
        self.assertEqual(fit(brain,'Select tools.',data,{},100)['shared_memory'],data['shared_memory'])
        self.assertEqual(fit(brain,'Select tools.',data,{},100)['preferences'],data['preferences'])

    def test_context_overflow_retry_preserves_profile(self):
        from hinglish_niche.profiles import use,CURRENT
        brain=Mock();seen=[]
        def answer(*a,**kw):
            seen.append(copy.deepcopy(CURRENT.get()))
            if len(seen)==1:raise RuntimeError('HTTP 400 context exceeds available size')
            return {'ok':True}
        brain.json.side_effect=answer
        profile={'profile':'gaming','feedback':'Keep game context.'}
        with use(profile):ask(brain,'Select tools.',{'request':'Upload one Reel.'},{},max_tokens=100)
        self.assertEqual(seen,[profile,profile])

    def test_profile_is_budgeted_and_never_silently_removed(self):
        from hinglish_niche.profiles import use
        brain=Mock()
        with use({'profile':'cricket','feedback':'required guidance '*5000}):
            with self.assertRaisesRegex(ValueError,'too much required'):
                ask(brain,'Select tools.',{'request':'Upload one Reel.'},{},max_tokens=100)
        brain.json.assert_not_called()

    def test_required_input_never_gets_silently_truncated_or_sent_over_budget(self):
        brain=Mock()
        with self.assertRaisesRegex(ValueError,'too much required'):
            ask(brain,'Select tools.',{'request':'essential source instructions '*5000},{},max_tokens=900)
        brain.json.assert_not_called()

    def test_context_check_returns_plan_without_dispatch_or_chat_mutation(self):
        from hinglish_app.server import AppState
        from hinglish_app.assistant_planner_check import check
        folder=Path(__file__).resolve().parents[1]/'tmp'
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            state=AppState(temporary);assistant=state.assistant;sid=assistant.create()['id']
            assistant._message(sid,'user','Upload two Reels on cricket and two on gaming.')
            assistant._update(sid,status='failed')
            before=assistant.snapshot(sid)
            answer={'reply':'Ready.','question':'','combine':False,'steps':[{'tool':'publish','options':{}}]}
            with patch('hinglish_app.assistant_plan.plan',return_value=(answer,'local model')),patch.object(state,'create_job') as create:
                result=check(assistant,sid)
            self.assertFalse(result['execution']);self.assertEqual(result['plan'],answer)
            self.assertEqual(assistant.snapshot(sid),before);create.assert_not_called()
            self.assertEqual(state.local_browser.data['jobs'],[]);self.assertEqual(state.publisher.store.list(),[])
