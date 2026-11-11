"""Where new sponsors come from.

Every source here works with no API key, because a tool that stops working the
month a free tier runs out is not a tool. A web search provider is used as well
when one is configured, but nothing depends on it.

The sources are ordered by how direct the signal is:

  cuelinks       an affiliate network's live campaign directory. Every entry is
                 an Indian brand paying commission right now, with the payout
                 printed next to it. About 1,800 campaigns, refreshed
                 constantly. This is the strongest source on the list.
  admitad        the same idea, filtered to India-targeted offers.
  youtube        who is already sponsoring other cricket channels. A brand
                 paying a rival for a read has decided that a cricket audience
                 is worth money - there is no stronger signal than that.
  trade_press    Indian marketing and startup press. New brands, new campaigns
                 and new funding rounds appear here before anywhere else, which
                 is how you reach a brand in the month it starts spending.
  search         only when a search key is configured.

Each source returns raw candidates. Nothing here decides whether a candidate is
any good - that happens later, once the site has been read.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field

from core import config, http
from core.crawler import strip_tags
from core.log import get_logger

log = get_logger("sponsorship.sources")

SOCIAL_HOSTS = {
    "youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.com",
    "twitter.com", "x.com", "linkedin.com", "t.me", "telegram.me",
    "whatsapp.com", "wa.me", "threads.net", "pinterest.com", "reddit.com",
    "discord.gg", "discord.com", "snapchat.com", "tiktok.com",
}
# Link shorteners and tracking hosts hide the real advertiser, and app-store
# links name the app rather than the company.
OPAQUE_HOSTS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "rb.gy", "cutt.ly", "linktr.ee",
    "beacons.ai", "bio.link", "play.google.com", "apps.apple.com",
    "onelink.me", "app.link", "smart.link", "tinyurl.ph", "shorturl.at",
    "amzn.to", "fkrt.it", "clnk.in", "cuelinks.com", "inrdeals.com",
    "earnkaro.com", "admitad.com", "wa.link", "chng.it", "onelink.to",
    "onelink.me", "gmail.com", "google.com", "forms.gle", "docs.google.com",
    "patreon.com", "buymeacoffee.com",
}


@dataclass
class Candidate:
    """Something that might be worth pitching. Unverified."""
    name: str
    url: str = ""
    source: str = ""
    source_url: str = ""
    note: str = ""
    deal_type: str = ""
    payout: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def domain(self) -> str:
        host = urllib.parse.urlsplit(self.url or "").netloc.lower()
        return host.removeprefix("www.")


def _get(url: str, timeout: float = 20.0):
    return http.get(url, headers=dict(http.BROWSER_HEADERS), timeout=timeout,
                    retries=1)


def _useful_host(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    if not host or "." not in host:
        return False
    return not any(host == h or host.endswith("." + h)
                   for h in SOCIAL_HOSTS | OPAQUE_HOSTS)


# ---------------------------------------------------------------------------
# 1. Cuelinks campaign directory
# ---------------------------------------------------------------------------
CUELINKS_LIST = "https://www.cuelinks.com/campaigns"
_CUE_SLUG = re.compile(r'href="(/campaigns/([a-z0-9\-]+)-affiliate-program)"')


def cuelinks(pages: int = 4, resolve: int = 30) -> list[Candidate]:
    """Brands currently paying commission, straight off the network.

    The listing gives a name and a payout. The campaign page carries the
    merchant's own domain as its first outbound link, which is what turns a
    name into something we can actually read and contact.
    """
    found: dict[str, Candidate] = {}
    for page in range(1, max(1, pages) + 1):
        url = CUELINKS_LIST if page == 1 else f"{CUELINKS_LIST}?page={page}"
        try:
            html = _get(url).text
        except Exception as exc:  # noqa: BLE001
            log.warn(f"cuelinks page {page} failed: {exc}")
            break
        text = strip_tags(html)
        payouts = dict(re.findall(
            r"([A-Z][\w&'.\- ]{2,40}?)\s*Payout Upto[:\s]*([^\n]{1,40})", text))
        for path, slug in _CUE_SLUG.findall(html):
            name = slug.replace("-", " ").title()
            if slug in found:
                continue
            payout = ""
            for k, v in payouts.items():
                if k.strip().lower().replace(" ", "") == name.lower().replace(" ", ""):
                    payout = v.strip()
                    break
            found[slug] = Candidate(
                name=name, source="cuelinks",
                source_url=urllib.parse.urljoin(CUELINKS_LIST, path),
                payout=payout, deal_type="affiliate",
                note=f"Live affiliate campaign{', ' + payout if payout else ''}")
    # Resolving costs a request each, so only the first `resolve` get one.
    for cand in list(found.values())[:resolve]:
        try:
            page = _get(cand.source_url).text
        except Exception:  # noqa: BLE001
            continue
        for link in re.findall(r'href="(https?://[^"]+)"', page):
            host = urllib.parse.urlsplit(link).netloc.lower()
            if _useful_host(host):
                cand.url = f"https://{host.removeprefix('www.')}"
                break
    out = [c for c in found.values() if c.url]
    log.info("cuelinks sweep", listed=len(found), resolved=len(out))
    return out


# ---------------------------------------------------------------------------
# 2. Admitad, India-targeted offers only
# ---------------------------------------------------------------------------
def admitad(limit: int = 40) -> list[Candidate]:
    out: list[Candidate] = []
    try:
        html = _get("https://www.admitad.com/store/").text
    except Exception as exc:  # noqa: BLE001
        log.warn(f"admitad sweep failed: {exc}")
        return out
    # Offer slugs carry a country suffix; -in is India.
    for slug in dict.fromkeys(re.findall(r"/offers/([a-z0-9\-]+-in)/", html)):
        name = re.sub(r"-(cps|cpa|cpl|cpi|in)$", "", slug).replace("-", " ").title()
        out.append(Candidate(
            name=name, source="admitad",
            source_url=f"https://www.admitad.com/store/offers/{slug}/",
            deal_type="affiliate",
            note="India-targeted affiliate offer"))
        if len(out) >= limit:
            break
    log.info("admitad sweep", found=len(out))
    return out


# ---------------------------------------------------------------------------
# 3. Who is sponsoring the competition
# ---------------------------------------------------------------------------
YT_SEARCH = "https://www.youtube.com/results?search_query="
DEFAULT_QUERIES = [
    "cricket analysis hindi", "cricket documentary hindi",
    "ipl analysis hindi", "cricket news hindi", "cricket highlights analysis",
]
_VIDEO_ID = re.compile(r'"videoId":"([\w\-]{11})"')
_DESC = re.compile(r'"attributedDescription":\{"content":"(.*?)","', re.S)


def _unescape_json(s: str) -> str:
    try:
        return s.encode("utf-8").decode("unicode_escape")
    except Exception:  # noqa: BLE001
        return s


def youtube_sponsors(queries: list[str] | None = None, channels: int = 3,
                     videos_per_channel: int = 4,
                     pause: float | None = None) -> list[Candidate]:
    """Read the sponsor links out of other cricket creators' descriptions.

    If a brand paid another cricket channel for a read, it has already decided
    a cricket audience is worth money, has a budget, and has someone whose job
    is to place it. That is a better lead than any listicle.
    """
    queries = queries or DEFAULT_QUERIES
    if pause is None:
        pause = config.get_float("YOUTUBE_MINE_PAUSE", 2.0)
    handles: list[str] = []
    for q in queries:
        try:
            html = _get(YT_SEARCH + urllib.parse.quote(q)).text
        except Exception as exc:  # noqa: BLE001
            log.warn(f"youtube search failed for {q!r}: {exc}")
            continue
        for h in re.findall(r'"canonicalBaseUrl":"/(@[\w\-.]+)"', html):
            if h not in handles:
                handles.append(h)
        if len(handles) >= channels * len(queries):
            break

    seen: dict[str, Candidate] = {}
    for handle in handles[: channels * 2]:
        try:
            page = _get(f"https://www.youtube.com/{handle}/videos").text
        except Exception:  # noqa: BLE001
            continue
        # The channel's own site keeps appearing in its own descriptions, and
        # it is not a sponsor. Drop anything that reads like the handle.
        own = re.sub(r"[^a-z0-9]+", "", handle.lower().lstrip("@"))[:10]
        for vid in list(dict.fromkeys(_VIDEO_ID.findall(page)))[:videos_per_channel]:
            time.sleep(pause)          # YouTube rate-limits hard otherwise
            try:
                watch = _get(f"https://www.youtube.com/watch?v={vid}").text
            except Exception:  # noqa: BLE001
                continue
            m = _DESC.search(watch)
            if not m:
                continue
            desc = _unescape_json(m.group(1))
            for link in re.findall(r"https?://[^\s\"'|\\)]+", desc):
                host = urllib.parse.urlsplit(link).netloc.lower().removeprefix("www.")
                if not _useful_host(host) or host in seen:
                    continue
                flat = re.sub(r"[^a-z0-9]+", "", host)
                if own and len(own) >= 5 and own[:6] in flat:
                    continue           # the channel's own site, not a sponsor
                seen[host] = Candidate(
                    name=host.rsplit(".", 2)[0].replace("-", " ").title(),
                    url=f"https://{host}", source="youtube",
                    source_url=f"https://www.youtube.com/watch?v={vid}",
                    deal_type="cash",
                    note=f"Already sponsoring {handle} on YouTube")
    log.info("youtube sponsor mining", channels=len(handles), found=len(seen))
    return list(seen.values())


# ---------------------------------------------------------------------------
# 4. Indian marketing and startup press
# ---------------------------------------------------------------------------
PRESS_FEEDS = [
    ("https://www.socialsamosa.com/category/digital/", "Social Samosa"),
    ("https://www.storyboard18.com/brand-makers/", "Storyboard18"),
    ("https://www.afaqs.com/news/advertising", "afaqs"),
    ("https://www.campaignindia.in/", "Campaign India"),
    ("https://brandequity.economictimes.indiatimes.com/news/marketing",
     "ET BrandEquity"),
    ("https://entrackr.com/", "Entrackr"),
    ("https://inc42.com/features/", "Inc42"),
]
# Verbs that mean a brand is spending money on marketing. Appointment news
# ("Sai Ganesh joins Emergent") is deliberately excluded, because the leading
# capitalised phrase there is a person, not a company.
SPEND_VERBS = (
    r"launch\w*|unveil\w*|roll\w* out|announce\w*|debut\w*|introduc\w*|"
    r"kick\w* off|partner\w*|rope\w* in|sign\w*|onboard\w*|tie\w* up|"
    r"collaborat\w*|bet\w* on|go\w* big on|doubl\w* down on|raise[sd]?|"
    r"bring\w*|celebrat\w*|take\w* on|trace\w*|spark\w*|drop\w*|return\w* with|"
    r"expand\w*|enter\w*|back\w*|tap\w*|pick\w*|unwrap\w*|reveal\w*"
)
NAME = r"[A-Z][\w&.'’\-]*(?:\s+(?:by\s+)?[A-Z0-9][\w&.'’\-]*){0,3}"

HEADLINE_PATTERNS = [
    # "Max Cement launches ...", "Timex bets on ..."
    re.compile(rf"^({NAME})\s+(?:{SPEND_VERBS})\b"),
    # "Porter's new campaign ...", "BabyOrgano's latest campaign ..."
    re.compile(rf"^({NAME})['’]s\s+(?:new|latest|first|festive|latest)?\s*"
               rf"(?:campaign|ad|film|spot|push|launch|collab\w*)\b"),
]

# Section labels that some sites prepend to the headline inside the same link.
SECTION_PREFIX = re.compile(
    r"^(?:STORY OF THE DAY|BRAND MAKERS|EXCLUSIVE|WATCH|OPINION|HOW TO|"
    r"INFOGRAPHIC|DECADE SAMOSA|BRAND\s?MAKERS)\s*[:\-]?\s*", re.I)
STOPWORDS = {
    "the", "this", "how", "why", "what", "india", "indian", "new", "top",
    "best", "watch", "exclusive", "opinion", "report", "brand", "brands",
    "marketing", "advertising", "campaign", "creator", "creators", "agency",
    "here", "these", "from", "with", "after", "amid", "meet", "inside",
}


def _brand_from_headline(title: str) -> str:
    title = SECTION_PREFIX.sub("", re.sub(r"\s+", " ", title).strip())
    for rx in HEADLINE_PATTERNS:
        m = rx.match(title)
        if not m:
            continue
        name = m.group(1).strip(" '’")
        words = name.split()
        if not words or words[0].lower() in STOPWORDS:
            return ""
        # A run of four capitalised words is usually a sentence, not a brand.
        if len(words) > 3 or len(name) < 3 or len(name) > 40:
            return ""
        return name
    return ""


def trade_press(feeds: list | None = None, per_feed: int = 30) -> list[Candidate]:
    """Brand names lifted out of headlines. Domains are resolved later."""
    feeds = feeds or PRESS_FEEDS
    out: dict[str, Candidate] = {}
    for url, label in feeds:
        try:
            html = _get(url).text
        except Exception as exc:  # noqa: BLE001
            log.warn(f"{label} failed: {exc}")
            continue
        seen_here = 0
        for href, inner in re.findall(
                r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            title = strip_tags(inner).strip()
            if len(title) < 25 or len(title) > 180:
                continue
            brand = _brand_from_headline(title)
            if not brand or brand.lower() in out:
                continue
            out[brand.lower()] = Candidate(
                name=brand, source="trade_press",
                source_url=urllib.parse.urljoin(url, href),
                deal_type="cash",
                note=f"{label}: {title[:110]}")
            seen_here += 1
            if seen_here >= per_feed:
                break
    log.info("trade press sweep", found=len(out))
    return list(out.values())


# ---------------------------------------------------------------------------
# Turning a brand name into a website, with no search key
# ---------------------------------------------------------------------------
TLDS = [".in", ".com", ".co.in", ".store", ".life", ".club"]


def resolve_domain(name: str) -> str:
    """Try the domains a brand of this name would plausibly own.

    Cheap and surprisingly effective for Indian D2C brands, which almost always
    hold the obvious .in or .com. A wrong guess is caught downstream, because
    the site still has to read as that brand and as Indian before it is kept.
    """
    slug = re.sub(r"[^a-z0-9]+", "", name.lower())
    if len(slug) < 3:
        return ""
    for tld in TLDS:
        url = f"https://{slug}{tld}"
        try:
            resp = http.get(url, headers=dict(http.BROWSER_HEADERS), timeout=8,
                            retries=0, allow_status=set(range(200, 600)))
        except Exception:  # noqa: BLE001
            continue
        if 200 <= resp.status < 400:
            body = (resp.text or "")[:60000].lower()
            # Guard against parking pages and unrelated squatters.
            if "domain is for sale" in body or "buy this domain" in body:
                continue
            if slug[:6] in re.sub(r"[^a-z0-9]+", "", body[:8000]):
                return url
    return ""


# ---------------------------------------------------------------------------
# Plain web search, with no API key
# ---------------------------------------------------------------------------
# Several open front-ends that answer an ordinary GET. They are tried in turn
# and the first that returns real links wins, because any single one of them
# may be rate-limiting, challenging, or down on a given day.
OPEN_ENGINES = [
    ("duckduckgo", "https://html.duckduckgo.com/html/?q={q}"),
    ("duckduckgo-lite", "https://lite.duckduckgo.com/lite/?q={q}"),
    ("mojeek", "https://www.mojeek.com/search?q={q}"),
    ("searx-inetol", "https://search.inetol.net/search?q={q}"),
    ("searx-opnxng", "https://opnxng.com/search?q={q}"),
    ("searx-priv", "https://priv.au/search?q={q}"),
    ("marginalia", "https://search.marginalia.nu/search?query={q}"),
]
_DDG_REDIRECT = re.compile(r"/l/\?uddg=([^&\"']+)")
# The engines' own infrastructure, plus the archives and directories that
# always show up in their results and are never a brand.
_ENGINE_HOSTS = {
    "duckduckgo.com", "mojeek.com", "inetol.net", "opnxng.com", "priv.au",
    "marginalia.nu", "marginalia-search.com", "searx.space", "vojk.au",
    "w3.org", "github.com", "creativecommons.org", "torproject.org",
    "techaro.lol", "web.archive.org", "archive.org", "wikipedia.org",
    "wikimedia.org", "scholar.google.com", "researchgate.net", "arxiv.org",
    "medium.com", "quora.com", "slideshare.net", "issuu.com", "scribd.com",
    "gov.in", "nic.in", "edu", "ac.in", "duke.edu",
}


def _result_links(html: str) -> list[str]:
    """Pull the outbound result links out of a search page."""
    out, seen = [], set()
    # DuckDuckGo wraps results in its own redirector.
    for enc in _DDG_REDIRECT.findall(html):
        url = urllib.parse.unquote(enc)
        if url.startswith("http") and url not in seen:
            seen.add(url)
            out.append(url)
    for url in re.findall(r'href="(https?://[^"]+)"', html):
        host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
        if any(host == h or host.endswith("." + h) for h in _ENGINE_HOSTS):
            continue
        if not _useful_host(host) or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def search_web(query: str, limit: int = 12) -> list[str]:
    """Search the internet for anything. Returns result URLs.

    No API key needed. If every open front-end refuses - some of them block
    datacentre addresses, and all of them rate-limit - and a search provider IS
    configured, that is used instead. If neither works the caller gets an empty
    list rather than an exception, because the other sources do not depend on
    this one.
    """
    q = urllib.parse.quote(query)
    for name, template in OPEN_ENGINES:
        try:
            resp = http.get(template.format(q=q),
                            headers=dict(http.BROWSER_HEADERS),
                            timeout=config.get_float("SEARCH_TIMEOUT", 12),
                            retries=0,
                            allow_status=set(range(200, 600)))
        except Exception as exc:  # noqa: BLE001
            log.debug(f"{name} failed: {exc}")
            continue
        if resp.status >= 400:
            log.debug(f"{name} returned {resp.status}")
            continue
        links = _result_links(resp.text)
        if links:
            log.info("web search", engine=name, query=query[:60],
                     results=len(links))
            return links[:limit]
    provider = (config.get("SEARCH_PROVIDER", "seeds") or "seeds").lower()
    if provider not in ("seeds", "chatgpt_web", ""):
        try:
            from core.search import get_search
            hits = get_search(provider).search(query, count=limit)
            log.info("web search via provider", provider=provider,
                     results=len(hits))
            return [h.url for h in hits]
        except Exception as exc:  # noqa: BLE001
            log.warn(f"search provider {provider} failed: {exc}")
    log.warn("every search engine refused this query", query=query[:60])
    return []


# What to ask the web when looking for brands that pay creators. Kept short and
# specific - broad queries return listicles, these return programme pages.
SEARCH_QUERIES = [
    "brand influencer collaboration programme india apply form",
    "creator partnership programme india d2c brand",
    "new affiliate programme india brand sign up 2026",
    "cricket brand sponsorship indian creators apply",
    "influencer barter collaboration india application",
    "\"collaborate with us\" influencer india brand",
]


def open_search(queries: list[str] | None = None,
                per_query: int = 8) -> list[Candidate]:
    """Anything the open web turns up for the standing questions."""
    out: dict[str, Candidate] = {}
    for q in (queries or SEARCH_QUERIES):
        for url in search_web(q, limit=per_query):
            host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
            if host in out:
                continue
            out[host] = Candidate(
                name=host.rsplit(".", 2)[0].replace("-", " ").title(),
                url=f"https://{host}", source="web_search", source_url=url,
                note=f"Found by searching: {q[:80]}")
    log.info("open web search sweep", found=len(out))
    return list(out.values())


# ---------------------------------------------------------------------------
# Optional: a configured search provider, used directly
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "brand influencer collaboration programme india apply",
    "creator partnership programme india d2c brand",
    "affiliate programme india new brand sign up",
    "cricket brand sponsorship creators india",
    "influencer barter collaboration india apply form",
]


SOURCES = {
    "cuelinks": cuelinks,
    "admitad": admitad,
    "youtube": youtube_sponsors,
    "trade_press": trade_press,
    "web_search": open_search,
}
