"""What the agents have learned to do differently.

The brains in agents/*/brain.py learn which targets are worth approaching.
That is ranking, and ranking alone cannot stop an agent repeating the same
mistake in the text it writes - reject a draft for being too long and the next
one is exactly as long, because nothing about the rejection ever reaches the
prompt.

This is the other half. Every rejection note and every edit becomes one rule,
in plain English, stored durably and read back into the prompt before the next
draft. A rule that keeps being followed by drafts he approves gains weight; one
that stops mattering is retired rather than deleted, so the history of why the
agent behaves as it does survives.

It is deliberately readable. `/learned` prints these rules as sentences, and he
can argue with any of them - which is the only way to tell an agent that has
learned something from one that has learned a superstition.
"""
from __future__ import annotations

import re
import time
import uuid

from core.log import get_logger
from core.store import Store, get_store

log = get_logger("lessons")

# How many rules to put in front of the model. Past about a dozen a local model
# starts ignoring the list rather than following it, and the newest, most
# specific rules are the ones worth spending that budget on.
MAX_IN_PROMPT = 10

# Longer than this and it is a paragraph, not a rule. Rules the model cannot
# hold in one thought do not get followed.
MAX_RULE_CHARS = 180


def _now() -> float:
    return time.time()


def _norm(text: str) -> str:
    """For deciding whether two rules are the same rule."""
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def _words(text: str) -> set:
    return {w for w in _norm(text).split() if len(w) > 3}


class Lessons:
    """The rules one agent has learned, and the evidence behind each."""

    def __init__(self, agent: str, store: Store | None = None):
        self.agent = agent
        self.store = store or get_store()

    # -- writing -----------------------------------------------------------
    def add(self, rule: str, *, evidence: str = "", scope: str = "",
            weight: float = 1.0) -> str:
        """Record a rule. Saying the same thing twice strengthens it instead."""
        rule = " ".join((rule or "").split())[:MAX_RULE_CHARS]
        if len(rule) < 12:
            return ""
        existing = self._same_rule(rule, scope)
        if existing:
            self.store.run(
                "UPDATE lessons SET weight = weight + ?, evidence = ?, "
                "retired_at = 0 WHERE id = ?",
                (weight, (evidence or existing["evidence"])[:600], existing["id"]))
            log.info("a lesson was reinforced", agent=self.agent, rule=rule[:60])
            return existing["id"]
        lid = uuid.uuid4().hex
        self.store.run(
            "INSERT INTO lessons (id, agent, scope, rule, evidence, weight, "
            "uses, created_at, last_used_at, retired_at) "
            "VALUES (?,?,?,?,?,?,0,?,0,0)",
            (lid, self.agent, scope, rule, (evidence or "")[:600], weight, _now()))
        log.info("learned a rule", agent=self.agent, rule=rule[:70])
        return lid

    def _same_rule(self, rule: str, scope: str) -> dict | None:
        """Near-duplicate detection, so twenty rejections do not make twenty
        near-identical rules that crowd out everything else."""
        want = _words(rule)
        if not want:
            return None
        for row in self.all():
            if scope and row["scope"] and row["scope"] != scope:
                continue
            have = _words(row["rule"])
            if not have:
                continue
            overlap = len(want & have) / max(len(want | have), 1)
            if overlap >= 0.6:
                return row
        return None

    def retire(self, lesson_id: str) -> None:
        self.store.run("UPDATE lessons SET retired_at=? WHERE id=? AND agent=?",
                       (_now(), lesson_id, self.agent))

    def forget(self, lesson_id: str) -> None:
        """He said the rule is wrong. Remove it rather than retire it."""
        self.store.run("DELETE FROM lessons WHERE id=? AND agent=?",
                       (lesson_id, self.agent))

    # -- reading -----------------------------------------------------------
    def all(self, include_retired: bool = False) -> list[dict]:
        sql = ("SELECT * FROM lessons WHERE agent=?"
               + ("" if include_retired else " AND retired_at=0")
               + " ORDER BY weight DESC, created_at DESC")
        return self.store.query(sql, (self.agent,))

    def relevant(self, context: str = "", scope: str = "",
                 limit: int = MAX_IN_PROMPT) -> list[dict]:
        """The rules worth spending prompt space on for this target.

        Scored on weight first, because a rule he has made twice matters more
        than one he made once, then on whether its words appear in what is
        about to be written about. A rule about pricing is not worth showing
        when the draft is a first hello.
        """
        rows = self.all()
        if scope:
            rows = [r for r in rows if not r["scope"] or r["scope"] == scope]
        ctx = _words(context)
        scored = []
        for r in rows:
            score = float(r["weight"])
            if ctx:
                overlap = len(_words(r["rule"]) & ctx)
                score += min(overlap, 4) * 0.4
            # A rule nobody has followed yet gets a small nudge so it is not
            # crowded out forever by older, heavier ones.
            if not int(r["uses"] or 0):
                score += 0.3
            scored.append((score, r))
        scored.sort(key=lambda t: -t[0])
        return [r for _, r in scored[:limit]]

    def mark_used(self, rows: list[dict]) -> None:
        for r in rows:
            self.store.run(
                "UPDATE lessons SET uses = uses + 1, last_used_at = ? WHERE id = ?",
                (_now(), r["id"]))

    def prompt_block(self, context: str = "", scope: str = "",
                     limit: int = MAX_IN_PROMPT) -> str:
        """The rules, as text to paste into a prompt. Empty when there are none."""
        rows = self.relevant(context, scope, limit)
        if not rows:
            return ""
        self.mark_used(rows)
        lines = ["WHAT YOU HAVE LEARNED SO FAR",
                 "These come from drafts he rejected or rewrote. They are not "
                 "suggestions - a draft that breaks one of these gets rejected "
                 "again."]
        for r in rows:
            lines.append(f"- {r['rule']}")
        return "\n".join(lines)

    def summary(self) -> dict:
        rows = self.all(include_retired=True)
        live = [r for r in rows if not r["retired_at"]]
        return {"total": len(rows), "live": len(live),
                "followed": sum(int(r["uses"] or 0) for r in live),
                "rules": live}


def get_lessons(agent: str, store: Store | None = None) -> Lessons:
    return Lessons(agent, store)
