"""Fixed-price payment work, and the floor under it.

pricing.py estimates a build in days and multiplies by a day rate. That is the
right shape for "build us a web app" and the wrong shape for "our checkout is
double-charging people", where the value has nothing to do with how many hours
it takes and everything to do with how fast it stops.

So payments work is priced as packages, with an ask and a floor, exactly like
the video client's rate card. Below the floor it stops and asks him. A floor
that bends for an urgent-sounding client is not a floor - and every client with
a broken checkout sounds urgent.
"""
from __future__ import annotations

import math
import pathlib
import re
from dataclasses import dataclass, field

from core import config
from core.log import get_logger
from core.yamlite import load_yaml

log = get_logger("dev.packages")

INR_MARKERS = ("india", "bharat", ".in", "bengaluru", "bangalore", "mumbai",
               "delhi", "hyderabad", "chennai", "pune", "kolkata", "noida",
               "gurugram", "gurgaon", "ahmedabad", "jaipur", "kochi", "indore",
               "rupee", "inr", "₹", "lakh", "crore")

# Which package answers what they described. First match wins.
PACKAGE_SIGNALS = [
    ("marketplace_payouts", r"\b(split payment|route\b|stripe connect|"
                            r"vendor payout|seller payout|marketplace payment|"
                            r"settlement|commission split)\w*"),
    # "mandate" and "autopay" are UPI's own vocabulary, not generic
    # subscription words. Leaving them here priced "add UPI autopay mandates"
    # as full subscription billing - the wrong package and nearly twice the
    # price, which is the kind of quote that ends a conversation.
    ("subscriptions", r"\b(subscription|recurring billing|recurring payment|"
                      r"plans? and pricing|proration|dunning|"
                      r"free trial billing)\w*"),
    ("upi_integration", r"\b(upi\b|bhim|qr code payment|collect request|"
                        r"upi autopay|upi intent)\w*"),
    ("payment_rescue", r"\b(fix (the|our|my|a|this)|not working|is broken|"
                       r"keeps failing|double charg|webhook.{0,25}(fail|not)|"
                       r"signature (mismatch|verification)|orders? not|"
                       r"payment.{0,20}(fail|stuck|missing)|reconcil)\w*"),
    ("payment_audit", r"\b(audit|review our|check our|second opinion|"
                      r"is it secure|pci\b)\w*"),
    ("gateway_standard", r"\b(razorpay|payu|cashfree|instamojo|phonepe|paytm|"
                         r"stripe|paypal|payment gateway|checkout integration|"
                         r"accept payments?)\w*"),
]


def card_path() -> pathlib.Path:
    return pathlib.Path(config.get("PRICING_FILE",
                                   str(config.profiles_dir() / "dev_rate_card.yaml")))


_CACHE: dict | None = None
_CACHE_KEY: tuple | None = None


def load_card(refresh: bool = False) -> dict:
    """Keyed on the file and its mtime, so an edit is picked up at once."""
    global _CACHE, _CACHE_KEY
    path = card_path()
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
    low = (text or "").lower()
    return "inr" if any(k in low for k in INR_MARKERS) else "usd"


def package_for(text: str) -> str:
    low = (text or "").lower()
    for pid, pattern in PACKAGE_SIGNALS:
        if re.search(pattern, low):
            return pid
    return ""


def rules() -> dict:
    return load_card().get("rules") or {}


@dataclass
class Package:
    id: str
    label: str
    currency: str
    ask: float
    floor: float
    turnaround: str = ""
    note: str = ""
    adjustments: list = field(default_factory=list)
    missing: bool = False

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
                    "be quoted. Fill in profiles/dev_rate_card.yaml.")
        out = self.money(self.ask)
        if self.turnaround:
            out += f", {self.turnaround}"
        return out

    def to_json(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, d: dict) -> "Package":
        return cls(**{k: v for k, v in (d or {}).items()
                      if k in cls.__dataclass_fields__})


def build_package(text: str, *, package_id: str = "",
                  currency: str = "") -> Package | None:
    """Price what they described, or None when it is a build rather than
    payments work - pricing.py handles those."""
    card = load_card()
    pid = package_id or package_for(text)
    if not pid:
        return None
    cur = (currency or currency_for(text)).lower()
    entry = next((p for p in (card.get("packages") or [])
                  if p.get("id") == pid), None)
    if not entry:
        return Package(id=pid, label=pid.replace("_", " "),
                       currency=cur.upper(), ask=0.0, floor=0.0, missing=True)
    money = entry.get(cur) or entry.get("usd") or {}
    ask = float(money.get("ask") or 0)
    floor = float(money.get("floor") or 0)
    adjustments = []
    r = rules()
    if re.search(r"\b(urgent|asap|today|right now|immediately|losing (money|sales))\b",
                 (text or "").lower()) and card.get("multipliers", {}).get("rush"):
        mult = float(card["multipliers"]["rush"])
        ask *= mult
        # The floor rises with the ask. Dropping everything else for a rush job
        # at the ordinary floor is worse than not taking it.
        floor *= mult
        adjustments.append(f"urgent, +{(mult - 1) * 100:.0f}%")
    from core.work_policy import project_floor
    if ask:
        floor = max(floor, project_floor(cur))
        ask = max(ask, floor)
    return Package(id=pid, label=entry.get("label", pid),
                   currency={"usd": "USD", "inr": "INR"}.get(cur, cur.upper()),
                   ask=ask, floor=floor,
                   turnaround=str(entry.get("turnaround", "")),
                   note=str(entry.get("note", "")), adjustments=adjustments,
                   missing=not ask)


# --------------------------------------------------------------------------
@dataclass
class Counter:
    action: str            # accept | counter | ask_operator | hold
    amount: float = 0.0
    reason: str = ""
    give: str = ""


# Never drop the price without removing something. On development work the
# honest concessions are scope, not discounts.
CONCESSIONS = [
    "one round of revisions instead of two",
    "a longer delivery window",
    "test-mode delivery, with go-live handled separately",
    "the fix only, with the written audit report dropped",
]


def find_offer(text: str, currency: str) -> float:
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


def respond_to(offer: float, pkg: Package) -> Counter:
    if pkg.missing:
        return Counter("ask_operator", reason="there is no rate card to quote from")
    if offer <= 0:
        return Counter("hold", amount=pkg.ask,
                       reason="they have not named a number yet")
    if offer >= pkg.ask:
        return Counter("accept", amount=offer, reason="at or above the asking price")
    if offer >= pkg.floor:
        mid = max(pkg.floor, math.ceil((offer + pkg.ask) / 2))
        if mid <= offer * 1.02:
            return Counter("accept", amount=offer,
                           reason="above the floor and close enough to the ask")
        return Counter("counter", amount=mid,
                       reason="above the floor, so there is room to meet them",
                       give=CONCESSIONS[0])
    return Counter("ask_operator", amount=offer,
                   reason=f"{pkg.money(offer)} is below the {pkg.money(pkg.floor)} "
                          f"floor for {pkg.label}")


def deposit_line(pkg: Package, amount: float | None = None) -> str:
    r = rules()
    pct = float(r.get("deposit_pct") or 0)
    if not pct or pkg.missing:
        return ""
    total = pkg.ask if amount is None else amount
    return (f"{pct:g}% ({pkg.money(total * pct / 100)}) to start, the balance on "
            f"delivery, payable within {int(r.get('payment_terms_days', 7))} days.")
