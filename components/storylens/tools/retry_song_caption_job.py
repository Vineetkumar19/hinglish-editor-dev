"""Retry the user's rejected song captions through the running local editor."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT/'output/validation/song-captions/retry-job.json'


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    bridge = json.loads((ROOT/'cache/app/bridge.json').read_text(encoding='utf-8'))
    headers = {'Content-Type': 'application/json', 'X-Hinglish-Token': bridge['token']}
    def request(path, payload=None):
        req = Request(bridge['url']+path, headers=headers,
                      data=json.dumps(payload).encode('utf-8') if payload is not None else None)
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    if '--start' in sys.argv:
        if RECEIPT.exists():
            previous = json.loads(RECEIPT.read_text(encoding='utf-8'))
            job = request('/api/jobs/'+previous['id'])
            if job['status'] not in ('error', 'failed', 'complete', 'completed', 'done'):
                raise RuntimeError('The retry is already running; no duplicate was started.')
        payload = {'mode': 'captions', 'device': 'cuda', 'caption_style': 'minimal',
                   'caption_content': 'speech', 'preview': True,
                   'source_paths': [str(ROOT/'cache/app/jobs/6cc056821555/media/0000-711239f3-Rog Music.mp4')],
                   'script': 'Haan tujhe dekhta raha\nKissi khwab ki tarah\nJo ab samne hai tu\nHo kaise yakeen bhala'}
        job = request('/api/jobs', payload)
    else:
        previous = json.loads(RECEIPT.read_text(encoding='utf-8'))
        job = request('/api/jobs/'+previous['id'])
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: job.get(key) for key in ('id', 'status', 'progress', 'stage', 'result')}, indent=2))
    print('\n'.join(job.get('logs', [])[-8:]))


if __name__ == '__main__':
    main()
