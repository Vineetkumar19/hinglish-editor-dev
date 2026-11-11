"""Shared machinery for the three outreach agents.

Agents 1-3 (sponsorship, video-editing clients, full-stack dev sales) differ in
who they contact and what they say, not in how they operate. That shared shape
lives here:

    discover -> pick_lead -> research -> qualify -> draft -> approve -> send
                     ^                     |                     |
                     +---------------------+---------------------+

plus a second graph for handling replies:

    ingest -> classify -> route -> (notify | draft_reply -> approve -> send | close)

Every outbound message passes through a human approval gate. Nothing is sent
without a decision, and the suppression list is checked on every hop.
"""
from __future__ import annotations

import json
import re
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core import config
from core.crawler import Crawler, SiteProfile
from core.graph import END, Command, StateGraph, append, merge_dict
from core.hitl import require_approval
from core.llm import LLM, get_llm, offline_handler
from core.log import get_logger
from core.mailer import Mailer, OutgoingMessage, SendBlocked, valid_email
from core.notify import Notifier, get_notifier
from core.search import (SearchHit, SeedsProvider, discover as search_discover,
                         get_search)
from core.store import Store, get_store, new_id, now

log = get_logger("outreach")

# --------------------------------------------------------------------------
# intent classification
# --------------------------------------------------------------------------
INTENTS = ["interested", "question", "objection_price", "objection_timing",
           "not_interested", "unsubscribe", "out_of_office", "referral",
           "auto_bounce", "other"]

