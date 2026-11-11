"""remember_fact / recall_facts / forget_fact — long-term memory (Phase 12).

These are the *explicit* half of memory: the user says "remember that X"
and it gets stored durably. The implicit half — automatically pulling
relevant stored facts into each conversation — happens in routers/chat.py
via core.recall, without the model needing to ask for it.

Facts live in SQLite alongside conversation history, so they survive
restarts, which conversation context alone does not.
"""

from core import db
from core.recall import retrieve_relevant
from core.tool_registry import tool
from core.permissions import RiskLevel

VALID_CATEGORIES = {"personal", "work", "preference", "contact", "project", "general"}
# First step of domain-scoped memory (architecture doc §04) — 'developer' is
# the first non-general domain, for facts about how you like your code
# written or how a project is structured. Recall still searches every
# domain by default; a caller can narrow with domain= when that matters.
VALID_DOMAINS = {"general", "developer"}


def remember_fact(content: str, category: str = "general", domain: str = "general") -> dict:
    content = (content or "").strip()
    if not content:
        return {"stored": False, "error": "Nothing to remember — the fact was empty."}
    if len(content) > 500:
        content = content[:500]

    cat = (category or "general").strip().lower()
    if cat not in VALID_CATEGORIES:
        cat = "general"

    dom = (domain or "general").strip().lower()
    if dom not in VALID_DOMAINS:
        dom = "general"

    fact_id = db.add_fact(content, cat, dom)
    return {"stored": True, "id": fact_id, "content": content, "category": cat, "domain": dom}


def recall_facts(query: str = "", limit: int = 10, domain: str = "") -> dict:
    dom = (domain or "").strip().lower() or None
    facts = db.all_facts(limit=300, domain=dom)
    if not facts:
        note = f"Nothing has been remembered yet in the '{dom}' domain." if dom else "Nothing has been remembered yet."
        return {"count": 0, "facts": [], "note": note}

    if query.strip():
        matched = retrieve_relevant(query, facts, top_k=limit)
        if not matched:
            return {"count": 0, "facts": [], "note": f"Nothing remembered about '{query}'."}
        db.mark_facts_used([f["id"] for f in matched])
    else:
        matched = facts[:limit]

    return {
        "count": len(matched),
        "facts": [
            {"id": f["id"], "content": f["content"], "category": f["category"], "domain": f.get("domain", "general")}
            for f in matched
        ],
    }


def forget_fact(fact_id: int) -> dict:
    ok = db.delete_fact(int(fact_id))
    return {"forgotten": ok, "id": fact_id} if ok else {"forgotten": False, "error": "No fact with that id."}


tool(
    name="remember_fact",
    description=(
        "Store something durably so you still know it in future conversations, "
        "even after a restart. Use whenever the user says to remember something, "
        "or shares a lasting personal detail (their preferences, key dates, "
        "people, ongoing projects). Store one clear self-contained fact per call."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The fact, written so it makes sense on its own later."},
            "category": {
                "type": "string",
                "description": "One of: personal, work, preference, contact, project, general.",
            },
            "domain": {
                "type": "string",
                "description": "'developer' for coding/project facts (conventions, stack, how you like fixes done), otherwise 'general'.",
            },
        },
        "required": ["content"],
    },
)(remember_fact)

tool(
    name="recall_facts",
    description=(
        "Search everything you've been asked to remember. Use when the user asks "
        "what you know/remember about something, or when you need a stored detail "
        "to answer. Leave query empty to list recent memories."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for. Empty lists the most recent."},
            "limit": {"type": "integer", "description": "Max facts to return (default 10)."},
            "domain": {"type": "string", "description": "Optional: 'developer' or 'general' to narrow the search."},
        },
        "required": [],
    },
)(recall_facts)

tool(
    name="forget_fact",
    description="Delete one stored memory by its id. Use recall_facts first to find the id.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"fact_id": {"type": "integer", "description": "Id of the fact to delete."}},
        "required": ["fact_id"],
    },
)(forget_fact)
