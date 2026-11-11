"""SQLite storage for conversation history (Phase 5) and the tool audit
log (basic version now, full audit dashboard is Phase 13).

One file, two tables. Kept intentionally simple — spec section 4/16 calls
for SQLite initially, Postgres/MySQL only "if needed" later.
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from core.config import settings

DB_PATH = Path(settings.memory_dir) / "cortana.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user' | 'assistant'
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    decision TEXT NOT NULL,       -- 'allowed' | 'denied' | 'error'
    result_summary TEXT,
    created_at REAL NOT NULL
);

-- Long-term memory: facts that outlive a single conversation and survive
-- restarts. Separate from `messages` on purpose — messages are a raw
-- transcript that gets trimmed for context, whereas these are durable
-- things worth recalling later ("my sister's birthday is 3 March").
CREATE TABLE IF NOT EXISTS memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at REAL NOT NULL,
    last_used_at REAL,
    use_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_facts_category ON memory_facts(category);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    due_at REAL NOT NULL,
    created_at REAL NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at, done);

-- HIGH-risk tool calls (e.g. edit_code_file) don't run immediately — they
-- park here with a human-readable preview (a diff, usually) until the user
-- explicitly approves or rejects via POST /api/confirm. This is what makes
-- RiskLevel.HIGH usable at all instead of permanently failing closed; see
-- core/tool_registry.py's dispatch()/execute_confirmed()/reject_confirmed().
CREATE TABLE IF NOT EXISTS pending_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    preview TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | expired
    created_at REAL NOT NULL,
    resolved_at REAL
);
"""


_schema_ready = False


def init_db():
    global _schema_ready
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
    _schema_ready = True


def _migrate(conn):
    """Additive, idempotent column migrations for tables that predate a
    later column. SQLite has no "ADD COLUMN IF NOT EXISTS", so check first."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memory_facts)").fetchall()}
    if "domain" not in cols:
        # Domain-scoped memory (architecture doc §04): every existing fact
        # becomes 'general' so nothing already remembered is lost or hidden.
        conn.execute("ALTER TABLE memory_facts ADD COLUMN domain TEXT NOT NULL DEFAULT 'general'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_domain ON memory_facts(domain)")
    confirmation_cols = {row[1] for row in conn.execute("PRAGMA table_info(pending_confirmations)").fetchall()}
    if "session_key" not in confirmation_cols:
        conn.execute("ALTER TABLE pending_confirmations ADD COLUMN session_key TEXT NOT NULL DEFAULT ''")


def _ensure_schema(conn):
    """Creates the tables if they aren't there yet.

    init_db() runs at agent startup, but a write can still arrive against a
    fresh/rotated/deleted DB file. The schema is all CREATE IF NOT EXISTS,
    so this is cheap and idempotent, and it means a missing table can never
    silently drop history or audit entries.
    """
    global _schema_ready
    if not _schema_ready:
        conn.executescript(SCHEMA)
        _migrate(conn)
        _schema_ready = True


@contextmanager
def get_conn():
    # timeout: OneDrive/AV can briefly hold the file; wait rather than
    # immediately raising "database is locked" mid-conversation.
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_message(session_id: str, role: str, content: str):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        _ensure_schema(conn)
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
        )


def get_recent_messages(session_id: str, limit: int) -> list[dict]:
    with get_conn() as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def clear_session(session_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))


# ---------------------------------------------------------------- memory
#
# `domain` is the first, lightweight step of the domain-scoped memory the
# architecture doc describes (§04): every fact belongs to a domain
# ('general' by default, 'developer' for coding-buddy context, etc.).
# Recall still searches across all domains for now — full per-domain
# isolation (a Developer-agent turn never seeing Finance facts) is a later
# step once more domains actually exist — but every fact is tagged from
# day one so that isolation can be turned on later without a data migration.

def add_fact(content: str, category: str = "general", domain: str = "general") -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        _ensure_schema(conn)
        # Don't store the same fact twice; refresh it instead.
        existing = conn.execute(
            "SELECT id FROM memory_facts WHERE lower(content) = lower(?)", (content,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE memory_facts SET created_at = ?, domain = ? WHERE id = ?",
                (time.time(), domain, existing[0]),
            )
            return existing[0]
        cur = conn.execute(
            "INSERT INTO memory_facts (content, category, domain, created_at) VALUES (?, ?, ?, ?)",
            (content, category, domain, time.time()),
        )
        return cur.lastrowid


def all_facts(limit: int = 200, domain: str | None = None) -> list[dict]:
    with get_conn() as conn:
        _ensure_schema(conn)
        if domain:
            rows = conn.execute(
                "SELECT id, content, category, created_at, domain FROM memory_facts "
                "WHERE domain = ? ORDER BY created_at DESC LIMIT ?",
                (domain, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, category, created_at, domain FROM memory_facts "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        {"id": r[0], "content": r[1], "category": r[2], "created_at": r[3], "domain": r[4]}
        for r in rows
    ]


def delete_fact(fact_id: int) -> bool:
    with get_conn() as conn:
        _ensure_schema(conn)
        cur = conn.execute("DELETE FROM memory_facts WHERE id = ?", (fact_id,))
        return cur.rowcount > 0


def mark_facts_used(ids: list[int]):
    if not ids:
        return
    try:
        with get_conn() as conn:
            _ensure_schema(conn)
            conn.executemany(
                "UPDATE memory_facts SET last_used_at = ?, use_count = use_count + 1 WHERE id = ?",
                [(time.time(), i) for i in ids],
            )
    except Exception:
        pass  # usage stats are nice-to-have, never worth failing a turn over


# -------------------------------------------------------------- reminders

def add_reminder(text: str, due_at: float) -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "INSERT INTO reminders (text, due_at, created_at) VALUES (?, ?, ?)",
            (text, due_at, time.time()),
        )
        return cur.lastrowid


def list_reminders(include_done: bool = False) -> list[dict]:
    with get_conn() as conn:
        _ensure_schema(conn)
        sql = "SELECT id, text, due_at, done FROM reminders"
        if not include_done:
            sql += " WHERE done = 0"
        sql += " ORDER BY due_at ASC"
        rows = conn.execute(sql).fetchall()
    return [{"id": r[0], "text": r[1], "due_at": r[2], "done": bool(r[3])} for r in rows]


def due_reminders() -> list[dict]:
    """Reminders past their time that haven't been announced yet."""
    now = time.time()
    with get_conn() as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT id, text, due_at FROM reminders WHERE done = 0 AND notified = 0 AND due_at <= ?",
            (now,),
        ).fetchall()
        if rows:
            conn.executemany(
                "UPDATE reminders SET notified = 1 WHERE id = ?", [(r[0],) for r in rows]
            )
    return [{"id": r[0], "text": r[1], "due_at": r[2]} for r in rows]


