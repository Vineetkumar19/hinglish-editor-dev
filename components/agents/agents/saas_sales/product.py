"""What the product is, and what the agent is allowed to say about it today.

The other four agents sell something that already exists: a channel with real
subscriber numbers, a resume, an editing service, an engineer's time. This one
does not. It sells a product that is still being built, which makes it the only
agent in the suite that can do real damage by being persuasive.

The audience for an AI video editing tool is small, technical and talks to
itself constantly. One round of pitching a product that turns out not to exist,
or promising a commission that cannot be paid, and the name is finished in that
community - and it is the same community he needs as his first customers, his
first partners and his first reviewers.

So `stage` in profiles/product.yaml is not advice. It is a gate applied to the
finished draft before it reaches him. While the product is `building` there is
no price, no trial link and no commission in any message, however the model
chooses to phrase it, and `check_claims()` is what enforces that.
"""
from __future__ import annotations

import pathlib
import re

from core import config
from core.log import get_logger
from core.yamlite import load_yaml

log = get_logger("saas.product")

# What each stage permits. Ordered from least to most.
STAGES = ("idea", "building", "beta", "live")

ALLOWS = {
    "idea": set(),
    "building": {"waitlist", "early_access", "early_partner_terms"},
    "beta": {"waitlist", "early_access", "early_partner_terms", "feedback",
             "founding_partner"},
    "live": {"waitlist", "early_access", "early_partner_terms", "feedback",
             "founding_partner", "price", "trial", "commission", "signup"},
}

# Language that asserts something only a live product can back. Deliberately
# broad: a false positive costs one redraft, a false negative costs the
# reputation the whole product launches into.
CLAIM_PATTERNS = {
    "price": r"(\$\s?\d|\bUSD\s?\d|\bINR\s?\d|₹\s?\d|\b\d+\s?(?:usd|dollars|rupees)\b|"
             r"\b(?:per|a)\s+month\b.{0,20}\d|\b\d+\s*/\s*(?:mo|month|yr|year)\b|"
             r"\bpricing (?:is|starts)\b|\bcosts?\s+\$?\d|\bsubscription is\b)",
    "trial": r"\b(free trial|try it (?:free|now|today)|start your trial|"
             r"\d+[- ]day trial|sign up (?:free|now|today)|get started (?:free|now))\b",
    "commission": r"\b(\d{1,3}\s?%|\bcommission\b|\brevenue share\b|\brev[- ]share\b|"
                  r"\bpayout\b|\bearn(?:ings)? per (?:sale|signup|referral)\b|"
                  r"\baffiliate (?:link|programme|program)\b|\byou (?:get|keep|make)\b.{0,15}%)",
    "signup": r"\b(sign up at|create an account|start using it|download it|"
              r"install the plugin|available (?:now|today))\b",
}

# A launch date is refused at every stage, including live - "next month" from a
# one-person team is a promise that breaks more often than it holds.
ALWAYS_REFUSED = {
    "launch_date": r"\b(launch(?:ing|es)? (?:on|in|next|this)|"
                   r"(?:available|ready|out) (?:next|this) (?:week|month|quarter)|"
                   r"by (?:january|february|march|april|may|june|july|august|"
                   r"september|october|november|december)\b|"
                   r"\bin \d+ weeks?\b|\bshipping (?:next|this)\b)",
    "user_numbers": r"\b(\d[\d,]{2,}\s*(?:users?|customers?|creators?|editors?)|"
                    r"thousands of (?:users?|customers?)|\btrusted by\b|"
                    r"\bused by \d)",
    "competitor_claim": r"\b(better than|faster than|cheaper than|beats)\s+"
                        r"(?:firecut|descript|opus ?clip|veed|kapwing|premiere|"
                        r"resolve|capcut|adobe)\b",
}


def profile_path() -> pathlib.Path:
    return pathlib.Path(config.get("PRODUCT_FILE",
                                   str(config.profiles_dir() / "product.yaml")))


