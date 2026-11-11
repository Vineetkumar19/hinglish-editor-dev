"""Consolidate actual evidence without promoting pending owner gates."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT/'data/real-delivery-acceptance'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    result = read(FOLDER/'result.json')
    integrated = read(FOLDER/'integrated-result.json')
    http = read(ROOT/'data/workflow-validation/latest.json')
    regression = read(ROOT/'data/test-results.json')
    restart = read(FOLDER/'restart-verification.json')
    accepted = (FOLDER/'owner-internal-acceptance.json').is_file()
    with sqlite3.connect((FOLDER/'suite.db').as_uri()+'?mode=ro', uri=True) as db:
        row = db.execute('SELECT result_json FROM suite_tasks WHERE task_id=?',
                         (integrated['sales']['task_id'],)).fetchone()
    sales = json.loads(row[0])
    video = next(a for a in result['render']['artifacts'] if a['type'] == 'mp4')
    folder = result['delivery']['workspace']['items'][0]['target']
    review = ['# Owner review — actual delivery and unsent drafts', '',
              'This review authorizes no sending, uploading, scheduling or publication.', '',
              f"[Play the actual ten-second excerpt](<{video['locator']}>)", '',
              f'[Open the Cortana delivery folder](<{folder}>)', '',
              'Scope: one straight ten-second source excerpt, original composition/audio, '
              'tracked revision and local attachment package. Owner-internal, INR 0; '
              'no third-party customer or fee agreement is asserted.', '',
              'Technical result: full decode, 960 x 720, 10 seconds, source unchanged, '
              'copied attachment hashes verified; browser played to the end.', '',
              '## Five proposed public replies', '',
              'These public issue reports are product feedback, not buying intent. '
              'Each reply is unsent and makes no framework-fix promise.', '']
    drafts = sales.get('prepared', {}).get('drafts', [])
    # Retain every review field rather than dropping provenance with presentation.
    for i, draft in enumerate(drafts, 1):
        review += [f'### Draft {i}', '', '```json', json.dumps(draft, indent=2, ensure_ascii=False), '```', '']
    review += ['## Personal learning summary', '',
               integrated['learning']['result']['prepared']['progress_summary'], '',
               'Proposed exercise: '+integrated['learning']['result']['prepared']['exercise'], '',
               ('Owner accepted the internal delivery and five drafts. This does not authorize sending/publication. '
                'Learning-summary approval was not inferred.' if accepted else
                'Owner review remains pending. Technical validation is not creative approval.'), '']
    (FOLDER/'OWNER-REVIEW.md').write_text('\n'.join(review), encoding='utf-8')
    report = {
        'status': 'internal_acceptance_complete' if accepted else 'live_receivers_and_brains_verified_owner_acceptance_pending',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'full_pdf_acceptance': False,
        'regression': regression,
        'fixture_http': {'checks': len(http['checks']), 'all_passed': all(c['passed'] for c in http['checks']),
                         'run_dir': http['run_dir'], 'scope': http['scope']},
        'live_receivers': restart,
        'brains': [{'engine': name, 'receipt': str(path), 'model': read(path)['result']['brain']['model'],
                    'fresh_model_response': read(path)['result']['brain']['fresh_model_response']}
                   for name, path in (
                       ('chatgpt', ROOT/'data/brain-validation/chatgpt-1793803552139608100/result.json'),
                       ('local14b', ROOT/'data/brain-validation/local14b-1793803649987928200/result.json'),
                       ('local9b', ROOT/'data/brain-validation/local9b-1793804276685303900/result.json'))],
        'delivery_case': {'task_id': result['task_id'], 'revision': result['revision'],
                          'type': result['case_type'], 'technically_verified': True, 'owner_review': result['owner_visual_review']},
        'browser_playback': {'duration': 10, 'current_time': 10, 'ended': True, 'ready_state': 4,
                             'width': 960, 'height': 720, 'error': None,
                             'evidence': str(FOLDER/'delivery-review.png')},
        'cortana_native_ui': {'evidence_source': 'Owner-authorized coordination with Cortana chat 01a1a6d8-5f28-7041-ba26-790b46fc88b5',
                              'restore_review': 'Resolved', 'outcome': 'Opened',
                              'exact_explorer_window_observed': True, 'explorer_contents_visually_verified': False,
                              'limitation': 'Window minimized; computer-control helper interruption. No repeated restore claimed.'},
        'native_publication_draft': read(FOLDER/'release-draft-result.json'),
        'native_prepare_post_ui_verified': False,
        'prepare_post_limit': 'Current UI takes preparation IDs, not publication-ledger job IDs; no fake preparation created.',
        'sales': integrated['sales'],
        'remaining_gates': [
            'Learning summary review remains pending; internal delivery and five drafts accepted.' if accepted else 'Owner review of delivery, learning summary and five drafts remains pending.',
            'Commercial enquiry/client acceptance not available; internal validation is labelled separately.',
            'Approved shared-body and three-intro production exports are absent; three-intro fixture checks do not replace them.',
            'Actual publication requires exact owner release authorization and verified platform/account support; no Trial Reels support inferred.'
        ],
        'sent': False, 'uploaded': False, 'published': False,
        'new_schedules_enabled': False,
        'documentation': str(ROOT/'docs/NEW_WORKFLOWS_IMPLEMENTATION.md')
    }
    if accepted:
        report['owner_internal_acceptance'] = read(FOLDER/'owner-internal-acceptance.json')
    (ROOT/'data/workflow-validation/final-status.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    shutil.copy2(ROOT/'data/test-results.json', FOLDER/'regression-final.json')
    print(json.dumps({'report': str(ROOT/'data/workflow-validation/final-status.json'),
                      'owner_review': str(FOLDER/'OWNER-REVIEW.md'), 'drafts': len(drafts)}))


if __name__ == '__main__':
    main()
