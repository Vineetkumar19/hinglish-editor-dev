"""Refuse a reload while any existing workflow or Google sign-in is active."""
from pathlib import Path
import json, urllib.request

root = Path(__file__).resolve().parents[1]
base = 'http://127.0.0.1:8765'
out = root / 'output/publisher-repair-2026-10-26'
out.mkdir(parents=True, exist_ok=True)
source = (root / 'tools/check_template_text_idle.py').read_text('utf-8')
source = source.replace("out=root/'output/template-text-evidence'", "out=root/'output/publisher-repair-2026-10-26'")
exec(compile(source, 'check_existing_jobs', 'exec'))
publisher = get('/api/publisher?profile=cricket', token)
tasks = publisher.get('tasks', [])
if isinstance(tasks, dict): tasks = list(tasks.values())
active_tasks = [{'id': t.get('id'), 'status': t.get('status')} for t in tasks if t.get('status') not in terminal]
browser=get('/api/local-browser',token)
active_browser=[{'id':j.get('id'),'status':j.get('status')} for j in browser.get('jobs',[]) if j.get('status') in ('running','sharing')]
record = {'active_publisher_tasks': active_tasks, 'active_browser_tasks': active_browser, 'worker_enabled': publisher.get('worker_enabled', False)}
(out / 'publisher-idle-before-reload.json').write_text(json.dumps(record, indent=2))
if active_tasks or active_browser or record['worker_enabled']:
    raise SystemExit('Publisher activity found. Service left running.')
print('Publisher idle; no Google sign-in or publishing task in progress.')