_CACHE: dict | None = None
_CACHE_KEY: tuple | None = None


def load_product(refresh: bool = False) -> dict:
    """Keyed on the file and its mtime, so an edit is picked up at once."""
    global _CACHE, _CACHE_KEY
    path = profile_path()
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        key = (str(path), None)
    if _CACHE is not None and not refresh and key == _CACHE_KEY:
        return _CACHE
    _CACHE_KEY = key
    if not path.exists():
        log.warn(f"no product profile at {path} - this agent cannot run")
        _CACHE = {}
        return _CACHE
    _CACHE = load_yaml(path.read_text(encoding="utf-8")) or {}
    return _CACHE


def stage() -> str:
    s = str(load_product().get("stage") or "idea").strip().lower()
    return s if s in STAGES else "idea"


def allows(what: str) -> bool:
    return what in ALLOWS.get(stage(), set())


def has_pricing() -> bool:
    p = (load_product().get("pricing") or {})
    return bool(p.get("tiers"))


def has_partner_terms() -> bool:
    p = (load_product().get("partner") or {})
    return bool(p.get("share_pct")) and bool(p.get("share_of"))


def ready_to_sell() -> tuple[bool, str]:
    """Whether there is enough here to write anything at all."""
    p = load_product()
    if not p:
        return False, "there is no profiles/product.yaml"
    if stage() == "idea":
        return False, ("the product is marked `idea`, so there is nothing to "
                       "pitch yet - this agent stays quiet until it is at "
                       "least `building`")
    if not (p.get("does") or []):
        return False, "product.yaml does not say what the product does"
    if not str(p.get("name") or "").strip():
        return False, ("product.yaml has no name - an email about an unnamed "
                       "product is not something anyone can act on")
    return True, ""


def check_claims(text: str) -> list[str]:
    """Everything in this draft that the stage does not support.

    Run on the finished body, after the model and after any code that touched
    it. An empty list means the draft is safe to put in front of him.
    """
    problems = []
    low = text or ""

    for name, pattern in CLAIM_PATTERNS.items():
        if not re.search(pattern, low, re.I):
            continue
        if allows(name):
            # Permitted by the stage, but a price still has to exist.
            if name == "price" and not has_pricing():
                problems.append("states a price, but product.yaml has no "
                                "pricing tiers filled in")
            if name == "commission" and not has_partner_terms():
                problems.append("promises a commission, but product.yaml has "
                                "no partner terms filled in")
            continue
        problems.append({
            "price": f"states a price - not allowed while the product is "
                     f"`{stage()}`",
            "trial": f"offers a trial - there is nothing to try while the "
                     f"product is `{stage()}`",
            "commission": f"promises a commission - it cannot be paid while "
                          f"the product is `{stage()}`",
            "signup": f"tells them to sign up or install - not possible while "
                      f"the product is `{stage()}`",
        }[name])

    for name, pattern in ALWAYS_REFUSED.items():
        hit = re.search(pattern, low, re.I)
        if hit:
            problems.append({
                "launch_date": f"promises a launch date ({hit.group(0)!r}) - "
                               f"refused at every stage",
                "user_numbers": f"claims a user count ({hit.group(0)!r}) - "
                                f"there is nothing to count yet",
                "competitor_claim": f"claims to beat a named competitor "
                                    f"({hit.group(0)!r})",
            }[name])

    # Capabilities it does not have.
    known = " ".join(str(d).lower() for d in (load_product().get("does") or []))
    # Every alternative ends in \w* rather than \b. A trailing \b after a stem
    # cannot match the word it is a stem OF - "auto[- ]?dub" followed by \b
    # never matches "auto-dubbing", so the claim sailed straight through.
    for invented in re.findall(
            r"\b(auto[- ]?dub\w*|translat\w*|green ?screen\w*|motion track\w*|"
            r"face ?swap\w*|lip ?sync\w*|colou?r grad\w*|music generation|"
            r"voice clon\w*|auto[- ]?edit\w*|thumbnail generat\w*)", low, re.I):
        if invented.lower() not in known:
            problems.append(f"claims a feature that is not in product.yaml's "
                            f"`does` list: {invented}")
    return problems


