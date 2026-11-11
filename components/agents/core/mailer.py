"""Outbound email: composition, compliance, volume control and delivery.

Two transports:
  gmail - send through the authorised Gmail account (users.messages.send)
  smtp  - any SMTP server (your own domain, Postmark, SES, Zoho...)

Everything routes through `Mailer.send`, which enforces, in order:
  1. the global DRY_RUN kill switch
  2. the suppression list (anyone who unsubscribed or bounced, ever)
  3. the per-mailbox daily cap
  4. a compliance footer with a real postal address and a working opt-out
  5. List-Unsubscribe + List-Unsubscribe-Post, which is what Gmail and Yahoo
     actually check on bulk mail

There is deliberately no mailbox rotation and no "warmup" that fakes engagement.
Those exist to disguise volume from spam filters; this sends a modest number of
real messages from one authenticated domain instead.
"""
from __future__ import annotations

import email.utils
import mimetypes
import pathlib
import re
import smtplib
import ssl
import textwrap
from dataclasses import dataclass, field
from email.message import EmailMessage

from . import config
from .log import get_logger
from .ratelimit import DailyCap
from .store import Store, get_store, new_id, now

log = get_logger("mailer")

SUPPRESSION_NS = "suppressed"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")

ROLE_PREFIXES = {
    "abuse", "postmaster", "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "bounce", "bounces", "unsubscribe", "spam", "security",
}


def valid_email(addr: str) -> bool:
    addr = (addr or "").strip()
    if not EMAIL_RE.match(addr) or len(addr) > 254:
        return False
    local = addr.split("@", 1)[0].lower()
    return local not in ROLE_PREFIXES


class SendBlocked(RuntimeError):
    """Raised when a policy check refuses a send."""


@dataclass
class Attachment:
    filename: str
    content: bytes
    mime: str = ""


@dataclass
class OutgoingMessage:
    to: str
    subject: str
    body: str
    from_addr: str = ""
    from_name: str = ""
    reply_to: str = ""
    cc: str = ""
    in_reply_to: str = ""
    references: str = ""
    gmail_thread_id: str = ""
    attachments: list = field(default_factory=list)
    tag: str = ""
    include_footer: bool = True
    unsubscribe_token: str = ""
    idempotency_key: str = ""


class SuppressionList:
    """Anyone here is never contacted again, for any reason, by any agent."""

    def __init__(self, store: Store | None = None):
        self.store = store or get_store()

    def add(self, addr: str, reason: str = "unsubscribe") -> None:
        addr = addr.strip().lower()
        self.store.kv_set(SUPPRESSION_NS, addr, {"reason": reason, "ts": now()})
        log.info("address suppressed", addr=addr, reason=reason)

    def contains(self, addr: str) -> bool:
        return self.store.kv_get(SUPPRESSION_NS, (addr or "").strip().lower()) is not None

    def all(self) -> dict:
        return self.store.kv_list(SUPPRESSION_NS)

    def remove(self, addr: str) -> None:
        self.store.kv_delete(SUPPRESSION_NS, (addr or "").strip().lower())


def unsubscribe_token(addr: str) -> str:
    import hashlib
    secret = config.get("UNSUBSCRIBE_SECRET", "change-me")
    return hashlib.sha256(f"{secret}:{addr.lower()}".encode()).hexdigest()[:24]


