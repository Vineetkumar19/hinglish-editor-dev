"""The two boards where Indian jobs actually get posted.

Greenhouse and Lever only cover companies that chose those tools. Most Indian
employers post to Naukri, and almost all of them post to LinkedIn, so a hunt
that skips both is missing the bulk of the market.

How each one is reached matters, and the two are not the same:

  LinkedIn - through the /jobs-guest/ endpoints their own careers pages call
             for logged-out visitors. No account, no cookie, no automation of
             his session, so nothing here can get his account restricted. This
             is deliberate: driving a logged-in LinkedIn with a script is the
             single most reliable way to have it flagged, and the guest
             endpoint returns the same public postings.

  Naukri   - their search API, with his own session cookie. Naukri shows very
             little to a logged-out visitor, so the cookie is what makes this
             worth having. It is his own session, read the way his browser
             reads it, at a human pace.
"""
from __future__ import annotations

import html as html_mod
import re
import time
import urllib.parse

from core import config, http
from core.log import get_logger

from .discovery import Job, Source, _clean

log = get_logger("boards-in")

LINKEDIN = "https://www.linkedin.com/jobs-guest/jobs/api"

# How far back to look, in LinkedIn's own vocabulary.
FRESHNESS = {1: "r86400", 7: "r604800", 30: "r2592000"}


def _freshness() -> str:
    days = config.get_int("JOB_MAX_AGE_DAYS", 30)
    for limit in sorted(FRESHNESS):
        if days <= limit:
            return FRESHNESS[limit]
    return FRESHNESS[30]


