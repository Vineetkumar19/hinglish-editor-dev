"""What the model is told before it writes to a client.

Same division of labour as the sponsorship brief, because it was the right one:

  The model decides   - what this client actually needs, which detail from
                        their own posting to open on, and how to say it.
  The code decides    - the rate, the floor, the portfolio links, the
                        signature, and the rule that the first email carries
                        no price.

Plus the thing that makes it improve: every rule he has taught this agent by
rejecting or rewriting a draft goes into the prompt, so a complaint made once
is obeyed forever rather than having to be made again.
"""
from __future__ import annotations

import textwrap

from core import config

from . import pitch as pitch_mod

PITCH_SCHEMA = {
    "type": "object",
    "required": ["reads_as", "subject", "body"],
    "properties": {
        # Written first on purpose: a model that has just stated what the
        # client needs writes a far more specific email than one that goes
        # straight to the pitch. It is also what the card shows, so a bad read
        # is visible before anything is sent.
        "reads_as": {"type": "string", "min_length": 10, "max_length": 400},
        "subject": {"type": "string", "min_length": 8, "max_length": 88},
        "body": {"type": "string", "min_length": 100, "max_length": 1500},
        "personalisation_note": {"type": "string", "max_length": 300, "default": ""},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
    },
}

WHO_THEY_ARE = {
    "agency": "an agency or studio that subcontracts editing. They care that "
              "you can take a brief, hit a deadline and not need managing.",
    "brand": "a company hiring for their own marketing. They care that there "
             "is one person to brief rather than four, and that it looks "
             "professional enough to put their name on.",
    "creator": "a creator hiring for their own channel. They care about "
               "retention - the first two seconds, the pacing, the graphics "
               "that keep someone watching.",
    "coach": "someone selling courses, coaching or a podcast. They care about "
             "volume, consistency and a turnaround they can plan around.",
    "unknown": "someone hiring a video editor; the posting does not say what "
               "kind of outfit they are.",
}


def _fill(text: str) -> str:
    """Dedent a prompt AFTER interpolation, block by block.

    textwrap.dedent() strips the COMMON leading whitespace, and any block
    interpolated at column 0 - a site's text, a posting - makes that common
    prefix empty. The template then reaches the model with ragged 8-space
    indentation on every line it wrote and none on the parts it quoted, which
    is exactly the kind of noise a small model reads as structure.
    """
    lines = []
    for line in text.strip("\n").splitlines():
        lines.append(line[8:] if line.startswith(" " * 8) else line)
    return "\n".join(lines).strip()


def build_prompt(ctx: dict) -> str:
    """ctx carries the gig, the quote, and the lessons block."""
    gig = ctx.get("gig") or {}
    quote = ctx.get("quote") or {}
    profile = pitch_mod.load_profile()
    skills = profile.get("skills") or {}

    def top(group, n=3):
        return ", ".join(str(x) for x in (skills.get(group) or [])[:n])

    kind = gig.get("kind") or "unknown"
    posting = (gig.get("description") or "").strip()
    if len(posting) < 120:
        posting_block = ("Their posting could not be read beyond the title. Say "
                         "plainly that you are writing off the title alone, keep "
                         "it short, and invent nothing about them.")
    else:
        posting_block = ("Their posting says:\n---\n"
                         + posting[:config.get_int("PITCH_SITE_CHARS", 6000)]
                         + "\n---")

    links = pitch_mod.portfolio_links()
    links_line = " | ".join(links[:2]) if links else "(none configured)"

    return _fill(f"""
        You are writing the first message to someone who has publicly advertised
        that they want to hire a video editor. Read their posting first, then
        write. A generic application is worse than none.

        THE CLIENT
        - Name: {gig.get('company', 'unknown')}
        - Role advertised: {gig.get('title', '')}
        - Where: {gig.get('location', 'not stated')}
        - They look like {WHO_THEY_ARE.get(kind, WHO_THEY_ARE['unknown'])}

        {posting_block}

        THE EDITOR YOU ARE WRITING FOR. These are the only capabilities you may
        claim. Do not add software, credits or clients that are not listed.
        - Editing: {top('editing')}
        - Motion graphics: {top('motion')}
        - Colour: {top('colour')}
        - Audio: {top('audio')}
        - He does all of it himself, so there is one person to brief.
        - Portfolio to link: {links_line}

        WHAT THIS JOB IS WORTH, for your information only
        - It reads as: {quote.get('tier_name', 'a standard edit')}
        - DO NOT put any price, rate, range or currency in this email. The rate
          goes out only after they reply. An opening email with a number in it
          gets filtered on budget before anyone reads the rest.

        STEP 1 - fill "reads_as": in one or two sentences, from their own words,
        what do they actually need, how often, and what would make someone good
        at it? If the posting does not say, write that it does not say.

        STEP 2 - write "subject" and "body", an email under 150 words.
        - Open with one concrete detail from their posting. Near-quote it.
        - Then one or two sentences connecting what they need to what he
          actually does. Name the specific capability, not all of them.
        - Include the portfolio link above, exactly as written.
        - End with a question that is easy to answer: whether it is still open,
          and what length and volume they are working with.
        - No sign-off, no name, no contact details. Those are added afterwards.

        RULES
        - Plain text. No markdown, no bullet points, no emoji.
        - Never promise views, growth, engagement or revenue.
        - Never claim to have watched their videos or worked with their brand.
        - No flattery that is not backed by something in their posting.
        - Never write "I hope this finds you well", "I am reaching out",
          "passionate", "rockstar", "ninja" or "guru".
        - Write like a working editor who read the ad, not like an application.
    """).strip()


def finish(draft: dict, ctx: dict) -> dict:
    """Put back the parts the model is not trusted with."""
    from agents.sponsorship.brief import strip_signoff
    out = dict(draft)
    profile = pitch_mod.load_profile()
    sig = pitch_mod.signature()
    body = strip_signoff(out.get("body", ""), profile)
    out["body"] = f"{body}\n\n{sig}".strip()
    note = (out.get("personalisation_note") or "").strip()
    out["personalisation_note"] = (note or out.get("reads_as", ""))[:300]
    return out
