"""A small, durable, cyclic state-graph runtime.

This is the orchestration layer the agents are built on. It provides the same
primitives the blueprint asks LangGraph for, with no third-party dependencies:

  * nodes and edges, including conditional edges, so graphs can branch and loop
  * a typed-ish dict state with per-key reducers
  * durable checkpointing after every super-step (SQLite or Postgres)
  * ``interrupt()`` for human-in-the-loop pauses that survive a process restart
  * ``Command(resume=...)`` to wake a suspended graph
  * a ``recursion_limit`` circuit breaker against runaway loops
  * per-node retry with exponential backoff

Usage::

    g = StateGraph(reducers={"log": append})
    g.add_node("research", research_fn)
    g.add_node("write", write_fn)
    g.set_entry_point("research")
    g.add_edge("research", "write")
    g.add_edge("write", END)
    app = g.compile(store=get_store(), name="my_agent")
    result = app.invoke({"topic": "x"}, thread_id="t1")
"""
from __future__ import annotations

import copy
import contextvars
import json
import random
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

from .log import get_logger, set_context
from .store import Store, get_store, new_id, now

log = get_logger("graph")

END = "__end__"
START = "__start__"


# --------------------------------------------------------------------------
# reducers
# --------------------------------------------------------------------------
def overwrite(old: Any, new: Any) -> Any:
    return new


def append(old: Any, new: Any) -> list:
    base = list(old or [])
    if isinstance(new, list):
        base.extend(new)
    elif new is not None:
        base.append(new)
    return base


def merge_dict(old: Any, new: Any) -> dict:
    out = dict(old or {})
    out.update(new or {})
    return out


def add_int(old: Any, new: Any) -> int:
    return (old or 0) + (new or 0)


# --------------------------------------------------------------------------
# control-flow signals
# --------------------------------------------------------------------------
class GraphInterrupt(Exception):
    """Raised by interrupt() to suspend the graph pending human input."""

    def __init__(self, payload: dict):
        super().__init__("graph interrupted for human input")
        self.payload = payload


class GraphRecursionError(RuntimeError):
    """Circuit breaker: too many super-steps without reaching END."""


class NodeFailure(RuntimeError):
    def __init__(self, node: str, original: BaseException):
        super().__init__(f"node {node!r} failed: {original}")
        self.node = node
        self.original = original


@dataclass
class Command:
    """Resume payload handed back into a suspended graph."""
    resume: Any = None
    update: dict = field(default_factory=dict)
    goto: str | None = None


@dataclass
class Send:
    """Fan out to a node with a specific payload (map step)."""
    node: str
    payload: dict


# --------------------------------------------------------------------------
# the interrupt mechanism
# --------------------------------------------------------------------------
class _Resumes:
    """Per-execution stack of resume values supplied by the caller."""

    def __init__(self):
        self.values: list[Any] = []
        self.cursor = 0

    def load(self, values: Iterable[Any]) -> None:
        self.values = list(values or [])
        self.cursor = 0

    def take(self) -> tuple[bool, Any]:
        if self.cursor < len(self.values):
            v = self.values[self.cursor]
            self.cursor += 1
            return True, v
        return False, None


_active_resumes = contextvars.ContextVar("graph_resumes", default=())


def has_resume() -> bool:
    """True when a resume value is queued for the next interrupt() call.

    Lets a node skip side effects (such as creating a duplicate approval row)
    when it is being replayed after a human has already answered.
    """
    stack = _active_resumes.get()
    if not stack:
        return False
    r = stack[-1]
    return r.cursor < len(r.values)


def interrupt(payload: dict) -> Any:
    """Pause the graph and surface ``payload`` to a human.

    On the first pass this raises GraphInterrupt; the runtime checkpoints the
    state and returns control to the caller. When the graph is later resumed
    with ``Command(resume=value)``, this call returns ``value`` instead and the
    node re-runs from the top with the answer in hand.
    """
    stack = _active_resumes.get()
    if stack:
        ok, value = stack[-1].take()
        if ok:
            return value
    raise GraphInterrupt(payload)


# --------------------------------------------------------------------------
# graph definition
# --------------------------------------------------------------------------
NodeFn = Callable[[dict], Any]


@dataclass
class _Node:
    name: str
    fn: NodeFn
    retries: int = 0
    backoff: float = 1.0
    tags: tuple = ()


