"""The sponsorship agent's own eyes on the internet.

This is not a separate agent. It is the first half of the sponsorship agent's
run: before working the list, it can go and see what is new, and add to the
list. The same brain that decides which brand to email decides which brand is
worth adding, because they are the same judgement made at two moments.

A run has two phases:

    refresh   sweep the web, verify what is found, ask you what to add
    work      go down the list, research, pitch, ask you to send

The refresh phase is skipped unless it is due (weekly by default) or you ask
for it, so the ordinary run is just the outreach it has always been.
"""
from __future__ import annotations

import json
import re
import time
import uuid

from agents.sponsorship import india as india_mod
from agents.sponsorship import sources as src
from core import config
from core.crawler import Crawler
from core.hitl import require_approval
from core.log import get_logger
from core.yamlite import load_yaml

log = get_logger("sponsorship.discover")

# Categories that must never reach the list, whatever a source says. India
# banned real-money gaming in 2025, and a betting brand that slips in through a
# scraped headline is the creator's legal problem, not the tool's.
BANNED = [
    "betting", "satta", "casino", "bookmaker", "teen patti", "rummy cash",
    "real money game", "real-money gaming", "fantasy cricket", "wager",
    "jackpot", "lottery", "gambling", "poker", "1xbet", "parimatch",
    "stake.com", "dafabet", "melbet", "crickex", "betway", "4rabet",
]


# A brand that only ever offers a cut of a sale is offering a sales job, not a
# promotion. Vineet was explicit twice: he is not a salesman. Relabelling such a
# target "cash" was not enough - what put it on the list in the first place was
# the affiliate programme, so it kept being pitched. This refuses it by the
# evidence, wherever that evidence appears: a list entry, or a page the sweep
# just read.
SALESMAN = re.compile(
    r"affiliate programme|affiliate program|commission|per[- ]sale|per sale|"
    r"discount code|coupon code|promo code|referral (?:bonus|programme|program)|"
    r"cashback|per account opened|per lead|payout per|earn per|revenue share|"
    r"\bcps\b|become an affiliate|join our affiliate", re.I)


def salesman_reason(*parts: str) -> str:
    """Empty string when nothing here is a commission deal."""
    hit = SALESMAN.search(" ".join(str(p or "") for p in parts))
    return (f"pays a cut per sale ({hit.group(0).lower()}) - that is a sales "
            f"job, not a paid promotion") if hit else ""


def banned_reason(name: str, text: str = "") -> str:
    blob = f"{name} {text}".lower()
    for term in BANNED:
        if term in blob:
            return f"mentions {term!r} - real-money gaming and betting are excluded"
    return ""


def sponsor_file():
    import pathlib
    return pathlib.Path(config.get(
        "SPONSOR_FILE", str(config.profiles_dir() / "sponsors.yaml")))


def listed_domains() -> set[str]:
    out: set[str] = set()
    try:
        data = load_yaml(sponsor_file().read_text(encoding="utf-8")) or {}
        for t in data.get("targets", []):
            dom = str(t.get("url", "")).split("//")[-1].split("/")[0].lower()
            if dom:
                out.add(dom.removeprefix("www."))
    except Exception as exc:  # noqa: BLE001
        log.warn(f"could not read the sponsor list: {exc}")
    return out


