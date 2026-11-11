"""Run the actual HTTP console against isolated, clearly labelled fixture data.

No production configuration, contacts, model inference, posting or mail delivery.
The server can stay up for native-browser acceptance using --serve.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    evidence = ROOT / 'data' / 'workflow-validation'
    evidence.mkdir(parents=True, exist_ok=True)
    run_dir = evidence / str(time.time_ns())
    run_dir.mkdir()
    from core import config
    config._LOADED = True
    os.environ.update(DRY_RUN='true', LLM_PROVIDER='offline', NOTIFY_CHANNELS='store', LOG_LEVEL='CRITICAL',
        DATA_DIR=str(run_dir), DB_URL='sqlite:///' + str(run_dir / 'suite.db'),
        DASHBOARD_TOKEN='workflow-fixture-review', SUITE_DEVICE_ID='local',
        SUITE_INTEGRATIONS_FILE=str(run_dir / 'unconfigured.json'))
    from core.store import Store
    from core.workflow_service import WorkflowService
    from server.app import DashboardServer
    store = Store()
    service = WorkflowService(store)
    store.run('''INSERT INTO leads (id,agent,company,email,status,created_at,updated_at)
        VALUES ('fixture-client','video_client','Validation fixture — not a real client',
        'client@example.invalid','qualified',?,?)''', (time.time(), time.time()))
    from scripts.workflow_fixtures import video
    from core.workflow_media import inspect_video
    source = video(run_dir / 'fixture-delivery.mp4', 'orange')
    inspection = inspect_video(source)
    artifact = service.ledger.register_artifact(source, project='storylens', revision='fixture-1',
        evidence=['fixture:source-and-approval'], approval_status='approved')
    server = DashboardServer(('127.0.0.1', 0), store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    url = base + '/workflows?token=workflow-fixture-review'
    checks = []
    def request(path, payload=None, auth=True):
        req = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer workflow-fixture-review'} if auth else {})})
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode()
            return json.loads(raw) if response.headers.get_content_type() == 'application/json' else raw
    def check(name, condition):
        checks.append({'check': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(name)
    def create(role, inputs, key):
        return request('/api/workflows', {'role': role, 'intent': 'Validation: ' + key, 'inputs': inputs, 'idempotency_key': key})
    try:
        try:
            request('/api/workflows', auth=False)
            check('unauthenticated API rejected', False)
        except urllib.error.HTTPError as exc:
            check('unauthenticated API rejected', exc.code == 401)
        check('existing console still renders', 'Agent Suite' in request('/'))
        check('workflow form is inside the existing console', 'Start a client delivery' in request('/workflows'))
        brief = {'contact_id': 'fixture-client', 'brief': {'source_ref': 'fixture:enquiry', 'text': 'One short edit'},
            'scope': 'One clip, one revision', 'price': {'amount': 10000, 'currency': 'INR', 'evidence': 'fixture:price'},
            'deliverables': [{'id': 'main', 'description': 'Short edit', 'acceptance': 'Reviewed playable export'}]}
        delivery = create('client_delivery', brief, 'client-scope')
        check('client scope reaches actual review', delivery['state'] == 'waiting_for_review')
        same = create('client_delivery', brief, 'client-scope')
        check('duplicate HTTP submission reuses exact task', same['task_id'] == delivery['task_id'])
        reviewed = request('/api/workflows/' + delivery['task_id'] + '/approve', {})
        check('scope review persists via HTTP', reviewed['state'] == 'succeeded')
        package = {**brief, 'phase': 'package', 'recipient': 'client@example.invalid', 'files': [artifact],
            'file_deliverables': {'main': artifact['artifact_id']},
            'acceptance_evidence': ['fixture:container-inspection-' + str(inspection['duration_seconds'])]}
        request('/api/workflows/' + delivery['task_id'] + '/revise', {'revision': 1, 'inputs': package})
        prepared = request('/api/workflows/' + delivery['task_id'] + '/prepare', {})
        check('delivery package reaches exact-file review', prepared['state'] == 'waiting_for_review')
        messages = {'messages': [{'source_ref': 'fixture:message', 'source_id': 'm1', 'contact_id': 'fixture-client',
            'text': 'I will send the file by 2026-11-06.', 'received_at': '2026-11-04T12:00:00+05:30'}]}
        inbox = create('inbox_commitment', messages, 'selected-message')
        check('source-linked inbox suggestion visible', inbox['result']['prepared']['commitments'][0]['deadline'] == '2026-11-06')
        learning = create('learning_evidence', {'goal': 'Infrastructure lab', 'period': 'Fixture period',
            'entries': [{'description': 'Saved local lab output', 'stage': 'demonstrated', 'source_ref': 'fixture:lab',
                         'context': 'personal_lab', 'artifacts': [artifact]}]}, 'learning')
        check('learning evidence review visible', learning['state'] == 'waiting_for_review')
        dataset = {'provenance': 'Synthetic workflow acceptance data; not a StoryLens quality result',
            'clips': [{'id': 'waterfall', 'text': 'waterfall forest river', 'source_ref': 'fixture:clip1'},
                      {'id': 'city', 'text': 'city traffic road', 'source_ref': 'fixture:clip2'}],
            'queries': [{'id': 'q1', 'text': 'forest waterfall', 'relevant_ids': ['waterfall'], 'split': 'held_out'}]}
        dataset_path = run_dir / 'retrieval-dataset.json'
        dataset_path.write_text(json.dumps(dataset), encoding='utf-8')
        dataset_ref = service.ledger.register_artifact(dataset_path, project='agents', revision='fixture-1', evidence=['fixture:labels'])
        experiment = create('research_experiment', {'question': 'Does TF-IDF improve metadata retrieval over overlap?',
            'source_ref': 'fixture:research', 'license': 'Self-authored test data', 'dataset': dataset_ref}, 'retrieval-experiment')
        repeated = create('research_experiment', experiment['input'], 'retrieval-repeat')
        check('experiment reproducible through actual HTTP service', experiment['state'] == 'succeeded'
              and experiment['result']['candidate']['mrr'] == repeated['result']['candidate']['mrr'])
        packages = []
        from scripts.workflow_fixtures import video
        for index in range(3):
            video_file = video(run_dir / f'fixture-intro-{index}.mp4', ('red', 'green', 'blue')[index])
            video_ref = service.ledger.register_artifact(video_file, project='storylens', revision='fixture-1',
                evidence=['fixture:approval'], approval_status='approved')
            packages.append({'platform': 'instagram', 'account': 'fixture-account', 'time': f'2026-11-{5+index:02}T18:00:00+05:30',
                'title': 'Fixture trial', 'caption': 'Fixture trial caption #Fixture #TestVideo #TestMedia #Validation #Workflow #Release #Intro #Video #Clip #Preview', 'artifact': video_ref, 'intro_id': f'intro-{index+1}'})
        release = create('content_release', {'body_revision': 'body-fixture-1', 'edit_approval_ref': 'fixture:edit',
            'rights_evidence': ['fixture:rights'], 'cinematic_trials': True, 'packages': packages}, 'three-intro-release')
        release = request('/api/workflows/' + release['task_id'] + '/approve', {})
        check('three intros require three independent destination reviews', len(release['result']['review_ids']) == 3
              and release['state'] == 'waiting_for_review')
        signals = []
        for index in range(20):
            cid = f'fixture-contact-{index}'
            store.run('''INSERT INTO leads (id,agent,company,email,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?)''', (cid, 'saas_sales', f'Fixture enquiry {index}', f'fixture{index}@example.invalid',
                    'new', time.time(), time.time()))
            signals.append({'contact_id': cid, 'source_ref': f'fixture:enquiry-{index}',
                'observed_at': '2026-11-04T12:00:00+05:30', 'expressed_need': 'I need searchable clip notes',
                'source_text': 'I need searchable clip notes', 'capability_ids': ['clip-notes'],
                'draft': 'Your enquiry mentions searchable clip notes. Would a walkthrough of that capability help? (Validation fixture.)'})
        sales = create('saas_sales', {'signals': signals, 'capabilities': {'clip-notes':
            {'status': 'working', 'evidence_ref': 'fixture:capability'}}}, 'selected-demand-signals')
        check('20 supplied enquiries ranked with five unsent drafts', len(sales['result']['prepared']['ranked_needs']) == 20
            and len(sales['result']['prepared']['drafts']) == 5)
        sales = request('/api/workflows/' + sales['task_id'] + '/approve', {})
        check('sales drafts have per-message reviews', len(sales['result']['review_ids']) == 5)
        health = create('system_health', {}, 'health')
        check('health results visible without auto recovery', bool(health['result'].get('checks')))
        cancelled = request('/api/workflows/' + inbox['task_id'] + '/cancel', {})
        check('cancellation survives fresh service instance', WorkflowService(store).ledger.get(inbox['task_id'])['state'] == 'cancelled')
        backup = request('/api/workflows/' + delivery['task_id'] + '/backup')
        check('task audit backup contains event lineage', bool(backup['events']))
        deleted = request('/api/workflows/' + inbox['task_id'] + '/delete-content', {'confirmation': inbox['task_id']})
        check('task content deletion retains cancellation tombstone', deleted['result'].get('content_deleted') and deleted['state'] == 'cancelled')
        ids = {'delivery': delivery['task_id'], 'health': health['task_id'], 'learning': learning['task_id'], 'inbox': inbox['task_id'],
               'research': experiment['task_id'], 'release': release['task_id'], 'saas': sales['task_id']}
        result = {'url': url, 'base_url': base, 'run_dir': str(run_dir), 'checks': checks, 'tasks': ids,
            'scope': 'Real Suite HTTP server and SQLite; synthetic inputs, no live client/platform acceptance',
            'production_env_loaded': False, 'external_actions': 0, 'pid': os.getpid()}
        (evidence / 'latest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2), flush=True)
        if args.serve:
            while not (run_dir / 'stop-server').exists():
                time.sleep(.25)
    finally:
        server.shutdown()
        server.server_close()
        store.close()


if __name__ == '__main__':
    main()
