"""A persisted approval gate around one specific calendar booking."""
from __future__ import annotations

import datetime as dt
import hashlib
import time

from core import config
from core.calendar import CalendarClient, Slot
from core.graph import END, StateGraph
from core.hitl import require_approval
from core.store import get_store


class BookingAgent:
    def __init__(self, store=None, calendar=None):
        self.store = store or get_store()
        self.calendar = calendar or CalendarClient(self.store)

    def n_review(self, state):
        start, end = (dt.datetime.fromisoformat(state[k]) for k in ("start", "end"))
        if not start.tzinfo or not end.tzinfo or end <= start:
            raise ValueError("Booking needs timezone-aware start and end, with end after start")
        decision = require_approval(agent="job_hunter", thread_id=state["_thread_id"],
            kind="book_interview", title=state["summary"],
            payload={"body": Slot(start, end).human(config.get("TIMEZONE", "Asia/Kolkata")),
                     "attendees": state["attendees"], "start": state["start"], "end": state["end"],
                     "note": "Approval creates a calendar event and emails invitations to the listed attendees."},
            store=self.store)
        return {"decision": decision.to_json()}

    def n_book(self, state):
        identity = "|".join([state["summary"], state["start"], state["end"], *sorted(state["attendees"])])
        key = hashlib.sha256(identity.encode()).hexdigest()
        previous = self.store.kv_get("calendar_booking", key)
        if previous:
            return {"result": previous}
        if config.dry_run():
            return {"result": {"outcome": "preview"}}
        start, end = (dt.datetime.fromisoformat(state[k]) for k in ("start", "end"))
        busy = self.calendar.freebusy(start, end)
        if any(start < b_end and end > b_start for b_start, b_end in busy):
            return {"result": {"outcome": "conflict", "reason": "Calendar changed; choose a new slot"}}
        # A fixed Google event ID makes retries safe if the response is lost.
        event = self.calendar.create_event(summary=state["summary"], start=start, end=end,
            attendees=state["attendees"], description=state.get("description", ""),
            add_meet=True, event_id=key)
        result = {"outcome": "booked", "event": event}
        self.store.kv_set("calendar_booking", key, result)
        self.store.event("interview_booked", "job_hunter", state["_thread_id"], **result)
        return {"result": result}

    def build(self):
        graph = StateGraph()
        graph.add_node("review", self.n_review)
        graph.add_node("book", self.n_book)
        graph.set_entry_point("review")
        graph.add_conditional_edges("review", lambda s: "yes" if s["decision"]["status"] in
                                    ("approved", "edited") else "no", {"yes": "book", "no": END})
        graph.add_edge("book", END)
        return graph.compile(store=self.store, name="job_hunter_booking")

    def run(self, summary, start, end, attendees, description="", thread_id=None):
        tid = thread_id or f"booking-{time.time_ns()}"
        return self.build().invoke({"_thread_id": tid, "summary": summary, "start": start,
            "end": end, "attendees": attendees, "description": description}, thread_id=tid)


def make(store=None, **kwargs):
    return BookingAgent(store=store, **kwargs)
