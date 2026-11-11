import json
from pathlib import Path
import time
from unittest.mock import patch
from tests.base import SuiteCase
from adapters.receiver import Receiver, canonical
from core.workflow_service import WorkflowService
from core.workflow_broker import ExecutionBroker


class ReceivingBoundaryTests(SuiteCase):
    def test_result_journal_recovers_lost_database_acknowledgement(self):
        storage=self.tmp/'receiver'
        receiver=Receiver('repository',Path(__file__).resolve().parent.parent,storage,'x'*40)
        key='action_'+'a'*64
        with receiver.connect() as db:
            db.execute('INSERT INTO actions VALUES (?,?,?,?)',(key,'a'*64,'{}',canonical({'status':'running'})))
        result={'status':'succeeded','verified':True,'remote_id':key,'idempotency_key':key,'exact_payload_hash':'a'*64,'evidence_refs':['fixture:report']}
        receiver.commit_result(key,result)
        restarted=Receiver('repository',receiver.root,storage,'x'*40)
        self.assertEqual(restarted.receipt(key),result)
        self.assertFalse(restarted.jobs)

    def test_restart_does_not_replay_unfinished_execution(self):
        storage=self.tmp/'receiver'
        receiver=Receiver('repository',Path(__file__).resolve().parent.parent,storage,'x'*40)
        key='action_'+'b'*64
        with receiver.connect() as db:
            db.execute('INSERT INTO actions VALUES (?,?,?,?)',(key,'b'*64,'{}',canonical({'status':'running'})))
        restarted=Receiver('repository',receiver.root,storage,'x'*40)
        self.assertEqual(restarted.receipt(key)['status'],'interrupted')
        self.assertTrue(restarted.receipt(key)['execution_stopped'])
        self.assertFalse(restarted.jobs)

    def test_model_cannot_add_an_execution_field(self):
        from core.workflow_brain import validate_plan
        from core.llm import LLMError
        from tests.test_workflow_brain import GOOD
        with self.assertRaises(LLMError):validate_plan({**GOOD,'send_now':True})

    def test_secret_artifact_registration_is_rejected(self):
        service=WorkflowService(self.store)
        secret=self.tmp/'dashboard.token'; secret.write_text('not-a-real-secret')
        with self.assertRaises(PermissionError):
            service.ledger.register_artifact(secret,project='agents',revision='1',evidence=['fixture'])

    def test_consistent_backup_restores_action_tombstones(self):
        from scripts.backup_workflow_database import snapshot
        service=WorkflowService(self.store)
        service.create('learning_evidence','fixture',{},'fixture')
        # Separate consistent copy, then restore into a fresh file. No worker is launched.
        source=self.store.url.removeprefix('sqlite:///')
        saved=snapshot(source,self.tmp/'backup.db')
        restored=snapshot(self.tmp/'backup.db',self.tmp/'restored.db')
        self.assertEqual(saved['counts'],restored['counts'])
        self.assertEqual(saved['sha256'],restored['sha256'])
        self.assertFalse(restored['workers_started'])
        with self.assertRaises(ValueError):snapshot(source,self.tmp/'restored.db')

    def test_expired_approval_can_reconcile_but_not_submit_again(self):
        service=WorkflowService(self.store)
        task=service.create('system_health','fixture',{},'fixture')
        aid=service.broker.request_review(task,'diagnostics.read',{'seconds':30},'cortana')
        from core.hitl import ApprovalQueue
        ApprovalQueue(self.store).approve(aid)
        row=self.store.one('SELECT binding_json FROM suite_reviews WHERE approval_id=?',(aid,))
        binding=json.loads(row['binding_json']); binding['expiry']=time.time()-5
        self.store.run('UPDATE suite_reviews SET binding_json=? WHERE approval_id=?',(canonical(binding),aid))
        key='action_'+binding['exact_payload_hash']
        self.store.run('INSERT INTO suite_actions VALUES (?,?,?,?,?,?)',(key,task['task_id'],binding['exact_payload_hash'],'uncertain','{}',time.time()))
        class ReadOnlyClient:
            def reconcile(inner,action_id):
                return {'idempotency_key':action_id,'exact_payload_hash':binding['exact_payload_hash'],
                    'verified':True,'remote_id':'native-report','evidence_refs':['fixture:report']}
            def submit(inner,*args):raise AssertionError('Must not submit')
        receipt=service.broker.execute(aid,'cortana',ReadOnlyClient())
        self.assertTrue(receipt['verified'])
