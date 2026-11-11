"""Lead discovery - pluggable web search plus a curated seed-list provider.

SEARCH_PROVIDER picks the backend:

  seeds   - read targets from a local YAML/JSON list (default; no API key, and
            frankly the highest-precision option for a niche like fantasy
            cricket, where you already know the twenty companies that matter)
  brave   - Brave Search API   (BRAVE_API_KEY)
  serper  - Serper.dev         (SERPER_API_KEY)
  searxng - your own SearXNG   (SEARXNG_URL)

All providers return the same shape, so agents do not care which is in use.
"""
from __future__ import annotations

import json
import pathlib
import re
import urllib.parse
from dataclasses import dataclass, field

from . import config, http
from .log import get_logger
from .yamlite import load_yaml

log = get_logger("search")


@dataclass
class SearchHit:
    url: str
    title: str = ""
    snippet: str = ""
    source: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def domain(self) -> str:
        return urllib.parse.urlsplit(self.url).netloc.lower().removeprefix("www.")


class SearchProvider:
    name = "base"

    def search(self, query: str, count: int = 10, **kw) -> list[SearchHit]:
        raise NotImplementedError


class SeedsProvider(SearchProvider):
    """Targets curated in a file. Precise, free, and auditable."""
    name = "seeds"

    def __init__(self, path: str | None = None):
        self.path = pathlib.Path(
            path or config.get("SEEDS_FILE", str(config.ROOT / "profiles" / "targets.yaml")))
        self._cache: list[dict] | None = None

    def load(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            log.warn(f"seeds file {self.path} not found; no targets available")
            self._cache = []
            return self._cache
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw) if self.path.suffix == ".json" else load_yaml(raw)
        items = data.get("targets", data) if isinstance(data, dict) else data
        out = []
        for it in items or []:
            if isinstance(it, str):
                out.append({"url": it, "name": it})
            elif isinstance(it, dict):
                out.append(it)
        self._cache = out
        return out

    def search(self, query: str, count: int = 10, *, category: str | None = None,
               **kw) -> list[SearchHit]:
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        hits = []
        for item in self.load():
            if category and item.get("category") != category:
                continue
            blob = " ".join(str(v) for v in item.values()).lower()
            score = sum(1 for t in terms if t in blob)
            if terms and score == 0 and not category:
                continue
            url = item.get("url") or item.get("website") or item.get("domain", "")
            if url and not url.startswith("http"):
                url = "https://" + url
            if not url:
                continue
            hits.append((score, SearchHit(
                url=url, title=item.get("name", ""),
                snippet=item.get("note", item.get("description", "")),
                source="seeds", meta=item)))
        hits.sort(key=lambda x: -x[0])
        return [h for _, h in hits[:count]]


class BraveProvider(SearchProvider):
    name = "brave"

    def search(self, query: str, count: int = 10, **kw) -> list[SearchHit]:
        key = config.require("BRAVE_API_KEY")
        data = http.get("https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": min(count, 20)},
                        headers={"X-Subscription-Token": key,
                                 "Accept": "application/json"},
                        timeout=30).raise_for_status().json()
        return [SearchHit(url=r.get("url", ""), title=r.get("title", ""),
                          snippet=re.sub("<[^>]+>", "", r.get("description", "")),
                          source="brave")
                for r in (data.get("web", {}).get("results", []) or [])]


class SerperProvider(SearchProvider):
    name = "serper"

    def search(self, query: str, count: int = 10, **kw) -> list[SearchHit]:
        key = config.require("SERPER_API_KEY")
        data = http.post("https://google.serper.dev/search",
                         json_body={"q": query, "num": min(count, 20),
                                    "gl": config.get("SEARCH_COUNTRY", "in")},
                         headers={"X-API-KEY": key},
                         timeout=30).raise_for_status().json()
        return [SearchHit(url=r.get("link", ""), title=r.get("title", ""),
                          snippet=r.get("snippet", ""), source="serper")
                for r in (data.get("organic", []) or [])]


