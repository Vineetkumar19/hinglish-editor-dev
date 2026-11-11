"""Explicit, live model acceptance; selected synthetic source data, no actions."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['chatgpt', 'local14b', 'local9b'])
    args = parser.parse_args()
    folder = ROOT / 'data' / 'brain-validation' / (args.engine + '-' + str(time.time_ns()))
    folder.mkdir(parents=True)
    from core import config
    config._LOADED = True
    os.environ.update(DATA_DIR=str(folder), DB_URL='sqlite:///' + str(folder / 'suite.db'),
                      DRY_RUN='true', NOTIFY_CHANNELS='store', LOG_LEVEL='CRITICAL')
    from core.store import Store
    from core.workflow_service import WorkflowService
    store = Store()
    service = WorkflowService(store)
    task = service.create('learning_evidence', 'Plan a source-backed personal integration lab',
        {'goal': 'Reliable workflow adapters', 'period': 'Acceptance probe on 4 November 2026',
         '_brain': args.engine, 'entries': [{'description': 'Read the task identity and exact-payload approval contract.',
            'stage': 'reading', 'context': 'personal_lab', 'source_ref': 'fixture:contract-reading'}]},
        'brain-acceptance-' + args.engine, budgets={'runtime_seconds': 300})
    print(json.dumps({'state': 'running', 'engine': args.engine, 'evidence': str(folder)}), flush=True)
    result = service.prepare(task['task_id'])
    receipt = {'engine': args.engine, 'state': result['state'], 'result': result['result'],
               'external_actions': store.query('SELECT * FROM suite_actions'), 'fixture': True}
    (folder / 'result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'engine': args.engine, 'state': result['state'], 'error': result['result'].get('error'),
        'model': result['result'].get('brain', {}).get('model'), 'evidence': str(folder)}), flush=True)
    return 0 if result['state'] == 'waiting_for_review' and not receipt['external_actions'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
