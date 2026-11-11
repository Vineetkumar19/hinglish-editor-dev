"""Which development clients are actually worth his time.

Fourth use of the same beta-binomial, fourth subclass rather than a copy. The
question here is narrower than it looks: not "is this a good project" but "does
this kind of client, from this source, for this kind of work, ever turn into
money". Two of those three are knowable from the posting before a word is
written, which is what makes the ranking useful on a sweep of three hundred.

Features carry the `fs:` prefix and are counted apart from the other three
agents, which share the table.
"""
from __future__ import annotations

import re
import uuid

from agents.sponsorship.brain import Memory as _Memory, _now
from core.log import get_logger
from core.store import Store

log = get_logger("dev.brain")

PREFIX = "fs:"

OUTCOME_WEIGHT = {
    "replied_no": -2.0,
    "unsubscribed": -3.0,
    "paid": 16.0,
    "deal_won": 10.0,
    "scoped": 3.0,          # they answered the scoping questions - real intent
    "quoted": 2.0,
    "replied": 3.0,
    "pitch_approved": 1.0,
    "sent": 0.5,
    "pitch_rejected": -1.0,
    "no_reply": -1.0,
    "declined_price": -2.0,
    "ghosted_after_quote": -2.5,
    "scope_creep": -3.0,    # it landed and then ate far more than it paid for
    "bounced": -1.5,
}
POSITIVE = {"paid", "deal_won", "scoped", "quoted", "replied",
            "pitch_approved", "sent"}

MARKETS = {
    "india": r"\b(india|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|"
             r"pune|noida|gurugram|kolkata|ahmedabad)",
    "us": r"\b(united states|usa|u\.s\.|,\s*[A-Z]{2}\b|new york|california|"
          r"texas|san francisco|austin|chicago|seattle|boston)",
    "canada": r"\b(canada|toronto|vancouver|montreal|ontario)",
    "uk": r"\b(united kingdom|england|london|manchester|scotland)",
    "eu": r"\b(germany|france|netherlands|spain|ireland|poland|berlin|paris|"
          r"amsterdam|dublin|lisbon|stockholm)",
    "gulf": r"\b(uae|dubai|abu dhabi|saudi|qatar|doha|riyadh)",
    "remote": r"\b(remote|worldwide|anywhere)",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:40]


def market_of(text: str) -> str:
    for name, pattern in MARKETS.items():
        if re.search(pattern, str(text or ""), re.I):
            return name
    return "unknown"


def deal_features(deal: dict) -> list[str]:
    feats = [f"{PREFIX}source={_slug(deal.get('source'))}",
             f"{PREFIX}client={_slug(deal.get('client_kind') or 'unknown')}",
             f"{PREFIX}work={_slug(deal.get('work_kind') or 'unknown')}",
             f"{PREFIX}market={market_of(deal.get('location') or deal.get('market'))}"]
    if deal.get("package_id"):
        feats.append(f"{PREFIX}package={_slug(deal['package_id'])}")
    if deal.get("currency"):
        feats.append(f"{PREFIX}currency={_slug(deal['currency'])}")
    if deal.get("company"):
        feats.append(f"{PREFIX}company={_slug(deal['company'])}")
    return feats


class DevMemory(_Memory):
    def counts(self, refresh: bool = False):
        if self._cache is not None and not refresh:
            return self._cache
        rows = self.store.query(
            "SELECT feature, outcome, weight FROM prospect_feedback "
            "WHERE feature LIKE ?", (PREFIX + "%",))
        out: dict[str, list[float]] = {}
        for r in rows:
            wins, losses = out.setdefault(r["feature"], [0.0, 0.0])
            w = float(r["weight"])
            if w >= 0:
                out[r["feature"]][0] = wins + w
            else:
                out[r["feature"]][1] = losses - w
        self._cache = {k: (v[0], v[1]) for k, v in out.items()}
        return self._cache

    def record_deal(self, deal: dict, outcome: str, note: str = "") -> int:
        weight = OUTCOME_WEIGHT.get(outcome)
        if weight is None:
            log.warn(f"ignoring unknown dev outcome {outcome!r}")
            return 0
        feats = deal_features(deal)
        stamp = _now()
        for feat in feats:
            self.store.run(
                "INSERT INTO prospect_feedback "
                "(id, domain, feature, outcome, weight, note, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, _slug(deal.get("company")), feat, outcome,
                 weight, note[:400], stamp))
        self._cache = None
        log.info("learned from a dev deal", outcome=outcome,
                 features=len(feats), company=deal.get("company", ""))
        return len(feats)

    def score_deal(self, deal: dict) -> tuple[float, list[dict]]:
        return self.score(deal, feats=deal_features(deal))

    def summary(self, limit: int = 12) -> dict:
        counts = self.counts()
        ranked = sorted(((f, self.contribution(f), w, l)
                         for f, (w, l) in counts.items()), key=lambda t: -t[1])
        rows = self.store.query(
            "SELECT outcome, COUNT(*) n FROM prospect_feedback "
            "WHERE feature LIKE ? GROUP BY outcome", (PREFIX + "%",))
        return {
            "decisions": sum(int(r["n"]) for r in rows),
            "events": {r["outcome"]: int(r["n"]) for r in rows},
            "base_rate": self.base_rate(),
            "best": [{"feature": f.removeprefix(PREFIX), "shift": round(c, 3),
                      "for": round(w, 1), "against": round(l, 1)}
                     for f, c, w, l in ranked[:limit] if c > 0],
            "worst": [{"feature": f.removeprefix(PREFIX), "shift": round(c, 3),
                       "for": round(w, 1), "against": round(l, 1)}
                      for f, c, w, l in reversed(ranked[-limit:]) if c < 0],
        }
