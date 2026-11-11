"""Additive records in the existing Store, using database atomic claims.

The execution row is separate from graph completion: reaching END does not prove
that a remote action happened. No worker/scheduler is started by this module.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from . import config
from .store import new_id
from .workflow_contracts import ArtifactRef, STATES, TERMINAL, TaskEnvelope, canonical, digest, input_references

SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS suite_tasks (
       task_id TEXT PRIMARY KEY, role TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
       request_hash TEXT NOT NULL, envelope_json TEXT NOT NULL, input_json TEXT NOT NULL,
       state TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL,
       result_json TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
       updated_at DOUBLE PRECISION NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS suite_artifacts (
       artifact_id TEXT NOT NULL, revision TEXT NOT NULL, ref_json TEXT NOT NULL,
       PRIMARY KEY (artifact_id,revision))''',
    '''CREATE TABLE IF NOT EXISTS suite_reviews (
       approval_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, task_revision INTEGER NOT NULL,
       binding_json TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)''',
    '''CREATE TABLE IF NOT EXISTS suite_actions (
       action_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
       state TEXT NOT NULL, receipt_json TEXT NOT NULL, updated_at DOUBLE PRECISION NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS suite_leases (
       resource TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL)''',
)


class Conflict(ValueError):
    pass


class WorkflowStore:
    def __init__(self, store):
        self.store = store
        with store.tx():
            for sql in SCHEMA:
                store.execute(sql)

    @staticmethod
    def decode(row):
        if not row:
            return None
        row = dict(row)
        for key in ('envelope', 'input', 'result'):
            row[key] = json.loads(row.pop(key + '_json'))
        row['paused'] = bool(row['paused'])
        return row

    def get(self, task_id):
        return self.decode(self.store.one('SELECT * FROM suite_tasks WHERE task_id=?', (task_id,)))

    def list(self, limit=100):
        return [self.decode(r) for r in self.store.query(
            'SELECT * FROM suite_tasks ORDER BY updated_at DESC LIMIT ?', (min(limit, 200),))]

    def create(self, envelope: TaskEnvelope, inputs):
        envelope.validate()
        data = envelope.to_json()
        request_hash = digest({'envelope': {k: v for k, v in data.items() if k != 'task_id'}, 'input': inputs})
        ts = time.time()
        with self.store.tx():
            inserted = self.store.execute('''INSERT INTO suite_tasks VALUES (?,?,?,?,?,?,?,0,1,?,?,?)
                ON CONFLICT(idempotency_key) DO NOTHING''',
                (envelope.task_id, envelope.role, envelope.idempotency_key, request_hash,
                 canonical(data), canonical(inputs), 'queued', '{}', ts, ts))
            row = self.store.one('SELECT * FROM suite_tasks WHERE idempotency_key=?', (envelope.idempotency_key,))
            if row['request_hash'] != request_hash:
                raise Conflict('This idempotency key already names different inputs')
            self.store.event('workflow_created' if inserted.rowcount else 'workflow_duplicate', envelope.role,
                             row['task_id'], request_hash=request_hash)
        return self.decode(row)

    def update(self, task_id, state, result, *, expected_revision=None):
        if state not in STATES:
            raise ValueError('Unknown task state')
        row = self.get(task_id)
        if not row:
            raise KeyError(task_id)
        if row['state'] == 'cancelled' or row['paused']:
            raise Conflict('Task is cancelled or paused')
        from .workflow_contracts import Outcome
        receipt = result.get('receipt', {})
        result = {**result, 'outcome': Outcome(task_id,
            result.get('verified_result',''),
            list(dict.fromkeys(result.get('evidence_refs',[]) + receipt.get('evidence_refs',[]) +
                [e for a in result.get('artifacts',[]) for e in a.get('evidence',[])])),
            [result['error']] if result.get('error') else [],
            [v for v in result.get('destinations',{}).values() if v.get('verified')],
            result.get('next_valid_action','')).to_json()}
        metrics = {**row['result'].get('metrics',{}), **result.get('metrics',{})}
        blocked = metrics.get('blocked_seconds',0)
        if row['state'].startswith('waiting_for_') or row['state'] == 'reconciling':
            blocked += max(0,time.time()-row['updated_at'])
        metrics.update(blocked_seconds=blocked, revision_count=row['revision'],
            correction_count=max(0,row['revision']-1),
            duplicate_requests=self.store.one("SELECT COUNT(*) AS n FROM events WHERE thread_id=? AND kind='workflow_duplicate'", (task_id,))['n'])
        result['metrics'] = metrics
        rev = expected_revision or row['revision']
        with self.store.tx():
            cur = self.store.execute('''UPDATE suite_tasks SET state=?, result_json=?, updated_at=?
                WHERE task_id=? AND revision=? AND state!='cancelled' AND paused=0''',
                (state, canonical(result), time.time(), task_id, rev))
            if cur.rowcount != 1:
                raise Conflict('Task changed while work was running')
            self.store.event('workflow_state', row['role'], task_id, state=state, revision=rev,
                             result_hash=digest(result))
        return self.get(task_id)

    def control(self, task_id, action):
        row = self.get(task_id)
        if not row:
            raise KeyError(task_id)
        if row['state'] == 'cancelled':
            raise Conflict('Cancelled tasks cannot resume; create a new task')
        if action not in ('pause', 'resume', 'cancel'):
            raise ValueError('Unknown control')
        with self.store.tx():
            self.store.execute('UPDATE suite_tasks SET paused=?, state=?, updated_at=? WHERE task_id=?',
                (int(action == 'pause'), 'cancelled' if action == 'cancel' else row['state'], time.time(), task_id))
            if action == 'cancel':
                self.store.execute("UPDATE approvals SET status='expired' WHERE thread_id=? AND status='pending'", (task_id,))
            self.store.event('workflow_' + action, row['role'], task_id)
        return self.get(task_id)

    def revise(self, task_id, inputs, expected_revision):
        if not isinstance(inputs, dict) or len(canonical(inputs).encode('utf-8')) > 2_000_000:
            raise ValueError('Inputs must be a JSON object of at most 2 MB')
        row = self.get(task_id)
        if not row or row['state'] == 'cancelled' or row['paused']:
            raise Conflict('Task cannot be revised')
        # Never replace a payload while an action may have reached its destination.
        if self.store.one("SELECT action_id FROM suite_actions WHERE task_id=? AND state IN ('executing','uncertain')", (task_id,)):
            raise Conflict('Reconcile the previous action before revising')
        with self.store.tx():
            envelope = {**row['envelope'], 'input_refs': input_references(inputs)}
            cur = self.store.execute('''UPDATE suite_tasks SET input_json=?, envelope_json=?, revision=revision+1,
                state='queued',result_json='{}',updated_at=? WHERE task_id=? AND revision=? AND state!='cancelled' ''',
                (canonical(inputs), canonical(envelope), time.time(), task_id, expected_revision))
            if cur.rowcount != 1:
                raise Conflict('Stale task revision')
            self.store.execute("UPDATE approvals SET status='expired' WHERE thread_id=? AND status='pending'", (task_id,))
            self.store.event('workflow_revision', row['role'], task_id,
                             previous_revision=expected_revision, previous_input_hash=digest(row['input']))
            self.store.kv_set('workflow_revisions', f'{task_id}:{expected_revision}', row)
        return self.get(task_id)

    def acquire(self, resource, owner, seconds=120):
        ts = time.time()
        with self.store.tx():
            cur = self.store.execute('''INSERT INTO suite_leases VALUES (?,?,?)
                ON CONFLICT(resource) DO UPDATE SET owner=excluded.owner, expires_at=excluded.expires_at
                WHERE suite_leases.expires_at<=? OR suite_leases.owner=?''',
                (resource, owner, ts + seconds, ts, owner))
            return cur.rowcount == 1

    def release(self, resource, owner):
        self.store.run('DELETE FROM suite_leases WHERE resource=? AND owner=?', (resource, owner))

    def register_artifact(self, path, *, project, revision, evidence, artifact_id=None, approval_status='unreviewed'):
        file = Path(path).resolve(strict=True)
        if file.name.lower() in ('.env', 'credentials.json', 'token.json') or file.suffix.lower() in ('.token','.pem','.pfx','.key') or any(
                part.lower() in ('.ssh', '.aws', '.codex', 'browser-profile', 'integration-secrets') for part in file.parts):
            raise PermissionError('Credential and private application stores cannot be workflow artifacts')
        if approval_status not in ('unreviewed', 'approved', 'rejected'):
            raise ValueError('Unknown artifact approval status')
        if not file.is_file() or not evidence or not revision or not project:
            raise ValueError('Artifact requires a file, project, revision and evidence')
        # Registration is owner-selected local input, not an adapter's remote path.
        content_hash = file_hash(file)
        ref = ArtifactRef(artifact_id or new_id('artifact'), project, str(revision), content_hash,
            config.get('SUITE_DEVICE_ID', 'local'), str(file), file.suffix.lstrip('.') or 'file',
            evidence, approval_status).to_json()
        with self.store.tx():
            self.store.execute('INSERT INTO suite_artifacts VALUES (?,?,?) ON CONFLICT DO NOTHING',
                               (ref['artifact_id'], ref['revision'], canonical(ref)))
            saved = self.artifact(ref['artifact_id'], ref['revision'])
            if saved != ref:
                raise Conflict('An artifact revision is immutable')
        return ref

    def artifact(self, artifact_id, revision):
        row = self.store.one('SELECT ref_json FROM suite_artifacts WHERE artifact_id=? AND revision=?',
                             (artifact_id, str(revision)))
        if not row:
            raise ValueError(f'Unknown artifact revision: {artifact_id}/{revision}')
        return json.loads(row['ref_json'])

    def verify_artifacts(self, refs):
        verified = []
        for requested in refs:
            ref = self.artifact(requested['artifact_id'], requested['revision'])
            if requested.get('content_hash', ref['content_hash']) != ref['content_hash']:
                raise Conflict('Artifact hash differs from the registered revision')
            if ref['device_id'] != config.get('SUITE_DEVICE_ID', 'local'):
                raise Conflict('Artifact belongs to another device; authenticated transfer is required')
            if file_hash(Path(ref['locator'])) != ref['content_hash']:
                raise Conflict('Artifact changed; register a new revision and review again')
            verified.append(ref)
        return verified

    def backup_task(self, task_id):
        task = self.get(task_id)
        if not task:
            raise KeyError(task_id)
        return {'contract_version': 1, 'task': task,
            'reviews': self.store.query('SELECT * FROM suite_reviews WHERE task_id=?', (task_id,)),
            'actions': self.store.query('SELECT * FROM suite_actions WHERE task_id=?', (task_id,)),
            'events': self.store.query('SELECT * FROM events WHERE thread_id=? ORDER BY ts', (task_id,)),
            'restoration_policy': 'Audit backup only. Restored external actions must reconcile with the receiver.'}

    def redact_task(self, task_id):
        """Erase task-owned payloads, retaining replay-prevention tombstones.

        This does not delete shared contacts, registered artifacts, source files,
        independent commitment records, exported backups or receiver records.
        """
        task = self.get(task_id)
        if not task or task['state'] not in TERMINAL:
            raise Conflict('Finish or cancel the task before deleting its saved content')
        if self.store.one("SELECT action_id FROM suite_actions WHERE task_id=? AND state IN ('executing','uncertain')", (task_id,)):
            raise Conflict('Reconcile external actions before deleting their evidence')
        if self.store.one('SELECT resource FROM suite_leases WHERE resource=? AND expires_at>?', ('task:' + task_id, time.time())):
            raise Conflict('A task worker still owns this record')
        envelope = {**task['envelope'], 'intent': 'Deleted task content', 'input_refs': []}
        with self.store.tx():
            self.store.execute("UPDATE suite_tasks SET envelope_json=?,input_json='{}',result_json=?,state='cancelled',paused=0,updated_at=? WHERE task_id=?",
                (canonical(envelope), canonical({'content_deleted': True}), time.time(), task_id))
            self.store.execute("UPDATE approvals SET title='Deleted task content',payload_json='{}',decision_json=NULL,status='expired' WHERE thread_id=?", (task_id,))
            for row in self.store.query('SELECT approval_id,binding_json FROM suite_reviews WHERE task_id=?', (task_id,)):
                binding = json.loads(row['binding_json'])
                self.store.execute('UPDATE suite_reviews SET consumed=1,binding_json=? WHERE approval_id=?',
                    (canonical({'content_deleted': True, 'exact_payload_hash': binding.get('exact_payload_hash')}), row['approval_id']))
            self.store.execute("UPDATE suite_actions SET receipt_json='{}' WHERE task_id=?", (task_id,))
            self.store.execute("UPDATE events SET payload_json='{}' WHERE thread_id=?", (task_id,))
            self.store.kv_delete('workflow_scope', task_id)
            brain_key = task['result'].get('brain',{}).get('source_hash')
            if brain_key:
                other = any(json.loads(r['result_json']).get('brain',{}).get('source_hash') == brain_key
                    for r in self.store.query('SELECT result_json FROM suite_tasks WHERE task_id!=?',(task_id,)))
                if not other:
                    self.store.kv_delete('workflow_brain_plans',brain_key)
            for key in self.store.kv_list('workflow_revisions'):
                if key.startswith(task_id + ':'):
                    self.store.kv_delete('workflow_revisions', key)
            self.store.event('workflow_content_deleted', task['role'], task_id,
                retained='IDs and hashes prevent replay; shared records and source files are unchanged')
        return self.get(task_id)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()
