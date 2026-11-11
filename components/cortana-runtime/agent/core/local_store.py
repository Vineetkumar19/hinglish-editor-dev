"""Versioned local records and source chunks; no model executes retrieved prose."""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
 kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
 data TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(kind,id));
CREATE TABLE IF NOT EXISTS chunks (
 id INTEGER PRIMARY KEY, document_id TEXT NOT NULL, page INTEGER NOT NULL,
 span TEXT NOT NULL, text TEXT NOT NULL, confidence REAL, method TEXT NOT NULL,
 embedding TEXT, embedding_version TEXT);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
 INSERT INTO chunks_fts(rowid,text) VALUES(new.id,new.text); END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
 INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',old.id,old.text); END;
CREATE TABLE IF NOT EXISTS action_ledger (
 id TEXT PRIMARY KEY, task_id TEXT, tool TEXT NOT NULL, args_hash TEXT NOT NULL,
 state TEXT NOT NULL, evidence TEXT, started REAL NOT NULL, finished REAL);
"""


@contextmanager
def connection():
    path = Path(settings.memory_dir) / 'local_architecture.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def put(kind, data, record_id=None, expected_revision=None):
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        result = put_in_transaction(conn, kind, data, record_id, expected_revision)
    return result


def put_in_transaction(conn, kind, data, record_id=None, expected_revision=None):
    """Update a record inside an already-open write transaction."""
    record_id = record_id or uuid4().hex
    previous = conn.execute('SELECT revision FROM records WHERE kind=? AND id=?', (kind, record_id)).fetchone()
    revision = previous['revision'] if previous else 0
    if expected_revision is not None and revision != expected_revision:
        raise ValueError('This record changed. Review its current version.')
    result = {**data, 'id': record_id, 'revision': revision + 1}
    conn.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)',
                 (kind, record_id, revision + 1, json.dumps(result, ensure_ascii=False), time.time()))
    return result


def get(kind, record_id):
    with connection() as conn:
        row = conn.execute('SELECT data FROM records WHERE kind=? AND id=?', (kind, record_id)).fetchone()
    if not row:
        raise ValueError(f'No {kind} with that ID.')
    return json.loads(row['data'])


def records(kind, limit=200):
    with connection() as conn:
        rows = conn.execute('SELECT data FROM records WHERE kind=? ORDER BY updated DESC LIMIT ?',
                            (kind, min(1000, max(1, limit)))).fetchall()
    return [json.loads(r['data']) for r in rows]


def remove(kind, record_id):
    with connection() as conn:
        if kind == 'document':
            conn.execute('DELETE FROM chunks WHERE document_id=?', (record_id,))
        conn.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, record_id))


def recover():
    # Unknown external side effects must never be replayed after a restart.
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("UPDATE action_ledger SET state='unknown', finished=? WHERE state='running'", (time.time(),))
        rows = conn.execute("SELECT kind,data FROM records WHERE kind IN ('request','draft','browser_command')").fetchall()
        for row in rows:
            record = json.loads(row['data'])
            kind = row['kind']
            if kind == 'request' and record.get('status') == 'running':
                record['status'] = 'interrupted_requires_review'
            elif kind == 'draft' and record.get('status') in {'APPROVED', 'SENDING'}:
                record['status'] = 'UNCERTAIN' if record['status'] == 'SENDING' else 'READY_FOR_REVIEW'
                record.pop('approval', None)
            elif kind == 'browser_command' and record.get('state') in {'pending','claimed'}:
                record['state'] = 'cancelled' if record['state'] == 'pending' else 'unknown'
            else:
                continue
            put_in_transaction(conn, kind, record, record['id'], record['revision'])
