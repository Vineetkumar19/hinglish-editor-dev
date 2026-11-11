"""Low volume, reviewed reminders for actual unanswered outreach."""
from __future__ import annotations

import time
from . import config
from .graph import END, StateGraph
from .hitl import require_approval
from .mailer import Mailer, OutgoingMessage, SendBlocked
from .store import get_store, now


class FollowUpAgent:
    def __init__(self, store=None, mailer=None):
        self.store = store or get_store()
        self.mailer = mailer or Mailer(self.store)

    def n_review(self, state):
        lead = state["lead"]
        subject = "Following up on my earlier note"
        body = ("Hi,\n\nJust checking whether my earlier note about "
                + {"video_client": "video editing", "fullstack_sales": "development work",
                   "sponsorship": "a potential partnership"}.get(lead["agent"], "working together")
                + " was relevant. Happy to share more details if it fits your current plans. "
                "If the timing isn't right, no problem.\n\n" + config.get("OPERATOR_NAME", "Vineet"))
        decision = require_approval(agent=lead["agent"], thread_id=state["_thread_id"],
            kind="send_email", title=f"Follow up: {lead.get('company') or lead['email']}",
            payload={"to": lead["email"], "subject": subject, "body": body,
                     "stage": "follow_up", "follow_up_number": state["index"] + 1}, store=self.store)
        if not decision.approved:
            self.store.kv_set("followups", lead["id"], {"stopped": True})
        return {"decision": decision.to_json(), "draft": decision.apply_to({"subject": subject, "body": body})}

    def n_send(self, state):
        lead = self.store.one("SELECT * FROM leads WHERE id=?", (state["lead"]["id"],))
        if not lead or lead["status"] != "contacted":
            return {"outcome": "no_longer_due"}
        latest = self.store.one("SELECT * FROM messages WHERE thread_id=? AND direction='out' ORDER BY ts DESC LIMIT 1",
                                (lead["thread_id"],)) or {}
        draft = state["draft"]
        message = OutgoingMessage(to=lead["email"], subject=draft["subject"], body=draft["body"],
            tag=lead["agent"], in_reply_to=latest.get("rfc_id", ""),
            idempotency_key=state["_thread_id"])
        try:
            result = self.mailer.send(message)
        except SendBlocked as exc:
            return {"outcome": "blocked", "reason": str(exc)}
        self.mailer.record(state["_thread_id"], lead["agent"], "out", message, result)
        if not result.get("dry_run"):
            self.store.kv_set("followups", lead["id"], {"index": state["index"] + 1, "last_sent": now()})
        return {"outcome": "dry_run" if result.get("dry_run") else "sent"}

    def build(self):
        graph = StateGraph()
        graph.add_node("review", self.n_review)
        graph.add_node("send", self.n_send)
        graph.set_entry_point("review")
        graph.add_conditional_edges("review", lambda s: "yes" if s["decision"]["status"] in
                                    ("approved", "edited") else "no", {"yes": "send", "no": END})
        graph.add_edge("send", END)
        return graph.compile(store=self.store, name="follow_up")


def queue_due(store, at=None):
    at = time.time() if at is None else at
    count = 0
    for lead in store.query("SELECT * FROM leads WHERE status='contacted' AND email<>''"):
        if lead["agent"] not in ("sponsorship", "video_client", "fullstack_sales"):
            continue
        progress = store.kv_get("followups", lead["id"]) or {}
        index = int(progress.get("index", 0))
        if progress.get("stopped") or index >= config.get_int("FOLLOWUP_MAX", 2):
            continue
        if at - float(progress.get("last_sent") or lead["updated_at"]) < config.get_int("FOLLOWUP_DAYS", 5) * 86400:
            continue
        if store.one("SELECT id FROM messages WHERE thread_id=? AND direction='in' LIMIT 1", (lead["thread_id"],)):
            continue
        tid = f"followup-{lead['id']}-{index}"
        if store.one("SELECT thread_id FROM threads WHERE thread_id=?", (tid,)):
            continue
        result = FollowUpAgent(store=store).build().invoke(
            {"lead": lead, "index": index, "_thread_id": tid}, thread_id=tid)
        count += int(result.interrupted)
    return count
