"""Which audiences are worth the product's launch attention.

Fifth use of the same beta-binomial. The question here is different from the
other four: not "will this person pay" but "does writing to this kind of person
produce anything at all" - a reply, a piece of feedback, a place on a list.
Before launch there is no money to count, so the signals are softer and the
weights reflect that honestly rather than pretending a signup exists.

Features carry the `sm:` prefix and are counted apart from the other four.
"""
from __future__ import annotations

import re
import uuid

from agents.sponsorship.brain import Memory as _Memory, _now
from core.log import get_logger
from core.store import Store

log = get_logger("saas.brain")

PREFIX = "sm:"

OUTCOME_WEIGHT = {
    # After launch.
    "paid": 16.0,
    "signed_up": 8.0,
    "partner_agreed": 10.0,
    # Before launch, which is where this agent actually lives today. Feedback
    # from someone who edits for a living is the most valuable thing available
    # at this stage and is weighted like it.
    "gave_feedback": 6.0,
    "joined_waitlist": 4.0,
    "listed": 3.0,             # a directory accepted the submission
    "replied": 3.0,
    "pitch_approved": 1.0,
    "sent": 0.5,
    # Negative.
    "pitch_rejected": -1.0,
    "no_reply": -1.0,
    "not_interested": -2.0,
    "asked_to_stop": -6.0,     # the worst outcome here by a distance
    "bounced": -1.5,
}
POSITIVE = {"paid", "signed_up", "partner_agreed", "gave_feedback",
            "joined_waitlist", "listed", "replied", "pitch_approved", "sent"}

SIZE_BANDS = ((1_000, "tiny"), (10_000, "small"), (100_000, "mid"),
              (1_000_000, "large"))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:40]


def size_band(subscribers: str) -> str:
    """"103K" -> "large". Audience size predicts reply rate more than anything
    else about a creator, and in the opposite direction to what people hope."""
    raw = str(subscribers or "").strip().upper().replace(",", "")
    m = re.match(r"([\d.]+)\s*([KMB]?)", raw)
    if not m:
        return "unknown"
    try:
        value = float(m.group(1))
    except ValueError:
        return "unknown"
    value *= {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(m.group(2), 1)
    for limit, name in SIZE_BANDS:
        if value < limit:
            return name
    return "huge"


def target_features(target: dict) -> list[str]:
    feats = [f"{PREFIX}source={_slug(target.get('source'))}",
             f"{PREFIX}kind={_slug(target.get('kind') or 'unknown')}"]
    band = size_band(target.get("subscribers") or "")
    if band != "unknown":
        feats.append(f"{PREFIX}size={band}")
    if target.get("has_email") is not None:
        feats.append(f"{PREFIX}contact="
                     + ("published" if target["has_email"] else "none"))
    if target.get("query"):
        feats.append(f"{PREFIX}query={_slug(target['query'])}")
    return feats


class LaunchMemory(_Memory):
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

    def record_target(self, target: dict, outcome: str, note: str = "") -> int:
        weight = OUTCOME_WEIGHT.get(outcome)
        if weight is None:
            log.warn(f"ignoring unknown launch outcome {outcome!r}")
            return 0
        feats = target_features(target)
        stamp = _now()
        for feat in feats:
            self.store.run(
                "INSERT INTO prospect_feedback "
                "(id, domain, feature, outcome, weight, note, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, _slug(target.get("name")), feat, outcome,
                 weight, note[:400], stamp))
        self._cache = None
        log.info("learned from a launch decision", outcome=outcome,
                 features=len(feats), target=target.get("name", ""))
        return len(feats)

    def score_target(self, target: dict) -> tuple[float, list[dict]]:
        return self.score(target, feats=target_features(target))

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
