"""Read-only verification of existing native receipts after receiver restart."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.workflow_broker import IntegrationClient
from core import config


def main():
    config._LOADED = True
    os.environ['SUITE_INTEGRATIONS_FILE'] = str(ROOT/'profiles/workflow_integrations.json')
    code_hash = hashlib.sha256((ROOT/'adapters/receiver.py').read_bytes()).hexdigest()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'receivers': {},
              'operation': 'GET only; no job resubmission'}
    for name in ('storylens', 'cortana', 'repository'):
        client = IntegrationClient(name)
        caps = client.capabilities()
        assert caps['receiver_source_hash'] == code_hash, name + ': stale receiver code'
        assert not caps['active_jobs'], name + ': receiver is not idle'
        database = ROOT/'data/receivers'/name/'receipts.sqlite3'
        with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as db:
            rows = db.execute('SELECT id,receipt FROM actions').fetchall()
        checked = []
        for key, raw in rows:
            previous = json.loads(raw)
            actual = client.reconcile(key)
            assert actual == previous, name + ': receipt changed on read'
            checked.append({'action_id': key, 'status': actual['status'],
                            'verified': actual.get('verified', False),
                            'remote_id': actual.get('remote_id')})
        report['receivers'][name] = {'source_hash': code_hash, 'runtime': caps['runtime'],
                                   'receipts': checked, 'active_jobs': []}
    path = ROOT/'data/real-delivery-acceptance/restart-verification.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(path), 'receivers': len(report['receivers']),
                      'receipts': sum(len(v['receipts']) for v in report['receivers'].values())}))


if __name__ == '__main__':
    main()