INTENT_SCHEMA = {
    "type": "object",
    "required": ["label", "confidence"],
    "properties": {
        "label": {"type": "string", "enum": INTENTS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
        "reason": {"type": "string", "max_length": 300, "default": ""},
        "asked_for": {"type": "string", "max_length": 200, "default": ""},
    },
}

_INTENT_RULES: list[tuple[str, str]] = [
    ("unsubscribe", r"\b(unsubscribe|remove me|opt.?out|stop emailing|do not "
                    r"contact|take me off)\b"),
    ("auto_bounce", r"\b(delivery (has )?failed|undeliverable|mailbox (is )?full|"
                    r"address not found|550[- ]5\.\d)\b"),
    ("out_of_office", r"\b(out of (the )?office|automatic reply|auto.?reply|"
                      r"on (annual )?leave|on vacation|maternity|paternity|"
                      r"currently away|limited access to email)\b"),
    ("not_interested", r"\b(not interested|no thanks|no thank you|we'?ll pass|"
                       r"not a (good )?fit|not looking|already have|"
                       r"not at this time|please stop)\b"),
    ("objection_price", r"\b(too expensive|budget|cost too much|out of our range|"
                        r"cheaper|price is|pricing is|can'?t afford|discount)\b"),
    ("objection_timing", r"\b(next quarter|later this year|circle back|not right "
                         r"now|bad timing|revisit in|after (q[1-4]|the launch)|"
                         r"too early|reach out in)\b"),
    ("referral", r"\b(forwarded (this|you) to|you should (speak|talk) to|"
                 r"the right person is|cc'?ing|looping in|reach out to \w+ "
                 r"instead|handles this)\b"),
    ("interested", r"\b(interested|sounds (good|great|interesting)|let'?s (talk|"
                   r"chat|discuss|set up)|happy to (chat|talk|discuss)|"
                   r"send (me |us )?(more|the|your)|tell me more|book a call|"
                   r"schedule a call|keen|would love to|yes[,.! ]|go ahead|"
                   r"share (your |the )?(rates?|portfolio|deck|pricing))\b"),
    ("question", r"\?\s*$|\b(what (is|are)|how (much|many|do|does|long)|"
                 r"can you|could you|do you (have|offer)|which|when can)\b"),
]


@offline_handler("classify_intent")
def _offline_intent(ctx: dict) -> dict:
    """Deterministic intent classifier used when no LLM is configured.

    Rules are ordered by consequence: an unsubscribe must never be misread as
    interest, so it is checked first and wins outright.
    """
    text = (ctx.get("text") or "").lower()
    for label, pattern in _INTENT_RULES:
        if re.search(pattern, text, re.I):
            return {"label": label, "confidence": 0.75,
                    "reason": f"matched rule for {label}", "asked_for": ""}
    return {"label": "other", "confidence": 0.3, "reason": "no rule matched",
            "asked_for": ""}


def classify_intent(llm: LLM, text: str, context: str = "") -> dict:
    """Classify a prospect reply. Safety-critical labels are rule-gated.

    Even with a model in the loop, an explicit opt-out or a bounce is decided by
    the regex, because getting that wrong is the one mistake with a legal and a
    reputational cost.
    """
    hard = _offline_intent({"text": text})
    if hard["label"] in ("unsubscribe", "auto_bounce"):
        hard["confidence"] = 0.99
        hard["reason"] = "explicit opt-out or bounce - rule takes precedence"
        return hard
    try:
        out = llm.structured(
            f"Classify this reply to a cold business email.\n"
            f"{'Context: ' + context if context else ''}\n\n"
            f"---\n{text[:4000]}\n---",
            INTENT_SCHEMA, task="classify_intent",
            context={"text": text, "context": context},
            system="You classify replies to business outreach. Be conservative: "
                   "only label 'interested' when the person clearly signals they "
                   "want to continue.",
            temperature=0.0)
        return out
    except Exception as exc:  # noqa: BLE001
        log.warn(f"LLM intent classification failed, using rules: {exc}")
        return hard


# --------------------------------------------------------------------------
# pitch drafting
# --------------------------------------------------------------------------
PITCH_SCHEMA = {
    "type": "object",
    "required": ["subject", "body"],
    "properties": {
        "subject": {"type": "string", "min_length": 8, "max_length": 90},
        "body": {"type": "string", "min_length": 120, "max_length": 2200},
        "personalisation_note": {"type": "string", "max_length": 300, "default": ""},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
    },
}

BANNED_PHRASES = [
    "i hope this email finds you well", "i hope this finds you well",
    "dear sir/madam", "to whom it may concern", "quick question for you",
    "just circling back", "per my last email", "guaranteed results",
    "10x your", "risk-free", "act now", "limited time offer",
]


def lint_pitch(subject: str, body: str, contact_name: str = "") -> list[str]:
    """Catch the tells that get cold email marked as spam - or just ignored."""
    problems = []
    low = (subject + "\n" + body).lower()
    for phrase in BANNED_PHRASES:
        if phrase in low:
            problems.append(f"contains cliche/spam phrase: {phrase!r}")
    if len(body.split()) > 220:
        problems.append(f"body is {len(body.split())} words; cold email over ~200 "
                        f"rarely gets read")
    if body.count("http") > 2:
        problems.append("more than two links - a known spam signal on first contact")
    if subject.isupper() or subject.count("!") > 1:
        problems.append("shouty subject line")
    if re.search(r"\{\{|\}\}|\[\[|\]\]|\bXXX\b|<name>", body):
        problems.append("unfilled merge field left in the body")
    if re.search(r"\b(guarantee|guaranteed)\b", low):
        problems.append("makes a guarantee - avoid promising outcomes you can't control")
    if contact_name and contact_name.lower() not in body.lower() \
            and "hi there" not in body.lower() and "hello" not in body.lower():
        problems.append("no greeting")
    return problems


# --------------------------------------------------------------------------
# state helpers
# --------------------------------------------------------------------------
def outreach_reducers() -> dict:
    return {"log": append, "leads": append, "sent": append, "sent_gigs": append,
            "handoff": append, "skipped": append, "stats": merge_dict}


@dataclass
class OutreachConfig:
    """What makes one outreach agent different from another."""
    agent: str
    search_queries: list[str]
    seed_category: str | None = None
    # An agent can work from its own curated list rather than the shared one.
    # The sponsorship agent uses profiles/sponsors.yaml, which is ordered and
    # annotated for that job specifically.
    seed_file: str | None = None
    # Optional sort applied to the discovered queue, lowest value first.
    rank_fn: Callable[[dict], tuple] | None = None
    # When no email is published, still pursue the lead down the other routes
    # the crawler found - WhatsApp, their enquiry form, a social profile. The
    # agent cannot send those itself, so it hands you a finished message and
    # the link to send it from. A brand with no public address is not a brand
    # that does not want to hear from you.
    allow_non_email: bool = False
    # Extra fields added to the approval card, e.g. the WhatsApp version.
    extras_fn: Callable[[dict], dict] | None = None
    # How many results to pull per search query before ranking and capping.
    per_query: int = 15
    looking_for: str = "partnerships or marketing"
    system_prompt: str = ""
    pitch_instruction: str = ""
    min_score: float = 0.35
    max_leads_per_run: int = 10
    reply_system_prompt: str = ""
    attachments_fn: Callable[[dict], list] | None = None
    enrich_fn: Callable[[SiteProfile, dict], dict] | None = None
    qualify_fn: Callable[[SiteProfile, dict], tuple[float, str]] | None = None
    # An agent whose pitch depends on facts this class knows nothing about
    # supplies its own brief, and the schema the model must answer in. The
    # generic prompt below is the fallback for agents that do not.
    pitch_prompt_fn: Callable[[dict], str] | None = None
    pitch_schema: dict | None = None
    # Runs on whatever the model returned, before linting. This is where a
    # signature gets attached and anything the model should not have written
    # gets taken back off - the model is asked for the message, not for the
    # facts about who is sending it.
    pitch_post_fn: Callable[[dict, dict], dict] | None = None


class OutreachAgent:
    """Builds the discovery/outreach graph and the reply-handling graph."""

    def __init__(self, cfg: OutreachConfig, store: Store | None = None,
                 llm: LLM | None = None, mailer: Mailer | None = None,
                 crawler: Crawler | None = None, notifier: Notifier | None = None,
                 search=None):
        self.cfg = cfg
        self.store = store or get_store()
        self.llm = llm or get_llm(self.store)
        self.mailer = mailer or Mailer(self.store)
        self.crawler = crawler or Crawler(llm=self.llm)
        self.notifier = notifier or get_notifier(self.store)
        self.supplemental_search = None
        if search is not None:
            self.search = search
        elif cfg.seed_file:
            self.search = SeedsProvider(cfg.seed_file)
            if config.get_bool("SUITE_STORYLENS_INTEGRATED"):
                self.supplemental_search = get_search()
        else:
            self.search = get_search()

    # ---------------------------------------------------------------- nodes --
    def n_discover(self, s: dict) -> dict:
        if s.get("leads_queue"):
            return {}
        hits = search_discover(self.cfg.search_queries,
                               per_query=self.cfg.per_query,
                               provider=self.search,
                               category=self.cfg.seed_category)
        if self.supplemental_search is not None:
            hits.extend(search_discover(self.cfg.search_queries, per_query=self.cfg.per_query,
                                       provider=self.supplemental_search,
                                       exclude_domains={hit.domain for hit in hits}))
        queue, skipped = [], []
        for h in hits:
            if self.store.seen(f"{self.cfg.agent}:domain", h.domain):
                skipped.append({"domain": h.domain, "reason": "already contacted"})
                continue
            queue.append({"url": h.url, "domain": h.domain, "title": h.title,
                          "snippet": h.snippet, "meta": h.meta})
        if self.cfg.rank_fn:
            queue.sort(key=self.cfg.rank_fn)
        queue = queue[: self.cfg.max_leads_per_run]
        log.info("discovered targets", found=len(hits), queued=len(queue),
                 already_seen=len(skipped))
        return {"leads_queue": queue, "skipped": skipped,
                "stats": {"discovered": len(hits), "queued": len(queue)}}

    def n_pick_lead(self, s: dict) -> dict:
        queue = list(s.get("leads_queue") or [])
        if not queue:
            return {"current": None}
        current = queue.pop(0)
        return {"current": current, "leads_queue": queue, "profile": None,
                "draft": None, "qualify": None}

    def n_research(self, s: dict) -> dict:
        cur = s["current"]
        hints = (cur.get("meta") or {}).get("hints") or []
        profile = self.crawler.profile_site(cur["url"], hints=hints)
        contacts = [c.__dict__ for c in profile.contacts]
        semantic = {}
        if not contacts or max((c["confidence"] for c in contacts), default=0) < 0.5:
            semantic = self.crawler.semantic_contacts(profile, self.cfg.looking_for)
            for person in semantic.get("people", []):
                if person.get("email") and valid_email(person["email"]):
                    contacts.append({"email": person["email"],
                                     "name": person.get("name", ""),
                                     "role": person.get("role", ""),
                                     "source_url": profile.pages[0].url
                                     if profile.pages else cur["url"],
                                     "confidence": 0.6, "phone": "",
                                     "channel": "email"})
        return {"profile": {
            "domain": profile.domain, "title": profile.title,
            "description": profile.description or semantic.get("company_summary", ""),
            "tech": profile.tech, "socials": profile.socials,
            "contact_form_url": profile.contact_form_url,
            "text": profile.combined_text[:8000],
            "pages_ok": sum(1 for p in profile.pages if p.ok),
        }, "contacts": contacts, "__site": profile}

    def n_qualify(self, s: dict) -> dict:
        cur, prof = s["current"], s.get("profile") or {}
        contacts = s.get("contacts") or []
        emails = [c for c in contacts if c.get("email")
                  and valid_email(c["email"])
                  and not self.mailer.suppression.contains(c["email"])]
        reasons = []
        score = 0.0
        if not prof.get("pages_ok"):
            reasons.append("could not read the site")
        if emails:
            best = max(emails, key=lambda c: c.get("confidence", 0))
            score += best.get("confidence", 0) * 0.6
        else:
            reasons.append("no usable email address found")
        if prof.get("description"):
            score += 0.1
        if prof.get("pages_ok", 0) >= 2:
            score += 0.1
        if self.cfg.qualify_fn:
            bonus, why = self.cfg.qualify_fn(s.get("__site"), s)
            score += bonus
            if why:
                reasons.append(why)
        score = max(0.0, min(1.0, score))
        chosen = max(emails, key=lambda c: c.get("confidence", 0)) if emails else None
        phone_only = (not emails) and any(c.get("phone") for c in contacts)
        if self.cfg.allow_non_email:
            # Every route competes on the same scale, so a phone number the
            # brand published beats an address we merely guessed - a guess can
            # bounce, a number on their contact page cannot. Ties break towards
            # the channel a human is most likely to read.
            order = {"email": 4, "whatsapp": 3, "phone": 2, "form": 1, "social": 0}

            def rank(c):
                return (round(c.get("confidence", 0), 3),
                        order.get(c.get("channel"), 0))

            pool = list(emails) + [c for c in contacts if not c.get("email")]
            if pool:
                best_any = max(pool, key=rank)
                if chosen is None or rank(best_any) > rank(chosen):
                    chosen = best_any
                if not chosen.get("email"):
                    score = max(score, 0.4)
                    reasons.append(f"no address worth trusting - reaching them "
                                   f"by {chosen.get('channel', 'other')} instead")
                elif chosen.get("guessed"):
                    reasons.append("address is a guess, not published by them")
        return {"qualify": {"score": round(score, 3), "reasons": reasons,
                            "contact": chosen, "phone_only": phone_only,
                            "channel": (chosen or {}).get("channel", "email")},
                "stats": {"qualified": 1 if chosen else 0}}

    def r_after_qualify(self, s: dict) -> str:
        q = s.get("qualify") or {}
        if q.get("contact") and q["score"] >= self.cfg.min_score:
            return "draft"
        return "skip"

    def n_skip(self, s: dict) -> dict:
        cur = s["current"]
        q = s.get("qualify") or {}
        reason = ("below score threshold" if q.get("contact")
                  else "; ".join(q.get("reasons") or ["no contact"]))
        # Phone-only leads are kept, not discarded - the blueprint's fallback.
        if q.get("phone_only"):
            phone = next((c["phone"] for c in (s.get("contacts") or [])
                          if c.get("phone")), "")
            self._save_lead(s, status="manual_followup",
                            contact={"phone": phone}, score=q.get("score", 0))
            reason = f"no email; phone {phone} saved for manual WhatsApp follow-up"
        self.store.mark_seen(f"{self.cfg.agent}:domain", cur["domain"],
                             meta={"reason": reason})
        log.info("lead skipped", domain=cur["domain"], reason=reason)
        return {"skipped": {"domain": cur["domain"],
                            "company": self._company_name(s),
                            "reason": reason},
                "log": f"skip {cur['domain']}: {reason}"}

    def n_draft(self, s: dict) -> dict:
        cur, prof, q = s["current"], s["profile"], s["qualify"]
        contact = q["contact"]
        context = {"current": cur, "profile": prof, "contact": contact,
                   "cfg": self.cfg, "state": s}
        if self.cfg.pitch_prompt_fn:
            prompt = self.cfg.pitch_prompt_fn(context)
        else:
            prompt = self._pitch_prompt(cur, prof, contact, s)
        # Everything it has been told off for, in front of it before it writes.
        # Without this the brain only changes who gets written to, never what
        # gets said - and the same rejected sentence comes back forever.
        learned = self.learned_block(
            context=f"{cur.get('domain','')} {prof.get('title','')} "
                    f"{prof.get('description','')[:300]}")
        if learned:
            prompt = f"{prompt}\n\n{learned}"
        # Hands. If this agent has a toolbelt and tool use is on, the model
        # gets to look things up before it writes - his real numbers, the rate
        # card, their pricing page - instead of only seeing what this code
        # decided to put in the prompt. With tools off, or offline, this is the
        # same single structured call it always was.
        from core import tools as tools_mod
        from core.toolbelt import belt_for
        belt = belt_for(self.cfg.agent) if config.get_bool(
            "TOOL_USE_ENABLED", True) else []
        call_log = tools_mod.CallLog()
        if belt and not self.llm.is_offline:
            draft, call_log = self.llm.structured_with_tools(
                prompt, self.cfg.pitch_schema or PITCH_SCHEMA, belt,
                task=f"pitch:{self.cfg.agent}", context=context,
                system=self.cfg.system_prompt, temperature=0.4,
                max_tokens=config.get_int("PITCH_MAX_TOKENS", 1200))
        else:
            draft = self.llm.structured(
                prompt, self.cfg.pitch_schema or PITCH_SCHEMA,
                task=f"pitch:{self.cfg.agent}", context=context,
                system=self.cfg.system_prompt, temperature=0.4,
                max_tokens=config.get_int("PITCH_MAX_TOKENS", 1200))
        if call_log.calls:
            draft = dict(draft)
            draft["_tool_calls"] = call_log.to_json()
            draft["_tools_used"] = call_log.summary()
        if self.cfg.pitch_post_fn:
            draft = self.cfg.pitch_post_fn(draft, context)
        problems = lint_pitch(draft["subject"], draft["body"],
                              contact.get("name", ""))
        return {"draft": draft, "lint": problems,
                "log": f"drafted for {cur['domain']} ({len(problems)} lint notes)"}

    def _reflect(self, decision, payload: dict) -> None:
        """Turn what he just said into a standing rule. Never fails a run."""
        try:
            from core.reflect import learn_from_decision
            learn_from_decision(self.cfg.agent, decision, payload,
                                store=self.store, llm=self.llm)
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not learn from that decision: {exc}")

    def learned_block(self, context: str = "", scope: str = "") -> str:
        """The rules this agent now follows, as prompt text."""
        try:
            from core.lessons import get_lessons
            return get_lessons(self.cfg.agent, self.store).prompt_block(
                context=context, scope=scope)
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not read the lessons: {exc}")
            return ""

    def _pitch_prompt(self, cur: dict, prof: dict, contact: dict, s: dict) -> str:
        who = contact.get("name") or "the team"
        role = f" ({contact['role']})" if contact.get("role") else ""
        return textwrap.dedent(f"""
            Write a short, specific first-contact email.

            Recipient: {who}{role} at {self._company_name(s) or cur['domain']}
            Their site says: {prof.get('description', '')[:400]}
            Detected stack: {', '.join(prof.get('tech', [])[:8]) or 'unknown'}

            {self.cfg.pitch_instruction}

            Rules:
            - Under 150 words. Plain text. No markdown.
            - Open with something specific and verifiable about THEIR site or work,
              drawn only from the content below. If you cannot find anything
              specific, say so plainly rather than inventing a compliment.
            - One clear ask at the end, phrased as a question.
            - No superlatives, no guarantees, no "hope this finds you well".
            - Sign off as {config.get('OPERATOR_NAME', 'Vineet')}.

            Their site content:
            ---
            {prof.get('text', '')[:6000]}
            ---
        """).strip()

    def n_approve(self, s: dict) -> dict:
        cur, draft, q = s["current"], s["draft"], s["qualify"]
        contact = q["contact"]
        channel = contact.get("channel") or "email"
        target = (contact.get("email") or contact.get("phone")
                  or contact.get("url") or cur["domain"])
        verb = {"email": "Email", "whatsapp": "WhatsApp", "phone": "Call",
                "form": "Enquiry form at", "social": "DM"}.get(channel, "Contact")
        payload = {"to": target, "subject": draft["subject"],
                   "body": draft["body"], "domain": cur["domain"],
                   "company": self._company_name(s),
                   "score": q["score"], "lint": s.get("lint", []),
                   "why": draft.get("personalisation_note", ""),
                   # What the model understood the brand to be, and whether a
                   # model wrote this at all. Both belong in front of you before
                   # you approve: a wrong read is the cheapest thing to catch.
                   "reads_as": draft.get("reads_as", ""),
                   # What the model went and looked up before writing this.
                   "tools_used": draft.get("_tools_used", ""),
                   "fallback": draft.get("_fallback", ""),
                   "source_url": contact.get("source_url", ""),
                   "channel": channel,
                   "guessed": bool(contact.get("guessed")),
                   "evidence": contact.get("evidence", "")}
        extras = {}
        if self.cfg.extras_fn:
            try:
                extras = self.cfg.extras_fn(s) or {}
                payload.update(extras)
            except Exception as exc:  # noqa: BLE001
                log.warn(f"extras_fn failed: {exc}")
        decision = require_approval(
            agent=self.cfg.agent, thread_id=s["_thread_id"],
            kind="send_email" if channel == "email" else "send_message",
            title=f"{verb} {target} at {cur['domain']}",
            payload=payload, store=self.store)
        self._reflect(decision, payload)
        if not decision.approved:
            self.store.mark_seen(f"{self.cfg.agent}:domain", cur["domain"],
                                 meta={"reason": "rejected by operator"})
            return {"decision": decision.to_json(), "extras": extras,
                    "skipped": {"domain": cur["domain"],
                                "company": self._company_name(s),
                                "reason": f"operator rejected: {decision.note}"},
                    "log": f"rejected {cur['domain']}"}
        final = decision.apply_to({"subject": draft["subject"], "body": draft["body"]})
        # The other-channel drafts travel with the state so the send step can
        # hand them over; they are built once, at approval time, from the same
        # facts the card showed you.
        return {"decision": decision.to_json(), "approved_draft": final,
                "extras": extras, "log": f"approved {cur['domain']}"}

    def r_after_approve(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "send" if d.get("status") in ("approved", "edited") else "next"

    def n_send(self, s: dict) -> dict:
        cur, q = s["current"], s["qualify"]
        contact = q["contact"]
        final = s["approved_draft"]

        channel = contact.get("channel") or "email"
        if channel != "email" or not contact.get("email"):
            # Nothing here can be posted automatically - a WhatsApp message and
            # a web form both need a human hand. So the finished message is
            # stored against the lead and handed over, rather than quietly
            # dropped, which is what used to happen.
            lead_id = self._save_lead(s, status="ready_to_send",
                                      contact=contact, score=q["score"])
            route = contact.get("phone") or contact.get("url") or cur["domain"]
            self.store.mark_seen(f"{self.cfg.agent}:domain", cur["domain"],
                                 meta={"channel": channel, "route": route})
            return {"handoff": {"domain": cur["domain"], "channel": channel,
                                "route": route, "lead_id": lead_id,
                                "company": self._company_name(s),
                                "subject": final["subject"],
                                "body": final["body"],
                                "whatsapp_text": (s.get("extras") or {}).get("whatsapp_text", ""),
                                "instagram_dm": (s.get("extras") or {}).get("instagram_dm", ""),
                                "wa_link": (s.get("extras") or {}).get("wa_link", ""),
                                "best_email": (s.get("extras") or {}).get("best_email", ""),
                                "best_phone": (s.get("extras") or {}).get("best_phone", "")},
                    "stats": {"ready_to_send": 1},
                    "log": f"ready to send by {channel} to {route}"}

        lead_id = self._save_lead(s, status="sending", contact=contact,
                                  score=q["score"])
        msg = OutgoingMessage(to=contact["email"], subject=final["subject"],
                              body=final["body"], tag=self.cfg.agent,
                              idempotency_key=f"{s['_thread_id']}:{cur['domain']}:opening")
        if self.cfg.attachments_fn:
            msg.attachments = self.cfg.attachments_fn(s) or []
        try:
            result = self.mailer.send(msg)
        except SendBlocked as exc:
            log.warn(f"send blocked: {exc}")
            self.store.run("UPDATE leads SET status=?,updated_at=? WHERE id=?",
                           ("blocked", now(), lead_id))
            return {"skipped": {"domain": cur["domain"], "reason": str(exc)},
                    "log": f"send blocked for {cur['domain']}: {exc}",
                    "blocked": True}
        self.mailer.record(s["_thread_id"], self.cfg.agent, "out", msg, result)
        self.store.mark_seen(f"{self.cfg.agent}:domain", cur["domain"],
                             meta={"email": contact["email"]})
        self.store.mark_seen(f"{self.cfg.agent}:email", contact["email"])
        self.store.run("UPDATE leads SET status=?, updated_at=? WHERE id=?",
                       ("dry_run" if result.get("dry_run") else "contacted", now(), lead_id))
        return {"sent": {"domain": cur["domain"], "to": contact["email"],
                         "subject": final["subject"],
                         "message_id": result.get("message_id"),
                         "lead_id": lead_id, "dry_run": result.get("dry_run")},
                "stats": {"sent": 1},
                "log": f"sent to {contact['email']}"}

    def r_more(self, s: dict) -> str:
        return "next" if s.get("leads_queue") else "done"

    def n_done(self, s: dict) -> dict:
        sent = s.get("sent") or []
        stats = {**(s.get("stats") or {}), "drafts_delivered": len(sent) + len(s.get("sent_gigs") or []),
                 "skipped": len(s.get("skipped") or [])}
        log.info("outreach run finished", **stats)
        return {"summary": stats}

    # -------------------------------------------------------------- helpers --
    @staticmethod
    def _company_name(s: dict) -> str:
        """What to call this company in an email.

        The curated name from your target list wins over the crawled <title>,
        because a page title is usually a keyword-stuffed sentence - writing
        "partnerships at Cricket Live Score, Cricket News, Predictions, Stats?"
        in a subject line marks the mail as automated instantly.
        """
        cur = s.get("current") or {}
        prof = s.get("profile") or {}
        seeded = (cur.get("title") or "").strip()
        if seeded and len(seeded) <= 48 and "," not in seeded:
            return seeded
        title = (prof.get("title") or "").strip()
        # trim the "Brand | tagline - keywords" pattern down to the brand
        for sep in ("|", " - ", "—", "–", ":", ","):
            if sep in title:
                title = title.split(sep)[0].strip()
                break
        if title and len(title) <= 48:
            return title
        if seeded:
            return seeded
        domain = (cur.get("domain") or "").removeprefix("www.")
        return domain.split(".")[0].replace("-", " ").title() if domain else ""

    def _save_lead(self, s: dict, status: str, contact: dict, score: float) -> str:
        cur, prof = s["current"], s.get("profile") or {}
        lead_id = new_id("ld")
        self.store.upsert("leads", ("id",), {
            "id": lead_id, "agent": self.cfg.agent,
            "company": self._company_name(s),
            "domain": cur["domain"], "person": contact.get("name", ""),
            "role": contact.get("role", ""), "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "source_url": contact.get("source_url", cur["url"]),
            "score": score, "status": status, "thread_id": s.get("_thread_id"),
            "data_json": json.dumps({"profile": prof, "qualify": s.get("qualify"),
                                     "target": cur, "draft": s.get("approved_draft") or s.get("draft")},
                                    default=str),
            "created_at": now(), "updated_at": now(),
        })
        return lead_id

    # ---------------------------------------------------------------- graph --
    def build(self, recursion_limit: int = 200):
        g = StateGraph(reducers=outreach_reducers())
        g.add_node("discover", self.n_discover, retries=1)
        g.add_node("pick_lead", self.n_pick_lead)
        g.add_node("research", self.n_research, retries=1, backoff=2)
        g.add_node("qualify", self.n_qualify)
        g.add_node("skip", self.n_skip)
        g.add_node("draft", self.n_draft, retries=1)
        g.add_node("approve", self.n_approve)
        g.add_node("send", self.n_send)
        g.add_node("done", self.n_done)

        g.set_entry_point("discover")
        g.add_conditional_edges("discover",
                                lambda s: "next" if s.get("leads_queue") else "done",
                                {"next": "pick_lead", "done": "done"})
        g.add_conditional_edges("pick_lead",
                                lambda s: "go" if s.get("current") else "done",
                                {"go": "research", "done": "done"})
        g.add_edge("research", "qualify")
        g.add_conditional_edges("qualify", self.r_after_qualify,
                                {"draft": "draft", "skip": "skip"})
        g.add_conditional_edges("skip", self.r_more,
                                {"next": "pick_lead", "done": "done"})
        g.add_edge("draft", "approve")
        g.add_conditional_edges("approve", self.r_after_approve,
                                {"send": "send", "next": "more"})
        g.add_node("more", lambda s: None)
        g.add_conditional_edges("more", self.r_more,
                                {"next": "pick_lead", "done": "done"})
        g.add_conditional_edges("send", self.r_more,
                                {"next": "pick_lead", "done": "done"})
        g.add_edge("done", END)
        return g.compile(store=self.store, name=self.cfg.agent,
                         recursion_limit=recursion_limit)

    def run(self, thread_id: str | None = None, **kw):
        tid = thread_id or f"{self.cfg.agent}-{time.strftime('%Y%m%d-%H%M%S')}"
        app = self.build()
        return app.invoke({"_thread_id": tid}, thread_id=tid, **kw)


# ==========================================================================
# reply handling
# ==========================================================================
REPLY_SCHEMA = {
    "type": "object",
    "required": ["body"],
    "properties": {
        "body": {"type": "string", "min_length": 60, "max_length": 2500},
        "subject": {"type": "string", "max_length": 120, "default": ""},
        "next_step": {"type": "string", "max_length": 200, "default": ""},
        "needs_human": {"type": "boolean", "default": False},
    },
}

TERMINAL_INTENTS = {"not_interested", "unsubscribe", "auto_bounce"}
NOTIFY_INTENTS = {"interested", "referral"}


@dataclass
class ReplyConfig:
    agent: str
    system_prompt: str = ""
    reply_instruction: str = ""
    escalate_intents: tuple = ("interested",)
    auto_close_intents: tuple = ("not_interested", "unsubscribe", "auto_bounce")
    snooze_days: int = 30


class ReplyAgent:
    """Turns an inbound reply into the right next action.

    The safety-critical branches (opt-out, bounce, hard no) are handled by the
    graph directly and never reach an LLM. Everything else drafts a reply that
    still needs your approval before it goes out.
    """

    def __init__(self, cfg: ReplyConfig, store: Store | None = None,
                 llm: LLM | None = None, mailer: Mailer | None = None,
                 notifier: Notifier | None = None):
        self.cfg = cfg
        self.store = store or get_store()
        self.llm = llm or get_llm(self.store)
        self.mailer = mailer or Mailer(self.store)
        self.notifier = notifier or get_notifier(self.store)

    # ---------------------------------------------------------------- nodes --
    def n_ingest(self, s: dict) -> dict:
        msg = s["message"]
        lead = self.store.one(
            "SELECT * FROM leads WHERE agent=? AND email=? ORDER BY created_at DESC "
            "LIMIT 1", (self.cfg.agent, (msg.get("from_addr") or "").lower()))
        history = []
        if lead:
            history = self.store.query(
                "SELECT direction, subject, body, ts FROM messages WHERE thread_id=? "
                "ORDER BY ts ASC LIMIT 20", (lead["thread_id"] or "",))
        self.store.upsert("messages", ("id",), {
            "id": new_id("ms"),
            "thread_id": (lead or {}).get("thread_id") or s["_thread_id"],
            "agent": self.cfg.agent, "direction": "in",
            "provider_id": msg.get("id", ""), "rfc_id": msg.get("rfc_message_id", ""),
            "in_reply_to": msg.get("in_reply_to", ""),
            "addr_from": msg.get("from_addr", ""), "addr_to": msg.get("to_addr", ""),
            "subject": msg.get("subject", ""), "body": msg.get("reply_text", ""),
            "intent": "", "ts": now(),
        })
        return {"lead": lead, "history": history,
                "log": f"ingested reply from {msg.get('from_addr')}"}

    def n_classify(self, s: dict) -> dict:
        msg = s["message"]
        hard = _offline_intent({"text": msg.get("reply_text", "")})
        if hard["label"] in ("unsubscribe", "auto_bounce"):
            intent = hard
        elif msg.get("is_auto_reply"):
            intent = {"label": "out_of_office", "confidence": 0.95,
                      "reason": "auto-reply headers", "asked_for": ""}
        else:
            ctx = f"Our agent: {self.cfg.agent}. Subject: {msg.get('subject','')}"
            intent = classify_intent(self.llm, msg.get("reply_text", ""), ctx)
        self.store.run("UPDATE messages SET intent=? WHERE provider_id=?",
                       (intent["label"], msg.get("id", "")))
        log.info("reply classified", intent=intent["label"],
                 confidence=intent["confidence"])
        return {"intent": intent, "log": f"intent={intent['label']}"}

    def r_route(self, s: dict) -> str:
        label = s["intent"]["label"]
        if label == "unsubscribe":
            return "unsubscribe"
        if label == "auto_bounce":
            return "bounce"
        if label == "out_of_office":
            return "snooze"
        if label == "not_interested":
            return "close"
        return "engage"

    def n_unsubscribe(self, s: dict) -> dict:
        addr = s["message"].get("from_addr", "")
        self.mailer.suppression.add(addr, reason="unsubscribe request in reply")
        self._set_lead_status(s, "unsubscribed")
        self._learn_outcome(s, "unsubscribed")
        self.notifier.send("Opt-out recorded",
                           f"{addr} asked to be removed. They are now suppressed "
                           f"permanently across every agent.", priority="low")
        return {"outcome": "unsubscribed", "log": f"suppressed {addr}"}

    def n_bounce(self, s: dict) -> dict:
        addr = s["message"].get("from_addr", "")
        target = s.get("lead", {}) or {}
        bounced = target.get("email") or addr
        self.mailer.suppression.add(bounced, reason="smtp bounce")
        self._set_lead_status(s, "bounced")
        self._learn_outcome(s, "bounced")
        rate = self.mailer.bounce_rate()
        if rate > 0.02:
            self.notifier.send(
                "Bounce rate above 2%",
                f"Current 30-day bounce rate is {rate:.1%}. Pause outreach and "
                f"clean the list before sending more - this is the threshold "
                f"where sender reputation starts to degrade.", priority="high")
        return {"outcome": "bounced", "bounce_rate": rate,
                "log": f"bounce recorded for {bounced}"}

    def n_snooze(self, s: dict) -> dict:
        until = now() + self.cfg.snooze_days * 86400
        self._set_lead_status(s, "snoozed")
        lead = s.get("lead") or {}
        if lead.get("id"):
            self.store.kv_set("snooze", lead["id"],
                              {"until": until, "agent": self.cfg.agent})
        return {"outcome": "snoozed", "snooze_until": until,
                "log": f"snoozed for {self.cfg.snooze_days} days"}

    def n_close(self, s: dict) -> dict:
        self._set_lead_status(s, "closed_lost")
        self._learn_outcome(s, "replied_no")
        return {"outcome": "closed_lost", "log": "closed - not interested"}

    def n_notify(self, s: dict) -> dict:
        msg = s["message"]
        lead = s.get("lead") or {}
        brand = lead.get("company") or msg.get("from_name") or msg.get("from_addr", "")
        operator = config.get("OPERATOR_NAME", "Vineet")
        base = config.get("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")
        positive = s["intent"]["label"] in ("interested", "referral")
        if positive:
            self._learn_outcome(s, "replied_interested")
        self.notifier.send(
            title=(f"{brand} has responded - they are interested!" if positive
                   else f"{brand} replied: {s['intent']['label']}"),
            body=f"Hey {operator}, {brand} replied ({s['intent']['label']}).\n\n"
                 f"From: {msg.get('from_addr')}\n"
                 f"Subject: {msg.get('subject')}\n\n"
                 f"{(msg.get('reply_text') or '')[:700]}",
            priority="urgent" if positive else "normal", url=f"{base}/approvals",
            # the agent name is how the Telegram channel picks a topic, so an
            # interview call lands in Jobs and a brand reply lands in Sponsorship
            tags=(self.cfg.agent, "tada", "incoming_envelope"))
        self._set_lead_status(s, "engaged")
        return {"notified": True, "log": f"operator alerted about {brand}"}

    def r_after_notify(self, s: dict) -> str:
        return "draft" if config.get_bool("AUTO_DRAFT_REPLIES", True) else "end"

    def _learn_outcome(self, state, outcome):
        lead = state.get("lead") or {}
        if not lead:
            return
        message_id = (state.get("message") or {}).get("id") or state["_thread_id"]
        key = f"{self.cfg.agent}:{message_id}:{outcome}"
        with self.store.tx():
            if self.store.seen("reply_feedback", key):
                return
            data = json.loads(lead.get("data_json") or "{}")
            target = data.get("target") or data.get("current") or lead
            if self.cfg.agent == "sponsorship":
                from agents.sponsorship.brain import Memory
                Memory(self.store).record_target(target, outcome)
            elif self.cfg.agent in ("video_client", "fullstack_sales"):
                if self.cfg.agent == "video_client":
                    from agents.video_client.brain import DealMemory as Brain
                else:
                    from agents.fullstack_sales.brain import DevMemory as Brain
                Brain(self.store).record_deal(target, "replied" if outcome == "replied_interested" else outcome)
            self.store.mark_seen("reply_feedback", key)

    def n_draft_reply(self, s: dict) -> dict:
        msg, lead = s["message"], s.get("lead") or {}
        history = "\n\n".join(
            f"[{h['direction']}] {h['subject']}\n{(h['body'] or '')[:800]}"
            for h in (s.get("history") or [])[-6:])
        prompt = textwrap.dedent(f"""
            A prospect replied to our outreach. Draft the next message.

            Their reply intent: {s['intent']['label']}
            They asked for: {s['intent'].get('asked_for') or 'nothing specific'}

            {self.cfg.reply_instruction}

            Rules:
            - Answer what they actually asked, first, in the first two lines.
            - Under 160 words, plain text, no markdown.
            - Never invent prices, dates, availability or past work. If a fact is
              needed that you do not have, set needs_human true and leave a clear
              placeholder describing exactly what is missing.
            - One concrete next step at the end.

            Conversation so far:
            ---
            {history}
            ---

            Their latest reply:
            ---
            {(msg.get('reply_text') or '')[:3000]}
            ---
        """).strip()
        draft = self.llm.structured(
            prompt, REPLY_SCHEMA, task=f"reply:{self.cfg.agent}",
            context={"message": msg, "lead": lead, "intent": s["intent"],
                     "history": s.get("history") or [], "state": s},
            system=self.cfg.system_prompt, temperature=0.4, max_tokens=1200)
        subject = draft.get("subject") or (
            msg.get("subject", "") if msg.get("subject", "").lower().startswith("re:")
            else "Re: " + msg.get("subject", ""))
        return {"reply_draft": {**draft, "subject": subject},
                "log": "reply drafted"}

    def n_approve_reply(self, s: dict) -> dict:
        msg = s["message"]
        d = s["reply_draft"]
        decision = require_approval(
            agent=self.cfg.agent, thread_id=s["_thread_id"], kind="send_reply",
            title=f"Reply to {msg.get('from_addr')} - {s['intent']['label']}",
            payload={"to": msg.get("from_addr"), "subject": d["subject"],
                     "body": d["body"], "intent": s["intent"],
                     "needs_human": d.get("needs_human"),
                     "next_step": d.get("next_step"),
                     "their_message": (msg.get("reply_text") or "")[:1500],
                     **(s.get("reply_extras") or {})},
            store=self.store)
        if not decision.approved:
            return {"decision": decision.to_json(), "outcome": "reply_rejected",
                    "log": "operator rejected the reply"}
        return {"decision": decision.to_json(),
                "final_reply": decision.apply_to({"subject": d["subject"],
                                                  "body": d["body"]})}

    def r_after_approve_reply(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "send" if d.get("status") in ("approved", "edited") else "end"

    def n_send_reply(self, s: dict) -> dict:
        msg = s["message"]
        final = s["final_reply"]
        out = OutgoingMessage(
            to=msg.get("from_addr", ""), subject=final["subject"],
            body=final["body"], in_reply_to=msg.get("rfc_message_id", ""),
            references=msg.get("references", ""),
            gmail_thread_id=msg.get("thread_id", ""), tag=self.cfg.agent,
            idempotency_key=f"{s['_thread_id']}:reply",
            include_footer=False)     # a threaded 1:1 reply is not bulk mail
        if s.get("reply_attachments"):
            from pathlib import Path
            from core.mailer import Attachment
            out.attachments = [Attachment(Path(path).name, Path(path).read_bytes())
                               for path in s["reply_attachments"]]
        try:
            result = self.mailer.send(out, enforce_cap=False)
        except SendBlocked as exc:
            return {"outcome": f"blocked: {exc}", "log": str(exc)}
        self.mailer.record(s["_thread_id"], self.cfg.agent, "out", out, result)
        self._set_lead_status(s, "in_conversation")
        return {"outcome": "replied", "log": f"replied to {msg.get('from_addr')}"}

    def _set_lead_status(self, s: dict, status: str) -> None:
        lead = s.get("lead") or {}
        if lead.get("id"):
            self.store.run("UPDATE leads SET status=?, updated_at=? WHERE id=?",
                           (status, now(), lead["id"]))

    # ---------------------------------------------------------------- graph --
    def build(self):
        g = StateGraph(reducers={"log": append})
        g.add_node("ingest", self.n_ingest)
        g.add_node("classify", self.n_classify, retries=1)
        g.add_node("unsubscribe", self.n_unsubscribe)
        g.add_node("bounce", self.n_bounce)
        g.add_node("snooze", self.n_snooze)
        g.add_node("close", self.n_close)
        g.add_node("notify", self.n_notify)
        g.add_node("draft_reply", self.n_draft_reply, retries=1)
        g.add_node("approve_reply", self.n_approve_reply)
        g.add_node("send_reply", self.n_send_reply)

        g.set_entry_point("ingest")
        g.add_edge("ingest", "classify")
        g.add_conditional_edges("classify", self.r_route, {
            "unsubscribe": "unsubscribe", "bounce": "bounce",
            "snooze": "snooze", "close": "close", "engage": "notify"})
        for terminal in ("unsubscribe", "bounce", "snooze", "close"):
            g.add_edge(terminal, END)
        g.add_conditional_edges("notify", self.r_after_notify,
                                {"draft": "draft_reply", "end": END})
        g.add_edge("draft_reply", "approve_reply")
        g.add_conditional_edges("approve_reply", self.r_after_approve_reply,
                                {"send": "send_reply", "end": END})
        g.add_edge("send_reply", END)
        return g.compile(store=self.store, name=f"{self.cfg.agent}_reply")

    def handle(self, message: dict, thread_id: str | None = None, **kw):
        tid = thread_id or f"{self.cfg.agent}-reply-{message.get('id') or new_id()}"
        return self.build().invoke({"message": message, "_thread_id": tid},
                                   thread_id=tid, **kw)
