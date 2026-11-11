"""Job aggregation across boards.

python-jobspy is not a dependency here, so each source is implemented against
the board's own public API or feed. Every provider returns the same normalised
Job record, and a run fans out across whichever providers are enabled.

Enabled with JOB_SOURCES, e.g. JOB_SOURCES=greenhouse,lever,remotive,remoteok

  greenhouse - boards-api.greenhouse.io, per company board token
  lever      - api.lever.co/v0/postings, per company
  remotive   - remotive.com public API
  remoteok   - remoteok.com/api
  adzuna     - Adzuna API (ADZUNA_APP_ID / ADZUNA_APP_KEY), covers India well
  jsonfeed   - any URL returning a list of job objects (your own aggregator)
  fixture    - a local JSON file, used by the tests
"""
from __future__ import annotations

import json
import pathlib
import re
import time
from dataclasses import asdict, dataclass, field

from core import config, http
from core.crawler import strip_tags
from core.log import get_logger

log = get_logger("jobs")


@dataclass
class Job:
    id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    remote: bool = False
    url: str = ""
    apply_url: str = ""
    description: str = ""
    salary_min: float = 0.0
    salary_max: float = 0.0
    salary_currency: str = ""
    salary_period: str = "year"
    posted_at: float = 0.0
    source: str = ""
    contact_email: str = ""
    raw: dict = field(default_factory=dict)

    def key(self) -> str:
        return f"{self.company.strip().lower()}|{re.sub(r'[^a-z0-9]+', '', self.title.lower())}"

    def to_json(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


def _clean(text: str, limit: int = 12000) -> str:
    return strip_tags(text or "")[:limit]


class Source:
    name = "base"

    def fetch(self, query: str, **kw) -> list[Job]:
        raise NotImplementedError


class GreenhouseSource(Source):
    """Public board API. Companies are listed in GREENHOUSE_BOARDS."""
    name = "greenhouse"

    def fetch(self, query: str, **kw) -> list[Job]:
        boards = config.get_list("GREENHOUSE_BOARDS", [])
        base = config.get("GREENHOUSE_BASE", "https://boards-api.greenhouse.io")
        out = []
        for board in boards:
            try:
                data = http.get(f"{base}/v1/boards/{board}/jobs",
                                params={"content": "true"}, timeout=30
                                ).raise_for_status().json()
            except Exception as exc:  # noqa: BLE001
                log.warn(f"greenhouse board {board} failed: {exc}")
                continue
            for j in data.get("jobs", []) or []:
                out.append(Job(
                    id=f"gh-{board}-{j.get('id')}", title=j.get("title", ""),
                    company=board, location=(j.get("location") or {}).get("name", ""),
                    url=j.get("absolute_url", ""), apply_url=j.get("absolute_url", ""),
                    description=_clean(j.get("content", "")),
                    posted_at=_parse_ts(j.get("updated_at")), source=self.name, raw=j))
        return out


class LeverSource(Source):
    name = "lever"

    def fetch(self, query: str, **kw) -> list[Job]:
        companies = config.get_list("LEVER_COMPANIES", [])
        base = config.get("LEVER_BASE", "https://api.lever.co")
        out = []
        for c in companies:
            try:
                data = http.get(f"{base}/v0/postings/{c}", params={"mode": "json"},
                                timeout=30).raise_for_status().json()
            except Exception as exc:  # noqa: BLE001
                log.warn(f"lever company {c} failed: {exc}")
                continue
            for j in data or []:
                cats = j.get("categories", {}) or {}
                out.append(Job(
                    id=f"lv-{j.get('id')}", title=j.get("text", ""), company=c,
                    location=cats.get("location", ""),
                    remote="remote" in (cats.get("location", "") or "").lower(),
                    url=j.get("hostedUrl", ""), apply_url=j.get("applyUrl", ""),
                    description=_clean(j.get("descriptionPlain")
                                       or j.get("description", "")),
                    posted_at=(j.get("createdAt", 0) or 0) / 1000.0,
                    source=self.name, raw=j))
        return out


class RemotiveSource(Source):
    name = "remotive"

    def fetch(self, query: str, **kw) -> list[Job]:
        base = config.get("REMOTIVE_BASE", "https://remotive.com")
        data = http.get(f"{base}/api/remote-jobs",
                        params={"search": query, "limit": kw.get("limit", 50)},
                        timeout=40).raise_for_status().json()
        return [Job(
            id=f"rm-{j.get('id')}", title=j.get("title", ""),
            company=j.get("company_name", ""),
            location=j.get("candidate_required_location", ""), remote=True,
            url=j.get("url", ""), apply_url=j.get("url", ""),
            description=_clean(j.get("description", "")),
            posted_at=_parse_ts(j.get("publication_date")),
            source=self.name, raw=j) for j in (data.get("jobs", []) or [])]


class RemoteOKSource(Source):
    name = "remoteok"

    def fetch(self, query: str, **kw) -> list[Job]:
        base = config.get("REMOTEOK_BASE", "https://remoteok.com")
        data = http.get(f"{base}/api", timeout=40).raise_for_status().json()
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        out = []
        for j in data:
            if not isinstance(j, dict) or not j.get("position"):
                continue
            blob = f"{j.get('position','')} {' '.join(j.get('tags',[]) or [])}".lower()
            if terms and not any(t in blob for t in terms):
                continue
            out.append(Job(
                id=f"ro-{j.get('id')}", title=j.get("position", ""),
                company=j.get("company", ""), location=j.get("location", ""),
                remote=True, url=j.get("url", ""), apply_url=j.get("apply_url")
                or j.get("url", ""), description=_clean(j.get("description", "")),
                salary_min=float(j.get("salary_min") or 0),
                salary_max=float(j.get("salary_max") or 0),
                salary_currency="USD", posted_at=_parse_ts(j.get("date")),
                source=self.name, raw=j))
        return out


class AdzunaSource(Source):
    """Good coverage of the Indian market, unlike most remote-only boards."""
    name = "adzuna"

    def fetch(self, query: str, **kw) -> list[Job]:
        app_id = config.require("ADZUNA_APP_ID")
        app_key = config.require("ADZUNA_APP_KEY")
        country = config.get("ADZUNA_COUNTRY", "in")
        base = config.get("ADZUNA_BASE", "https://api.adzuna.com")
        data = http.get(f"{base}/v1/api/jobs/{country}/search/1", timeout=40,
                        params={"app_id": app_id, "app_key": app_key,
                                "what": query, "results_per_page": kw.get("limit", 50),
                                "content-type": "application/json"}
                        ).raise_for_status().json()
        return [Job(
            id=f"az-{j.get('id')}", title=j.get("title", ""),
            company=(j.get("company") or {}).get("display_name", ""),
            location=(j.get("location") or {}).get("display_name", ""),
            url=j.get("redirect_url", ""), apply_url=j.get("redirect_url", ""),
            description=_clean(j.get("description", "")),
            salary_min=float(j.get("salary_min") or 0),
            salary_max=float(j.get("salary_max") or 0), salary_currency="INR",
            posted_at=_parse_ts(j.get("created")), source=self.name, raw=j)
            for j in (data.get("results", []) or [])]


class JsonFeedSource(Source):
    name = "jsonfeed"

    def fetch(self, query: str, **kw) -> list[Job]:
        url = config.require("JOB_FEED_URL")
        data = http.get(url, timeout=40).raise_for_status().json()
        items = data.get("jobs", data) if isinstance(data, dict) else data
        return [_from_generic(j, self.name) for j in (items or [])]


class FixtureSource(Source):
    name = "fixture"

    def fetch(self, query: str, **kw) -> list[Job]:
        path = pathlib.Path(config.require("JOB_FIXTURE_FILE"))
        items = json.loads(path.read_text(encoding="utf-8"))
        items = items.get("jobs", items) if isinstance(items, dict) else items
        return [_from_generic(j, self.name) for j in items]


def _from_generic(j: dict, source: str) -> Job:
    return Job(
        id=str(j.get("id") or j.get("slug") or j.get("url", ""))[:80],
        title=j.get("title", ""), company=j.get("company", ""),
        location=j.get("location", ""), remote=bool(j.get("remote")),
        url=j.get("url", ""), apply_url=j.get("apply_url") or j.get("url", ""),
        description=_clean(j.get("description", "")),
        salary_min=float(j.get("salary_min") or 0),
        salary_max=float(j.get("salary_max") or 0),
        salary_currency=j.get("salary_currency", ""),
        salary_period=j.get("salary_period", "year"),
        posted_at=_parse_ts(j.get("posted_at")) or time.time(),
        contact_email=j.get("contact_email", ""), source=source, raw=j)


def _parse_ts(value) -> float:
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) / (1000.0 if value > 1e11 else 1.0)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return time.mktime(time.strptime(str(value)[:19], fmt))
        except ValueError:
            continue
    return 0.0