def complete_reminder(reminder_id: int) -> bool:
    with get_conn() as conn:
        _ensure_schema(conn)
        cur = conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))
        return cur.rowcount > 0


def get_audit(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT tool_name, args_json, risk_level, decision, result_summary, created_at "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "tool_name": r[0], "args": r[1], "risk_level": r[2],
            "decision": r[3], "result_summary": r[4], "created_at": r[5],
        }
        for r in rows
    ]


def log_audit(tool_name: str, args: dict, risk_level: str, decision: str, result_summary: str = ""):
    """Best-effort audit write.

    Deliberately never raises. The audit log is a record of what happened,
    not a precondition for it — if the DB file is missing, locked (this
    project lives in a OneDrive-synced folder, which does lock files
    mid-sync), or on a read-only volume, a tool that already ran
    successfully must not be reported to the user as a failure. Failures
    are surfaced on stderr so they're visible in the agent's console
    rather than swallowed in silence.
    """
    import json
    import hashlib
    import sys

    try:
        # Audit records need action identity, not copied document text, draft
        # bodies, email addresses, access tokens or page excerpts.
        serialized = json.dumps(args, sort_keys=True, default=str, ensure_ascii=False)
        redacted_args = {'fields': sorted(args), 'sha256': hashlib.sha256(serialized.encode()).hexdigest(),
                         'values': 'redacted'}
        safe_summary = ('Detail redacted; SHA256 ' + hashlib.sha256(str(result_summary).encode()).hexdigest()) if result_summary else ''
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with get_conn() as conn:
            _ensure_schema(conn)
            conn.execute(
                "INSERT INTO audit_log (tool_name, args_json, risk_level, decision, result_summary, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tool_name, json.dumps(redacted_args), risk_level, decision, safe_summary, time.time()),
            )
    except Exception as e:  # noqa: BLE001 — auditing must never break execution
        print(f"[audit] could not record {tool_name}: {e}", file=sys.stderr)


# --------------------------------------------------- pending confirmations

CONFIRMATION_TTL_SECONDS = 5 * 60


def _confirmation_session() -> str:
    import hashlib
    import os

    return hashlib.sha256(os.environ.get("CORTANA_API_TOKEN", "").encode()).hexdigest()


def create_pending_confirmation(tool_name: str, args: dict, preview: str) -> int:
    import json

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "INSERT INTO pending_confirmations (tool_name, args_json, preview, created_at, session_key) "
            "VALUES (?, ?, ?, ?, ?)",
            (tool_name, json.dumps(args, default=str), preview, time.time(), _confirmation_session()),
        )
        return cur.lastrowid


def get_pending_confirmation(confirmation_id: int) -> dict | None:
    import json

    with get_conn() as conn:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT id, tool_name, args_json, preview, status, created_at, session_key FROM pending_confirmations "
            "WHERE id = ?",
            (confirmation_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "tool_name": row[1],
        "args": json.loads(row[2]),
        "preview": row[3],
        "status": row[4],
        "created_at": row[5],
        "expired": row[4] == "pending" and (
            (time.time() - row[5]) > CONFIRMATION_TTL_SECONDS or row[6] != _confirmation_session()
        ),
    }


def claim_pending_confirmation(confirmation_id: int, status: str = "executing") -> bool:
    """A single SQL compare-and-set owns approval or rejection.

    A crash after the claim remains 'executing'; it is deliberately never
    replayed automatically because the tool may already have acted.
    """
    if status not in {"executing", "rejected"}:
        raise ValueError("Invalid confirmation claim status.")
    with get_conn() as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "UPDATE pending_confirmations SET status = ?, resolved_at = ? "
            "WHERE id = ? AND status = 'pending' AND created_at >= ? AND session_key = ?",
            (status, time.time(), confirmation_id, time.time() - CONFIRMATION_TTL_SECONDS, _confirmation_session()),
        )
        return cur.rowcount == 1


def resolve_pending_confirmation(confirmation_id: int, status: str):
    if status not in {"approved", "rejected", "failed", "expired"}:
        raise ValueError("Invalid confirmation resolution status.")
    with get_conn() as conn:
        _ensure_schema(conn)
        conn.execute(
            "UPDATE pending_confirmations SET status = ?, resolved_at = ? WHERE id = ? AND status = 'executing'",
            (status, time.time(), confirmation_id),
        )


def revoke_pending_confirmations():
    """Stop invalidates every unconsumed review in this desktop session."""
    with get_conn() as conn:
        _ensure_schema(conn)
        result = conn.execute("UPDATE pending_confirmations SET status='rejected',resolved_at=? "
                              "WHERE status='pending' AND session_key=?", (time.time(),_confirmation_session()))
        return result.rowcount
