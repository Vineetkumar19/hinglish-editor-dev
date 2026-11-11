"""Building the actual messages: cold email, WhatsApp, and Instagram DM.

Three rules run through all of it.

Nothing is invented. Every number comes from profiles/creator.yaml, and a
field left at zero is left out of the message rather than estimated. A brand
can check a subscriber count in about thirty seconds, and being caught
inflating one ends the relationship before it starts.

The angle is theirs, not yours. A protein brand and an influencer agency are
being sold two different things, so the middle paragraph changes by segment
rather than a single template going out 113 times.

Channels are written separately. A WhatsApp message is not an email with the
paragraphs removed - it is three lines with one question at the end, because
that is what gets answered on a phone.
"""
from __future__ import annotations

import pathlib
import re
import urllib.parse

from core import config
from core.log import get_logger
from core.yamlite import load_yaml


def _sentence(s: str) -> str:
    """Upper-case the first letter only.

    str.capitalize() lower-cases everything after it, which turned "12.5K
    subscribers on YouTube" into "12.5k subscribers on youtube" in live emails.
    """
    s = (s or "").strip()
    return s[0].upper() + s[1:] if s else s

log = get_logger("sponsorship.pitch")

_CREATOR_CACHE: dict | None = None


def creator_path() -> pathlib.Path:
    return pathlib.Path(config.get("CREATOR_PROFILE",
                                   str(config.profiles_dir() / "creator.yaml")))


