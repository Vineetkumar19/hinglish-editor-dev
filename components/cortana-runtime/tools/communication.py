"""Email / WhatsApp / calendar / Telegram — Phase 14, credential-free.

Important design decision, stated plainly because it changes what these
tools promise:

These tools **compose and open** a message; they do not silently send it.
"Send an email to X saying Y" opens your mail client (or Gmail) with the
recipient, subject and body already filled in, and you press Send.
WhatsApp opens the chat with the message typed out, and you press Send.

Two reasons, and both are deliberate:

1. No credentials required. Truly sending mail needs SMTP credentials or
   an OAuth app; sending WhatsApp needs the paid WhatsApp Business API.
   Neither exists here, and hard-coding an app password into a config
   file on disk is a bad trade for a local assistant.
2. A local 3B model mis-hearing a dictated sentence and then silently
   emailing it to a real person is not a recoverable mistake. A human
   pressing Send is the right last step, and costs one click.

The handoff is done through URL schemes Windows already understands
(mailto:, https://wa.me/, Google Calendar's event template, tg://), so
there is no API key, no login flow, and nothing stored.
"""

import platform
import subprocess
import urllib.parse
from core.processes import shell_open
from datetime import datetime, timedelta, timezone

from core.tool_registry import tool
from core.permissions import RiskLevel

GMAIL_COMPOSE = "https://mail.google.com/mail/?view=cm&fs=1"
GCAL_TEMPLATE = "https://calendar.google.com/calendar/render?action=TEMPLATE"


class BadRecipient(Exception):
    pass


def _launch(url: str) -> bool:
    """Hand a URL to Windows. Returns whether it actually launched."""
    if platform.system() != "Windows":
        return False
    shell_open(url)
    return True


