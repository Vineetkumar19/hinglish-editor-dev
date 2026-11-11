"""Tool registry — spec section 9's "Tool Calling — Core Engineering
Pattern": the LLM never directly executes anything. It requests a
structured tool call; Python validates it, checks permission policy, and
only then runs the real function.

Usage:

    from core.tool_registry import tool
    from core.permissions import RiskLevel

    @tool(
        name="open_folder",
        description="Open an approved local folder by its friendly name.",
        risk=RiskLevel.LOW,
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    def open_folder(name: str) -> dict:
        ...

Registered tools are automatically exposed to Ollama's tool-calling API
(to_ollama_tools()) and to GET /api/tools.
"""

from dataclasses import dataclass, field
import math
import threading
from contextlib import nullcontext
from typing import Any, Callable

from core import db
from core.permissions import FORBIDDEN_TOOL_NAMES, Decision, RiskLevel, check
from core.tasks import check_cancelled, may_prepare_communication


class ForbiddenTool(Exception):
    """Raised at import time if someone registers a capability that must
    never exist in this project (arbitrary command execution, deletion,
    registry edits). See core/permissions.py for the reasoning."""


@dataclass
class Tool:
    name: str
    description: str
    risk: RiskLevel
    parameters: dict
    func: Callable
    result_summary: Callable[[Any], str] = field(default=lambda r: str(r)[:200])
    # Only meaningful for HIGH-risk tools. Called with the same kwargs the
    # model supplied, must return a short human-readable description of what
    # would happen (a diff, usually) — this is what the user sees in the
    # Approve/Reject card before the action actually runs. If omitted, a
    # generic "name(args)" preview is used.
    preview: Callable[..., str] | None = None
    # Internal preparation binds a review to the exact file/window snapshot.
    # Internal arguments are never accepted from the model's public schema.
    prepare: Callable[..., tuple[dict, str]] | None = None


REGISTRY: dict[str, Tool] = {}
_effects_lock = threading.RLock()
_FOCUS_CHANGING_TOOLS = {
    "open_application", "close_application", "close_website", "open_folder", "open_path", "open_website",
    "open_in_ide", "open_github", "focus_window", "scroll_screen", "prepare_message_draft",
    "restore_workspace", "open_calendar", "calendar_availability", "create_calendar_event", "focus_browser_tab",
    "open_communication_app",
}
_COMMUNICATION_TOOLS = {"prepare_message_draft", "compose_email", "send_whatsapp"}


def serialized_effects():
    """Share action serialization with authenticated direct draft endpoints."""
    return _effects_lock


def _check_communication_intent(name: str):
    if name in _COMMUNICATION_TOOLS and not may_prepare_communication():
        raise ToolDenied(name, RiskLevel.CRITICAL)


def tool(*, name: str, description: str, risk: RiskLevel, parameters: dict, preview: Callable[..., str] | None = None,
         prepare: Callable[..., tuple[dict, str]] | None = None):
    def decorator(func: Callable):
        if name.lower() in FORBIDDEN_TOOL_NAMES:
            raise ForbiddenTool(
                f"Refusing to register '{name}': this capability is permanently "
                "barred from Cortana (see agent/core/permissions.py). The agent "
                "must never be able to run arbitrary commands or delete data."
            )
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            risk=risk,
            parameters={**parameters, "additionalProperties": False},
            func=func,
            preview=preview,
            prepare=prepare,
        )
        return func

    return decorator


def to_ollama_tools(names: list[str] | None = None) -> list[dict]:
    """Ollama's /api/chat `tools` field expects OpenAI-style function specs.

    Pass `names` to emit only a subset — see core.tool_router for why we
    don't send all of them on every request.
    """
    tools = REGISTRY.values() if names is None else [REGISTRY[n] for n in names if n in REGISTRY]
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def list_tools() -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "risk": t.risk.value}
        for t in REGISTRY.values()
    ]


class ToolNotFound(Exception):
    pass


class ToolDenied(Exception):
    def __init__(self, tool_name: str, risk: RiskLevel):
        self.tool_name = tool_name
        self.risk = risk
        super().__init__(f"{tool_name} is {risk.value} risk and was denied by policy.")


