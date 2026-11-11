"""Deterministic message templates used when no LLM is configured.

These exist so the whole pipeline can be exercised end to end - and so a dry run
produces something a human can actually read and judge. They only ever
interpolate facts already present in the crawled page or your own profile, so
nothing here can hallucinate.
"""
from __future__ import annotations

import re
import textwrap

from core import config


def _first_sentence(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return ""
    m = re.match(r"(.{20,%d}?[.!?])\s" % limit, text + " ")
    out = (m.group(1) if m else text[:limit]).strip()
    return out


def observation(profile: dict) -> str:
    """One specific, verifiable thing about the prospect - or an honest blank."""
    desc = _first_sentence(profile.get("description", ""))
    if desc:
        return desc
    title = profile.get("title", "")
    if title:
        return title.strip()
    return ""


def company_name(profile: dict, fallback: str = "", preferred: str = "") -> str:
    """Pull a usable company name out of a page title.

    `preferred` is the name you curated in profiles/targets.yaml, and it wins
    outright - a hand-written "CricTracker" beats anything scraped. Page titles
    are usually "Brand - tagline" or "Brand | Category", so the brand is the
    part worth putting in a subject line; a title that is really a keyword list
    ("Cricket Live Score, Cricket News, Predictions, Stats") is cut at the
    first comma rather than pasted into the subject whole.
    """
    preferred = (preferred or "").strip()
    if preferred and len(preferred) <= 48:
        return preferred
    title = (profile.get("title") or "").strip()
    if not title:
        return fallback
    parts = [p.strip() for p in
             re.split(r"\s+[-|\u2013\u2014:]\s+|,", title) if p.strip()]
    generic = {"home", "homepage", "index", "welcome", "official site",
               "official website", "welcome to"}
    for part in parts:
        if part.lower() in generic or len(part) < 3:
            continue
        return re.sub(r"^(welcome to)\s+", "", part, flags=re.I).strip()[:60]
    return (parts[0] if parts else title or fallback)[:60]


def greeting(contact: dict) -> str:
    name = (contact.get("name") or "").strip().split(" ")[0]
    return f"Hi {name}," if name and name.isalpha() else "Hi there,"


def signature() -> str:
    name = config.get("OPERATOR_NAME", "Vineet")
    links = []
    for key, label in (("YOUTUBE_CHANNEL_URL", "Channel"),
                       ("PORTFOLIO_URL", "Portfolio"),
                       ("WEBSITE_URL", "Site")):
        v = config.get(key)
        if v:
            links.append(f"{label}: {v}")
    return name + (("\n" + "\n".join(links[:2])) if links else "")


def compose(greet: str, paragraphs: list[str], ask: str) -> str:
    body = [greet, ""]
    for p in paragraphs:
        if p and p.strip():
            body.append(textwrap.fill(p.strip(), width=78))
            body.append("")
    body.append(textwrap.fill(ask.strip(), width=78))
    body.append("")
    body.append(signature())
    return "\n".join(body).strip()