SOURCES = {c.name: c for c in (GreenhouseSource, LeverSource, RemotiveSource,
                               RemoteOKSource, AdzunaSource, JsonFeedSource,
                               FixtureSource)}


def _register_indian_boards() -> None:
    """Add linkedin and naukri to SOURCES, once.

    boards_in imports Job and Source from this module, so registering them at
    import time here deadlocks: whichever module is imported first finds the
    other half-built. Importing on demand breaks the cycle, and boards_in
    registers itself on the way in as well, so either entry point works.
    """
    if "linkedin" in SOURCES:
        return
    from .boards_in import LinkedInSource, NaukriSource
    SOURCES.update({c.name: c for c in (LinkedInSource, NaukriSource)})


def aggregate(queries: list[str], sources: list[str] | None = None,
              limit_per_source: int = 50) -> list[Job]:
    """Fan out across boards and return a deduplicated list."""
    _register_indian_boards()
    names = sources or config.get_list("JOB_SOURCES", ["remotive"])
    seen, out = set(), []
    for name in names:
        cls = SOURCES.get(name)
        if cls is None:
            log.warn(f"unknown job source {name!r}; known: {sorted(SOURCES)}")
            continue
        src = cls()
        for q in queries:
            try:
                jobs = src.fetch(q, limit=limit_per_source)
            except Exception as exc:  # noqa: BLE001
                log.warn(f"source {name} failed for {q!r}: {exc}")
                continue
            for j in jobs:
                k = j.key()
                if k in seen:
                    continue
                seen.add(k)
                out.append(j)
    log.info("job aggregation complete", sources=names, queries=len(queries),
             unique=len(out))
    return out