def _reachable_base() -> str:
    """The public URL, or empty when it is only reachable from this machine."""
    base = config.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base or any(h in base for h in
                       ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
        return ""
    return base


def unsubscribe_url(addr: str) -> str:
    base = _reachable_base() or "http://localhost:8080"
    return (f"{base}/unsubscribe?e={email.utils.quote(addr)}"
            f"&t={unsubscribe_token(addr)}")


def unsubscribe_link(addr: str) -> str:
    """What to put in front of the recipient.

    A link to localhost is worse than no link: the brand cannot open it, and an
    unsubscribe that visibly does not work reads as a spammer's footer. Until
    the dashboard has a public address, ask them to reply instead - which is a
    real unsubscribe route, because replies are read.
    """
    if _reachable_base():
        return f"Unsubscribe: {unsubscribe_url(addr)}"
    return "reply with 'unsubscribe'."


# Left in the .env.example for people to replace. If it is still here, it is
# not an address, and printing it at the bottom of a cold email is worse than
# printing nothing.
PLACEHOLDER_POSTAL = {"street, city, state, india", "your street", "street",
                      "city, state", "your address here", "your city"}


def compliance_footer(addr: str) -> str:
    sender = config.get("SENDER_NAME", config.get("OPERATOR_NAME", "Vineet"))
    postal = config.get("SENDER_POSTAL_ADDRESS", "").strip()
    lines = ["", "--", sender]
    if postal and postal.lower() not in PLACEHOLDER_POSTAL:
        lines.append(postal)
    lines.append(f"Don't want to hear from me again? {unsubscribe_link(addr)}")
    return "\n".join(lines)


class Mailer:
    def __init__(self, store: Store | None = None, transport: str | None = None,
                 gmail=None):
        self.store = store or get_store()
        self.transport = (transport or config.get("MAIL_TRANSPORT", "smtp")).lower()
        self.suppression = SuppressionList(self.store)
        self.cap = DailyCap(self.store)
        self._gmail = gmail
        self.from_addr = config.get("SENDER_EMAIL", "")
        self.from_name = config.get("SENDER_NAME", config.get("OPERATOR_NAME", ""))
        self.daily_cap = config.get_int("DAILY_SEND_CAP", 40)

    @property
    def gmail(self):
        if self._gmail is None:
            from .gmail import GmailClient
            self._gmail = GmailClient(self.store)
        return self._gmail

    # -- composition ---------------------------------------------------------
    def build(self, msg: OutgoingMessage) -> EmailMessage:
        m = EmailMessage()
        frm = msg.from_addr or self.from_addr
        if not frm:
            raise SendBlocked("SENDER_EMAIL is not configured")
        name = msg.from_name or self.from_name
        m["From"] = email.utils.formataddr((name, frm)) if name else frm
        m["To"] = msg.to
        if msg.cc:
            m["Cc"] = msg.cc
        m["Subject"] = msg.subject
        m["Date"] = email.utils.formatdate(localtime=True)
        domain = frm.split("@", 1)[-1]
        m["Message-ID"] = email.utils.make_msgid(domain=domain)
        if msg.reply_to:
            m["Reply-To"] = msg.reply_to
        if msg.in_reply_to:
            m["In-Reply-To"] = msg.in_reply_to
            refs = (msg.references + " " + msg.in_reply_to).strip()
            m["References"] = refs
        if msg.include_footer:
            # The mailto form always works; the URL is only offered when the
            # dashboard is actually reachable from outside this machine.
            parts = [f"<mailto:{frm}?subject=unsubscribe>"]
            if _reachable_base():
                parts.insert(0, f"<{unsubscribe_url(msg.to)}>")
            m["List-Unsubscribe"] = ", ".join(parts)
            m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        m["X-Agent"] = msg.tag or "agentsuite"
        m["Auto-Submitted"] = "auto-generated"

        body = msg.body.rstrip()
        if msg.include_footer:
            body += "\n" + compliance_footer(msg.to)
        m.set_content(body)

        for att in msg.attachments:
            mime = att.mime or (mimetypes.guess_type(att.filename)[0]
                                or "application/octet-stream")
            maintype, _, subtype = mime.partition("/")
            m.add_attachment(att.content, maintype=maintype,
                             subtype=subtype or "octet-stream",
                             filename=att.filename)
        return m

    # -- policy --------------------------------------------------------------
    def preflight(self, msg: OutgoingMessage, enforce_cap: bool = True) -> None:
        if not valid_email(msg.to):
            raise SendBlocked(f"{msg.to!r} is not a deliverable personal address")
        if self.suppression.contains(msg.to):
            raise SendBlocked(f"{msg.to} is on the suppression list")
        if not msg.subject.strip():
            raise SendBlocked("refusing to send an email with no subject")
        if len(msg.body.strip()) < 40:
            raise SendBlocked("refusing to send a near-empty body")
        mailbox = msg.from_addr or self.from_addr
        if enforce_cap and not self.cap.check_and_increment(mailbox, self.daily_cap):
            raise SendBlocked(
                f"daily cap of {self.daily_cap} reached for {mailbox}. "
                f"This protects sender reputation - raise DAILY_SEND_CAP only if "
                f"the domain is warm and bounce rate is under 2%.")

    # -- delivery ------------------------------------------------------------
    def send(self, msg: OutgoingMessage, enforce_cap: bool = True,
             dry_run: bool | None = None) -> dict:
        dry = config.dry_run() if dry_run is None else dry_run
        send_key = f"{'dry' if dry else 'live'}:{msg.idempotency_key}"
        if msg.idempotency_key:
            previous = self.store.kv_get("send_receipts", send_key)
            if previous:
                if previous.get("status") == "sent":
                    return previous["result"]
                raise SendBlocked("A previous delivery attempt has no confirmed receipt; "
                                  "check the mailbox before retrying this message")
        self.preflight(msg, enforce_cap=enforce_cap and not dry)
        # One contact owner across initial outreach agents. Replies remain on
        # their existing threads; a second role cannot start competing pitches.
        outreach_roles = {'community', 'sponsorship', 'video_client', 'fullstack_sales', 'saas_sales'}
        if not dry and msg.tag in outreach_roles and msg.include_footer and not msg.in_reply_to:
            import json
            identity = msg.to.strip().lower()
            with self.store.tx():
                historical = self.store.one(
                    'SELECT agent FROM send_log WHERE lower(addr_to)=? AND agent!=? LIMIT 1',
                    (identity, msg.tag))
                if historical and historical['agent'] in outreach_roles:
                    raise SendBlocked('Another agent already contacted this person; review the existing conversation')
                self.store.execute(
                    'INSERT INTO kv(namespace,k,value_json,updated_at) VALUES(?,?,?,?) ON CONFLICT(namespace,k) DO NOTHING',
                    ('contact_outreach_owner', identity, json.dumps({'agent': msg.tag}), now()))
                owner = self.store.kv_get('contact_outreach_owner', identity)
                if owner['agent'] != msg.tag:
                    raise SendBlocked('Another agent owns this contact attempt; reconcile it before new outreach')
        built = self.build(msg)
        rfc_id = built["Message-ID"]
        if msg.idempotency_key:
            import json
            with self.store.tx():
                claimed = self.store.execute(
                    "INSERT INTO kv(namespace,k,value_json,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(namespace,k) DO NOTHING",
                    ("send_receipts", send_key, json.dumps({"status": "sending", "rfc_id": rfc_id}), now()))
            if claimed.rowcount != 1:
                raise SendBlocked("This delivery is already being processed; check its receipt before retrying")

        if dry:
            log.info("DRY RUN - not sending", to=msg.to, subject=msg.subject)
            if config.get_bool("DRY_RUN_PRINT", True):
                print("\n" + "-" * 60 + f"\nDRY RUN: would send to {msg.to}\n"
                      + "-" * 60 + f"\nSubject: {msg.subject}\n\n"
                      + built.get_content()[:1500] + "\n" + "-" * 60 + "\n",
                      flush=True)
            result = {"ok": True, "dry_run": True, "message_id": rfc_id,
                      "provider_id": "dryrun-" + new_id()}
        elif self.transport == "gmail":
            data = self.gmail.send_raw(built.as_bytes(),
                                       thread_id=msg.gmail_thread_id or None)
            result = {"ok": True, "dry_run": False, "message_id": rfc_id,
                      "provider_id": data.get("id", ""),
                      "thread_id": data.get("threadId", "")}
        else:
            result = self._send_smtp(built, msg)

        if msg.idempotency_key:
            self.store.kv_set("send_receipts", send_key,
                              {"status": "sent", "result": result})

        if not dry:
            self.store.upsert("send_log", ("id",), {
                "id": new_id("sl"), "ts": now(),
                "mailbox": msg.from_addr or self.from_addr, "addr_to": msg.to,
                "agent": msg.tag, "thread_id": msg.gmail_thread_id or "",
            })
        self.store.event("email_sent", msg.tag, msg.gmail_thread_id or "",
                         to=msg.to, subject=msg.subject, dry_run=result["dry_run"])
        log.info("email sent", to=msg.to, subject=msg.subject[:60],
                 dry_run=result["dry_run"])
        return result

    def _send_smtp(self, built: EmailMessage, msg: OutgoingMessage) -> dict:
        host = config.require("SMTP_HOST")
        port = config.get_int("SMTP_PORT", 587)
        user = config.get("SMTP_USER", "")
        password = config.get("SMTP_PASSWORD", "")
        use_ssl = config.get_bool("SMTP_SSL", False)
        starttls = config.get_bool("SMTP_STARTTLS", not use_ssl)
        timeout = config.get_float("SMTP_TIMEOUT", 30)

        ctx = ssl.create_default_context()
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        try:
            server.ehlo()
            if starttls and not use_ssl:
                try:
                    server.starttls(context=ctx)
                    server.ehlo()
                except smtplib.SMTPNotSupportedError:
                    if config.get_bool("SMTP_REQUIRE_TLS", True):
                        raise
                    log.warn("SMTP server does not support STARTTLS")
            if user:
                server.login(user, password)
            try:
                refused = server.send_message(built)
            except smtplib.SMTPRecipientsRefused as exc:
                # Every recipient was rejected, so smtplib raises rather than
                # returning the dict. Record the bounces either way - an address
                # that hard-bounces must never be tried again.
                for addr, (code, reason) in (exc.recipients or {}).items():
                    self.suppression.add(
                        addr, reason=f"smtp {code}: "
                                     f"{reason.decode() if isinstance(reason, bytes) else reason}")
                raise SendBlocked(
                    f"all recipients refused: {exc.recipients}") from exc
            except smtplib.SMTPResponseException as exc:
                raise SendBlocked(
                    f"SMTP error {exc.smtp_code}: "
                    f"{exc.smtp_error.decode() if isinstance(exc.smtp_error, bytes) else exc.smtp_error}"
                ) from exc
        finally:
            try:
                server.quit()
            except Exception:  # noqa: BLE001
                server.close()
        if refused:
            for addr, (code, reason) in refused.items():
                self.suppression.add(addr, reason=f"smtp {code}: {reason}")
            raise SendBlocked(f"recipients refused: {refused}")
        return {"ok": True, "dry_run": False, "message_id": built["Message-ID"],
                "provider_id": built["Message-ID"]}

    # -- bookkeeping ---------------------------------------------------------
    def record(self, thread_id: str, agent: str, direction: str, msg: OutgoingMessage,
               result: dict) -> None:
        self.store.upsert("messages", ("id",), {
            "id": new_id("ms"), "thread_id": thread_id, "agent": agent,
            "direction": direction, "provider_id": result.get("provider_id", ""),
            "rfc_id": result.get("message_id", ""), "in_reply_to": msg.in_reply_to,
            "addr_from": msg.from_addr or self.from_addr, "addr_to": msg.to,
            "subject": msg.subject, "body": msg.body, "intent": "", "ts": now(),
        })

    def sent_today(self, mailbox: str | None = None) -> int:
        return self.cap.count(mailbox or self.from_addr)

    def bounce_rate(self, window_days: int = 30) -> float:
        since = now() - window_days * 86400
        sent = self.store.one("SELECT COUNT(*) AS c FROM send_log WHERE ts>?", (since,))
        total = (sent or {}).get("c", 0) or 0
        bounced = sum(1 for v in self.suppression.all().values()
                      if str(v.get("reason", "")).startswith("smtp")
                      and v.get("ts", 0) > since)
        return (bounced / total) if total else 0.0


def wrap(text: str, width: int = 78) -> str:
    out = []
    for para in text.split("\n\n"):
        out.append("\n".join(textwrap.wrap(para.strip(), width=width))
                   if len(para) > width else para.strip())
    return "\n\n".join(out)
