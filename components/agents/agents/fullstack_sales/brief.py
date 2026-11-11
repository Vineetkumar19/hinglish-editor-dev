"""What the model is told before it writes to a development client.

Same division of labour as the other three, because it has held up:

  The model decides - what this client is actually stuck on, which detail of
                      their posting to open on, and how to say it.
  The code decides  - the price, the floor, the deposit, the signature, and
                      the rule that the first email carries no number.

The one thing that is different here is the opening. A developer pitching a
broken checkout has an advantage nobody else in the inbox has: he can name the
actual failure. "Your webhook is probably not verifying the signature" from a
stranger reads as competence in a way that no amount of "passionate about
clean code" ever will. The brief pushes hard for that, and just as hard
against guessing when the posting does not say.
"""
from __future__ import annotations

import textwrap

from core import config

PITCH_SCHEMA = {
    "type": "object",
    "required": ["reads_as", "likely_cause", "subject", "body"],
    "properties": {
        "reads_as": {"type": "string", "min_length": 10, "max_length": 400},
        # The technical read. Shown on the card so he can sanity-check it
        # before it goes out with his name on it.
        "likely_cause": {"type": "string", "max_length": 300, "default": ""},
        "subject": {"type": "string", "min_length": 8, "max_length": 88},
        "body": {"type": "string", "min_length": 100, "max_length": 1600},
        "personalisation_note": {"type": "string", "max_length": 300, "default": ""},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
    },
}

WHO_THEY_ARE = {
    "agency": "an agency that subcontracts build work. They care that you can "
              "take a spec, hit a date and not need managing in front of their "
              "own client.",
    "startup": "an early-stage startup. They care about shipping, and about "
               "not being left with code nobody can maintain.",
    "saas": "a SaaS business. Billing is their revenue, so correctness and "
            "reconciliation matter more to them than speed.",
    "ecommerce": "an online store. Every hour the checkout is wrong is money "
                 "they are not taking.",
    "smb": "a small business. They want it to work and to be explained in "
           "plain language, not in framework names.",
    "unknown": "someone who needs development work done; the posting does not "
               "say what kind of business they are.",
}

WORK_FRAMING = {
    "payment_rescue": "Their payment integration is BROKEN. This is the most "
                      "urgent kind of work there is and the opening should "
                      "show you know what usually causes it.",
    "payments": "They want a payment integration built or extended.",
    "rescue": "Something they have is broken and they want it fixed.",
    "backend": "Server-side work: APIs, data models, integrations.",
    "frontend": "Interface work in React or similar.",
    "fullstack": "A whole application, front end through database.",
    "mobile": "A mobile application.",
    "design": "Design work before or alongside the build.",
    "site": "A website or store build.",
    "unknown": "Development work; the posting does not make the shape clear.",
}

# The failures that actually cause most broken Indian and global checkouts.
# Given to the model as candidates to recognise, never as things to assert.
COMMON_FAULTS = """
- webhook signature verification failing, usually the raw request body being
  parsed to JSON before the signature is computed
- the webhook endpoint not reachable, or returning a non-2xx so the gateway
  retries and then gives up
- orders marked paid on the client-side redirect instead of on the webhook, so
  a closed browser loses the order
- no idempotency on the webhook handler, so a retry creates a duplicate order
  or a double refund
- capture never called after authorisation, so money is held and not taken
- UPI collect requests timing out with no reconciliation job to catch them
- test-mode keys left in production, or the reverse
- refunds and partial refunds not written back to the order
"""


def _fill(text: str) -> str:
    lines = [ln[8:] if ln.startswith(" " * 8) else ln
             for ln in text.strip("\n").splitlines()]
    return "\n".join(lines).strip()