def load_creator(refresh: bool = False) -> dict:
    global _CREATOR_CACHE
    if _CREATOR_CACHE is not None and not refresh:
        return _CREATOR_CACHE
    p = creator_path()
    if not p.exists():
        log.warn(f"no creator profile at {p} - pitches will carry no numbers")
        _CREATOR_CACHE = {}
        return _CREATOR_CACHE
    try:
        _CREATOR_CACHE = load_yaml(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        log.warn(f"could not read creator profile: {exc}")
        _CREATOR_CACHE = {}
    return _CREATOR_CACHE


# --------------------------------------------------------------------------
# facts
# --------------------------------------------------------------------------
def _channel(creator: dict, platform: str) -> dict:
    for c in creator.get("channels") or []:
        if (c.get("platform") or "").lower() == platform:
            return c
    return {}


def _n(v) -> int:
    try:
        return int(str(v).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0


def human_number(n: int) -> str:
    """Indian-audience readable: 12,500 becomes 12.5K, 250000 becomes 2.5L."""
    if n >= 100000:
        val = n / 100000
        return f"{val:.1f}".rstrip("0").rstrip(".") + "L"
    if n >= 1000:
        val = n / 1000
        return f"{val:.1f}".rstrip("0").rstrip(".") + "K"
    return str(n)


def audience_facts(creator: dict) -> list[str]:
    """Only statements that are true given what has actually been filled in."""
    out: list[str] = []
    yt, ig = _channel(creator, "youtube"), _channel(creator, "instagram")
    subs, views = _n(yt.get("subscribers")), _n(yt.get("avg_views"))
    followers, reels = _n(ig.get("followers")), _n(ig.get("avg_reel_views"))

    if subs:
        s = f"{human_number(subs)} subscribers on YouTube"
        if views:
            s += f", averaging {human_number(views)} views a video"
        out.append(s)
    elif views:
        out.append(f"averaging {human_number(views)} views a video on YouTube")

    if followers:
        s = f"{human_number(followers)} on Instagram"
        if reels:
            s += f", Reels averaging {human_number(reels)}"
        out.append(s)
    elif reels:
        out.append(f"Reels averaging {human_number(reels)} views on Instagram")

    aud = creator.get("audience") or {}
    male, young = _n(aud.get("male_share")), _n(aud.get("age_18_34_share"))
    india = _n(aud.get("country_share"))
    bits = []
    if india:
        bits.append(f"{india}% in India")
    if male:
        bits.append(f"{male}% male")
    if young:
        bits.append(f"{young}% aged 18 to 34")
    if bits:
        out.append("audience is " + ", ".join(bits))
    return out


def has_numbers(creator: dict | None = None) -> bool:
    return bool(audience_facts(creator if creator is not None else load_creator()))


def best_work_links(creator: dict, limit: int = 2) -> list[dict]:
    return [w for w in (creator.get("best_work") or [])
            if (w.get("url") or "").strip()][:limit]


def craft_line(creator: dict) -> str:
    craft = [c for c in (creator.get("craft") or []) if str(c).strip()]
    if not craft:
        return ("I write, edit, grade and sound-design every video myself, so "
                "the production quality is consistent rather than outsourced.")
    joined = craft[0][0].lower() + craft[0][1:]
    if len(craft) > 1:
        second = craft[1][0].lower() + craft[1][1:]
        return f"Everything is {joined}, with {second}."
    return f"Everything is {joined}."


# --------------------------------------------------------------------------
# the per-segment angle - why a cricket audience is worth their money
# --------------------------------------------------------------------------
ANGLES = {
    "agency": ("If you are building a roster for cricket-season campaigns, I "
               "make the kind of content those budgets go to, and I can turn a "
               "brief around inside a match week."),
    "sports_agency": ("If any of your cricket properties need digital content "
                      "around them, that is exactly what I make."),
    "cricket_tech": ("Your users and my viewers are the same people - the ones "
                     "who follow the game closely enough to want the detail."),
    "cricket_media": ("If you commission cricket video from outside the "
                      "newsroom, I would like to be considered for it."),
    "sports_booking": ("The people who watch a match breakdown on a Tuesday are "
                       "the ones booking a ground on Sunday."),
    "sports_streaming": ("Cricket-first creators are how a streaming platform "
                         "gets discovered by the people already watching."),
    "cricket_gear": ("Gear content works on a cricket channel because the "
                     "audience already plays - a bat review is not an "
                     "interruption, it is the video they came for."),
    "nutrition": ("A cricket audience skews young and male and already trains, "
                  "which is the demographic this category spends most to reach."),
    "grooming": ("This is a young male audience watching long-form content, "
                 "which is where a grooming integration actually gets watched "
                 "rather than skipped."),
    "merch": ("Cricket fandom is the reason people buy fan merchandise, and my "
              "audience is fandom rather than casual viewership."),
    "consumer_tech": ("Audio and wearables sit naturally in cricket content - "
                      "the audience watches highlights on a phone with "
                      "earphones in."),
    "fintech": ("Match-day viewing and first-time investing reach the same "
                "18-to-30 audience, which is why this category buys cricket "
                "inventory every season."),
    "gaming": ("Cricket viewers and mobile gamers overlap heavily, and a "
               "cricket channel reaches them without competing for the same "
               "creators everyone else is bidding on."),
    "creator_tools": ("I edit everything in-house in After Effects and Resolve, "
                      "so a tools integration on my channel is demonstrated "
                      "rather than described."),
    "ott": ("Cricket is the most reliable way to reach an Indian entertainment "
            "audience, and my viewers are there for the long-form version."),
    "beverage": ("Match viewing is a consumption occasion, which is the whole "
                 "basis for this category's cricket spend."),
    "food": ("Match nights are an ordering occasion, and my content sits "
             "directly in that window."),
    "ticketing": ("The people planning to be at a game are the ones watching "
                  "the preview of it."),
    "travel": ("Series travel is a real behaviour in this audience, not a "
               "hypothetical one."),
}
DEFAULT_ANGLE = ("A cricket audience in India is young, male and reliably "
                 "engaged through the season, which is why this is where a lot "
                 "of consumer budgets end up.")


def angle_for(segment: str) -> str:
    return ANGLES.get((segment or "").lower(), DEFAULT_ANGLE)


# --------------------------------------------------------------------------
# email
# --------------------------------------------------------------------------
def _opening(brand: dict, observation: str) -> str:
    """The first line. Only ever says something the brand itself published.

    The `fit` note on each target is written for YOU - it is the reason the
    brand is on the list, and it says things like "small brand, quick to
    answer". That belongs on the approval card, never in the email. An earlier
    version spliced it into the opening and produced a message telling the
    brand it was small and easy to reach, which is not a way to start.
    """
    name = brand.get("name") or "your team"
    if observation:
        return f"I came across {name} - your site describes it as: \"{observation}\"."
    return (f"I came across {name} while looking for brands worth approaching "
            f"about cricket content.")


def deal_type(brand: dict) -> str:
    """What is realistically on the table with this target.

    A cash sponsorship is not the only thing worth asking for, and at a small
    channel size it is rarely the first thing to land. Asking a brand that runs
    an open affiliate programme "do you do sponsorships?" gets a no; asking to
    join the programme gets a yes the same week.
    """
    d = (brand.get("deal_type") or "").strip().lower()
    return d if d in ("affiliate", "barter", "agency", "cash") else "cash"


def _first_deliverable(creator: dict) -> str:
    items = [str(d).strip() for d in (creator.get("deliverables") or [])
             if str(d).strip()]
    if not items:
        return "a dedicated segment inside a cricket video"
    first = items[0][0].lower() + items[0][1:]
    # The deliverables are written as list entries ("60 to 90 second read"),
    # so they need an article before they read as a sentence.
    if not re.match(r"(a|an|one|two|three|the)\b", first):
        first = ("an " if first[0] in "aeiou8" else "a ") + first
    return first


def _ask_for(brand: dict, name: str, creator: dict,
             is_agency: bool) -> tuple[str, str]:
    """Subject line and closing question, by the kind of deal on offer."""
    kind = deal_type(brand)

    if kind == "affiliate":
        return (f"Affiliate programme - {name}"[:88],
                "Do you have an affiliate or referral programme I can join? "
                "Happy to send channel details if you need them to approve an "
                "account.")

    if kind == "agency" or is_agency:
        return (f"Cricket creator for your roster - {name}"[:88],
                "Do you take creator submissions for your roster? Happy to send "
                "a media kit if that is the right next step.")

    if kind == "barter":
        if (creator or {}).get("accepts_barter", True):
            return (f"Cricket content collaboration - {name}"[:88],
                    f"Would you be open to a collaboration? I can do "
                    f"{_first_deliverable(creator)} in exchange for product, "
                    f"and send the edit over before it goes live.")
        return (f"Cricket content partnership - {name}"[:88],
                "Do you run creator partnerships, and who looks after them?")

    return (f"Cricket content partnership - {name}"[:88],
            "Do you run creator partnerships, and who looks after them? If "
            "there is a fit I can put together a proposal for the coming "
            "series.")


def email_pitch(brand: dict, observation: str = "", contact_name: str = "",
                creator: dict | None = None) -> dict:
    """The cold email. Returns subject, body and a note on what it leaned on."""
    creator = creator if creator is not None else load_creator()
    name = brand.get("name") or "your team"
    segment = brand.get("segment") or ""
    is_agency = segment in ("agency", "sports_agency")

    greet = f"Hi {contact_name.split()[0]}," if contact_name.strip() else "Hi,"

    paras: list[str] = [_opening(brand, observation)]

    facts = audience_facts(creator)
    tagline = (creator.get("tagline") or
               "cricket analysis and documentary-style edits")
    who = f"I run a cricket channel - {tagline[0].lower() + tagline[1:]}."
    # Say everything the profile actually supports. At a small scale the
    # second platform is often the stronger number, and leaving it out sells
    # the channel short for no reason.
    for fact in facts[:3]:
        who += " " + _sentence(fact) + "."
    paras.append(who)

    paras.append(craft_line(creator))
    paras.append(angle_for(segment))

    work = best_work_links(creator)
    if work:
        bits = [f"{w.get('title') or 'a recent video'}: {w['url']}" for w in work]
        # It said "Two examples" whatever was in the profile, so one link read
        # as a promise the email did not keep - the first thing a brand
        # notices. Also drop the "; " join when there is nothing to join.
        lead = "Two examples - " if len(bits) > 1 else "One recent example - "
        paras.append(lead + "; ".join(bits) + ".")

    subject, ask = _ask_for(brand, name, creator, is_agency)

    body = greet + "\n\n" + "\n\n".join(paras) + "\n\n" + ask + "\n\n" + signature(creator)
    return {
        "subject": subject[:88],
        "body": body,
        "personalisation_note": (f"Opened on their own site copy: {observation[:110]}"
                                 if observation else
                                 f"Opened on the stated fit: {brand.get('fit','')[:110]}"),
        "confidence": 0.75 if observation else 0.55,
        "has_numbers": bool(facts),
    }


def signature(creator: dict | None = None) -> str:
    """Name, then every way they can reach you.

    The email address matters most: a brand that wants to talk will reply to
    whatever is in front of them, and the address the message was sent FROM is
    not always the one you want the conversation on. Both channel links go in
    too - some brands check Instagram before they check YouTube.
    """
    creator = creator if creator is not None else load_creator()
    lines = [creator.get("name") or config.get("OPERATOR_NAME", "Vineet")]

    contact = creator.get("contact") or {}
    email = (contact.get("email") or "").strip() or config.get("OPERATOR_EMAIL", "")
    if email:
        lines.append(email)

    # One channel link only. The body already carries a link to the work, and
    # a first email with three links in it trips spam filters - the lint check
    # flags exactly this. An email address is not a link, so it costs nothing.
    link = ((_channel(creator, "youtube").get("url") or "").strip()
            or (_channel(creator, "instagram").get("url") or "").strip()
            or config.get("YOUTUBE_CHANNEL_URL", ""))
    if link:
        lines.append(link)

    phone = (contact.get("phone") or "").strip() or config.get("OPERATOR_PHONE", "")
    if phone:
        lines.append(phone)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# WhatsApp and DM - short-form, written for a phone screen
# --------------------------------------------------------------------------
def whatsapp_pitch(brand: dict, creator: dict | None = None) -> str:
    creator = creator if creator is not None else load_creator()
    who = creator.get("name") or config.get("OPERATOR_NAME", "Vineet")
    name = brand.get("name") or "your team"
    facts = audience_facts(creator)
    line2 = ("I run a cricket channel - match breakdowns and documentary-style "
             "edits, all written and edited in-house.")
    if facts:
        line2 += f" {_sentence(facts[0])}."
    segment = brand.get("segment") or ""
    kind = deal_type(brand)
    if kind == "agency" or segment in ("agency", "sports_agency"):
        ask = "Do you take creator submissions for your roster?"
    elif kind == "affiliate":
        ask = f"Does {name} have an affiliate or referral programme I can join?"
    elif kind == "barter":
        ask = (f"Would {name} be open to a collaboration - a video in exchange "
               f"for product?")
    else:
        ask = (f"Does {name} run creator partnerships? Happy to send a media "
               f"kit if that is useful.")
    link = ""
    yt = _channel(creator, "youtube")
    if (yt.get("url") or "").strip():
        link = f"\n\n{yt['url'].strip()}"
    return (f"Hi, this is {who}.\n\n{line2}\n\n{ask}{link}")


def instagram_dm(brand: dict, creator: dict | None = None) -> str:
    """Shorter again. Instagram truncates, and a wall of text is not opened."""
    creator = creator if creator is not None else load_creator()
    who = creator.get("name") or config.get("OPERATOR_NAME", "Vineet")
    facts = audience_facts(creator)
    opener = f"Hi - {who} here, I make cricket breakdowns and documentary edits."
    if facts:
        opener += f" {_sentence(facts[0])}."
    segment = brand.get("segment") or ""
    kind = deal_type(brand)
    if kind == "agency" or segment in ("agency", "sports_agency"):
        ask = "Do you take creator submissions?"
    elif kind == "affiliate":
        ask = "Do you have an affiliate programme I can join?"
    elif kind == "barter":
        ask = "Would you be open to a collaboration - a video for product?"
    else:
        ask = "Is there someone who looks after creator partnerships there?"
    return f"{opener}\n\n{ask} Happy to send work samples."


def gmail_link(to: str, subject: str, body: str) -> str:
    """A Gmail compose window with everything already filled in.

    Telegram's inline buttons only accept http(s), so a mailto: link cannot be
    a button. Gmail's own compose URL can, and it opens in the Gmail app on a
    phone and in the browser on a desktop - already addressed, already written,
    sending from whichever account is signed in.
    """
    if not (to or "").strip():
        return ""
    q = urllib.parse.urlencode({"view": "cm", "fs": "1", "to": to.strip(),
                                "su": subject or "", "body": body or ""},
                               quote_via=urllib.parse.quote)
    return "https://mail.google.com/mail/?" + q


def wa_link(phone: str, text: str) -> str:
    """A click-to-chat link with the message already typed in."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return ""
    return ("https://wa.me/" + digits + "?text="
            + urllib.parse.quote(text or "", safe=""))
