"""Exercise the real chat route with already uploaded clips; never upload again."""
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FOLDER = ROOT / 'output/validation/chat-publishing'


def main():
    from hinglish_app.server import AppState
    from hinglish_publish.store import Store
    FOLDER.mkdir(parents=True, exist_ok=True)
    marker = FOLDER / 'live-chat-request.json'
    bridge = json.loads((ROOT / 'cache/app/bridge.json').read_text('utf-8-sig'))
    def call(path, payload=None):
        req = urllib.request.Request(bridge['url'] + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'X-Hinglish-Token': bridge['token']})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    before = Store(ROOT).list()
    if marker.exists():
        record = json.loads(marker.read_text('utf-8'))
    else:
        manifest = json.loads((ROOT / 'output/validation/youtube-two-channel-local-demo-20261019/prepared.json').read_text('utf-8'))
        assert manifest['reviewed'] is True
        state = AppState(ROOT)
        session = state.assistant.create()['id']
        attached = []
        for clip in manifest['clips']:
            video = Path(clip['video'])
            video.with_suffix('.publish.json').write_text(json.dumps({'metadata_language': 'en', 'metadata': clip['metadata']}), 'utf-8')
            attached.append(state.assistant.attach(session, video)['id'])
        record = {'session': session, 'created': time.time(), 'expected_existing_results': 4, 'draft_only': True,
                  'note': 'Validation reuses already accepted private video identities; it never invokes the final upload action.'}
        marker.write_text(json.dumps(record, indent=2), 'utf-8')
        call('/api/assistant/message', {'session': session, 'profile': 'general', 'attachments': attached,
             'message': 'Prepare private YouTube drafts for both my YouTube channels, one long and one Short, with titles and descriptions.'})
    deadline = time.monotonic() + 60
    while True:
        snapshot = call('/api/assistant/session?id=' + record['session'])
        if snapshot['status'] not in ('planning', 'running', 'transcribing') or time.monotonic() > deadline:
            break
        time.sleep(.5)
    assert snapshot['status'] == 'complete', snapshot['stage']
    results = snapshot['messages'][-1].get('publish_results', [])
    assert len(results) == 4 and all(r['visibility'] == 'private' for r in results)
    assert len(Store(ROOT).list()) == len(before), 'Expected deduplication, not new queue items.'
    receipt = {'session': record['session'], 'status': snapshot['status'], 'stage': snapshot['stage'],
               'results': results, 'no_new_queue_items': True, 'no_upload_endpoint_invoked': True,
               'saved_copy_reused': True, 'health': call('/api/health'),
               'url': bridge['url'] + '/publisher.html?chat=' + record['session']}
    (FOLDER / 'live-chat-reuse-receipt.json').write_text(json.dumps(receipt, indent=2), 'utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
