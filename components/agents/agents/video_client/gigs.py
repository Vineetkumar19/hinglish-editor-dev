"""The gig half of the video client agent.

The original agent only did cold outreach: crawl a creator's site, find an
address, write. That still runs. This adds the half that was missing - the
people who are already trying to hire an editor and have said so in public.
They convert at a different order of magnitude, because the decision to spend
money has already been made.

It is a mixin on the same graph rather than a second agent, for the reason the
sponsorship agent is one agent: finding a client and pitching one are the same
judgement made twice, and they have to share a memory or neither gets better.
"""
from __future__ import annotations

import json
import re
import time

from core import config
from core.delivery import contact_email, deliver_reviewed
from core.hitl import require_approval
from core.log import get_logger

from . import docs as docs_mod
from . import pitch as pitch_mod
from . import sources as src
from .brain import DealMemory
from .quote import build_quote, find_offer, respond_to

log = get_logger("video.gigs")

# Anything that still looks like markup, a cookie banner or a job-board chrome
# line must never reach the first sentence of an email. This is the last gate
# before his name is on it.
_JUNK = re.compile(
    r'(class=|["<>{}]|description__|show more|show less|sign in|cookies?|'
    r'apply on|posted \d|\b\d{1,2} (minutes|hours|days) ago)', re.I)


def _first_real_sentence(text: str) -> str:
    """The first sentence worth quoting back to them, or nothing."""
    for chunk in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        chunk = chunk.strip()
        if not (40 <= len(chunk) <= 180):
            continue
        if _JUNK.search(chunk):
            continue
        # Has to read like prose, not a list of tags.
        if sum(c.isalpha() or c.isspace() for c in chunk) / len(chunk) < 0.85:
            continue
        return chunk
    return ""


