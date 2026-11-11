"""What to send once a development client replies.

Kept apart from brief.py because these are not model output. Once a number is
involved, every sentence around it is assembled in code from the rate card -
there is no version of "the model phrased the payment terms" that is worth the
risk.
"""
from __future__ import annotations

from core import config

from .packages import Package, deposit_line, rules


def _signature() -> str:
    try:
        from agents.job_hunter.resume import load_master
        profile = load_master()
    except Exception:  # noqa: BLE001
        profile = {}
    contact = profile.get("contact") or {}
    lines = [profile.get("name") or config.get("OPERATOR_NAME", "Vineet")]
    email = (contact.get("email") or "").strip() or config.get("OPERATOR_EMAIL", "")
    if email:
        lines.append(email)
    for key in ("github", "website"):
        value = (contact.get(key) or "").strip()
        if value:
            lines.append(value if value.startswith("http") else "https://" + value)
            break
    return "\n".join(lines)


def rate_reply(gig: dict, pkg: Package, *, amount: float | None = None) -> dict:
    total = pkg.ask if amount is None else amount
    company = gig.get("company") or "your team"
    paras = ["Thanks for coming back to me."]

    if pkg.missing:
        paras.append("PLACEHOLDER - no rate card is configured, so no price "
                     "can go in this email. Fill in profiles/dev_rate_card.yaml "
                     "before sending.")
    else:
        paras.append(f"For {pkg.label.lower()}, my price is {pkg.money(total)}"
                     + (f", {pkg.turnaround}." if pkg.turnaround else "."))
        if pkg.note:
            paras.append(pkg.note)
        r = rules()
        if r.get("revisions_included"):
            paras.append(f"That includes {r['revisions_included']} rounds of "
                         f"changes after delivery.")
        # The sentence that decides whether he gets paid.
        line = deposit_line(pkg, total)
        if line:
            paras.append(line)
        paras.append("I work in test mode against your sandbox keys until it "
                     "is signed off, so nothing touches live payments until "
                     "you are happy with it.")

    paras.append("If the budget is somewhere else, tell me the number you had "
                 "in mind and I will say straight away whether I can do it.")
    return {"subject": f"Scope and price - {company}"[:88],
            "body": "Hi,\n\n" + "\n\n".join(paras) + "\n\n" + _signature(),
            "stage": "rate"}


def counter_reply(gig: dict, pkg: Package, counter) -> dict:
    paras = ["Thanks - that is workable with one change.",
             f"I can do {pkg.money(counter.amount)} if we go with "
             f"{counter.give}.",
             "Everything else stays as described, including the sign-off in "
             "test mode before anything goes live."]
    line = deposit_line(pkg, counter.amount)
    if line:
        paras.append(line)
    paras.append("Say the word and I will send the invoice for the deposit.")
    return {"subject": f"Re: scope and price - {gig.get('company', '')}"[:88],
            "body": "Hi,\n\n" + "\n\n".join(paras) + "\n\n" + _signature(),
            "stage": "counter"}


# Two touches then stop. Development buyers move slower than video clients, so
# the gaps are wider.
FOLLOW_UPS = [
    (4, "Bumping this in case it landed at a bad moment. Still available for "
        "the {title}, and I can start this week."),
    (12, "Last one from me. If it is still open later, the scope and price are "
         "in the earlier email and nothing about them changes."),
]


def follow_up(gig: dict, index: int) -> dict | None:
    if index < 0 or index >= len(FOLLOW_UPS):
        return None
    _, template = FOLLOW_UPS[index]
    body = template.format(title=(gig.get("title") or "work").lower())
    return {"subject": f"Re: {gig.get('title', 'development work')}"[:88],
            "body": "Hi,\n\n" + body + "\n\n" + _signature(),
            "stage": f"follow_up_{index}"}


def due_after_days(index: int) -> int:
    return FOLLOW_UPS[index][0] if 0 <= index < len(FOLLOW_UPS) else 0
