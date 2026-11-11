"""Agent 1 - Sponsorship.

One agent with one brain, doing two things that are really the same thing.

    It finds brands.   It sweeps affiliate networks, the Indian marketing
                       press, and the sponsor links in other cricket creators'
                       video descriptions, checks each one is real and Indian,
                       and asks whether to add it to your list.

    It pitches them.   It works down that list, reads each site, finds a route
                       to a human, writes the message for that kind of deal,
                       and asks before anything is sent.

They share a brain because they are the same judgement made at two moments.
Every answer you give - add this brand, do not add that one, send this pitch,
do not send that one - and every answer a BRAND gives - a reply, a no, a
bounce - is filed as evidence. What it learns from a reply to a nutrition brand
lifts both the next nutrition brand it finds and the nutrition brands still
waiting on your list.

Nothing is sent, and nothing is added, without you saying so.
"""
from __future__ import annotations

from agents.common import (OutreachAgent, OutreachConfig, ReplyAgent,
                           ReplyConfig, outreach_reducers)
from agents.sponsorship import brief as brief_mod
from agents.sponsorship import pitch as pitch_mod
from agents.sponsorship import sources as src
from agents.sponsorship.brain import Memory
from agents.sponsorship.discover import (DiscoveryMixin, banned_reason,
                                         salesman_reason)
from agents.templates import company_name, compose
from core import config
from core.graph import END, StateGraph
from core.llm import offline_handler
from core.log import get_logger

log = get_logger("sponsorship")

AGENT = "sponsorship"

SYSTEM = """You write short sponsorship enquiry emails on behalf of a cricket
analysis creator. You are honest and specific. You never exaggerate audience
size, never promise results, and never claim a relationship that does not exist.
If you do not know a number, you leave it out rather than inventing one."""

PITCH_INSTRUCTION = """You are writing on behalf of {operator}, who runs a
cricket analysis and documentary-edit channel and edits every video himself.
The goal of this first email is a reply, not a signed deal.

Ask whether they run a creator partnership or sponsorship programme, and who
handles it. Mention production quality only as a concrete fact, never as a
boast. Never state an audience figure - those come from the profile, not from
you."""

# The seed list carries everything; these queries just let a keyword search
# narrow it when you ask for one segment rather than the whole list.
SEARCH_QUERIES = [
    "creator partnership sponsorship brand collaboration india cricket",
]

# Real-money gaming and betting are refused in one place, agents/sponsorship/
# discover.py, and applied both to what the web sweep finds and to what is
# already on the list. `blocked_reason` below is the list-side check.
BLOCKED_SEGMENTS = {"betting", "real_money_gaming", "fantasy_sports", "casino"}


def blocked_reason(brand: dict) -> str:
    """Empty string when the brand is fine to approach."""
    seg = (brand.get("segment") or "").lower()
    if seg in BLOCKED_SEGMENTS:
        return f"{seg} is a real-money gaming category - not legal to promote in India"
    why = salesman_reason(brand.get("fit", ""), brand.get("why", ""),
                          " ".join(str(h) for h in (brand.get("hints") or [])))
    if why:
        return why
    return banned_reason(brand.get("name", ""),
                         " ".join(str(v) for v in brand.values()))


# The point of this agent is brands PAYING to be promoted in a video. That is
# what goes first. An agency roster is next because agencies bring paid work.
# Barter comes third - product instead of money, worth taking early on to build
# real brand credits. Affiliate is last and off by default: selling other
# people's products for a cut of the sale is a different job, and not this one.
DEAL_ORDER = {"cash": 0, "agency": 1, "barter": 2, "affiliate": 3}


def wanted_deals() -> set:
    """Which kinds of deal to work at all. Affiliate is excluded by default."""
    return set(config.get_list("SPONSORSHIP_DEAL_TYPES",
                               ["cash", "agency", "barter"]))


def rank(lead: dict) -> tuple:
    """Tier 1 first, then the deals that pay soonest, then cricket-native."""
    meta = lead.get("meta") or {}
    tier = meta.get("tier") or 3
    seg = (meta.get("segment") or "").lower()
    deal = (meta.get("deal_type") or "cash").lower()
    native = 0 if seg.startswith("cricket") or seg in ("agency", "sports_agency",
                                                       "sports_booking",
                                                       "sports_streaming") else 1
    return (int(tier), DEAL_ORDER.get(deal, 9), native, meta.get("name", ""))