class DiscoveryMixin:
    """Nodes bolted onto the front of the sponsorship graph.

    Expects the host to provide `self.store`, `self.brain` and `self.cfg`.
    """

    # ------------------------------------------------------------ helpers
    @property
    def sources(self) -> dict:
        return getattr(self, "_sources", None) or src.SOURCES

    @sources.setter
    def sources(self, value: dict) -> None:
        self._sources = value

    def _discovery_crawler(self) -> Crawler:
        # A quick look, not a full profile: enough to tell whether the site is
        # real, Indian, and contactable. A deep crawl of forty candidates takes
        # an hour and says nothing more.
        if getattr(self, "_disco_crawler", None) is None:
            self._disco_crawler = Crawler(
                max_pages=config.get_int("PROSPECT_CRAWL_PAGES", 3),
                timeout=config.get_float("PROSPECT_CRAWL_TIMEOUT", 10))
        return self._disco_crawler

    def _known(self) -> set[str]:
        out = listed_domains()
        for table in ("leads", "prospects"):
            for r in self.store.query(f"SELECT domain FROM {table}"):
                if r.get("domain"):
                    out.add(str(r["domain"]).lower().removeprefix("www."))
        return out

    def _say(self, text: str) -> None:
        """A line of progress, so a long sweep is not a silent one."""
        try:
            from core.notify import get_notifier
            get_notifier(self.store).send("Sponsorship", text,
                                          tags=("sponsorship",))
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not post progress: {exc}")

    def discovery_due(self) -> bool:
        if not config.get_bool("DISCOVER_ENABLED", True):
            return False
        every = config.get_float("DISCOVER_INTERVAL_SECONDS", 7 * 86400)
        last = self.store.kv_get("sponsorship", "last_discovery") or 0
        try:
            last = float(last)
        except (TypeError, ValueError):
            last = 0.0
        return (time.time() - last) >= every

    # -------------------------------------------------------------- nodes
    def n_refresh(self, s: dict) -> dict:
        """Decide whether to go looking, then look."""
        want = s.get("discover")
        if want is None:
            want = self.discovery_due()
        if not want:
            return {"log": "skipping the web sweep - not due yet",
                    "new_finds": []}

        # An automatic sweep uses only the fast sources. YouTube mining and open
        # web search are worth running, but they are slow and rate-limited, so
        # they only run when you name them - otherwise /run sponsorship sits
        # silent for ten minutes before showing you anything.
        wanted = s.get("only_sources")
        if not wanted:
            default = config.get_list("DISCOVER_SOURCES",
                                      ["cuelinks", "trade_press", "admitad"])
            wanted = [n for n in default if n in self.sources] or list(self.sources)
        weights = self.brain.source_weights(wanted)
        self._say(f"Looking for new brands on {len(wanted)} sources. "
                  f"This takes a couple of minutes.")
        budget = max(config.get_int("PROSPECT_MAX_CHECK", 40), 10)
        found, per_source = [], {}
        for name in sorted(wanted, key=lambda n: -weights.get(n, 0)):
            fn = self.sources.get(name)
            if fn is None:
                continue
            share = max(4, int(budget * weights.get(name, 0.2)))
            try:
                got = _call_source(name, fn, share)
            except Exception as exc:  # noqa: BLE001
                log.warn(f"source {name} failed: {exc}")
                continue
            per_source[name] = len(got)
            found.extend(got)

        self.store.kv_set("sponsorship", "last_discovery", time.time())
        log.info("web sweep", sources=len(per_source), candidates=len(found),
                 per_source=per_source)
        self._say(f"Found {len(found)} possible brands. Checking which are new "
                  f"and Indian.")
        return {"candidates": [c.__dict__ | {"domain": c.domain} for c in found],
                "stats": {"swept": len(found)},
                "log": f"swept {len(per_source)} sources, {len(found)} candidates"}

    def n_screen(self, s: dict) -> dict:
        """Drop the banned, the duplicated, and the ones with no website."""
        if not s.get("candidates"):
            return {"new_finds": []}
        known = self._known()
        kept, dropped, seen = [], [], set()
        for c in s["candidates"]:
            name = c.get("name", "")
            why = banned_reason(name, c.get("note", ""))
            if why:
                dropped.append({"name": name, "reason": why})
                continue
            dom = (c.get("domain") or "").lower().removeprefix("www.")
            if not dom and name:
                url = src.resolve_domain(name)
                if url:
                    c["url"] = url
                    dom = url.split("//")[-1].lower().removeprefix("www.")
            if not dom:
                dropped.append({"name": name, "reason": "no website found"})
                continue
            if dom in known or dom in seen:
                dropped.append({"name": name, "reason": "already on the list"})
                continue
            seen.add(dom)
            c["domain"] = dom
            kept.append(c)
        kept = kept[: config.get_int("PROSPECT_MAX_CHECK", 40)]
        log.info("screened", kept=len(kept), dropped=len(dropped))
        return {"candidates": kept, "skipped": dropped,
                "stats": {"new_domains": len(kept)}}

    def n_check(self, s: dict) -> dict:
        """Read each site: real, Indian, contactable? Then rank by the brain."""
        crawler = self._discovery_crawler()
        india_min = config.get_float("PROSPECT_INDIA_MIN", 0.30)
        kept, dropped = [], []
        for c in s.get("candidates") or []:
            try:
                profile = crawler.profile_site(c["url"])
            except Exception as exc:  # noqa: BLE001
                dropped.append({"name": c.get("name", ""),
                                "reason": f"could not read the site: {exc}"[:90]})
                continue
            text = profile.combined_text
            html = "".join(getattr(p, "_html", "") for p in profile.pages[:2])
            why = banned_reason(c.get("name", ""), text[:20000])
            if why:
                dropped.append({"name": c.get("name", ""), "reason": why})
                continue
            # A site that refused to load has no text to judge, and reporting
            # that as "does not look Indian" is misleading - it is a site we
            # could not see, not one we looked at and rejected.
            if profile.blocked or len(text.strip()) < 60:
                dropped.append({"name": c.get("name", ""),
                                "reason": "site refused to load - nothing to read"})
                continue
            score, hits = india_mod.india_score(text, html, c["domain"])
            if score < india_min:
                dropped.append({"name": c.get("name", ""),
                                "reason": f"does not look Indian ({score:.2f})"})
                continue
            emails = [x for x in profile.contacts if x.email and not x.guessed]
            rec = {**c,
                   "title": profile.title[:140],
                   "description": (profile.description or "")[:300],
                   "india_score": round(score, 3), "india_hits": hits,
                   "has_email": bool(emails),
                   "contact": emails[0].email if emails else "",
                   "segment": c.get("segment") or _guess_segment(text, c),
                   }
            fit, working = self.brain.score({
                "domain": rec["domain"], "source": rec.get("source", ""),
                "segment": rec.get("segment", ""),
                "deal_type": rec.get("deal_type", ""),
                "india_score": rec["india_score"],
                "data": {"has_email": rec["has_email"],
                         "payout": rec.get("payout")}})
            if rec["has_email"]:
                fit += 0.05
            if rec.get("payout"):
                fit += 0.05
            rec["score"] = round(min(1.0, fit), 3)
            rec["why"] = working
            kept.append(rec)

        kept.sort(key=lambda r: -r["score"])
        kept = kept[: config.get_int("PROSPECT_MAX_PROPOSE", 15)]
        self._save_prospects(kept)
        log.info("checked", ok=len(kept), dropped=len(dropped))
        if kept:
            self._say(f"{len(kept)} worth adding. Showing them one at a time.")
        else:
            self._say("Nothing new worth adding this time. Moving on to the "
                      "outreach.")
        return {"new_finds": kept, "skipped": dropped,
                "stats": {"verified": len(kept)}}

    def n_pick_find(self, s: dict) -> dict:
        queue = list(s.get("new_finds") or [])
        if not queue:
            return {"find": None}
        return {"find": queue.pop(0), "new_finds": queue}

    def n_add(self, s: dict) -> dict:
        """Ask before touching the list. Either answer teaches the brain."""
        r = s["find"]
        decision = require_approval(
            agent=self.cfg.agent, thread_id=s["_thread_id"], kind="add_target",
            title=f"Add {r.get('name') or r['domain']} to your sponsor list?",
            payload={
                "company": r.get("name", ""), "domain": r["domain"],
                "url": r.get("url", ""), "to": r.get("contact", ""),
                "source": r.get("source", ""),
                "source_url": r.get("source_url", ""),
                "deal_type": r.get("deal_type", ""),
                "segment": r.get("segment", ""),
                "india_score": r.get("india_score", 0),
                "india_hits": r.get("india_hits", []),
                "score": r.get("score", 0), "payout": r.get("payout", ""),
                "note": r.get("note", ""),
                "body": (r.get("description") or r.get("title") or "")[:600],
                "why": [f"{w['feature']}  {w['shift']:+.2f}"
                        for w in (r.get("why") or [])[:5]],
            },
            store=self.store)

        outcome = "added" if decision.approved else "not_added"
        self.brain.record({
            "domain": r["domain"], "source": r.get("source", ""),
            "segment": r.get("segment", ""), "deal_type": r.get("deal_type", ""),
            "india_score": r.get("india_score", 0),
            "data": {"has_email": r.get("has_email"),
                     "payout": r.get("payout")}},
            outcome, note=decision.note or "")
        self.store.run("UPDATE prospects SET status=?, updated_at=? WHERE domain=?",
                       (outcome, time.time(), r["domain"]))

        if not decision.approved:
            return {"skipped": {"domain": r["domain"],
                                "company": r.get("name", ""),
                                "reason": "you said no to adding it"},
                    "log": f"did not add {r['domain']}"}
        written = self._append_to_list(r)
        return {"added": written, "stats": {"added": 1},
                "log": f"added {r['domain']} to the sponsor list"}

    def r_more_finds(self, s: dict) -> str:
        return "next" if s.get("new_finds") else "outreach"

    # ------------------------------------------------------------ storage
    def _save_prospects(self, finds: list) -> None:
        now = time.time()
        for r in finds:
            self.store.run(
                "INSERT OR IGNORE INTO prospects (id, name, domain, url, source,"
                " source_url, segment, deal_type, india_score, score, status,"
                " why_json, data_json, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, r.get("name", ""), r["domain"],
                 r.get("url", ""), r.get("source", ""), r.get("source_url", ""),
                 r.get("segment", ""), r.get("deal_type", ""),
                 float(r.get("india_score") or 0), float(r.get("score") or 0),
                 "proposed", json.dumps(r.get("why", []))[:4000],
                 json.dumps({k: r.get(k) for k in
                             ("title", "description", "india_hits", "has_email",
                              "contact", "payout", "note")})[:4000],
                 now, now))

    def _append_to_list(self, r: dict) -> dict:
        path = sponsor_file()
        fit = (r.get("note") or r.get("description")
               or "Found on the web by the agent").replace(":", " -")[:160]
        entry = (
            f"\n  - name: {r.get('name') or r['domain']}\n"
            f"    url: {r.get('url')}\n"
            f"    category: sponsor\n"
            f"    segment: {r.get('segment') or 'discovered'}\n"
            f"    tier: 1\n"
            f"    deal_type: {r.get('deal_type') or 'cash'}\n"
            f"    fit: {fit}\n"
            f"    tags: [discovered, {r.get('source', 'web')}, india]\n"
            f"    hints: []\n")
        header = ("\n  # " + "=" * 68 +
                  "\n  # FOUND ON THE WEB - approved by you\n  # " +
                  "=" * 68 + "\n")
        try:
            text = path.read_text(encoding="utf-8")
            if "FOUND ON THE WEB" not in text:
                text += header
            path.write_text(text + entry, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.warn(f"could not write to the sponsor list: {exc}")
            return {"name": r.get("name", ""), "domain": r["domain"],
                    "written": False, "error": str(exc)[:120]}
        return {"name": r.get("name", ""), "domain": r["domain"],
                "url": r.get("url", ""),
                "deal_type": r.get("deal_type") or "cash", "written": True}


def _call_source(name: str, fn, share: int):
    if name == "cuelinks":
        return fn(pages=max(1, share // 12), resolve=share)
    if name == "admitad":
        return fn(limit=share)
    if name == "youtube":
        return fn(channels=max(1, share // 10), videos_per_channel=3)
    if name == "trade_press":
        return fn(per_feed=max(4, share // 6))
    return fn()


# Words that place a brand in one of the segments the pitch already knows how
# to argue for. Getting this right means a new find gets the same tailored
# angle as a hand-curated target, instead of the generic one.
SEGMENT_WORDS = {
    "nutrition": ["protein", "whey", "supplement", "nutrition", "creatine",
                  "mass gainer", "bcaa"],
    "grooming": ["beard", "grooming", "shaving", "fragrance", "deodorant",
                 "skincare", "hair care"],
    "consumer_tech": ["earbuds", "headphone", "smartwatch", "power bank",
                      "soundbar", "neckband", "charger"],
    "merch": ["t-shirt", "tshirt", "apparel", "streetwear", "hoodie",
              "oversized", "jersey", "merchandise"],
    "cricket_gear": ["cricket bat", "batting pads", "cricket ball",
                     "wicket", "cricket kit", "willow"],
    "fintech": ["demat", "broking", "mutual fund", "invest", "insurance",
                "upi", "credit card", "savings"],
    "food": ["snack", "peanut butter", "granola", "makhana", "dry fruit",
             "protein bar"],
    "beverage": ["energy drink", "coffee", "cold brew", "hydration", "ors"],
    "creator_tools": ["video editing", "stock footage", "royalty free music",
                      "vpn", "web hosting", "domain name"],
    "edtech": ["course", "bootcamp", "upskill", "placement", "cohort"],
    "ott": ["web series", "streaming", "audiobook", "audio series", "podcast"],
    "gaming": ["esports", "mobile game", "battle royale", "gaming tournament"],
}


def _guess_segment(text: str, candidate: dict) -> str:
    low = f"{text[:20000]} {candidate.get('note', '')}".lower()
    best, best_hits = "", 0
    for segment, words in SEGMENT_WORDS.items():
        hits = sum(1 for w in words if w in low)
        if hits > best_hits:
            best, best_hits = segment, hits
    return best if best_hits >= 2 else "discovered"