class StateGraph:
    def __init__(self, reducers: dict[str, Callable[[Any, Any], Any]] | None = None):
        self.nodes: dict[str, _Node] = {}
        self.edges: dict[str, str] = {}
        self.conditional: dict[str, tuple[Callable[[dict], Any], dict[str, str]]] = {}
        self.entry: str | None = None
        self.reducers: dict[str, Callable[[Any, Any], Any]] = dict(reducers or {})

    def add_node(self, name: str, fn: NodeFn, *, retries: int = 0,
                 backoff: float = 1.0, tags: Iterable[str] = ()) -> "StateGraph":
        if name in (END, START):
            raise ValueError(f"{name!r} is reserved")
        if name in self.nodes:
            raise ValueError(f"duplicate node {name!r}")
        self.nodes[name] = _Node(name, fn, retries, backoff, tuple(tags))
        return self

    def add_edge(self, src: str, dst: str) -> "StateGraph":
        if src in self.conditional:
            raise ValueError(f"{src!r} already has a conditional edge")
        self.edges[src] = dst
        return self

    def add_conditional_edges(self, src: str, router: Callable[[dict], Any],
                              mapping: dict[str, str] | None = None) -> "StateGraph":
        if src in self.edges:
            raise ValueError(f"{src!r} already has a static edge")
        self.conditional[src] = (router, dict(mapping or {}))
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self.entry = name
        return self

    def set_reducer(self, key: str, fn: Callable[[Any, Any], Any]) -> "StateGraph":
        self.reducers[key] = fn
        return self

    def validate(self) -> None:
        if not self.entry:
            raise ValueError("graph has no entry point")
        if self.entry not in self.nodes:
            raise ValueError(f"entry point {self.entry!r} is not a node")
        targets = set(self.edges.values())
        for _, mapping in self.conditional.values():
            targets |= set(mapping.values())
        for t in targets:
            if t != END and t not in self.nodes:
                raise ValueError(f"edge points at unknown node {t!r}")
        for n in self.nodes:
            if n not in self.edges and n not in self.conditional:
                raise ValueError(
                    f"node {n!r} is a dead end - add an edge to another node or END")

    def compile(self, store: Store | None = None, name: str = "graph",
                recursion_limit: int = 50) -> "CompiledGraph":
        self.validate()
        return CompiledGraph(self, store or get_store(), name, recursion_limit)


# --------------------------------------------------------------------------
# execution
# --------------------------------------------------------------------------
@dataclass
class RunResult:
    state: dict
    status: str            # "complete" | "interrupted" | "error"
    thread_id: str
    interrupt: dict | None = None
    approval_id: str | None = None
    error: str | None = None
    steps: int = 0

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    @property
    def interrupted(self) -> bool:
        return self.status == "interrupted"

    def __getitem__(self, k):  # convenience: result["field"]
        return self.state[k]

    def get(self, k, default=None):
        return self.state.get(k, default)


