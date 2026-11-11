"""One durable queue shared by the dashboard and the unattended worker."""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30), 'IST')


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def next_slot(clock, after):
    hour, minute = map(int, clock.split(':'))
    current = datetime.fromtimestamp(after, IST)
    slot = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot.timestamp() <= after:
        slot += timedelta(days=1)
    return slot.timestamp()


class Store:
    def __init__(self, root):
        self.path = Path(root) / 'cache' / 'publisher' / 'queue.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, identity TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL, due REAL NOT NULL, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, created REAL NOT NULL, job_id TEXT,
                    message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS channel_queue_meta (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    revision INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO channel_queue_meta VALUES(1,0);
                CREATE TABLE IF NOT EXISTS channel_queue_requests (
                    request_id TEXT PRIMARY KEY,
                    batch_id TEXT UNIQUE NOT NULL,
                    intent_sha256 TEXT NOT NULL,
                    proposal_sha256 TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS channel_queue_jobs_insert AFTER INSERT ON jobs
                    BEGIN UPDATE channel_queue_meta SET revision=revision+1 WHERE singleton=1; END;
                CREATE TRIGGER IF NOT EXISTS channel_queue_jobs_update AFTER UPDATE ON jobs
                    BEGIN UPDATE channel_queue_meta SET revision=revision+1 WHERE singleton=1; END;
                CREATE TRIGGER IF NOT EXISTS channel_queue_jobs_delete AFTER DELETE ON jobs
                    BEGIN UPDATE channel_queue_meta SET revision=revision+1 WHERE singleton=1; END;
                CREATE TRIGGER IF NOT EXISTS channel_queue_requests_insert AFTER INSERT ON channel_queue_requests
                    BEGIN UPDATE channel_queue_meta SET revision=revision+1 WHERE singleton=1; END;
                CREATE TRIGGER IF NOT EXISTS channel_queue_requests_update AFTER UPDATE ON channel_queue_requests
                    BEGIN UPDATE channel_queue_meta SET revision=revision+1 WHERE singleton=1; END;
                CREATE TRIGGER IF NOT EXISTS channel_queue_requests_delete AFTER DELETE ON channel_queue_requests
                    BEGIN UPDATE channel_queue_meta SET revision=revision+1 WHERE singleton=1; END;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        return {**json.loads(row['data']), 'id': row['id'], 'status': row['status'], 'due': row['due']}

    def list(self):
        with self.connect() as db:
            return [self.decode(row) for row in db.execute('SELECT * FROM jobs ORDER BY due, rowid')]

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise ValueError('Queue item is unavailable')
            return self.decode(row)

    def add_batch(self, items, clock='19:00', now=None, *, daily_window=False):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            lasts, slots, ids, days = {}, {}, [], {}
            from hinglish_niche.profiles import valid_profile
            for item in items:
                profile = valid_profile(item.get('profile', 'general'))
                identity = item['fingerprint'] + ':' + item['platform']
                if profile != 'general':
                    identity += ':' + profile
                if item.get('test_repeat_scope'):
                    import re
                    from .test_mode import enabled
                    scope = item['test_repeat_scope']
                    if not isinstance(scope, str) or not re.fullmatch('[a-f0-9]{32}', scope) or not enabled(self.path.parents[2], profile):
                        raise ValueError('Repeat uploads require the enabled publishing test mode and a saved preparation identity.')
                    identity += ':publishing-test:' + scope
                # An explicitly requested private full-video copy is a separate
                # delivery from an existing scheduled release of the same file.
                # Scope it to the durable campaign so retries remain idempotent.
                if item.get('private_copy_scope'):
                    if item['platform']!='youtube' or item['kind']!='long' or item.get('visibility')!='private':
                        raise ValueError('A separate private copy must be a private full YouTube video.')
                    identity += ':private-copy:' + item['private_copy_scope']
                existing = db.execute('SELECT id,due FROM jobs WHERE identity=?', (identity,)).fetchone()
                if existing:
                    if daily_window and existing['due']>now:slots.setdefault((profile,item['fingerprint']),existing['due'])
                    ids.append(existing['id'])
                    continue
                if item['kind'] == 'short':
                    if profile not in lasts:
                        last = db.execute("SELECT MAX(due) FROM jobs WHERE json_extract(data,'$.kind')='short' "
                            "AND COALESCE(json_extract(data,'$.profile'),'general')=? "
                            "AND status NOT IN ('cancelled')", (profile,)).fetchone()[0]
                        lasts[profile] = max(now, last or 0)
                    slot_key = (profile, item['fingerprint'])
                    if slot_key not in slots:
                        if daily_window:
                            today=datetime.fromtimestamp(now,IST).date()
                            if profile not in days:
                                last=db.execute("SELECT MAX(due) FROM jobs WHERE json_extract(data,'$.kind')='short' AND COALESCE(json_extract(data,'$.profile'),'general')=? AND status!='cancelled'",(profile,)).fetchone()[0]
                                days[profile]=max(today,datetime.fromtimestamp(last,IST).date()+timedelta(days=1)) if last else today
                            day=days[profile]
                            while True:
                                minute=17*60+int(hashlib.sha256((profile+':'+item['fingerprint']+':'+day.isoformat()).encode()).hexdigest()[:8],16)%241
                                candidate=datetime(day.year,day.month,day.day,minute//60,minute%60,tzinfo=IST).timestamp()
                                if candidate>now:break
                                day+=timedelta(days=1)
                            lasts[profile]=candidate;days[profile]=day+timedelta(days=1)
                        else:lasts[profile] = next_slot(clock, lasts[profile])
                        slots[slot_key] = lasts[profile]
                    due = slots[slot_key]
                else:
                    due = now
                job_id = uuid.uuid4().hex[:16]
                data = {**item, 'created': now, 'remote': {}, 'error': '', 'attempts': 0}
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',
                           (job_id, identity, 'draft', due, json.dumps(data, ensure_ascii=False)))
                ids.append(job_id)
            return ids

    def refresh_draft_copy(self,ids,items,expected):
        """Explicit regenerate, with original copy kept and concurrent edits refused."""
        from .metadata import validate
        candidates={(i.get('profile','general'),i['platform'],i['fingerprint']):i for i in items}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for key in ids:
                if key not in expected:continue
                row=db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone();job=self.decode(row)
                if row['status']!='draft' or job.get('remote') or job['metadata']!=expected[key]:
                    raise ValueError('An existing draft changed or started uploading. Its saved copy was kept; review it before regenerating.')
                item=candidates[(job.get('profile','general'),job['platform'],job['fingerprint'])]
                copy=validate(item['metadata'])
                if copy==job['metadata']:continue
                data=json.loads(row['data']);data.setdefault('metadata_history',[]).append({'at':time.time(),'metadata':data['metadata'],'brain':data.get('brain','')})
                data.update(metadata=copy,brain=item.get('brain',data.get('brain','')))
                db.execute('UPDATE jobs SET data=? WHERE id=?',(json.dumps(data,ensure_ascii=False),key))

    def _proposal_snapshot(self, db, bindings, existing_lineage=None):
        """Read under caller's transaction. Never infer accounts from active UI.

        The service supplies credential-free verified bindings and, for legacy
        short rows, explicit verified historical destination/asset manifests.
        Unknown history blocks planning rather than disappearing from occupancy.
        No legacy row or remote receipt is rewritten to normalize this view.
        """
        from . import channel_queue_plan as qp
        if not isinstance(bindings, list):
            qp._error('destination_unverified', 'Supply the explicit verified account bindings.')
        supplied = existing_lineage if existing_lineage is not None else {}
        if not isinstance(supplied, dict):
            qp._error('queue_history_unverified', 'Supply explicit historical lineage by existing job ID.')
        rows = db.execute('SELECT * FROM jobs ORDER BY due,id').fetchall()
        entries = []
        for row in rows:
            try:
                data = json.loads(row['data'])
                if not isinstance(data, dict) or data.get('kind') not in ('short', 'long'):
                    raise ValueError()
                if data['kind'] != 'short':
                    continue
                if 'asset' in data and 'destination' in data:
                    dest, asset = qp._destination(data['destination']), qp._asset(data['asset'])
                    if (data.get('account_id') != dest['account_id']
                            or data.get('connection_ref') != dest['connection_ref']):
                        raise ValueError()
                else:
                    attested = supplied[row['id']]
                    if attested.get('verified') is not True:
                        raise ValueError()
                    dest, asset = qp._destination(attested['destination']), qp._asset(attested['asset'])
                if (data.get('profile', 'general') != dest['profile_id']
                        or data.get('platform') != dest['platform']
                        or data.get('account_id') not in (None, '', dest['account_id'])
                        or data.get('fingerprint', '').lower() != asset['content_sha256']):
                    raise ValueError()
                instant = datetime.fromtimestamp(row['due'], qp.IST)
                attempts = data.get('attempts', 0)
                if not qp._integer(attempts):
                    raise ValueError()
                # Canonical SQL due/status win over stale display fields in data.
                entry = {**data, 'id': row['id'], 'kind': 'short', 'status': row['status'],
                         'destination': dest, 'asset': asset, 'timezone': 'Asia/Kolkata',
                         'release_at': instant.isoformat(),
                         'release_at_utc': instant.astimezone(timezone.utc).isoformat(),
                         'local_date': instant.date().isoformat(),
                         'submission_started': data.get('submission_started') is True
                             or attempts > 0 or row['status'] == 'uploading'}
                entries.append(entry)
            except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
                qp._error('queue_history_unverified', 'An existing short lacks verified historical account/media lineage. Reconcile it before adding a batch; existing rows are preserved.')
        requests = db.execute('SELECT * FROM channel_queue_requests ORDER BY request_id').fetchall()
        records = []
        for row in requests:
            try:
                saved = json.loads(row['data'])
                record = saved['record']
                receipt = saved['receipt']
                created = [d['entry_id'] for d in record['deliveries'] if d['reason'] == 'created']
                referenced = list(dict.fromkeys(d['entry_id'] for d in record['deliveries']))
                if (record['request_id'] != row['request_id'] or record['batch_id'] != row['batch_id']
                        or record['intent_sha256'] != row['intent_sha256']
                        or not qp._sha(row['proposal_sha256'])
                        or receipt['request_id'] != row['request_id']
                        or receipt['proposal_id'] != record['proposal_id']
                        or receipt['execution_authorized'] is not False or receipt['created_as'] != 'draft'
                        or receipt['created_job_ids'] != created or receipt['referenced_job_ids'] != referenced
                        or record['blocked'] or receipt['counts']['blocked_n'] != 0
                        or receipt['counts']['new_n'] != len(created)
                        or receipt['counts']['delivery_n'] != len(record['deliveries'])):
                    raise ValueError()
                records.append(record)
            except (KeyError, TypeError, ValueError):
                qp._error('request_receipt_incomplete', 'A saved request receipt is inconsistent; reconcile it without creating replacement jobs.')
        result = dict(revision=db.execute('SELECT revision FROM channel_queue_meta WHERE singleton=1').fetchone()[0],
                      bindings=[qp._destination(d) for d in bindings], entries=entries, requests=records,
                      store_rows_sha256=qp._hash([list(r) for r in rows]),
                      store_requests_sha256=qp._hash([list(r) for r in requests]))
        qp._snapshot(result)
        return result

    def proposal_snapshot(self, bindings, *, existing_lineage=None):
        """Consistent planning view; no account, media, provider or model reads."""
        with self.connect() as db:
            db.execute('BEGIN')
            return self._proposal_snapshot(db, bindings, existing_lineage)

    @staticmethod
    def _proposal_media(entry, media, now, proposal_id):
        """Validate upstream attestations; do not open/hash/transcribe the video.

        Metadata is supplied by the existing preparation service. Ordinary
        authorization must still validate publication copy and disclosures.
        """
        from . import channel_queue_plan as qp
        asset_id = entry['asset']['asset_id']
        if not isinstance(media, dict) or not isinstance(media.get(asset_id), dict):
            qp._error('media_identity_changed', 'Supply the verified finished media for every new draft.')
        item = media[asset_id]
        allowed = {'verified', 'asset', 'content_sha256', 'video', 'metadata', 'visibility',
                   'thumbnail', 'thumbnail_fingerprint', 'video_url', 'brain',
                   'duration', 'width', 'height', 'review_file'}
        if set(item) - allowed:
            qp._error('draft_fields_required', 'Queue proposals create unapproved drafts only; do not supply execution states, receipts or authorization fields.')
        dest = entry['destination']
        try:
            if (item.get('verified') is not True or qp._asset(item['asset']) != entry['asset']
                    or not qp._sha(item['content_sha256'])
                    or item['content_sha256'].lower() != entry['asset']['content_sha256']
                    or not qp._text(item['video']) or item['visibility'] not in ('public', 'private', 'unlisted')):
                raise ValueError()
            metadata = item['metadata'][dest['platform']]
            if not isinstance(metadata, dict) or not qp._text(metadata.get('title')):
                raise ValueError()
            qp._hash(item)  # finite JSON only; rejects executable/client objects
        except (KeyError, TypeError, ValueError):
            qp._error('media_identity_changed', 'The prepared media/hash/lineage or platform metadata differs; prepare and review that exact short first.')
        data = {**entry, 'video': item['video'], 'fingerprint': entry['asset']['content_sha256'],
                'profile': dest['profile_id'], 'platform': dest['platform'],
                'account_id': dest['account_id'], 'connection_ref': dest['connection_ref'],
                'metadata': metadata, 'visibility': item['visibility'],
                'thumbnail': item.get('thumbnail', ''), 'thumbnail_fingerprint': item.get('thumbnail_fingerprint', ''),
                'video_url': item.get('video_url', ''), 'brain': item.get('brain', ''),
                'created': now.timestamp(), 'remote': {}, 'attempts': 0, 'error': '',
                'queue_proposal_id': proposal_id, 'execution_authorized': False}
        for optional in ('duration', 'width', 'height', 'review_file'):
            if optional in item:
                data[optional] = item[optional]
        return data

    def apply_proposal(self, proposal, *, bindings, finished_candidates, selection,
                       destinations, policy, now, media, existing_lineage=None):
        """Atomically append DRAFT/unarmed jobs and one durable request receipt.

        Service-owned explicit inputs must match the reviewed pure proposal.
        BEGIN IMMEDIATE serializes snapshot/identity/occupancy revalidation and
        the complete append. Legacy writes are captured by revision triggers.
        A committed replay returns its receipt without changing jobs or retrying
        uploads, even after expiry. Uncertain/missed entries are reported for
        review. This method does not arm workers, call providers, inspect files,
        fetch credentials or verify the service's account/media attestations.

        Existing methods remain available. Service authorization still needs its
        own current-binding/media/disclosure checks; it is outside this adapter.
        Unmapped legacy short history blocks rather than guessing a destination.
        """
        from . import channel_queue_plan as qp
        if not isinstance(proposal, dict):
            qp._error('invalid_proposal', 'Supply the complete reviewed proposal.')
        unsigned = {k: v for k, v in proposal.items() if k != 'proposal_sha256'}
        if proposal.get('proposal_sha256') != qp._hash(unsigned):
            qp._error('invalid_proposal', 'The proposal changed after planning; create a fresh proposal.')
        if proposal.get('execution_authorized') is not False:
            qp._error('draft_fields_required', 'A queue proposal cannot authorize publication.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            snapshot = self._proposal_snapshot(db, bindings, existing_lineage)
            request_id = selection.get('request_id') if isinstance(selection, dict) else None
            previous = db.execute('SELECT * FROM channel_queue_requests WHERE request_id=?', (request_id,)).fetchone()
            if previous is None:
                qp.validate_preconditions(proposal, snapshot)
            actual = qp.propose_replenishment(snapshot, finished_candidates, selection,
                                              destinations, policy, now, proposal.get('slot_choices'))
            if previous is not None:
                saved = json.loads(previous['data'])
                if (proposal.get('proposal_id') != actual['proposal_id']
                        or proposal['proposal_sha256'] not in (previous['proposal_sha256'], actual['proposal_sha256'])):
                    qp._error('proposal_mismatch', 'This request does not match its committed proposal; preserve and review its existing receipt.')
                return {'replayed': True, 'receipt': saved['receipt'],
                        'review_actions': [m for m in actual['existing_matches']
                                           if m['action'] not in ('preserve_existing', 'preserve_remote')],
                        'revision': snapshot['revision']}
            if actual['proposal_sha256'] != proposal['proposal_sha256']:
                qp._error('proposal_mismatch', 'The proposed entries differ from the explicit request; nothing was appended.')
            if not actual['commit_ready']:
                qp._error('proposal_requires_review', 'Resolve the duplicate/lineage/submission review before committing this batch; nothing was appended.')
            # Validate the entire batch before INSERT; SQL failures also roll back
            # earlier inserts, request receipts and revision-trigger increments.
            prepared = [(e, self._proposal_media(e, media, now, actual['proposal_id']))
                        for e in actual['new_entries']]
            for entry, data in prepared:
                identity = 'channel-queue-v1:' + qp._hash([
                    entry['destination']['platform'], entry['destination']['account_id'],
                    entry['asset']['content_sha256']])
                db.execute('INSERT INTO jobs(id,identity,status,due,data) VALUES(?,?,?,?,?)',
                           (entry['id'], identity, 'draft', qp._instant(entry['release_at']).timestamp(),
                            json.dumps(data, ensure_ascii=False, allow_nan=False)))
            record = actual['request_record']
            receipt = dict(request_id=request_id, proposal_id=actual['proposal_id'],
                           created_job_ids=[e['id'] for e in actual['new_entries']],
                           referenced_job_ids=list(dict.fromkeys(d['entry_id'] for d in record['deliveries'])),
                           counts=actual['counts'], created_as='draft', execution_authorized=False)
            db.execute('INSERT INTO channel_queue_requests(request_id,batch_id,intent_sha256,proposal_sha256,data) VALUES(?,?,?,?,?)',
                       (request_id, record['batch_id'], record['intent_sha256'], actual['proposal_sha256'],
                        json.dumps({'record': record, 'receipt': receipt}, ensure_ascii=False, allow_nan=False)))
            revision = db.execute('SELECT revision FROM channel_queue_meta WHERE singleton=1').fetchone()[0]
            return {'replayed': False, 'receipt': receipt, 'review_actions': [], 'revision': revision}

    def change(self, job_id, expected_status=None, **changes):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise ValueError('Queue item is unavailable')
            if expected_status is not None and row['status'] not in expected_status:
                raise ValueError('This post changed while you were reviewing it; refresh the queue')
            data = json.loads(row['data'])
            status = changes.pop('status', row['status'])
            due = changes.pop('due', row['due'])
            data.update(changes)
            db.execute('UPDATE jobs SET status=?,due=?,data=? WHERE id=?',
                       (status, due, json.dumps(data, ensure_ascii=False), job_id))

    def claim(self, now, profiles=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            profile_sql = '' if profiles is None else " AND COALESCE(json_extract(data,'$.profile'),'general') IN (" + ','.join('?' for _ in profiles) + ') '
            row = db.execute("SELECT * FROM jobs WHERE status='ready' AND "
                             "(due<=? OR json_extract(data,'$.platform')='youtube') "
                              + profile_sql + "ORDER BY due, rowid LIMIT 1", (now, *(profiles or []))).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='uploading' WHERE id=? AND status='ready'", (row['id'],))
            job = self.decode(row)
            job['status'] = 'uploading'
            return job

    def recover(self):
        # The remote service might have accepted the upload before the computer stopped.
        # Require reconciliation instead of blindly repeating the upload.
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='needs_review' WHERE status='uploading'")

    def event(self, job_id, message):
        with self.connect() as db:
            db.execute('INSERT INTO events(created,job_id,message) VALUES (?,?,?)',
                       (time.time(), job_id, message))

    def events(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100')]
