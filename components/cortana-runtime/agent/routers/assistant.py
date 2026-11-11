"""Endpoints backing the desktop app's memory / reminders / audit panels.

These are read-and-manage views over the same SQLite tables the tools
write to, so what the UI shows is always exactly what Cortana knows —
there is no second copy of state to drift out of sync.
"""

import asyncio
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from core import db
from core.tool_registry import (
    ConfirmationExpiredOrResolved,
    ConfirmationNotFound,
    ConfirmedActionStale,
    ToolArgumentsInvalid,
    execute_confirmed,
    list_tools,
    reject_confirmed,
)

router = APIRouter(tags=["assistant"])


class FactIn(BaseModel):
    content: str
    category: str = "general"
    domain: str = "general"


class ReminderIn(BaseModel):
    text: str
    when: str


class ConfirmIn(BaseModel):
    approve: bool
    request_id: str = Field(default_factory=lambda:uuid4().hex, pattern=r'^[A-Za-z0-9_-]{8,80}$')


# ------------------------------------------------------------------ memory

@router.get("/api/memory/facts")
def get_facts(limit: int = 100):
    return {"facts": db.all_facts(limit=limit)}


@router.post("/api/memory/facts")
def create_fact(body: FactIn):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Fact content cannot be empty.")
    return {"id": db.add_fact(content, body.category, body.domain), "content": content}


@router.delete("/api/memory/facts/{fact_id}")
def remove_fact(fact_id: int):
    if not db.delete_fact(fact_id):
        raise HTTPException(status_code=404, detail="No fact with that id.")
    return {"deleted": True, "id": fact_id}


# --------------------------------------------------------------- reminders

@router.get("/api/reminders")
def get_reminders(include_done: bool = False):
    from tools.reminders import list_reminders

    return list_reminders(include_done=include_done)


@router.post("/api/reminders")
def create_reminder(body: ReminderIn):
    from tools.reminders import add_reminder

    result = add_reminder(body.text, body.when)
    if not result.get("created"):
        raise HTTPException(status_code=400, detail=result.get("error", "Could not create reminder."))
    return result


@router.get("/api/reminders/due")
def get_due():
    """Reminders that have come due and not yet been announced.

    Polled by the desktop app. Calling this marks them announced, so each
    reminder is spoken exactly once even across a page reload.
    """
    return {"due": db.due_reminders()}


@router.post("/api/reminders/{reminder_id}/complete")
def finish_reminder(reminder_id: int):
    if not db.complete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="No reminder with that id.")
    return {"completed": True, "id": reminder_id}


# ----------------------------------------------------- pending confirmations

@router.post("/api/confirm/{confirmation_id}")
async def confirm_action(confirmation_id: int, body: ConfirmIn):
    """Approve or reject a HIGH-risk tool call that's parked waiting for a
    human (currently just edit_code_file). See core/tool_registry.py for
    the full mechanism."""
    from core import tasks
    token = tasks.begin(body.request_id)
    try:
        if body.approve:
            result = await run_in_threadpool(execute_confirmed, confirmation_id)
            return {"status": "approved", "result": result}
        else:
            result = await run_in_threadpool(reject_confirmed, confirmation_id)
            return {"status": "rejected", "result": result}
    except ConfirmationNotFound:
        raise HTTPException(status_code=404, detail="No pending confirmation with that id.")
    except ConfirmationExpiredOrResolved as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ConfirmedActionStale as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ToolArgumentsInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.CancelledError:
        raise HTTPException(409, 'Stopped. Review observed state before retrying.')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confirmed action failed: {e}")
    finally:
        tasks.finish(body.request_id, token)


# ------------------------------------------------------------------- audit

@router.get("/api/audit/log")
def audit_log(limit: int = 100):
    return {"entries": db.get_audit(limit=limit)}


@router.get("/api/capabilities")
def capabilities():
    """Everything Cortana can currently do, grouped for the UI's help panel."""
    from core.permissions import FORBIDDEN_TOOL_NAMES

    return {
        "tools": list_tools(),
        "permanently_blocked": sorted(FORBIDDEN_TOOL_NAMES),
    }
