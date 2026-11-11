"""Publication-time eligibility shared by the comment reply transports."""

from datetime import datetime, timedelta, timezone


POST_REPLY_WINDOW = timedelta(days=5)


def reply_cutoff(now):
    return now - POST_REPLY_WINDOW


def publication_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def recent_publication(value, now):
    published = publication_time(value)
    return published if published is not None and reply_cutoff(now) < published <= now else None
