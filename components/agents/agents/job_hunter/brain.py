"""The part of the job hunter that gets better.

Same machinery as the sponsorship brain - a beta-binomial per feature, summed
as log-odds, with the working printable - pointed at a different question. It
is deliberately a subclass rather than a copy: the maths was already argued
over once, and two copies drift.

What it learns from is every decision he makes. Approve an SDE role at Meesho
found on LinkedIn and four features gain evidence: `source=linkedin`,
`company=meesho`, `family=software`, `city=bengaluru`. Pass on it and the same
four lose. What a company does afterwards counts for far more than what he
guessed at the card - an interview call is worth four approvals, because an
approval is only his opinion that they might reply.

Every feature is written with a `jh:` prefix and counted separately from the
sponsorship features, which share the same table. Without that, approving a
nutrition brand would quietly make Java roles look more promising.
"""
from __future__ import annotations

import re

from agents.sponsorship.brain import Memory as _Memory
from core.log import get_logger
from core.store import Store

log = get_logger("jobs.brain")

PREFIX = "jh:"

# What each event is worth. The top group is what an employer did; the bottom
# is what he guessed.
OUTCOME_WEIGHT = {
    "offer": 12.0,
    "interview": 6.0,
    "callback": 4.0,        # any human reply that is not a rejection
    "applied": 1.5,         # he approved it and applied
    "shortlisted_by_him": 0.5,
    "passed": -1.0,         # he looked and said no
    "company_rejected": -1.5,
    "no_reply": -0.5,
    "fraud": -4.0,          # the scam filter caught it; never show its like again
}
POSITIVE = {"offer", "interview", "callback", "applied", "shortlisted_by_him"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:40]


def job_features(job: dict) -> list[str]:
    """The handful of things about a posting that might predict his answer.

    Kept small on purpose. Every extra feature splits the same evidence into
    thinner slices, and with a few dozen decisions a year thin slices learn
    nothing.
    """
    match = job.get("match") or {}
    feats = [f"{PREFIX}source={_slug(job.get('source'))}"]
    if job.get("company"):
        feats.append(f"{PREFIX}company={_slug(job['company'])}")
    if match.get("family"):
        feats.append(f"{PREFIX}family={_slug(match['family'])}")

    place = str(job.get("location") or "").lower()
    for city in ("bengaluru", "bangalore", "pune", "hyderabad", "mumbai",
                 "chennai", "noida", "gurugram", "gurgaon", "delhi"):
        if city in place:
            # Bangalore and Bengaluru are one city and must not be two features.
            feats.append(f"{PREFIX}city="
                         + ("bengaluru" if city == "bangalore" else
                            "gurugram" if city == "gurgaon" else city))
            break
    else:
        if job.get("remote"):
            feats.append(f"{PREFIX}city=remote")

    seniority = match.get("seniority")
    if seniority is not None:
        feats.append(f"{PREFIX}level={seniority}")

    coverage = job.get("keyword_coverage")
    if isinstance(coverage, (int, float)):
        band = "high" if coverage >= 0.7 else "mid" if coverage >= 0.45 else "low"
        feats.append(f"{PREFIX}coverage={band}")

    # The two or three skills the posting leads with. More than that and each
    # one carries almost no evidence.
    for skill in (match.get("skills") or [])[:3]:
        feats.append(f"{PREFIX}skill={_slug(skill)}")
    return feats


class JobMemory(_Memory):
    """The sponsorship brain's arithmetic, counting only job evidence."""

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

    def record_job(self, job: dict, outcome: str, note: str = "") -> int:
        weight = OUTCOME_WEIGHT.get(outcome)
        if weight is None:
            log.warn(f"ignoring unknown job outcome {outcome!r}")
            return 0
        import uuid
        from agents.sponsorship.brain import _now
        feats = job_features(job)
        stamp = _now()
        for feat in feats:
            self.store.run(
                "INSERT INTO prospect_feedback "
                "(id, domain, feature, outcome, weight, note, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, _slug(job.get("company")), feat, outcome,
                 weight, note[:400], stamp))
        self._cache = None
        log.info("learned from a job decision", outcome=outcome,
                 features=len(feats), company=job.get("company", ""))
        return len(feats)

    def score_job(self, job: dict) -> tuple[float, list[dict]]:
        return self.score(job, feats=job_features(job))

    def summary(self, limit: int = 12) -> dict:
        counts = self.counts()
        ranked = sorted(
            ((f, self.contribution(f), w, l) for f, (w, l) in counts.items()),
            key=lambda t: -t[1])
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


def get_brain(store: Store | None = None) -> JobMemory:
    return JobMemory(store)
