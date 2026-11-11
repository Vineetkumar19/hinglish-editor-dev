"""add_reminder / list_reminders / complete_reminder — Phase 17.

Reminders are stored locally in SQLite and surfaced by the desktop app,
which polls /api/reminders/due and has Cortana speak anything that has
come due. No cloud scheduler, no notification service — it works offline
and survives an agent restart because the due time is a stored timestamp,
not an in-memory timer.

Natural-language times ("in 20 minutes", "tomorrow at 6pm", "friday 9am")
are parsed here rather than being pushed onto the 3B model, which is not
reliable at date arithmetic.
"""

import re
import time
from datetime import datetime, timedelta

from core import db
from core.tool_registry import tool
from core.permissions import RiskLevel

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

UNIT_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400,
    "week": 604800, "weeks": 604800,
}


class TimeNotUnderstood(Exception):
    pass


def _parse_clock(text: str, base: datetime) -> datetime | None:
    """'6pm', '18:30', '9 am' -> a datetime today (or tomorrow if past)."""
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if m:
        hour = int(m.group(1)) % 12
        minute = int(m.group(2) or 0)
        if m.group(3) == "pm":
            hour += 12
    else:
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if not m:
            return None
        hour, minute = int(m.group(1)), int(m.group(2))

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_when(when: str, now: datetime | None = None) -> float:
    """Natural-language time -> unix timestamp. Raises if not understood."""
    now = now or datetime.now()
    text = (when or "").strip().lower()
    if not text:
        raise TimeNotUnderstood("No time given.")

    # "in 20 minutes" / "after 2 hours"
    m = re.search(r"\b(?:in|after)\s+(\d+)\s*([a-z]+)", text)
    if m and m.group(2) in UNIT_SECONDS:
        return (now + timedelta(seconds=int(m.group(1)) * UNIT_SECONDS[m.group(2)])).timestamp()

    # "20 minutes" on its own
    m = re.fullmatch(r"(\d+)\s*([a-z]+)", text)
    if m and m.group(2) in UNIT_SECONDS:
        return (now + timedelta(seconds=int(m.group(1)) * UNIT_SECONDS[m.group(2)])).timestamp()

    # weekday, optionally with a clock time
    for name, idx in WEEKDAYS.items():
        if name in text:
            days_ahead = (idx - now.weekday()) % 7
            if days_ahead == 0 and "next" in text:
                days_ahead = 7
            target = now + timedelta(days=days_ahead)
            clock = _parse_clock(text, target)
            target = clock or target.replace(hour=9, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=7)
            return target.timestamp()

    if "tomorrow" in text:
        base = now + timedelta(days=1)
        target = _parse_clock(text, base) or base.replace(hour=9, minute=0, second=0, microsecond=0)
        return target.timestamp()

    if "tonight" in text:
        return (_parse_clock(text, now) or now.replace(hour=20, minute=0, second=0, microsecond=0)).timestamp()

    # bare clock time -> today, or tomorrow if it's already passed
    clock = _parse_clock(text, now)
    if clock:
        if clock <= now:
            clock += timedelta(days=1)
        return clock.timestamp()

    # explicit date: 2026-08-25 or 25/08/2026
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        target = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 9, 0)
        c = _parse_clock(text, target)
        return (c or target).timestamp()
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if m:
        target = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), 9, 0)
        c = _parse_clock(text, target)
        return (c or target).timestamp()

    raise TimeNotUnderstood(
        f"Couldn't understand the time '{when}'. Try 'in 20 minutes', "
        "'tomorrow at 6pm', 'friday 9am', or '2026-08-25'."
    )


def add_reminder(text: str, when: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"created": False, "error": "The reminder text was empty."}
    try:
        due_ts = parse_when(when)
    except TimeNotUnderstood as e:
        return {"created": False, "error": str(e)}

    rid = db.add_reminder(text, due_ts)
    due_str = datetime.fromtimestamp(due_ts).strftime("%a %d %b, %I:%M %p")
    return {"created": True, "id": rid, "text": text, "due": due_str}


def list_reminders(include_done: bool = False) -> dict:
    items = db.list_reminders(include_done=include_done)
    for it in items:
        it["due"] = datetime.fromtimestamp(it["due_at"]).strftime("%a %d %b, %I:%M %p")
        it["overdue"] = it["due_at"] < time.time() and not it["done"]
    return {"count": len(items), "reminders": items}


def complete_reminder(reminder_id: int) -> dict:
    ok = db.complete_reminder(int(reminder_id))
    return {"completed": ok, "id": reminder_id} if ok else {"completed": False, "error": "No reminder with that id."}


tool(
    name="add_reminder",
    description=(
        "Set a reminder that Cortana will announce when it comes due. Give the "
        "reminder text and when it should fire, in plain language: 'in 20 minutes', "
        "'tomorrow at 6pm', 'friday 9am', '2026-08-25'."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "What to be reminded about."},
            "when": {"type": "string", "description": "When it should fire, in plain language."},
        },
        "required": ["text", "when"],
    },
)(add_reminder)

tool(
    name="list_reminders",
    description="List pending reminders, soonest first. Use when the user asks what's coming up or what their day looks like.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "include_done": {"type": "boolean", "description": "Include already-completed reminders."}
        },
        "required": [],
    },
)(list_reminders)

tool(
    name="complete_reminder",
    description="Mark a reminder as done by its id. Use list_reminders first to find the id.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"reminder_id": {"type": "integer", "description": "Id of the reminder."}},
        "required": ["reminder_id"],
    },
)(complete_reminder)
