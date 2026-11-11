"""Agent 5 - taking the SaaS product to the people who would use and promote it.

The other four sell something that exists. This one is a launch agent for a
product that does not exist yet, which changes what it is for: today its job is
to build a waitlist, collect feedback from people who edit for a living, and
warm up the creators who might eventually recommend it. When product.yaml's
stage moves to `live`, the same graph starts selling without a line changing.

Every message passes product.check_claims() before it reaches him, and the send
node refuses to run while that returns anything. The stage is a gate, not a
guideline.
"""
from __future__ import annotations

import time

from core import config
from core.graph import END, StateGraph, append, merge_dict
from core.hitl import require_approval
from core.llm import LLM, get_llm
from core.log import get_logger
from core.store import get_store, new_id, now

from . import brief as brief_mod
from . import product as prod
from . import sources as src
from .brain import LaunchMemory

log = get_logger("saas_sales")

AGENT = "saas_sales"


def reducers() -> dict:
    return {"sent": append, "skipped": append, "handoff": append,
            "submissions": append, "stats": merge_dict}


class SaasSalesAgent:
    """Find them, read them, write to them, and never overclaim."""

    def __init__(self, store=None, llm: LLM | None = None, notifier=None):
        self.store = store or get_store()
        self.llm = llm or get_llm(self.store)
        self._brain = None
        self._notifier = notifier

    @property
    def brain(self) -> LaunchMemory:
        if self._brain is None:
            self._brain = LaunchMemory(self.store)
        return self._brain

    def _say(self, text: str) -> None:
        try:
            from core.notify import get_notifier
            (self._notifier or get_notifier(self.store)).send(
                "Product launch", text, tags=(AGENT,))
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not post progress: {exc}")

    # -- nodes -------------------------------------------------------------
    def n_check_product(self, s: dict) -> dict:
        """Refuse to run at all rather than send something half-true.

        Two gates. SAAS_ENABLED is his switch - the agent is finished and
        parked until he says the product is ready, and a parked agent that
        still ran every night would be the whole problem this agent was built
        to avoid. ready_to_sell() is the second gate, for when it is switched
        on but the profile is still half-empty.
        """
        if not config.get_bool("SAAS_ENABLED", False):
            why = ("parked - the product is not ready yet. Turn it on with "
                   "SAAS_ENABLED=true in .env once profiles/product.yaml is "
                   "filled in and the stage is past `building`.")
            return {"ready": False, "blocked_reason": why, "log": "parked"}
        ok, why = prod.ready_to_sell()
        if not ok:
            self._say(f"Not running: {why}")
        return {"ready": ok, "blocked_reason": why,
                "log": "ready" if ok else f"blocked: {why}"}

    def r_ready(self, s: dict) -> str:
        return "go" if s.get("ready") else "stop"

    def n_sweep(self, s: dict) -> dict:
        if s.get("queue"):
            return {}
        names = s.get("only_sources") or config.get_list(
            "SAAS_SOURCES", ["youtube", "directories"])
        self._say(f"Looking for people to tell about it, on {len(names)} "
                  f"sources. This takes a minute.")
        found = src.find_targets(names)
        fresh, seen_before = [], 0
        for t in found:
            if not self.store.mark_seen(f"{AGENT}:target", t.key()):
                seen_before += 1
                continue
            row = t.to_json()
            row["brain_score"] = round(self.brain.score_target(row)[0], 4)
            fresh.append(row)
        # Directories first: they cost nothing, they work before launch, and
        # they are the only channel here that does not spend goodwill.
        order = {"directory": 0, "promoter": 1, "agency": 2, "user": 3}
        fresh.sort(key=lambda r: (order.get(r["kind"], 9), -r["brain_score"]))
        cap = config.get_int("SAAS_MAX_PER_RUN", 12)
        self._say(f"Found {len(found)}, {len(fresh)} new. "
                  f"Showing the best {min(cap, len(fresh))}.")
        return {"queue": fresh[:cap],
                "stats": {"found": len(found), "already_seen": seen_before,
                          "queued": len(fresh[:cap])}}

    def n_pick(self, s: dict) -> dict:
        q = list(s.get("queue") or [])
        if not q:
            return {"target": None}
        return {"target": q.pop(0), "queue": q, "about": None, "draft": None}

    def n_read(self, s: dict) -> dict:
        """Read what they say about themselves, and drop the competitors."""
        target = dict(s["target"])
        if target.get("kind") == "directory":
            return {"target": target, "about": {}}
        t = src.Target(**{k: v for k, v in target.items()
                          if k in src.Target.__dataclass_fields__})
        about = src.channel_about(t)
        desc = about.get("description", "")
        rival = src.is_competitor(target.get("name", ""), desc, target.get("url", ""))
        if rival:
            # Telling a competing plugin exactly what is coming is not outreach.
            target["rejected"] = f"this is {rival}, a competing tool"
        else:
            target["kind"] = src.classify(target.get("name", ""), desc)
        target["subscribers"] = about.get("subscribers", "")
        target["has_email"] = bool(about.get("email"))
        target["contact"] = about.get("email", "")
        return {"target": target, "about": about,
                "log": f"read {target.get('name','')} -> {target.get('kind','')}"}

    def r_after_read(self, s: dict) -> str:
        return "skip" if (s.get("target") or {}).get("rejected") else "write"

    def n_skip(self, s: dict) -> dict:
        t = s["target"]
        return {"skipped": [{"name": t.get("name", ""),
                             "reason": t.get("rejected", "")}],
                "stats": {"skipped": 1},
                "log": f"skipped {t.get('name','')}: {t.get('rejected','')}"}

    def n_write(self, s: dict) -> dict:
        target, about = s["target"], s.get("about") or {}
        if target.get("kind") == "directory":
            return {"draft": self._directory_card(target)}

        from core.lessons import get_lessons
        from core.llm import LLMError
        if not self.llm.is_offline:
            prompt = brief_mod.build_prompt({"target": target, "about": about})
            learned = get_lessons(AGENT, self.store).prompt_block(
                context=f"{target.get('name','')} {target.get('kind','')}",
                scope="pitch")
            if learned:
                prompt = f"{prompt}\n\n{learned}"
            try:
                draft = self.llm.structured(
                    prompt, brief_mod.PITCH_SCHEMA, task=f"pitch:{AGENT}",
                    context={"target": target, "about": about},
                    system="You write short, honest emails about a product "
                           "that is still being built. You never overclaim, "
                           "and you say plainly that it is unfinished.",
                    temperature=0.4,
                    max_tokens=config.get_int("PITCH_MAX_TOKENS", 1200))
                draft = brief_mod.finish(draft, {"target": target})
                return {"draft": draft,
                        "log": f"model wrote to {target.get('name','')}"}
            except (LLMError, Exception) as exc:  # noqa: BLE001
                if getattr(self.llm, "provider_name", None) == "chatgpt":
                    raise
                log.warn(f"model could not write, falling back: {exc}")

        return {"draft": self._plain_note(target, about),
                "log": f"template note for {target.get('name','')}"}

    def _plain_note(self, target: dict, about: dict) -> dict:
        """No model. Deliberately spare - every sentence is from product.yaml."""
        p = prod.load_product()
        does = (p.get("does") or ["automates repetitive editing passes"])[0]
        name = p.get("name") or "a tool"
        body = (f"Hi,\n\nI found your channel through your work on video "
                f"editing.\n\nI am building {name} - it {str(does)[0].lower()}"
                f"{str(does)[1:]}. It is not finished yet, so there is nothing "
                f"to try and nothing to buy.\n\nWould you want to be told when "
                f"it is ready, and would you be willing to look at it early "
                f"and tell me what is wrong with it?")
        draft = {"reads_as": f"{target.get('name','')} - "
                             f"{target.get('evidence','')}",
                 "subject": f"Something I am building for editors"[:88],
                 "body": body, "personalisation_note": "written without a model",
                 "_fallback": "the local model was not available"}
        return brief_mod.finish(draft, {"target": target})

    def _directory_card(self, target: dict) -> dict:
        """A submission, not an email. He does this one by hand."""
        p = prod.load_product()
        blurb = (p.get("tagline") or
                 "; ".join(str(d) for d in (p.get("does") or [])[:3]))
        return {"reads_as": target.get("evidence", ""),
                "subject": f"Submit to {target.get('name','')}",
                "body": (f"Submission, not an email - open the link and paste "
                         f"this.\n\nName: {p.get('name') or '(unnamed)'}\n"
                         f"One line: {blurb}\n"
                         f"Cost: {target.get('where','')}\n"
                         f"Note: {target.get('evidence','')}"),
                "claim_problems": [], "is_submission": True}

    def n_approve(self, s: dict) -> dict:
        target, draft = s["target"], s["draft"]
        problems = draft.get("claim_problems") or []
        decision = require_approval(
            agent=AGENT, thread_id=s["_thread_id"],
            kind="submit_listing" if draft.get("is_submission") else "send_email",
            title=f"{'Submit to' if draft.get('is_submission') else 'Write to'} "
                  f"{target.get('name','')}",
            payload={
                "company": target.get("name", ""),
                "title": target.get("kind", ""),
                "audience": target.get("kind", ""),
                "subscribers": target.get("subscribers", ""),
                "apply_url": target.get("url", ""),
                "to": target.get("contact", ""),
                "source": target.get("source", ""),
                "evidence": target.get("evidence", ""),
                "subject": draft.get("subject", ""),
                "body": draft.get("body", ""),
                "reads_as": draft.get("reads_as", ""),
                "fallback": draft.get("_fallback", ""),
                "stage": prod.stage(),
                "claim_problems": problems,
                "brain_score": target.get("brain_score"),
            }, store=self.store)
        try:
            from core.reflect import learn_from_decision
            learn_from_decision(AGENT, decision, {"body": draft.get("body", "")},
                                store=self.store, llm=self.llm, scope="pitch")
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not learn from that decision: {exc}")
        self.brain.record_target(
            target, "pitch_approved" if decision.approved else "pitch_rejected",
            note=decision.note or "")
        final = decision.apply_to(draft)
        final["claim_problems"] = ([] if draft.get("is_submission") else
                                   prod.check_claims(final.get("body", "")))
        return {"decision": decision.to_json(), "draft": final,
                "log": f"{decision.status} for {target.get('name','')}"}

    def r_after_approve(self, s: dict) -> str:
        d = s.get("decision") or {}
        if d.get("status") not in ("approved", "edited"):
            return "next"
        # The gate. Approval does not override it - he can approve a draft
        # without reading every line, and the whole point of the gate is that
        # it catches what a tired reader would not.
        if (s.get("draft") or {}).get("claim_problems"):
            return "blocked"
        return "send"

    def n_blocked(self, s: dict) -> dict:
        target, draft = s["target"], s["draft"]
        problems = draft.get("claim_problems") or []
        self._say(f"Held back the message to {target.get('name','')} - it "
                  f"claims something the product cannot back yet:\n"
                  + "\n".join(f"- {p}" for p in problems))
        return {"skipped": [{"name": target.get("name", ""),
                             "reason": "; ".join(str(p) for p in problems)}],
                "stats": {"blocked": 1},
                "log": f"BLOCKED {target.get('name','')}: {problems}"}

    def n_send(self, s: dict) -> dict:
        target, draft = s["target"], s["draft"]
        from core.delivery import deliver_reviewed
        route_target = dict(target)
        if draft.get("is_submission"):
            route_target["contact"] = ""
        delivery = deliver_reviewed(store=self.store, agent=AGENT,
                                    thread_id=s["_thread_id"], target=route_target,
                                    draft=draft, decision=s["decision"])
        if delivery["status"] == "contacted":
            self.brain.record_target(target, "sent")
        return {"sent": [delivery] if delivery["status"] == "contacted" else [],
                "handoff": ({**delivery, "channel": "form", "route": delivery["url"]}
                            if delivery["status"] == "ready_to_send" else []),
                "stats": {delivery["status"]: 1},
                "log": f"{delivery['status']}: {target.get('name','')}"}

    def r_more(self, s: dict) -> str:
        return "next" if s.get("queue") else "done"

    def n_done(self, s: dict) -> dict:
        self.store.kv_set(AGENT, "last_run", time.time())
        return {"summary": s.get("stats", {})}

    # -- graph -------------------------------------------------------------
    def build(self, recursion_limit: int = 400):
        g = StateGraph(reducers=reducers())
        g.add_node("check", self.n_check_product)
        g.add_node("sweep", self.n_sweep, retries=1)
        g.add_node("pick", self.n_pick)
        g.add_node("read", self.n_read, retries=1, backoff=2)
        g.add_node("skip", self.n_skip)
        g.add_node("write", self.n_write, retries=1)
        g.add_node("approve", self.n_approve)
        g.add_node("blocked", self.n_blocked)
        g.add_node("send", self.n_send)
        g.add_node("more", lambda s: None)
        g.add_node("done", self.n_done)

        g.set_entry_point("check")
        g.add_conditional_edges("check", self.r_ready,
                                {"go": "sweep", "stop": "done"})
        g.add_conditional_edges(
            "sweep", lambda s: "go" if s.get("queue") else "done",
            {"go": "pick", "done": "done"})
        g.add_conditional_edges(
            "pick", lambda s: "go" if s.get("target") else "done",
            {"go": "read", "done": "done"})
        g.add_conditional_edges("read", self.r_after_read,
                                {"write": "write", "skip": "skip"})
        g.add_conditional_edges("skip", self.r_more,
                                {"next": "pick", "done": "done"})
        g.add_edge("write", "approve")
        g.add_conditional_edges("approve", self.r_after_approve,
                                {"send": "send", "blocked": "blocked",
                                 "next": "more"})
        g.add_conditional_edges("blocked", self.r_more,
                                {"next": "pick", "done": "done"})
        g.add_conditional_edges("more", self.r_more,
                                {"next": "pick", "done": "done"})
        g.add_conditional_edges("send", self.r_more,
                                {"next": "pick", "done": "done"})
        g.add_edge("done", END)
        return g.compile(store=self.store, name=AGENT,
                         recursion_limit=recursion_limit)

    def run(self, thread_id: str | None = None, **kw):
        tid = thread_id or f"{AGENT}-{time.strftime('%Y%m%d-%H%M%S')}"
        state = {"_thread_id": tid}
        for key in ("only_sources",):
            if kw.get(key) is not None:
                state[key] = kw.pop(key)
        return self.build().invoke(state, thread_id=tid, **kw)


def make(store=None, **kw) -> SaasSalesAgent:
    return SaasSalesAgent(store=store, **kw)
