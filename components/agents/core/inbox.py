"""Durable inbox routing shared by the CLI, scheduler, and push endpoint."""
from __future__ import annotations

import hashlib
import re

from . import config
from .log import get_logger

log = get_logger("inbox")


def process(store, push=None, inbox=None) -> int:
    transport = (config.get("INBOX_TRANSPORT", "") or
                 ("imap" if config.get("MAIL_TRANSPORT", "smtp") == "smtp" else "gmail"))
    if inbox is None:
        if transport == "imap" and not push:
            from .imapbox import ImapBox
            inbox = ImapBox(store)
            if not inbox.configured:
                return 0
        else:
            from .gmail import GmailClient
            inbox = GmailClient(store)
    messages = inbox.handle_push(push) if push else inbox.poll()
    for message in messages:
        payload = {"id": message.id, "thread_id": message.thread_id,
                   "from_addr": message.from_addr.lower(), "from_name": message.from_name,
                   "to_addr": message.to_addr, "subject": message.subject,
                   "rfc_message_id": message.rfc_message_id,
                   "in_reply_to": message.in_reply_to, "references": message.references,
                   "reply_text": message.reply_text, "is_auto_reply": message.is_auto_reply}
        key = hashlib.sha256(f"{transport}:{message.id}".encode()).hexdigest()[:24]
        if not store.seen("inbox_handled", key):
            store.kv_set("inbox_pending", key, payload)
    handled = 0
    for key, payload in store.kv_list("inbox_pending").items():
        try:
            route(store, payload, f"inbox-{key}")
            # Persist acknowledgement before calling a provider that might fail.
            store.mark_seen("inbox_handled", key)
            store.kv_delete("inbox_pending", key)
            inbox.mark_read(payload["id"])
            handled += 1
        except Exception as exc:
            log.error("inbox message deferred", error=str(exc)[:300])
    return handled


def route(store, message: dict, thread_id: str):
    previous = store.one("SELECT status FROM threads WHERE thread_id=?", (thread_id,))
    if previous and previous["status"] in ("complete", "interrupted"):
        return
    lead = store.one("SELECT * FROM leads WHERE LOWER(email)=? ORDER BY created_at DESC LIMIT 1",
                     (message["from_addr"].lower(),))
    from agents.job_hunter.agent import looks_like_interview_request, make_scheduler
    from agents.common import _offline_intent
    terminal = _offline_intent({"text": message["reply_text"]})["label"] in ("unsubscribe", "auto_bounce")
    offer = store.kv_get("interview_offers", message["from_addr"].lower()) if not lead or lead["agent"] == "job_hunter" else None
    if offer and not terminal:
        selected = selected_slot(message["reply_text"], offer)
        if selected is not None:
            from agents.job_hunter.booking import BookingAgent
            start, end = offer["slot_iso"][selected]
            result = BookingAgent(store=store).run(offer["summary"], start, end,
                                                   [message["from_addr"]], thread_id=thread_id)
            if result.error:
                raise RuntimeError(result.error)
            return
    if terminal:
        from agents.common import ReplyAgent, ReplyConfig
        agent = ReplyAgent(ReplyConfig(agent=lead["agent"] if lead else "sponsorship"), store=store)
    elif (not lead or lead["agent"] == "job_hunter") and looks_like_interview_request(message["subject"] + " " + message["reply_text"]):
        agent = make_scheduler(store=store)
    elif not lead:
        store.event("inbox_unmatched", "", thread_id, message_id=message["id"])
        return
    elif lead["agent"] == "fullstack_sales":
        from agents.fullstack_sales.agent import make_reply
        agent = make_reply(store=store)
    elif lead["agent"] == "video_client":
        from agents.video_client.agent import make_reply
        agent = make_reply(store=store)
    elif lead["agent"] == "saas_sales":
        from agents.common import ReplyAgent, ReplyConfig
        agent = ReplyAgent(ReplyConfig(agent="saas_sales",
                                      reply_instruction="Use only the product profile; "
                                      "ask the operator about commercial commitments."), store=store)
    elif lead["agent"] == "job_hunter":
        # An application acknowledgement is not an interview request.
        store.event("job_reply", "job_hunter", thread_id, subject=message["subject"])
        return
    else:
        from agents.sponsorship.agent import make_reply
        agent = make_reply(store=store)
    result = agent.handle(message, thread_id=thread_id)
    if result.error:
        raise RuntimeError(result.error)


def selected_slot(text, offer):
    """Recognise an unambiguous choice from previously offered actual slots."""
    indices = set()
    for i, label in enumerate(offer.get("slots") or []):
        if label.lower() in text.lower():
            indices.add(i)
    for match in re.finditer(r"\b(?:option|slot|time)\s*#?\s*([1-9])\b", text, re.I):
        index = int(match[1]) - 1
        if index < len(offer.get("slot_iso") or []):
            indices.add(index)
    return next(iter(indices)) if len(indices) == 1 else None
