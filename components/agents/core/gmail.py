"""Gmail REST client - stdlib only, no google-api-python-client.

Covers exactly what the blueprint's event-driven inbox monitor needs:

  * users.watch  - register a Pub/Sub topic against INBOX, with the 7-day
                   expiry tracked so a scheduled job can renew it
  * users.history.list - fetch only the delta since the last stored historyId,
                   instead of re-listing the inbox
  * users.messages.get / send / modify
  * a polling fallback for when you have no public HTTPS endpoint for Pub/Sub

Message bodies are decoded from Gmail's base64url MIME parts and flattened to
plain text.
"""
from __future__ import annotations

import base64
import email.utils
import html as html_mod
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import config, http
from .log import get_logger
from .oauth import GoogleOAuth
from .store import Store, get_store, new_id, now

log = get_logger("gmail")

API = "https://gmail.googleapis.com/gmail/v1"
CURSOR_NS = "gmail_cursor"
WATCH_NS = "gmail_watch"


def b64url_decode(data: str) -> bytes:
    if not data:
        return b""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def html_to_text(html: str) -> str:
    s = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def strip_quoted(text: str) -> str:
    """Drop the quoted history so intent classification sees only the new reply."""
    lines = []
    for line in text.splitlines():
        st = line.strip()
        if st.startswith(">"):
            continue
        if re.match(r"^On .{5,80}\s+wrote:$", st):
            break
        if re.match(r"^-{2,}\s*(Original Message|Forwarded message)", st, re.I):
            break
        if st in ("--", "__") or re.match(r"^_{5,}$", st):
            break
        lines.append(line)
    return "\n".join(lines).strip()


@dataclass
class GmailMessage:
    id: str = ""
    thread_id: str = ""
    history_id: str = ""
    label_ids: list = field(default_factory=list)
    headers: dict = field(default_factory=dict)
    body_text: str = ""
    snippet: str = ""
    internal_date: float = 0.0

    @property
    def subject(self) -> str:
        return self.headers.get("subject", "")

    @property
    def from_addr(self) -> str:
        return email.utils.parseaddr(self.headers.get("from", ""))[1].lower()

    @property
    def from_name(self) -> str:
        return email.utils.parseaddr(self.headers.get("from", ""))[0]

    @property
    def to_addr(self) -> str:
        return email.utils.parseaddr(self.headers.get("to", ""))[1].lower()

    @property
    def rfc_message_id(self) -> str:
        return self.headers.get("message-id", "")

    @property
    def in_reply_to(self) -> str:
        return self.headers.get("in-reply-to", "")

    @property
    def references(self) -> str:
        return self.headers.get("references", "")

    @property
    def reply_text(self) -> str:
        return strip_quoted(self.body_text) or self.snippet

    @property
    def is_auto_reply(self) -> bool:
        h = self.headers
        if h.get("auto-submitted", "").lower() not in ("", "no"):
            return True
        if h.get("x-autoreply") or h.get("x-autorespond"):
            return True
        if h.get("precedence", "").lower() in ("bulk", "auto_reply", "junk"):
            return True
        return bool(re.search(r"\b(out of (the )?office|auto[- ]?reply|"
                              r"automatic reply|on (leave|vacation))\b",
                              self.subject, re.I))


