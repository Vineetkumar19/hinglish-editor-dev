"""Immutable publication intents and append-only verification observations.

This is a guard/projection around the existing executors, never a second queue.
Only executor receipts and explicit readbacks determine delivery state.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))


class Ledger:
    def __init__(self,root):
        self.path=Path(root)/'cache/publisher/pipeline-ledger.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS intents(
                    review_id TEXT NOT NULL, delivery_id TEXT NOT NULL,
                    session_id TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL,
                    created REAL NOT NULL, PRIMARY KEY(review_id,delivery_id));
                CREATE TABLE IF NOT EXISTS observations(
                    id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, review_id TEXT NOT NULL,
                    created REAL NOT NULL, payload TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def freeze(self,session_id,review_id,deliveries):
        """Commit the whole reviewed intent atomically before any external action."""
        if not deliveries or len({d['id'] for d in deliveries})!=len(deliveries):
            raise ValueError('The publishing plan has missing or repeated delivery records. Prepare it again.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT delivery_id FROM intents WHERE review_id=?',(review_id,)).fetchall()
            if old and {r['delivery_id'] for r in old}!={d['id'] for d in deliveries}:
                raise ValueError('The saved publishing plan changed. Prepare a new review before publishing.')
            for delivery in deliveries:
                payload=canonical(delivery);digest=hashlib.sha256(payload.encode()).hexdigest()
                previous=db.execute('SELECT * FROM intents WHERE review_id=? AND delivery_id=?',
                                    (review_id,delivery['id'])).fetchone()
                if previous and (previous['digest']!=digest or previous['session_id']!=session_id):
                    raise ValueError('The saved file, account, metadata or release time changed. Prepare a new review; the previous upload will not be repeated.')
                if not previous:
                    db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?)',
                        (review_id,delivery['id'],session_id,digest,payload,time.time()))

    def inspect(self,review_id):
        with self.connect() as db:
            return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM intents WHERE review_id=?',(review_id,))]

    def private_intents(self,session_id,campaigns):
        """Latest immutable private-video records, independent of chat trimming."""
        folders={str(Path(p).resolve()) for p in campaigns}
        found={}
        with self.connect() as db:
            for record in db.execute('SELECT payload FROM intents WHERE session_id=? ORDER BY created DESC',(session_id,)):
                entry=json.loads(record['payload'])
                if (entry.get('platform')=='youtube' and entry.get('visibility')=='private'
                    and not entry.get('publish_at') and str(Path(entry['video']).parent.resolve()) in folders):
                    found.setdefault(entry['id'],entry)
        return list(found.values())

    def observe(self,session_id,review_id,report):
        with self.connect() as db:
            db.execute('INSERT INTO observations(session_id,review_id,created,payload) VALUES(?,?,?,?)',
                       (session_id,review_id,time.time(),canonical(report)))


def intent(assistant,review):
    rows=[]
    for row in review.get('rows',[]):
        job=assistant.state.publisher.store.get(row['id'])
        rows.append({'id':'youtube:'+job['id'],'platform':'youtube','video':str(Path(job['video']).resolve()),
            'fingerprint':job['fingerprint'],'account':review['accounts'][job['profile']]['id'],
            'metadata':job['metadata'],'publish_at':row.get('publish_at',''),
            'made_for_kids':review.get('made_for_kids'),'synthetic_media':review.get('synthetic_media'),
            'check_only':bool(review.get('youtube_check_only'))})
        if row.get('private_only'):rows[-1]['visibility']='private'
    for row in review.get('instagram_rows',[]):
        rows.append({'id':'instagram:'+row['id'],'platform':'instagram','video':str(Path(row['video']).resolve()),
            'fingerprint':row['fingerprint'],'account':row['account'],
            'caption':row.get('caption',''),'publish_at':row.get('publish_at','')})
    return rows


def validate_files(deliveries):
    from hinglish_publish.store import fingerprint
    seen={}
    for row in deliveries:
        path=row['video']
        if path not in seen:
            before=Path(path).stat()
            seen[path]=fingerprint(path)
            after=Path(path).stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise ValueError('A reviewed video is still changing. Wait for its export to finish.')
        if seen[path]!=row['fingerprint']:
            raise ValueError('A reviewed video changed. Prepare a new review before uploading it.')
    return seen


def freeze(assistant,session_id,review):
    rows=intent(assistant,review)
    validate_files(rows)
    Ledger(assistant.root).freeze(session_id,review['id'],rows)
    review['intent_version']=1


def outcome(review,audit=None):
    """A completed chat turn is not a completed delivery workflow."""
    audit=audit if audit and audit.get('review_id')==review.get('id') else {}
    observed={r['id']:r for r in audit.get('deliveries',[])}
    deliveries=[]
    for row in review.get('rows',[]):
        key='youtube:'+row['id'];verified=observed.get(key,{})
        # Readbacks are tied to the exact reviewed release, never reused after a date edit.
        if verified.get('publish_at')!=row.get('publish_at',''):verified={}
        if review.get('youtube_check_only'):state='checked'
        elif verified.get('state') in ('published','attention'):state=verified['state']
        elif row.get('private_verified'):state='private'
        elif row.get('publication_verified'):state='published'
        elif row.get('schedule_verified'):state='scheduled'
        elif row.get('url'):state='uploaded'
        else:state='pending'
        deliveries.append({'id':key,'platform':'youtube','state':state})
    for row in review.get('instagram_rows',[]):
        state=row.get('status','draft')
        verified=observed.get('instagram:'+row['id'],{})
        if verified.get('publish_at')==row.get('publish_at','') and verified.get('state')=='attention':state='attention'
        elif state=='published' and row.get('url'):state='published'
        elif state in ('blocked','needs_review','cancelled','attention'):state='attention'
        elif state in ('queued','running','sharing'):state='queued'
        else:state='pending'
        deliveries.append({'id':'instagram:'+row['id'],'platform':'instagram','state':state,
            'previously_published':bool(row.get('previously_published'))})
    counts={s:sum(d['state']==s for d in deliveries) for s in ('published','private','scheduled','uploaded','queued','pending','attention','checked')}
    complete=bool(deliveries) and counts['published']+counts['private']+counts['checked']==len(deliveries)
    state='complete' if complete else 'attention' if counts['attention'] else 'waiting' if counts['queued'] or counts['scheduled'] else 'preparing'
    labels=[]
    for platform,name in (('youtube','YouTube'),('instagram','Instagram')):
        subset=[d for d in deliveries if d['platform']==platform]
        for status,label in (('published','published'),('private','private and verified'),('scheduled','scheduled'),('uploaded','uploaded privately'),('queued','queued'),('pending','unfinished'),('attention','need attention'),('checked','checked only')):
            n=sum(d['state']==status for d in subset)
            if platform=='instagram' and status=='published':
                earlier=sum(d['state']=='published' and d.get('previously_published',False) for d in subset)
                if earlier:
                    if n-earlier:labels.append(f'{n-earlier} Instagram newly posted')
                    labels.append(f'{earlier} Instagram posted earlier')
                    continue
            if n:labels.append(f'{n} {name} {label}')
    return {'state':state,'complete':complete,'counts':counts,'summary':' · '.join(labels),
            'delivery_count':len(deliveries),'published_count':counts['published']}
