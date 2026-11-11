"""Agent 3 - Full-Stack Development Sales.

Two graphs:

  outreach  - find prospects whose site suggests a build need, pitch, send
  quote     - when a prospect asks for a number, infer scope from their own
              words, price it deterministically from your rate card, draft a
              proposal, and STOP. The quote is never sent without your explicit
              approval, and you can edit the total at the gate.

This is the blueprint's human-in-the-loop requirement taken literally: an agent
should not commit you to a price.
"""
from __future__ import annotations

import textwrap

from agents.common import (OutreachAgent, OutreachConfig, ReplyAgent, ReplyConfig,
                           classify_intent)
from agents.fullstack_sales.gigs import DevGigMixin
from agents.fullstack_sales.pricing import Quote, build_quote, infer_scope, load_rate_card
from agents.templates import company_name, compose, greeting, observation, signature
from core import config
from core.graph import END, StateGraph, append
from core.hitl import require_approval
from core.llm import LLM, get_llm, offline_handler
from core.log import get_logger
from core.mailer import Mailer, OutgoingMessage, SendBlocked
from core.notify import get_notifier
from core.store import get_store, new_id, now

log = get_logger("fullstack_sales")

AGENT = "fullstack_sales"

SYSTEM = """You write B2B emails on behalf of a software engineer offering
web and backend development. You are technical, concise and concrete. You never
state a price unless one is supplied to you. You never promise a delivery date.
You never claim to have worked with companies you have not."""

PITCH_INSTRUCTION = """You are writing on behalf of {operator}, a software
engineer who builds web applications and backend services.

Reference something specific and technical about their current site - the stack
you detected, a page that is clearly dated, a missing capability - and be honest
that it is an outside observation. Ask one question about what they are trying
to build. Do not quote a price."""

SEARCH_QUERIES = [
    "small business website redesign needed",
    "startup looking for web developer india",
    "saas company outdated website",
    "company needs custom web application",
]

STACK_OPPORTUNITY = {
    "jQuery": "the front end is still on jQuery",
    "WordPress": "the site runs on WordPress",
    "Bootstrap": "the layout is on an older Bootstrap build",
    "Wix": "the site is on Wix, which caps what you can customise",
    "Squarespace": "the site is on Squarespace",
}


def qualify_bonus(site, state) -> tuple[float, str]:
    if site is None:
        return 0.0, ""
    tech = set(getattr(site, "tech", []) or [])
    modern = {"React", "Next.js", "Vue", "Angular", "Tailwind"}
    dated = set(STACK_OPPORTUNITY) & tech
    if dated:
        return 0.25, f"dated stack detected: {', '.join(sorted(dated))}"
    if tech & modern:
        return -0.05, "already on a modern stack - lower need"
    return 0.05, "stack not determined"


@offline_handler(f"pitch:{AGENT}")
def _offline_pitch(ctx: dict) -> dict:
    prof = ctx.get("profile") or {}
    contact = ctx.get("contact") or {}
    cur = ctx.get("current") or {}
    company = company_name(prof, cur.get("domain", "your company"),
                           preferred=cur.get("title", ""))
    obs = observation(prof)
    tech = prof.get("tech", []) or []
    dated = [STACK_OPPORTUNITY[t] for t in tech if t in STACK_OPPORTUNITY]

    opening = (f"I came across {company} - your site describes it as: \"{obs}\"."
               if obs else f"I came across {company}.")
    if dated:
        tech_note = (f"From the outside it looks like {dated[0]}. That is a guess "
                     f"from the page source, so tell me if I have it wrong.")
    else:
        tech_note = (f"I had a look at the site but could not tell much about the "
                     f"stack from the outside.")
    para = (f"I build web applications end to end - React or Next.js on the front, "
            f"an API and data model behind it, deployment and CI. I work solo, so "
            f"you deal with the person writing the code.")
    ask = ("Is there anything on your roadmap this quarter that needs building? "
           "Happy to give you a straight estimate if so.")
    return {
        "subject": f"A question about {company}'s site"[:88],
        "body": compose(greeting(contact), [opening, tech_note, para], ask),
        "personalisation_note": (dated[0] if dated else
                                 (f"site copy: {obs[:110]}" if obs else "no detail")),
        "confidence": 0.7 if dated else 0.45,
    }


