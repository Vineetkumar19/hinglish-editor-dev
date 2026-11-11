"""Pricing, negotiating, and knowing when to stop.

The rule this module exists to enforce: every number that reaches a client
comes out of profiles/video_rates.yaml. Not from a model, not from an average,
not from what the client says someone else charges. A model that invents a
price is not making a mistake you can spot in the draft - it reads perfectly
well and costs you the difference.

Two numbers per tier do the work. `ask` is what the quote opens at. `floor` is
where he walks away. Between them the agent may move on its own; below the
floor it stops and asks him, every time, with no exceptions and no "just this
once" for a client who seems promising. A floor that bends is not a floor.
"""
from __future__ import annotations

import math
import pathlib
import re
from dataclasses import dataclass, field

from core import config
from core.log import get_logger
from core.yamlite import load_yaml

log = get_logger("video.quote")

# Where the client is decides which card they see. An Indian client quoted in
# dollars walks; a US client quoted in rupees reads it as amateur.
INR_COUNTRIES = ("india", "bharat", ".in", "bengaluru", "bangalore", "mumbai",
                 "delhi", "hyderabad", "chennai", "pune", "kolkata", "noida",
                 "gurugram", "gurgaon", "ahmedabad", "jaipur", "kochi")

# What the client says they want -> which tier answers it. Ordered: the first
# match wins, so the more specific patterns come first.
# Every pattern ends in \w* rather than \b on purpose. A trailing \b after a
# stem cannot match the word it is a stem OF - "colou?r grad" followed by \b
# never matches "colour grading", because the boundary falls inside the word.
# That silently priced a grade-only enquiry as a full long-form edit.
TIER_SIGNALS = [
    ("explainer", r"\b(explainer|saas video|product video|animated (video|ad)|"
                  r"brand film|commercial|advert)\w*"),
    ("documentary", r"\b(documentar|mini[- ]doc|video essay|storytell|archive|"
                    r"long form story|narrative edit)\w*"),
    ("retainer", r"\b(retainer|ongoing|monthly|full[- ]time|long[- ]term|"
                 r"every week|per month|dedicated editor)\w*"),
    ("short_form_pack", r"\b(\d+\s*(shorts|reels|tiktoks)\s*(a|per)\s*(week|month)|"
                        r"batch of (shorts|reels))\w*"),
    ("motion_asset", r"\b(logo anim|motion graphic|title sequence|lower third|"
                     r"data anim|kinetic typograph|intro anim)\w*"),
    ("grade_only", r"\b(colou?r grad|colou?r correct|grading only|just the grade)\w*"),
    ("sound_only", r"\b(sound design|audio mix|sound mix|audio clean)\w*"),
    ("short_form", r"\b(short[- ]?form|reels?|shorts?|tiktoks?|vertical video)\w*"),
    ("long_form", r"\b(long[- ]?form|youtube video|podcast edit|vlog|"
                  r"talking head|interview edit)\w*"),
]

RUSH = r"\b(urgent|asap|rush|by tomorrow|this week|quick turnaround|tight deadline)\b"


def rates_path() -> pathlib.Path:
    return pathlib.Path(config.get("VIDEO_RATES_FILE",
                                   str(config.profiles_dir() / "video_rates.yaml")))


# Keyed on which file, and when it last changed. A cache keyed on nothing meant
# that pointing VIDEO_RATES_FILE somewhere else, or editing the card, went on
# quoting the prices already in memory - the one kind of staleness that costs
# money rather than time.
_CACHE: dict | None = None
_CACHE_KEY: tuple | None = None


def load_rates(refresh: bool = False) -> dict:
    global _CACHE, _CACHE_KEY
    path = rates_path()
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        key = (str(path), None)
    if _CACHE is not None and not refresh and key == _CACHE_KEY:
        return _CACHE
    _CACHE_KEY = key
    if not path.exists():
        log.warn(f"no rate card at {path} - every quote will be PLACEHOLDER")
        _CACHE = {}
        return _CACHE
    _CACHE = load_yaml(path.read_text(encoding="utf-8")) or {}
    return _CACHE


def currency_for(text: str) -> str:
    """USD unless there is a reason to think they are in India."""
    low = (text or "").lower()
    return "inr" if any(k in low for k in INR_COUNTRIES) else "usd"


def tier_for(text: str) -> str:
    low = (text or "").lower()
    for tier, pattern in TIER_SIGNALS:
        if re.search(pattern, low):
            return tier
    return "long_form"


def rules() -> dict:
    return (load_rates().get("rules") or {})


@dataclass
class Quote:
    """One priced offer, and everything needed to defend it."""
    tier_id: str
    tier_name: str
    currency: str
    ask: float
    floor: float
    unit: str
    turnaround: str = ""
    rush: bool = False
    first_project: bool = False
    note: str = ""
    adjustments: list = field(default_factory=list)
    missing: bool = False          # no rate card - nothing may be sent

    @property
    def symbol(self) -> str:
        return {"USD": "$", "INR": "INR "}.get(self.currency, self.currency + " ")

    def money(self, amount: float) -> str:
        if self.missing:
            return "PLACEHOLDER"
        number = f"{amount:,.0f}" if float(amount).is_integer() else f"{amount:,.2f}"
        return f"{self.symbol}{number}"

    def render(self) -> str:
        if self.missing:
            return ("PLACEHOLDER - no rate card is configured, so no price can "
                    "be quoted. Fill in profiles/video_rates.yaml.")
        out = f"{self.money(self.ask)} {self.unit}"
        if self.turnaround:
            out += f", {self.turnaround}"
        return out

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_json(cls, d: dict) -> "Quote":
        return cls(**{k: v for k, v in (d or {}).items()
                      if k in cls.__dataclass_fields__})