@offline_handler(f"pitch:{AGENT}")
def _offline_pitch(ctx: dict) -> dict:
    """The pitch itself. Built in code rather than prompted out of a model,
    because every sentence is accountable to something in the profile."""
    prof = ctx.get("profile") or {}
    contact = ctx.get("contact") or {}
    cur = ctx.get("current") or {}
    brand = dict(cur.get("meta") or {})
    if not brand.get("name"):
        brand["name"] = company_name(prof, cur.get("domain", "your team"),
                                     preferred=cur.get("title", ""))
    observation = (prof.get("description") or "").strip()[:180]
    creator = pitch_mod.load_creator()
    out = pitch_mod.email_pitch(brand, observation=observation,
                                contact_name=contact.get("name", ""))
    # The model is asked for all three channels and a read of the brand, so the
    # written fallback has to answer in the same shape or it fails validation
    # exactly when it is needed most - when the model is unavailable.
    out.setdefault("reads_as", observation or
                   f"{brand.get('name') or cur.get('domain', 'this brand')} - "
                   f"written from the list entry; the site was not readable.")
    out.setdefault("whatsapp", pitch_mod.whatsapp_pitch(brand, creator))
    out.setdefault("instagram_dm", pitch_mod.instagram_dm(brand, creator))
    return out


def message_extras(s: dict) -> dict:
    """The other two channels, plus the facts that make the card readable."""
    cur = s.get("current") or {}
    brand = dict(cur.get("meta") or {})
    if not brand.get("name"):
        brand["name"] = (s.get("profile") or {}).get("title") or cur.get("domain", "")
    contact = ((s.get("qualify") or {}).get("contact")) or {}
    creator = pitch_mod.load_creator()
    draft = s.get("draft") or {}
    # When a model wrote the email it wrote these two as well, against the same
    # brand. Falling back to the template here would put a tailored email and a
    # generic DM on the same card.
    wa_text = (draft.get("whatsapp") or "").strip() \
        or pitch_mod.whatsapp_pitch(brand, creator)
    dm_text = (draft.get("instagram_dm") or "").strip() \
        or pitch_mod.instagram_dm(brand, creator)
    # Every route this brand has, not only the one the agent picked. You wanted
    # to reach a brand by mail AND by WhatsApp, and which one the qualifier
    # happened to rank first is no reason to hide the other.
    best_email, best_phone = contact.get("email", ""), contact.get("phone", "")
    for c in sorted(s.get("contacts") or [],
                    key=lambda c: -float(c.get("confidence") or 0)):
        if not best_email and c.get("email"):
            best_email = c["email"]
        if not best_phone and c.get("phone"):
            best_phone = c["phone"]
    return {
        "whatsapp_text": wa_text,
        "instagram_dm": dm_text,
        "best_email": best_email,
        "best_phone": best_phone,
        "wa_link": pitch_mod.wa_link(best_phone, wa_text),
        "segment": brand.get("segment", ""),
        "tier": brand.get("tier", ""),
        "deal_type": pitch_mod.deal_type(brand),
        "fit": brand.get("fit", ""),
        "contact_form_url": (s.get("profile") or {}).get("contact_form_url", ""),
        "socials": (s.get("profile") or {}).get("socials", {}),
        "has_numbers": pitch_mod.has_numbers(creator),
    }


@offline_handler(f"reply:{AGENT}")
def _offline_reply(ctx: dict) -> dict:
    intent = (ctx.get("intent") or {}).get("label", "other")
    asked = (ctx.get("intent") or {}).get("asked_for", "")
    msg = ctx.get("message") or {}
    name = (msg.get("from_name") or "").split(" ")[0]
    greet = f"Hi {name}," if name.isalpha() and name else "Hi there,"
    if intent == "interested":
        body = compose(greet, [
            "Thanks for coming back to me - glad it's of interest.",
            "PLACEHOLDER: add current channel stats (subscribers, average views "
            "per video, audience split) and two example videos. These numbers "
            "are deliberately not auto-filled, because they must be accurate."],
            "Would a 15-minute call this week or next suit you better?")
        return {"body": body, "subject": "", "needs_human": True,
                "next_step": "Fill in real channel numbers, then send"}
    if intent == "referral":
        return {"body": compose(greet, [
            "Thanks for pointing me in the right direction."],
            "I'll reach out to them directly - is it alright to mention you "
            "passed this along?"), "subject": "", "needs_human": False,
            "next_step": "Add the referred contact as a new lead"}
    return {"body": compose(greet, [
        f"Thanks for the reply.",
        f"PLACEHOLDER: respond to what they raised{(' - they asked about: ' + asked) if asked else ''}."],
        "Let me know what would be most useful."),
        "subject": "", "needs_human": True,
        "next_step": "Answer their specific point manually"}


