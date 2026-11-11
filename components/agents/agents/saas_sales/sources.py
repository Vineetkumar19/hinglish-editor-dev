"""Finding the four audiences, worldwide.

The other agents answer people who advertised that they want something. Nobody
advertises "I would like to be sold a video editing tool", so this one works
the other way round: it finds people whose public work shows the problem the
product solves, and people whose audience is made of those people.

Four different kinds of target, found four different ways:

  user       - editors and creators publishing enough video that the
               repetitive passes actually cost them hours
  promoter   - creators whose channel is ABOUT tools and workflow. These are
               the partner targets, and there are far fewer of them than the
               50/50 idea assumes - a channel that reviews editing software is
               a specific, findable thing.
  agency     - editing and production studios, who buy seats rather than one
               licence
  directory  - the tool directories and newsletters that list new software,
               which cost nothing and are the only channel here that works
               before launch

Everything is keyless. No API keys, no logins, nothing that stops working when
a token expires two years from now.
"""
from __future__ import annotations

import html as html_mod
import re
import time
import urllib.parse
from dataclasses import dataclass, field

from core import config, http
from core.log import get_logger

log = get_logger("saas.sources")

# Where the people who review and recommend editing tools actually are.
YOUTUBE_QUERIES = [
    "best video editing software 2026",
    "premiere pro plugins workflow",
    "davinci resolve tutorial workflow",
    "edit faster podcast workflow",
    "remove silence premiere pro",
    "auto captions video editing",
    "video editing tools i use",
    "youtube editing workflow behind the scenes",
]

# Directories and listing sites that accept a submission before launch. These
# are hand-kept rather than scraped: there are perhaps thirty that matter and
# the list changes slowly.
DIRECTORIES = [
    {"name": "Product Hunt", "url": "https://www.producthunt.com/ship",
     "note": "Ship page collects a waitlist before launch", "cost": "free"},
    {"name": "BetaList", "url": "https://betalist.com/submit",
     "note": "Exists specifically for pre-launch products", "cost": "free tier"},
    {"name": "There's An AI For That", "url": "https://theresanaiforthat.com/submit/",
     "note": "Largest AI tool directory, high traffic", "cost": "free + paid"},
    {"name": "Futurepedia", "url": "https://www.futurepedia.io/submit-tool",
     "note": "AI tool directory with a video editing category", "cost": "free + paid"},
    {"name": "AlternativeTo", "url": "https://alternativeto.net/manage/",
     "note": "Listed as an alternative to the tools they already use", "cost": "free"},
    {"name": "SaaSHub", "url": "https://www.saashub.com/submit",
     "note": "Comparison listings", "cost": "free"},
    {"name": "Indie Hackers", "url": "https://www.indiehackers.com/products",
     "note": "Build-in-public audience, good before launch", "cost": "free"},
    {"name": "Toolify", "url": "https://www.toolify.ai/submit",
     "note": "AI tool directory", "cost": "free + paid"},
]

# A channel that reviews tools, versus one that just makes videos.
PROMOTER_SIGNALS = re.compile(
    r"\b(review|tutorial|workflow|plugin|software|tools? i use|my setup|"
    r"best \w+ for|vs\b|comparison|tested|how i edit|edit faster)\w*", re.I)

# Someone who edits a lot, and would feel the problem.
USER_SIGNALS = re.compile(
    r"\b(podcast|youtuber|content creator|video editor|editor|filmmaker|"
    r"vlogger|streamer|course creator|videograph)\w*", re.I)

AGENCY_SIGNALS = re.compile(
    r"\b(agency|studio|production (house|company)|post house|media house|"
    r"we edit for|our clients|editing team)\w*", re.I)


@dataclass
class Target:
    id: str
    name: str
    kind: str                  # user | promoter | agency | directory
    url: str = ""
    handle: str = ""
    where: str = ""
    evidence: str = ""         # why this one, in one line
    contact: str = ""
    source: str = ""
    found_at: float = 0.0
    raw: dict = field(default_factory=dict)

    def key(self) -> str:
        return (self.url or f"{self.source}:{self.id}").lower()

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "raw"}


