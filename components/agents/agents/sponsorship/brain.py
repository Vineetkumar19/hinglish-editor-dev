"""The brain: the part of the sponsorship agent that gets better.

Every decision you make is a labelled example. Approve a barter deal with a
nutrition brand found on Cuelinks and three features just got evidence for
them: `segment=nutrition`, `deal=barter`, `source=cuelinks`. Reject it and the
same three get evidence against. A reply from a brand is stronger evidence than
an approval, because an approval is only your guess that they might answer.

From those counts it builds a score. The maths is a beta-binomial per feature -
count the wins, count the losses, work out how much that feature shifts the
odds, and add the shifts up. Two properties matter more than sophistication:

  it moves on the first example, so the agent is different after one decision
  rather than after a hundred, and

  it can show its working. `/why` prints the exact contribution of every
  feature, so when it ranks something highly you can see the reason and
  disagree with it.

The same counts decide where to spend the next sweep. A source that keeps
producing brands you approve gets more of the budget; one that produces noise
gets less. That is Thompson sampling, and it is about fifteen lines.
"""
from __future__ import annotations

import math
import random
import time
import uuid

from core.log import get_logger
from core.store import Store, get_store

log = get_logger("sponsorship.brain")

# How much each kind of event counts. A reply from a brand is the only signal
# that reflects what the brand thought; the rest reflect what you thought.
OUTCOME_WEIGHT = {
    # What a brand did. Only these reflect what THEY thought, so they weigh
    # most.
    "deal_agreed": 8.0,
    "replied_interested": 4.0,
    "replied_no": -2.0,
    "bounced": -1.5,
    "unsubscribed": -3.0,
    # What you did. A guess about a brand, which is worth less than the
    # brand's own answer, but is the only signal available on day one.
    "added": 1.0,            # you said yes to putting it on the list
    "pitch_approved": 1.5,   # you said yes to actually writing to them
    "sent": 0.5,
    "not_added": -1.0,       # you said no to adding it
    "pitch_rejected": -1.5,  # it got onto the list, and the pitch still failed
    # What the agent itself worked out.
    "unreachable": -0.5,     # no route to a human could be found
}
POSITIVE = {"added", "pitch_approved", "sent", "replied_interested",
            "deal_agreed"}

# Older names, kept so history written before the merge still counts.
ALIASES = {"approved": "added", "rejected": "not_added"}

# Until a feature has been seen this many times, it barely moves the score.
# Without this one lucky approval would make "source=trade_press" look like a
# law of nature.
PRIOR_STRENGTH = 4.0

# The overall hit rate needs a prior of its own. One approval writes evidence
# for six features and nothing against any of them, which without this would
# put the base rate at 100% and make the very first find look like a certainty.
BASE_PRIOR = 30.0
BASE_GUESS = 0.35


def _now() -> float:
    return time.time()


def features_of(prospect: dict) -> list[str]:
    """The handful of things about a prospect worth learning from.

    Deliberately coarse. Learning per-domain would only ever tell us about
    domains we have already seen, which is useless for ranking a brand found
    this morning.
    """
    out = []
    for key in ("source", "segment", "deal_type"):
        val = str(prospect.get(key) or "").strip().lower()
        if val:
            out.append(f"{key}={val}")
    dom = str(prospect.get("domain") or "").lower()
    if dom:
        tld = dom.rsplit(".", 1)[-1]
        out.append(f"tld={tld}")
    india = float(prospect.get("india_score") or 0)
    out.append("india=" + ("high" if india >= 0.6 else
                           "some" if india >= 0.3 else "low"))
    tier = prospect.get("tier")
    if tier:
        out.append(f"tier={tier}")
    data = prospect.get("data") or {}
    out.append("contact=" + ("published" if data.get("has_email") else "none"))
    if data.get("payout"):
        out.append("payout=known")
    if data.get("channel"):
        out.append(f"channel={data['channel']}")
    return out


def target_features(target: dict) -> list[str]:
    """The same view of a brand already on the list.

    This is what makes it one brain rather than two. A target from
    sponsors.yaml and a brand found on the web this morning are described in
    the same vocabulary, so everything learned about one applies to the other:
    if nutrition brands keep replying, that lifts both the next nutrition
    discovery AND the nutrition targets still waiting to be emailed.
    """
    meta = target.get("meta") or target
    dom = str(meta.get("url") or meta.get("domain") or "")
    dom = dom.split("//")[-1].split("/")[0].removeprefix("www.")
    tags = [str(t).lower() for t in (meta.get("tags") or [])]
    return features_of({
        "domain": dom,
        "source": "list" if "discovered" not in tags else "discovered",
        "segment": meta.get("segment", ""),
        "deal_type": meta.get("deal_type", ""),
        "tier": meta.get("tier"),
        "india_score": 1.0,          # everything on the list is already Indian
        "data": {"has_email": bool(meta.get("email"))},
    })


