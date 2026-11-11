"""What the model is told before it writes, and what is done with what it wrote.

The templates in pitch.py are safe because every sentence in them is assembled
from a fact in the profile. A model is worth using instead only if it is given
the same facts AND the brand's own words, and is held to the same standard: it
may choose what to say about the brand, it may not invent anything about the
channel.

So the brief below is strict about the division of labour.

  The model decides   - what this brand actually sells and would want, which
                        detail from their site to open on, and how to phrase
                        the ask for email, WhatsApp and Instagram.
  The code decides    - the numbers, the links, the sign-off, the deal type,
                        and the categories that are refused outright.

`finish()` puts the code's half back on afterwards, so a model that hallucinates
a subscriber count or signs off as the wrong person cannot get that into a sent
message.
"""
from __future__ import annotations

import re
import textwrap

from core import config

from . import pitch as pitch_mod

# The model is asked for the message only. Everything identifying is appended
# by finish(), so `body` here is deliberately sign-off free.
PITCH_SCHEMA = {
    "type": "object",
    "required": ["reads_as", "subject", "body", "whatsapp", "instagram_dm"],
    "properties": {
        # Written first on purpose: a model that has just stated what the brand
        # sells writes a noticeably more specific email than one that goes
        # straight to the pitch. It is also what gets shown on the approval
        # card, so a bad read is visible before anything is sent.
        "reads_as": {"type": "string", "min_length": 10, "max_length": 400},
        "subject": {"type": "string", "min_length": 8, "max_length": 88},
        "body": {"type": "string", "min_length": 100, "max_length": 1600},
        "whatsapp": {"type": "string", "max_length": 700, "default": ""},
        "instagram_dm": {"type": "string", "max_length": 500, "default": ""},
        "personalisation_note": {"type": "string", "max_length": 300, "default": ""},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
    },
}

# What to ask for, by what is realistically on the table. The model phrases it;
# it does not choose it.
ASK_BY_DEAL = {
    "cash": ("a paid promotion inside a cricket video - a dedicated segment, "
             "not a banner. Ask whether they run creator partnerships and who "
             "looks after them. Do not name a price."),
    "agency": ("a place on their creator roster, so they bring paid brand work. "
               "Ask whether they take creator submissions and what they need "
               "to consider one."),
    "barter": ("a collaboration where they send product and get a video "
               "segment for it. Offer to send the edit for approval before it "
               "goes live."),
    "affiliate": ("their affiliate or referral programme."),
}


def _facts(creator: dict) -> str:
    lines = []
    for f in pitch_mod.audience_facts(creator):
        lines.append(f"- {f}")
    if not lines:
        lines.append("- the channel is new and the numbers are small; do not "
                     "quote any audience figure at all")
    craft = pitch_mod.craft_line(creator)
    if craft:
        lines.append(f"- {craft}")
    for w in pitch_mod.best_work_links(creator, limit=2):
        title = (w.get("title") or "a recent video").strip()
        lines.append(f"- a video worth linking: {title} - {w['url']}")
    deliverables = [str(d).strip() for d in (creator.get("deliverables") or [])
                    if str(d).strip()]
    if deliverables:
        lines.append("- can deliver: " + "; ".join(deliverables[:4]))
    return "\n".join(lines)


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
    """The brief. `ctx` is what n_draft passes: current, profile, contact."""
    cur = ctx.get("current") or {}
    prof = ctx.get("profile") or {}
    contact = ctx.get("contact") or {}
    brand = dict(cur.get("meta") or {})
    creator = pitch_mod.load_creator()

    name = brand.get("name") or prof.get("title") or cur.get("domain", "the brand")
    deal = pitch_mod.deal_type(brand)
    ask = ASK_BY_DEAL.get(deal, ASK_BY_DEAL["cash"])
    segment = (brand.get("segment") or "").replace("_", " ")
    site_text = (prof.get("text") or "").strip()
    who = contact.get("name") or ""

    # A site that refused to load is the one case where there is nothing to be
    # specific about, and the model must be told so rather than left to fill
    # the gap with flattery.
    # How much of their site the model gets to read. More is better: the point
    # of this agent is that it read the brand, and a detail worth opening on is
    # as likely to be on the third page as the first. Speed is not a reason to
    # lower it.
    site_text = site_text[:config.get_int("PITCH_SITE_CHARS", 6000)]
    if len(site_text) < 200:
        site_block = ("Their site could not be read. Say plainly that you are "
                      "writing without having been able to read much of their "
                      "site, and keep the message short. Invent nothing about "
                      "them.")
    else:
        site_block = "Their own website says:\n---\n" + site_text + "\n---"

    return _fill(f"""
        You are writing the first approach to an Indian brand on behalf of a
        cricket creator on YouTube and Instagram. Read the brand first, then
        write. A generic message is worse than no message.

        THE BRAND
        - Name: {name}
        - Website: {cur.get('domain', '')}
        - Category on our list: {segment or 'unknown'}
        {'- Person to address: ' + who if who else '- No named person; address the team'}

        {site_block}

        THE CREATOR, in facts. These are the ONLY facts about the channel you
        may use. Do not add, round up, or estimate any other number.
        {_facts(creator)}

        WHAT TO ASK FOR
        This brand is being approached for {ask}

        STEP 1 - fill "reads_as": in one or two sentences, from their own words
        above, what does this brand sell, who buys it, and is there any sign
        they already work with creators or run campaigns? If their site does
        not say, write that it does not say.

        STEP 2 - write "subject" and "body", an email under 150 words.
        - Open with one concrete detail from their site - a product, a claim, a
          launch, a line from their about page. Near-quote it. If you had
          nothing to read, say so instead of guessing.
        - Then one or two sentences on why a cricket audience fits what they
          sell. Make the connection to THEIR product, not to cricket in general.
        - Then the ask above, as a question, at the end.
        - No sign-off, no name, no "Regards", no contact details. Those are
          added automatically after you finish. End on the question.

        STEP 3 - write "whatsapp": the same approach for WhatsApp, under 60
        words, no subject line, no sign-off.

        STEP 4 - write "instagram_dm": the same approach as a DM, under 40
        words, no sign-off.

        RULES, all three messages
        - Plain text. No markdown, no bullet points, no emoji.
        - Never promise sales, views, reach or any result.
        - Never mention betting, fantasy sports, casino or any real-money
          gaming, even if their site does - promoting it is illegal in India.
        - No flattery that is not backed by something on their site. "I love
          your brand" is banned; quoting what they say about themselves is not.
        - Never write "I hope this finds you well", "just circling back",
          "quick question", "risk-free", "guaranteed" or "limited time".
        - Write as a person who watched their site for two minutes, not as
          marketing copy.
    """).strip()