def qualify_bonus(site, state) -> tuple[float, str]:
    """Sponsorship-specific signals, on top of the generic contact score."""
    cur = (state or {}).get("current") or {}
    brand = cur.get("meta") or {}

    why = blocked_reason(brand)
    if why:
        return -10.0, f"EXCLUDED: {why}"

    bonus, notes = 0.0, []

    # A curated entry already carries an argument for the pitch to stand on,
    # so it does not depend on whatever the homepage happens to say.
    if brand.get("fit"):
        bonus += 0.15
        notes.append("curated fit")
    tier = brand.get("tier")
    if tier == 1:
        bonus += 0.15
        notes.append("tier 1, reachable")
    elif tier == 2:
        bonus += 0.05

    if site is not None:
        text = (site.combined_text or "").lower()
        strong = ["creator programme", "creator program", "influencer",
                  "brand partnership", "brand ambassador", "collaborat"]
        weak = ["partnership", "sponsorship", "affiliate", "press", "media kit"]
        hit = next((w for w in strong if w in text), "")
        if hit:
            bonus += 0.2
            notes.append(f"site mentions {hit}")
        else:
            hit = next((w for w in weak if w in text), "")
            if hit:
                bonus += 0.1
                notes.append(f"site mentions {hit}")
            else:
                notes.append("no partnership language on site")
    return bonus, "; ".join(notes)


def build_config() -> OutreachConfig:
    return OutreachConfig(
        agent=AGENT,
        search_queries=SEARCH_QUERIES,
        seed_file=config.get("SPONSOR_FILE",
                             str(config.profiles_dir() / "sponsors.yaml")),
        seed_category=config.get("SPONSORSHIP_CATEGORY", "sponsor"),
        looking_for="sponsorships, brand partnerships or creator programmes",
        system_prompt=SYSTEM,
        pitch_instruction=PITCH_INSTRUCTION.format(
            operator=config.get("OPERATOR_NAME", "Vineet")),
        min_score=config.get_float("SPONSORSHIP_MIN_SCORE", 0.30),
        # The point is volume. One reply in fifty is a normal cold-outreach
        # rate, so a run that stops after ten brands cannot work by design.
        max_leads_per_run=config.get_int("SPONSORSHIP_MAX_LEADS", 40),
        # The whole list is a candidate every run; ranking and the cap decide
        # who actually gets looked at today.
        per_query=config.get_int("SPONSORSHIP_POOL", 500),
        qualify_fn=qualify_bonus,
        rank_fn=rank,
        allow_non_email=True,
        extras_fn=message_extras,
        # With a model configured, these three replace the generic prompt: the
        # brief hands it the brand's own site text and this channel's real
        # numbers, and finish() puts the signature back on afterwards. With
        # LLM_PROVIDER=offline they are never reached and the written templates
        # run exactly as before.
        pitch_prompt_fn=brief_mod.build_prompt,
        pitch_schema=brief_mod.PITCH_SCHEMA,
        pitch_post_fn=brief_mod.finish,
    )


def build_reply_config() -> ReplyConfig:
    return ReplyConfig(
        agent=AGENT,
        system_prompt=SYSTEM,
        reply_instruction=(
            "You are replying on behalf of a cricket analysis YouTube creator "
            "discussing a possible sponsorship. Never state audience numbers, "
            "rates or availability - you do not have them. Where such a fact is "
            "needed, write PLACEHOLDER and describe what is missing."),
    )