def facts_block() -> str:
    """The product, as prompt text. Only what the file actually says."""
    p = load_product()
    if not p:
        return ""
    lines = [f"- Name: {p.get('name') or '(unnamed)'}"]
    if p.get("tagline"):
        lines.append(f"- In one line: {p['tagline']}")
    lines.append("- What it does, and nothing beyond this list:")
    for d in (p.get("does") or []):
        lines.append(f"    - {d}")
    if p.get("works_with"):
        lines.append(f"- Works inside: {', '.join(str(w) for w in p['works_with'])}")
    if p.get("for_who"):
        lines.append("- Who it is for:")
        for w in p["for_who"]:
            lines.append(f"    - {w}")
    if p.get("different_because"):
        lines.append("- What makes it different:")
        for w in p["different_because"]:
            lines.append(f"    - {w}")
    else:
        lines.append("- No differentiator is recorded. Do not invent one. It is "
                     "better to describe what it does plainly than to claim an "
                     "edge that cannot be defended.")
    return "\n".join(lines)


def stage_rules_block() -> str:
    """What this stage forbids, written for the model."""
    s = stage()
    common = ("- Never promise a launch date, not even a vague one.\n"
              "- Never claim a user count, a customer name or a revenue figure.\n"
              "- Never say it is better, faster or cheaper than a named tool.\n"
              "- Never describe a capability that is not on the list above.")
    if s == "building":
        return (f"THE PRODUCT IS STILL BEING BUILT. This is the hard part of "
                f"this email and the whole point of it.\n"
                f"- There is NO price to state. Do not state one, hint at one, "
                f"or say it will be affordable.\n"
                f"- There is NOTHING to try yet. Do not offer a trial, a demo "
                f"link, a download or a signup.\n"
                f"- There is NO commission to promise. It cannot be paid yet.\n"
                f"- What you are actually asking for is much smaller: whether "
                f"they want to be told when it is ready, and whether they would "
                f"be willing to look at it early and say what is wrong with it.\n"
                f"- Being straight that it is not finished is the strongest "
                f"thing in the email. Say it plainly and early.\n{common}")
    if s == "beta":
        return (f"THE PRODUCT IS IN BETA. It works and it is rough.\n"
                f"- You may offer early access and ask for feedback.\n"
                f"- You may discuss founding-partner terms as terms, but no "
                f"live billing or payout claims.\n"
                f"- Still no price unless product.yaml lists tiers.\n{common}")
    if s == "live":
        return (f"THE PRODUCT IS LIVE.\n"
                f"- You may link the signup and state prices, but ONLY prices "
                f"that appear in product.yaml.\n{common}")
    return (f"THE PRODUCT IS AN IDEA. Do not pitch it. Ask questions about how "
            f"they work today and what wastes their time.\n{common}")


def partner_offer_block() -> str:
    """What a promoter is actually being offered today."""
    p = load_product()
    partner = p.get("partner") or {}
    if has_partner_terms() and allows("commission"):
        return (f"- {partner['share_pct']}% "
                f"({str(partner.get('share_of', '')).replace('_', ' ')})"
                + (f", {partner['cookie_days']}-day attribution"
                   if partner.get("cookie_days") else ""))
    lines = ["- No commission can be promised yet, and you must not imply one.",
             "- What can be offered, and costs nothing to honour:"]
    for t in (partner.get("early_terms") or []):
        lines.append(f"    - {t}")
    lines.append("- Say plainly that the commercial terms are not set, and "
                 "that you will come to them with numbers before anything "
                 "goes live.")
    return "\n".join(lines)
