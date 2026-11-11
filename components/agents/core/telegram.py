"""Telegram Bot API client - dependency free, standard library only.

Speaks the real Bot API over HTTPS: long polling for updates, messages with
inline keyboards, file uploads as multipart/form-data, and forum topic
creation. Nothing here needs python-telegram-bot or requests.

Two things about Telegram that shape the design of the bot:

  * A bot cannot create a group. The Bot API has no such method, by design -
    a bot can only ever be *added* to a chat by a person. What it can do is
    create topics inside a group that already has Topics turned on, which is
    how one group ends up with one thread per agent.

  * Updates arrive by long polling. `get_updates` holds the connection open
    until something happens or the timeout expires, so the bot is not
    hammering the API in a loop.
"""
from __future__ import annotations

import json
import mimetypes
import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import config, http
from .log import get_logger

log = get_logger("telegram")

DEFAULT_API_BASE = "https://api.telegram.org"

# Telegram rejects any message over 4096 UTF-16 code units.
MAX_MESSAGE = 4096


class TelegramError(RuntimeError):
    """The API returned ok:false."""

    def __init__(self, method: str, code: int, description: str):
        self.method, self.code, self.description = method, code, description
        super().__init__(f"{method} failed ({code}): {description}")

    @property
    def is_fatal(self) -> bool:
        """Errors that retrying will never fix - a bad token, a kicked bot."""
        d = self.description.lower()
        return (self.code in (401, 403)
                or "unauthorized" in d or "chat not found" in d
                or "bot was kicked" in d or "bot was blocked" in d)


# ---------------------------------------------------------------------------
# message helpers
# ---------------------------------------------------------------------------
def esc(text: Any) -> str:
    """Escape for Telegram's HTML parse mode."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def split_message(text: str, limit: int = MAX_MESSAGE) -> list[str]:
    """Break a long message on line boundaries, never mid-line if avoidable."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:  # a single monstrous line
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


@dataclass
class Button:
    """One inline keyboard button. `data` is what comes back on a tap."""
    text: str
    data: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        if self.url:
            return {"text": self.text, "url": self.url}
        # Telegram caps callback_data at 64 bytes.
        return {"text": self.text, "callback_data": self.data[:64]}


def keyboard(rows: Iterable[Iterable[Button]]) -> dict:
    return {"inline_keyboard": [[b.to_dict() for b in row] for row in rows]}


