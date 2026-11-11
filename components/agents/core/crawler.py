"""Polite web crawling and contact extraction - the Crawl4AI role, stdlib only.

Given a site, it fetches a small, robots-respecting set of pages (home, about,
contact, team, partnerships), converts them to clean Markdown-ish text, and runs
two extraction strategies, exactly as the blueprint specifies:

  deterministic - regex sweep for mailto:, plain email addresses and phone
                  numbers, with Indian mobile formats (+91) handled explicitly
  semantic      - an LLM pass constrained by a schema, used to name the right
                  person ("Head of Partnerships") from an about/team page

Fallback hierarchy: prefer a direct email; if none is found keep the phone
number and flag the lead for manual follow-up rather than discarding it.
"""
from __future__ import annotations

import html as html_mod
import re
import urllib.parse
from dataclasses import dataclass, field

from . import config, http
from .log import get_logger
from .ratelimit import HostLimiter
from .schema import validate

log = get_logger("crawler")

CONTACT_PATHS = [
    "", "/contact", "/contact-us", "/contactus", "/about", "/about-us",
    "/team", "/our-team", "/leadership", "/partnerships", "/partner",
    "/advertise", "/sponsorship", "/press", "/media", "/work-with-us",
    # Shopify puts every static page under /pages/, and a large share of the
    # Indian D2C brands worth pitching run on Shopify. Without these the
    # crawler was walking past the one page with the address on it.
    "/pages/contact", "/pages/contact-us", "/pages/about-us",
    "/pages/collaborate", "/pages/influencer-collaboration",
    "/pages/partnership", "/pages/press",
    # Creator-programme pages, which is what we are actually looking for.
    "/collaborate", "/collaboration", "/influencer", "/influencers",
    "/creators", "/creator", "/brand-partnership", "/affiliate",
    "/affiliates", "/get-in-touch", "/connect", "/reach-us", "/support",
]

EMAIL_RE = re.compile(
    r"(?<![\w.+-])([A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24})(?![\w-])")

# Obfuscated addresses. Deliberately strict: a bare "at"/"." pair would match
# ordinary prose like "reach him at sanjay.kumar", inventing a contact that does
# not exist. So either the @ is bracketed, or the dot is spelled out as a word.
_BRACKET_AT = r"(?:\(|\[|\{)\s*(?:at|@)\s*(?:\)|\]|\})"
_BRACKET_DOT = r"(?:\(|\[|\{)?\s*dot\s*(?:\)|\]|\})?"
_LOCAL = r"([A-Za-z0-9._%+-]{2,64})"
_DOMAIN = r"([A-Za-z0-9-]{2,63}(?:\s*(?:\(|\[|\{)?\s*(?:dot|\.)\s*(?:\)|\]|\})?\s*[A-Za-z0-9-]{2,63})*)"
_TLD = r"([A-Za-z]{2,10})"

OBFUSCATED_RES = [
    # name (at) domain (dot) com  /  name [at] domain.com
    re.compile(rf"{_LOCAL}\s*{_BRACKET_AT}\s*([A-Za-z0-9.-]+)\s*"
               rf"(?:\(|\[|\{{)?\s*(?:dot|\.)\s*(?:\)|\]|\}})?\s*{_TLD}", re.I),
    # name at domain dot com  - requires the spelled-out "dot"
    re.compile(rf"{_LOCAL}\s+(?:at|@)\s+([A-Za-z0-9-]+)\s*{_BRACKET_DOT}\s*{_TLD}",
               re.I),
]

# Indian mobile: optional +91/0091/0, then 6-9 followed by 9 digits.
IN_PHONE_RE = re.compile(
    r"(?<!\d)(?:(?:\+|00)?91[\s.-]?|0)?([6-9]\d{4})[\s.-]?(\d{5})(?!\d)")
INTL_PHONE_RE = re.compile(r"(?<!\d)(\+\d{1,3})[\s.-]?(\d[\d\s.-]{6,14}\d)(?!\d)")