class GigMixin:
    """Sweep for open editing work, rank it, and pitch it."""

    @property
    def brain(self) -> DealMemory:
        if getattr(self, "_deal_brain", None) is None:
            self._deal_brain = DealMemory(self.store)
        return self._deal_brain

    def _say(self, text: str) -> None:
        try:
            from core.notify import get_notifier
            get_notifier(self.store).send("Video clients", text,
                                          tags=("video_client",))
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not post progress: {exc}")

    def sweep_due(self) -> bool:
        if not config.get_bool("VIDEO_GIGS_ENABLED", True):
            return False
        every = config.get_float("VIDEO_GIGS_INTERVAL_SECONDS", 86400)
        last = self.store.kv_get("video_client", "last_sweep") or 0
        try:
            return (time.time() - float(last)) >= every
        except (TypeError, ValueError):
            return True

    # -- nodes -------------------------------------------------------------
    def n_sweep(self, s: dict) -> dict:
        """Find open editing work across every market he sells into."""
        if s.get("gig_queue"):
            return {}
        if not (s.get("sweep") or self.sweep_due()):
            return {"gig_queue": []}
        names = s.get("only_sources") or config.get_list(
            "VIDEO_CLIENT_SOURCES", ["linkedin", "remoteok", "weworkremotely"])
        self._say(f"Looking for editing work on {len(names)} sources. "
                  f"This takes a minute.")
        found = src.find_gigs(names)
        self.store.kv_set("video_client", "last_sweep", time.time())

        fresh, seen_before = [], 0
        for gig in found:
            if not self.store.mark_seen("video_client:gig", gig.key()):
                seen_before += 1
                continue
            row = gig.to_json()
            from core.work_policy import budget_check
            if budget_check(row)["reject"]:
                continue
            row["kind"] = gig.kind()
            row["brain_score"] = round(self.brain.score_deal(row)[0], 4)
            fresh.append(row)

        # Best first. With no history every score is the base rate, so this is
        # a no-op until he has made some decisions - which is the point.
        fresh.sort(key=lambda r: -r["brain_score"])
        cap = config.get_int("VIDEO_CLIENT_MAX_GIGS", 15)
        self._say(f"Found {len(found)} open gigs, {len(fresh)} of them new. "
                  f"Showing the best {min(cap, len(fresh))}.")
        return {"gig_queue": fresh[:cap],
                "stats": {"gigs_found": len(found), "gigs_seen": seen_before,
                          "gigs_queued": len(fresh[:cap])}}

    def n_pick_gig(self, s: dict) -> dict:
        queue = list(s.get("gig_queue") or [])
        if not queue:
            return {"gig": None}
        return {"gig": queue.pop(0), "gig_queue": queue}

    def n_read_gig(self, s: dict) -> dict:
        """Pull the ad text. Without it every pitch is generic."""
        gig = s["gig"]
        if not gig.get("description"):
            from .sources import Gig, describe
            gig = dict(gig)
            gig["description"] = describe(Gig(**{
                k: v for k, v in gig.items()
                if k in Gig.__dataclass_fields__})) or ""
            gig["kind"] = Gig(**{k: v for k, v in gig.items()
                                 if k in Gig.__dataclass_fields__}).kind()
        quote = build_quote(f"{gig.get('title','')} {gig.get('description','')[:2000]} "
                            f"{gig.get('location','')}", first_project=True)
        return {"gig": gig, "quote": quote.to_json(),
                "log": f"read {gig.get('company','')} -> {quote.tier_id}"}

    def n_pitch_gig(self, s: dict) -> dict:
        """Write the approach. The model reads their posting; the code owns
        the facts, the links and the rule that no price goes out yet."""
        from core.lessons import get_lessons
        from core.llm import LLMError
        from .quote import Quote
        from . import brief as brief_mod
        gig, quote = s["gig"], Quote.from_json(s["quote"])

        llm = getattr(self, "llm", None)
        if llm is not None and not llm.is_offline:
            prompt = brief_mod.build_prompt({"gig": gig, "quote": quote.to_json()})
            learned = get_lessons("video_client", self.store).prompt_block(
                context=f"{gig.get('title','')} {gig.get('company','')} "
                        f"{gig.get('kind','')}", scope="pitch")
            if learned:
                prompt = f"{prompt}\n\n{learned}"
            try:
                draft = llm.structured(
                    prompt, brief_mod.PITCH_SCHEMA, task="pitch:video_client",
                    context={"gig": gig, "quote": quote.to_json()},
                    system="You write short, concrete emails offering video "
                           "editing work. You are a working editor, not an "
                           "agency, and you never claim anything you were not "
                           "given.",
                    temperature=0.4,
                    max_tokens=config.get_int("PITCH_MAX_TOKENS", 1200))
                draft = brief_mod.finish(draft, {"gig": gig})
                return {"draft": draft,
                        "log": f"model wrote the pitch for {gig.get('company','')}"}
            except (LLMError, Exception) as exc:  # noqa: BLE001
                if getattr(llm, "provider_name", None) == "chatgpt":
                    raise
                # Never lose the lead because the model is down.
                log.warn(f"model could not write the pitch, using the written "
                         f"template: {exc}")

        observation = _first_real_sentence(gig.get("description") or "")
        draft = pitch_mod.opening_pitch(gig, observation=observation)
        draft["_fallback"] = "the local model was not available"
        return {"draft": draft,
                "log": f"template pitch for {gig.get('company','')}"}

    def n_approve_gig(self, s: dict) -> dict:
        from .quote import Quote
        gig, draft = s["gig"], s["draft"]
        quote = Quote.from_json(s["quote"])
        decision = require_approval(
            agent="video_client", thread_id=s["_thread_id"],
            kind="send_email" if contact_email(gig) else "send_message",
            title=f"Pitch {gig.get('company','')} - {gig.get('title','')}",
            payload={
                "company": gig.get("company", ""),
                "title": gig.get("title", ""),
                "location": gig.get("location", ""),
                "client_kind": gig.get("kind", "unknown"),
                "source": gig.get("source", ""),
                "to": contact_email(gig),
                "apply_url": gig.get("url", ""),
                "subject": draft["subject"], "body": draft["body"],
                "quote_tier": quote.tier_name,
                "quote_ask": quote.render(),
                "quote_floor": quote.money(quote.floor),
                "brain_score": gig.get("brain_score"),
                "reads_as": draft.get("reads_as", ""),
                "fallback": draft.get("_fallback", ""),
                "stage": "opening",
            }, store=self.store)
        try:
            from core.reflect import learn_from_decision
            learn_from_decision("video_client", decision,
                                {"body": draft["body"]}, store=self.store,
                                llm=getattr(self, "llm", None), scope="pitch")
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not learn from that decision: {exc}")
        outcome = "pitch_approved" if decision.approved else "pitch_rejected"
        self.brain.record_deal({**gig, "tier_id": quote.tier_id,
                                "currency": quote.currency}, outcome,
                               note=decision.note or "")
        return {"decision": decision.to_json(),
                "approved_draft": decision.apply_to(draft),
                "log": f"{outcome} for {gig.get('company','')}"}

    def r_after_gig_approve(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "send" if d.get("status") in ("approved", "edited") else "next"

    def n_send_gig(self, s: dict) -> dict:
        """Record it and schedule the chase. Sending itself is the mailer's job."""
        from .quote import Quote
        gig = s["gig"]
        quote = Quote.from_json(s["quote"])
        delivery = deliver_reviewed(
            store=self.store, agent="video_client", thread_id=s["_thread_id"],
            target=gig, draft=s.get("approved_draft") or s["draft"],
            decision=s["decision"], mailer=self.mailer)
        if delivery["status"] == "blocked":
            return {"skipped": {"company": gig.get("company", ""),
                                "reason": delivery["reason"]}}
        deal_id = self.store.kv_get("video_client", "next_deal_id") or 0
        record = {
            "gig": gig, "quote": quote.to_json(),
            "stage": "opening" if delivery["status"] == "contacted" else delivery["status"],
            "lead_id": delivery["lead_id"],
            "draft": s.get("approved_draft") or s["draft"],
            "follow_up_index": 0,
            "next_touch_at": time.time() + pitch_mod.due_after_days(0) * 86400,
            "created_at": time.time(),
        }
        key = f"deal:{gig.get('source','')}:{gig.get('id','')}"
        self.store.kv_set("video_client", key, record)
        self.store.kv_set("video_client", "next_deal_id", int(deal_id) + 1)
        if delivery["status"] == "contacted":
            self.brain.record_deal({**gig, "tier_id": quote.tier_id,
                                    "currency": quote.currency}, "sent")
        return {"sent_gigs": [{"company": gig.get("company", ""),
                               "title": gig.get("title", ""),
                               "url": gig.get("url", "")}],
                "handoff": ({**delivery, "channel": "form", "route": delivery["url"]}
                            if delivery["status"] == "ready_to_send" else []),
                "stats": {delivery["status"]: 1},
                "log": f"{delivery['status']}: {gig.get('company','')}"}

    def r_more_gigs(self, s: dict) -> str:
        return "next" if s.get("gig_queue") else "done"

    # -- chasing -----------------------------------------------------------
    def due_follow_ups(self, now: float | None = None) -> list[dict]:
        """Deals that have gone quiet long enough to deserve another touch."""
        now = now or time.time()
        out = []
        for row in self.store.query(
                "SELECT k, value_json FROM kv WHERE namespace=? "
                "AND k LIKE 'deal:%'", ("video_client",)):
            try:
                rec = json.loads(row["value_json"])
            except Exception:  # noqa: BLE001
                continue
            if rec.get("stage") not in ("opening", "follow_up"):
                continue
            idx = int(rec.get("follow_up_index", 0))
            if idx >= len(pitch_mod.FOLLOW_UPS):
                continue
            if float(rec.get("next_touch_at") or 0) <= now:
                out.append({"key": row["k"], **rec})
        return out

    def advance_follow_up(self, key: str, rec: dict) -> dict | None:
        """Write the next chase and move the clock, or close it out."""
        from .quote import Quote
        idx = int(rec.get("follow_up_index", 0))
        gig = rec.get("gig") or {}
        quote = Quote.from_json(rec.get("quote") or {})
        draft = pitch_mod.follow_up(gig, idx, quote)
        if draft is None:
            rec["stage"] = "lost"
            self.store.kv_set("video_client", key, rec)
            self.brain.record_deal({**gig, "tier_id": quote.tier_id,
                                    "currency": quote.currency}, "no_reply")
            return None
        rec["follow_up_index"] = idx + 1
        nxt = pitch_mod.due_after_days(idx + 1)
        rec["next_touch_at"] = time.time() + (nxt or 0) * 86400
        self.store.kv_set("video_client", key, rec)
        return {"gig": gig, "draft": draft, "quote": quote.to_json(),
                "follow_up_index": idx}

    # -- when they reply ---------------------------------------------------
    def handle_reply(self, gig: dict, message_text: str, quote_json: dict) -> dict:
        """Decide what the reply means and what to send back."""
        from .quote import Quote
        quote = Quote.from_json(quote_json)
        offer = find_offer(message_text, quote.currency)
        counter = respond_to(offer, quote)
        self.brain.record_deal({**gig, "tier_id": quote.tier_id,
                                "currency": quote.currency}, "replied")

        if counter.action == "hold":
            draft = pitch_mod.rate_reply(gig, quote)
            return {"action": "quote", "draft": draft, "amount": quote.ask,
                    "needs_operator": quote.missing}
        if counter.action == "accept":
            return {"action": "accept", "amount": counter.amount,
                    "draft": pitch_mod.rate_reply(gig, quote),
                    "needs_operator": False, "reason": counter.reason}
        if counter.action == "counter":
            return {"action": "counter", "amount": counter.amount,
                    "draft": pitch_mod.counter_reply(gig, quote, counter),
                    "needs_operator": False, "reason": counter.reason,
                    "give": counter.give}
        # Below the floor, or no rate card. This is the one branch that must
        # never resolve itself.
        return {"action": "ask_operator", "amount": counter.amount,
                "draft": None, "needs_operator": True,
                "reason": counter.reason}

    def win(self, gig: dict, quote_json: dict, amount: float) -> dict:
        """They said yes. Produce the paperwork and file the outcome."""
        from .quote import Quote
        quote = Quote.from_json(quote_json)
        proposal = docs_mod.proposal(gig, quote, amount=amount)
        invoice = docs_mod.invoice(gig, quote, amount=amount, deposit=True)
        self.brain.record_deal({**gig, "tier_id": quote.tier_id,
                                "currency": quote.currency}, "deal_won",
                               note=f"{quote.money(amount)}")
        key = f"deal:{gig.get('source','')}:{gig.get('id','')}"
        raw = self.store.kv_get("video_client", key)
        rec = raw if isinstance(raw, dict) else {"gig": gig, "quote": quote_json}
        rec.update({"stage": "won", "amount": amount, "proposal": proposal,
                    "invoice": invoice})
        self.store.kv_set("video_client", key, rec)
        return {"proposal": proposal, "invoice": invoice, "amount": amount}
