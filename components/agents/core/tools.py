"""Hands for the model.

Until now the model has had a brain and no hands. Python decided what to look
up, put it in the prompt, and the model wrote text back - one shot, no way to
say "I do not know enough about this brand, let me go and read their pricing
page". This is the other half: a set of functions the model may call itself,
mid-thought, and get answers back before it writes.

THE SAFETY LINE, which is the most important thing in this file:

    Bound tools are READ-ONLY. Always.

Nothing that sends an email, spends money, writes to his files, or changes
anything outside this process is ever reachable by the model. A model that can
look things up is useful; a model that can act is a model that can send a
half-finished pitch to three hundred people at three in the morning because it
misread its own instructions. Every send in this suite goes through the
approval card and it stays that way.

`Tool.safe` is False by default, and `bind()` refuses anything not explicitly
marked safe. That is deliberate: the failure mode of forgetting the flag should
be a tool that does not work, not a tool that does damage.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core.log import get_logger

log = get_logger("tools")

# A model that loops calling tools forever is a model burning his evening. The
# cap is low on purpose: three or four lookups is a thorough agent, twenty is
# one that has lost the thread.
MAX_CALLS = 6
MAX_RESULT_CHARS = 4000


@dataclass
class Tool:
    """One thing the model can do, and what it costs to let it."""
    name: str
    description: str
    parameters: dict                      # JSON Schema for the arguments
    run: Callable[..., Any]
    # Read-only, no side effects outside this process, safe to call with
    # arguments the model invented. Anything else must not be bound.
    safe: bool = False
    # Rough seconds. Used to warn, not to enforce.
    cost_hint: float = 1.0

    def spec(self) -> dict:
        """The shape Ollama and the OpenAI dialect both expect."""
        return {"type": "function",
                "function": {"name": self.name,
                             "description": self.description,
                             "parameters": self.parameters}}


_REGISTRY: dict[str, Tool] = {}


def register(tool_obj: Tool) -> Tool:
    if tool_obj.name in _REGISTRY:
        log.debug(f"replacing already-registered tool {tool_obj.name!r}")
    _REGISTRY[tool_obj.name] = tool_obj
    return tool_obj


def tool(name: str, description: str, parameters: dict, *, safe: bool = False,
         cost_hint: float = 1.0):
    """Decorator form. `safe=True` is a claim you are making about the function."""
    def deco(fn):
        register(Tool(name=name, description=description, parameters=parameters,
                      run=fn, safe=safe, cost_hint=cost_hint))
        return fn
    return deco


def get(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def all_tools() -> dict[str, Tool]:
    return dict(_REGISTRY)


def bind(names: list[str]) -> list[Tool]:
    """The tools an agent is handing to the model for one call.

    Refuses anything not marked safe. A tool that can act does not become
    bindable by being useful.
    """
    out = []
    for name in names:
        t = _REGISTRY.get(name)
        if t is None:
            log.warn(f"no tool named {name!r}; known: {sorted(_REGISTRY)}")
            continue
        if not t.safe:
            log.error(f"refusing to bind {name!r} - it is not marked read-only. "
                      f"Tools the model can call must not have side effects.")
            continue
        out.append(t)
    return out


@dataclass
class CallLog:
    """What the model actually did with its hands, for the approval card."""
    calls: list = field(default_factory=list)

    def add(self, name: str, args: dict, result: str, seconds: float,
            error: str = "") -> None:
        self.calls.append({"tool": name, "args": args,
                           "result": str(result)[:400],
                           "seconds": round(seconds, 2), "error": error})

    def summary(self) -> str:
        if not self.calls:
            return ""
        parts = []
        for c in self.calls:
            arg = ", ".join(f"{k}={str(v)[:40]}"
                            for k, v in (c["args"] or {}).items())
            parts.append(f"{c['tool']}({arg})" + (" FAILED" if c["error"] else ""))
        return " -> ".join(parts)

    def to_json(self) -> list:
        return list(self.calls)


def execute(tool_name: str, arguments: Any, log_to: CallLog | None = None) -> str:
    """Run one tool call and return a string the model can read.

    Never raises. A tool that blows up returns its error as text, because a
    model that gets an error back can try something else, whereas an exception
    ends the whole draft.
    """
    t = _REGISTRY.get(tool_name)
    if t is None:
        msg = (f"There is no tool called {tool_name!r}. Available: "
               f"{', '.join(sorted(_REGISTRY))}")
        if log_to:
            log_to.add(tool_name, {}, "", 0.0, error="no such tool")
        return msg
    if not t.safe:
        if log_to:
            log_to.add(tool_name, {}, "", 0.0, error="not read-only")
        return f"The tool {tool_name!r} is not available to you."

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:  # noqa: BLE001
            arguments = {"query": arguments}
    if not isinstance(arguments, dict):
        arguments = {}

    started = time.time()
    try:
        result = t.run(**arguments)
    except TypeError as exc:
        # The model got the arguments wrong. Telling it exactly how is more
        # useful than failing.
        took = time.time() - started
        msg = (f"Wrong arguments for {tool_name}: {exc}. It takes: "
               f"{json.dumps(t.parameters.get('properties', {}))}")
        if log_to:
            log_to.add(tool_name, arguments, "", took, error=str(exc)[:200])
        return msg
    except Exception as exc:  # noqa: BLE001
        took = time.time() - started
        if log_to:
            log_to.add(tool_name, arguments, "", took, error=str(exc)[:200])
        return f"{tool_name} failed: {exc}"

    took = time.time() - started
    if not isinstance(result, str):
        try:
            result = json.dumps(result, default=str)
        except Exception:  # noqa: BLE001
            result = str(result)
    result = result[:MAX_RESULT_CHARS]
    if log_to:
        log_to.add(tool_name, arguments, result, took)
    log.debug(f"tool {tool_name} ran in {took:.1f}s", chars=len(result))
    return result or "(the tool returned nothing)"
