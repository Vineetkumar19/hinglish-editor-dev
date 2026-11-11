"""Where the paying work is.

Cold-emailing YouTubers who never asked for an editor is the slowest way into
this market. People actively hiring one have already decided to spend money and
say so in public, so this looks there first: LinkedIn's public job feed, and
the remote boards, filtered to editing work.

The LinkedIn card parser is the job hunter's, imported rather than copied. It
was written against live HTML and it is the piece most likely to need fixing
when LinkedIn changes; one copy means one fix.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field

from core import config, http
from core.log import get_logger

log = get_logger("video.sources")

# Worth writing to. Ordered by how much the phrase implies a budget.
QUERIES = [
    "freelance video editor",
    "video editor contract",
    "motion graphics designer freelance",
    "after effects animator freelance",
    "youtube video editor",
    "short form video editor",
    "colorist freelance",
    "video editor retainer",
]

# A posting that mentions one of these is not editing work, whatever the title
# says. "Video Producer" who must be on set in Ohio is not a remote edit job.
NOT_EDITING = re.compile(
    r"\b(camera operator|on[- ]set|videographer on location|studio based|"
    r"must be on site|on-site only|photographer|live stream operator|"
    r"broadcast engineer|av technician|drone pilot)\b", re.I)

# "editor" on its own is not enough. A live sweep surfaced "Course Writer and
# Editor: UX, UI and AI" as editing work - the word is just as common in
# publishing, and a pitch offering to cut their footage would be embarrassing.
# So a bare "editor" only counts when something video-shaped sits near it.
EDITING = re.compile(
    r"\b(video edit|film edit|motion graphic|after effects|premiere pro|"
    r"davinci|colou?rist|colou?r grad|post[- ]production|videograph|"
    r"video producer|reels? editor|shorts? editor|sound design|"
    r"animator|animation)\w*", re.I)

# Any of these near the word "editor" makes it a video editor.
VIDEO_CONTEXT = re.compile(
    r"\b(video|footage|youtube|reel|short[- ]form|tiktok|podcast|vlog|"
    r"film|edit suite|timeline|b[- ]roll|clip)\w*", re.I)
_BARE_EDITOR = re.compile(r"\beditor\b", re.I)


def _is_video_editing(text: str) -> bool:
    if EDITING.search(text or ""):
        return True
    return bool(_BARE_EDITOR.search(text or "")
                and VIDEO_CONTEXT.search(text or ""))

# What the client is, from how they describe themselves. Each one is pitched
# differently: an agency wants to know you can take a brief and disappear, a
# creator wants to know you understand retention.
CLIENT_KINDS = [
    ("agency", r"\b(agency|studio|production (house|company)|post house|"
               r"we produce|our clients)\w*"),
    ("brand", r"\b(saas|startup|our product|b2b|ecommerce|d2c|brand|"
              r"marketing team|growth team)\w*"),
    ("creator", r"\b(youtube channel|my channel|creator|influencer|"
                r"subscribers|our channel)\w*"),
    ("coach", r"\b(course|coach|cohort|webinar|podcast|newsletter)\w*"),
]


@dataclass
class Gig:
    """One piece of work somebody is trying to hire for."""
    id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    posted_at: float = 0.0
    source: str = ""
    remote: bool = False
    raw: dict = field(default_factory=dict)

    def key(self) -> str:
        return (self.url or f"{self.source}:{self.id}").lower()

    def kind(self) -> str:
        blob = f"{self.company} {self.title} {self.description}"
        for name, pattern in CLIENT_KINDS:
            if re.search(pattern, blob, re.I):
                return name
        return "unknown"

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "raw"}


def is_editing_work(gig: Gig) -> tuple[bool, str]:
    blob = f"{gig.title} {gig.description[:2000]}"
    if not _is_video_editing(gig.title) and not _is_video_editing(blob):
        return False, "not editing work"
    hit = NOT_EDITING.search(blob)
    if hit and not re.search(r"\bremote\b", blob, re.I):
        return False, f"needs someone on location ({hit.group(0).lower()})"
    return True, "editing work"


# --------------------------------------------------------------------------
def from_linkedin(query: str, places: list[str] | None = None) -> list[Gig]:
    """Public postings, one search per market he sells into."""
    from agents.job_hunter.boards_in import LinkedInSource
    places = places or config.get_list(
        "VIDEO_CLIENT_MARKETS",
        ["United States", "Canada", "United Kingdom", "Worldwide", "India"],
        sep="|")
    out: list[Gig] = []
    for place in places:
        q = urllib.parse.urlencode({"keywords": query, "location": place,
                                    "f_TPR": "r604800", "start": 0})
        resp = http.get(
            f"https://www.linkedin.com/jobs-guest/jobs/api/"
            f"seeMoreJobPostings/search?{q}", timeout=25, retries=1)
        if not resp.ok:
            log.warn(f"linkedin {place}: HTTP {resp.status}")
            continue
        for job in LinkedInSource.parse_cards(resp.text):
            out.append(Gig(id=job.id, title=job.title, company=job.company,
                           location=job.location or place, url=job.url,
                           description="", posted_at=job.posted_at,
                           source="linkedin", remote=job.remote))
    return out


def describe(gig: Gig) -> str:
    """Pull the ad text. Needed to price it and to write anything specific."""
    if gig.source != "linkedin":
        return gig.description
    from agents.job_hunter.boards_in import LinkedInSource
    return LinkedInSource._describe(gig.id)


def _title_matches(title: str) -> bool:
    return _is_video_editing(title or "")


def from_remoteok() -> list[Gig]:
    """RemoteOK, filtered here.

    Their ?tags= parameter is accepted and then ignored - asking for video
    returns the whole board - so the filtering has to happen on this side.
    """
    resp = http.get("https://remoteok.com/api", timeout=25, retries=1)
    if not resp.ok:
        return []
    try:
        rows = resp.json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("position"):
            continue
        if not _title_matches(r["position"]):
            continue
        out.append(Gig(id=str(r.get("id") or r.get("slug") or ""),
                       title=r["position"], company=r.get("company", ""),
                       location=r.get("location", "") or "Remote",
                       url=r.get("url", ""),
                       description=re.sub(r"<[^>]+>", " ",
                                          r.get("description", ""))[:6000],
                       posted_at=float(r.get("epoch") or 0) or time.time(),
                       source="remoteok", remote=True, raw=r))
    return out


def from_remotive(query: str) -> list[Gig]:
    resp = http.get("https://remotive.com/api/remote-jobs",
                    params={"search": query, "limit": 50}, timeout=25, retries=1)
    if not resp.ok:
        return []
    try:
        jobs = resp.json().get("jobs") or []
    except Exception:  # noqa: BLE001
        return []
    out = []
    for j in jobs:
        if not _title_matches(j.get("title", "")):
            continue
        out.append(Gig(id=str(j.get("id", "")), title=j.get("title", ""),
                       company=j.get("company_name", ""),
                       location=j.get("candidate_required_location", "Remote"),
                       url=j.get("url", ""),
                       description=re.sub(r"<[^>]+>", " ",
                                          j.get("description", ""))[:6000],
                       posted_at=time.time(), source="remotive", remote=True,
                       raw=j))
    return out


def from_weworkremotely() -> list[Gig]:
    resp = http.get("https://weworkremotely.com/categories/"
                    "remote-design-jobs.rss", timeout=25, retries=1)
    if not resp.ok:
        return []
    out = []
    for item in re.split(r"<item>", resp.text)[1:]:
        title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
                          item, re.S)
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        if not (title and link):
            continue
        text = title.group(1).strip()
        if not _title_matches(text):
            continue
        company, _, role = text.partition(":")
        out.append(Gig(id=link.group(1).strip()[-40:], title=(role or text).strip(),
                       company=company.strip(), location="Remote",
                       url=link.group(1).strip(),
                       description=re.sub(r"<[^>]+>", " ", item)[:4000],
                       posted_at=time.time(), source="weworkremotely",
                       remote=True))
    return out


SOURCES = {
    "linkedin": lambda: [g for q in QUERIES for g in from_linkedin(q)],
    "remoteok": from_remoteok,
    "remotive": lambda: [g for q in QUERIES[:3] for g in from_remotive(q)],
    "weworkremotely": from_weworkremotely,
}


def find_gigs(sources: list[str] | None = None) -> list[Gig]:
    """Everything worth writing to today, deduplicated."""
    names = sources or config.get_list("VIDEO_CLIENT_SOURCES",
                                       ["linkedin", "remoteok", "weworkremotely"])
    seen, out = set(), []
    for name in names:
        fn = SOURCES.get(name)
        if fn is None:
            log.warn(f"unknown gig source {name!r}; known: {sorted(SOURCES)}")
            continue
        try:
            gigs = fn()
        except Exception as exc:  # noqa: BLE001
            log.warn(f"gig source {name} failed: {exc}")
            continue
        for g in gigs:
            ok, _ = is_editing_work(g)
            if not ok or g.key() in seen:
                continue
            seen.add(g.key())
            out.append(g)
    log.info("gig sweep complete", sources=names, found=len(out))
    return out
