"""Delivery of reviewed drafts, with explicit manual handoffs and durable receipts."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

from .crawler import extract_emails
from .mailer import Mailer, OutgoingMessage, SendBlocked, valid_email
from .store import now


def contact_email(target: dict) -> str:
    """Only use supplied or published addresses; never infer a person's address."""
    for key in ("contact_email", "email", "contact"):
        value = str(target.get(key) or "").strip().lower()
        if valid_email(value):
            return value
    addresses = extract_emails(str(target.get("description") or ""))
    return next((a for a in addresses if valid_email(a)), "")


def deliver_reviewed(*, store, agent: str, thread_id: str, target: dict,
                     draft: dict, decision: dict, mailer=None,
                     reply: dict | None = None) -> dict:
    if decision.get("status") not in ("approved", "edited"):
        raise SendBlocked("the draft has not been approved")
    final = {**draft, **(decision.get("edits") or {})}
    address = contact_email(target)
    route = target.get("apply_url") or target.get("url") or target.get("source_url") or ""
    identity = f"{agent}:{thread_id}:{target.get('id') or route or address}"
    key = hashlib.sha256(identity.encode()).hexdigest()[:24]
    receipt = store.kv_get("delivery", key)
    if receipt:
        return receipt
    lead_id = "ld_" + key
    company = target.get("company") or target.get("name") or ""
    record = {"target": target, "draft": final, "stage": final.get("stage", "opening")}
    status = "ready_to_send"
    result = {}
    if address:
        reply = reply or {}
        message = OutgoingMessage(
            to=address, subject=final.get("subject", ""), body=final.get("body", ""),
            tag=agent, in_reply_to=reply.get("rfc_message_id", ""),
            references=reply.get("references", ""),
            gmail_thread_id=reply.get("thread_id", ""),
            include_footer=not bool(reply), idempotency_key=key)
        sender = mailer or Mailer(store)
        try:
            result = sender.send(message, enforce_cap=not bool(reply))
        except SendBlocked as exc:
            return {"status": "blocked", "reason": str(exc), "lead_id": lead_id}
        sender.record(thread_id, agent, "out", message, result)
        status = "dry_run" if result.get("dry_run") else "contacted"
    store.upsert("leads", ("id",), {
        "id": lead_id, "agent": agent, "company": company,
        "domain": urlsplit(route).netloc, "person": target.get("person", ""),
        "role": target.get("title") or target.get("kind", ""),
        "email": address, "phone": "", "source_url": route,
        "score": float(target.get("brain_score") or 0), "status": status,
        "thread_id": thread_id, "data_json": json.dumps(record),
        "created_at": now(), "updated_at": now()})
    receipt = {"status": status, "lead_id": lead_id, "to": address, "url": route,
               "company": company, "subject": final.get("subject", ""),
               "body": final.get("body", ""), **result}
    store.kv_set("delivery", key, receipt)
    if status == "ready_to_send":
        store.event("manual_handoff", agent, thread_id, lead_id=lead_id, url=route)
    return receipt


def mark_manual_sent(store, lead_id: str) -> bool:
    """Record an operator-confirmed handoff exactly once."""
    with store.tx():
        cursor = store.execute(
            "UPDATE leads SET status=?,updated_at=? WHERE id=? AND status=?",
            ("contacted", now(), lead_id, "ready_to_send"))
    if cursor.rowcount != 1:
        return False
    store.event("manual_sent", "", "", lead_id=lead_id)
    return True
