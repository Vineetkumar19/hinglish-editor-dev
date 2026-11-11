"""Turning a rejection into a rule.

This is the step that makes the difference between an agent that records what
happened and one that changes because of it. When he rejects a draft with
"too long, and stop saying I guarantee anything", that sentence has to become a
standing instruction or the next draft is exactly as long.

The local model does the conversion, and this is a good use for it: it happens
once per decision rather than once per lead, so it is cheap, and turning a
specific complaint into a general rule is exactly what a language model is for.

When there is no model, the complaint is stored verbatim as the rule. Less
sharp, but a verbatim complaint in front of the next draft still works, and an
agent that only learns when a GPU is present is not the agent he asked for.
"""
from __future__ import annotations

import difflib

from core.lessons import MAX_RULE_CHARS, get_lessons
from core.llm import LLMError, get_llm
from core.log import get_logger
from core.store import Store

log = get_logger("reflect")

RULE_SCHEMA = {
    "type": "object",
    "required": ["rules"],
    "properties": {
        "rules": {
            "type": "array", "min_items": 1, "max_items": 3,
            "items": {"type": "string", "min_length": 12,
                      "max_length": MAX_RULE_CHARS},
        },
    },
}

PROMPT = """You wrote a draft. It was rejected or rewritten. Work out what to
do differently next time, as standing rules you will be shown before every
future draft.

{what_happened}

Write between one and three rules.

Rules for the rules:
- Each one must be a general instruction you could follow on a completely
  different target, not a comment about this one. "Do not say we guarantee
  results" is a rule. "Do not say we guarantee results to Acme" is not.
- Imperative, under 25 words, no explanation and no preamble.
- Only what this specific rejection supports. If the note says the email was
  too long, do not also invent a rule about tone.
- If there is genuinely nothing general to learn here, return one rule saying
  exactly: NOTHING GENERAL TO LEARN
"""


def _diff(before: str, after: str, limit: int = 1800) -> str:
    """What he actually changed, as a readable diff."""
    a = (before or "").splitlines()
    b = (after or "").splitlines()
    out = []
    for line in difflib.unified_diff(a, b, lineterm="", n=1):
        if line.startswith(("---", "+++", "@@")):
            continue
        out.append(line)
    return "\n".join(out)[:limit]


def _describe(note: str, before: str, after: str) -> str:
    parts = []
    if note.strip():
        parts.append(f"His reason, in his words:\n\"{note.strip()[:600]}\"")
    if before and after and before.strip() != after.strip():
        parts.append("What you wrote, and what he changed it to "
                     "(- is yours, + is his):\n" + _diff(before, after))
    elif before:
        parts.append("What you wrote, which he rejected:\n" + before[:1200])
    return "\n\n".join(parts)


def learn_from_decision(agent: str, decision, payload: dict, *,
                        store: Store | None = None, scope: str = "",
                        llm=None) -> list[str]:
    """Called after every approval decision. Returns the rules it wrote."""
    note = (getattr(decision, "note", "") or "").strip()
    edits = getattr(decision, "edits", None) or {}
    status = getattr(decision, "status", "")

    before = str(payload.get("body") or "")
    after = str(edits.get("body") or "")
    changed = bool(after and after.strip() != before.strip())

    # An approval with nothing said and nothing changed teaches nothing, and
    # inventing a rule from it would be superstition.
    if status not in ("rejected", "edited") and not (note or changed):
        return []
    if not note and not changed:
        return []

    what = _describe(note, before, after)
    if not what:
        return []

    lessons = get_lessons(agent, store)
    llm = llm or get_llm(store)
    evidence = (note or "he rewrote the draft")[:400]

    if llm.is_offline:
        # No model: his own words become the rule. Blunter, still effective.
        if note:
            return [r for r in [lessons.add(
                f"He rejected a draft for this reason - do not repeat it: {note}",
                evidence=evidence, scope=scope)] if r]
        return []

    try:
        out = llm.structured(
            PROMPT.format(what_happened=what), RULE_SCHEMA,
            task=f"reflect:{agent}",
            system="You improve your own instructions from feedback. You are "
                   "terse and you never explain yourself.",
            temperature=0.1, max_tokens=300)
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warn(f"could not turn the feedback into a rule: {exc}")
        if note:
            return [r for r in [lessons.add(
                f"He rejected a draft for this reason - do not repeat it: {note}",
                evidence=evidence, scope=scope)] if r]
        return []

    made = []
    for rule in (out.get("rules") or []):
        clean = " ".join(str(rule).split())
        if not clean or "NOTHING GENERAL TO LEARN" in clean.upper():
            continue
        lid = lessons.add(clean, evidence=evidence, scope=scope)
        if lid:
            made.append(clean)
    log.info("turned feedback into rules", agent=agent, rules=len(made))
    return made
