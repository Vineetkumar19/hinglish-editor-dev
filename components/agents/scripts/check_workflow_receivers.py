"""Read-only checks against endpoints observed in the existing projects' source."""
import json
from pathlib import Path
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
checks = []
for name, url in [('cortana', 'http://127.0.0.1:8000/api/health'),
                  ('storylens', 'http://127.0.0.1:8765/api/health'),
                  ('ollama', 'http://127.0.0.1:11434/api/tags')]:
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read(100000))
            if name == 'ollama':
                data = {'model_count': len(data.get('models', [])), 'generation_test_performed': False}
            checks.append({'receiver': name, 'endpoint': url, 'status': response.status, 'observed': data})
    except Exception as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        checks.append({'receiver': name, 'endpoint': url, 'error': type(reason).__name__,
                       'os_error': getattr(reason, 'winerror', None) or getattr(reason, 'errno', None),
                       'http_status': getattr(exc, 'code', None)})
result = {'checked_at': time.time(), 'checks': checks,
    'suite_adapter_configured': (ROOT / 'profiles/workflow_integrations.json').exists(),
    'scope': 'Existing read-only service endpoints; reachability does not establish a compatible task/approval/artifact receiver.'}
out = ROOT / 'data/workflow-validation/receiver-checks.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