def _text(raw: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


class LinkedInSource(Source):
    """Public job postings, one search per location he named."""
    name = "linkedin"

    def fetch(self, query: str, **kw) -> list[Job]:
        out: list[Job] = []
        # Separated by "|", not ",": LinkedIn wants "Bengaluru, India" as one
        # place, and a comma-separated setting would cut that into two.
        places = config.get_list("LINKEDIN_LOCATIONS",
                                 ["India", "Bengaluru, India", "Pune, India",
                                  "Hyderabad, India", "Mumbai, India",
                                  "Chennai, India", "Noida, India",
                                  "Delhi, India"], sep="|")
        want_detail = config.get_bool("LINKEDIN_FETCH_DESCRIPTIONS", True)
        per_place = config.get_int("LINKEDIN_PER_PLACE", 25)
        for place in places:
            for start in range(0, per_place, 25):
                cards = self._search(query, place, start)
                if not cards:
                    break
                out.extend(cards)
        if want_detail:
            # The card carries no description, and both the relevance check and
            # the location check read one. Fetching them is the slow part, so
            # it is capped and can be turned off.
            for job in out[:config.get_int("LINKEDIN_MAX_DESCRIPTIONS", 40)]:
                job.description = self._describe(job.id) or job.description
        return out

    def _search(self, query: str, place: str, start: int) -> list[Job]:
        q = urllib.parse.urlencode({"keywords": query, "location": place,
                                    "f_TPR": _freshness(), "start": start})
        resp = http.get(f"{LINKEDIN}/seeMoreJobPostings/search?{q}",
                        timeout=25, retries=1)
        if not resp.ok:
            log.warn(f"linkedin search failed for {place!r}: {resp.status}")
            return []
        return self.parse_cards(resp.text)

    @staticmethod
    def parse_cards(raw: str) -> list[Job]:
        """One Job per <li> in the returned fragment.

        Parsed per card rather than by collecting each field across the whole
        document: findall on the full page returns the fields in separate
        lists, and one card missing a location silently shifts every later
        company onto the wrong job.
        """
        out = []
        for chunk in re.split(r"<li>", raw)[1:]:
            jid = re.search(r"urn:li:jobPosting:(\d+)", chunk)
            title = re.search(r'base-search-card__title">\s*([^<]+)', chunk)
            company = re.search(
                r'base-search-card__subtitle">\s*(?:<a[^>]*>)?\s*([^<]+)', chunk)
            place = re.search(r'job-search-card__location">\s*([^<]+)', chunk)
            link = re.search(r'href="(https://[a-z.]*linkedin\.com/jobs/view/[^"?]+)',
                             chunk)
            posted = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', chunk)
            if not (jid and title and company):
                continue
            stamp = 0.0
            if posted:
                try:
                    stamp = time.mktime(time.strptime(posted.group(1), "%Y-%m-%d"))
                except ValueError:
                    stamp = 0.0
            url = link.group(1) if link else \
                f"https://www.linkedin.com/jobs/view/{jid.group(1)}"
            out.append(Job(
                id=f"li-{jid.group(1)}", title=_text(title.group(1)),
                company=_text(company.group(1)),
                location=_text(place.group(1)) if place else "",
                remote="remote" in chunk.lower(), url=url, apply_url=url,
                description="", posted_at=stamp or time.time(),
                source="linkedin", raw={"linkedin_id": jid.group(1)}))
        return out

    @staticmethod
    def _describe(job_id: str) -> str:
        jid = job_id.removeprefix("li-")
        resp = http.get(f"{LINKEDIN}/jobPosting/{jid}", timeout=20, retries=0)
        if not resp.ok:
            return ""
        # Start AFTER the opening tag, not at the class name. Matching from
        # "description__text" itself dragged `description__text--rich">` into
        # the text, and that went straight into the opening line of a pitch.
        body = re.search(
            r'(?s)<div[^>]*class="[^"]*description__text[^"]*"[^>]*>(.*?)</section>',
            resp.text)
        if not body:
            body = re.search(r'(?s)description__text[^>]*>(.*?)</section>', resp.text)
        return _clean(_text(body.group(1) if body else resp.text))[:6000]


class NaukriSource(Source):
    """Naukri search, using his own logged-in session.

    Without NAUKRI_COOKIE this returns nothing rather than pretending: Naukri
    answers a logged-out request with either an error or a near-empty result,
    and silently contributing nothing to a run is worse than saying so.
    """
    name = "naukri"
    API = "https://www.naukri.com/jobapi/v3/search"

    def fetch(self, query: str, **kw) -> list[Job]:
        cookie = config.get("NAUKRI_COOKIE", "").strip()
        if not cookie:
            log.info("naukri skipped - NAUKRI_COOKIE is not set")
            return []
        out: list[Job] = []
        for place in config.get_list("NAUKRI_LOCATIONS",
                                     ["bengaluru", "pune", "hyderabad",
                                      "mumbai", "delhi-ncr", "chennai"]):
            out.extend(self._search(query, place, cookie))
        return out

    def _search(self, query: str, place: str, cookie: str) -> list[Job]:
        q = urllib.parse.urlencode({
            "noOfResults": config.get_int("NAUKRI_PER_PLACE", 20),
            "urlType": "search_by_key_loc", "searchType": "adv",
            "keyword": query, "location": place, "pageNo": 1,
            "src": "jobsearchDesk",
            "experience": config.get("JOB_EXPERIENCE_YEARS", "0")})
        resp = http.get(f"{self.API}?{q}", timeout=25, retries=1, headers={
            "appid": "109", "systemid": "Naukri", "clientid": "d3skt0p",
            "Accept": "application/json", "Cookie": cookie,
            "Referer": f"https://www.naukri.com/{query.replace(' ', '-')}-jobs"})
        if not resp.ok:
            log.warn(f"naukri {place}: HTTP {resp.status} - if this is 401 or "
                     f"403 the cookie has expired; copy a fresh one")
            return []
        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warn(f"naukri {place}: unreadable reply ({exc})")
            return []
        return [self._to_job(j) for j in (data.get("jobDetails") or [])]

    @staticmethod
    def _to_job(j: dict) -> Job:
        holders = {p.get("type"): p.get("label")
                   for p in (j.get("placeholders") or []) if isinstance(p, dict)}
        url = j.get("jdURL") or ""
        if url and not url.startswith("http"):
            url = "https://www.naukri.com" + url
        return Job(
            id=f"nk-{j.get('jobId', '')}", title=j.get("title", ""),
            company=j.get("companyName", ""),
            location=holders.get("location", ""), remote=False,
            url=url, apply_url=url,
            description=_clean(" ".join(filter(None, [
                j.get("jobDescription", ""), holders.get("experience", ""),
                " ".join(str(t.get("title", "")) for t in (j.get("tagsAndSkills")
                                                           or []) if isinstance(t, dict)),
                str(j.get("tagsAndSkills") or "")])))[:6000],
            posted_at=(float(j.get("footerPlaceholderValue") or 0) or time.time()),
            source="naukri", raw=j)


# Registering here too means importing this module directly - which is what the
# video client agent does, for the card parser - also makes the sources
# available, without either module importing the other at module scope.
from .discovery import SOURCES as _SOURCES  # noqa: E402

_SOURCES.setdefault(LinkedInSource.name, LinkedInSource)
_SOURCES.setdefault(NaukriSource.name, NaukriSource)
