"""What kinds of client are worth his time.

Third use of the same arithmetic, and again a subclass rather than a copy.
Features are about the deal, not the person: which source found them, what kind
of client they are, which market, which tier of work, and what they actually
paid. Prefixed `vc:` and counted apart from the other two agents, which share
the table.

The outcome that matters here is money. An approval is a guess, a reply is
interest, and only `deal_won` and `paid` mean anything landed - so they
outweigh everything else by a wide margin.
"""
from __future__ import annotations

import re
import uuid

from agents.sponsorship.brain import Memory as _Memory, _now
from core.log import get_logger
from core.store import Store

log = get_logger("video.brain")

PREFIX = "vc:"

OUTCOME_WEIGHT = {
    "replied_no": -2.0,
    "unsubscribed": -3.0,
    "paid": 16.0,            # the invoice cleared
    "deal_won": 10.0,        # they said yes to a number
    "quoted": 2.0,           # they asked for a rate - real interest
    "replied": 3.0,
    "pitch_approved": 1.0,
    "sent": 0.5,
    "pitch_rejected": -1.0,
    "no_reply": -1.0,        # after the last chase, nothing
    "declined_price": -2.0,  # they came back and the number killed it
    "ghosted_after_quote": -2.5,
    "bounced": -1.5,
}
POSITIVE = {"paid", "deal_won", "quoted", "replied", "pitch_approved", "sent"}

MARKETS = {
    "us": r"\b(united states|usa|u\.s\.|,\s*[A-Z]{2}\b|new york|california|texas|"
          r"florida|chicago|seattle|austin|boston|los angeles)",
    "canada": r"\b(canada|toronto|vancouver|montreal|ontario|quebec|alberta)",
    "uk": r"\b(united kingdom|england|london|manchester|scotland|wales)",
    "eu": r"\b(germany|france|netherlands|spain|ireland|poland|berlin|paris|"
          r"amsterdam|dublin|madrid|lisbon|stockholm)",
    "india": r"\b(india|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune)",
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
    """Kept deliberately few - a handful of deals a month cannot teach more."""
    feats = [f"{PREFIX}source={_slug(deal.get('source'))}"]
    kind = deal.get("kind") or "unknown"
    feats.append(f"{PREFIX}client={_slug(kind)}")
    feats.append(f"{PREFIX}market={market_of(deal.get('location') or deal.get('market'))}")
    if deal.get("tier_id"):
        feats.append(f"{PREFIX}work={_slug(deal['tier_id'])}")
    if deal.get("currency"):
        feats.append(f"{PREFIX}currency={_slug(deal['currency'])}")
    if deal.get("company"):
        feats.append(f"{PREFIX}company={_slug(deal['company'])}")
    return feats


class DealMemory(_Memory):
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
            log.warn(f"ignoring unknown deal outcome {outcome!r}")
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
        log.info("learned from a deal", outcome=outcome, features=len(feats),
                 company=deal.get("company", ""))
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