class GmailClient:
    def __init__(self, store: Store | None = None, account: str = "default",
                 base_url: str | None = None, oauth: GoogleOAuth | None = None):
        self.store = store or get_store()
        self.account = account
        self.base = (base_url or config.get("GMAIL_API_BASE", API)).rstrip("/")
        self.oauth = oauth or GoogleOAuth(self.store, account)
        self.user_id = config.get("GMAIL_USER_ID", "me")

    # -- plumbing ------------------------------------------------------------
    def _call(self, method: str, path: str, **kw) -> Any:
        url = f"{self.base}/users/{self.user_id}{path}"
        headers = dict(kw.pop("headers", {}) or {})
        headers.update(self.oauth.headers())
        resp = http.request(method, url, headers=headers, timeout=60, **kw)
        if resp.status == 401:
            # token may have just expired mid-flight; force one refresh + retry
            tok = self.oauth.load()
            if tok:
                self.oauth.refresh(tok)
                headers.update(self.oauth.headers())
                resp = http.request(method, url, headers=headers, timeout=60, **kw)
        resp.raise_for_status()
        return resp.json()

    # -- profile / watch -----------------------------------------------------
    def profile(self) -> dict:
        return self._call("GET", "/profile")

    def watch(self, topic: str, label_ids: Iterable[str] = ("INBOX",)) -> dict:
        """Register a Pub/Sub push subscription. Expires after 7 days."""
        data = self._call("POST", "/watch", json_body={
            "topicName": topic, "labelIds": list(label_ids),
            "labelFilterBehavior": "INCLUDE"})
        record = {"historyId": data.get("historyId"),
                  "expiration": int(data.get("expiration", 0)),
                  "topic": topic, "registered_at": now()}
        self.store.kv_set(WATCH_NS, self.account, record)
        if data.get("historyId") and not self.get_cursor():
            self.set_cursor(str(data["historyId"]))
        log.info("gmail watch registered",
                 expires_in_days=round((record["expiration"] / 1000 - time.time())
                                       / 86400, 2) if record["expiration"] else None)
        return record

    def stop_watch(self) -> None:
        self._call("POST", "/stop")
        self.store.kv_delete(WATCH_NS, self.account)

    def watch_state(self) -> dict:
        return self.store.kv_get(WATCH_NS, self.account, {}) or {}

    def watch_expires_in(self) -> float | None:
        exp = self.watch_state().get("expiration")
        return (int(exp) / 1000 - time.time()) if exp else None

    def renew_watch_if_needed(self, topic: str, within_hours: float = 36.0) -> bool:
        """Called by the scheduler; the blueprint's 7-day renewal cron."""
        left = self.watch_expires_in()
        if left is None or left < within_hours * 3600:
            self.watch(topic)
            return True
        return False

    # -- cursor --------------------------------------------------------------
    def get_cursor(self) -> str | None:
        return self.store.kv_get(CURSOR_NS, self.account)

    def set_cursor(self, history_id: str) -> None:
        self.store.kv_set(CURSOR_NS, self.account, str(history_id))

    # -- history delta -------------------------------------------------------
    def history_since(self, start_history_id: str,
                      history_types: Iterable[str] = ("messageAdded",)) -> list[dict]:
        out, page = [], None
        while True:
            params = {"startHistoryId": str(start_history_id), "maxResults": 500}
            for t in history_types:
                params.setdefault("historyTypes", []).append(t)
            if page:
                params["pageToken"] = page
            data = self._call("GET", "/history", params=params)
            out.extend(data.get("history", []))
            page = data.get("nextPageToken")
            if not page:
                if data.get("historyId"):
                    self.set_cursor(str(data["historyId"]))
                break
        return out

    def new_message_ids_since(self, start_history_id: str) -> list[str]:
        ids, seen = [], set()
        for h in self.history_since(start_history_id):
            for added in h.get("messagesAdded", []):
                m = added.get("message", {})
                mid = m.get("id")
                if mid and mid not in seen and "SENT" not in (m.get("labelIds") or []):
                    seen.add(mid)
                    ids.append(mid)
        return ids

    def handle_push(self, notification: dict) -> list["GmailMessage"]:
        """Process a Pub/Sub push body.

        The payload carries only a base64 blob with {emailAddress, historyId};
        the actual delta comes from users.history.list against our cursor.
        """
        raw = notification.get("message", {}).get("data", "")
        try:
            payload = __import__("json").loads(b64url_decode(raw) or b"{}")
        except Exception:  # noqa: BLE001
            payload = {}
        incoming = str(payload.get("historyId", "")) or None
        cursor = self.get_cursor()
        if not cursor:
            if incoming:
                self.set_cursor(incoming)
            log.warn("no gmail cursor yet; seeding from push and skipping this delta")
            return []
        ids = self.new_message_ids_since(cursor)
        try:
            messages = [self.get_message(i) for i in ids]
        except Exception:
            self.set_cursor(cursor)
            raise
        if incoming:
            self.set_cursor(incoming)
        log.info("gmail push processed", new_messages=len(ids))
        return messages

    def poll(self, query: str = "in:inbox -in:chats newer_than:7d",
             max_results: int = 25) -> list["GmailMessage"]:
        """Fallback when there is no public endpoint for Pub/Sub push."""
        cursor = self.get_cursor()
        if cursor:
            ids = self.new_message_ids_since(cursor)
            if ids:
                try:
                    return [self.get_message(i) for i in ids]
                except Exception:
                    self.set_cursor(cursor)
                    raise
        data = self._call("GET", "/messages",
                          params={"q": query, "maxResults": max_results})
        msgs = []
        for ref in data.get("messages", []) or []:
            if not self.store.seen(f"gmail_poll:{self.account}", ref["id"]):
                message = self.get_message(ref["id"])
                self.store.mark_seen(f"gmail_poll:{self.account}", ref["id"])
                msgs.append(message)
        prof = self.profile()
        if prof.get("historyId"):
            self.set_cursor(str(prof["historyId"]))
        return msgs

    # -- messages ------------------------------------------------------------
    def get_message(self, message_id: str, fmt: str = "full") -> GmailMessage:
        data = self._call("GET", f"/messages/{message_id}", params={"format": fmt})
        return self.parse_message(data)

    @staticmethod
    def parse_message(data: dict) -> GmailMessage:
        payload = data.get("payload", {}) or {}
        headers = {h.get("name", "").lower(): h.get("value", "")
                   for h in payload.get("headers", []) or []}
        text_parts, html_parts = [], []

        def walk(part: dict) -> None:
            mime = part.get("mimeType", "")
            body = part.get("body", {}) or {}
            if body.get("data"):
                decoded = b64url_decode(body["data"]).decode("utf-8", "replace")
                if mime == "text/plain":
                    text_parts.append(decoded)
                elif mime == "text/html":
                    html_parts.append(decoded)
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        body = "\n".join(text_parts).strip()
        if not body and html_parts:
            body = html_to_text("\n".join(html_parts))
        try:
            internal = float(data.get("internalDate", 0)) / 1000.0
        except (TypeError, ValueError):
            internal = 0.0
        return GmailMessage(
            id=data.get("id", ""), thread_id=data.get("threadId", ""),
            history_id=str(data.get("historyId", "")),
            label_ids=data.get("labelIds", []) or [], headers=headers,
            body_text=body, snippet=html_mod.unescape(data.get("snippet", "")),
            internal_date=internal)

    def send_raw(self, raw_mime: bytes, thread_id: str | None = None) -> dict:
        body: dict = {"raw": b64url_encode(raw_mime)}
        if thread_id:
            body["threadId"] = thread_id
        return self._call("POST", "/messages/send", json_body=body)

    def modify(self, message_id: str, add: Iterable[str] = (),
               remove: Iterable[str] = ()) -> dict:
        return self._call("POST", f"/messages/{message_id}/modify", json_body={
            "addLabelIds": list(add), "removeLabelIds": list(remove)})

    def mark_read(self, message_id: str) -> dict:
        return self.modify(message_id, remove=["UNREAD"])
