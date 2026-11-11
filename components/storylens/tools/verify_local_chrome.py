"""Verify local assistant -> Chrome preview. This tool never requests publication."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'output/validation/local-chrome-integration'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preview', 'status'])
    parser.add_argument('--wait', type=int, default=0)
    args = parser.parse_args()
    bridge = json.loads((ROOT / 'cache/app/bridge.json').read_text('utf-8-sig'))
    FOLDER.mkdir(parents=True, exist_ok=True)

    def call(path, body=None):
        req = urllib.request.Request(bridge['url'] + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'X-Hinglish-Token': bridge['token']})
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)

    if args.action == 'preview':
        for attempt in range(40):
            status = call('/api/local-browser')
            if status['connected'] and status['extension_version'] == '0.2.0':
                break
            time.sleep(1)
        else:
            raise RuntimeError('Connect extension 0.2.0 before this test.')
        session = call('/api/assistant/session', {})
        video = ROOT / 'output/validation/gaming-youtube-existing-footage-20261018/short.mp4'
        attachment = call('/api/assistant/attach', {'session': session['id'], 'path': str(video)})
        message = ('Prepare an Instagram Reel preview for @vineet_editz19 using this finished clip. '
                   'Write a caption about the video. Do not post or click Share.')
        call('/api/assistant/message', {'session': session['id'], 'message': message,
                                      'attachments': [attachment['id']], 'profile': 'general'})
        (FOLDER / 'live-preview-session.json').write_text(json.dumps(
            {'session': session['id'], 'request': message}, indent=2), 'utf-8')
        print(json.dumps({'session': session['id'], 'status': 'planning', 'publication_requested': False}))
        return

    record = json.loads((FOLDER / 'live-preview-session.json').read_text('utf-8'))
    deadline = time.monotonic() + min(50, max(0, args.wait))
    while True:
        session = call('/api/assistant/session?id=' + record['session'])
        if session['status'] not in ('planning', 'running', 'transcribing') or time.monotonic() >= deadline:
            break
        time.sleep(2)
    connection = call('/api/local-browser')
    job = next((j for j in connection['jobs'] if j.get('session') == record['session']), None)
    result = {'session': record['session'], 'status': session['status'], 'stage': session.get('stage'),
              'brain': session.get('brain'), 'messages': session['messages'], 'connection': connection}
    (FOLDER / 'live-preview-check.json').write_text(json.dumps(result, indent=2), 'utf-8')
    print(json.dumps({'status': session['status'], 'stage': session.get('stage'),
                      'extension_version': connection['extension_version'], 'job': job}))


if __name__ == '__main__':
    main()
