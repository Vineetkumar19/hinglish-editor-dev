"""Where people asking for development work actually say so.

Same shape as the video client's sweep, pointed at a different market and with
one addition that matters more than the rest: a set of queries aimed squarely
at **broken** payment integrations.

That is the highest-intent work there is. A marketing site is a project someone
gets round to; a checkout that is double-charging customers is costing them
money every hour it stays broken, and they answer emails about it the same day.
It is also the thing he is unusually placed to fix - Razorpay and UPI are
India-specific, and a foreign team with an Indian checkout has nobody in the
building who has wired one.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field

from core import config, http
from core.log import get_logger

log = get_logger("dev.sources")

# Ordered by intent. The payment ones come first because they are the ones
# worth spending the sweep's time on.
QUERIES = [
    "payment gateway integration developer",
    "razorpay integration developer",
    "stripe integration developer",
    "freelance full stack developer contract",
    "react developer freelance contract",
    "node.js backend developer contract",
    "next.js developer freelance",
    "mern stack developer contract",
    "web developer freelance project",
]

# What kind of work it is. First match wins, so the specific patterns lead.
WORK_KINDS = [
    ("payments", r"\b(razorpay|payu|cashfree|instamojo|phonepe|paytm|stripe|"
                 r"paypal|adyen|braintree|upi\b|payment gateway|checkout flow|"
                 r"subscription billing|recurring billing|payment integration|"
                 r"split payment|payout|settlement|webhook.{0,20}payment)\w*"),
    # "errors" and "issue" appear in half of all job descriptions. A rescue is
    # a request to FIX something, so the verb has to be there.
    ("rescue", r"\b(fix (the|our|my|a|this)|not working|is broken|keeps failing|"
               r"urgent(ly)? (fix|need)|troubleshoot|help (me |us )?(fix|debug)|"
               r"stopped working|someone to fix|need it fixed|"
               r"broken (checkout|integration|payment|site|app))\w*"),
    ("mobile", r"\b(react native|flutter|android app|ios app|mobile app)\w*"),
    ("backend", r"\b(backend|api|node\.?js|express|django|fastapi|spring boot|"
                r"microservice|database design)\w*"),
    ("frontend", r"\b(react|next\.?js|frontend|front[- ]end|vue|angular|"
                 r"tailwind|ui development)\w*"),
    ("fullstack", r"\b(full[- ]?stack|mern|mean|web app|web application|"
                  r"saas build)\w*"),
    ("design", r"\b(ui/?ux|figma|website design|redesign|landing page design)\w*"),
    ("site", r"\b(website|wordpress|webflow|shopify|landing page|marketing site)\w*"),
]

# Not development work, whatever the title says.
NOT_DEV = re.compile(
    r"\b(data entry|virtual assistant|seo writer|content writer|copywriter|"
    r"social media manager|telecaller|bpo|sales executive|recruiter|"
    r"business development|customer support|manual tester only)\b", re.I)

# "engineer" on its own let a Toptal listing for a MECHANICAL ENGINEER through.
# The word belongs to a dozen professions; only the software ones are ours.
NOT_DEV_ENGINEER = re.compile(
    r"\b(mechanical|civil|electrical|chemical|structural|industrial|"
    r"manufacturing|process|sales|solutions? sales|estimator|hvac|"
    r"petroleum|mining|aerospace|automotive|quality) engineer\b", re.I)

DEV = re.compile(
    r"\b(developer|engineer|programmer|full[- ]?stack|backend|front[- ]?end|"
    r"react|node|python|java|django|laravel|php|api|web app|mobile app|"
    r"razorpay|stripe|payment gateway|upi|integration|wordpress|shopify|"
    r"webflow|next\.?js|flutter|react native)\w*", re.I)

CLIENT_KINDS = [
    ("agency", r"\b(agency|studio|consultancy|software house|we build for "
               r"clients|our clients)\w*"),
    ("startup", r"\b(startup|seed|pre[- ]seed|founder|yc\b|early stage|mvp)\w*"),
    ("saas", r"\b(saas|b2b platform|our platform|subscription business)\w*"),
    ("ecommerce", r"\b(ecommerce|e-commerce|d2c|online store|shopify|"
                  r"marketplace|checkout)\w*"),
    ("smb", r"\b(small business|local business|clinic|restaurant|school|"
            r"shop|store owner)\w*"),
]


@dataclass
class Gig:
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

    def _blob(self) -> str:
        return f"{self.title} {self.company} {self.description[:3000]}"

    def work_kind(self) -> str:
        blob = self._blob()
        # A broken payment integration is payments work AND rescue work. The
        # rescue framing is what gets the reply, so it wins.
        pay = re.search(WORK_KINDS[0][1], blob, re.I)
        broke = re.search(WORK_KINDS[1][1], blob, re.I)
        if pay and broke:
            return "payment_rescue"
        for name, pattern in WORK_KINDS:
            if re.search(pattern, blob, re.I):
                return name
        return "unknown"

    def client_kind(self) -> str:
        blob = self._blob()
        for name, pattern in CLIENT_KINDS:
            if re.search(pattern, blob, re.I):
                return name
        return "unknown"

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "raw"}


# The distinction this agent lives or dies on: a CLIENT who wants something
# built, versus an EMPLOYER hiring staff. A live sweep returned nine postings
# from Stripe - jobs AT Stripe - which this agent would have answered by
# offering to integrate Stripe for them. Employment postings are the job
# hunter's business, not this one's.
HIRING_STAFF = re.compile(
    r"\b(full[- ]time (position|role|employee)|permanent (role|position)|"
    r"benefits package|health insurance|401\(?k\)?|equity|stock options|rsus?|"
    r"paid time off|pto\b|join our team|join us|we are hiring|our mission|"
    r"life at |relocation assistance|visa sponsorship|annual salary|"
    r"per annum|lpa\b|employee resource group|career growth|"
    r"performance review|onboarding buddy)\b", re.I)

CLIENT_WORK = re.compile(
    r"\b(freelance|freelancer|contract(or| basis| role| position|ing)?|"
    r"project[- ]based|per[- ]project|fixed[- ]price|hourly rate|"
    r"short[- ]term|one[- ]off|need (someone|a developer|help) to|"
    r"looking for (someone|a developer|a freelancer) to|"
    r"we need (a|an) .{0,24}(developer|engineer)|build (us|our|a)|"
    r"outsourc|agency work|subcontract|consultant|gig\b|"
    r"scope of work|statement of work|deliverables?)\b", re.I)


def is_dev_work(gig: Gig) -> tuple[bool, str]:
    blob = f"{gig.title} {gig.description[:2500]}"
    if NOT_DEV.search(gig.title):
        return False, "not development work"
    if NOT_DEV_ENGINEER.search(gig.title):
        return False, "a different kind of engineer"
    if not DEV.search(gig.title) and not DEV.search(blob):
        return False, "nothing development-shaped in it"

    client = CLIENT_WORK.search(blob)
    staff = HIRING_STAFF.search(blob)
    if staff and not client:
        return False, f"a job, not a client ({staff.group(0).lower()})"
    if not client:
        # No description yet - the sweep has only the title. Keep it and let
        # the read step decide once the posting has been fetched.
        if len(gig.description.strip()) < 120:
            return True, "no posting text yet - judged on the title alone"
        return False, "reads as employment, not project work"
    return True, "someone looking to have work done"


def from_linkedin(query: str, places: list[str] | None = None) -> list[Gig]:
    from agents.job_hunter.boards_in import LinkedInSource
    places = places or config.get_list(
        "DEV_CLIENT_MARKETS",
        ["India", "United States", "United Kingdom", "Canada", "Worldwide"],
        sep="|")
    out: list[Gig] = []
    for place in places:
        q = urllib.parse.urlencode({"keywords": query, "location": place,
                                    "f_TPR": "r604800", "start": 0})
        resp = http.get(f"https://www.linkedin.com/jobs-guest/jobs/api/"
                        f"seeMoreJobPostings/search?{q}", timeout=25, retries=1)
        if not resp.ok:
            log.warn(f"linkedin {place}: HTTP {resp.status}")
            continue
        for job in LinkedInSource.parse_cards(resp.text):
            out.append(Gig(id=job.id, title=job.title, company=job.company,
                           location=job.location or place, url=job.url,
                           posted_at=job.posted_at, source="linkedin",
                           remote=job.remote))
    return out


def describe(gig: Gig) -> str:
    if gig.source != "linkedin":
        return gig.description
    from agents.job_hunter.boards_in import LinkedInSource
    return LinkedInSource._describe(gig.id)


def from_remoteok() -> list[Gig]:
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
        if not DEV.search(r["position"]):
            continue
        out.append(Gig(id=str(r.get("id") or ""), title=r["position"],
                       company=r.get("company", ""),
                       location=r.get("location") or "Remote",
                       url=r.get("url", ""),
                       description=re.sub(r"<[^>]+>", " ",
                                          r.get("description", ""))[:6000],
                       posted_at=float(r.get("epoch") or 0) or time.time(),
                       source="remoteok", remote=True, raw=r))
    return out


def from_weworkremotely() -> list[Gig]:
    out = []
    for feed in ("remote-programming-jobs", "remote-full-stack-programming-jobs"):
        resp = http.get(f"https://weworkremotely.com/categories/{feed}.rss",
                        timeout=25, retries=1)
        if not resp.ok:
            continue
        for item in re.split(r"<item>", resp.text)[1:]:
            title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
                              item, re.S)
            link = re.search(r"<link>(.*?)</link>", item, re.S)
            if not (title and link):
                continue
            text = title.group(1).strip()
            if not DEV.search(text):
                continue
            company, _, role = text.partition(":")
            out.append(Gig(id=link.group(1).strip()[-40:],
                           title=(role or text).strip(), company=company.strip(),
                           location="Remote", url=link.group(1).strip(),
                           description=re.sub(r"<[^>]+>", " ", item)[:4000],
                           posted_at=time.time(), source="weworkremotely",
                           remote=True))
    return out


SOURCES = {
    "linkedin": lambda: [g for q in QUERIES for g in from_linkedin(q)],
    "remoteok": from_remoteok,
    "weworkremotely": from_weworkremotely,
}


def find_gigs(sources: list[str] | None = None) -> list[Gig]:
    names = sources or config.get_list("DEV_CLIENT_SOURCES",
                                       ["linkedin", "remoteok", "weworkremotely"])
    seen, out = set(), []
    for name in names:
        fn = SOURCES.get(name)
        if fn is None:
            log.warn(f"unknown dev source {name!r}; known: {sorted(SOURCES)}")
            continue
        try:
            gigs = fn()
        except Exception as exc:  # noqa: BLE001
            log.warn(f"dev source {name} failed: {exc}")
            continue
        for g in gigs:
            ok, _ = is_dev_work(g)
            if not ok or g.key() in seen:
                continue
            seen.add(g.key())
            out.append(g)
    # Payment work first: it pays best and it is answered fastest.
    order = {"payment_rescue": 0, "payments": 1, "rescue": 2}
    out.sort(key=lambda g: order.get(g.work_kind(), 5))
    log.info("dev gig sweep complete", sources=names, found=len(out))
    return out