def _clean_phone(phone: str) -> str:
    """Digits only, with a default country code for bare 10-digit numbers."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        raise BadRecipient("No usable phone number given.")
    if len(digits) == 10:  # bare Indian mobile number
        digits = "91" + digits
    if not 10 <= len(digits) <= 15:
        raise BadRecipient(f"'{phone}' doesn't look like a valid phone number.")
    return digits


# ------------------------------------------------------------------ email

def compose_email(to: str = "", subject: str = "", body: str = "", use_gmail: bool = True) -> dict:
    to = (to or "").strip()
    if to and "@" not in to:
        raise BadRecipient(f"'{to}' is not a valid email address.")

    if use_gmail:
        params = {}
        if to:
            params["to"] = to
        if subject:
            params["su"] = subject
        if body:
            params["body"] = body
        url = GMAIL_COMPOSE + ("&" + urllib.parse.urlencode(params) if params else "")
    else:
        query = {}
        if subject:
            query["subject"] = subject
        if body:
            query["body"] = body
        url = f"mailto:{urllib.parse.quote(to)}"
        if query:
            url += "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)

    launched = _launch(url)
    return {
        "opened": launched,
        "to": to,
        "subject": subject,
        "via": "gmail" if use_gmail else "default mail app",
        "note": (
            "Draft is open with everything filled in — review it and press Send. "
            "Cortana does not send mail on its own."
            if launched
            else "Not running on Windows — skipped launch (sandbox verification only)."
        ),
        "url": url,
    }


# --------------------------------------------------------------- whatsapp

def send_whatsapp(phone: str = "", message: str = "", contact_name: str = "") -> dict:
    if not phone:
        return {
            "opened": False,
            "error": (
                f"I need a phone number to message {contact_name or 'them'}. "
                "Tell me the number, or ask me to remember it for next time "
                "(e.g. 'remember Amit's number is 9876543210')."
            ),
        }

    digits = _clean_phone(phone)
    url = f"https://wa.me/{digits}"
    if message:
        url += "?text=" + urllib.parse.quote(message)

    launched = _launch(url)
    return {
        "opened": launched,
        "to": contact_name or digits,
        "message": message,
        "note": (
            "WhatsApp is open with the message typed in — press Send to deliver it."
            if launched
            else "Not running on Windows — skipped launch (sandbox verification only)."
        ),
        "url": url,
    }


# --------------------------------------------------------------- calendar

_IST = timezone(timedelta(hours=5, minutes=30), 'Asia/Kolkata')


def _calendar_range(when, duration_minutes):
    from tools.reminders import parse_when
    try:
        start = datetime.fromisoformat(when)
    except ValueError:
        start = datetime.fromtimestamp(parse_when(when, now=datetime.now(_IST)), tz=_IST)
    if start.tzinfo is None:
        start = start.replace(tzinfo=_IST)
    start = start.astimezone(_IST)
    if not 5 <= duration_minutes <= 480:
        raise ValueError('Choose a duration between 5 and 480 minutes.')
    return start, start + timedelta(minutes=duration_minutes)


def _calendar_preview(title, when, duration_minutes=60, details='', location=''):
    from core.communication_targets import sender_email
    start, end = _calendar_range(when, duration_minutes)
    return {'title':title,'when':start.isoformat(),'duration_minutes':duration_minutes,
            'details':details,'location':location}, (
        f"Prepare calendar event: {title}\nAccount: {sender_email()}\n"
        f"Start: {start.isoformat()} (Asia/Kolkata)\nEnd: {end.isoformat()}\n"
        f"Location: {location or 'None'}\nDetails: {details or 'None'}\nGuests: None.")


def create_calendar_event(
    title: str, when: str, duration_minutes: int = 60, details: str = "", location: str = ""
) -> dict:
    start, end = _calendar_range(when, duration_minutes)
    def stamp(value):
        return value.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{stamp(start)}/{stamp(end)}",
        "ctz": "Asia/Kolkata",
    }
    if details:
        params["details"] = details
    if location:
        params["location"] = location

    _open_calendar_route('render', params)
    return {
        "opened": True,
        "status": "opened_unverified",
        "title": title,
        "starts": start.strftime("%a %d %b, %I:%M %p"),
        "ends": end.strftime("%I:%M %p"),
        "note": "I opened the reviewed event form. Check the title, times, calendar and guests before saving.",
    }


def _open_calendar_route(route, parameters=None):
    from core.app_config import approved_apps
    from core.communication_targets import chrome_profile_args, sender_email
    from core.processes import public_environment
    from pathlib import Path

    chrome = approved_apps().get('chrome')
    if not isinstance(chrome, list) or not chrome or not Path(chrome[0]).is_file():
        raise ValueError('The configured Chrome application was not found.')
    sender = sender_email()
    url = 'https://calendar.google.com/calendar/' + route + '?' + urllib.parse.urlencode({**(parameters or {}),'authuser':sender})
    subprocess.Popen([chrome[0], *chrome_profile_args(), url], env=public_environment(), shell=False)
    return sender


def open_calendar(view: str = "day") -> dict:
    view_key = (view or "day").strip().lower()
    path = {"day":"day", "week":"week", "month":"month", "agenda":"agenda", "schedule":"agenda"}.get(view_key)
    if path is None:
        return {'opened':False, 'error':'Choose Calendar day, week, month or schedule view.'}
    _open_calendar_route('r/' + path)
    return {'opened':True, 'view':path, 'status':'opened_unverified',
            'note':'I asked Chrome to open Calendar. Check the signed-in account and schedule view in the browser.'}


def calendar_availability(date: str) -> dict:
    from datetime import date as calendar_date
    from core.desktop_drafts import draft_request
    day = calendar_date.fromisoformat(date)
    if day.isoformat() != date:
        raise ValueError('Use the date YYYY-MM-DD.')
    return draft_request('calendar_availability', {'date':date})


# --------------------------------------------------------------- telegram

def open_telegram(contact: str = "") -> dict:
    if contact:
        handle = contact.strip().lstrip("@")
        url = f"https://t.me/{urllib.parse.quote(handle)}"
    else:
        url = "https://web.telegram.org"
    launched = _launch(url)
    return {"opened": launched, "contact": contact or "(app)", "url": url}


# ------------------------------------------------------------ registration

tool(
    name="compose_email",
    description=(
        "Open a pre-filled email draft with the recipient, subject and body ready "
        "to send. Use when the user asks to email/write to someone. The user "
        "presses Send themselves — never claim the email was sent."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string", "description": "Subject line."},
            "body": {"type": "string", "description": "Full message body."},
            "use_gmail": {"type": "boolean", "description": "Open in Gmail (default true) vs the desktop mail app."},
        },
        "required": [],
    },
)(compose_email)

tool(
    name="send_whatsapp",
    description=(
        "Open WhatsApp with a message typed out to a phone number, ready to send. "
        "The user presses Send — never claim the message was delivered. If you "
        "don't know the number, use recall_facts to look for a saved one first."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Phone number, with or without country code."},
            "message": {"type": "string", "description": "The message text."},
            "contact_name": {"type": "string", "description": "Who this is, for the reply back to the user."},
        },
        "required": [],
    },
)(send_whatsapp)

tool(
    name="create_calendar_event",
    description=(
        "Open Google Calendar with a new event pre-filled. Use for 'schedule a "
        "meeting', 'add to my calendar', 'book time for X'. The user presses Save."
    ),
    risk=RiskLevel.HIGH,
    prepare=_calendar_preview,
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title."},
            "when": {"type": "string", "description": "Start time in plain language, e.g. 'tomorrow at 3pm'."},
            "duration_minutes": {"type": "integer", "description": "Length in minutes (default 60)."},
            "details": {"type": "string", "description": "Notes/description."},
            "location": {"type": "string", "description": "Where it happens."},
        },
        "required": ["title", "when"],
    },
)(create_calendar_event)

tool(
    name="open_calendar",
    description="Open Google Calendar in the configured Chrome profile and account to see the schedule.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"view": {"type": "string", "enum": ["day", "week", "month", "agenda", "schedule"]}},
        "required": [],
    },
)(open_calendar)

tool(
    name="open_telegram",
    description="Open Telegram, optionally straight to a contact's chat by @username.",
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {"contact": {"type": "string", "description": "Telegram @username, optional."}},
        "required": [],
    },
)(open_telegram)

tool(name='calendar_availability', description='Read the configured account’s visible Google Calendar schedule for an exact date.',
     risk=RiskLevel.LOW, parameters={'type':'object','properties':{'date':{'type':'string','maxLength':10}},
                                     'required':['date']})(calendar_availability)
