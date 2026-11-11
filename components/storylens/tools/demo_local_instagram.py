"""Run the creator-authorized two-account live demo through the local assistant.

Never retries a submitted upload. The second request is allowed only after the
first assistant task has a verified publication receipt.
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'output/validation/local-instagram-demo-20261019'
SELECTIONS = [
    ('vineet_editz19', FOLDER / 'instagram-1.mp4'),
    ('fantasy_legends91', FOLDER / 'instagram-3.mp4'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'status', 'resume'])
    parser.add_argument('number', type=int, choices=[1, 2])
    parser.add_argument('--wait', type=int, default=0)
    args = parser.parse_args()
    bridge = json.loads((ROOT / 'cache/app/bridge.json').read_text('utf-8-sig'))
    FOLDER.mkdir(parents=True, exist_ok=True)

    def call(path, body=None):
        request = urllib.request.Request(bridge['url'] + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'X-Hinglish-Token': bridge['token']})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    record_path = FOLDER / f'upload-{args.number}.json'
    if args.action == 'resume':
        record = json.loads(record_path.read_text('utf-8'))
        session = call('/api/assistant/session?id=' + record['session'])
        jobs = call('/api/local-browser')['jobs']
        related = [j for j in jobs if j.get('session') == record['session']]
        def before_share(job):
            return job['status'] == 'cancelled' or (job['status'] == 'needs_review' and not job.get('url') and
                job.get('message') in ('Instagram has not confirmed the original audio track. Review the reel before posting.',
                                       'Sign in to @fantasy_legends91 in Chrome first.'))
        if session['status'] not in ('failed', 'stopped', 'needs_review') or any(not before_share(j) for j in related):
            raise RuntimeError('Resume is allowed only after a pre-upload failure with no submitted Chrome job.')
        message = record['request']
        if related:
            # This is an operator-requested revision after a proven pre-Share audio failure.
            # A revised caption creates a distinct request; ambiguous submissions remain blocked.
            if args.number == 1:
                message += (' Revise the caption to begin with Explore Mumbai Indians, and focus on the '
                            'franchise journey and Rohit Sharma in two concise sentences, followed by '
                            'relevant cricket hashtags.')
            else:
                message += (' Revise the caption to begin with Mumbai Indians playoff journey, and focus '
                            'on the Eliminator victory and the subsequent exit in two concise sentences '
                            'followed by relevant team and cricket hashtags.')
        record.setdefault('followups', []).append({'message': message, 'requested': time.time(),
                                                  'prior_status': session['status'], 'prior_stage': session.get('stage')})
        record_path.write_text(json.dumps(record, indent=2), 'utf-8')
        call('/api/assistant/message', {'session': record['session'], 'message': message,
             'attachments': [session['attachments'][0]['id']], 'profile': 'general'})
        print(json.dumps({'number': args.number, 'session': record['session'], 'status': 'requested after pre-upload failure'}))
        return
    if args.action == 'start':
        if record_path.exists():
            raise RuntimeError('This demo upload was already requested. Check status; do not repeat it.')
        for _ in range(40):
            connection = call('/api/local-browser')
            if connection['connected'] and connection['extension_version'] == '0.3.0':
                break
            time.sleep(1)
        else:
            raise RuntimeError('Storylens Local Publisher 0.3.0 must be connected.')
        if any(job['status'] in ('queued', 'running', 'sharing') for job in connection['jobs']):
            raise RuntimeError('Another Chrome task is active. Finish it first.')
        if args.number == 2:
            first = json.loads((FOLDER / 'upload-1.json').read_text('utf-8'))
            jobs = connection['jobs']
            if not any(j.get('session') == first['session'] and j['status'] == 'published' for j in jobs):
                raise RuntimeError('The first publication must be verified before switching accounts.')
        account, video = SELECTIONS[args.number - 1]
        if not video.is_file():
            raise FileNotFoundError(video)
        session = call('/api/assistant/session', {})
        attachment = call('/api/assistant/attach', {'session': session['id'], 'path': str(video)})
        message = (f'Upload this attached finished video as an Instagram Reel to @{account} now. '
                   'Use the actual spoken content to write a proper English caption with 3-5 relevant '
                   'hashtags. Preserve the portrait framing and original audio. Publish this one Reel.')
        if args.number == 2:
            message += (' Content notes verified against the excerpt: Mumbai Indians win the Eliminator '
                        'against Kolkata Knight Riders, then their campaign ends against Royal Challengers '
                        'Bangalore in Qualifier 2. Focus on that victory and subsequent exit. Use hashtags '
                        'about the teams and IPL rather than the destination account.')
        record = {'session': session['id'], 'account': account, 'source': str(video), 'request': message,
                  'requested': time.time(), 'publication_authorized': True}
        # Persist before dispatch: an ambiguous request is reviewed rather than submitted twice.
        record_path.write_text(json.dumps(record, indent=2), 'utf-8')
        response = call('/api/assistant/message', {'session': session['id'], 'message': message,
                        'attachments': [attachment['id']], 'profile': 'general'})
        print(json.dumps({'number': args.number, 'session': session['id'], 'account': account,
                          'source': str(video), 'status': response.get('status', 'requested')}))
        return

    record = json.loads(record_path.read_text('utf-8'))
    end = time.monotonic() + min(50, max(0, args.wait))
    while True:
        session = call('/api/assistant/session?id=' + record['session'])
        if session['status'] not in ('planning', 'running', 'transcribing') or time.monotonic() >= end:
            break
        time.sleep(2)
    connection = call('/api/local-browser')
    job = next((j for j in connection['jobs'] if j['id'] == session.get('browser_job_id')), None)
    if job is None:
        job = next((j for j in reversed(connection['jobs']) if j.get('session') == record['session']), None)
    result = {**record, 'checked': time.time(), 'status': session['status'], 'stage': session.get('stage'),
              'brain': session.get('brain'), 'messages': session['messages'], 'steps': session.get('steps'),
              'extension_version': connection['extension_version'], 'job': job}
    (FOLDER / f'upload-{args.number}-receipt.json').write_text(json.dumps(result, indent=2), 'utf-8')
    print(json.dumps({'number': args.number, 'status': session['status'], 'stage': session.get('stage'),
                      'brain': session.get('brain'), 'job': job}, ensure_ascii=False))


if __name__ == '__main__':
    main()
