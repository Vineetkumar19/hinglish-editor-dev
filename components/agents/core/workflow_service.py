"""Single Suite workflow facade shared by HTTP and CLI; uses existing records."""
from __future__ import annotations

import json
import time

from . import config
from .graph import RunResult
from .hitl import ApprovalQueue
from .store import new_id
from .workflow_broker import ExecutionBroker, IntegrationUnavailable
from .workflow_contracts import ROLE_PERMISSIONS, ROLES, TaskEnvelope, digest, input_references
from .workflow_store import Conflict, WorkflowStore


class WorkflowService:
    def __init__(self, store):
        self.store = store
        self.ledger = WorkflowStore(store)
        self.broker = ExecutionBroker(store)

    def create(self, role, intent, inputs, idempotency_key, *, device_id=None, budgets=None, permissions=None, parent_task_id=None):
        if role not in ROLES:
            raise ValueError('Unknown workflow role')
        if not isinstance(inputs, dict) or len(json.dumps(inputs).encode('utf-8')) > 2_000_000:
            raise ValueError('Inputs must be a JSON object of at most 2 MB')
        env = TaskEnvelope(new_id('task'), role, intent, input_references(inputs),
            device_id or config.get('SUITE_DEVICE_ID', 'local'),
            {'runtime_seconds': 300 if inputs.get('_brain', 'manual') != 'manual' else 60,
             'storage_bytes': 10_000_000, 'retries': 1, **(budgets or {})},
            sorted(ROLE_PERMISSIONS[role]) if permissions is None else permissions,
            parent_task_id, idempotency_key)
        return self.ledger.create(env, inputs)

    def prepare(self, task_id):
        task = self.ledger.get(task_id)
        if not task:
            raise KeyError(task_id)
        if task['paused'] or task['state'] == 'cancelled':
            raise Conflict('Task is paused or cancelled')
        if task['state'] in ('succeeded', 'waiting_for_review'):
            return task
        owner = new_id('plan')
        resource = 'task:' + task_id
        if not self.ledger.acquire(resource, owner, seconds=task['envelope']['budgets']['runtime_seconds'] + 30):
            raise Conflict('Task is already running')
        start = time.monotonic()
        try:
            self.ledger.update(task_id, 'planning', task['result'])
            role = task['role']
            brain = None
            if task['input'].get('_brain', 'manual') != 'manual':
                from .workflow_brain import plan
                brain = plan(self.store, task, task['input']['_brain'])
                current = self.ledger.get(task_id)
                if current['paused'] or current['state'] == 'cancelled':
                    return current
            if role == 'system_health':
                from .workflow_health import run_health
                def guard():
                    current = self.ledger.get(task_id)
                    if current['paused'] or current['state'] == 'cancelled':
                        raise Conflict('Readiness check stopped by task control')
                result = run_health(self.store, retry_budget=task['envelope']['budgets']['retries'],
                    runtime_seconds=task['envelope']['budgets']['runtime_seconds'], guard=guard)
                result['verified_result'] = 'Readiness probes completed; dependency failures are listed separately'
                state = 'succeeded' if result['ready'] else 'partially_succeeded'
            elif role == 'research_experiment':
                from .workflow_experiment import run_experiment
                if 'experiment.run' not in task['envelope']['permissions']:
                    raise PermissionError('Experiment capability is missing')
                self.ledger.update(task_id, 'running', {'phase': 'bounded metadata retrieval comparison'})
                result = run_experiment(task, self.ledger, config.data_dir() / 'experiments')
                result['verified_result'] = 'Baseline and candidate measured on the same held-out query labels'
                state = 'succeeded'
            else:
                from agents import workflows
                planner = {'client_delivery': workflows.client_delivery, 'inbox_commitment': workflows.inbox_commitment,
                    'learning_evidence': workflows.learning_evidence, 'content_release': workflows.content_release,
                    'saas_sales': workflows.saas_demand}[role]
                payload, action, target, refs = planner(task, self.ledger)
                if brain:
                    payload['planning_review'] = brain
                    if role == 'learning_evidence':
                        payload['exercise'] = brain['plan']['exercise'] or payload['exercise']
                aid = self.broker.request_review(task, action, payload, target, refs)
                result = {'prepared': payload, 'approval_id': aid, 'verified_result': '',
                          'next_valid_action': 'Review the exact prepared result', 'external_action_performed': False}
                state = 'waiting_for_review'
            if brain:
                result['brain'] = brain
            result['metrics'] = {'elapsed_seconds': time.monotonic() - start,
                'cost': None if brain else 0, 'model_calls': int(bool(brain and not brain.get('reused_saved_plan'))),
                'peak_ram': None, 'peak_vram': None}
            return self.ledger.update(task_id, state, result, expected_revision=task['revision'])
        except Exception as exc:
            current = self.ledger.get(task_id)
            if current['state'] == 'cancelled' or current['paused']:
                return current
            return self.ledger.update(task_id, 'failed', {'error': str(exc), 'verified_result': '',
                'next_valid_action': 'Correct inputs or the named dependency, then retry or revise'}, expected_revision=task['revision'])
        finally:
            self.ledger.release(resource, owner)

    def accept_decision(self, task_id, decision, approval_id=None):
        task = self.ledger.get(task_id)
        aid = approval_id or task['result'].get('approval_id')
        if not aid:
            raise ValueError('Task has no pending review')
        if decision.get('status') == 'rejected':
            if aid in task['result'].get('review_ids', []):
                pending = [rid for rid in task['result']['review_ids'] if ApprovalQueue(self.store).get(rid)['status'] == 'pending']
                self.ledger.update(task_id, 'waiting_for_review' if pending else 'partially_succeeded',
                    {**task['result'], 'next_valid_action': 'Review remaining items; rejected items will not execute'})
            else:
                self.ledger.control(task_id, 'cancel')
            return RunResult({}, 'complete', task_id)
        checked, review, binding = self.broker.validate_review(aid)
        if checked['task_id'] != task_id:
            raise Conflict('Approval belongs to a different task')
        payload = binding['exact']['payload']
        if checked['role'] == 'client_delivery' and binding['action_type'] == 'prepare':
            self.store.kv_set('workflow_scope', task_id, {'scope_hash': payload['scope_hash'],
                'revision': checked['revision'], 'approval_id': aid})
        if checked['role'] == 'inbox_commitment':
            with self.store.tx():
                for c in payload['commitments']:
                    self.store.kv_set('commitment_sources', c['source_key'], {'text_hash': c['text_hash']})
                    if not self.store.kv_get('commitments', c['id']):
                        self.store.kv_set('commitments', c['id'], {**c, 'reviewed_by': aid})
        if binding['action_type'] == 'prepare':
            self.store.run('UPDATE suite_reviews SET consumed=1 WHERE approval_id=?', (aid,))
            state = 'succeeded'
            verified = 'Prepared material reviewed and saved; no external action performed'
        else:
            state = 'waiting_for_device'
            verified = 'Exact package reviewed; dispatch and receiver verification remain pending'
        result = {**task['result'], 'verified_result': verified, 'next_valid_action':
                  'Provide the next revision when ready' if state == 'succeeded' else 'Dispatch through a configured compatible receiver'}
        if checked['role'] == 'saas_sales' and 'ranked_needs' in payload:
            review_ids = []
            for draft in payload['drafts']:
                review_ids.append(self.broker.request_review(checked, 'prepare',
                    {'source_ref': draft['source_ref'], 'body': draft['draft'], 'recipient': draft['target'],
                     'contact_id': draft['contact_id'], 'supported_capabilities': draft['qualification_facts'],
                     'research_only_draft': draft.get('research_only_draft', False),
                     'outgoing_authorized': False}, draft['target']))
            result.update(review_ids=review_ids, approval_id=None,
                          next_valid_action='Review each selected draft; no sending is enabled for demand research')
            state = 'waiting_for_review' if review_ids else 'succeeded'
        elif checked['role'] == 'saas_sales' and aid in task['result'].get('review_ids', []):
            pending = [rid for rid in task['result']['review_ids'] if ApprovalQueue(self.store).get(rid)['status'] == 'pending']
            state = 'waiting_for_review' if pending else 'succeeded'
            result['next_valid_action'] = 'Review remaining drafts' if pending else 'Record real responses or disqualification evidence when available'
        elif checked['role'] == 'content_release' and binding['action_type'] == 'prepare':
            review_ids = []
            for package in payload['packages']:
                review_ids.append(self.broker.request_review(checked, 'storylens.package' if package.get('preview_only') else 'storylens.publish', package,
                    package['account'], [package['artifact']]))
            result.update(review_ids=review_ids, approval_id=None,
                          next_valid_action='Review each exact platform package and release time separately')
            state = 'waiting_for_review'
        elif checked['role'] == 'content_release' and binding['action_type'] in ('storylens.publish','storylens.package'):
            pending = [rid for rid in task['result'].get('review_ids', [])
                       if ApprovalQueue(self.store).get(rid)['status'] == 'pending']
            state = 'waiting_for_review' if pending else 'waiting_for_device'
            result['next_valid_action'] = 'Review remaining destinations' if pending else 'Dispatch approved destinations through StoryLens'
        self.ledger.update(task_id, state, result, expected_revision=checked['revision'])
        return RunResult(result, 'complete', task_id)

    def request_work(self, task_id):
        task = self.ledger.get(task_id)
        if task['role'] != 'client_delivery' or task['paused'] or task['state'] == 'cancelled':
            raise Conflict('Work request needs an active client-delivery task')
        approved = self.store.kv_get('workflow_scope', task_id, {})
        payload = task['result'].get('prepared', {})
        if not approved or approved.get('scope_hash') != payload.get('scope_hash'):
            raise Conflict('Review the current scope before requesting work')
        work = payload['work_request']
        capability = 'storylens.prepare' if work['project'] == 'storylens' else 'repository.prepare'
        aid = self.broker.request_review(task, capability, work, work['project'], work['artifact_refs'])
        return self.ledger.update(task_id, 'waiting_for_review', {**task['result'], 'approval_id': aid,
            'prepared': work, 'next_valid_action': 'Review the bounded work request before dispatch'})

    def request_diagnostics(self, task_id):
        task = self.ledger.get(task_id)
        if task['role'] != 'system_health' or task['paused'] or task['state'] == 'cancelled':
            raise Conflict('Diagnostics requires an active health task')
        payload = {'seconds':30,'purpose':'Read-only device diagnosis through Cortana; no process or setting changes'}
        aid = self.broker.request_review(task, 'diagnostics.read', payload, 'cortana')
        return self.ledger.update(task_id, 'waiting_for_review', {**task['result'], 'approval_id':aid,
            'prepared':payload, 'next_valid_action':'Review the 30-second Cortana diagnostic sample'})

    def decide(self, task_id, approve, approval_id=None):
        task = self.ledger.get(task_id)
        if task['paused'] or task['state'] == 'cancelled':
            raise Conflict('Task is paused or cancelled')
        aid = approval_id or task['result'].get('approval_id')
        if aid not in [task['result'].get('approval_id'), *task['result'].get('review_ids', [])]:
            raise Conflict('Approval is not attached to this task revision')
        decision = (ApprovalQueue(self.store).approve(aid) if approve else ApprovalQueue(self.store).reject(aid))
        self.accept_decision(task_id, decision.to_json(), aid)
        return self.ledger.get(task_id)

    def dispatch(self, task_id):
        task = self.ledger.get(task_id)
        if task['paused'] or task['state'] == 'cancelled':
            raise Conflict('Task is paused or cancelled')
        if task['role'] == 'content_release':
            return self.dispatch_release(task)
        aid = task['result'].get('approval_id')
        review = self.store.one('SELECT binding_json FROM suite_reviews WHERE approval_id=?', (aid,))
        action_type = json.loads(review['binding_json'])['action_type'] if review else ''
        integration = {'delivery.send': 'cortana', 'delivery.package': 'cortana', 'diagnostics.read':'cortana', 'storylens.prepare': 'storylens',
                       'repository.prepare': 'repository'}.get(action_type, 'storylens')
        try:
            receipt = self.broker.execute(aid, integration)
            for ref in receipt.get('artifacts', []):
                saved = self.ledger.register_artifact(ref['locator'], project=ref['project'], revision=ref['revision'],
                    evidence=ref['evidence'], artifact_id=ref['artifact_id'], approval_status='unreviewed')
                if saved['content_hash'] != ref['content_hash']:
                    raise Conflict('Receiving artifact changed after its receipt')
            verified = receipt.get('verified') is True and receipt.get('remote_id') and receipt.get('evidence_refs')
            failed = receipt.get('status') in ('failed', 'cancelled', 'interrupted') and receipt.get('execution_stopped') is True
            return self.ledger.update(task_id, 'succeeded' if verified else 'failed' if failed else 'reconciling',
                {**task['result'], 'receipt': receipt, 'verified_result':
                 'Receiver confirmed the exact action' if verified else '',
                 'error': receipt.get('error', ''),
                 'next_valid_action': '' if verified else 'Inspect receiver evidence and create a corrected revision' if failed else 'Reconcile by the saved action ID before retrying'})
        except Exception as exc:
            from .workflow_health import classify
            kind = classify(exc)
            state = {'authentication': 'waiting_for_auth', 'dns': 'waiting_for_network',
                     'transient': 'waiting_for_network'}.get(kind, 'waiting_for_device')
            if self.store.one("SELECT action_id FROM suite_actions WHERE task_id=? AND state IN ('uncertain','executing')", (task_id,)):
                state = 'reconciling'
            return self.ledger.update(task_id, state, {**task['result'], 'error': str(exc)[:300],
                'next_valid_action': 'Configure/check the named receiver; reconcile any uncertain action before retrying'})

    def control(self, task_id, action):
        result = self.ledger.control(task_id, action)
        if action not in ('cancel', 'pause'):
            return result
        from .workflow_broker import IntegrationClient
        for row in self.store.query("SELECT action_id,payload_hash FROM suite_actions WHERE task_id=? AND state IN ('executing','uncertain')", (task_id,)):
            reviews = self.store.query('SELECT binding_json FROM suite_reviews WHERE task_id=?', (task_id,))
            binding = next((json.loads(r['binding_json']) for r in reviews if json.loads(r['binding_json'])['exact_payload_hash'] == row['payload_hash']), None)
            if not binding:
                continue
            kind = binding['action_type']
            integration = 'cortana' if kind.startswith(('delivery.', 'diagnostics.')) else 'repository' if kind.startswith('repository.') else 'storylens'
            try:
                receipt = IntegrationClient(integration).cancel(row['action_id'])
                self.store.event('workflow_receiver_stop_requested', result['role'], task_id, action_id=row['action_id'], status=receipt.get('status'))
            except Exception as exc:
                self.store.event('workflow_receiver_stop_unconfirmed', result['role'], task_id, action_id=row['action_id'], error=type(exc).__name__)
        return result

    def dispatch_release(self, task):
        receipts = dict(task['result'].get('destinations', {}))
        for aid in task['result'].get('review_ids', []):
            if receipts.get(aid, {}).get('verified'):
                continue
            if ApprovalQueue(self.store).get(aid)['status'] != 'approved':
                receipts[aid] = {'error': 'Destination is not approved', 'verified': False}
                continue
            try:
                receipts[aid] = self.broker.execute(aid, 'storylens')
            except Exception as exc:
                receipts[aid] = {'error': type(exc).__name__ + ': ' + str(exc)[:240], 'verified': False}
            # Persist each platform independently before proceeding to the next.
            self.ledger.update(task['task_id'], 'reconciling', {**task['result'], 'destinations': receipts})
        count = sum(bool(r.get('verified') and r.get('remote_id') and r.get('evidence_refs')) for r in receipts.values())
        state = 'succeeded' if receipts and count == len(receipts) else 'partially_succeeded' if count else 'waiting_for_device'
        return self.ledger.update(task['task_id'], state, {**task['result'], 'destinations': receipts,
            'verified_result': f'{count}/{len(receipts)} destinations verified by the receiver',
            'next_valid_action': '' if state == 'succeeded' else 'Reconcile and retry only the unfinished destinations'})

    def record_outcome(self, task_id, contact_id, status, source_ref, quote):
        task = self.ledger.get(task_id)
        if task['role'] != 'saas_sales' or task['state'] == 'cancelled' or task['paused']:
            raise Conflict('Outcome is not valid for this task')
        if status not in ('posted', 'interested', 'disqualified', 'opt_out') or not source_ref or not quote:
            raise ValueError('An observed response/disqualification needs source and exact evidence')
        needs = task['result'].get('prepared', {}).get('ranked_needs', [])
        if not any(n['contact_id'] == contact_id for n in needs):
            raise ValueError('Contact was not in the reviewed shortlist')
        lead = self.store.one('SELECT * FROM leads WHERE id=?', (contact_id,))
        if status == 'posted':
            from .search import public_web_url
            approved = [ApprovalQueue(self.store).get(aid) for aid in task['result'].get('review_ids', [])]
            if not public_web_url(source_ref) or not any(
                r and r['status'] == 'approved' and
                r['payload']['workflow_binding']['exact']['payload'].get('contact_id') == contact_id
                for r in approved
            ):
                raise ValueError('Record a public post link only after its exact draft is approved')
        if status == 'opt_out' and lead['email']:
            from .mailer import SuppressionList
            SuppressionList(self.store).add(lead['email'], reason='Owner-recorded opt-out: ' + source_ref)
        payload = {'contact_id': contact_id, 'status': status, 'source_ref': source_ref, 'quote': quote,
                   'owner_role': 'saas_sales', 'observed_at': time.time()}
        self.store.kv_set('workflow_opportunities', contact_id, payload)
        self.store.run('UPDATE leads SET status=?,updated_at=? WHERE id=?',
                       ('suppressed' if status == 'opt_out' else status, time.time(), contact_id))
        self.store.event('workflow_contact_outcome', 'saas_sales', task_id,
                         contact_id=contact_id, status=status, source_ref=source_ref)
        return payload


class ReviewResumer:
    def __init__(self, store):
        self.service = WorkflowService(store)

    def resume(self, thread_id, value):
        # CLI/Telegram approvals already persist their decision. Resolve the
        # exact decided row, never consume a neighbouring destination's review.
        task = self.service.ledger.get(thread_id)
        candidates = [r['id'] for r in self.service.store.query(
            "SELECT id FROM approvals WHERE thread_id=? AND status IN ('approved','rejected') ORDER BY decided_at DESC", (thread_id,))]
        for aid in filter(None, candidates):
            row = self.service.store.one('SELECT consumed FROM suite_reviews WHERE approval_id=?', (aid,))
            approval = ApprovalQueue(self.service.store).get(aid)
            if row and not row['consumed'] and approval['status'] in ('approved', 'rejected'):
                return self.service.accept_decision(thread_id, approval['decision'], aid)
        raise Conflict('No unconsumed decision for this task')
