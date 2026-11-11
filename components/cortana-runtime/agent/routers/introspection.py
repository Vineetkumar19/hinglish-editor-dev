"""Real (non-stub) versions of a few core internal APIs (spec section 20)
that Phases 5/6 gave us the backing data for early:

    GET    /api/tools               -> registered tool list
    GET    /api/permissions         -> the policy table itself
    GET    /api/audit               -> recent tool-call audit log entries
    GET    /api/memory              -> recent conversation history for a session
    DELETE /api/memory              -> clear a session's history
"""

from fastapi import APIRouter, Query

from core import db
from core.permissions import RiskLevel, check
from core.tool_registry import list_tools

router = APIRouter(tags=["introspection"])


@router.get("/api/tools")
def get_tools():
    return {"tools": list_tools()}


@router.get("/api/permissions")
def get_permissions():
    return {
        "policy": {level.value: check(level).value for level in RiskLevel},
        "note": "LOW/MEDIUM auto-allow today; HIGH needs a confirmation UX not built yet (fails closed); CRITICAL is always denied.",
    }


@router.get("/api/audit")
def get_audit(limit: int = Query(50, le=500)):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT tool_name, args_json, risk_level, decision, result_summary, created_at "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {
        "entries": [
            {
                "tool_name": r[0],
                "args": r[1],
                "risk_level": r[2],
                "decision": r[3],
                "result_summary": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]
    }


@router.get("/api/memory")
def get_memory(session_id: str = "default", limit: int = Query(50, le=500)):
    return {"session_id": session_id, "messages": db.get_recent_messages(session_id, limit)}


@router.delete("/api/memory")
def delete_memory(session_id: str = "default"):
    db.clear_session(session_id)
    return {"session_id": session_id, "cleared": True}