def build_prompt(ctx: dict) -> str:
    gig = ctx.get("gig") or {}
    pkg = ctx.get("package") or {}
    profile = ctx.get("profile") or {}
    work = gig.get("work_kind") or "unknown"
    client = gig.get("client_kind") or "unknown"

    skills = profile.get("skills") or {}
    stack = ", ".join(
        str(x) for group in ("languages", "backend", "databases", "frontend")
        for x in (skills.get(group) or [])[:5])

    posting = (gig.get("description") or "").strip()
    if len(posting) < 120:
        posting_block = ("Their posting could not be read beyond the title. Say "
                         "plainly that you are writing off the title alone, keep "
                         "it short, and invent nothing about them.")
    else:
        posting_block = ("Their posting says:\n---\n"
                         + posting[:config.get_int("PITCH_SITE_CHARS", 6000)]
                         + "\n---")

    faults = COMMON_FAULTS if work in ("payment_rescue", "payments") else ""
    faults_block = (f"""
        FAILURES THAT CAUSE MOST BROKEN CHECKOUTS. Use these to recognise what
        they are describing. Name at most ONE, and only when their own words
        point at it. If their description does not say enough, ask one specific
        diagnostic question instead of guessing - a wrong guess stated
        confidently is worse than no guess at all.
        {faults}""" if faults else "")

    return _fill(f"""
        You are writing the first message to someone who has publicly asked for
        development work. Read their posting first, then write. A generic
        application is worse than none.

        THE CLIENT
        - Name: {gig.get('company', 'unknown')}
        - They advertised: {gig.get('title', '')}
        - Where: {gig.get('location', 'not stated')}
        - They look like {WHO_THEY_ARE.get(client, WHO_THEY_ARE['unknown'])}
        - The work: {WORK_FRAMING.get(work, WORK_FRAMING['unknown'])}

        {posting_block}
        {faults_block}
        THE DEVELOPER YOU ARE WRITING FOR. These are the only capabilities you
        may claim. Do not add languages, frameworks or clients not listed here.
        - {profile.get('headline', 'Software Engineer')}
        - Stack: {stack}
        - Specialism: payment integrations - Razorpay, Stripe, UPI, PayU,
          Cashfree: checkout, webhooks, signature verification, refunds,
          reconciliation, subscriptions and marketplace payouts.
        - He works end to end: design, front end, API, database, deployment.

        WHAT THIS IS WORTH, for your information only
        - It reads as: {pkg.get('label') or 'a build priced by the day'}
        - DO NOT put any price, rate, range, currency or day count in this
          email. The number goes out only after they reply. An opening email
          with a price in it is filtered on budget before anyone reads it.

        STEP 1 - fill "reads_as": in one or two sentences, from their own
        words, what are they actually trying to do and what is in their way? If
        the posting does not say, write that it does not say.

        STEP 2 - fill "likely_cause": if something of theirs is broken, the one
        most likely technical cause, in one sentence. If nothing is broken, or
        their description does not support a guess, leave it empty. Never fill
        this with a guess you could not defend on a call.

        STEP 3 - write "subject" and "body", an email under 150 words.
        - Open with one concrete detail from their posting. Near-quote it.
        - Then the single most useful thing you can say: for broken work, the
          likely cause or the one question that would identify it; for a build,
          the part of their description that is usually underestimated.
        - One sentence on relevant experience. Specific, not a list of tools.
        - End with a question that is easy to answer.
        - No sign-off, no name, no contact details. Those are added afterwards.

        RULES
        - Plain text. No markdown, no bullet points, no emoji, no code blocks.
        - Never promise a delivery date before seeing their code.
        - Never claim to have worked with their company, product or industry.
        - Never say "passionate", "rockstar", "ninja", "guru", "I hope this
          finds you well", "I am reaching out" or "clean, maintainable code".
        - Never offer to do a free trial task or an unpaid proof of concept.
        - Write like an engineer who read the ticket, not like an applicant.
    """)


def finish(draft: dict, ctx: dict) -> dict:
    """Put back the parts the model is not trusted with."""
    from agents.sponsorship.brief import strip_signoff
    from agents.job_hunter.resume import load_master
    out = dict(draft)
    try:
        profile = load_master()
    except Exception:  # noqa: BLE001
        profile = {}
    contact = profile.get("contact") or {}
    name = profile.get("name") or config.get("OPERATOR_NAME", "Vineet")
    email = (contact.get("email") or "").strip() or config.get("OPERATOR_EMAIL", "")
    sig_lines = [name]
    if email:
        sig_lines.append(email)
    for key in ("github", "website"):
        value = (contact.get(key) or "").strip()
        if value:
            sig_lines.append(value if value.startswith("http") else "https://" + value)
            break
    sig = "\n".join(sig_lines)

    body = strip_signoff(out.get("body", ""), {"name": name,
                                               "contact": {"email": email}})
    out["body"] = f"{body}\n\n{sig}".strip()
    note = (out.get("personalisation_note") or "").strip()
    out["personalisation_note"] = (note or out.get("reads_as", ""))[:300]
    return out