@dataclass
class Update:
    """One incoming update, flattened to the handful of fields a bot needs."""
    raw: dict = field(default_factory=dict)

    @property
    def id(self) -> int:
        return int(self.raw.get("update_id", 0))

    @property
    def message(self) -> dict:
        return (self.raw.get("message") or self.raw.get("edited_message")
                or self.raw.get("channel_post") or {})

    @property
    def callback(self) -> dict:
        return self.raw.get("callback_query") or {}

    @property
    def is_callback(self) -> bool:
        return bool(self.callback)

    @property
    def text(self) -> str:
        if self.is_callback:
            return str(self.callback.get("data", ""))
        return str(self.message.get("text", "") or self.message.get("caption", ""))

    @property
    def chat_id(self) -> int | None:
        msg = self.callback.get("message", {}) if self.is_callback else self.message
        chat = msg.get("chat") or {}
        return chat.get("id")

    @property
    def chat_type(self) -> str:
        msg = self.callback.get("message", {}) if self.is_callback else self.message
        return str((msg.get("chat") or {}).get("type", ""))

    @property
    def thread_id(self) -> int | None:
        """The forum topic this arrived in, if any."""
        msg = self.callback.get("message", {}) if self.is_callback else self.message
        return msg.get("message_thread_id")

    @property
    def message_id(self) -> int | None:
        msg = self.callback.get("message", {}) if self.is_callback else self.message
        return msg.get("message_id")

    @property
    def from_id(self) -> int | None:
        who = self.callback.get("from") if self.is_callback else self.message.get("from")
        return (who or {}).get("id")

    @property
    def from_name(self) -> str:
        who = (self.callback.get("from") if self.is_callback
               else self.message.get("from")) or {}
        name = " ".join(x for x in (who.get("first_name"), who.get("last_name")) if x)
        return name or who.get("username", "") or str(who.get("id", ""))

    @property
    def callback_id(self) -> str:
        return str(self.callback.get("id", ""))

    def command(self) -> tuple[str, str]:
        """Split "/run jobs" into ("run", "jobs"). Strips any @botname suffix."""
        text = self.text.strip()
        if not text.startswith("/"):
            return "", text
        head, _, rest = text.partition(" ")
        cmd = head[1:].split("@", 1)[0].lower()
        return cmd, rest.strip()


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------
class Telegram:
    def __init__(self, token: str | None = None, api_base: str | None = None,
                 timeout: float = 35.0):
        self.token = (token or config.get("TELEGRAM_BOT_TOKEN", "")).strip()
        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is not set. Message @BotFather on Telegram, "
                "send /newbot, and put the token it gives you in your .env file.")
        self.api_base = (api_base or config.get("TELEGRAM_API_BASE",
                                                DEFAULT_API_BASE)).rstrip("/")
        self.timeout = timeout

    def _url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.token}/{method}"

    def call(self, method: str, params: dict | None = None,
             *, timeout: float | None = None, retries: int = 2) -> Any:
        body = {k: v for k, v in (params or {}).items() if v is not None}
        # Nested structures have to be sent as JSON strings in form encoding.
        for key, value in list(body.items()):
            if isinstance(value, (dict, list)):
                body[key] = json.dumps(value)
        resp = http.post_form(self._url(method), body,
                              timeout=timeout or self.timeout, retries=retries,
                              allow_status={400, 401, 403, 404, 409})
        try:
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise TelegramError(method, resp.status, resp.text[:200]) from exc
        if not payload.get("ok"):
            raise TelegramError(method, int(payload.get("error_code", resp.status)),
                                str(payload.get("description", "unknown error")))
        return payload.get("result")

    # -- identity -----------------------------------------------------------
    def get_me(self) -> dict:
        return self.call("getMe")

    def set_my_commands(self, commands: list[tuple[str, str]]) -> Any:
        return self.call("setMyCommands", {
            "commands": [{"command": c, "description": d} for c, d in commands]})

    def get_chat(self, chat_id) -> dict:
        return self.call("getChat", {"chat_id": chat_id})

    # -- receiving ----------------------------------------------------------
    def get_updates(self, offset: int | None = None, timeout: int = 25,
                    limit: int = 50) -> list[Update]:
        """Long poll. Blocks up to `timeout` seconds waiting for activity."""
        result = self.call("getUpdates",
                           {"offset": offset, "timeout": timeout, "limit": limit},
                           timeout=timeout + 15, retries=0)
        return [Update(u) for u in (result or [])]

    def delete_webhook(self, drop_pending: bool = False) -> Any:
        """Polling and webhooks are mutually exclusive; clear any stale webhook."""
        return self.call("deleteWebhook", {"drop_pending_updates": drop_pending})

    # -- sending ------------------------------------------------------------
    def send_message(self, chat_id, text: str, *, thread_id=None, buttons=None,
                     parse_mode: str = "HTML", preview: bool = False,
                     silent: bool = False) -> dict:
        """Send text, splitting anything over Telegram's 4096 character limit.

        Buttons are attached to the final chunk so they sit under the whole
        message rather than in the middle of it.
        """
        chunks = split_message(text)
        sent: dict = {}
        for i, chunk in enumerate(chunks):
            last = i == len(chunks) - 1
            sent = self.call("sendMessage", {
                "chat_id": chat_id,
                "message_thread_id": thread_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "link_preview_options": json.dumps({"is_disabled": not preview}),
                "disable_notification": silent,
                "reply_markup": buttons if (buttons and last) else None,
            })
        return sent

    def edit_message_text(self, chat_id, message_id, text: str, *, buttons=None,
                          parse_mode: str = "HTML") -> Any:
        return self.call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": split_message(text)[0], "parse_mode": parse_mode,
            "reply_markup": buttons})

    def answer_callback(self, callback_id: str, text: str = "",
                        alert: bool = False) -> Any:
        """Stops the button's loading spinner. Telegram requires this."""
        return self.call("answerCallbackQuery", {
            "callback_query_id": callback_id, "text": text[:200],
            "show_alert": alert})

    def send_document(self, chat_id, path, *, caption: str = "", thread_id=None,
                      parse_mode: str = "HTML") -> dict:
        p = pathlib.Path(path)
        if not p.exists():
            raise FileNotFoundError(f"cannot send {p}: file does not exist")
        fields = {"chat_id": str(chat_id), "caption": caption[:1024],
                  "parse_mode": parse_mode}
        if thread_id is not None:
            fields["message_thread_id"] = str(thread_id)
        body, content_type = _multipart(fields, "document", p)
        resp = http.post(self._url("sendDocument"), data=body,
                         headers={"Content-Type": content_type},
                         timeout=max(self.timeout, 120), retries=1,
                         allow_status={400, 401, 403, 404})
        payload = resp.json()
        if not payload.get("ok"):
            raise TelegramError("sendDocument",
                                int(payload.get("error_code", resp.status)),
                                str(payload.get("description", "")))
        return payload.get("result")

    # -- forum topics -------------------------------------------------------
    def create_forum_topic(self, chat_id, name: str,
                           icon_color: int | None = None) -> dict:
        """Create a topic in a group that has Topics enabled.

        Requires the bot to be an administrator with manage_topics rights.
        This is the closest thing to "the bot makes its own groups" that the
        Bot API allows.
        """
        return self.call("createForumTopic", {
            "chat_id": chat_id, "name": name[:128], "icon_color": icon_color})

    def edit_forum_topic(self, chat_id, thread_id, name: str) -> Any:
        return self.call("editForumTopic", {
            "chat_id": chat_id, "message_thread_id": thread_id, "name": name[:128]})


def _multipart(fields: dict, file_field: str, path: pathlib.Path) -> tuple[bytes, str]:
    """Build a multipart/form-data body. urllib has no such thing built in."""
    boundary = f"----agentsuite{uuid.uuid4().hex}"
    sep = f"--{boundary}\r\n".encode()
    out = bytearray()
    for key, value in fields.items():
        out += sep
        out += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        out += f"{value}\r\n".encode("utf-8")
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    out += sep
    out += (f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{path.name}"\r\n').encode("utf-8")
    out += f"Content-Type: {ctype}\r\n\r\n".encode()
    out += path.read_bytes()
    out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"
