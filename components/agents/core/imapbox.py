"""Reading replies over IMAP, with the same app password used for sending.

The Gmail API route needs a Google Cloud project, an OAuth consent screen and a
token dance. That is a lot of setup for one job: noticing that a brand wrote
back. IMAP does the same job with the credentials already in the .env file, so
turning on reply alerts costs nothing extra once sending works.

It produces GmailMessage objects, the same shape the rest of the suite already
handles, so nothing downstream needs to know which route the mail came in by.
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import time
from email.header import decode_header, make_header

from . import config
from .gmail import GmailMessage, html_to_text
from .log import get_logger
from .store import Store, get_store

log = get_logger("imap")

# Gmail, Outlook and Zoho all answer on 993 with the same commands; only the
# host differs, and it can be guessed from the address when not configured.
HOST_BY_DOMAIN = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "zoho.com": "imap.zoho.com",
    "zohomail.in": "imap.zoho.in",
}


def _decode(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value


def default_host(address: str) -> str:
    domain = (address or "").rsplit("@", 1)[-1].lower()
    return HOST_BY_DOMAIN.get(domain, f"imap.{domain}" if domain else "")


class ImapBox:
    """Fetches messages that arrived since the last check."""

    def __init__(self, store: Store | None = None):
        self.store = store or get_store()
        self.address = (config.get("IMAP_USER")
                        or config.get("SMTP_USER")
                        or config.get("SENDER_EMAIL", ""))
        self.password = (config.get("IMAP_PASSWORD")
                         or config.get("SMTP_PASSWORD", ""))
        self.host = config.get("IMAP_HOST") or default_host(self.address)
        self.port = config.get_int("IMAP_PORT", 993)
        self.folder = config.get("IMAP_FOLDER", "INBOX")

    @property
    def configured(self) -> bool:
        return bool(self.address and self.password and self.host)

    def _connect(self) -> imaplib.IMAP4_SSL:
        box = imaplib.IMAP4_SSL(self.host, self.port,
                                timeout=config.get_float("IMAP_TIMEOUT", 30))
        try:
            box.login(self.address, self.password)
        except imaplib.IMAP4.error as exc:
            # The commonest cause by far, and the error Gmail returns is not
            # helpful on its own.
            raise RuntimeError(
                f"IMAP login failed for {self.address}. If this is Gmail, the "
                f"password must be a 16-character App Password, not your normal "
                f"one, and IMAP must be enabled in Gmail settings. ({exc})"
            ) from exc
        box.select(self.folder)
        return box

    def check(self) -> str:
        """One-line health check, for the doctor."""
        if not self.configured:
            return "not configured"
        try:
            box = self._connect()
        except Exception as exc:  # noqa: BLE001
            return f"failed: {exc}"[:200]
        try:
            typ, data = box.search(None, "ALL")
            count = len((data[0] or b"").split()) if typ == "OK" else 0
            return f"connected to {self.host}, {count} messages in {self.folder}"
        finally:
            self._logout(box)

    @staticmethod
    def _logout(box) -> None:
        try:
            box.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            box.logout()
        except Exception:  # noqa: BLE001
            pass

    def poll(self, days: int | None = None,
             max_results: int = 25) -> list[GmailMessage]:
        """New messages since the last poll, oldest first.

        Every message id is recorded, so a message is only ever handled once
        even if the mailbox is re-read.
        """
        if not self.configured:
            log.info("IMAP is not configured; no replies will be noticed")
            return []
        days = days if days is not None else config.get_int("IMAP_LOOKBACK_DAYS", 7)
        since = time.strftime("%d-%b-%Y", time.gmtime(time.time() - days * 86400))

        box = self._connect()
        out: list[GmailMessage] = []
        try:
            typ, data = box.search(None, f'(SINCE "{since}")')
            if typ != "OK":
                return []
            ids = (data[0] or b"").split()[-max_results:]
            for num in ids:
                typ, raw = box.fetch(num, "(RFC822)")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = self._to_message(raw[0][1])
                if msg is None:
                    continue
                # mark_seen returns True the first time it sees a key.
                key = msg.id
                if self.store.seen(f"imap:{self.address}", key):
                    continue
                out.append(msg)
        finally:
            self._logout(box)
        log.info("imap poll", host=self.host, new=len(out))
        return out

    def mark_read(self, message_id: str) -> None:
        """Acknowledge after routing succeeded, so a failed handler can retry."""
        self.store.mark_seen(f"imap:{self.address}", message_id)

    @staticmethod
    def _to_message(raw: bytes) -> GmailMessage | None:
        try:
            parsed = email.message_from_bytes(raw)
        except Exception as exc:  # noqa: BLE001
            log.warn(f"could not parse a message: {exc}")
            return None

        headers = {k.lower(): _decode(v) for k, v in parsed.items()}
        text, html = "", ""
        if parsed.is_multipart():
            for part in parsed.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get_filename():
                    continue
                try:
                    payload = part.get_payload(decode=True) or b""
                    body = payload.decode(part.get_content_charset() or "utf-8",
                                          "replace")
                except Exception:  # noqa: BLE001
                    continue
                if part.get_content_type() == "text/plain" and not text:
                    text = body
                elif part.get_content_type() == "text/html" and not html:
                    html = body
        else:
            try:
                payload = parsed.get_payload(decode=True) or b""
                body = payload.decode(parsed.get_content_charset() or "utf-8",
                                      "replace")
            except Exception:  # noqa: BLE001
                body = ""
            # A single-part message can still be HTML. Treating it as plain
            # text left brands' replies full of tags.
            if parsed.get_content_type() == "text/html":
                html = body
            else:
                text = body

        body_text = text or html_to_text(html)
        stamp = 0.0
        if headers.get("date"):
            try:
                stamp = email.utils.mktime_tz(
                    email.utils.parsedate_tz(headers["date"]))
            except Exception:  # noqa: BLE001
                stamp = 0.0
        # A reply's thread is the message it answers; failing that, the first
        # id in References; failing that, itself.
        refs = headers.get("references", "").split()
        thread = (headers.get("in-reply-to")
                  or (refs[0] if refs else "")
                  or headers.get("message-id", ""))
        return GmailMessage(
            id=headers.get("message-id", "") or __import__("hashlib").sha256(raw).hexdigest(),
            thread_id=thread,
            headers=headers,
            body_text=body_text[:40000],
            snippet=body_text.strip()[:300],
            internal_date=stamp,
        )


def get_inbox(store: Store | None = None) -> ImapBox:
    return ImapBox(store)