@offline_handler(f"reply:{AGENT}")
def _offline_reply(ctx: dict) -> dict:
    msg = ctx.get("message") or {}
    intent = (ctx.get("intent") or {}).get("label", "other")
    name = (msg.get("from_name") or "").split(" ")[0]
    greet = f"Hi {name}," if name and name.isalpha() else "Hi there,"
    if intent == "interested":
        return {"body": compose(greet, [
            "Good to hear from you.",
            "To put a real number on this rather than a range, I need three "
            "things: roughly what the system has to do, whether anything has to "
            "integrate with what you already run, and when you need it live."],
            "If you can answer those, I'll send a scoped estimate within a day."),
            "subject": "", "needs_human": False,
            "next_step": "Await scope answers, then run the quote graph"}
    return {"body": compose(greet, ["Thanks for the reply.",
            "PLACEHOLDER: respond to their specific point."],
            "What would be most useful from here?"),
            "subject": "", "needs_human": True, "next_step": "Answer manually"}


PROPOSAL_SCHEMA = {
    "type": "object",
    "required": ["body"],
    "properties": {
        "body": {"type": "string", "min_length": 100, "max_length": 3000},
        "subject": {"type": "string", "max_length": 120, "default": ""},
    },
}


@offline_handler("proposal:fullstack_sales")
def _offline_proposal(ctx: dict) -> dict:
    quote: Quote = ctx["quote"]
    msg = ctx.get("message") or {}
    name = (msg.get("from_name") or "").split(" ")[0]
    greet = f"Hi {name}," if name and name.isalpha() else "Hi there,"

    parts = [greet, "",
             "Here is a scoped estimate based on what you described.", "",
             "SCOPE"]
    parts += [f"  - {l.label} ({l.days:g} days)" for l in quote.lines]
    parts += ["", "ESTIMATE", quote.render(), "",
              textwrap.fill(
                  f"That is {quote.total_days:g} working days of build time, plus "
                  f"a 15% contingency for the things that always surface "
                  f"mid-project. It is an estimate, not a fixed-price bid - if "
                  f"the scope moves the number moves, and I will tell you before "
                  f"it does.", width=78),
              "", "ASSUMPTIONS"]
    parts += [f"  - {a}" for a in (quote.assumptions or ["None recorded."])]
    parts += ["",
              textwrap.fill(
                  "If the shape is roughly right, the next step is a 30-minute "
                  "call to pin down the details, after which I can turn this "
                  "into a fixed statement of work.", width=78),
              "", signature()]
    return {"body": "\n".join(parts),
            "subject": f"Estimate: {quote.currency} {quote.total:,.0f}"}