def _text(raw: str) -> str:
    return re.sub(r"\s+", " ",
                  html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


# --------------------------------------------------------------------------
def from_youtube(query: str, limit: int = 12) -> list[Target]:
    """Channels publishing about editing tools and workflow.

    Read off the search results page rather than the Data API: no key to
    expire, no quota to run out, and the agent keeps working in five years.
    """
    q = urllib.parse.urlencode({"search_query": query, "sp": "CAASAhAB"})
    resp = http.get(f"https://www.youtube.com/results?{q}", timeout=25, retries=1)
    if not resp.ok:
        log.warn(f"youtube search failed for {query!r}: {resp.status}")
        return []
    out, seen = [], set()
    # The channel name and its handle travel together in the rendered JSON.
    for m in re.finditer(
            r'"ownerText":\{"runs":\[\{"text":"([^"]{2,60})".*?'
            r'"canonicalBaseUrl":"(/@[\w.-]{2,40})"', resp.text):
        name, path = m.group(1), m.group(2)
        if path in seen:
            continue
        seen.add(path)
        out.append(Target(
            id=path.strip("/@"), name=name, kind="promoter",
            url=f"https://www.youtube.com{path}", handle=path.strip("/"),
            evidence=f"publishes about: {query}", source="youtube",
            found_at=time.time()))
        if len(out) >= limit:
            break
    return out


def channel_about(target: Target) -> dict:
    """What the channel says about itself, plus any published contact.

    Read from the channel page's meta description rather than the /about tab:
    the About tab renders client-side and arrives empty, while the meta tag is
    in the first response and carries the same text.

    A business email in that description is PUBLISHED, not guessed. That is the
    whole difference between contacting someone and spamming them, and it is
    why no address is ever constructed here.
    """
    if not target.url:
        return {}
    resp = http.get(target.url.rstrip("/"), timeout=25, retries=1)
    if not resp.ok:
        return {}
    text = resp.text
    desc = ""
    for pattern in (r'<meta name="description" content="([^"]{20,600})"',
                    r'<meta property="og:description" content="([^"]{20,600})"',
                    r'"description":\{"simpleText":"(.{20,1200}?)"\}'):
        m = re.search(pattern, text)
        if m:
            desc = html_mod.unescape(m.group(1))
            break
    subs = ""
    for pattern in (r'"subscriberCountText":\{"simpleText":"([^"]+)"',
                    # [\d.]+ stops at a comma, so "1,000,000 subscribers"
                    # came back as "000" and banded a large channel as tiny.
                    r'([\d][\d.,]*\s*[KMB]?)\s*subscribers'):
        m = re.search(pattern, text)
        if m:
            subs = m.group(1)
            break
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]{2,12}", desc)
    links = re.findall(r'"(https?://(?!\w*\.?youtube|yt\d|www\.google)'
                       r'[^"\s]{6,90})"', text)[:12]
    return {"description": _text(desc)[:3000], "subscribers": subs,
            "email": emails[0] if emails else "",
            "links": list(dict.fromkeys(links))[:5]}


# Channels that ARE a competing plugin. Pitching an AI editing tool to the
# people who sell one is not outreach, it is telling a competitor exactly what
# is coming. A live search returned two of these in the first eight results.
COMPETITORS = re.compile(
    r"\b(autocut|firecut|easytimeline|descript|opus ?clip|veed|kapwing|"
    r"timebolt|recut|gling|vidyo|submagic|captions\.ai|eddie ?ai|"
    r"simon says|trint|otter\.ai)\w*", re.I)


def is_competitor(name: str, description: str = "", url: str = "") -> str:
    hit = COMPETITORS.search(f"{name} {description} {url}")
    return hit.group(0) if hit else ""


def classify(name: str, description: str) -> str:
    blob = f"{name} {description}"
    if is_competitor(name, description):
        return "competitor"
    if AGENCY_SIGNALS.search(blob):
        return "agency"
    if PROMOTER_SIGNALS.search(blob):
        return "promoter"
    if USER_SIGNALS.search(blob):
        return "user"
    return "user"


def from_directories() -> list[Target]:
    """The listing sites. No fetching - the work here is submitting, and that
    is his to do, so each one becomes a card with the link and what it costs."""
    return [Target(id=d["name"].lower().replace(" ", "-"), name=d["name"],
                   kind="directory", url=d["url"], evidence=d["note"],
                   where=d["cost"], source="directory", found_at=time.time())
            for d in DIRECTORIES]


SOURCES = {
    "youtube": lambda: [t for q in YOUTUBE_QUERIES for t in from_youtube(q)],
    "directories": from_directories,
}


def find_targets(sources: list[str] | None = None) -> list[Target]:
    names = sources or config.get_list("SAAS_SOURCES", ["youtube", "directories"])
    seen, out = set(), []
    for name in names:
        fn = SOURCES.get(name)
        if fn is None:
            log.warn(f"unknown saas source {name!r}; known: {sorted(SOURCES)}")
            continue
        try:
            found = fn()
        except Exception as exc:  # noqa: BLE001
            log.warn(f"saas source {name} failed: {exc}")
            continue
        for t in found:
            if t.key() in seen:
                continue
            seen.add(t.key())
            out.append(t)
    log.info("saas sweep complete", sources=names, found=len(out))
    return out
