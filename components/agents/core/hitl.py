"""Human-in-the-loop approval queue.

Bridges graph `interrupt()` calls to a durable queue that the dashboard, the
CLI and (optionally) a chat webhook can act on. Nothing that costs money or
leaves the machine happens without a row here moving to 'approved'.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .graph import has_resume, interrupt
from .log import get_logger
from .store import Store, get_store, new_id, now

log = get_logger("hitl")

PENDING, APPROVED, REJECTED, EDITED, EXPIRED = (
    "pending", "approved", "rejected", "edited", "expired")


@dataclass
class Decision:
    status: str
    edits: dict
    note: str = ""

    @property
    def approved(self) -> bool:
        return self.status in (APPROVED, EDITED)

    def apply_to(self, payload: dict) -> dict:
        out = dict(payload)
        out.update(self.edits or {})
        return out

    def to_json(self) -> dict:
        return {"status": self.status, "edits": self.edits, "note": self.note}

    @classmethod
    def from_json(cls, data: Any) -> "Decision":
        if isinstance(data, bool):
            return cls(APPROVED if data else REJECTED, {})
        if isinstance(data, dict):
            return cls(data.get("status", REJECTED), data.get("edits") or {},
                       data.get("note", ""))
        return cls(REJECTED, {})


class ApprovalQueue:
    def __init__(self, store: Store | None = None):
        self.store = store or get_store()

    def create(self, *, thread_id: str, agent: str, kind: str, title: str,
               payload: dict) -> str:
        aid = new_id("ap")
        self.store.upsert("approvals", ("id",), {
            "id": aid, "thread_id": thread_id, "agent": agent, "kind": kind,
            "title": title[:300],
            "payload_json": json.dumps(payload, default=str),
            "status": PENDING, "decision_json": None,
            "created_at": now(), "decided_at": None,
        })
        self.store.event("approval_created", agent, thread_id, approval_id=aid,
                         kind=kind, title=title)
        log.info(f"approval requested: {title}", approval_id=aid, kind=kind)
        return aid

    def get(self, approval_id: str) -> dict | None:
        row = self.store.one("SELECT * FROM approvals WHERE id=?", (approval_id,))
        if row:
            row["payload"] = json.loads(row["payload_json"])
            row["decision"] = (json.loads(row["decision_json"])
                               if row["decision_json"] else None)
        return row

    def pending(self, agent: str | None = None, limit: int = 100) -> list[dict]:
        if agent:
            rows = self.store.query(
                "SELECT * FROM approvals WHERE status=? AND agent=? "
                "ORDER BY created_at ASC LIMIT ?", (PENDING, agent, limit))
        else:
            rows = self.store.query(
                "SELECT * FROM approvals WHERE status=? ORDER BY created_at ASC "
                "LIMIT ?", (PENDING, limit))
        for r in rows:
            r["payload"] = json.loads(r["payload_json"])
        return rows

    def recent(self, limit: int = 50) -> list[dict]:
        rows = self.store.query(
            "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,))
        for r in rows:
            r["payload"] = json.loads(r["payload_json"])
            r["decision"] = (json.loads(r["decision_json"])
                             if r["decision_json"] else None)
        return rows

    def decide(self, approval_id: str, status: str, edits: dict | None = None,
               note: str = "") -> Decision:
        if status not in (APPROVED, REJECTED, EDITED, EXPIRED):
            raise ValueError(f"bad decision status {status!r}")
        if edits and status == APPROVED:
            status = EDITED
        d = Decision(status, edits or {}, note)
        row = self.get(approval_id)
        if row is None:
            raise KeyError(f"no such approval {approval_id}")
        if row["status"] != PENDING:
            raise RuntimeError(
                f"approval {approval_id} was already {row['status']}")
        with self.store.tx():
            cursor = self.store.execute(
                "UPDATE approvals SET status=?, decision_json=?, decided_at=? "
                "WHERE id=? AND status=?",
                (status, json.dumps(d.to_json()), now(), approval_id, PENDING))
            if cursor.rowcount != 1:
                raise RuntimeError(f"approval {approval_id} was already decided")
        self.store.event("approval_decided", row["agent"], row["thread_id"],
                         approval_id=approval_id, status=status, note=note)
        log.info(f"approval {status}", approval_id=approval_id)
        return d

    def approve(self, approval_id: str, edits: dict | None = None, note: str = ""):
        return self.decide(approval_id, APPROVED, edits, note)

    def reject(self, approval_id: str, note: str = ""):
        return self.decide(approval_id, REJECTED, None, note)


def require_approval(*, agent: str, thread_id: str, kind: str, title: str,
                     payload: dict, store: Store | None = None) -> Decision:
    """Suspend the graph until a human decides.

    First pass: creates a queue row and raises GraphInterrupt.
    After resume: returns the Decision the human made.
    """
    if has_resume():
        # Replay after the human answered - the queue row already exists and has
        # already been decided, so do not create a second one.
        return Decision.from_json(interrupt({}))
    q = ApprovalQueue(store)
    aid = q.create(thread_id=thread_id, agent=agent, kind=kind, title=title,
                   payload=payload)
    raw = interrupt({"approval_id": aid, "kind": kind, "title": title,
                     "payload": payload, "agent": agent})
    return Decision.from_json(raw)
