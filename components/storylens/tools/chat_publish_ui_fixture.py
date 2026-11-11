"""Loopback-only UI test. Fake accounts and fake uploader: cannot contact YouTube."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FOLDER = ROOT / 'output/validation/chat-publishing/ui-fixture'


def main():
    from hinglish_app.server import serve
    from hinglish_publish.store import fingerprint
    FOLDER.mkdir(parents=True, exist_ok=True)
    server, state = serve(FOLDER, 0)
    state.publisher.accounts = lambda profile='general': {
        'youtube': {'connected': True, 'id': 'test-' + profile, 'name': 'Validation ' + profile.title()},
        'instagram': {'connected': False, 'name': '', 'id': ''}}
    calls = []
    class FakeUploader:
        def __init__(self, *args): pass
        def publish(self, job, checkpoint):
            calls.append({'profile': job['profile'], 'kind': job['kind'], 'visibility': job['visibility']})
            remote = {'id': f'test{len(calls):07d}', 'url': f'https://www.youtube.com/watch?v=test{len(calls):07d}', 'privacy': 'private'}
            checkpoint(remote)
            (FOLDER / 'calls.json').write_text(json.dumps(calls), 'utf-8')
            return remote, 'uploaded_private'
    state.publisher.providers['youtube'] = FakeUploader
    session = state.assistant.create()['id']
    rows, ids, accounts = [], [], {}
    for profile in ('cricket', 'gaming'):
        accounts[profile] = state.publisher.accounts(profile)['youtube']
        for kind in ('long', 'short'):
            video = FOLDER / (session + '-' + profile + '-' + kind + '.mp4')
            video.write_bytes((profile + kind).encode())
            meta = {'title': 'UI validation ' + profile + ' ' + kind,
                    'description': 'Local interface test only. #Cricket #IPL #History', 'tags': ['Cricket'], 'instagram_caption': 'Test'}
            item = {'platform': 'youtube', 'profile': profile, 'kind': kind, 'video': str(video),
                    'fingerprint': fingerprint(video), 'metadata': meta, 'brain': 'UI fixture',
                    'visibility': 'private', 'thumbnail': '', 'video_url': ''}
            job_id = state.publisher.store.add_batch([item])[0]
            ids.append(job_id)
            rows.append({'id': job_id, 'channel': accounts[profile]['name'], 'profile': profile, 'kind': kind,
                         'source': 'Local UI fixture (no real video upload)', 'duration': 90 if kind == 'long' else 15,
                         'metadata': meta, 'status': 'draft', 'url': ''})
    review = {'id': uuid.uuid4().hex, 'ids': ids, 'accounts': accounts, 'rows': rows,
              'visibility': 'private', 'state': 'review', 'upload_requested': False}
    state.assistant._update(session, publishing_review=review, status='needs_review', profile='general', selected='publish')
    state.assistant._message(session, 'assistant', 'UI VALIDATION ONLY: these are fake accounts and a local test uploader. No Google or YouTube connection exists.', publishing_review=review)
    (FOLDER / 'connection.json').write_text(json.dumps({'pid': os.getpid(), 'session': session,
        'url': f'http://127.0.0.1:{state.port}/?chat={session}'}), 'utf-8')
    print('Local UI fixture ready; no real account provider is installed.', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
