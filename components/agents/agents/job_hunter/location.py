"""Is this job somewhere he can actually take it?

Nothing in this agent looked at location before. Greenhouse, Remotive and
RemoteOK are all global, so a run would pull San Francisco and Berlin postings,
run the local model over each one to tailor a resume, and put them on his phone.
Every one of those is a wasted minute of model time and a wasted decision.

The rule is not "is India in the string". A posting that says "Remote (US
only)" mentions no Indian city and is a no; one that says "Bengaluru" says
nothing about India and is a yes. So this checks three things in order: an
explicit block on the location, a wanted place, and then whether remote is
open to India.
"""
from __future__ import annotations

import re

from core import config

# Where he said he can work: the Mumbai belt he lives in, the cities he will
# relocate for, and remote within India.
DEFAULT_PLACES = [
    "mumbai", "navi mumbai", "thane", "badlapur", "kalyan", "dombivli",
    "panvel", "mmr",
    "pune", "pimpri", "chinchwad", "hinjewadi", "kharadi", "magarpatta",
    "bengaluru", "bangalore", "whitefield", "koramangala", "electronic city",
    "hyderabad", "secunderabad", "gachibowli", "hitec city", "hitech city",
    "delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida", "faridabad",
    "ghaziabad",
    "chennai", "madras", "omr", "sholinganallur",
    "india", "bharat",
]

# A remote posting that names one of these is remote *for someone else*.
REMOTE_BLOCKED = [
    "us only", "u.s. only", "usa only", "united states only", "us-based",
    "us based", "must be based in the us", "must reside in the united states",
    "uk only", "eu only", "eea only", "europe only", "emea only",
    "canada only", "australia only", "singapore only", "latam", "brazil only",
    "us citizens", "green card", "work authorization in the united states",
    "must be authorized to work in the us", "eu work permit",
    "apac excluding india", "anywhere in the us", "remote - us", "remote (us",
    "remote, us", "remote usa", "remote - canada", "remote - europe",
]

# Places that are simply not commutable and not India. Only consulted when the
# posting names no wanted place at all, so "Bengaluru or London" still passes.
FOREIGN = [
    "san francisco", "new york", "seattle", "austin", "boston", "chicago",
    "denver", "los angeles", "san jose", "palo alto", "mountain view",
    "toronto", "vancouver", "london", "manchester", "dublin", "berlin",
    "munich", "amsterdam", "paris", "madrid", "barcelona", "lisbon",
    "stockholm", "zurich", "tel aviv", "singapore", "sydney", "melbourne",
    "tokyo", "seoul", "shanghai", "beijing", "hong kong", "dubai", "abu dhabi",
    "riyadh", "doha", "warsaw", "prague", "bucharest", "mexico city",
    "sao paulo", "buenos aires", "cape town", "nairobi", "lagos",
    "united states", "usa", "u.s.a", "united kingdom", "germany", "france",
    "netherlands", "canada", "australia", "ireland", "spain", "poland",
    "brazil", "mexico", "japan", "israel", "uae", "philippines", "vietnam",
    "indonesia", "malaysia", "thailand",
]

# "Indiana" and "Indianapolis" both contain "india". A word boundary is not
# enough, because "India" is a prefix of both.
_INDIA = re.compile(r"\bindia\b(?!\s*n)", re.I)

# "San Mateo, CA" is not in the FOREIGN list and never will be - there are too
# many towns. But a trailing two-letter code is how the US and Canada write an
# address and nobody writes an Indian one that way: it is "Bangalore,
# Karnataka", not "Bangalore, KA".
_US_STATE = re.compile(r",\s*[A-Z]{2}\b")


def wanted_places() -> list[str]:
    return [p.lower() for p in config.get_list("JOB_LOCATIONS", DEFAULT_PLACES)]


_WORDS: dict[str, re.Pattern] = {}


def _word(needle: str) -> re.Pattern:
    """A whole-word matcher, cached.

    Substring matching put "Indianapolis, IN" through as an Indian city,
    because "india" is a prefix of it. Every place name here needs a boundary
    on both sides, and "india" additionally must not be followed by an "n".
    """
    pat = _WORDS.get(needle)
    if pat is None:
        body = re.escape(needle).replace(r"\ ", r"\s+")
        tail = r"(?!\s*n)" if needle == "india" else ""
        pat = _WORDS[needle] = re.compile(rf"\b{body}\b{tail}", re.I)
    return pat


def _mentions(text: str, needles) -> str:
    for n in needles:
        if _word(n).search(text):
            return n
    return ""


def acceptable(job) -> tuple[bool, str]:
    """(can he take this job, why).

    `job` is a Job or a dict - only `location`, `remote` and the text fields
    are read.
    """
    get = job.get if isinstance(job, dict) else lambda k, d=None: getattr(job, k, d)
    place = str(get("location", "") or "")
    remote = bool(get("remote", False))
    # The location field is often empty or just "Remote", and the real answer
    # is a line in the description.
    body = " ".join(str(get(k, "") or "") for k in ("location", "title",
                                                    "description"))[:4000]
    low_place, low_body = place.lower(), body.lower()

    blocked = _mentions(low_body, REMOTE_BLOCKED)
    if blocked and not _INDIA.search(low_body):
        return False, f"remote but not for India ({blocked})"

    hit = _mentions(low_place, wanted_places()) or (
        "india" if _INDIA.search(low_place) else "")
    if hit:
        return True, f"in {place.strip()}" if place.strip() else f"mentions {hit}"

    # The location field is the posting's own answer, so when it names a place
    # he cannot take, that settles it. Reading the body first let an InMobi
    # role in San Mateo through because the ad mentioned the India office
    # further down.
    foreign = _mentions(low_place, FOREIGN)
    if foreign:
        return False, f"{foreign.title()} - not somewhere he can take it"
    if _US_STATE.search(place):
        return False, f"{place.strip()} is a US address"

    # Only now fall back to the body: plenty of Greenhouse posts leave the
    # location field blank or say "Remote" and put "Bengaluru, India" in the
    # ad text.
    hit = _mentions(low_body, wanted_places()) or (
        "india" if _INDIA.search(low_body) else "")
    if hit:
        return True, f"the posting mentions {hit}"

    foreign = _mentions(low_body, FOREIGN)
    if foreign:
        return False, f"{foreign.title()} - not somewhere he can take it"

    if remote or "remote" in low_place or "remote" in low_body[:600]:
        # Remote with no country named at all. Worth showing: a genuinely
        # worldwide role is exactly the kind he asked for, and the card says
        # the country is unstated so he can judge.
        return True, "remote, country not stated"

    if not place.strip():
        return True, "no location given - worth a look"
    return False, f"{place.strip()} is outside the places he named"