class ToolNeedsConfirmation(Exception):
    def __init__(self, tool_name: str, risk: RiskLevel, confirmation_id: int, preview: str):
        self.tool_name = tool_name
        self.risk = risk
        self.confirmation_id = confirmation_id
        self.preview = preview
        super().__init__(f"{tool_name} is {risk.value} risk and needs explicit confirmation.")


class ConfirmationNotFound(Exception):
    pass


class ConfirmationExpiredOrResolved(Exception):
    pass


class ToolArgumentsInvalid(ValueError):
    pass


class ConfirmedActionStale(RuntimeError):
    pass


def _execute_recorded(t, args):
    import hashlib
    import json
    import time
    from uuid import uuid4
    from core import local_store, tasks
    request_id = uuid4().hex
    work = tasks.current.get()
    with local_store.connection() as conn:
        conn.execute('INSERT INTO action_ledger(id,task_id,tool,args_hash,state,started) VALUES(?,?,?,?,?,?)',
            (request_id, work.request_id if work else None, t.name,
             hashlib.sha256(json.dumps(args,sort_keys=True,default=str).encode()).hexdigest(), 'running', time.time()))
    try:
        result = t.func(**args)
    except BaseException as exc:
        with local_store.connection() as conn:
            conn.execute('UPDATE action_ledger SET state=?,evidence=?,finished=? WHERE id=?',
                ('unknown', type(exc).__name__, time.time(), request_id))
        raise
    with local_store.connection() as conn:
        evidence = {key:result[key] for key in ('id','status','opened','closed','verified','request_id')
                    if isinstance(result,dict) and key in result}
        evidence['result_type']=type(result).__name__
        conn.execute('UPDATE action_ledger SET state=?,evidence=?,finished=? WHERE id=?',
            ('returned', json.dumps(evidence, default=str), time.time(), request_id))
    return result


def _validate(value, schema: dict, location: str = "arguments"):
    """Validate the supported tool schema subset, without coercion.

    All currently registered schemas use these primitive JSON types. Unknown
    schema types fail closed instead of silently bypassing validation.
    """
    kind = schema.get("type", "object")
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in {int, float} and math.isfinite(value),
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(kind, False)
    if not valid:
        raise ToolArgumentsInvalid(f"{location} must be {kind}.")
    if "enum" in schema and value not in schema["enum"]:
        raise ToolArgumentsInvalid(f"{location} is not an allowed value.")
    if kind == "object":
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - value.keys()
        extra = value.keys() - properties.keys()
        if missing:
            raise ToolArgumentsInvalid(f"{location} is missing: {', '.join(sorted(missing))}.")
        if extra:
            raise ToolArgumentsInvalid(f"{location} has unknown fields: {', '.join(sorted(extra))}.")
        for key, item in value.items():
            _validate(item, properties[key], f"{location}.{key}")
    elif kind == "array":
        if len(value) > schema.get("maxItems", 1000):
            raise ToolArgumentsInvalid(f"{location} has too many items.")
        for index, item in enumerate(value):
            _validate(item, schema.get("items", {}), f"{location}[{index}]")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 100_000):
            raise ToolArgumentsInvalid(f"{location} has an invalid length.")
        if "\0" in value:
            raise ToolArgumentsInvalid(f"{location} contains a null character.")
    elif kind in {"integer", "number"}:
        if value < schema.get("minimum", -1e15) or value > schema.get("maximum", 1e15):
            raise ToolArgumentsInvalid(f"{location} is out of range.")