class Memory:
    """Counts of what worked, and the score that falls out of them."""

    def __init__(self, store: Store | None = None):
        self.store = store or get_store()
        self._cache: dict[str, tuple[float, float]] | None = None

    # -- writing -----------------------------------------------------------
    def record(self, prospect: dict, outcome: str, note: str = "") -> int:
        """File one decision against every feature of the thing decided on."""
        outcome = ALIASES.get(outcome, outcome)
        weight = OUTCOME_WEIGHT.get(outcome)
        if weight is None:
            log.warn(f"ignoring unknown outcome {outcome!r}")
            return 0
        feats = features_of(prospect)
        now = _now()
        for feat in feats:
            self.store.run(
                "INSERT INTO prospect_feedback "
                "(id, domain, feature, outcome, weight, note, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, str(prospect.get("domain") or ""), feat,
                 outcome, weight, note[:400], now))
        self._cache = None
        log.info("learned from a decision", outcome=outcome,
                 features=len(feats), domain=prospect.get("domain", ""))
        return len(feats)

    # -- reading -----------------------------------------------------------
    def counts(self, refresh: bool = False) -> dict[str, tuple[float, float]]:
        """feature -> (evidence for, evidence against)."""
        if self._cache is not None and not refresh:
            return self._cache
        # The job hunter writes its own evidence to this same table, prefixed
        # "jh:". Counting it here would make approving a nutrition brand shift
        # the odds on Java roles, and vice versa.
        rows = self.store.query(
            "SELECT feature, outcome, weight FROM prospect_feedback "
            "WHERE feature NOT LIKE 'jh:%' AND feature NOT LIKE 'vc:%' AND feature NOT LIKE 'fs:%' AND feature NOT LIKE 'sm:%'")
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

    def base_rate(self) -> float:
        counts = self.counts()
        wins = sum(w for w, _ in counts.values())
        losses = sum(l for _, l in counts.values())
        rate = ((wins + BASE_GUESS * BASE_PRIOR) /
                (wins + losses + BASE_PRIOR))
        return max(0.05, min(0.90, rate))

    def contribution(self, feature: str) -> float:
        """How much this feature shifts the log-odds, shrunk toward nothing."""
        wins, losses = self.counts().get(feature, (0.0, 0.0))
        seen = wins + losses
        if seen <= 0:
            return 0.0
        base = self.base_rate()
        rate = (wins + base * PRIOR_STRENGTH) / (seen + PRIOR_STRENGTH)
        rate = max(0.02, min(0.98, rate))
        shift = math.log(rate / (1 - rate)) - math.log(base / (1 - base))
        # Confidence grows with evidence, so one example cannot dominate.
        confidence = seen / (seen + PRIOR_STRENGTH)
        return shift * confidence

    def score(self, prospect: dict, feats: list[str] | None = None
              ) -> tuple[float, list[dict]]:
        """A 0-1 score, plus the working so it can be argued with."""
        base = self.base_rate()
        logit = math.log(base / (1 - base))
        why = []
        for feat in (feats if feats is not None else features_of(prospect)):
            c = self.contribution(feat)
            wins, losses = self.counts().get(feat, (0.0, 0.0))
            logit += c
            why.append({"feature": feat, "shift": round(c, 3),
                        "for": round(wins, 1), "against": round(losses, 1)})
        why.sort(key=lambda d: -abs(d["shift"]))
        return 1 / (1 + math.exp(-logit)), why

    # -- where to spend the next sweep -------------------------------------
    def source_weights(self, sources: list[str]) -> dict[str, float]:
        """Thompson sampling over each source's hit rate.

        Sources with a good record get most of the budget, but every source
        keeps a real chance of being tried, so a source that was unlucky early
        on is not written off forever.
        """
        out = {}
        for name in sources:
            wins, losses = self.counts().get(f"source={name}", (0.0, 0.0))
            out[name] = random.betavariate(1.0 + wins, 1.0 + losses)
        total = sum(out.values()) or 1.0
        return {k: v / total for k, v in out.items()}

    def score_target(self, target: dict) -> tuple[float, list[dict]]:
        """How promising a brand already on the list is, right now."""
        return self.score(target, feats=target_features(target))

    def record_target(self, target: dict, outcome: str, note: str = "") -> int:
        """File an outreach outcome against a brand on the list."""
        meta = target.get("meta") or target
        dom = str(meta.get("url") or meta.get("domain") or "")
        dom = dom.split("//")[-1].split("/")[0].removeprefix("www.")
        outcome = ALIASES.get(outcome, outcome)
        weight = OUTCOME_WEIGHT.get(outcome)
        if weight is None:
            log.warn(f"ignoring unknown outcome {outcome!r}")
            return 0
        now = _now()
        feats = target_features(target)
        for feat in feats:
            self.store.run(
                "INSERT INTO prospect_feedback "
                "(id, domain, feature, outcome, weight, note, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, dom, feat, outcome, weight, note[:400], now))
        self._cache = None
        log.info("learned from outreach", outcome=outcome, domain=dom,
                 features=len(feats))
        return len(feats)

    def summary(self, limit: int = 12) -> dict:
        counts = self.counts(refresh=True)
        rows = []
        for feat, (wins, losses) in counts.items():
            rows.append({"feature": feat, "for": wins, "against": losses,
                         "shift": self.contribution(feat)})
        rows.sort(key=lambda r: -abs(r["shift"]))
        decisions = self.store.one(
            "SELECT COUNT(*) AS n FROM prospect_feedback "
            "WHERE feature NOT LIKE 'jh:%' AND feature NOT LIKE 'vc:%' AND feature NOT LIKE 'fs:%' AND feature NOT LIKE 'sm:%'") or {"n": 0}
        by_outcome = {r["outcome"]: int(r["n"]) for r in self.store.query(
            "SELECT outcome, COUNT(*) AS n FROM prospect_feedback "
            "WHERE feature NOT LIKE 'jh:%' AND feature NOT LIKE 'vc:%' AND feature NOT LIKE 'fs:%' AND feature NOT LIKE 'sm:%' GROUP BY outcome ORDER BY n DESC")}
        return {
            "decisions": int(decisions.get("n") or 0),
            "events": by_outcome,
            "base_rate": self.base_rate(),
            "best": [r for r in rows if r["shift"] > 0][:limit],
            "worst": [r for r in rows if r["shift"] < 0][:limit],
        }
