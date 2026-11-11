"""What the model is told before it writes about the product.

Four audiences, four genuinely different emails:

  user       wants to know whether it solves a problem they actually have
  promoter   wants to know whether their audience will thank them for it
  agency     wants to know what it does to their throughput and their margin
  directory  is not a person - it is a submission with a form

And one constraint that outranks all of them: the product is not finished. The
brief is built around saying that plainly rather than hiding it, because the
alternative - a confident email about software that does not exist - is the one
mistake in this whole suite that cannot be walked back. The people being
written to here are the people he needs as first customers, first partners and
first reviewers, and they all talk to each other.

The stage gate in product.py enforces this on the finished draft. The brief's
job is to make a draft that does not need blocking.
"""
from __future__ import annotations

from core import config

from . import product as prod

PITCH_SCHEMA = {
    "type": "object",
    "required": ["reads_as", "subject", "body"],
    "properties": {
        "reads_as": {"type": "string", "min_length": 10, "max_length": 400},
        "subject": {"type": "string", "min_length": 8, "max_length": 88},
        "body": {"type": "string", "min_length": 80, "max_length": 1400},
        "personalisation_note": {"type": "string", "max_length": 300, "default": ""},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
    },
}

AUDIENCE = {
    "user": {
        "who": "someone who edits video themselves, often enough that the "
               "repetitive passes cost them real hours every week.",
        "wants": "to know whether this removes a job they currently do by "
                 "hand. Nothing else in the email matters to them.",
        "ask": "whether the passes you listed are actually what eats their "
               "time, and whether they want to be told when it is ready.",
    },
    "promoter": {
        "who": "a creator whose channel is about editing tools and workflow. "
               "Their audience is exactly who this is for.",
        "wants": "to know whether their audience would thank them for it. A "
                 "creator who recommends a bad tool pays for it in trust, so "
                 "they are more sceptical than a user, not less.",
        "ask": "whether they would look at it early and say what is wrong "
               "with it, before any question of promoting it comes up.",
    },
    "agency": {
        "who": "an editing or production studio with more footage than people.",
        "wants": "to know what it does to throughput per editor. They think in "
                 "hours per deliverable, not features.",
        "ask": "how many hours a week their team spends on those passes today.",
    },
    "directory": {
        "who": "a tool directory or listing site - not a person.",
        "wants": "a short, factual description that fits their format.",
        "ask": "nothing. This is a submission, not a conversation.",
    },
}


def _fill(text: str) -> str:
    lines = [ln[8:] if ln.startswith(" " * 8) else ln
             for ln in text.strip("\n").splitlines()]
    return "\n".join(lines).strip()


def build_prompt(ctx: dict) -> str:
    target = ctx.get("target") or {}
    kind = target.get("kind") or "user"
    spec = AUDIENCE.get(kind, AUDIENCE["user"])
    about = ctx.get("about") or {}

    desc = (about.get("description") or "").strip()
    if len(desc) < 40:
        them = ("Their channel description could not be read. Say plainly that "
                "you found them through their work on editing and keep it "
                "short. Invent nothing about them.")
    else:
        them = ("What they say about themselves:\n---\n"
                + desc[:config.get_int("PITCH_SITE_CHARS", 3000)] + "\n---")
    size = f"\n- Audience size: {about['subscribers']}" if about.get("subscribers") else ""

    partner_block = ""
    if kind == "promoter":
        partner_block = _fill(f"""
        WHAT A PROMOTER IS BEING OFFERED TODAY
        {prod.partner_offer_block()}
        Do not lead with any of this. A creator who is pitched a commission by
        a stranger before they have seen the product assumes it is bad. Ask
        them to look at it first; the commercial side comes after they like it.
        """) + "\n"

    return _fill(f"""
        You are writing one email on behalf of a solo developer who is building
        a video editing tool. Read who they are first, then write.

        WHO YOU ARE WRITING TO
        - Name: {target.get('name', 'unknown')}
        - They are {spec['who']}{size}
        - Found because: {target.get('evidence', 'they publish about editing')}
        - What they actually want to know: {spec['wants']}

        {them}

        THE PRODUCT. These are the only things you may say about it.
        {prod.facts_block()}

        {prod.stage_rules_block()}

        {partner_block}
        STEP 1 - fill "reads_as": in one or two sentences, from their own
        words, what do they make and where would this fit into it? If their
        description does not say, write that it does not say.

        STEP 2 - write "subject" and "body". Under 130 words.
        - Open with one concrete thing about them, from their own description
          or the work you found them through. Near-quote it.
        - Say in one plain sentence what the tool does. Pick the ONE capability
          from the list above that matters most to this particular person, not
          all of them.
        - Say that it is not finished yet. Do not bury this and do not
          apologise for it - it is the reason the email is honest and the
          reason they might help.
        - End by asking: {spec['ask']}
        - No sign-off, no name, no links. Those are added afterwards.

        RULES
        - Plain text. No markdown, no bullets, no emoji.
        - Under 130 words. A cold email about an unfinished product earns
          about four sentences of attention.
        - Never say "I hope this finds you well", "I am reaching out",
          "game-changer", "revolutionary", "10x", "supercharge" or
          "I came across your channel and loved your content".
        - Never flatter. One specific observation beats any compliment.
        - Never suggest they promote it, share it, or tell their audience.
        - Write like one person emailing another about a thing they are
          building, because that is exactly what this is.
    """)


def finish(draft: dict, ctx: dict) -> dict:
    """Attach the signature, and whatever link the stage actually permits."""
    from agents.sponsorship.brief import strip_signoff
    p = prod.load_product()
    out = dict(draft)

    name = config.get("OPERATOR_NAME", "Vineet")
    email = config.get("OPERATOR_EMAIL", "")
    lines = [name]
    if email:
        lines.append(email)
    # The waitlist link is the only URL that is honest before launch, and only
    # if one actually exists.
    if prod.allows("waitlist") and str(p.get("waitlist_url") or "").strip():
        lines.append(p["waitlist_url"].strip())
    elif prod.stage() == "live" and str(p.get("url") or "").strip():
        lines.append(p["url"].strip())

    body = strip_signoff(out.get("body", ""),
                         {"name": name, "contact": {"email": email}})
    out["body"] = f"{body}\n\n" + "\n".join(lines)
    note = (out.get("personalisation_note") or "").strip()
    out["personalisation_note"] = (note or out.get("reads_as", ""))[:300]
    # The gate. Anything the stage does not support is reported on the card,
    # and the send node refuses to proceed while this is non-empty.
    out["claim_problems"] = prod.check_claims(out["body"] + " " +
                                              out.get("subject", ""))
    return out