WHATSAPP_RE = re.compile(
    r"https?://(?:api\.whatsapp\.com/send[^\"'<>\s]*|wa\.me/[+\d][^\"'<>\s]*"
    r"|web\.whatsapp\.com/send[^\"'<>\s]*)", re.I)

# Sites very often publish contact details inside a schema.org JSON-LD block
# even when the visible page renders client-side, so this is frequently the
# only place an address survives on a modern single-page site.
JSONLD_EMAIL_RE = re.compile(r"\"email\"\s*:\s*\"(?:mailto:)?([^\"]{5,120})\"", re.I)
JSONLD_PHONE_RE = re.compile(r"\"telephone\"\s*:\s*\"([^\"]{6,32})\"", re.I)

SOCIAL_RE = {
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/[\w\-%.]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]{2,15})", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{2,30})", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@[\w\-.]+|c/[\w\-.]+|channel/[\w\-]+)", re.I),
}

JUNK_EMAIL_DOMAINS = {
    "example.com", "example.org", "sentry.io", "wixpress.com", "godaddy.com",
    "squarespace.com", "domain.com", "email.com", "yourdomain.com",
    "cloudflare.com", "w3.org", "schema.org", "gstatic.com",
}
JUNK_LOCALPARTS = {"your", "name", "email", "user", "username", "someone", "test",
                   "noreply", "no-reply", "donotreply", "do-not-reply",
                   "mailer-daemon", "postmaster", "abuse", "bounce", "bounces",
                   "unsubscribe", "privacy", "dmca", "webmaster"}

ROLE_HINTS = [
    ("partnership", 10), ("sponsorship", 10), ("brand", 7), ("marketing", 8),
    ("bizdev", 9), ("business development", 9), ("collab", 8), ("media", 5),
    ("press", 4), ("growth", 6), ("founder", 7), ("ceo", 6), ("hello", 3),
    ("contact", 2), ("info", 1), ("support", 0), ("sales", 3), ("careers", 0),
]

# Inboxes that belong to another department entirely. Mailing a sponsorship
# pitch to hr@ or returns@ does not get forwarded, it gets deleted, so these
# are pushed to the bottom rather than competing with a real business address.
WRONG_DEPARTMENT = [
    "hr@", "hr.", "careers", "career", "jobs", "job@", "hiring", "recruit",
    "resume", "cv@", "legal", "compliance", "grievance", "nodal",
    "invoice", "billing", "accounts", "payment", "refund", "returns",
    "orders", "order@", "complaint", "warranty", "helpdesk", "customercare",
    "customer.care", "wholesale", "vendor", "procurement",
]


@dataclass
class Contact:
    email: str = ""
    phone: str = ""
    name: str = ""
    role: str = ""
    source_url: str = ""
    confidence: float = 0.0
    channel: str = "email"   # email | whatsapp | form | social
    # True when the address was constructed from a common pattern rather than
    # read off the page. Guessed addresses are never sent without being shown
    # to you first, and they are labelled as guesses everywhere they appear.
    guessed: bool = False
    evidence: str = ""       # how this was found, in one human-readable line
    url: str = ""            # form URL or social profile, when that is the route

    @property
    def label(self) -> str:
        if self.email:
            return self.email + (" (guessed)" if self.guessed else "")
        if self.phone:
            return self.phone
        return self.url or "no contact"


@dataclass
class PageResult:
    url: str
    status: int = 0
    title: str = ""
    text: str = ""
    markdown: str = ""
    links: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    phones: list = field(default_factory=list)
    socials: dict = field(default_factory=dict)
    whatsapp: list = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.error