class SponsorshipAgent(DiscoveryMixin, OutreachAgent):
    """The whole thing: find brands, then pitch them, learning from both.

    The graph runs in two phases. The first sweeps the web and asks what to
    add; it is skipped unless a sweep is due or you asked for one, so an
    ordinary run is just the outreach. The second is the outreach loop, which
    now orders the list by what the brain has learned rather than by a fixed
    rule.
    """

    def __init__(self, cfg: OutreachConfig, brain: Memory | None = None,
                 source_fns: dict | None = None,
                 discovery_crawler=None, **kw):
        super().__init__(cfg, **kw)
        self.brain = brain or Memory(self.store)
        if source_fns is not None:
            self.sources = source_fns
        self._disco_crawler = discovery_crawler

    # -- ordering the list by what it has learned --------------------------
    def n_discover(self, s: dict) -> dict:
        """The list, ordered by the brain instead of by a fixed rule.

        `rank` still decides the broad shape - tier first, then the deals that
        pay soonest - but within that the brain's score breaks ties, so the
        kinds of brand that have actually replied drift to the top of the
        queue over time.
        """
        out = super().n_discover(s)
        queue = out.get("leads_queue") or []
        wanted = wanted_deals()
        before = len(queue)
        queue = [l for l in queue
                 if ((l.get("meta") or {}).get("deal_type") or "cash") in wanted]
        if before != len(queue):
            log.info("filtered the queue by deal type", kept=len(queue),
                     dropped=before - len(queue), wanted=sorted(wanted))
        out["leads_queue"] = queue
        if not queue or not self.brain.counts():
            return out
        scored = []
        for lead in queue:
            fit, _ = self.brain.score_target(lead)
            scored.append((lead, fit))
        # Keep the coarse ordering, use the brain as the tie-breaker inside it.
        scored.sort(key=lambda pair: (rank(pair[0])[:2], -pair[1]))
        out["leads_queue"] = [lead for lead, _ in scored]
        best = scored[0][1] if scored else 0
        log.info("queue ordered by the brain", leads=len(scored),
                 top_score=round(best, 3))
        return out

    # -- recording what happens -------------------------------------------
    def n_approve(self, s: dict) -> dict:
        out = super().n_approve(s)
        decision = out.get("decision") or {}
        approved = decision.get("status") in ("approved", "edited")
        self.brain.record_target(
            s.get("current") or {},
            "pitch_approved" if approved else "pitch_rejected",
            note=decision.get("note", "") or "")
        return out

    def n_skip(self, s: dict) -> dict:
        out = super().n_skip(s)
        # A brand nobody could be reached at is a weak negative: not your
        # judgement, but still a fact about that kind of target.
        if not (s.get("qualify") or {}).get("contact"):
            self.brain.record_target(s.get("current") or {}, "unreachable")
        return out

    def n_send(self, s: dict) -> dict:
        out = super().n_send(s)
        if out.get("sent") or out.get("handoff"):
            self.brain.record_target(s.get("current") or {}, "sent")
        return out

    def n_draft(self, s: dict) -> dict:
        """Say what is happening first.

        On a machine without a GPU this one step is minutes, not seconds, and a
        silent minute is indistinguishable from a hang - which is exactly how
        it was read the first time.
        """
        cur = s.get("current") or {}
        name = (cur.get("meta") or {}).get("name") or cur.get("domain", "")
        if not self.llm.is_offline:
            self._say(f"Read {name}. Writing the message now - this is the slow "
                      f"part, give it a minute.")
        return super().n_draft(s)

    def run(self, thread_id: str | None = None, **kw):
        """Extra arguments go into the STATE, not into invoke().

        `run(discover=True)` used to be forwarded straight to
        CompiledGraph.invoke(), which does not take it, so /discover died with
        "unexpected keyword argument 'discover'".
        """
        import time as _time
        tid = thread_id or f"{self.cfg.agent}-{_time.strftime('%Y%m%d-%H%M%S')}"
        # Load the model now rather than inside the first brand's wait. Purely
        # a matter of when the loading happens - nothing about the pitch changes.
        impl = getattr(self.llm, "impl", None) if not self.llm.is_offline else None
        if hasattr(impl, "warm"):
            impl.warm()
        state = {"_thread_id": tid}
        for key in ("discover", "only_sources"):
            if kw.get(key) is not None:
                state[key] = kw.pop(key)
        return self.build().invoke(state, thread_id=tid, **kw)

    # -- the merged graph --------------------------------------------------
    def build(self, recursion_limit: int = 400):
        g = StateGraph(reducers=outreach_reducers())

        # phase one: go and look
        g.add_node("refresh", self.n_refresh, retries=1)
        g.add_node("screen", self.n_screen)
        g.add_node("check", self.n_check, retries=1, backoff=2)
        g.add_node("pick_find", self.n_pick_find)
        g.add_node("add", self.n_add)

        # phase two: work the list
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

        g.set_entry_point("refresh")
        g.add_conditional_edges(
            "refresh", lambda s: "screen" if s.get("candidates") else "outreach",
            {"screen": "screen", "outreach": "discover"})
        g.add_edge("screen", "check")
        g.add_edge("check", "pick_find")
        g.add_conditional_edges(
            "pick_find", lambda s: "add" if s.get("find") else "outreach",
            {"add": "add", "outreach": "discover"})
        g.add_conditional_edges("add", self.r_more_finds,
                                {"next": "pick_find", "outreach": "discover"})

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


def make(store=None, **kw) -> SponsorshipAgent:
    return SponsorshipAgent(build_config(), store=store, **kw)


def make_reply(store=None, **kw) -> ReplyAgent:
    return ReplyAgent(build_reply_config(), store=store, **kw)
