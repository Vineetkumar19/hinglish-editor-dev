from pathlib import Path
import datetime as dt
import json
import shutil
import sys
import urllib.request

root = Path(__file__).parent
note = """## Latest owner activation and clean UI — 4 November 2026

The owner explicitly asked why feeds/GPT were OFF and requested collection and timed GPT research. This supersedes the earlier quiet-period OFF state: feeds and GPT are now enabled in the local saved configuration. Feeds run every 30 minutes; GPT is scheduled every 30 minutes from 18:00 to 00:00 IST (end exclusive), with 12 attempts/day. Both remain individually switchable; schedules, dates, domains and caps remain owner-editable. Do not reset them OFF based on the earlier instruction. Verify current persisted settings before future changes.

The current GPT engine uses official ChatGPT-authenticated Codex CLI live web search, NOT visible Chrome automation. Full GPT research execution remains untested; no run was forced outside the selected window. Native heartbeat automations stay PAUSED to avoid duplicate research. Feed collection works for public Reddit/news candidates; X/Instagram returned zero indexed direct posts and r/Cricket was rate-limited. Do not claim complete social coverage, downloaded Reels, or verified news merely from candidates.

The inbox now has a simple event bar, feed/GPT switches, To review/Selected/Skipped tabs, source/search filters and compact cards. Detailed schedules and domains are under Settings. Browser checks passed for Settings open/close, source/search filtering and Selected view, with no captured JavaScript console errors. No posting was performed. UI proof: D:/Workflow_Automation/cricket-meme-inbox/clean-ui.png.

"""

if '--global' in sys.argv:
    destination = Path('C:/Users/Vineet Kumar/.codex/references/cricket-meme-inbox-20261104')
    for name in ('OWNER-CONTROLS.md', 'RESEARCH-RUNBOOK.md', 'README.md', 'ui-update-result.json'):
        shutil.copy2(root / name, destination / name)
    skill = Path('C:/Users/Vineet Kumar/.codex/skills/storylens-workflows/SKILL.md')
    text = skill.read_text(encoding='utf-8')
    old = 'Latest default is OFF until owner enables for an auction/tournament. No automatic model call for this quiet period.'
    new = 'Latest owner activation on 4 November supersedes the earlier OFF state: saved feeds and GPT are ON. Feeds every 30 min; GPT every 30 min 18:00–00:00 IST, max 12/day; independently switchable and owner-editable. Inspect current saved settings, do not reset OFF from historical notes. GPT uses live web search, not Chrome UI automation.'
    if old in text:
        skill.write_text(text.replace(old, new), encoding='utf-8')
    elif new not in text:
        raise RuntimeError('Expected inbox instruction not found; no broad rewrite attempted')
    print('Global reference and Storylens skill activation reconciled')
else:
    state = json.load(urllib.request.urlopen('http://127.0.0.1:8879/api/state', timeout=10))
    cfg = state['config']
    assert cfg['enabled'] and cfg['gpt_enabled']
    for name in ('OWNER-CONTROLS.md', 'RESEARCH-RUNBOOK.md', 'README.md'):
        path = root / name
        text = path.read_text(encoding='utf-8')
        if not text.startswith(note):
            path.write_text(note + text.replace('LATEST: GPT research OFF', 'Historical checkpoint: GPT research OFF', 1), encoding='utf-8')
    result = {
        'verified_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'config': cfg,
        'candidates': len(state['items']),
        'browser_checks': ['settings open/close', 'Reddit source filter', 'search filter', 'Selected empty state', 'both activation checkboxes checked'],
        'console_errors_observed': [],
        'gpt_live_run_tested': False,
        'gpt_running_at_check': state['gpt_running'],
        'engine': 'ChatGPT-authenticated official Codex CLI live web search; no Chrome UI automation',
        'screenshot': str(root / 'clean-ui.png'),
        'no_publishing': True,
        'task_ui_actions_finished': True,
    }
    (root / 'ui-update-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    path = root / 'RESULT.json'
    previous = json.loads(path.read_text(encoding='utf-8'))
    previous.update(local_scheduler='Owner-enabled; feeds every 30 min, GPT 18:00–00:00 IST every 30 min', feeds_off=False, gpt_off=False, inbox_candidates=len(state['items']), reason='Latest explicit owner activation supersedes quiet-period OFF', ui_screenshot='clean-ui.png', ui_update_receipt='ui-update-result.json')
    path.write_text(json.dumps(previous, indent=2), encoding='utf-8')
    print(json.dumps({'saved_activation': True, 'candidates': len(state['items']), 'gpt_live_run_tested': False}))
