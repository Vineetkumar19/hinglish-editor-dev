"""Agent 2 - Video Editing Client Acquisition.

Finds creators who publish regularly and plausibly need an editor, works out who
to write to, and sends a short pitch that points at your portfolio. When someone
replies asking for samples or rates, the reply engine drafts the follow-up and
attaches the portfolio link - still behind your approval.

The portfolio link comes from PORTFOLIO_URL (a Google Drive folder works fine).
Rates are never quoted automatically; see `rates.yaml`.
"""
from __future__ import annotations

import pathlib
import re
import textwrap

from agents.common import OutreachAgent, OutreachConfig, ReplyAgent, ReplyConfig
from agents.video_client.gigs import GigMixin
from agents.templates import company_name, compose, greeting, observation, signature
from core import config
from core.llm import offline_handler
from core.log import get_logger
from core.yamlite import load_yaml

log = get_logger("video_client")

AGENT = "video_client"

SYSTEM = """You write short, concrete emails offering video editing services to
content creators. You are a working editor, not a marketing agency: you describe
what you actually do, you never claim to have watched videos you have not, and
you never promise growth, views or subscribers. You do not quote prices unless
they are given to you explicitly."""

PITCH_INSTRUCTION = """You are writing on behalf of {operator}, a video editor
who works in Premiere Pro and After Effects: motion graphics, colour grading in
DaVinci Resolve, and sound design.

The goal is a reply. Offer to send samples; do not attach or promise a rate.
If their site shows how often they publish or what format they make, reference
that specifically. Otherwise keep the opening factual and brief."""

SEARCH_QUERIES = [
    "youtube creator hire video editor",
    "cricket youtube channel editing help",
    "content creator looking for editor india",
    "podcast channel video editing outsource",
]

# Signals that a creator plausibly needs an editor.
NEED_SIGNALS = [
    (r"\b(looking for|hiring|need|want)\s+(an?\s+)?(video\s+)?editor\b", 0.30,
     "explicitly looking for an editor"),
    (r"\b(editing (everything|it all) myself|edit(ing)? my own)\b", 0.25,
     "says they edit everything themselves"),
    (r"\b(twice|three times|\d+\s*(videos?|episodes?))\s*(a|per)\s*week\b", 0.15,
     "publishes on a regular, demanding schedule"),
    (r"\b(work with me|collaborat|hire me|join the team|careers)\b", 0.08,
     "has a work-with-me page"),
    (r"\b(podcast|youtube|shorts|reels|vlog)\b", 0.05, "publishes video content"),
]


def rates_path() -> pathlib.Path:
    return pathlib.Path(config.get("VIDEO_RATES_FILE",
                                   str(config.ROOT / "profiles" / "video_rates.yaml")))


