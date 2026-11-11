"""Authenticated UI entry points for connect, prepare, select and resume."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from core.desktop_drafts import DesktopDraftUnavailable, draft_request, cancel_drafts as stop_drafts
from core.draft_adapters import DraftProblem, validate_payload

router = APIRouter(tags=["drafts"])
Platform = Literal["whatsapp", "gmail", "instagram"]


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Platform
    recipient: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=6000)
    subject: str = Field(default="", max_length=300)


class RecipientChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(pattern=r"^[a-f0-9]{32}$")


async def request(operation, payload=None):
    try:
        return await run_in_threadpool(draft_request, operation, payload)
    except DraftProblem as error:
        raise HTTPException(400, str(error)) from error
    except DesktopDraftUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, OSError, RuntimeError) as error:
        raise HTTPException(503, str(error)) from error


@router.get("/api/integrations/status")
async def integration_status():
    return await request("status")


@router.post("/api/integrations/{platform}/open")
async def open_integration(platform: Platform):
    return await request("open", {"platform": platform})


@router.post("/api/drafts/prepare")
async def prepare_draft(body: DraftRequest):
    try:
        data = validate_payload(body.model_dump())
    except DraftProblem as error:
        raise HTTPException(400, str(error)) from error
    return await request("prepare", data)


@router.post("/api/drafts/cancel")
async def cancel_drafts():
    await run_in_threadpool(stop_drafts)
    return {"cancelled": True, "note": "Draft preparation stopped. Your apps and Chrome were left open; existing drafts were preserved."}


def draft_key(value):
    import re
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise HTTPException(400, "Invalid draft identifier.")
    return value


@router.post("/api/drafts/{draft_id}/resume")
async def resume_draft(draft_id: str):
    return await request("resume", {"draft_id": draft_key(draft_id)})


@router.post("/api/drafts/{draft_id}/select")
async def select_recipient(draft_id: str, body: RecipientChoice):
    return await request("select", {"draft_id": draft_key(draft_id), "candidate_id": body.candidate_id})
