"""Authenticated receiver hosted in the owning project's Python runtime.

No inference, cron, UI automation or publishing worker starts at import/startup.
The receiver calls existing project executors and persists submission receipts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import subprocess
import threading
import time
from urllib.parse import urlsplit

CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


class Receiver:
    def __init__(self, project, root, storage, token, device='local'):
        self.project, self.root, self.storage, self.token, self.device = project, Path(root), Path(storage), token, device
        self.storage.mkdir(parents=True, exist_ok=True)
        self.db = self.storage / 'receipts.sqlite3'
        self.jobs = {}
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, hash TEXT, request TEXT, receipt TEXT)')
        sys.path.insert(0, str(self.root))
        if project == 'cortana':
            sys.path.insert(0, str(self.root / 'agent'))
        if project == 'cortana':
            from core import local_store
            with local_store.connection():
                pass
        # Recover a result committed before the process lost its HTTP/SQLite
        # acknowledgement. Never replay an uncertain external submission.
        with self.connect() as db:
            rows = db.execute('SELECT id,receipt FROM actions').fetchall()
        for row in rows:
            previous = json.loads(row['receipt'])
            journal = self.storage / (row['id'] + '-result.json')
            if journal.is_file():
                self.save(row['id'], json.loads(journal.read_text(encoding='utf-8')))
            elif previous.get('status') in ('queued', 'running'):
                previous.update(status='interrupted', verified=False, execution_stopped=True,
                    error='Receiver restarted before completion. Partial output is retained; review before a new revision.')
                self.save(row['id'], previous)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def capabilities(self):
        actions = {'storylens': ['storylens.prepare', 'storylens.package', 'storylens.publish'],
            'cortana': ['diagnostics.read', 'delivery.package'], 'repository': ['repository.prepare']}[self.project]
        return {'contract_version': 1, 'device_id': self.device, 'project': self.project,
            'reconciliation': True, 'actions': actions, 'publication_ledger_owner': 'storylens' if self.project == 'storylens' else None,
            'trial_reels_verified_accounts': {}, 'runtime': sys.executable, 'root': str(self.root),
            'receiver_source_hash':CODE_HASH, 'active_jobs':list(self.jobs),
            'limits': ['No automatic desktop input or sending', 'Trial Reels requires separate verified account support']}

    def verify_refs(self, refs):
        for ref in refs:
            if ref['device_id'] != self.device:
                raise ValueError('Transfer cross-device artifacts through the authenticated content store first')
            path = Path(ref['locator']).resolve(strict=True)
            if path.drive.upper() != 'A:' or path.name.lower() in ('.env','credentials.json','token.json') or path.suffix.lower() in ('.token','.pem','.pfx','.key') or any(
                part.lower() in ('.ssh','.aws','.codex','browser-profile','integration-secrets') for part in path.parts):
                raise ValueError('Only selected non-credential A: artifacts are accepted')
            if not path.is_file() or file_hash(path) != ref['content_hash']:
                raise ValueError('Artifact revision changed')
        return refs

    def receipt(self, key):
        with self.connect() as db:
            row = db.execute('SELECT receipt FROM actions WHERE id=?', (key,)).fetchone()
        if not row:
            return {'idempotency_key': key, 'status': 'unknown', 'verified': False}
        result = json.loads(row['receipt'])
        if self.project == 'storylens' and result.get('publisher_job_id') and not result.get('verified'):
            from hinglish_publish.service import Publisher
            publisher = Publisher(self.root)
            job = publisher.store.get(result['publisher_job_id'])
            if job:
                actual = job.get('remote') or {}
                verified = job['status'] in ('published','uploaded_private','scheduled') and bool(actual.get('id') or actual.get('video_id') or actual.get('url'))
                result.update(status=job['status'], verified=verified, remote=actual,
                    remote_id=actual.get('id') or actual.get('video_id') or job['id'],
                    evidence_refs=[str(publisher.store.path)] if verified else [],
                    verified_result='Existing StoryLens worker verified publication' if verified else 'Awaiting existing StoryLens publisher outcome')
                if job['status']=='cancelled':
                    result['execution_stopped']=True
                self.save(key, result)
                if verified or job['status']=='cancelled':
                    self.commit_result(key,result)
        return result

    def save(self, key, receipt):
        with self.connect() as db:
            db.execute('UPDATE actions SET receipt=? WHERE id=?', (canonical(receipt), key))

    def commit_result(self, key, receipt):
        journal = self.storage / (key + '-result.json')
        pending = journal.with_suffix('.tmp')
        pending.write_text(canonical(receipt), encoding='utf-8')
        pending.replace(journal)

    def cancel(self, key):
        if key in self.jobs:
            self.jobs[key].set()
        result = self.receipt(key)
        if self.project == 'storylens' and result.get('publisher_job_id') and not result.get('verified'):
            from hinglish_publish.service import Publisher
            Publisher(self.root).cancel(result['publisher_job_id'])
            result.update(status='cancelled',verified=False,execution_stopped=True)
            self.save(key,result)
            self.commit_result(key,result)
        return result

    def submit(self, request):
        exact, approval, task = request['exact'], request['approval'], request['task']
        key, binding = request['idempotency_key'], digest(exact)
        if not re.fullmatch(r'action_[a-f0-9]{64}', key) or key != 'action_' + binding:
            raise ValueError('Invalid exact action identity')
        if request.get('contract_version') != 1 or approval['exact'] != exact or approval['exact_payload_hash'] != binding:
            raise ValueError('Approval payload does not match')
        if approval['expiry'] <= time.time() or task['device_id'] != self.device:
            raise ValueError('Approval expired or wrong device')
        if exact['action_type'] not in self.capabilities()['actions'] or exact['action_type'] not in task['permissions']:
            raise PermissionError('Capability not granted')
        role_actions = {'system_health': ['diagnostics.read'], 'client_delivery': ['storylens.prepare','delivery.package','repository.prepare'],
                        'content_release': ['storylens.package','storylens.publish']}
        if exact['action_type'] not in role_actions.get(task['role'], []):
            raise PermissionError('Role cannot request this action')
        self.verify_refs(exact['artifact_refs'])
        if exact['target'] != approval['target']:
            raise ValueError('Approval destination changed')
        with self.connect() as db:
            receipt = {'idempotency_key': key, 'exact_payload_hash': binding, 'verified': False,
                       'status': 'queued', 'remote_id': key, 'evidence_refs': []}
            created = db.execute('INSERT INTO actions VALUES (?,?,?,?) ON CONFLICT DO NOTHING',
                (key, binding, canonical(request), canonical(receipt))).rowcount
        if created:
            cancel = threading.Event()
            self.jobs[key] = cancel
            threading.Thread(target=self.execute, args=(request, cancel), daemon=True).start()
        return self.receipt(key)

    def execute(self, request, cancel):
        key, exact = request['idempotency_key'], request['exact']
        receipt = self.receipt(key)
        receipt['status'] = 'running'
        self.save(key, receipt)
        timer = threading.Timer(max(1,min(3600,request['task']['budgets']['runtime_seconds'])),cancel.set)
        timer.daemon=True
        timer.start()
        try:
            if cancel.is_set():
                raise ValueError('Cancelled before execution')
            if self.project == 'storylens':
                result = self.storylens(request, cancel)
            elif self.project == 'cortana':
                result = self.cortana(request, cancel)
            else:
                result = self.repository(request, cancel)
            receipt.update(result)
        except Exception as exc:
            receipt.update(status='cancelled' if cancel.is_set() else 'failed', verified=False,
                execution_stopped=True, error=str(exc)[:500], error_type=type(exc).__name__)
        self.commit_result(key,receipt)
        self.save(key, receipt)
        timer.cancel()
        self.jobs.pop(key, None)

    def artifact(self, path, key, revision):
        path = Path(path).resolve(strict=True)
        return {'artifact_id': key + '-' + path.name, 'project': self.project, 'revision': str(revision),
            'content_hash': file_hash(path), 'device_id': self.device, 'locator': str(path), 'type': path.suffix.lstrip('.'),
            'evidence': [str(path.parent / 'verification.json')], 'approval_status': 'unreviewed', 'contract_version': 1}

    def storylens(self, request, cancel):
        exact, key = request['exact'], request['idempotency_key']
        payload = exact['payload']
        if exact['action_type'] != 'storylens.prepare':
            return self.publication(request, cancel)
        order = payload.get('work_order', {})
        if order.get('operation') != 'source_excerpt':
            raise ValueError('Provide a bounded source_excerpt work order; arbitrary editor mutation is not supported')
        refs = self.verify_refs(exact['artifact_refs'])
        ref = next((r for r in refs if r['artifact_id'] == order.get('source_artifact_id')), None)
        if not ref:
            raise ValueError('Work order source is absent from approved artifacts')
        start, duration = float(order.get('start_seconds', 0)), float(order['duration_seconds'])
        if not 0 <= start <= 36000 or not 0 < duration <= 180:
            raise ValueError('Excerpt must be bounded to at most 180 seconds')
        from hinglish_shorts.source import open_video
        facts = open_video(ref['locator'])
        if start + duration > facts.duration + .05:
            raise ValueError('Excerpt exceeds source duration')
        from hinglish_cinematic.render import run_ffmpeg
        from hinglish_cut.gpu_lock import gpu_lock
        folder = self.root / 'output/suite-delivery' / key
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'delivery-preview.mp4'
        with gpu_lock(self.root):
            run_ffmpeg(['-ss', start, '-i', ref['locator'], '-t', duration, '-map', '0:v:0', '-map', '0:a?',
                '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '23', '-c:a', 'aac', '-b:a', '192k', str(output)], folder, cancel)
        observed = open_video(output)
        if output.stat().st_size > request['task']['budgets']['storage_bytes']:
            raise ValueError('Rendered media exceeds the approved storage budget; partial file retained for review')
        run_ffmpeg(['-i', str(output), '-f', 'null', '-'], folder, cancel)
        if abs(observed.duration - duration) > .12 or (observed.width, observed.height) != (facts.width, facts.height):
            raise ValueError('Rendered excerpt duration or dimensions failed acceptance')
        evidence = {'operation': 'source_excerpt', 'source': ref, 'source_start': start, 'requested_seconds': duration,
            'observed_seconds': observed.duration, 'width': observed.width, 'height': observed.height,
            'full_decode_passed': True, 'source_unchanged': file_hash(ref['locator']) == ref['content_hash'],
            'creative_changes': 'None; straight excerpt preserving source aspect and audio', 'executor': 'StoryLens cinematic.run_ffmpeg',
            'approval_scope': 'Technical output ready for owner review, not published or artistically approved'}
        (folder / 'verification.json').write_text(canonical(evidence), encoding='utf-8')
        (folder / 'work-order.json').write_text(canonical(payload), encoding='utf-8')
        artifacts = [self.artifact(output, key, exact['revision']), self.artifact(folder / 'verification.json', key, exact['revision'])]
        return {'status': 'succeeded', 'verified': True, 'evidence_refs': [str(folder / 'verification.json')], 'artifacts': artifacts,
            'verified_result': 'Actual StoryLens excerpt rendered and fully decoded; ready for owner review'}

    def cortana(self, request, cancel):
        exact, key = request['exact'], request['idempotency_key']
        if exact['action_type'] == 'diagnostics.read':
            from core.diagnostics import sample_system
            report = sample_system(30)
            path = self.storage / (key + '-diagnostics.json')
            path.write_text(canonical(report), encoding='utf-8')
            return {'status': 'succeeded', 'verified': True, 'evidence_refs': [str(path)], 'diagnostics': report}
        refs = self.verify_refs(exact['artifact_refs'])
        payload = exact['payload']
        if not refs or not payload.get('recipient') or payload['recipient'] != exact['target']:
            raise ValueError('Exact recipient and delivery artifacts are required')
        from core.workspaces import capture_workspace, find_workspace
        from tools.files import within_approved_roots
        from core.app_config import approved_search_roots
        folder = self.root / 'documents/suite-deliveries' / key
        if not within_approved_roots(str(folder), approved_search_roots()):
            raise ValueError('Delivery folder is outside Cortana approved file roots')
        folder.mkdir(parents=True, exist_ok=True)
        copied = []
        for index, ref in enumerate(refs):
            if cancel.is_set():
                raise ValueError('Cancelled before the next file operation')
            source = Path(ref['locator'])
            target = folder / (str(index + 1) + '-' + source.name)
            if not target.exists():
                shutil.copy2(source, target)
            if file_hash(target) != ref['content_hash']:
                raise ValueError('Delivery copy differs from reviewed bytes')
            copied.append(str(target))
        from email.message import EmailMessage
        mail = EmailMessage()
        mail['To'], mail['Subject'], mail['X-Unsent'] = payload['recipient'], payload.get('subject','Delivery for review'), '1'
        mail.set_content(payload.get('body', ''))
        if sum(Path(p).stat().st_size for p in copied) > 50_000_000:
            raise ValueError('Local email draft attachments exceed the 50 MB package limit')
        import mimetypes
        for path in copied:
            kind = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            major, minor = kind.split('/', 1)
            mail.add_attachment(Path(path).read_bytes(), maintype=major, subtype=minor, filename=Path(path).name)
        (folder / 'unsent-delivery.eml').write_bytes(mail.as_bytes())
        manifest = {'recipient': payload['recipient'], 'files': refs, 'copied_files': copied, 'sent': False,
                    'exact_payload_hash': digest(exact), 'scope': 'Local package and unsent draft only'}
        (folder / 'delivery-manifest.json').write_text(canonical(manifest), encoding='utf-8')
        name = 'Suite delivery ' + key[-16:]
        existing = find_workspace(name)
        workspace = existing[0] if existing else capture_workspace(name,
            [{'kind': 'folder', 'target': str(folder), 'title': 'Reviewed delivery package'}], 'Unsent local delivery; owner reviews and sends.')
        (folder / 'verification.json').write_text(canonical({'copies_hash_verified': True, 'workspace': workspace, 'sent': False}), encoding='utf-8')
        return {'status': 'succeeded', 'verified': True, 'evidence_refs': [str(folder / 'verification.json')],
            'artifacts': [self.artifact(folder / 'delivery-manifest.json', key, exact['revision'])],
            'workspace': workspace, 'package_folder': str(folder), 'sent': False,
            'verified_result': 'Cortana saved and verified the local delivery package and unsent draft'}

    def publication(self, request, cancel):
        from datetime import datetime
        from hinglish_publish.service import Publisher
        from hinglish_publish.metadata import validate
        from hinglish_shorts.source import open_video
        payload, key, exact = request['exact']['payload'], request['idempotency_key'], request['exact']
        refs = self.verify_refs(exact['artifact_refs'])
        if len(refs) != 1 or payload.get('artifact', {}).get('content_hash') != refs[0]['content_hash']:
            raise ValueError('One exact approved export is required for each destination')
        if exact['action_type']=='storylens.publish' and (payload.get('preview_only') or refs[0].get('approval_status') != 'approved'):
            raise ValueError('An unapproved preview cannot authorize publication')
        if payload.get('trial') and exact['action_type'] == 'storylens.publish':
            raise ValueError('Trial Reels support has not been verified for this account')
        if exact['action_type'] == 'storylens.publish' and (
                not all(type(payload.get(k)) is bool for k in ('made_for_kids','synthetic_media')) or
                payload.get('visibility') not in ('private','public','unlisted')):
            raise ValueError('Publish approval must bind visibility, audience and synthetic-media disclosure')
        profile = payload.get('profile')
        if profile not in ('cricket','gaming','general'):
            raise ValueError('Select the actual StoryLens profile for this account')
        publisher = Publisher(self.root)  # Constructor does not start its worker.
        accounts = publisher.accounts(profile)
        platform = payload['platform']
        connected_id = accounts.get(platform,{}).get('id')
        if platform not in ('youtube','instagram') or (connected_id and connected_id != payload['account']) or (exact['action_type'] == 'storylens.publish' and connected_id != payload['account']):
            raise ValueError('Selected account does not match the connected StoryLens profile')
        meta = validate({'title':payload['title'], 'description':payload['caption'],
            'instagram_caption':payload['caption'] if platform == 'instagram' else '',
            'tags':re.findall(r'#([A-Za-z0-9_]+)',payload['caption'])})
        from hinglish_publish.description_policy import apply as description_policy
        if description_policy(self.root, profile, dict(meta), platform) != meta:
            raise ValueError('StoryLens description policy would change the approved copy. Review compliant copy before submitting.')
        facts = open_video(refs[0]['locator'])
        due = datetime.fromisoformat(payload['time'].replace('Z','+00:00')).timestamp()
        kind = 'short' if facts.height > facts.width and facts.duration <= 180 else 'long'
        if platform == 'instagram' and kind != 'short':
            raise ValueError('Instagram package must be a portrait video of at most 180 seconds')
        from hinglish_niche.profiles import account_key
        item = {'video':refs[0]['locator'], 'fingerprint':refs[0]['content_hash'], 'kind':kind, 'platform':platform,
            'profile':profile, 'metadata':meta, 'thumbnail':'', 'thumbnail_fingerprint':'',
            'visibility':payload.get('visibility','private'), 'duration':facts.duration, 'width':facts.width,'height':facts.height,
            'account_id':payload['account'],'connection_ref':account_key(platform,profile),
            'destination':{'profile_id':profile,'platform':platform,'account_id':payload['account'],
                'connection_ref':account_key(platform,profile),'verified':connected_id == payload['account']},
            'suite_binding_hash':digest(exact),'suite_action_id':key, 'suite_body_revision':payload['body_revision'],
            'suite_intro_id':payload['intro_id'], 'brain':{'provider':'reviewed_suite_copy','model_calls':0}}
        existing = [j for j in publisher.store.list() if j.get('fingerprint') == refs[0]['content_hash'] and j['platform'] == platform and j.get('profile','general') == profile]
        if existing and existing[0].get('suite_binding_hash') != item['suite_binding_hash']:
            previous = existing[0]
            same_package = all(previous.get(k) == item.get(k) for k in (
                'metadata','visibility','account_id','suite_body_revision','suite_intro_id')) and previous.get('due') == due
            if not (exact['action_type'] == 'storylens.publish' and same_package and previous.get('suite_action_id') and previous['status'] == 'draft'):
                raise ValueError('An existing publication owns this source/destination. Review that exact job rather than duplicate it')
            publisher.store.change(previous['id'], expected_status=('draft',), suite_publish_binding_hash=digest(exact))
        job_id = existing[0]['id'] if existing else publisher.store.add_batch([item])[0]
        job = publisher.store.get(job_id)
        if job['status'] == 'draft':
            publisher.store.change(job_id, expected_status=('draft',), due=due)
        if exact['action_type'] == 'storylens.package':
            return {'status':'succeeded','verified':True,'remote_id':job_id,
                'evidence_refs':[str(publisher.store.path)], 'publication_status':'draft', 'published':False,
                'account_binding_verified':connected_id == payload['account'], 'edit_approved':refs[0].get('approval_status') == 'approved',
                'verified_result':'Draft package saved in the existing StoryLens publication ledger'}
        if job['status'] in ('draft','blocked') and not job.get('remote'):
            if cancel.is_set():
                raise ValueError('Cancelled before publication authorization')
            publisher.authorize({'ids':[job_id], 'authorize':True,'made_for_kids':payload['made_for_kids'], 'synthetic_media':payload['synthetic_media']})
        job = publisher.store.get(job_id)
        actual = job.get('remote') or {}
        verified = job['status'] in ('published','uploaded_private','scheduled') and bool(actual.get('id') or actual.get('video_id') or actual.get('url'))
        return {'status':job['status'],'verified':verified,'remote_id':actual.get('id') or actual.get('video_id') or job_id,
            'evidence_refs':[str(publisher.store.path)] if verified else [], 'publisher_job_id':job_id, 'remote':actual,
            'verified_result':'Existing StoryLens worker verified publication' if verified else 'Awaiting the existing StoryLens publisher; no second scheduler was started'}

    def repository(self, request, cancel):
        payload, exact, key = request['exact']['payload'], request['exact'], request['idempotency_key']
        order = payload.get('work_order',{})
        if order.get('operation') != 'validate_repository' or Path(order.get('repository','')).resolve() != self.root.resolve():
            raise ValueError('Select this registered repository and the validate_repository operation')
        pattern = order.get('test_pattern','test_workflows.py')
        if not re.fullmatch(r'test_[A-Za-z0-9_]+\.py',pattern) or not (self.root/'tests'/pattern).is_file():
            raise ValueError('Select an existing bounded test file')
        folder = self.storage/key
        folder.mkdir(parents=True,exist_ok=True)
        command = [sys.executable,str(self.root/'scripts/run_tests.py'),'--pattern',pattern]
        env = dict(os.environ)
        env.pop('SUITE_RECEIVER_TOKEN',None)
        with (folder/'test-output.txt').open('wb') as log:
            process = subprocess.Popen(command,cwd=self.root,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+min(300,request['task']['budgets']['runtime_seconds'])
            while process.poll() is None:
                if cancel.wait(.2) or time.monotonic()>deadline:
                    process.terminate();process.wait(timeout=10)
                    raise ValueError('Repository validation cancelled or exceeded its budget')
        report={'repository':str(self.root),'test_pattern':pattern,'command':command,'exit_code':process.returncode,
                'test_source_hash':file_hash(self.root/'tests'/pattern),'deployment_performed':False}
        (folder/'verification.json').write_text(canonical(report),encoding='utf-8')
        if process.returncode:
            raise ValueError('Repository checks failed; inspect '+str(folder/'test-output.txt'))
        return {'status':'succeeded','verified':True,'evidence_refs':[str(folder/'verification.json')],
            'artifacts':[self.artifact(folder/'verification.json',key,exact['revision'])],
            'verified_result':'Bounded repository tests passed; no deployment performed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', choices=['cortana','storylens','repository'], required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--storage', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    token = os.environ.get('SUITE_RECEIVER_TOKEN', '')
    if len(token) < 32:
        raise SystemExit('An authenticated receiver token is required')
    receiver = Receiver(args.project, args.root, args.storage, token)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def auth(self):
            if self.headers.get('Origin') or urlsplit('//' + self.headers.get('Host','')).hostname not in ('127.0.0.1','localhost','::1'):
                return False
            return hmac.compare_digest(self.headers.get('Authorization','').encode(), ('Bearer ' + token).encode())
        def reply(self, status, value):
            raw = canonical(value).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            if not self.auth():
                return self.reply(401, {'error':'Authentication required'})
            if self.path == '/capabilities':
                return self.reply(200,receiver.capabilities())
            if self.path.startswith('/tasks/action_'):
                return self.reply(200,receiver.receipt(self.path.split('/')[-1]))
            self.reply(404,{'error':'Unknown receiver route'})
        def do_POST(self):
            if not self.auth():
                return self.reply(401,{'error':'Authentication required'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 2_000_000:
                    raise ValueError('Invalid request length')
                payload = json.loads(self.rfile.read(length))
                if self.path == '/tasks':
                    return self.reply(202, receiver.submit(payload))
                if self.path.startswith('/tasks/') and self.path.endswith('/cancel'):
                    key = self.path.split('/')[-2]
                    return self.reply(200,receiver.cancel(key))
                self.reply(404,{'error':'Unknown receiver route'})
            except (ValueError,KeyError,PermissionError,OSError) as exc:
                self.reply(409,{'error':str(exc)[:300]})
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    connection = {'base_url':f'http://127.0.0.1:{server.server_port}', 'device_id':'local',
                  'project':args.project, 'pid':os.getpid(), 'runtime':sys.executable}
    (receiver.storage / 'connection.json').write_text(canonical(connection),encoding='utf-8')
    print(canonical(connection),flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