def load_rates() -> dict:
    p = rates_path()
    if not p.exists():
        return {}
    try:
        return load_yaml(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        log.warn(f"could not read {p}: {exc}")
        return {}


def qualify_bonus(site, state) -> tuple[float, str]:
    if site is None:
        return 0.0, ""
    text = (site.combined_text or "").lower()
    total, notes = 0.0, []
    for pattern, weight, why in NEED_SIGNALS:
        if re.search(pattern, text, re.I):
            total += weight
            notes.append(why)
    if not notes:
        return 0.0, "no signal that they need an editor"
    return min(0.35, total), notes[0]


@offline_handler(f"pitch:{AGENT}")
def _offline_pitch(ctx: dict) -> dict:
    prof = ctx.get("profile") or {}
    contact = ctx.get("contact") or {}
    cur = ctx.get("current") or {}
    state = ctx.get("state") or {}
    operator = config.get("OPERATOR_NAME", "Vineet")
    portfolio = config.get("PORTFOLIO_URL", "")
    company = company_name(prof, cur.get("domain", "your channel"),
                           preferred=cur.get("title", ""))
    obs = observation(prof)
    why = ((state.get("qualify") or {}).get("reasons") or [""])[-1]

    opening = (f"I found {company} - your site says: \"{obs}\"."
               if obs else f"I came across {company}.")
    if why and "edit" in why.lower():
        opening += f" It also reads like you're {why}."
    para2 = (f"I edit long-form and short-form video: Premiere Pro for the cut, "
             f"After Effects for motion graphics, DaVinci Resolve for the grade, "
             f"and I do my own sound design. I work on cricket and sports content "
             f"mostly, so the pacing conventions are familiar.")
    ask = ("Would it help if I sent two or three samples in the format you "
           "publish, so you can see whether the style fits?")
    return {
        "subject": f"Editing help for {company}?"[:88],
        "body": compose(greeting(contact), [opening, para2], ask),
        "personalisation_note": why or (f"Opened on their site copy: {obs[:110]}"
                                        if obs else "no specific detail found"),
        "confidence": 0.7 if (obs and why) else 0.45,
    }


@offline_handler(f"reply:{AGENT}")
def _offline_reply(ctx: dict) -> dict:
    intent = (ctx.get("intent") or {}).get("label", "other")
    asked = ((ctx.get("intent") or {}).get("asked_for") or "").lower()
    msg = ctx.get("message") or {}
    name = (msg.get("from_name") or "").split(" ")[0]
    greet = f"Hi {name}," if name and name.isalpha() else "Hi there,"
    portfolio = config.get("PORTFOLIO_URL", "")
    rates = load_rates()

    wants_portfolio = any(w in (asked + " " + (msg.get("reply_text") or "")).lower()
                          for w in ("sample", "portfolio", "reel", "example",
                                    "previous work", "showreel"))
    wants_price = any(w in (asked + " " + (msg.get("reply_text") or "")).lower()
                      for w in ("rate", "price", "cost", "charge", "quote", "budget"))

    paras, needs_human, next_step = [], False, ""
    if wants_portfolio:
        if portfolio:
            paras.append(f"Here's a folder with recent work: {portfolio}. The first "
                         f"two are closest to what you publish.")
        else:
            paras.append("PLACEHOLDER: portfolio link. Set PORTFOLIO_URL in .env so "
                         "this fills in automatically.")
            needs_human = True
            next_step = "Set PORTFOLIO_URL"
    if wants_price:
        # One reader for the rate card, the same one the gig half uses. This
        # used to read a flat `tiers:` list; the card now has a currency per
        # market, and two readers of one file is how they drift apart.
        from .quote import build_quote, currency_for
        text = f"{asked} {msg.get('reply_text') or ''}"
        quote = build_quote(text, currency=currency_for(
            f"{text} {msg.get('from_email') or ''}"))
        if not quote.missing:
            paras.append(f"On rates, {quote.tier_name.lower()} is "
                         f"{quote.render()}. Final number depends on runtime "
                         f"and turnaround, so tell me roughly what you need "
                         f"and I'll be specific.")
        else:
            paras.append("PLACEHOLDER: rates. Fill in profiles/video_rates.yaml so "
                         "the agent can quote your real numbers rather than guessing.")
            needs_human = True
            next_step = "Fill in profiles/video_rates.yaml"
    if not paras:
        paras.append("Thanks for getting back to me.")
        paras.append("PLACEHOLDER: answer their specific point.")
        needs_human = True
        next_step = "Answer manually"

    ask = ("What's your typical video length and how fast do you need turnaround? "
           "That'll let me give you an exact number.")
    return {"body": compose(greet, paras, ask), "subject": "",
            "needs_human": needs_human, "next_step": next_step}


def portfolio_attachments(state: dict) -> list:
    """No attachments on first contact - a link keeps you out of the spam folder."""
    return []


def build_config() -> OutreachConfig:
    return OutreachConfig(
        agent=AGENT,
        search_queries=SEARCH_QUERIES,
        seed_category=config.get("VIDEO_CLIENT_CATEGORY") or None,
        looking_for="the creator themselves, or whoever handles business enquiries",
        system_prompt=SYSTEM,
        pitch_instruction=PITCH_INSTRUCTION.format(
            operator=config.get("OPERATOR_NAME", "Vineet")),
        min_score=config.get_float("VIDEO_CLIENT_MIN_SCORE", 0.35),
        max_leads_per_run=config.get_int("VIDEO_CLIENT_MAX_LEADS", 10),
        qualify_fn=qualify_bonus,
        attachments_fn=portfolio_attachments,
    )


def build_reply_config() -> ReplyConfig:
    return ReplyConfig(
        agent=AGENT, system_prompt=SYSTEM,
        reply_instruction=(
            "You are replying as a freelance video editor. If they ask for "
            "samples, share the portfolio link you were given and nothing else. "
            "If they ask about price, use only the tiers in the rate card you "
            "were given; if there is no rate card, say PLACEHOLDER and set "
            "needs_human true. Never invent a turnaround time."),
    )


class VideoClientAgent(GigMixin, OutreachAgent):
    """Cold outreach and open-gig hunting, sharing one memory.

    The cold half crawls creators' sites; the gig half answers people who have
    already said in public that they want to hire an editor. Both write to the
    same brain, because "is this client worth my time" is one question asked at
    two moments.
    """

    # -- the merged graph --------------------------------------------------
    def build(self, recursion_limit: int = 400):
        from agents.common import outreach_reducers
        from core.graph import END, StateGraph
        g = StateGraph(reducers=outreach_reducers())

        # phase one: people already hiring an editor
        g.add_node("sweep", self.n_sweep, retries=1)
        g.add_node("pick_gig", self.n_pick_gig)
        g.add_node("read_gig", self.n_read_gig, retries=1, backoff=2)
        g.add_node("pitch_gig", self.n_pitch_gig)
        g.add_node("approve_gig", self.n_approve_gig)
        g.add_node("send_gig", self.n_send_gig)
        g.add_node("more_gigs", lambda s: None)

        # phase two: cold outreach to creators, unchanged
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
        g.add_edge("read_gig", "pitch_gig")
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

    def run(self, thread_id: str | None = None, **kw):
        import time as _time
        tid = thread_id or f"video_client-{_time.strftime('%Y%m%d-%H%M%S')}"
        state = {"_thread_id": tid}
        for key in ("sweep", "only_sources"):
            if kw.get(key) is not None:
                state[key] = kw.pop(key)
        return self.build().invoke(state, thread_id=tid, **kw)


def make(store=None, **kw) -> VideoClientAgent:
    return VideoClientAgent(build_config(), store=store, **kw)


def make_reply(store=None, **kw) -> ReplyAgent:
    from agents.sales_conversation import SalesReplyAgent
    return SalesReplyAgent(build_reply_config(), store=store, **kw)
