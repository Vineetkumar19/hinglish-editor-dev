"""The half of the dev sales agent that goes looking.

The existing agent waits: it crawls company sites and pitches whoever looks
like they might need software one day. This adds the half that answers people
who have already said they want work done, which converts at a different order
of magnitude for the same reason it does in the video agent - the decision to
spend money has already been made.

One graph, two phases, one memory. Same as the other three.
"""
from __future__ import annotations

import json
import re
import time

from core import config
from core.delivery import contact_email, deliver_reviewed
from core.hitl import require_approval
from core.log import get_logger

from . import packages as pkg_mod
from . import sources as src
from .brain import DevMemory

log = get_logger("dev.gigs")

# Anything that still looks like markup or job-board chrome must never reach
# the first sentence of an email with his name on it.
_JUNK = re.compile(
    r'(class=|["<>{}]|description__|show more|show less|sign in|cookies?|'
    r'apply on|posted \d|\b\d{1,2} (minutes|hours|days) ago)', re.I)


def _first_real_sentence(text: str) -> str:
    for chunk in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        chunk = chunk.strip()
        if not (40 <= len(chunk) <= 180) or _JUNK.search(chunk):
            continue
        if sum(c.isalpha() or c.isspace() for c in chunk) / len(chunk) < 0.85:
            continue
        return chunk
    return ""


