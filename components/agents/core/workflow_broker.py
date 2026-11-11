"""Exact-payload review and bounded versioned cross-project execution.

No project imports, guessed API endpoints, UI drivers or second publication queue.
An operator-configured receiver must advertise protocol v1 and reconcile by key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request

from . import config
from .hitl import ApprovalQueue
from .store import new_id
from .workflow_contracts import Approval, ROLE_PERMISSIONS, canonical, digest
from .workflow_store import Conflict, WorkflowStore


class IntegrationUnavailable(RuntimeError):
    pass


class IntegrationClient:
    def __init__(self, name):
        path = Path(config.get('SUITE_INTEGRATIONS_FILE', str(config.profiles_dir() / 'workflow_integrations.json')))
        integrations = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        self.settings = integrations.get(name)
        if not self.settings:
            raise IntegrationUnavailable(f'{name}: no configured versioned Suite adapter')
        if self.settings.get('connection_file'):
            live = json.loads(Path(self.settings['connection_file']).read_text(encoding='utf-8'))
            if live.get('project') != name:
                raise IntegrationUnavailable('Receiver connection belongs to another project')
            self.settings = {**self.settings, **live}
        parsed = urllib.parse.urlsplit(self.settings['base_url'])
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid adapter base URL')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Remote adapters require authenticated TLS')
        self.token = os.environ.get(self.settings.get('token_env', ''), '')
        if not self.token and self.settings.get('token_file'):
            self.token = Path(self.settings['token_file']).read_text(encoding='utf-8').strip()
        if not self.token or not self.settings.get('device_id'):
            raise IntegrationUnavailable(f'{name}: device identity or authentication is missing')

    def request(self, route, payload=None):
        body = canonical(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.settings['base_url'].rstrip('/') + route, data=body,
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        # No automatic POST retry or cross-origin credential forwarding.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=10) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Adapter response exceeds limit')
            return json.loads(raw)

    def capabilities(self):
        result = self.request('/capabilities')
        if result.get('contract_version') != 1 or result.get('device_id') != self.settings['device_id']:
            raise IntegrationUnavailable('Adapter protocol or device identity mismatch')
        if not result.get('reconciliation'):
            raise IntegrationUnavailable('Adapter must reconcile requests by idempotency key')
        return result

    def submit(self, payload):
        return self.request('/tasks', payload)

    def reconcile(self, action_id):
        return self.request('/tasks/' + urllib.parse.quote(action_id, safe=''))

    def cancel(self, action_id):
        return self.request('/tasks/' + urllib.parse.quote(action_id, safe='') + '/cancel', {})


class ExecutionBroker:
    def __init__(self, store):
        self.store = store
        self.tasks = WorkflowStore(store)
        self.queue = ApprovalQueue(store)

    def request_review(self, task, action_type, payload, target='', artifacts=()):
        if action_type not in ROLE_PERMISSIONS[task['role']]:
            raise PermissionError('Action is outside role permissions')
        refs = self.tasks.verify_artifacts(list(artifacts))
        bound = {'action_type': action_type, 'payload': payload, 'target': target,
                 'artifact_refs': refs, 'revision': task['revision']}
        binding = Approval(action_type, digest(bound), target, refs, time.time() + 86400).__dict__
        binding['exact'] = bound
        # A task lease serializes preparations; this lookup also covers restart.
        for row in self.store.query('SELECT approval_id,binding_json FROM suite_reviews WHERE task_id=? AND task_revision=?', (task['task_id'], task['revision'])):
            old = json.loads(row['binding_json'])
            queued = self.queue.get(row['approval_id'])
            if old['exact_payload_hash'] == binding['exact_payload_hash'] and old['expiry'] > time.time() and queued['status'] in ('pending', 'approved'):
                return row['approval_id']
        with self.store.tx():
            aid = self.queue.create(thread_id=task['task_id'], agent=task['role'],
                kind='workflow_review', title=task['envelope']['intent'],
                payload={'body': json.dumps(payload, indent=2, ensure_ascii=False),
                         'workflow_binding': binding, 'target': target, 'artifacts': refs})
            self.store.execute('INSERT INTO suite_reviews VALUES (?,?,?,?,0)',
                (aid, task['task_id'], task['revision'], canonical(binding)))
        return aid

    def validate_review(self, aid):
        review = self.store.one('SELECT * FROM suite_reviews WHERE approval_id=?', (aid,))
        if not review:
            raise ValueError('No workflow review')
        task = self.tasks.get(review['task_id'])
        binding = json.loads(review['binding_json'])
        approval = self.queue.get(aid)
        if task['paused'] or task['state'] == 'cancelled':
            raise Conflict('Task is paused or cancelled')
        if task['revision'] != review['task_revision'] or time.time() > binding['expiry']:
            raise Conflict('Review expired or task revision changed')
        if approval['status'] != 'approved' or (approval.get('decision') or {}).get('edits'):
            raise PermissionError('Exact review approval is required; edits need a new revision')
        if digest(binding['exact']) != binding['exact_payload_hash']:
            raise Conflict('Review payload changed')
        self.tasks.verify_artifacts(binding['artifact_refs'])
        return task, review, binding

    def execute(self, aid, integration, client=None):
        # Reconciliation is a read of an already-submitted identity. Expiry
        # blocks new execution, not learning what the previous receiver did.
        recorded = self.store.one('SELECT * FROM suite_reviews WHERE approval_id=?', (aid,))
        if recorded:
            saved = json.loads(recorded['binding_json'])
            identity = 'action_' + saved.get('exact_payload_hash','')
            existing = self.store.one('SELECT * FROM suite_actions WHERE action_id=?',(identity,))
            current = self.tasks.get(recorded['task_id'])
            if current['paused'] or current['state']=='cancelled':
                raise Conflict('Task is paused or cancelled')
            if existing and existing['state'] not in ('safe_to_retry',):
                if existing['state']=='verified':
                    return json.loads(existing['receipt_json'])
                receiver = client or IntegrationClient(integration)
                return self._receipt(current,identity,receiver.reconcile(identity))
        task, review, binding = self.validate_review(aid)
        action = binding['action_type']
        if action not in ROLE_PERMISSIONS[task['role']] or action not in task['envelope']['permissions']:
            raise PermissionError('Task capability is not granted')
        if action == 'prepare':
            raise ValueError('Local review does not need an external executor')
        if config.dry_run():
            raise IntegrationUnavailable('DRY_RUN is enabled; prepared only')
        client = client or IntegrationClient(integration)
        caps = client.capabilities()
        if action not in caps.get('actions', []) or task['envelope']['device_id'] != caps['device_id']:
            raise IntegrationUnavailable('Receiver does not support this action/device')
        exact = binding['exact']
        # A path on this machine is never treated as a path on another worker.
        for ref in binding['artifact_refs']:
            if ref['device_id'] != caps['device_id'] and ref['content_hash'] not in caps.get('available_artifact_hashes', []):
                raise IntegrationUnavailable('Receiving device has not confirmed this content-addressed artifact; transfer it through its authenticated artifact adapter first')
        if action == 'delivery.send':
            from .mailer import SuppressionList
            if SuppressionList(self.store).contains(exact['target']):
                raise PermissionError('Recipient is suppressed; delivery is blocked')
        if action == 'storylens.publish' and caps.get('publication_ledger_owner') != 'storylens':
            raise IntegrationUnavailable('StoryLens must own the publication ledger and scheduler')
        if action == 'storylens.publish' and exact['payload'].get('trial') and not caps.get('trial_reels_verified_accounts', {}).get(exact['target']):
            raise IntegrationUnavailable('Trial Reels support is unverified for this account')
        action_id = 'action_' + binding['exact_payload_hash']
        old = self.store.one('SELECT * FROM suite_actions WHERE action_id=?', (action_id,))
        if old and old['state'] == 'verified':
            return json.loads(old['receipt_json'])
        if old and old['state'] != 'safe_to_retry':
            receipt = client.reconcile(action_id)
            return self._receipt(task, action_id, receipt)
        if review['consumed'] and not old:
            raise Conflict('Review was consumed; reconcile instead of resubmitting')
        resources = ['task:' + task['task_id'], 'browser-account:' + exact['target']]
        if action == 'storylens.publish':
            resources.append('publication:' + exact['target'] + ':' + str(exact['payload'].get('time')))
        owner = new_id('execution')
        acquired = []
        try:
            for resource in resources:
                if not self.tasks.acquire(resource, owner, seconds=60):
                    raise Conflict('Resource is in use; task remains queued')
                acquired.append(resource)
            # Check cancellation again at the external boundary, then atomically claim.
            self.validate_review(aid)
            with self.store.tx():
                attempts = self.store.kv_get('workflow_action_attempts', action_id, 0)
                if attempts >= 1 + task['envelope']['budgets']['retries']:
                    raise Conflict('Action retry budget exhausted; inspect the receiver evidence')
                if old:
                    cur = self.store.execute("UPDATE suite_actions SET state='executing',updated_at=? WHERE action_id=? AND state='safe_to_retry'", (time.time(), action_id))
                    if cur.rowcount != 1:
                        raise Conflict('Action was claimed by another worker')
                else:
                    cur = self.store.execute('UPDATE suite_reviews SET consumed=1 WHERE approval_id=? AND consumed=0', (aid,))
                    if cur.rowcount != 1:
                        raise Conflict('This review was already claimed')
                    self.store.execute('INSERT INTO suite_actions VALUES (?,?,?,?,?,?)',
                        (action_id, task['task_id'], binding['exact_payload_hash'], 'executing', '{}', time.time()))
                self.store.kv_set('workflow_action_attempts', action_id, attempts + 1)
            try:
                receipt = client.submit({'contract_version': 1, 'idempotency_key': action_id,
                    'task': task['envelope'], 'approval': binding, 'exact': exact})
                return self._receipt(task, action_id, receipt)
            except Exception:
                self.store.run("UPDATE suite_actions SET state='uncertain',updated_at=? WHERE action_id=? AND state!='verified'", (time.time(), action_id))
                raise
        finally:
            for resource in reversed(acquired):
                self.tasks.release(resource, owner)

    def _receipt(self, task, action_id, receipt):
        if receipt.get('idempotency_key') != action_id:
            raise Conflict('Receiver receipt identity mismatch')
        row = self.store.one('SELECT payload_hash FROM suite_actions WHERE action_id=?', (action_id,))
        if receipt.get('exact_payload_hash') != row['payload_hash']:
            raise Conflict('Receiver did not confirm the exact reviewed payload hash')
        verified = receipt.get('verified') is True and bool(receipt.get('evidence_refs')) and bool(receipt.get('remote_id'))
        safe_retry = receipt.get('status') == 'not_submitted' and receipt.get('absence_verified') is True and bool(receipt.get('evidence_refs'))
        terminal_failure = receipt.get('status') in ('failed', 'cancelled', 'interrupted') and receipt.get('execution_stopped') is True
        state = 'verified' if verified else 'safe_to_retry' if safe_retry else 'failed' if terminal_failure else 'uncertain'
        self.store.run('UPDATE suite_actions SET state=?,receipt_json=?,updated_at=? WHERE action_id=?',
                       (state, canonical(receipt), time.time(), action_id))
        return receipt
