"""Agent registry - maps a graph name to something that can rebuild and resume it.

The dashboard and the CLI both need to wake a suspended graph given only the
name stored on its checkpoint, so the mapping lives in one place.
"""
from __future__ import annotations

from typing import Callable

from .log import get_logger
from .store import Store, get_store

log = get_logger("registry")

_BUILDERS: dict[str, Callable] = {}


def register(name: str, builder: Callable) -> None:
    _BUILDERS[name] = builder


def names() -> list[str]:
    _load_all()
    return sorted(_BUILDERS)


_loaded = False


def _load_all() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    from agents.fullstack_sales import agent as fs
    from agents.community import agent as cm
    from agents.job_hunter import agent as jh
    from agents.job_hunter import application as ja
    from agents.job_hunter import booking as jb
    from agents.saas_sales import agent as ss
    from agents.sponsorship import agent as sp
    from agents.video_client import agent as vc
    from .followups import FollowUpAgent

    register("sponsorship", lambda store: sp.make(store=store).build())
    register("community", lambda store: cm.make(store=store).build())
    register("follow_up", lambda store: FollowUpAgent(store=store).build())
    register("sponsorship_reply", lambda store: sp.make_reply(store=store).build())
    register("video_client", lambda store: vc.make(store=store).build())
    register("video_client_reply", lambda store: vc.make_reply(store=store).build())
    register("fullstack_sales", lambda store: fs.make(store=store).build())
    register("fullstack_sales_reply",
             lambda store: fs.make_reply(store=store).build())
    register("fullstack_sales_quote",
             lambda store: fs.make_quote(store=store).build())
    register("saas_sales", lambda store: ss.make(store=store).build())
    register("job_hunter", lambda store: jh.make(store=store).build())
    register("job_hunter_application", lambda store: ja.make(store=store).build())
    register("job_hunter_booking", lambda store: jb.make(store=store).build())
    register("job_hunter_interview",
             lambda store: jh.make_scheduler(store=store).build())


def get_graph(name: str, store: Store | None = None):
    _load_all()
    builder = _BUILDERS.get(name)
    if builder is None:
        raise KeyError(f"unknown agent {name!r}; registered: {sorted(_BUILDERS)}")
    return builder(store or get_store())


def resume_thread(thread_id: str, value, store: Store | None = None):
    """Wake whichever graph owns this thread with the operator's decision."""
    st = store or get_store()
    if thread_id.startswith('task_'):
        from .workflow_service import ReviewResumer
        from .workflow_store import WorkflowStore
        if WorkflowStore(st).get(thread_id):
            return ReviewResumer(st).resume(thread_id, value)
    row = st.one("SELECT agent FROM threads WHERE thread_id=?", (thread_id,))
    if row is None:
        raise KeyError(f"no thread {thread_id!r}")
    graph = get_graph(row["agent"], st)
    log.info("resuming thread", thread_id=thread_id, agent=row["agent"])
    return graph.resume(thread_id, value)
