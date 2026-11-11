"""Google Calendar REST client - freebusy, slot finding and event creation."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config, http
from .log import get_logger
from .oauth import GoogleOAuth
from .store import Store, get_store

log = get_logger("calendar")

API = "https://www.googleapis.com/calendar/v3"


def timezone(label: str):
    try:
        return ZoneInfo(label)
    except ZoneInfoNotFoundError:
        if label in ("Asia/Kolkata", "Asia/Calcutta"):
            return dt.timezone(dt.timedelta(hours=5, minutes=30), label)
        if label in ("UTC", "Etc/UTC"):
            return dt.timezone.utc
        raise ValueError(f"Install tzdata for timezone {label}")


def _rfc3339(t: dt.datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Slot:
    start: dt.datetime
    end: dt.datetime

    def human(self, tz_label: str = "") -> str:
        start = self.start.astimezone(timezone(tz_label)) if tz_label else self.start
        end = self.end.astimezone(timezone(tz_label)) if tz_label else self.end
        return (f"{start.strftime('%a %d %b, %H:%M')}"
                f"-{end.strftime('%H:%M')}"
                + (f" {tz_label}" if tz_label else ""))


class CalendarClient:
    def __init__(self, store: Store | None = None, account: str = "default",
                 base_url: str | None = None, oauth: GoogleOAuth | None = None):
        self.store = store or get_store()
        self.base = (base_url or config.get("CALENDAR_API_BASE", API)).rstrip("/")
        self.oauth = oauth or GoogleOAuth(self.store, account)
        self.calendar_id = config.get("CALENDAR_ID", "primary")
        self.tz = config.get("TIMEZONE", "Asia/Kolkata")

    def _call(self, method: str, path: str, **kw):
        headers = dict(kw.pop("headers", {}) or {})
        headers.update(self.oauth.headers())
        resp = http.request(method, f"{self.base}{path}", headers=headers,
                            timeout=45, **kw)
        resp.raise_for_status()
        return resp.json()

    def freebusy(self, start: dt.datetime, end: dt.datetime) -> list[tuple]:
        data = self._call("POST", "/freeBusy", json_body={
            "timeMin": _rfc3339(start), "timeMax": _rfc3339(end),
            "timeZone": self.tz, "items": [{"id": self.calendar_id}]})
        busy = (data.get("calendars", {}).get(self.calendar_id, {})
                .get("busy", []) or [])
        out = []
        for b in busy:
            try:
                out.append((dt.datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                            dt.datetime.fromisoformat(b["end"].replace("Z", "+00:00"))))
            except (KeyError, ValueError):
                continue
        return out

    def find_slots(self, *, days_ahead: int = 7, duration_min: int = 30,
                   work_start: int = 10, work_end: int = 18,
                   max_slots: int = 5, skip_weekends: bool = True,
                   now: dt.datetime | None = None) -> list[Slot]:
        """Propose interview times that do not clash with anything on the calendar."""
        now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(timezone(self.tz))
        start = now + dt.timedelta(hours=config.get_int("SCHEDULE_LEAD_HOURS", 18))
        end = now + dt.timedelta(days=days_ahead)
        busy = self.freebusy(start, end)

        slots: list[Slot] = []
        cursor = start.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        step = dt.timedelta(minutes=30)
        length = dt.timedelta(minutes=duration_min)
        while cursor + length <= end and len(slots) < max_slots:
            if skip_weekends and cursor.weekday() >= 5:
                cursor += dt.timedelta(days=1)
                cursor = cursor.replace(hour=work_start, minute=0)
                continue
            if not (work_start <= cursor.hour < work_end):
                cursor += step
                continue
            finish = cursor + length
            if finish.date() != cursor.date() or (finish.hour, finish.minute) > (work_end, 0):
                cursor += step
                continue
            clash = any(cursor < b_end and finish > b_start for b_start, b_end in busy)
            if not clash:
                slots.append(Slot(cursor, finish))
                cursor += dt.timedelta(hours=2)   # spread proposals out
            else:
                cursor += step
        return slots

    def create_event(self, *, summary: str, start: dt.datetime, end: dt.datetime,
                     attendees: list[str] | None = None, description: str = "",
                     location: str = "", add_meet: bool = False, event_id: str = "") -> dict:
        body = {
            "summary": summary, "description": description, "location": location,
            "start": {"dateTime": _rfc3339(start), "timeZone": self.tz},
            "end": {"dateTime": _rfc3339(end), "timeZone": self.tz},
            "attendees": [{"email": a} for a in (attendees or [])],
            "reminders": {"useDefault": True},
        }
        params = {"sendUpdates": "all"}
        if event_id:
            body["id"] = event_id
        if add_meet:
            body["conferenceData"] = {"createRequest": {
                "requestId": f"agentsuite-{int(start.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
            params["conferenceDataVersion"] = 1
        try:
            data = self._call("POST", f"/calendars/{self.calendar_id}/events",
                              json_body=body, params=params)
        except http.HttpError as exc:
            if event_id and exc.status == 409:
                return self._call("GET", f"/calendars/{self.calendar_id}/events/{event_id}")
            raise
        log.info("calendar event created", event_id=data.get("id"),
                 when=_rfc3339(start))
        return data

    def list_events(self, start: dt.datetime, end: dt.datetime) -> list[dict]:
        data = self._call("GET", f"/calendars/{self.calendar_id}/events",
                          params={"timeMin": _rfc3339(start), "timeMax": _rfc3339(end),
                                  "singleEvents": "true", "orderBy": "startTime"})
        return data.get("items", []) or []