@dataclass
class SiteProfile:
    domain: str
    pages: list = field(default_factory=list)
    contacts: list = field(default_factory=list)
    socials: dict = field(default_factory=dict)
    title: str = ""
    description: str = ""
    tech: list = field(default_factory=list)
    contact_form_url: str = ""
    whatsapp: str = ""
    blocked: bool = False    # every page refused us (403 / bot wall)

    @property
    def best_contact(self) -> Contact | None:
        if not self.contacts:
            return None
        return sorted(self.contacts, key=lambda c: -c.confidence)[0]

    @property
    def combined_text(self) -> str:
        return "\n\n".join(p.markdown for p in self.pages if p.ok)[:40000]


# --------------------------------------------------------------------------
# HTML handling
# --------------------------------------------------------------------------
def strip_tags(html: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|section|article|tr|li|h[1-6]|td)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", s).strip()


def to_markdown(html: str) -> str:
    """Good-enough HTML to Markdown so the LLM sees structure, not tag soup."""
    s = re.sub(r"(?is)<(script|style|noscript|svg|head|nav|footer)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    for level in range(1, 7):
        s = re.sub(rf"(?is)<h{level}[^>]*>(.*?)</h{level}>",
                   lambda m, l=level: "\n\n" + "#" * l + " " + strip_tags(m.group(1)) + "\n",
                   s)
    s = re.sub(r"(?is)<li[^>]*>(.*?)</li>",
               lambda m: "\n- " + strip_tags(m.group(1)), s)
    s = re.sub(r"(?is)<a [^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
               lambda m: f"[{strip_tags(m.group(2))}]({m.group(1)})", s)
    s = re.sub(r"(?is)<(strong|b)>(.*?)</\1>", lambda m: f"**{strip_tags(m.group(2))}**", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|section|article|tr)>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", s).strip()


def page_title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return html_mod.unescape(strip_tags(m.group(1))).strip()[:200] if m else ""


def meta_description(html: str) -> str:
    m = re.search(r"(?is)<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](.*?)[\"']", html)
    if not m:
        m = re.search(r"(?is)<meta[^>]+property=[\"']og:description[\"'][^>]+content=[\"'](.*?)[\"']", html)
    return html_mod.unescape(m.group(1)).strip()[:400] if m else ""


def detect_tech(html: str, headers: dict) -> list[str]:
    """Light digital-footprint read, used by the sales agent to size a prospect."""
    found = set()
    checks = {
        "WordPress": r"wp-content|wp-includes|generator\"\s*content=\"WordPress",
        "Shopify": r"cdn\.shopify\.com|Shopify\.theme",
        "Wix": r"wix\.com|wixstatic",
        "Squarespace": r"squarespace",
        "Webflow": r"webflow",
        "React": r"__NEXT_DATA__|react(?:-dom)?(?:\.production)?\.min\.js|data-reactroot",
        "Next.js": r"__NEXT_DATA__|/_next/static",
        "Vue": r"vue(?:\.runtime)?(?:\.min)?\.js|data-v-[0-9a-f]{8}",
        "Angular": r"ng-version=",
        "jQuery": r"jquery[.-]",
        "Bootstrap": r"bootstrap(?:\.min)?\.css",
        "Tailwind": r"tailwind",
        "Google Analytics": r"gtag\(|google-analytics\.com|googletagmanager",
        "Meta Pixel": r"connect\.facebook\.net/.*fbevents",
        "HubSpot": r"js\.hs-scripts\.com",
        "Stripe": r"js\.stripe\.com",
        "Razorpay": r"checkout\.razorpay\.com",
        "Cloudflare": r"cloudflare",
    }
    for name, pattern in checks.items():
        if re.search(pattern, html, re.I):
            found.add(name)
    server = (headers or {}).get("server", "")
    if server:
        found.add(f"server:{server.split('/')[0]}")
    return sorted(found)


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------
def normalise_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return "+91" + digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    if len(digits) == 13 and digits.startswith("0091"):
        return "+" + digits[2:]
    if 8 <= len(digits) <= 15:
        return "+" + digits
    return ""


def extract_emails(text: str, html: str = "") -> list[str]:
    found: list[str] = []
    for m in re.finditer(r"mailto:([^\"'?>\s]+)", html or "", re.I):
        found.append(urllib.parse.unquote(m.group(1)))
    found += EMAIL_RE.findall(text)
    for rx in OBFUSCATED_RES:
        for local, dom, tld in rx.findall(text):
            dom = re.sub(r"\s*(?:\(|\[|\{)?\s*(?:dot)\s*(?:\)|\]|\})?\s*",
                         ".", dom, flags=re.I).strip(".")
            candidate = f"{local}@{dom}.{tld}".replace("..", ".")
            if EMAIL_RE.match(candidate):
                found.append(candidate)
    out, seen = [], set()
    for e in found:
        # Addresses lifted out of inline JavaScript arrive with escape
        # characters and quotes still attached; a trailing backslash turned
        # hi@pulpkey.com into a second, broken contact.
        e = e.strip().strip("\\\"'<>()[]{}").strip(".,;:").lower()
        if not EMAIL_RE.match(e):
            continue
        local, _, domain = e.partition("@")
        if domain in JUNK_EMAIL_DOMAINS or local in JUNK_LOCALPARTS:
            continue
        if re.search(r"\.(png|jpe?g|gif|webp|svg|css|js|woff2?)$", domain):
            continue
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def extract_phones(text: str) -> list[str]:
    out, seen = [], set()
    for a, b in IN_PHONE_RE.findall(text):
        p = normalise_phone(a + b)
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    for cc, rest in INTL_PHONE_RE.findall(text):
        p = normalise_phone(cc + rest)
        if p and p not in seen and len(p) >= 11:
            seen.add(p)
            out.append(p)
    return out


def extract_whatsapp(html: str) -> list[str]:
    """Pull WhatsApp click-to-chat links and turn them into phone numbers."""
    out, seen = [], set()
    for link in WHATSAPP_RE.findall(html or ""):
        m = re.search(r"(?:wa\.me/|phone=)\+?(\d{8,15})", link)
        if not m:
            continue
        num = normalise_phone(m.group(1))
        if num and num not in seen:
            seen.add(num)
            out.append(num)
    return out


def extract_jsonld_contacts(html: str) -> tuple[list[str], list[str]]:
    """Read email and telephone out of schema.org blocks."""
    emails, phones = [], []
    for raw in JSONLD_EMAIL_RE.findall(html or ""):
        e = raw.strip().lower()
        if EMAIL_RE.match(e):
            emails.append(e)
    for raw in JSONLD_PHONE_RE.findall(html or ""):
        ph = normalise_phone(raw)
        if ph:
            phones.append(ph)
    return emails, phones


def has_mx(domain: str, timeout: float = 6.0) -> bool:
    """Does this domain accept mail at all?

    Asked over DNS-over-HTTPS because the standard library has no MX resolver
    and the point of this project is to stay dependency-free. A domain with no
    MX record cannot receive the email, so there is no sense drafting one.
    """
    domain = (domain or "").strip().lower().removeprefix("www.")
    if not domain or "." not in domain:
        return False
    try:
        resp = http.get("https://dns.google/resolve",
                        params={"name": domain, "type": "MX"},
                        timeout=timeout, retries=1)
        answers = (resp.json() or {}).get("Answer") or []
        return any(a.get("type") == 15 for a in answers)
    except Exception as exc:  # noqa: BLE001
        log.debug(f"MX lookup failed for {domain}: {exc}")
        return False


# Addresses that are near-universal at companies of this size. Used only when
# the site gave up nothing, always marked as a guess, and only after the domain
# is confirmed to accept mail at all.
# Scored below every route the brand published itself - including a bare phone
# number. A guess can bounce; a number on their contact page cannot.
GUESS_LOCALPARTS = [
    ("partnerships", 0.20), ("marketing", 0.19), ("collab", 0.18),
    ("hello", 0.17), ("contact", 0.16), ("info", 0.15),
]


def guessed_contacts(domain: str, limit: int = 3) -> list["Contact"]:
    domain = (domain or "").lower().removeprefix("www.")
    if not domain or not has_mx(domain):
        return []
    out = []
    for local, conf in GUESS_LOCALPARTS[:limit]:
        out.append(Contact(
            email=f"{local}@{domain}", confidence=conf, channel="email",
            guessed=True,
            evidence=(f"not published on the site - standard address pattern, "
                      f"{domain} does accept mail")))
    return out


def extract_socials(html: str) -> dict:
    out = {}
    for name, rx in SOCIAL_RE.items():
        m = rx.search(html or "")
        if m:
            out[name] = m.group(0)
    return out


def score_email(addr: str, domain_hint: str = "") -> float:
    local = addr.split("@", 1)[0].lower()
    dom = addr.split("@", 1)[1].lower()
    score = 4.0
    for hint, weight in ROLE_HINTS:
        if hint.replace(" ", "") in local.replace(".", "").replace("-", ""):
            score = max(score, 4.0 + weight)
    if domain_hint and dom.endswith(domain_hint.lower().lstrip("www.")):
        score += 4
    else:
        score -= 3          # a gmail address on a corporate site is weaker
    if re.fullmatch(r"[a-z]{2,}[._-][a-z]{2,}", local):
        score += 5          # firstname.lastname@ is a named human, not a queue
    if local in ("info", "support", "admin"):
        score -= 1
    probe = addr.lower()
    if any(w in probe for w in WRONG_DEPARTMENT):
        score -= 9
    return max(0.0, min(20.0, score)) / 20.0


# --------------------------------------------------------------------------
# crawler
# --------------------------------------------------------------------------
class Crawler:
    def __init__(self, limiter: HostLimiter | None = None, llm=None,
                 max_pages: int | None = None, timeout: float | None = None):
        self.limiter = limiter or HostLimiter(
            min_interval=config.get_float("CRAWL_MIN_INTERVAL", 1.5),
            respect_robots=config.get_bool("RESPECT_ROBOTS", True),
            user_agent=config.get("USER_AGENT", http.DEFAULT_UA))
        self.llm = llm
        self.max_pages = max_pages or config.get_int("CRAWL_MAX_PAGES", 6)
        self.timeout = timeout or config.get_float("CRAWL_TIMEOUT", 20)
        self.browser_ua = config.get_bool("CRAWL_BROWSER_UA", True)

    def fetch(self, url: str) -> PageResult:
        if not self.limiter.allowed(url):
            log.info("robots.txt disallows this path, skipping", url=url)
            return PageResult(url=url, error="disallowed by robots.txt")
        headers = dict(http.BROWSER_HEADERS) if self.browser_ua else None
        try:
            resp = http.get(url, timeout=self.timeout, retries=1,
                            headers=headers, limiter=self.limiter)
        except http.HttpError as exc:
            return PageResult(url=url, status=getattr(exc, "status", 0),
                              error=str(exc)[:200])
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return PageResult(url=url, status=resp.status,
                              error=f"non-HTML content ({ctype})")
        html = resp.text
        text = strip_tags(html)
        ld_emails, ld_phones = extract_jsonld_contacts(html)
        wa = extract_whatsapp(html)
        emails = extract_emails(text, html)
        for e in ld_emails:
            if e not in emails:
                emails.append(e)
        phones = extract_phones(text)
        for ph in ld_phones + wa:
            if ph not in phones:
                phones.append(ph)
        page = PageResult(
            url=resp.url, status=resp.status, title=page_title(html),
            text=text, markdown=to_markdown(html)[:30000],
            emails=emails, phones=phones,
            socials=extract_socials(html), whatsapp=wa,
            links=self._links(html, resp.url))
        page._html = html                              # noqa: SLF001 - internal
        page._headers = resp.headers                   # noqa: SLF001
        return page

    @staticmethod
    def _links(html: str, base: str) -> list[str]:
        out, seen = [], set()
        for m in re.finditer(r"(?is)<a [^>]*href=[\"']([^\"'#]+)[\"']", html):
            href = urllib.parse.urljoin(base, m.group(1).strip())
            if href.startswith(("http://", "https://")) and href not in seen:
                seen.add(href)
                out.append(href)
        return out[:400]

    def profile_site(self, url: str, hints: list | None = None) -> SiteProfile:
        """Crawl the handful of pages where contact details actually live."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        domain = parts.netloc.lower().removeprefix("www.")
        profile = SiteProfile(domain=domain)

        home = self.fetch(origin + "/")
        pages = [home]
        candidates: list[str] = []
        if home.ok:
            profile.title = home.title
            profile.description = meta_description(getattr(home, "_html", ""))
            profile.tech = detect_tech(getattr(home, "_html", ""),
                                       getattr(home, "_headers", {}))
            wanted = re.compile(
                r"/(contact|about|team|leader|partner|sponsor|advertis|press|"
                r"media|work-with|collab|influenc|creator|affiliat|connect|"
                r"get-in-touch|reach-us|enquir|inquir|support|help)", re.I)
            for link in home.links:
                lp = urllib.parse.urlsplit(link)
                if lp.netloc.lower().removeprefix("www.") != domain:
                    continue
                if wanted.search(lp.path or ""):
                    candidates.append(link)
                if re.search(r"/(contact|enquir|inquir)", lp.path or "", re.I) \
                        and not profile.contact_form_url:
                    profile.contact_form_url = link
        # Paths specific to this target, from the sponsor list, are tried first.
        for path in (hints or []):
            if path:
                candidates.insert(0, origin + ("" if path.startswith("/") else "/") + path)
        for path in CONTACT_PATHS[1:]:
            candidates.append(origin + path)

        seen = {home.url.rstrip("/")}
        # max_pages counts pages KEPT, but a site where nothing exists at any
        # of the guessed paths would otherwise be tried against the whole list,
        # and a slow host turns that into several minutes per domain. So the
        # number of attempts is capped too, and a run of failures gives up.
        attempts = 0
        misses = 0
        attempt_cap = max(self.max_pages * 3, 8)
        for link in candidates:
            if len(pages) >= self.max_pages or attempts >= attempt_cap:
                break
            if misses >= 5:
                log.info("giving up on this host, nothing at the usual paths",
                         domain=domain)
                break
            key = link.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            attempts += 1
            p = self.fetch(link)
            if not p.ok:
                misses += 1
            # Keep any page that carries a contact, however short. Contact pages
            # are routinely two lines long, and those two lines are the point.
            if p.ok and (len(p.text) > 40 or p.emails or p.phones):
                pages.append(p)

        profile.pages = pages
        for p in pages:
            profile.socials.update(p.socials)
            if p.whatsapp and not profile.whatsapp:
                profile.whatsapp = p.whatsapp[0]
        profile.blocked = not any(p.ok for p in pages)
        profile.contacts = self._build_contacts(profile)
        log.info("site profiled", domain=domain,
                 pages=sum(1 for p in pages if p.ok),
                 contacts=len(profile.contacts),
                 blocked=profile.blocked)
        return profile

    def _build_contacts(self, profile: SiteProfile) -> list[Contact]:
        """Work down a ladder until something usable is found.

        A brand that cannot be emailed is not a dead lead - it is a lead that
        has to be reached a different way. Each rung is a real route to a human,
        and every contact carries the evidence for how it was found so nothing
        has to be taken on trust.

          1. an address published on their own site
          2. a WhatsApp number they published themselves
          3. any other phone number on the site
          4. their contact form, with the message ready to paste
          5. a social profile to DM
          6. a standard address pattern, checked for a live mail server,
             clearly labelled as a guess
        """
        contacts: dict[str, Contact] = {}

        # 1. published email addresses
        for p in profile.pages:
            if not p.ok:
                continue
            for e in p.emails:
                conf = score_email(e, profile.domain)
                if e not in contacts or contacts[e].confidence < conf:
                    contacts[e] = Contact(
                        email=e, source_url=p.url, confidence=conf,
                        channel="email",
                        evidence=f"published on {p.url}")

        # 2 and 3. WhatsApp first, then any other number.
        for p in profile.pages:
            if not p.ok:
                continue
            for ph in p.phones:
                if ph in contacts:
                    continue
                is_wa = ph in (p.whatsapp or [])
                contacts[ph] = Contact(
                    phone=ph, source_url=p.url,
                    confidence=0.42 if is_wa else 0.30,
                    channel="whatsapp" if (is_wa or ph.startswith("+91")) else "phone",
                    evidence=("WhatsApp link on " if is_wa else "phone number on ") + p.url)

        # 4. their own contact form
        if profile.contact_form_url and profile.contact_form_url not in contacts:
            contacts[profile.contact_form_url] = Contact(
                channel="form", url=profile.contact_form_url,
                source_url=profile.contact_form_url, confidence=0.22,
                evidence="no address published - use their enquiry form")

        # 5. a social profile worth a DM
        for net in ("instagram", "linkedin", "twitter"):
            link = profile.socials.get(net)
            if link and link not in contacts:
                contacts[link] = Contact(
                    channel="social", url=link, source_url=link,
                    confidence=0.14, role=net,
                    evidence=f"{net} profile found on their site")
                break

        # 6. last resort: a pattern address on a domain that accepts mail
        has_real_email = any(c.email and not c.guessed for c in contacts.values())
        if not has_real_email and config.get_bool("CONTACT_GUESS_ENABLED", True):
            for guess in guessed_contacts(profile.domain):
                if guess.email not in contacts:
                    guess.source_url = f"https://{profile.domain}/"
                    contacts[guess.email] = guess

        return sorted(contacts.values(), key=lambda c: -c.confidence)

    # -- semantic pass -------------------------------------------------------
    SEMANTIC_SCHEMA = {
        "type": "object",
        "required": ["people"],
        "properties": {
            "company_summary": {"type": "string", "max_length": 600, "default": ""},
            "people": {
                "type": "array", "max_items": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "default": ""},
                        "role": {"type": "string", "default": ""},
                        "email": {"type": "string", "default": ""},
                        "relevance": {"type": "number", "minimum": 0,
                                      "maximum": 1, "default": 0.5},
                    },
                },
                "default": [],
            },
        },
    }

    def semantic_contacts(self, profile: SiteProfile, looking_for: str) -> dict:
        """LLM pass to name the right human, when regex alone is not enough."""
        if self.llm is None:
            return {"company_summary": profile.description, "people": []}
        prompt = (
            f"Below is the public website content for {profile.domain}.\n"
            f"Identify people who would own: {looking_for}.\n"
            f"Only report names, roles and email addresses that appear verbatim "
            f"in the text. Never guess or construct an email address. If nobody "
            f"relevant is listed, return an empty people array.\n\n"
            f"---\n{profile.combined_text[:12000]}\n---")
        try:
            out = self.llm.structured(
                prompt, self.SEMANTIC_SCHEMA, task="semantic_contacts",
                context={"profile": profile, "looking_for": looking_for},
                system="You extract contact facts from web pages. You never invent them.",
                temperature=0.0)
        except Exception as exc:  # noqa: BLE001
            log.warn(f"semantic extraction failed: {exc}")
            return {"company_summary": profile.description, "people": []}
        # Guard: drop any email the model produced that is not on the page.
        page_emails = {e for p in profile.pages for e in p.emails}
        for person in out.get("people", []):
            if person.get("email") and person["email"].lower() not in page_emails:
                log.warn("dropping hallucinated email", email=person["email"])
                person["email"] = ""
        return out