class SearxngProvider(SearchProvider):
    name = "searxng"

    def search(self, query: str, count: int = 10, **kw) -> list[SearchHit]:
        base = config.require("SEARXNG_URL").rstrip("/")
        data = http.get(f"{base}/search",
                        params={"q": query, "format": "json"},
                        timeout=30).raise_for_status().json()
        return [SearchHit(url=r.get("url", ""), title=r.get("title", ""),
                          snippet=r.get("content", ""), source="searxng")
                for r in (data.get("results", []) or [])[:count]]


class ChatGPTWebProvider(SearchProvider):
    """Bounded public discovery through the signed-in Codex web search tool."""
    name = "chatgpt_web"

    def search(self, query: str, count: int = 10, **kw) -> list[SearchHit]:
        return self.search_many([query], count=count, **kw)

    def search_many(self, queries, count=10, **kw):
        from .workflow_brain import ChatGPTProvider, ChatGPTUnavailable, cloud_unavailable, record_outage

        limit = max(1, min(int(count), 12))
        schema = {"type": "object", "properties": {"hits": {"type": "array",
                  "items": {"type": "object", "properties": {
                      "url": {"type": "string"}, "title": {"type": "string"},
                      "quote": {"type": "string"}, "organization": {"type": "string"},
                  }}}}}
        prompt = (
            f"Use live web search to find up to {limit} relevant public sources. "
            "Use the direct source page, avoiding result pages, aggregators and tracking links. "
            "Return a short, exact, contiguous source quote for each hit and the published "
            "organization when identifiable. Never infer private information or fabricate a URL. "
            "Skip any candidate you cannot source. Search queries: " + json.dumps(queries)
        )
        integrated = config.get_bool('SUITE_STORYLENS_INTEGRATED')
        try:
            if integrated and (reason := cloud_unavailable()):
                raise ChatGPTUnavailable(reason)
            answer = ChatGPTProvider().search(prompt, schema)
        except ChatGPTUnavailable as error:
            if not integrated:
                raise
            if not cloud_unavailable():
                record_outage(error)
            if kw.get('demand_query'):
                return public_demand_search(kw['demand_query'], limit)
            log.info('Discovery using curated targets while ChatGPT search is unavailable')
            return SeedsProvider().search(' '.join(queries), count=limit, **kw)
        hits = []
        for item in answer["hits"][:limit]:
            url = item["url"].strip()
            if not public_web_url(url):
                continue
            quote = item["quote"].strip()
            if quote:
                hits.append(SearchHit(url, item["title"][:250], quote[:500], self.name,
                                      {"organization": item["organization"][:150]}))
        return hits


def public_demand_search(query, count):
    """Search an ordinary public feed without an authenticated Reddit session."""
    import html
    import xml.etree.ElementTree as ET

    words = re.findall(r'[a-z0-9_-]+', query.lower())
    useful = [word for word in words if word in {'caption', 'captions', 'subtitle', 'subtitles',
              'srt', 'transcription', 'retakes', 'silence', 'multicam', 'export', 'reframe', 'shorts', 'proxy'}]
    term = ' OR '.join(dict.fromkeys(useful[:3])) or query[:100]
    community = 'premiere' if 'premiere' in words else 'VideoEditing'
    try:
        response = http.get(f'https://www.reddit.com/r/{community}/search.rss',
                            params={'q': term, 'restrict_sr': '1', 'limit': count},
                            headers={'Accept': 'application/atom+xml', 'User-Agent': 'StorylensResearch/1.0'},
                            timeout=12, retries=0).raise_for_status()
        root = ET.fromstring(response.body)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        hits = []
        for entry in root.findall('atom:entry', ns)[:count]:
            link = entry.find('atom:link', ns)
            url = link.get('href', '') if link is not None else ''
            parts = urllib.parse.urlsplit(url)
            if not public_web_url(url) or parts.hostname not in ('reddit.com', 'www.reddit.com') or '/comments/' not in parts.path:
                continue
            title = (entry.findtext('atom:title', '', ns) or '').strip()
            source = entry.findtext('atom:content', '', ns) or ''
            match = re.search(r'<!--\s*SC_OFF\s*-->(.*?)<!--\s*SC_ON\s*-->', source, re.S)
            if match:
                source = match.group(1)
            quote = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', source)).split()) if match else title
            if quote:
                hits.append(SearchHit(url, title[:250], quote[:500], 'reddit_public_rss'))
        if hits:
            return hits
    except (http.HttpError, OSError, ValueError, ET.ParseError) as error:
        log.warn('Public Reddit research feed unavailable', error=type(error).__name__)
    return public_issue_search(query, count)


