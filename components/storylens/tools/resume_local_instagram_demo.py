"""Explicitly resume the already prepared second demo upload once, without LLM regeneration."""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'output/validation/local-instagram-demo-20261019'
JOB = '237acf90d4734a21'


def main():
    bridge = json.loads((ROOT / 'cache/app/bridge.json').read_text('utf-8-sig'))
    def call(path, body=None):
        request = urllib.request.Request(bridge['url'] + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json','X-Hinglish-Token':bridge['token']})
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.load(response)
    marker = FOLDER / 'resume-prepared.json'
    if marker.exists():
        print('This prepared upload was already resumed; checking status is safe, resubmission is not needed.')
        return
    connection = call('/api/local-browser')
    if not connection['connected'] or connection['extension_version'] != '0.3.0':
        raise RuntimeError('Activate Storylens Local Publisher 0.3.0 before resuming.')
    job = next(j for j in connection['jobs'] if j['id'] == JOB)
    if job['status'] != 'needs_review' or job.get('submission_started') is not False:
        raise RuntimeError('This task is not a confirmed pre-Share interruption. Check its receipt instead.')
    marker.write_text(json.dumps({'job':JOB,'started':time.time(),'video_and_caption_reused':True,
                                 'new_llm_request':False},indent=2),'utf-8')
    result = call('/api/local-browser/retry', {'id':JOB})
    print(json.dumps({'resumed':result['id'],'new_llm_request':False,'extra_instagram_tabs_requested':0}))


if __name__ == '__main__':
    main()