def build_quote(text: str, *, tier_id: str = "", currency: str = "",
                first_project: bool = False) -> Quote:
    """Read what they asked for and price it from the card."""
    rates = load_rates()
    cur = (currency or currency_for(text)).lower()
    card = rates.get(cur) or {}
    tiers = {t.get("id"): t for t in (card.get("tiers") or [])}
    tid = tier_id or tier_for(text)
    tier = tiers.get(tid)
    if not tier:
        log.warn(f"no tier {tid!r} in the {cur} rate card")
        return Quote(tier_id=tid, tier_name=tid.replace("_", " "),
                     currency=card.get("currency", cur.upper()), ask=0.0,
                     floor=0.0, unit="", missing=True)

    ask = float(tier.get("ask") or 0)
    floor = float(tier.get("floor") or 0)
    adjustments = []
    r = rules()

    rush = bool(re.search(RUSH, (text or "").lower()))
    if rush and r.get("rush_surcharge_pct"):
        pct = float(r["rush_surcharge_pct"])
        ask *= 1 + pct / 100
        # The floor rises with the ask. A rush job at the normal floor means
        # dropping everything else for less money than the ordinary work.
        floor *= 1 + pct / 100
        adjustments.append(f"rush turnaround, +{pct:g}%")

    if first_project and r.get("first_project_discount_pct"):
        pct = float(r["first_project_discount_pct"])
        ask *= 1 - pct / 100
        adjustments.append(f"first project with this client, -{pct:g}%")

    from core.work_policy import project_floor
    minimum = project_floor(card.get("currency", cur.upper()))
    if ask:
        floor = max(floor, minimum)
        ask = max(ask, floor)

    return Quote(tier_id=tid, tier_name=tier.get("name", tid),
                 currency=card.get("currency", cur.upper()),
                 ask=ask, floor=floor, unit=tier.get("unit", ""),
                 turnaround=str(tier.get("turnaround", "")), rush=rush,
                 first_project=first_project, note=str(tier.get("note", "")),
                 adjustments=adjustments, missing=not ask)


# --------------------------------------------------------------------------
# negotiating
# --------------------------------------------------------------------------
@dataclass
class Counter:
    """What to do about a number the client put on the table."""
    action: str            # "accept" | "counter" | "ask_operator" | "hold"
    amount: float = 0.0
    reason: str = ""
    give: str = ""         # what to take away if the price comes down


# Never drop the price without taking something out. A discount alone teaches
# the client the first number was padded; a smaller scope at a lower price is a
# different deal, and it protects the rate for everyone after them.
CONCESSIONS = [
    "one round of revisions instead of two",
    "a longer turnaround",
    "delivery without the motion-graphics titles",
    "a three-video commitment at this rate rather than a single video",
]


def find_offer(text: str, currency: str) -> float:
    """The number the client named, if they named one."""
    low = (text or "").replace(",", "")
    if currency == "INR":
        pats = [r"(?:inr|rs\.?|₹)\s*([0-9]+(?:\.[0-9]+)?)\s*(k|lakh|l)?",
                r"([0-9]+(?:\.[0-9]+)?)\s*(k|lakh|l)?\s*(?:inr|rs\b|rupees)"]
    else:
        pats = [r"(?:usd|\$)\s*([0-9]+(?:\.[0-9]+)?)\s*(k)?",
                r"([0-9]+(?:\.[0-9]+)?)\s*(k)?\s*(?:usd|dollars)\b"]
    for pat in pats:
        m = re.search(pat, low, re.I)
        if not m:
            continue
        value = float(m.group(1))
        suffix = (m.group(2) or "").lower()
        if suffix == "k":
            value *= 1_000
        elif suffix in ("lakh", "l"):
            value *= 100_000
        return value
    return 0.0


def respond_to(offer: float, quote: Quote) -> Counter:
    """Accept, counter, or stop and ask him. The floor is absolute."""
    if quote.missing:
        return Counter("ask_operator", reason="there is no rate card to quote from")
    if offer <= 0:
        return Counter("hold", amount=quote.ask,
                       reason="they have not named a number yet")
    if offer >= quote.ask:
        return Counter("accept", amount=offer, reason="at or above the asking price")
    if offer >= quote.floor:
        # Worth meeting in the middle rather than taking the first offer: the
        # midpoint is still above the floor, and a client who names a number
        # expects one back.
        mid = max(quote.floor, math.ceil((offer + quote.ask) / 2))
        if mid <= offer * 1.02:
            return Counter("accept", amount=offer,
                           reason="above the floor and close enough to the ask")
        return Counter("counter", amount=mid,
                       reason="above the floor, so there is room to meet them",
                       give=CONCESSIONS[0])
    return Counter("ask_operator", amount=offer,
                   reason=f"{quote.money(offer)} is below the {quote.money(quote.floor)} "
                          f"floor for {quote.tier_name}")


def deposit_line(quote: Quote, amount: float | None = None) -> str:
    """The sentence that decides whether he gets paid."""
    r = rules()
    pct = float(r.get("deposit_pct") or 0)
    if not pct or quote.missing:
        return ""
    total = quote.ask if amount is None else amount
    return (f"{pct:g}% ({quote.money(total * pct / 100)}) to start, the balance "
            f"on delivery, payable within {int(r.get('payment_terms_days', 7))} days.")