class CompiledGraph:
    def __init__(self, spec: StateGraph, store: Store, name: str, recursion_limit: int):
        self.spec = spec
        self.store = store
        self.name = name
        self.recursion_limit = recursion_limit

    # -- state merge ---------------------------------------------------------
    def _merge(self, state: dict, update: dict | None) -> dict:
        if not update:
            return state
        out = dict(state)
        for k, v in update.items():
            reducer = self.spec.reducers.get(k) or overwrite
            out[k] = reducer(out.get(k), v)
        return out

    # -- checkpointing -------------------------------------------------------
    @staticmethod
    def _persistable(state: dict) -> dict:
        """Strip transient keys and verify the rest survives a round trip.

        State is written to the database after every super-step, so anything in
        it must be JSON-serialisable. Keys prefixed with ``__`` are treated as
        scratch for the current process and are never persisted - use them for
        live objects (open sockets, parsed page trees) that a resumed run should
        rebuild rather than restore.
        """
        durable = {k: v for k, v in state.items() if not k.startswith("__")}
        for key, value in durable.items():
            try:
                json.dumps(value)
            except (TypeError, ValueError) as exc:
                raise TypeError(
                    f"graph state key {key!r} holds a {type(value).__name__}, "
                    f"which cannot be checkpointed ({exc}). Either store a plain "
                    f"dict/list instead, or rename the key to '__{key}' to mark "
                    f"it as transient and rebuild it after a resume."
                ) from exc
        return durable

    def _save(self, thread_id: str, state: dict, node: str | None,
              nxt: list[str], status: str, parent: str | None, seq: int) -> str:
        cid = new_id("ck")
        self.store.upsert("checkpoints", ("checkpoint_id",), {
            "checkpoint_id": cid, "thread_id": thread_id, "parent_id": parent,
            "seq": seq, "ts": now(), "node": node,
            "state_json": json.dumps(self._persistable(state)),
            "next_json": json.dumps(nxt), "status": status,
        })
        self.store.upsert("threads", ("thread_id",), {
            "thread_id": thread_id, "agent": self.name, "status": status,
            "created_at": now(), "updated_at": now(),
            "meta_json": json.dumps({"last_checkpoint": cid, "seq": seq}),
        })
        return cid

    def latest_checkpoint(self, thread_id: str) -> dict | None:
        row = self.store.one(
            "SELECT * FROM checkpoints WHERE thread_id=? ORDER BY seq DESC LIMIT 1",
            (thread_id,))
        if row:
            row["state"] = json.loads(row["state_json"])
            row["next"] = json.loads(row["next_json"])
        return row

    def history(self, thread_id: str) -> list[dict]:
        rows = self.store.query(
            "SELECT * FROM checkpoints WHERE thread_id=? ORDER BY seq ASC", (thread_id,))
        for r in rows:
            r["state"] = json.loads(r["state_json"])
        return rows

    def _resume_values(self, thread_id: str) -> list:
        return self.store.kv_get("resume", f"{self.name}:{thread_id}", []) or []

    def _push_resume(self, thread_id: str, value: Any) -> None:
        vals = self._resume_values(thread_id)
        vals.append(value)
        self.store.kv_set("resume", f"{self.name}:{thread_id}", vals)

    def _clear_resume(self, thread_id: str) -> None:
        self.store.kv_delete("resume", f"{self.name}:{thread_id}")

    # -- routing -------------------------------------------------------------
    def _next_node(self, node: str, state: dict) -> str:
        if node in self.spec.edges:
            return self.spec.edges[node]
        router, mapping = self.spec.conditional[node]
        decision = router(state)
        if decision is None:
            raise RuntimeError(f"router for {node!r} returned None")
        if isinstance(decision, str) and mapping:
            if decision not in mapping:
                raise RuntimeError(
                    f"router for {node!r} returned {decision!r}, which is not in "
                    f"{sorted(mapping)}")
            return mapping[decision]
        return decision

    # -- node execution with retry ------------------------------------------
    def _run_node(self, node: _Node, state: dict) -> Any:
        attempt = 0
        while True:
            try:
                return node.fn(state)
            except GraphInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt >= node.retries:
                    raise NodeFailure(node.name, exc) from exc
                delay = node.backoff * (2 ** attempt) * (0.7 + 0.6 * random.random())
                log.warn(f"node {node.name} failed, retrying in {delay:.1f}s",
                         attempt=attempt + 1, error=str(exc)[:200])
                time.sleep(min(delay, 30))
                attempt += 1

    # -- main loop -----------------------------------------------------------
    def invoke(self, input_state: dict | None = None, *, thread_id: str | None = None,
               resume: Any = None, recursion_limit: int | None = None,
               restart: bool = False,
               on_event: Callable[[dict], None] | None = None) -> RunResult:
        """Run the graph, resuming this thread if it has a live checkpoint.

        Pass ``restart=True`` to ignore any existing checkpoint and start the
        thread from the beginning.
        """
        thread_id = thread_id or new_id("th")
        limit = recursion_limit or self.recursion_limit
        set_context(agent=self.name, thread_id=thread_id)

        ck = self.latest_checkpoint(thread_id)
        seq = (ck["seq"] + 1) if ck else 0
        parent = ck["checkpoint_id"] if ck else None

        if ck and ck["status"] == "interrupted":
            state = self._merge(ck["state"], input_state)
            pending = ck["next"]
            current = pending[0] if pending else self.spec.entry
            if resume is not None:
                self._push_resume(thread_id, resume)
        elif (ck and not restart and ck["status"] in ("ok", "error")
              and ck["next"] and ck["next"][0] != END):
            # A previous run stopped part-way - either the process died between
            # super-steps, or a node exhausted its retries. The checkpoint holds
            # the state as it was *before* that node ran, so picking up at
            # ck["next"] re-runs only the failed step, never a completed one.
            state = self._merge(ck["state"], input_state)
            current = ck["next"][0]
            log.info(f"resuming an interrupted run ({ck['status']})", node=current)
        else:
            state = dict(input_state or {})
            current = self.spec.entry

        resumes = _Resumes()
        resumes.load(self._resume_values(thread_id))
        resume_token = _active_resumes.set((*_active_resumes.get(), resumes))

        steps = 0
        try:
            while True:
                if current == END:
                    self._save(thread_id, state, None, [END], "complete", parent, seq)
                    self._clear_resume(thread_id)
                    set_context(node=None)
                    self.store.event("run_complete", self.name, thread_id, steps=steps)
                    return RunResult(state, "complete", thread_id, steps=steps)

                if steps >= limit:
                    self._save(thread_id, state, current, [current], "error", parent, seq)
                    raise GraphRecursionError(
                        f"{self.name}: hit recursion limit of {limit} super-steps "
                        f"without reaching END (stuck at node {current!r}). "
                        f"This is the circuit breaker - inspect the graph's routing.")

                node = self.spec.nodes[current]
                set_context(node=current)
                t0 = time.time()
                if on_event:
                    on_event({"type": "node_start", "node": current, "step": steps})

                try:
                    result = self._run_node(node, state)
                except GraphInterrupt as gi:
                    cid = self._save(thread_id, state, current, [current],
                                     "interrupted", parent, seq)
                    self.store.event("interrupt", self.name, thread_id,
                                     node=current, payload=gi.payload)
                    log.info("interrupted for human input", node=current)
                    if on_event:
                        on_event({"type": "interrupt", "node": current,
                                  "payload": gi.payload})
                    return RunResult(state, "interrupted", thread_id,
                                     interrupt=gi.payload,
                                     approval_id=gi.payload.get("approval_id"),
                                     steps=steps)
                except NodeFailure as nf:
                    self._save(thread_id, state, current, [current], "error", parent, seq)
                    self.store.event("node_error", self.name, thread_id, node=current,
                                     error=str(nf.original)[:500],
                                     trace=traceback.format_exc()[-2000:])
                    log.error(f"node {current} failed permanently", exc_info=nf.original)
                    if on_event:
                        on_event({"type": "error", "node": current, "error": str(nf)})
                    return RunResult(state, "error", thread_id, error=str(nf), steps=steps)

                # The node completed. Any resume values it consumed are now baked
                # into the state we are about to checkpoint, so retire them -
                # otherwise a later resume would replay stale human answers.
                if resumes.values:
                    self._clear_resume(thread_id)
                    resumes.load([])

                goto = None
                if isinstance(result, Command):
                    state = self._merge(state, result.update)
                    goto = result.goto
                elif isinstance(result, dict):
                    state = self._merge(state, result)
                elif result is not None:
                    raise TypeError(
                        f"node {current!r} returned {type(result).__name__}; "
                        f"nodes must return a dict, a Command, or None")

                nxt = goto or self._next_node(current, state)
                seq += 1
                parent = self._save(thread_id, state, current, [nxt], "ok", parent, seq)
                if on_event:
                    on_event({"type": "node_end", "node": current, "next": nxt,
                              "ms": int((time.time() - t0) * 1000)})
                log.debug(f"{current} -> {nxt}", ms=int((time.time() - t0) * 1000))
                current = nxt
                steps += 1
        finally:
            _active_resumes.reset(resume_token)
            set_context(node=None)

    def resume(self, thread_id: str, value: Any, **kw) -> RunResult:
        """Wake a suspended graph with the human's answer."""
        return self.invoke(thread_id=thread_id, resume=value, **kw)

    def stream(self, input_state: dict | None = None, **kw) -> Iterator[dict]:
        """Yield node events as the graph runs (buffered, then replayed)."""
        events: list[dict] = []
        result = self.invoke(input_state, on_event=events.append, **kw)
        yield from events
        yield {"type": "result", "result": result}

    # -- introspection -------------------------------------------------------
    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        lines.append(f'    {START}(["start"]) --> {self.spec.entry}')
        for src, dst in self.spec.edges.items():
            tgt = "__end__([end])" if dst == END else dst
            lines.append(f"    {src} --> {tgt}")
        for src, (_, mapping) in self.spec.conditional.items():
            for label, dst in (mapping or {}).items():
                tgt = "__end__([end])" if dst == END else dst
                lines.append(f"    {src} -.{label}.-> {tgt}")
        return "\n".join(lines)