class QuoteAgent:
    """Scope -> price -> proposal -> mandatory human approval -> send."""

    def __init__(self, store=None, llm: LLM | None = None, mailer=None, notifier=None):
        self.store = store or get_store()
        self.llm = llm or get_llm(self.store)
        self.mailer = mailer or Mailer(self.store)
        self.notifier = notifier or get_notifier(self.store)

    def n_analyse(self, s: dict) -> dict:
        msg = s["message"]
        lead = self.store.one(
            "SELECT * FROM leads WHERE agent=? AND email=? ORDER BY created_at DESC "
            "LIMIT 1", (AGENT, (msg.get("from_addr") or "").lower()))
        corpus = " ".join([msg.get("reply_text", ""), msg.get("subject", ""),
                           s.get("site_text", "")])
        scope, mods = infer_scope(corpus)
        return {"lead": lead, "scope": scope, "modifiers": mods,
                "log": f"scope={scope} modifiers={mods}"}

    def r_have_scope(self, s: dict) -> str:
        return "price" if s.get("scope") else "ask"

    def n_ask_scope(self, s: dict) -> dict:
        """Refuse to guess. An estimate from nothing is worse than no estimate."""
        return {"outcome": "insufficient_scope",
                "log": "not enough detail to price - asking the prospect instead"}

    def n_price(self, s: dict) -> dict:
        assumptions = [
            "Assumes you supply copy, brand assets and any third-party accounts.",
            "Assumes a single production environment and one round of revisions "
            "per milestone.",
        ]
        q = build_quote(s["scope"], modifiers=s.get("modifiers"),
                        assumptions=assumptions)
        log.info("quote computed", total=q.total, currency=q.currency,
                 days=q.total_days)
        return {"__quote": q, "quote_json": q.to_json(),
                "log": f"priced at {q.currency} {q.total:,.0f}"}

    @staticmethod
    def _quote(s: dict) -> Quote:
        """The live Quote if this pass built it, otherwise rebuilt from state."""
        q = s.get("__quote")
        return q if isinstance(q, Quote) else Quote.from_json(s["quote_json"])

    def n_draft_proposal(self, s: dict) -> dict:
        q = self._quote(s)
        prompt = textwrap.dedent(f"""
            Write the covering email for this estimate. The numbers below are
            fixed and computed - reproduce them exactly, do not recalculate,
            round or renegotiate them.

            {q.render()}

            Scope: {', '.join(l.label for l in q.lines)}
            Total build days: {q.total_days:g}
            Assumptions: {'; '.join(q.assumptions)}

            What they told us:
            ---
            {(s['message'].get('reply_text') or '')[:2000]}
            ---

            Be direct. State that it is an estimate and what would change it.
            End with one concrete next step.
        """).strip()
        draft = self.llm.structured(
            prompt, PROPOSAL_SCHEMA, task="proposal:fullstack_sales",
            context={"quote": q, "message": s["message"], "state": s},
            system=SYSTEM, temperature=0.3, max_tokens=1600)
        return {"proposal": draft, "log": "proposal drafted"}

    def n_approve_quote(self, s: dict) -> dict:
        """The gate. Nothing priced leaves the machine without a decision."""
        q = self._quote(s)
        msg = s["message"]
        decision = require_approval(
            agent=AGENT, thread_id=s["_thread_id"], kind="send_quote",
            title=f"QUOTE {q.currency} {q.total:,.0f} to {msg.get('from_addr')}",
            payload={"to": msg.get("from_addr"),
                     "subject": s["proposal"].get("subject", "Estimate"),
                     "body": s["proposal"]["body"],
                     "quote": q.to_json(),
                     "breakdown": q.render(),
                     "scope": s["scope"], "modifiers": s.get("modifiers", []),
                     "editable": ["subject", "body", "total"],
                     "their_message": (msg.get("reply_text") or "")[:1500]},
            store=self.store)
        if not decision.approved:
            return {"decision": decision.to_json(), "outcome": "quote_rejected",
                    "log": f"operator rejected the quote: {decision.note}"}
        edits = decision.edits or {}
        final = {"subject": edits.get("subject", s["proposal"].get("subject", "Estimate")),
                 "body": edits.get("body", s["proposal"]["body"])}
        if "total" in edits:
            new_total = float(edits["total"])
            old = q.total
            final["body"] = final["body"].replace(f"{old:,.0f}", f"{new_total:,.0f}")
            final["subject"] = f"Estimate: {q.currency} {new_total:,.0f}"
            log.info("operator overrode the quote total", was=old, now=new_total)
        return {"decision": decision.to_json(), "final_quote": final,
                "final_total": float(edits.get("total", q.total))}

    def r_after_approve(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "send" if d.get("status") in ("approved", "edited") else "end"

    def n_send(self, s: dict) -> dict:
        msg = s["message"]
        final = s["final_quote"]
        out = OutgoingMessage(
            to=msg.get("from_addr", ""), subject=final["subject"],
            body=final["body"], in_reply_to=msg.get("rfc_message_id", ""),
            references=msg.get("references", ""),
            gmail_thread_id=msg.get("thread_id", ""), tag=AGENT,
            include_footer=False)
        try:
            result = self.mailer.send(out, enforce_cap=False)
        except SendBlocked as exc:
            return {"outcome": f"blocked: {exc}", "log": str(exc)}
        self.mailer.record(s["_thread_id"], AGENT, "out", out, result)
        lead = s.get("lead") or {}
        if lead.get("id"):
            self.store.run("UPDATE leads SET status=?, updated_at=? WHERE id=?",
                           ("quoted", now(), lead["id"]))
        self.store.event("quote_sent", AGENT, s["_thread_id"],
                         total=s.get("final_total"), to=msg.get("from_addr"))
        return {"outcome": "quote_sent", "log": "quote sent"}

    def n_won(self, s: dict) -> dict:
        """Terminal celebration node, reached when a reply is classified as accept."""
        lead = s.get("lead") or {}
        total = s.get("final_total") or (s.get("quote_json") or {}).get("total")
        self.notifier.send(
            f"Deal closed - {lead.get('company') or s['message'].get('from_addr')}",
            f"They accepted. Value: {total}. Onboarding is yours from here.",
            priority="urgent", tags=("tada",))
        if lead.get("id"):
            self.store.run("UPDATE leads SET status=?, updated_at=? WHERE id=?",
                           ("closed_won", now(), lead["id"]))
        return {"outcome": "closed_won"}

    def build(self):
        g = StateGraph(reducers={"log": append})
        g.add_node("analyse", self.n_analyse)
        g.add_node("ask_scope", self.n_ask_scope)
        g.add_node("price", self.n_price)
        g.add_node("draft_proposal", self.n_draft_proposal, retries=1)
        g.add_node("approve_quote", self.n_approve_quote)
        g.add_node("send", self.n_send)
        g.set_entry_point("analyse")
        g.add_conditional_edges("analyse", self.r_have_scope,
                                {"price": "price", "ask": "ask_scope"})
        g.add_edge("ask_scope", END)
        g.add_edge("price", "draft_proposal")
        g.add_edge("draft_proposal", "approve_quote")
        g.add_conditional_edges("approve_quote", self.r_after_approve,
                                {"send": "send", "end": END})
        g.add_edge("send", END)
        return g.compile(store=self.store, name=f"{AGENT}_quote")

    def handle(self, message: dict, site_text: str = "", thread_id: str | None = None,
               **kw):
        tid = thread_id or f"{AGENT}-quote-{message.get('id') or new_id()}"
        return self.build().invoke(
            {"message": message, "site_text": site_text, "_thread_id": tid},
            thread_id=tid, **kw)


def build_config() -> OutreachConfig:
    return OutreachConfig(
        agent=AGENT, search_queries=SEARCH_QUERIES,
        seed_category=config.get("FULLSTACK_CATEGORY") or None,
        looking_for="the founder, CTO or whoever owns the website",
        system_prompt=SYSTEM,
        pitch_instruction=PITCH_INSTRUCTION.format(
            operator=config.get("OPERATOR_NAME", "Vineet")),
        min_score=config.get_float("FULLSTACK_MIN_SCORE", 0.35),
        max_leads_per_run=config.get_int("FULLSTACK_MAX_LEADS", 10),
        qualify_fn=qualify_bonus)


def build_reply_config() -> ReplyConfig:
    return ReplyConfig(
        agent=AGENT, system_prompt=SYSTEM,
        reply_instruction=(
            "You are replying as a freelance software engineer. Never state a "
            "price, a day rate or a delivery date in this reply - pricing is "
            "handled by a separate approved quote. Ask for the scope details "
            "needed to produce one."))


class DevSalesAgent(DevGigMixin, OutreachAgent):
    """Answering people who want work done, and cold outreach, in one graph.

    Same structure as the video client agent, and for the same reason: finding
    a client and pitching one are the same judgement made twice, so they have
    to share a memory or neither half gets better.
    """

    def run(self, thread_id: str | None = None, **kw):
        import time as _time
        tid = thread_id or f"fullstack_sales-{_time.strftime('%Y%m%d-%H%M%S')}"
        state = {"_thread_id": tid}
        for key in ("sweep", "only_sources"):
            if kw.get(key) is not None:
                state[key] = kw.pop(key)
        return self.build().invoke(state, thread_id=tid, **kw)

    def build(self, recursion_limit: int = 400):
        from agents.common import outreach_reducers
        from core.graph import END, StateGraph
        g = StateGraph(reducers=outreach_reducers())

        # phase one: people already asking for development work
        g.add_node("sweep", self.n_sweep, retries=1)
        g.add_node("pick_gig", self.n_pick_gig)
        g.add_node("read_gig", self.n_read_gig, retries=1, backoff=2)
        g.add_node("skip_gig", self.n_skip_gig)
        g.add_node("pitch_gig", self.n_pitch_gig)
        g.add_node("approve_gig", self.n_approve_gig)
        g.add_node("send_gig", self.n_send_gig)
        g.add_node("more_gigs", lambda s: None)

        # phase two: cold outreach, unchanged
        g.add_node("discover", self.n_discover, retries=1)
        g.add_node("pick_lead", self.n_pick_lead)
        g.add_node("research", self.n_research, retries=1, backoff=2)
        g.add_node("qualify", self.n_qualify)
        g.add_node("skip", self.n_skip)
        g.add_node("draft", self.n_draft, retries=1)
        g.add_node("approve", self.n_approve)
        g.add_node("send", self.n_send)
        g.add_node("more", lambda s: None)
        g.add_node("done", self.n_done)

        g.set_entry_point("sweep")
        g.add_conditional_edges(
            "sweep", lambda s: "gigs" if s.get("gig_queue") else "cold",
            {"gigs": "pick_gig", "cold": "discover"})
        g.add_conditional_edges(
            "pick_gig", lambda s: "go" if s.get("gig") else "cold",
            {"go": "read_gig", "cold": "discover"})
        g.add_conditional_edges("read_gig", self.r_after_read,
                                {"pitch": "pitch_gig", "skip": "skip_gig"})
        g.add_conditional_edges("skip_gig", self.r_more_gigs,
                                {"next": "pick_gig", "done": "discover"})
        g.add_edge("pitch_gig", "approve_gig")
        g.add_conditional_edges("approve_gig", self.r_after_gig_approve,
                                {"send": "send_gig", "next": "more_gigs"})
        g.add_conditional_edges("more_gigs", self.r_more_gigs,
                                {"next": "pick_gig", "done": "discover"})
        g.add_conditional_edges("send_gig", self.r_more_gigs,
                                {"next": "pick_gig", "done": "discover"})

        g.add_conditional_edges(
            "discover", lambda s: "next" if s.get("leads_queue") else "done",
            {"next": "pick_lead", "done": "done"})
        g.add_conditional_edges(
            "pick_lead", lambda s: "go" if s.get("current") else "done",
            {"go": "research", "done": "done"})
        g.add_edge("research", "qualify")
        g.add_conditional_edges("qualify", self.r_after_qualify,
                                {"draft": "draft", "skip": "skip"})
        g.add_conditional_edges("skip", self.r_more,
                                {"next": "pick_lead", "done": "done"})
        g.add_edge("draft", "approve")
        g.add_conditional_edges("approve", self.r_after_approve,
                                {"send": "send", "next": "more"})
        g.add_conditional_edges("more", self.r_more,
                                {"next": "pick_lead", "done": "done"})
        g.add_conditional_edges("send", self.r_more,
                                {"next": "pick_lead", "done": "done"})
        g.add_edge("done", END)
        return g.compile(store=self.store, name=self.cfg.agent,
                         recursion_limit=recursion_limit)


def make(store=None, **kw) -> DevSalesAgent:
    return DevSalesAgent(build_config(), store=store, **kw)


def make_reply(store=None, **kw) -> ReplyAgent:
    from agents.sales_conversation import SalesReplyAgent
    return SalesReplyAgent(build_reply_config(), store=store, **kw)


def make_quote(store=None, **kw) -> QuoteAgent:
    return QuoteAgent(store=store, **kw)
