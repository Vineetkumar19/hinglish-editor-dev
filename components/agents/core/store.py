"""Durable storage. SQLite by default (stdlib); PostgreSQL when psycopg is
installed and DB_URL points at it.

Everything the agents need to survive a restart lives here: graph checkpoints,
pending human approvals, the dedupe ledger, leads, message history and a
general key/value space for cursors and tokens.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import pathlib
import re
import sqlite3
import threading
import time
import uuid
from typing import Any, Iterable, Sequence

from . import config
from .log import get_logger

log = get_logger("store")

# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS threads (
        thread_id   TEXT PRIMARY KEY,
        agent       TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'running',
        created_at  DOUBLE PRECISION NOT NULL,
        updated_at  DOUBLE PRECISION NOT NULL,
        meta_json   TEXT NOT NULL DEFAULT '{}'
    )""",
    """CREATE TABLE IF NOT EXISTS checkpoints (
        checkpoint_id TEXT PRIMARY KEY,
        thread_id     TEXT NOT NULL,
        parent_id     TEXT,
        seq           INTEGER NOT NULL,
        ts            DOUBLE PRECISION NOT NULL,
        node          TEXT,
        state_json    TEXT NOT NULL,
        next_json     TEXT NOT NULL DEFAULT '[]',
        status        TEXT NOT NULL DEFAULT 'ok'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ckpt_thread ON checkpoints(thread_id, seq)",
    """CREATE TABLE IF NOT EXISTS checkpoint_writes (
        id            TEXT PRIMARY KEY,
        thread_id     TEXT NOT NULL,
        checkpoint_id TEXT NOT NULL,
        idx           INTEGER NOT NULL,
        node          TEXT NOT NULL,
        value_json    TEXT NOT NULL,
        ts            DOUBLE PRECISION NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_writes_ckpt ON checkpoint_writes(thread_id, checkpoint_id)",
    """CREATE TABLE IF NOT EXISTS approvals (
        id            TEXT PRIMARY KEY,
        thread_id     TEXT NOT NULL,
        agent         TEXT NOT NULL,
        kind          TEXT NOT NULL,
        title         TEXT NOT NULL DEFAULT '',
        payload_json  TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'pending',
        decision_json TEXT,
        created_at    DOUBLE PRECISION NOT NULL,
        decided_at    DOUBLE PRECISION
    )""",
    "CREATE INDEX IF NOT EXISTS idx_appr_status ON approvals(status, created_at)",
    """CREATE TABLE IF NOT EXISTS dedupe (
        namespace  TEXT NOT NULL,
        key_hash   TEXT NOT NULL,
        first_seen DOUBLE PRECISION NOT NULL,
        meta_json  TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (namespace, key_hash)
    )""",
    """CREATE TABLE IF NOT EXISTS leads (
        id          TEXT PRIMARY KEY,
        agent       TEXT NOT NULL,
        company     TEXT NOT NULL DEFAULT '',
        domain      TEXT NOT NULL DEFAULT '',
        person      TEXT NOT NULL DEFAULT '',
        role        TEXT NOT NULL DEFAULT '',
        email       TEXT NOT NULL DEFAULT '',
        phone       TEXT NOT NULL DEFAULT '',
        source_url  TEXT NOT NULL DEFAULT '',
        score       DOUBLE PRECISION NOT NULL DEFAULT 0,
        status      TEXT NOT NULL DEFAULT 'new',
        thread_id   TEXT,
        data_json   TEXT NOT NULL DEFAULT '{}',
        created_at  DOUBLE PRECISION NOT NULL,
        updated_at  DOUBLE PRECISION NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_leads_agent ON leads(agent, status)",
    """CREATE TABLE IF NOT EXISTS messages (
        id           TEXT PRIMARY KEY,
        thread_id    TEXT NOT NULL,
        agent        TEXT NOT NULL DEFAULT '',
        direction    TEXT NOT NULL,
        provider_id  TEXT NOT NULL DEFAULT '',
        rfc_id       TEXT NOT NULL DEFAULT '',
        in_reply_to  TEXT NOT NULL DEFAULT '',
        addr_from    TEXT NOT NULL DEFAULT '',
        addr_to      TEXT NOT NULL DEFAULT '',
        subject      TEXT NOT NULL DEFAULT '',
        body         TEXT NOT NULL DEFAULT '',
        intent       TEXT NOT NULL DEFAULT '',
        ts           DOUBLE PRECISION NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_msg_thread ON messages(thread_id, ts)",
    """CREATE TABLE IF NOT EXISTS kv (
        namespace  TEXT NOT NULL,
        k          TEXT NOT NULL,
        value_json TEXT NOT NULL,
        updated_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (namespace, k)
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id         TEXT PRIMARY KEY,
        ts         DOUBLE PRECISION NOT NULL,
        agent      TEXT NOT NULL DEFAULT '',
        thread_id  TEXT NOT NULL DEFAULT '',
        kind       TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)",
    # -- prospecting -------------------------------------------------------
    # Candidates the sponsorship agent found on the internet, before they become
    # targets. Kept separately from `leads` so a bad sweep can be thrown away
    # without touching anything you have already approached.
    """CREATE TABLE IF NOT EXISTS prospects (
        id           TEXT PRIMARY KEY,
        name         TEXT NOT NULL DEFAULT '',
        domain       TEXT NOT NULL DEFAULT '',
        url          TEXT NOT NULL DEFAULT '',
        source       TEXT NOT NULL DEFAULT '',
        source_url   TEXT NOT NULL DEFAULT '',
        segment      TEXT NOT NULL DEFAULT '',
        deal_type    TEXT NOT NULL DEFAULT '',
        india_score  DOUBLE PRECISION NOT NULL DEFAULT 0,
        score        DOUBLE PRECISION NOT NULL DEFAULT 0,
        status       TEXT NOT NULL DEFAULT 'new',
        why_json     TEXT NOT NULL DEFAULT '[]',
        data_json    TEXT NOT NULL DEFAULT '{}',
        created_at   DOUBLE PRECISION NOT NULL,
        updated_at   DOUBLE PRECISION NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status, score)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_prospects_domain ON prospects(domain)",

    # Every decision you make, kept as a labelled example. This is the whole
    # basis of the agent getting better: a feature that keeps appearing on
    # things you approve gets weighted up, one that appears on things you
    # reject gets weighted down.
    """CREATE TABLE IF NOT EXISTS prospect_feedback (
        id           TEXT PRIMARY KEY,
        domain       TEXT NOT NULL DEFAULT '',
        feature      TEXT NOT NULL,
        outcome      TEXT NOT NULL,
        weight       DOUBLE PRECISION NOT NULL DEFAULT 1,
        note         TEXT NOT NULL DEFAULT '',
        created_at   DOUBLE PRECISION NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_feedback_feature ON prospect_feedback(feature)",

    # What the agents have learned to do differently. One row is one rule, in
    # plain English, derived from something he rejected or edited. These are
    # read back into the prompt before every draft, which is what makes the
    # agents change their behaviour rather than just their ranking.
    """CREATE TABLE IF NOT EXISTS lessons (
        id           TEXT PRIMARY KEY,
        agent        TEXT NOT NULL,
        scope        TEXT NOT NULL DEFAULT '',
        rule         TEXT NOT NULL,
        evidence     TEXT NOT NULL DEFAULT '',
        weight       DOUBLE PRECISION NOT NULL DEFAULT 1,
        uses         INTEGER NOT NULL DEFAULT 0,
        created_at   DOUBLE PRECISION NOT NULL,
        last_used_at DOUBLE PRECISION NOT NULL DEFAULT 0,
        retired_at   DOUBLE PRECISION NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_lessons_agent ON lessons(agent, retired_at)",

    """CREATE TABLE IF NOT EXISTS send_log (
        id         TEXT PRIMARY KEY,
        ts         DOUBLE PRECISION NOT NULL,
        mailbox    TEXT NOT NULL,
        addr_to    TEXT NOT NULL,
        agent      TEXT NOT NULL DEFAULT '',
        thread_id  TEXT NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS idx_send_mailbox ON send_log(mailbox, ts)",
]


def now() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    return (prefix + "_" if prefix else "") + uuid.uuid4().hex[:20]


def hash_key(*parts: Any) -> str:
    raw = "\x1f".join(str(p).strip().lower() for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Store:
    """Small portable SQL wrapper.

    SQL is written with '?' placeholders; for Postgres they are rewritten to
    '%s' and a couple of type keywords are adjusted.
    """

    def __init__(self, url: str | None = None):
        self.url = url or config.get("DB_URL") or f"sqlite:///{config.data_dir()/'agentsuite.db'}"
        self.is_pg = self.url.startswith(("postgres://", "postgresql://"))
        self._local = threading.local()
        self._lock = threading.RLock()
        if self.is_pg:
            try:
                import psycopg  # noqa: F401
                self._driver = "psycopg"
            except ImportError:
                try:
                    import psycopg2  # noqa: F401
                    self._driver = "psycopg2"
                except ImportError as exc:
                    raise RuntimeError(
                        "DB_URL points at PostgreSQL but neither psycopg nor "
                        "psycopg2 is installed. Either `pip install psycopg[binary]` "
                        "or set DB_URL=sqlite:///data/agentsuite.db"
                    ) from exc
        else:
            self._driver = "sqlite3"
        self.migrate()

    # -- connection handling -------------------------------------------------
    def _connect(self):
        if self.is_pg:
            if self._driver == "psycopg":
                import psycopg
                return psycopg.connect(self.url, autocommit=False)
            import psycopg2
            return psycopg2.connect(self.url)
        path = self.url[len("sqlite:///"):] if self.url.startswith("sqlite:///") else self.url
        # Create the containing folder if it is missing. A fresh checkout has no
        # data/ directory (it is gitignored), and sqlite3 will not create one --
        # it fails with the opaque "unable to open database file" instead.
        parent = pathlib.Path(path).expanduser().parent
        if str(parent) not in ("", "."):
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise sqlite3.OperationalError(
                    f"cannot create the folder for the database file: {parent} ({exc})"
                ) from exc
        try:
            conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
        except sqlite3.OperationalError as exc:
            raise sqlite3.OperationalError(
                f"{exc}: could not open the database at {path!r}. Check that the "
                f"folder exists and is writable (cloud-synced folders such as "
                f"OneDrive can lock files); or set DB_URL to another location."
            ) from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @property
    def conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = self._connect()
            self._local.conn = c
        return c

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            with contextlib.suppress(Exception):
                c.close()
            self._local.conn = None

    def _adapt(self, sql: str) -> str:
        if not self.is_pg:
            return sql
        sql = sql.replace("?", "%s")
        sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
        return sql

    @contextlib.contextmanager
    def tx(self):
        """Transaction scope. Nested use re-enters the same transaction."""
        depth = getattr(self._local, "depth", 0)
        self._local.depth = depth + 1
        try:
            yield self.conn
            if self._local.depth == 1:
                self.conn.commit()
        except Exception:
            if self._local.depth == 1:
                with contextlib.suppress(Exception):
                    self.conn.rollback()
            raise
        finally:
            self._local.depth -= 1

    def execute(self, sql: str, params: Sequence = ()):
        cur = self.conn.cursor()
        cur.execute(self._adapt(sql), tuple(params))
        return cur

    def run(self, sql: str, params: Sequence = ()) -> None:
        with self.tx():
            self.execute(sql, params)

    def _rows(self, cur) -> list[dict]:
        if cur.description is None:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def query(self, sql: str, params: Sequence = ()) -> list[dict]:
        return self._rows(self.execute(sql, params))

    def one(self, sql: str, params: Sequence = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def migrate(self) -> None:
        with self._lock, self.tx():
            for stmt in SCHEMA:
                s = stmt
                if self.is_pg:
                    s = s.replace("DOUBLE PRECISION", "DOUBLE PRECISION")
                self.execute(s)

    # -- upsert helper -------------------------------------------------------
    def upsert(self, table: str, key_cols: Sequence[str], values: dict) -> None:
        cols = list(values.keys())
        placeholders = ", ".join("?" for _ in cols)
        if self.is_pg:
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in key_cols)
            conflict = ", ".join(key_cols)
            sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
                   f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
                   if updates else
                   f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
                   f"ON CONFLICT ({conflict}) DO NOTHING")
        else:
            sql = (f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) "
                   f"VALUES ({placeholders})")
        with self.tx():
            self.execute(sql, [values[c] for c in cols])

    # ---------------------------------------------------------------- kv ----
    def kv_get(self, namespace: str, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value_json FROM kv WHERE namespace=? AND k=?",
                       (namespace, key))
        return json.loads(row["value_json"]) if row else default

    def kv_set(self, namespace: str, key: str, value: Any) -> None:
        self.upsert("kv", ("namespace", "k"), {
            "namespace": namespace, "k": key,
            "value_json": json.dumps(value, default=str), "updated_at": now(),
        })

    def kv_delete(self, namespace: str, key: str) -> None:
        self.run("DELETE FROM kv WHERE namespace=? AND k=?", (namespace, key))

    def kv_list(self, namespace: str) -> dict:
        rows = self.query("SELECT k, value_json FROM kv WHERE namespace=?", (namespace,))
        return {r["k"]: json.loads(r["value_json"]) for r in rows}

    # ------------------------------------------------------------ dedupe ----
    def seen(self, namespace: str, *parts: Any) -> bool:
        h = hash_key(*parts)
        return self.one("SELECT 1 AS x FROM dedupe WHERE namespace=? AND key_hash=?",
                        (namespace, h)) is not None

    def mark_seen(self, namespace: str, *parts: Any, meta: dict | None = None) -> bool:
        """Record the key. Returns True if this is the first time we've seen it."""
        h = hash_key(*parts)
        if self.one("SELECT 1 AS x FROM dedupe WHERE namespace=? AND key_hash=?",
                    (namespace, h)):
            return False
        self.upsert("dedupe", ("namespace", "key_hash"), {
            "namespace": namespace, "key_hash": h, "first_seen": now(),
            "meta_json": json.dumps(meta or {}, default=str),
        })
        return True

    # ------------------------------------------------------------ events ----
    def event(self, kind: str, agent: str = "", thread_id: str = "", /,
              **payload) -> None:
        """Append an audit event. Positional-only params so that payload
        keys such as ``kind`` or ``agent`` cannot collide with them."""
        self.upsert("events", ("id",), {
            "id": new_id("ev"), "ts": now(), "agent": agent,
            "thread_id": thread_id, "kind": kind,
            "payload_json": json.dumps(payload, default=str),
        })

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self.query("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))
        for r in rows:
            r["payload"] = json.loads(r["payload_json"])
        return rows


_default: Store | None = None


def get_store() -> Store:
    global _default
    if _default is None:
        _default = Store()
    return _default


def reset_store() -> None:
    """Test helper: drop the cached singleton."""
    global _default
    if _default is not None:
        _default.close()
    _default = None
