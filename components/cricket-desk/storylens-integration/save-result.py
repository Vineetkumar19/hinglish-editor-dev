from pathlib import Path
import datetime as dt
import hashlib
import json
import sys
import urllib.request

here = Path(__file__).parent
note = '''
## Storylens feature integration — 4 November 2026

Cricket Desk is now in the Storylens WEB feature menu: Show tools > Cricket Desk, beside Photo Collector. Direct entry: http://127.0.0.1:8765/?tool=cricketDesk. It opens the existing http://127.0.0.1:8879/ inbox in a single tool iframe, sharing the same saved database, selections and enabled schedule. There is no duplicate collector, new GPT run, worker restart, planner-model change or publication. Native Adobe CEP menus were not changed.

Actual running Storylens browser verification confirmed the feature is searchable/clickable and renders the real 80-candidate inbox with both feed/GPT switches checked. Source-description registration was corrected after a real feature-switch error; no later error appeared in captured logs. Automated clicks inside the cross-origin inbox iframe were unavailable (click/focus target errors), so embedded Settings interaction was not independently accepted in this integration pass. The same inbox's standalone Settings/search/selection checks passed in the earlier UI pass. Keep this scope distinction. Screenshot and detailed receipt: D:/Workflow_Automation/cricket-meme-inbox/storylens-integration/.

The existing Windows sign-in launcher starts Cricket Desk. If its service is stopped, open D:/Workflow_Automation/cricket-meme-inbox/Launch Cricket Desk.vbs. Do not start/restart Storylens merely to inspect this integration: static files are served without a restart.
'''

if '--global' in sys.argv:
    root = Path('C:/Users/Vineet Kumar/.codex')
    guide = root / 'references/cricket-meme-inbox-20261104/OWNER-CONTROLS.md'
    text = guide.read_text(encoding='utf-8')
    if '## Storylens feature integration — 4 November 2026' not in text:
        guide.write_text(note + '\n' + text, encoding='utf-8')
    skill = root / 'skills/storylens-workflows/SKILL.md'
    text = skill.read_text(encoding='utf-8')
    old = 'This is not an installed Storylens panel route or publishing authorization.'
    new = 'The Storylens web feature menu now includes Cricket Desk beside Photo Collector (/?tool=cricketDesk), using the same saved inbox/schedule. Native Adobe panels are unchanged. This is not publishing authorization. See the maintained owner-controls guide for live validation scope and service-start recovery.'
    if old in text:
        skill.write_text(text.replace(old, new), encoding='utf-8')
    elif new not in text:
        raise RuntimeError('Expected skill integration anchor missing')
    print('Global Storylens feature entry saved')
else:
    state = json.load(urllib.request.urlopen('http://127.0.0.1:8879/api/state', timeout=10))
    result = json.loads((here / 'result.json').read_text(encoding='utf-8'))
    static = Path('D:/Full Drive/remove silence/hinglish_app/static')
    result.update(
        browser_validation='Feature search/menu activation and real inbox render verified',
        validated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        iframe_mode='single direct iframe to existing 8879 service',
        embedded_settings_interaction='Computer-use click/focus target unavailable; not independently verified',
        standalone_settings='Previously verified; see ui-update-result.json',
        candidates=len(state['items']),
        feeds_enabled=state['config']['enabled'],
        gpt_enabled=state['config']['gpt_enabled'],
        screenshot=str(here / 'feature-visible.png'),
        task_ui_actions_finished=True,
        sha256={name:hashlib.sha256((static/name).read_bytes()).hexdigest() for name in ('index.html','app.js','icons.js','feature-tools.js')},
        backups=[str(p) for p in here.glob('backup-*')],
    )
    (here / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (here / 'INTEGRATION.md').write_text(note, encoding='utf-8')
    owner = here.parent / 'OWNER-CONTROLS.md'
    text = owner.read_text(encoding='utf-8')
    if '## Storylens feature integration — 4 November 2026' not in text:
        owner.write_text(note + '\n' + text, encoding='utf-8')
    print(json.dumps({'verified':True,'feeds_on':result['feeds_enabled'],'gpt_on':result['gpt_enabled']}))
