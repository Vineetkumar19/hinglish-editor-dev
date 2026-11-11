"""What gets written to a client, at each stage of the deal.

Four different readers, four different openings. An agency wants to know you
can take a brief and disappear; a brand wants to know you will not need
managing; a creator wants to know you understand retention; a course seller
wants volume and consistency. The same email to all four converts on none of
them.

Every sentence is assembled from profiles/master_resume_video.yaml and the rate
card. Nothing here claims work he has not done, and no number appears that is
not in the card - the model's job is which of these to say, not what is true.
"""
from __future__ import annotations

import pathlib

from core import config
from core.log import get_logger
from core.yamlite import load_yaml

from .quote import Quote, deposit_line

log = get_logger("video.pitch")

_PROFILE: dict | None = None


def profile_path() -> pathlib.Path:
    return pathlib.Path(config.get("RESUME_VIDEO_FILE",
                                   str(config.profiles_dir() /
                                       "master_resume_video.yaml")))


def load_profile(refresh: bool = False) -> dict:
    global _PROFILE
    if _PROFILE is None or refresh:
        path = profile_path()
        _PROFILE = load_yaml(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _PROFILE or {}


def portfolio_links() -> list[str]:
    out = [config.get("PORTFOLIO_URL", "").strip(),
           config.get("SHOWREEL_URL", "").strip()]
    site = (load_profile().get("contact") or {}).get("website", "").strip()
    if site and not site.startswith("http"):
        site = "https://" + site
    out.append(site)
    return [u for u in out if u]


def signature() -> str:
    p = load_profile()
    lines = [p.get("name") or config.get("OPERATOR_NAME", "Vineet")]
    email = ((p.get("contact") or {}).get("email") or "").strip() \
        or config.get("OPERATOR_EMAIL", "")
    if email:
        lines.append(email)
    links = portfolio_links()
    if links:
        lines.append(links[0])
    return "\n".join(lines)


# What to lead with, by who is reading. Each is one sentence, because the
# opening line decides whether the second one is read.
OPENINGS = {
    "agency": "I work as a freelance editor and motion designer, and I am used "
              "to taking a brief, hitting a deadline and not needing managing.",
    "brand": "I am a freelance editor and motion designer - I cut the video, "
             "build the motion graphics, grade it and mix it, so there is one "
             "person to brief rather than four.",
    "creator": "I am a freelance editor who cuts for retention: the first two "
               "seconds, the pacing, and the graphics that keep someone "
               "watching to the end.",
    "coach": "I am a freelance editor who works on recurring content - the "
             "same look, the same turnaround, every week, so your series stays "
             "consistent without you checking it.",
    "unknown": "I am a freelance video editor and motion designer, working in "
               "Premiere Pro, After Effects and DaVinci Resolve.",
}

# The one capability worth naming, by reader. More than one reads as a list of
# software rather than a person who can help.
HOOKS = {
    "agency": "Motion graphics in After Effects and node-based grading in "
              "Resolve, delivered to spec.",
    "brand": "Explainers and product films: script to screen, including the "
             "motion graphics and the sound.",
    "creator": "Long-form story edits and short-form verticals, with the "
               "titles and lower thirds built rather than templated.",
    "coach": "Repeatable design systems - one set of titles, transitions and "
             "lower thirds that every episode reuses.",
    "unknown": "Edit, motion graphics, colour grade and sound design, all in "
               "house.",
}


def _skill_line() -> str:
    skills = load_profile().get("skills") or {}
    tools = []
    for group in ("editing", "motion", "colour", "audio"):
        for item in (skills.get(group) or [])[:1]:
            tools.append(str(item))
    return ", ".join(tools)


def opening_pitch(gig: dict, observation: str = "") -> dict:
    """The first message. Asks for a reply, never quotes a price."""
    kind = gig.get("kind") or "unknown"
    company = gig.get("company") or "your team"
    role = (gig.get("title") or "video editing").strip()

    paras = []
    if observation:
        paras.append(f"I saw your posting for {role} at {company} - "
                     f"{observation.strip().rstrip('.')}.")
    else:
        paras.append(f"I saw your posting for {role} at {company}.")
    paras.append(OPENINGS.get(kind, OPENINGS["unknown"]))
    paras.append(HOOKS.get(kind, HOOKS["unknown"]))

    links = portfolio_links()
    if links:
        paras.append("Work: " + " | ".join(links[:2]))
    else:
        paras.append("Happy to send a reel and two recent edits.")

    paras.append("Is this still open, and what length and volume are you "
                 "working with? I can come back with a rate the same day.")

    # "Freelance Video Editor - freelance editor available" is what happens
    # when the role title already carries the word.
    tail = "available this week" if "freelance" in role.lower() \
        else "freelance editor available"
    subject = f"{role} - {tail}"[:88]
    return {"subject": subject,
            "body": "Hi,\n\n" + "\n\n".join(paras) + "\n\n" + signature(),
            "stage": "opening",
            "personalisation_note": observation[:200] or f"pitched as {kind}"}


def rate_reply(gig: dict, quote: Quote, *, samples: bool = True,
               amount: float | None = None) -> dict:
    """They replied. Send the number, the scope, and the deposit terms."""
    company = gig.get("company") or "your team"
    paras = [f"Thanks for coming back to me."]

    if quote.missing:
        paras.append("PLACEHOLDER - no rate card is configured, so no price "
                     "can go in this email. Fill in profiles/video_rates.yaml "
                     "before sending.")
    else:
        total = quote.ask if amount is None else amount
        paras.append(f"For {quote.tier_name.lower()}, my rate is "
                     f"{quote.money(total)} {quote.unit}. "
                     f"Turnaround is subject to the source footage and agreed schedule.")
        if quote.note:
            paras.append(quote.note)
        rules = (load_yaml(pathlib.Path(config.get(
            "VIDEO_RATES_FILE",
            str(config.profiles_dir() / "video_rates.yaml"))
        ).read_text(encoding="utf-8")) or {}).get("rules") or {}
        revisions = rules.get("revisions_included")
        if revisions:
            paras.append(f"That includes {revisions} rounds of revisions.")
        line = deposit_line(quote, total)
        if line:
            paras.append(line)

    if samples:
        links = portfolio_links()
        if links:
            paras.append("Closest samples to what you described: "
                         + " | ".join(links[:2]))

    paras.append("If that works, we can agree a start date after reviewing the files. "
                 "If the budget is somewhere else, tell me the number you had "
                 "in mind and I will say straight away whether I can do it.")
    return {"subject": f"Rates - {company}"[:88],
            "body": "Hi,\n\n" + "\n\n".join(paras) + "\n\n" + signature(),
            "stage": "rate"}


def counter_reply(gig: dict, quote: Quote, counter) -> dict:
    """They named a number below the ask but above the floor."""
    paras = ["Thanks - that is workable with one change."]
    paras.append(f"I can do {quote.money(counter.amount)} {quote.unit} "
                 f"if we go with {counter.give}.")
    paras.append("Everything else stays as described: same delivery, same "
                 "turnaround, and I still send the edit for approval before "
                 "anything is final.")
    line = deposit_line(quote, counter.amount)
    if line:
        paras.append(line)
    paras.append("Say the word and I will send the invoice for the deposit.")
    return {"subject": f"Re: rates - {gig.get('company', '')}"[:88],
            "body": "Hi,\n\n" + "\n\n".join(paras) + "\n\n" + signature(),
            "stage": "counter"}


# --------------------------------------------------------------------------
# chasing
# --------------------------------------------------------------------------
# Most freelance work is lost to silence, not to a no. Three touches, each one
# saying something new - a chase that only says "just following up" teaches the
# reader that ignoring you costs nothing.
FOLLOW_UPS = [
    (3, "short", "Bumping this in case it landed at a bad moment. Still "
                 "available for the {role} work, and I can start this week."),
    (8, "value", "One thought since I wrote: for {company} I would put the "
                 "first cut in front of you within {turnaround} of getting the "
                 "files, so you can see the pacing before anything is locked."),
    (18, "close", "Last one from me - I will not keep writing. If the work is "
                  "still live later in the year, my rates and turnaround are "
                  "in the earlier email and the door is open."),
]


def follow_up(gig: dict, index: int, quote: Quote | None = None) -> dict | None:
    """The nth chase, or None when it is time to stop."""
    if index < 0 or index >= len(FOLLOW_UPS):
        return None
    _, name, template = FOLLOW_UPS[index]
    body = template.format(
        role=(gig.get("title") or "editing").lower(),
        company=gig.get("company") or "you",
        turnaround=(quote.turnaround if quote and quote.turnaround else "a few days"))
    return {"subject": f"Re: {gig.get('title', 'video editing')}"[:88],
            "body": "Hi,\n\n" + body + "\n\n" + signature(),
            "stage": f"follow_up_{name}"}


def due_after_days(index: int) -> int:
    return FOLLOW_UPS[index][0] if 0 <= index < len(FOLLOW_UPS) else 0