class DevGigMixin:
    """Sweep for open development work, rank it, read it, and pitch it."""

    @property
    def brain(self) -> DevMemory:
        if getattr(self, "_dev_brain", None) is None:
            self._dev_brain = DevMemory(self.store)
        return self._dev_brain

    def _say(self, text: str) -> None:
        try:
            from core.notify import get_notifier
            get_notifier(self.store).send("Dev sales", text,
                                          tags=("fullstack_sales",))
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not post progress: {exc}")

    def sweep_due(self) -> bool:
        if not config.get_bool("DEV_GIGS_ENABLED", True):
            return False
        every = config.get_float("DEV_GIGS_INTERVAL_SECONDS", 86400)
        last = self.store.kv_get("fullstack_sales", "last_sweep") or 0
        try:
            return (time.time() - float(last)) >= every
        except (TypeError, ValueError):
            return True

    # -- nodes -------------------------------------------------------------
    def n_sweep(self, s: dict) -> dict:
        if s.get("gig_queue"):
            return {}
        if not (s.get("sweep") or self.sweep_due()):
            return {"gig_queue": []}
        names = s.get("only_sources") or config.get_list(
            "DEV_CLIENT_SOURCES", ["linkedin", "remoteok", "weworkremotely"])
        self._say(f"Looking for development work on {len(names)} sources. "
                  f"This takes a minute.")
        found = src.find_gigs(names)
        self.store.kv_set("fullstack_sales", "last_sweep", time.time())

        fresh, seen_before = [], 0
        for gig in found:
            if not self.store.mark_seen("fullstack_sales:gig", gig.key()):
                seen_before += 1
                continue
            row = gig.to_json()
            from core.work_policy import budget_check
            if budget_check(row)["reject"]:
                continue
            row["work_kind"] = gig.work_kind()
            row["client_kind"] = gig.client_kind()
            row["brain_score"] = round(self.brain.score_deal(row)[0], 4)
            fresh.append(row)

        # Payment work first, then whatever the brain has learned pays.
        rank = {"payment_rescue": 0, "payments": 1, "rescue": 2}
        fresh.sort(key=lambda r: (rank.get(r["work_kind"], 5), -r["brain_score"]))
        cap = config.get_int("DEV_CLIENT_MAX_GIGS", 15)
        pay = sum(1 for r in fresh if r["work_kind"] in ("payment_rescue", "payments"))
        self._say(f"Found {len(found)} open gigs, {len(fresh)} new, {pay} of them "
                  f"payment work. Showing the best {min(cap, len(fresh))}.")
        return {"gig_queue": fresh[:cap],
                "stats": {"gigs_found": len(found), "gigs_seen": seen_before,
                          "gigs_queued": len(fresh[:cap]), "payment_gigs": pay}}

    def n_pick_gig(self, s: dict) -> dict:
        queue = list(s.get("gig_queue") or [])
        if not queue:
            return {"gig": None}
        return {"gig": queue.pop(0), "gig_queue": queue}

    def n_read_gig(self, s: dict) -> dict:
        """Fetch the posting, re-judge it, and price it."""
        gig = dict(s["gig"])
        if not gig.get("description"):
            g = src.Gig(**{k: v for k, v in gig.items()
                           if k in src.Gig.__dataclass_fields__})
            gig["description"] = src.describe(g) or ""
            g.description = gig["description"]
            # Now that the text exists, the employment-versus-client judgement
            # can actually be made. On the sweep it was a guess from the title.
            ok, why = src.is_dev_work(g)
            gig["work_kind"] = g.work_kind()
            gig["client_kind"] = g.client_kind()
            gig["rejected"] = "" if ok else why
        blob = f"{gig.get('title','')} {gig.get('description','')[:2500]} " \
               f"{gig.get('location','')}"
        package = pkg_mod.build_package(blob)
        return {"gig": gig,
                "package": package.to_json() if package else {},
                "log": f"read {gig.get('company','')} -> "
                       f"{gig.get('work_kind','')}"}

    def r_after_read(self, s: dict) -> str:
        return "skip" if (s.get("gig") or {}).get("rejected") else "pitch"

    def n_skip_gig(self, s: dict) -> dict:
        gig = s["gig"]
        return {"skipped": [{"domain": gig.get("company", ""),
                             "company": gig.get("company", ""),
                             "reason": gig.get("rejected", "")}],
                "stats": {"gigs_skipped": 1},
                "log": f"skipped {gig.get('company','')}: {gig.get('rejected','')}"}

    def n_pitch_gig(self, s: dict) -> dict:
        from core.lessons import get_lessons
        from core.llm import LLMError
        from . import brief as brief_mod
        gig = s["gig"]
        package = s.get("package") or {}

        llm = getattr(self, "llm", None)
        if llm is not None and not llm.is_offline:
            try:
                from agents.job_hunter.resume import load_master
                profile = load_master()
            except Exception:  # noqa: BLE001
                profile = {}
            prompt = brief_mod.build_prompt({"gig": gig, "package": package,
                                             "profile": profile})
            learned = get_lessons("fullstack_sales", self.store).prompt_block(
                context=f"{gig.get('title','')} {gig.get('work_kind','')} "
                        f"{gig.get('client_kind','')}", scope="pitch")
            if learned:
                prompt = f"{prompt}\n\n{learned}"
            try:
                draft = llm.structured(
                    prompt, brief_mod.PITCH_SCHEMA, task="pitch:fullstack_sales",
                    context={"gig": gig, "package": package},
                    system="You write short, concrete emails offering software "
                           "development work. You are a working engineer, not "
                           "an agency, and you never claim anything you were "
                           "not given.",
                    temperature=0.4,
                    max_tokens=config.get_int("PITCH_MAX_TOKENS", 1200))
                draft = brief_mod.finish(draft, {"gig": gig})
                return {"draft": draft,
                        "log": f"model wrote the pitch for {gig.get('company','')}"}
            except (LLMError, Exception) as exc:  # noqa: BLE001
                if getattr(llm, "provider_name", None) == "chatgpt":
                    raise
                log.warn(f"model could not write the pitch, falling back: {exc}")

        from .agent import _offline_pitch
        draft = _offline_pitch({"current": {"domain": gig.get("company", ""),
                                            "meta": gig},
                                "profile": {"title": gig.get("company", ""),
                                            "description": _first_real_sentence(
                                                gig.get("description") or "")},
                                "contact": {}})
        draft["_fallback"] = "the local model was not available"
        return {"draft": draft,
                "log": f"template pitch for {gig.get('company','')}"}

    def n_approve_gig(self, s: dict) -> dict:
        gig, draft = s["gig"], s["draft"]
        package = s.get("package") or {}
        pkg = pkg_mod.Package.from_json(package) if package else None
        decision = require_approval(
            agent="fullstack_sales", thread_id=s["_thread_id"], kind="send_email" if contact_email(gig) else "send_message",
            title=f"Pitch {gig.get('company','')} - {gig.get('title','')}",
            payload={
                "company": gig.get("company", ""),
                "title": gig.get("title", ""),
                "location": gig.get("location", ""),
                "work_kind": gig.get("work_kind", "unknown"),
                "client_kind": gig.get("client_kind", "unknown"),
                "source": gig.get("source", ""),
                "to": contact_email(gig),
                "apply_url": gig.get("url", ""),
                "subject": draft["subject"], "body": draft["body"],
                "reads_as": draft.get("reads_as", ""),
                "likely_cause": draft.get("likely_cause", ""),
                "fallback": draft.get("_fallback", ""),
                "quote_tier": pkg.label if pkg else "priced by the day",
                "quote_ask": pkg.render() if pkg else "day rate",
                "quote_floor": pkg.money(pkg.floor) if pkg else "",
                "brain_score": gig.get("brain_score"),
                "stage": "opening",
            }, store=self.store)
        try:
            from core.reflect import learn_from_decision
            learn_from_decision("fullstack_sales", decision,
                                {"body": draft["body"]}, store=self.store,
                                llm=getattr(self, "llm", None), scope="pitch")
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not learn from that decision: {exc}")
        outcome = "pitch_approved" if decision.approved else "pitch_rejected"
        self.brain.record_deal({**gig, "package_id": (pkg.id if pkg else ""),
                                "currency": (pkg.currency if pkg else "")},
                               outcome, note=decision.note or "")
        return {"decision": decision.to_json(),
                "approved_draft": decision.apply_to(draft),
                "log": f"{outcome} for {gig.get('company','')}"}

    def r_after_gig_approve(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "send" if d.get("status") in ("approved", "edited") else "next"

    def n_send_gig(self, s: dict) -> dict:
        gig = s["gig"]
        delivery = deliver_reviewed(
            store=self.store, agent="fullstack_sales", thread_id=s["_thread_id"],
            target=gig, draft=s.get("approved_draft") or s["draft"],
            decision=s["decision"], mailer=self.mailer)
        if delivery["status"] == "blocked":
            return {"skipped": {"company": gig.get("company", ""),
                                "reason": delivery["reason"]}}
        package = s.get("package") or {}
        pkg = pkg_mod.Package.from_json(package) if package else None
        key = f"deal:{gig.get('source','')}:{gig.get('id','')}"
        self.store.kv_set("fullstack_sales", key, {
            "gig": gig, "package": package,
            "stage": "opening" if delivery["status"] == "contacted" else delivery["status"],
            "lead_id": delivery["lead_id"],
            "draft": s.get("approved_draft") or s["draft"],
            "created_at": time.time()})
        if delivery["status"] == "contacted":
            self.brain.record_deal({**gig, "package_id": (pkg.id if pkg else ""),
                                    "currency": (pkg.currency if pkg else "")}, "sent")
        return {"sent_gigs": [{"company": gig.get("company", ""),
                               "title": gig.get("title", ""),
                               "url": gig.get("url", "")}],
                "handoff": ({**delivery, "channel": "form", "route": delivery["url"]}
                            if delivery["status"] == "ready_to_send" else []),
                "stats": {delivery["status"]: 1},
                "log": f"{delivery['status']}: {gig.get('company','')}"}

    def r_more_gigs(self, s: dict) -> str:
        return "next" if s.get("gig_queue") else "done"

    # -- when they reply ---------------------------------------------------
    def handle_reply(self, gig: dict, message_text: str,
                     package_json: dict) -> dict:
        """Accept, counter, or stop. The floor is absolute."""
        from . import pitch_replies as replies
        pkg = pkg_mod.Package.from_json(package_json) if package_json else None
        if pkg is None:
            return {"action": "ask_operator", "needs_operator": True,
                    "reason": "this is a build, not a package - scope it first"}
        offer = pkg_mod.find_offer(message_text, pkg.currency)
        counter = pkg_mod.respond_to(offer, pkg)
        self.brain.record_deal({**gig, "package_id": pkg.id,
                                "currency": pkg.currency}, "replied")
        if counter.action == "hold":
            return {"action": "quote", "amount": pkg.ask,
                    "draft": replies.rate_reply(gig, pkg),
                    "needs_operator": pkg.missing}
        if counter.action == "accept":
            return {"action": "accept", "amount": counter.amount,
                    "draft": replies.rate_reply(gig, pkg),
                    "needs_operator": False, "reason": counter.reason}
        if counter.action == "counter":
            return {"action": "counter", "amount": counter.amount,
                    "draft": replies.counter_reply(gig, pkg, counter),
                    "needs_operator": False, "reason": counter.reason,
                    "give": counter.give}
        return {"action": "ask_operator", "amount": counter.amount,
                "draft": None, "needs_operator": True, "reason": counter.reason}
