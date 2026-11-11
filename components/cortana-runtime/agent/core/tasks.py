"""One owned task at a time, with cooperative cancellation at tool boundaries."""
import asyncio
import contextvars
import threading
import time
from dataclasses import dataclass, field

from fastapi import HTTPException


@dataclass
class Work:
    task: asyncio.Task
    request_id: str = ''
    cancelled: threading.Event = field(default_factory=threading.Event)
    screen_allowed: bool = False
    communication_allowed: bool = False


_active: dict[str, Work] = {}
_finished: dict[str, float] = {}
current: contextvars.ContextVar[Work | None] = contextvars.ContextVar("work", default=None)


def begin(request_id: str, screen_allowed: bool = False, communication_allowed: bool = False):
    now = time.monotonic()
    for key, when in list(_finished.items()):
        if now - when > 600:
            _finished.pop(key, None)
    if request_id in _active or request_id in _finished:
        raise HTTPException(409, "This request was already handled or cancelled.")
    if _active:
        raise HTTPException(409, "Cortana is busy. Stop the current task before starting another.")
    from core import local_store
    try:
        previous = local_store.get('request', request_id)
    except ValueError:
        previous = None
    if previous:
        raise HTTPException(409, 'This request ID was already recorded. Inspect its outcome before retrying.')
    local_store.put('request', {'status':'running', 'started_at':time.time()}, request_id, 0)
    work = Work(
        asyncio.current_task(), request_id=request_id, screen_allowed=screen_allowed,
        communication_allowed=communication_allowed,
    )
    _active[request_id] = work
    return current.set(work)


def finish(request_id: str, token):
    work = _active.pop(request_id, None)
    _finished[request_id] = time.monotonic()
    current.reset(token)
    from core import local_store
    row = local_store.get('request', request_id)
    row.update(status='cancelled' if work and work.cancelled.is_set() else 'finished', finished_at=time.time())
    local_store.put('request', row, request_id, row['revision'])


def cancel(request_id: str) -> dict:
    work = _active.get(request_id)
    _finished[request_id] = time.monotonic()
    if work:
        work.cancelled.set()
        work.task.cancel()
    return {
        "cancelled": bool(work),
        "request_id": request_id,
        "note": "No further steps will start. An already completed action is not undone.",
    }


def check_cancelled():
    work = current.get()
    if work and work.cancelled.is_set():
        raise asyncio.CancelledError()


def cancel_all():
    from core import db
    from core.draft_transactions import revoke_all
    from core.resource_broker import release_when_idle
    release_when_idle()
    cancelled = [cancel(request_id) for request_id in list(_active)]
    return {'requests':cancelled,'revoked_confirmations':db.revoke_pending_confirmations(),
            'revoked_draft_approvals':revoke_all()}


def may_capture_screen() -> bool:
    work = current.get()
    return bool(work and work.screen_allowed and not work.cancelled.is_set())


def may_prepare_communication() -> bool:
    """Only an explicit user communication request permits message drafting."""
    work = current.get()
    return bool(work and work.communication_allowed and not work.cancelled.is_set())
