"""Placeholder routes for the core internal APIs (spec section 20) that
still don't have a phase behind them.

/api/tools, /api/memory, /api/permissions, /api/audit moved to
routers/introspection.py once Phases 5/6 landed. /api/files and
/api/documents as *generic REST browsing* endpoints stay stubbed — the
actual Phase 7/8 functionality is exposed through the search_files /
read_pdf / read_docx / read_xlsx tool-calling path instead, which is
what the LLM actually uses.

    /api/agent/tasks   -> Phase 11 (planning + multi-step agent loop)
    /api/files         -> generic REST file browsing (tools.search_files covers the real use)
    /api/documents     -> generic REST document browsing (tools.read_* covers the real use)
    /api/integrations  -> Phase 14+ (email, calendar, GitHub, IDEs)
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["not-yet-implemented"])

_NOT_READY = {
    "/api/agent/tasks": 11,
    "/api/files": "n/a — use the search_files tool via /api/chat",
    "/api/documents": "n/a — use the read_pdf/read_docx/read_xlsx tools via /api/chat",
    "/api/integrations": 14,
}


def _not_implemented(path: str):
    phase = _NOT_READY[path]
    raise HTTPException(
        status_code=501,
        detail=f"{path}: {phase}",
    )


@router.get("/api/agent/tasks")
def agent_tasks():
    _not_implemented("/api/agent/tasks")


@router.get("/api/files")
def files():
    _not_implemented("/api/files")


@router.get("/api/documents")
def documents():
    _not_implemented("/api/documents")


@router.get("/api/integrations")
def integrations():
    _not_implemented("/api/integrations")