def public_issue_search(query, count):
    """Bounded, public source retrieval independent of ChatGPT and Ollama."""
    terms = [term for term in re.findall(r'[a-zA-Z0-9_-]+', query.lower()) if len(term) >= 3
             and term not in {'find', 'show', 'how', 'for', 'with', 'the', 'and', 'want', 'about', 'what', 'people', 'need'}]
    if not terms:
        return []
    try:
        result = http.get('https://api.github.com/search/issues',
                          params={'q': ' '.join(terms[:6]) + ' is:issue in:title,body', 'per_page': count},
                          headers={'Accept': 'application/vnd.github+json'},
                          timeout=12, retries=0).raise_for_status().json()
    except (http.HttpError, OSError, ValueError) as error:
        log.warn('Public issue search unavailable; research returned no verified leads', error=type(error).__name__)
        return []
    hits = []
    for issue in (result or {}).get('items', [])[:count]:
        url = issue.get('html_url', '')
        quote = (issue.get('body') or '').strip()
        if quote and public_web_url(url) and urllib.parse.urlsplit(url).hostname == 'github.com':
            lines = [line.strip() for line in quote.splitlines() if line.strip() and not line.startswith('<!--')]
            words = set(terms)
            excerpt = max(lines, key=lambda line: len(words.intersection(re.findall(r'[a-zA-Z0-9_-]+', line.lower()))), default='')
            if excerpt:
                hits.append(SearchHit(url, issue.get('title', '')[:250], excerpt[:500], 'github_public_issues'))
    return hits


def public_web_url(url: str) -> bool:
    import ipaddress
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        if (parts.scheme != "https" or "." not in host or parts.username or parts.password
                or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
                or parts.port not in (None, 443)):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return False
    except ValueError:
        return False


PROVIDERS = {
    "seeds": SeedsProvider, "brave": BraveProvider,
    "serper": SerperProvider, "searxng": SearxngProvider,
    "chatgpt_web": ChatGPTWebProvider,
}

BLOCKED_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "pinterest.com", "reddit.com", "quora.com", "youtube.com", "wikipedia.org",
    "glassdoor.com", "indeed.com", "crunchbase.com", "amazon.in", "amazon.com",
}


def get_search(provider: str | None = None) -> SearchProvider:
    name = (provider or config.get("SEARCH_PROVIDER", "seeds")).lower()
    if name not in PROVIDERS:
        raise ValueError(f"unknown SEARCH_PROVIDER {name!r}; "
                         f"choose from {sorted(PROVIDERS)}")
    return PROVIDERS[name]()


def discover(queries: list[str], per_query: int = 10, provider=None,
             exclude_domains: set | None = None, **kw) -> list[SearchHit]:
    """Run several queries, dedupe by domain, drop aggregators and socials."""
    prov = provider or get_search()
    excluded = BLOCKED_DOMAINS | set(exclude_domains or set())
    seen, out = set(), []
    def query_sources():
        if isinstance(prov, ChatGPTWebProvider):
            yield prov.search_many(queries, count=per_query, **kw)
            return
        for q in queries:
            try:
                yield prov.search(q, count=per_query, **kw)
            except Exception as exc:  # noqa: BLE001
                log.warn(f"search failed for {q!r}: {exc}")

    for hits in query_sources():
        for h in hits:
            d = h.domain
            if not d or d in seen or any(d == b or d.endswith("." + b)
                                         for b in excluded):
                continue
            seen.add(d)
            out.append(h)
    log.info("discovery complete", queries=len(queries), unique_domains=len(out))
    return out