def dispatch(name: str, args: dict, *, user_requested_launch: bool = False) -> Any:
    """Runs a registered tool after enforcing its permission decision, and
    writes an audit log entry (spec section 11: "Audit log")."""
    check_cancelled()
    t = REGISTRY.get(name)
    if t is None:
        raise ToolNotFound(name)
    _validate(args, t.parameters)
    _check_communication_intent(name)

    decision = check(t.risk)
    # The deterministic parser can authorize an exact user-requested website
    # launch. Model-supplied calls never receive this flag, and it cannot
    # bypass approval for any other capability.
    if name == "open_website" and user_requested_launch and t.risk == RiskLevel.HIGH:
        decision = Decision.ALLOWED

    if decision == Decision.DENIED:
        db.log_audit(name, args, t.risk.value, "denied")
        raise ToolDenied(name, t.risk)

    if decision == Decision.NEEDS_CONFIRMATION:
        # HIGH-risk tools never run inline. A pending row is created with a
        # human-readable preview (a diff, for edit_code_file) and the model
        # is told to wait — the actual run only happens via execute_confirmed()
        # once a human clicks Approve in the UI (POST /api/confirm).
        with _effects_lock:
            check_cancelled()
            if t.prepare:
                prepared_args, preview_text = t.prepare(**args)
            else:
                prepared_args = args
                preview_text = t.preview(**args) if t.preview else f"{name}({args})"
        check_cancelled()
        confirmation_id = db.create_pending_confirmation(name, prepared_args, preview_text)
        db.log_audit(name, args, t.risk.value, "pending_confirmation", preview_text[:200])
        raise ToolNeedsConfirmation(name, t.risk, confirmation_id, preview_text)

    try:
        with _effects_lock if name in _FOCUS_CHANGING_TOOLS else nullcontext():
            check_cancelled()
            result = _execute_recorded(t, args)
        db.log_audit(name, args, t.risk.value, "allowed", t.result_summary(result))
        return result
    except Exception as e:
        db.log_audit(name, args, t.risk.value, "error", str(e)[:200])
        raise


def execute_confirmed(confirmation_id: int) -> Any:
    """Runs the tool call a human has just approved via /api/confirm.

    Bypasses check() deliberately — that check's whole purpose was to
    force this exact human-in-the-loop step, and it has now happened. Still
    goes through the same audit log and the same exception-on-failure
    behavior as a normal dispatch().
    """
    check_cancelled()
    row = db.get_pending_confirmation(confirmation_id)
    if row is None:
        raise ConfirmationNotFound(str(confirmation_id))
    if row["status"] != "pending" or row["expired"]:
        raise ConfirmationExpiredOrResolved(
            f"Confirmation {confirmation_id} is '{row['status']}'"
            + (" (expired)" if row["expired"] else "")
        )
    if not db.claim_pending_confirmation(confirmation_id):
        raise ConfirmationExpiredOrResolved(f"Confirmation {confirmation_id} was already claimed or expired.")

    t = REGISTRY.get(row["tool_name"])
    if t is None:
        db.resolve_pending_confirmation(confirmation_id, "rejected")
        raise ToolNotFound(row["tool_name"])

    try:
        _validate({k: v for k, v in row["args"].items() if not k.startswith("_")}, t.parameters)
        if check(t.risk) == Decision.DENIED:
            raise ToolDenied(t.name, t.risk)
        with _effects_lock:
            check_cancelled()
            _check_communication_intent(t.name)
            result = _execute_recorded(t, row["args"])
        db.resolve_pending_confirmation(confirmation_id, "approved")
        db.log_audit(row["tool_name"], row["args"], t.risk.value, "allowed", f"user-confirmed: {t.result_summary(result)}")
        return result
    except Exception as e:
        db.resolve_pending_confirmation(confirmation_id, "failed")
        db.log_audit(row["tool_name"], row["args"], t.risk.value, "error", f"user-confirmed, then failed: {e}"[:200])
        raise


def reject_confirmed(confirmation_id: int) -> dict:
    row = db.get_pending_confirmation(confirmation_id)
    if row is None:
        raise ConfirmationNotFound(str(confirmation_id))
    if row["status"] != "pending" or row["expired"]:
        raise ConfirmationExpiredOrResolved(f"Confirmation {confirmation_id} is already '{row['status']}'")
    if not db.claim_pending_confirmation(confirmation_id, "rejected"):
        raise ConfirmationExpiredOrResolved(f"Confirmation {confirmation_id} was already claimed or expired.")
    db.log_audit(row["tool_name"], row["args"], "HIGH", "denied", "user rejected")
    return {"rejected": True, "tool_name": row["tool_name"]}
