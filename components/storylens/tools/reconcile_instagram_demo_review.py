"""Record an actually inspected publication; never represent it as automatic verification.

Run only while the editor is stopped. This is the bounded recovery for the demo
whose Share completed but whose automatic receipt timed out.
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'output/validation/local-instagram-demo-20261019'
JOB = '237acf90d4734a21'
URL = 'https://www.instagram.com/fantasy_legends91/reel/DeqTptLqqag/'


def main():
    assert (FOLDER / 'second-published.png').is_file()
    path = ROOT / 'cache/local-browser/state.json'
    state = json.loads(path.read_text('utf-8'))
    assert not any(j['status'] in ('queued', 'running', 'sharing') for j in state['jobs'])
    job = next(j for j in state['jobs'] if j['id'] == JOB)
    assert job['status'] == 'needs_review' and job['submission_started'] is True
    assert job['account'] == 'fantasy_legends91' and job['last_phase'] == 'sharing'
    checked = time.time()
    audit = {
        'job': JOB, 'checked': checked, 'url': URL, 'caption': job['caption'],
        'extension_version': '0.3.0', 'local_extension_performed_share': True,
        'local_extension_entered_saved_caption': True, 'caption_repaired_by_codex': False,
        'automatic_receipt_status': job['status'], 'automatic_receipt_message': job['message'],
        'verification_method': 'operator_browser_review',
        'evidence': 'Exact new permalink and complete caption inspected in published article; owner View Insights and Original audio visible; profile increased from 3 to 4 posts.',
        'proof': 'second-published.png', 'instagram_tabs': 1, 'new_llm_request_on_resume': False,
        'source': job['video'], 'no_additional_share_or_caption_edit_during_review': True,
    }
    (FOLDER / 'second-publication-reconciliation.json').write_text(json.dumps(audit, indent=2), 'utf-8')
    job.update(status='published', url=URL, verified=checked,
               verification_method='operator_browser_review', review_audit=audit,
               message='Published; exact Reel and saved caption verified by operator browser review after automatic receipt timeout.')
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), 'utf-8')
    chat_path = ROOT / 'cache/assistant/6623f8432ea14a5e.json'
    chat = json.loads(chat_path.read_text('utf-8'))
    chat.update(status='complete', stage='Published; verified by operator review after automatic receipt timeout.')
    chat['messages'].append({'id': 'second-demo-publication-review', 'role': 'assistant',
        'text': 'Published to @fantasy_legends91. The local extension uploaded the video and saved its caption. Operator browser review confirmed the actual Reel after the automatic receipt timed out.',
        'created': checked, 'profile': 'general', 'browser_url': URL})
    chat_path.write_text(json.dumps(chat, indent=2, ensure_ascii=False), 'utf-8')
    print(json.dumps({'published': URL, 'verification_method': 'operator_browser_review'}))


if __name__ == '__main__':
    main()