# --------------------------------------------------------------------------
# putting the code's half back on
# --------------------------------------------------------------------------
_SIGNOFF = re.compile(
    r"\n+\s*(best|regards|best regards|thanks|thank you|cheers|warm regards|"
    r"sincerely|yours|looking forward)[,.!]*\s*(\n.*)?$",
    re.I | re.S)


def strip_signoff(body: str, creator: dict) -> str:
    """Remove a sign-off the model added anyway.

    Models add one about half the time whatever the instruction says, and two
    sign-offs in one email is the single most obvious tell that a machine wrote
    it. Cutting it here is more reliable than asking again.
    """
    body = (body or "").strip()
    body = _SIGNOFF.sub("", body).strip()
    name = (creator.get("name") or "").strip()
    email = ((creator.get("contact") or {}).get("email") or "").strip()
    keep = []
    for line in body.splitlines():
        bare = line.strip()
        low = bare.lower()
        if not bare:
            keep.append(line)
            continue
        # A trailing line that is just the name, the address or a channel link
        # is part of a signature, not of the message.
        if bare == name or (email and email.lower() in low):
            continue
        if re.fullmatch(r"(https?://\S+|@[\w.]+)", bare):
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def finish(draft: dict, ctx: dict) -> dict:
    """Attach the signature and the facts the model was not trusted with."""
    creator = pitch_mod.load_creator()
    out = dict(draft)
    sig = pitch_mod.signature(creator)

    # The written template already signs off, and this runs on that too when the
    # model was unavailable. Re-signing a signed message is the one way this
    # step can make things worse, so check first.
    if not (out.get("body") or "").rstrip().endswith(sig):
        body = strip_signoff(out.get("body", ""), creator)
        out["body"] = f"{body}\n\n{sig}".strip()

    # The templated pitch already carries the operator's email inside the
    # WhatsApp and DM text; a model writing them fresh will not, and a brand
    # that wants to reply by mail needs somewhere to reply to.
    email = ((creator.get("contact") or {}).get("email") or "").strip() \
        or config.get("OPERATOR_EMAIL", "")
    for key, limit in (("whatsapp", 700), ("instagram_dm", 500)):
        text = (out.get(key) or "").strip()
        if not text:
            continue
        text = strip_signoff(text, creator)
        first = (creator.get("name") or config.get("OPERATOR_NAME", "")).split(" ")[0]
        tail = f"\n\n- {first}" if first else ""
        if email and email.lower() not in text.lower() and len(text) + 40 < limit:
            tail = f"\n\n- {first} ({email})" if first else f"\n\n{email}"
        out[key] = (text + tail).strip()[:limit]

    note = (out.get("personalisation_note") or "").strip()
    out["personalisation_note"] = (note or out.get("reads_as", ""))[:300]
    return out
