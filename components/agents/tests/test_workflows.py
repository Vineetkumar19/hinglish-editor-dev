from __future__ import annotations

import errno
import json
import socket
import time
import urllib.error
from unittest.mock import patch

from tests.base import SuiteCase
from core.workflow_contracts import digest
from core.workflow_store import Conflict, WorkflowStore
from core.workflow_service import WorkflowService
from core.workflow_broker import ExecutionBroker, IntegrationUnavailable

FIXTURE_TAGS = ' #Fixture #TestVideo #TestMedia #Validation #Workflow #Release #Intro #Video #Clip #Preview'


class WorkflowTests(SuiteCase):
    def setUp(self):
        super().setUp()
        self.service = WorkflowService(self.store)
        self.ledger = self.service.ledger
        now = time.time()
        self.store.run('''INSERT INTO leads (id,agent,company,email,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)''', ('client', 'video_client', 'Fixture client', 'client@example.com', 'qualified', now, now))

    def create(self, role='client_delivery', inputs=None, key='case', permissions=None):
        if inputs is None:
            inputs = self.brief()
        return self.service.create(role, 'Fixture review', inputs, key, permissions=permissions)

    def brief(self):
        return {'contact_id': 'client', 'brief': {'source_ref': 'fixture:brief', 'text': 'Edit the supplied clip.'},
            'scope': 'One edit, one revision', 'price': {'amount': 10000, 'currency': 'INR', 'evidence': 'fixture:agreement'},
            'deliverables': [{'id': 'main', 'description': 'One edit', 'acceptance': 'Approved playable export'}]}

    def artifact(self, name='clip.txt', content=b'fixture data'):
        path = self.tmp / name
        path.write_bytes(content)
        return self.ledger.register_artifact(path, project='storylens', revision='1', evidence=['fixture:approval'], approval_status='approved')

    def video_artifact(self, name='clip.mp4', color='blue'):
        from scripts.workflow_fixtures import video
        path = video(self.tmp / name, color)
        return self.ledger.register_artifact(path, project='storylens', revision='1', evidence=['fixture:approval'], approval_status='approved')

    def package(self):
        task = self.create(permissions=['prepare', 'delivery.send'])
        self.service.prepare(task['task_id'])
        self.service.decide(task['task_id'], True)
        inputs = self.brief()
        ref = self.artifact()
        inputs.update(phase='package', recipient='client@example.com', files=[ref],
                      file_deliverables={'main': ref['artifact_id']}, acceptance_evidence=['fixture:playback'])
        self.ledger.revise(task['task_id'], inputs, 1)
        result = self.service.prepare(task['task_id'])
        self.assertEqual(result['state'], 'waiting_for_review', result)
        self.service.decide(task['task_id'], True)
        return self.ledger.get(task['task_id']), ref

    def test_duplicate_task_and_changed_key_conflict(self):
        a = self.create()
        b = self.create()
        self.assertEqual(a['task_id'], b['task_id'])
        with self.assertRaises(Conflict):
            self.create(inputs={**self.brief(), 'scope': 'Different'})

    def test_content_deletion_retains_replay_tombstone_and_shared_contact(self):
        task = self.create()
        self.service.prepare(task['task_id'])
        self.ledger.control(task['task_id'], 'cancel')
        deleted = self.ledger.redact_task(task['task_id'])
        self.assertTrue(deleted['result']['content_deleted'])
        self.assertEqual(deleted['input'], {})
        self.assertEqual(self.create()['task_id'], task['task_id'])
        self.assertEqual(self.create()['state'], 'cancelled')
        self.assertIsNotNone(self.store.one('SELECT id FROM leads WHERE id=?', ('client',)))
        backup = json.dumps(self.ledger.backup_task(task['task_id']))
        self.assertNotIn('Edit the supplied clip', backup)
        with self.assertRaises(Conflict):
            self.ledger.revise(task['task_id'], self.brief(), 1)

    def test_health_preserves_wrapped_socket_error_and_unverified_model(self):
        from core.workflow_health import run_health
        error = PermissionError(errno.EACCES, 'Socket access denied')
        with patch('core.workflow_health.probe', side_effect=urllib.error.URLError(error)):
            report = run_health(self.store, probes=[{'id': 'local-service', 'kind': 'http'}])
        self.assertEqual(report['checks'][0]['classification'], 'permission')
        self.assertEqual(report['checks'][0]['os_error'], errno.EACCES)
        self.assertEqual(report['checks'][0]['cause_type'], 'PermissionError')
        report = run_health(self.store, probes=[{'id': 'model', 'kind': 'model'}])
        self.assertEqual(report['checks'][0]['classification'], 'unverified')

    def test_versioned_adapter_over_real_loopback_http_reuses_action(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from core.workflow_broker import IntegrationClient
        receipts, posts = {}, []
        class Receiver(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, data):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            def do_GET(self):
                if self.headers.get('Authorization') != 'Bearer fixture-token':
                    self.send_error(401)
                elif self.path == '/capabilities':
                    self.reply({'contract_version': 1, 'device_id': 'local',
                        'reconciliation': True, 'actions': ['delivery.send']})
                else:
                    self.reply(receipts[self.path.rsplit('/', 1)[1]])
            def do_POST(self):
                if self.headers.get('Authorization') != 'Bearer fixture-token':
                    return self.send_error(401)
                value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                posts.append(value)
                key = value['idempotency_key']
                receipts[key] = {'idempotency_key': key, 'exact_payload_hash': value['approval']['exact_payload_hash'],
                    'verified': True, 'remote_id': 'local-fixture-receipt', 'evidence_refs': ['fixture:http-receiver']}
                self.reply(receipts[key])
        server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        settings = self.tmp / 'integrations.json'
        settings.write_text(json.dumps({'cortana': {'base_url': 'http://127.0.0.1:' + str(server.server_port),
            'device_id': 'local', 'token_env': 'SUITE_FIXTURE_TOKEN'}}), encoding='utf-8')
        try:
            task, _ = self.package()
            with self.env(DRY_RUN='false', SUITE_INTEGRATIONS_FILE=str(settings), SUITE_FIXTURE_TOKEN='fixture-token'):
                client = IntegrationClient('cortana')
                receipt = self.service.broker.execute(task['result']['approval_id'], 'cortana', client)
                restarted = WorkflowService(self.store)
                self.assertEqual(restarted.broker.execute(task['result']['approval_id'], 'cortana', client), receipt)
                self.assertEqual(len(posts), 1)
                self.assertEqual(client.reconcile(posts[0]['idempotency_key']), receipt)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_review_restart_revision_and_scope_expansion(self):
        task = self.create()
        a = self.service.prepare(task['task_id'])
        self.service = WorkflowService(self.store)
        b = self.service.prepare(task['task_id'])
        self.assertEqual(a['result']['approval_id'], b['result']['approval_id'])
        self.service.decide(task['task_id'], True)
        self.ledger.revise(task['task_id'], {**self.brief(), 'scope': 'Two edits'}, 1)
        result = self.service.prepare(task['task_id'])
        self.assertTrue(result['result']['prepared']['scope_expansion'])

    def test_artifact_mutation_invalidates_approval(self):
        task, ref = self.package()
        from pathlib import Path
        Path(ref['locator']).write_bytes(b'changed after approval')
        with self.assertRaises(Conflict):
            self.service.broker.validate_review(task['result']['approval_id'])

    def test_cancelled_queued_action_never_runs(self):
        task, _ = self.package()
        self.ledger.control(task['task_id'], 'cancel')
        with self.assertRaises(Conflict):
            self.service.broker.validate_review(task['result']['approval_id'])
        with self.assertRaises(Conflict):
            self.ledger.control(task['task_id'], 'resume')

    def test_resource_claim_is_shared_between_connections(self):
        from core.store import Store
        other = Store(self.store.url)
        try:
            second = WorkflowStore(other)
            self.assertTrue(self.ledger.acquire('gpu:local', 'one'))
            self.assertFalse(second.acquire('gpu:local', 'two'))
            second.release('gpu:local', 'two')
            self.assertFalse(second.acquire('gpu:local', 'two'))
            self.ledger.release('gpu:local', 'one')
            self.assertTrue(second.acquire('gpu:local', 'two'))
        finally:
            other.close()

    def test_receiver_crash_reconciles_without_second_submission(self):
        task, _ = self.package()
        aid = task['result']['approval_id']
        class Receiver:
            calls = 0
            def capabilities(self):
                return {'contract_version': 1, 'device_id': 'local', 'actions': ['delivery.send'], 'reconciliation': True}
            def submit(self, payload):
                self.calls += 1
                self.key = payload['idempotency_key']
                raise ConnectionError('response lost after receiving')
            def reconcile(self, key):
                return {'idempotency_key': key, 'exact_payload_hash': key.removeprefix('action_'), 'verified': True, 'remote_id': 'fixture-remote', 'evidence_refs': ['fixture:receiver']}
        receiver = Receiver()
        with self.env(DRY_RUN='false'):
            with self.assertRaises(ConnectionError):
                self.service.broker.execute(aid, 'fixture', receiver)
            result = ExecutionBroker(self.store).execute(aid, 'fixture', receiver)
            self.assertTrue(result['verified'])
            again = ExecutionBroker(self.store).execute(aid, 'fixture', receiver)
            self.assertEqual(again['remote_id'], 'fixture-remote')
        self.assertEqual(receiver.calls, 1)

    def test_role_permissions_and_expiry(self):
        with self.assertRaises(PermissionError):
            self.create('research_experiment', {}, permissions=['delivery.send'])
        task, _ = self.package()
        aid = task['result']['approval_id']
        row = self.store.one('SELECT binding_json FROM suite_reviews WHERE approval_id=?', (aid,))
        binding = json.loads(row['binding_json'])
        binding['expiry'] = time.time() - 1
        self.store.run('UPDATE suite_reviews SET binding_json=? WHERE approval_id=?', (json.dumps(binding), aid))
        with self.assertRaises(Conflict):
            self.service.broker.validate_review(aid)

    def test_health_failure_classification_and_incident_cooldown(self):
        from core.workflow_health import classify, run_health
        cases = [(socket.gaierror(11001, 'dns'), 'dns'),
            (urllib.error.HTTPError('https://example.invalid', 401, 'expired', {}, None), 'authentication'),
            (OSError(errno.EADDRINUSE, 'busy'), 'busy_port'),
            (ConnectionRefusedError(errno.ECONNREFUSED, 'ollama unavailable'), 'dependency'),
            (OSError(errno.ENOSPC, 'full disk'), 'disk'), (PermissionError(10013, 'access'), 'permission')]
        for exc, category in cases:
            self.assertEqual(classify(exc), category)
        specs = [{'id': str(i), 'kind': 'fixture', 'workflows': ['client_delivery']} for i in range(len(cases))]
        for _ in range(2):
            with patch('core.workflow_health.probe', side_effect=[c[0] for c in cases]):
                report = run_health(self.store, specs, 0)
            self.assertEqual([c['classification'] for c in report['checks']], [c[1] for c in cases])
        self.assertEqual(len(self.store.query("SELECT * FROM events WHERE kind='health_incident'")), 1)

    def test_stale_worker_is_not_completed(self):
        from core.workflow_health import run_health
        self.store.run("INSERT INTO threads VALUES ('crashed','video_client','running',0,0,'{}')")
        report = run_health(self.store, [], 0)
        self.assertEqual(report['checks'][0]['classification'], 'worker_crash')
        self.assertFalse(report['ready'])

    def test_inbox_reimports_deduplicate_and_ambiguous_date_stays_open(self):
        inputs = {'messages': [{'source_ref': 'fixture:mail', 'source_id': 'm1', 'contact_id': 'client',
            'received_at': '2026-11-04T12:00:00+05:30', 'text': 'I will send it tomorrow.'}]}
        for i in range(2):
            task = self.create('inbox_commitment', inputs, key=str(i))
            result = self.service.prepare(task['task_id'])
            self.assertEqual(result['state'], 'waiting_for_review', result)
            c = result['result']['prepared']['commitments'][0]
            self.assertEqual(c['deadline'], '')
            self.assertEqual(c['status'], 'proposed')
            self.service.decide(task['task_id'], True)
        self.assertEqual(len(self.store.kv_list('commitments')), 1)

    def test_learning_cannot_turn_reading_into_work_experience(self):
        task = self.create('learning_evidence', {'goal': 'Terraform', 'period': 'November', 'entries': [
            {'description': 'Read modules guide', 'stage': 'demonstrated', 'context': 'personal_lab', 'source_ref': 'fixture:lab'}]})
        self.assertEqual(self.service.prepare(task['task_id'])['state'], 'failed')

    def test_three_intro_release_package_preserves_identity(self):
        refs = [self.video_artifact(f'intro{i}.mp4', color) for i, color in enumerate(('red', 'blue', 'green'))]
        inputs = {'body_revision': 'body-2', 'edit_approval_ref': 'fixture:edit', 'rights_evidence': ['fixture:rights'],
            'cinematic_trials': True, 'packages': [{'platform': 'instagram', 'account': 'fixture',
                'time': '2026-11-05T18:00:00+05:30', 'title': 'Fixture title', 'caption': 'Fixture caption' + FIXTURE_TAGS,
                'artifact': ref, 'intro_id': f'intro-{i}'} for i, ref in enumerate(refs)]}
        task = self.create('content_release', inputs)
        result = self.service.prepare(task['task_id'])
        self.assertEqual(result['state'], 'waiting_for_review', result)
        self.assertEqual(len({p['intro_id'] for p in result['result']['prepared']['packages']}), 3)
        self.assertEqual(self.store.query('SELECT * FROM suite_actions'), [])

    def test_experiment_reproduces_metrics_from_exact_dataset(self):
        dataset = {'provenance': 'synthetic fixture, not actual StoryLens footage',
            'clips': [{'id': 'a', 'text': 'waterfall forest', 'source_ref': 'fixture:a'},
                      {'id': 'b', 'text': 'city car', 'source_ref': 'fixture:b'}],
            'queries': [{'id': 'q', 'text': 'waterfall', 'relevant_ids': ['a'], 'split': 'held_out'}]}
        ref = self.artifact('dataset.json', json.dumps(dataset).encode())
        inputs = {'question': 'Does TF-IDF improve metadata retrieval?', 'source_ref': 'fixture:research',
                  'license': 'self-authored fixture', 'dataset': ref}
        metrics = []
        for i in range(2):
            task = self.create('research_experiment', inputs, key=str(i))
            result = self.service.prepare(task['task_id'])
            self.assertEqual(result['state'], 'succeeded', result)
            metrics.append(result['result']['candidate']['mrr'])
        self.assertEqual(metrics, [1.0, 1.0])

    def test_experiment_registration_interruption_reuses_measured_bytes(self):
        dataset = {'provenance': 'fixture', 'clips': [{'id': 'a', 'text': 'waterfall', 'source_ref': 'fixture:a'}],
            'queries': [{'id': 'q', 'text': 'waterfall', 'relevant_ids': ['a'], 'split': 'held_out'}]}
        ref = self.artifact('restart-dataset.json', json.dumps(dataset).encode())
        task = self.create('research_experiment', {'question': 'Metadata comparison', 'source_ref': 'fixture:research',
            'license': 'Self-authored fixture', 'dataset': ref})
        original = self.ledger.register_artifact
        calls = []
        def interrupted(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            if len(calls) == 2:
                raise OSError('Simulated interruption after second artifact commit')
            return result
        with patch.object(self.ledger, 'register_artifact', side_effect=interrupted):
            self.assertEqual(self.service.prepare(task['task_id'])['state'], 'failed')
        result = WorkflowService(self.store).prepare(task['task_id'])
        self.assertEqual(result['state'], 'succeeded', result)
        recovered = {ref['artifact_id']: ref for ref in result['result']['artifacts']}
        for ref in calls:
            self.assertEqual(recovered[ref['artifact_id']], ref)

    def test_cross_agent_contact_claim_prevents_second_initial_send(self):
        from core.mailer import Mailer, OutgoingMessage, SendBlocked
        from tests.fakes.servers import FakeSMTPServer
        smtp = FakeSMTPServer().start()
        try:
            with self.env(DRY_RUN='false', SMTP_HOST='127.0.0.1', SMTP_PORT=smtp.port,
                          SMTP_STARTTLS='false', SMTP_REQUIRE_TLS='false', SMTP_USER='', SMTP_PASSWORD=''):
                mailer = Mailer(self.store, transport='smtp')
                mailer.send(OutgoingMessage(to='client@example.com', subject='One reviewed pitch',
                    body='This is a complete, reviewed fixture pitch for a local server.', tag='video_client'))
                with self.assertRaises(SendBlocked):
                    mailer.send(OutgoingMessage(to='client@example.com', subject='Competing pitch',
                        body='This is a different complete fixture pitch from another agent.', tag='saas_sales'))
                self.assertEqual(len(smtp.messages), 1)
        finally:
            smtp.stop()

    def test_release_destinations_review_separately_and_reuse_verified_receipts(self):
        ref = self.video_artifact()
        inputs = {'body_revision': 'body-1', 'edit_approval_ref': 'fixture:edit', 'rights_evidence': ['fixture:rights'],
            'packages': [{'platform': platform, 'account': 'fixture-' + platform,
                'time': '2026-11-05T18:00:00+05:30', 'title': 'Fixture', 'caption': 'Fixture caption' + FIXTURE_TAGS,
                'artifact': ref, 'intro_id': 'intro-1'} for platform in ('youtube', 'instagram')]}
        task = self.create('content_release', inputs)
        self.service.prepare(task['task_id'])
        result = self.service.decide(task['task_id'], True)
        self.assertEqual(len(result['result']['review_ids']), 2)
        for aid in result['result']['review_ids']:
            self.service.decide(task['task_id'], True, aid)
        calls = []
        def dispatch(aid, integration):
            calls.append(aid)
            if len(calls) == 2:
                raise IntegrationUnavailable('second destination offline')
            return {'verified': True, 'remote_id': 'fixture-remote-' + aid, 'evidence_refs': ['fixture:receiver']}
        with patch.object(self.service.broker, 'execute', side_effect=dispatch):
            partial = self.service.dispatch(task['task_id'])
            self.assertEqual(partial['state'], 'partially_succeeded')
            finished = self.service.dispatch(task['task_id'])
            self.assertEqual(finished['state'], 'succeeded')
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1], calls[2])
        self.assertNotEqual(calls[0], calls[2])
