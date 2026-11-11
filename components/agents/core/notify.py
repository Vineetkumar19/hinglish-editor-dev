"""Push notification delivery - the "Hey Vineet, X replied!" channel.

Channels are configured with NOTIFY_CHANNELS (comma separated):
  console  - always available, writes to stderr
  ntfy     - ntfy.sh or a self-hosted server (NTFY_URL, NTFY_TOPIC, NTFY_TOKEN)
  webhook  - generic JSON POST (NOTIFY_WEBHOOK_URL)
  slack    - Slack incoming webhook (SLACK_WEBHOOK_URL)
  discord  - Discord webhook (DISCORD_WEBHOOK_URL)
  email    - send to OPERATOR_EMAIL through the configured mailer
  store    - record in the events table so the dashboard shows it
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import config, http
from .log import get_logger

log = get_logger("notify")

PRIORITY = {"low": 2, "normal": 3, "high": 4, "urgent": 5}


@dataclass
class Notification:
    title: str
    body: str
    priority: str = "normal"
    url: str | None = None
    tags: tuple = ()


class Notifier:
    def __init__(self, store=None, channels: list[str] | None = None):
        self.store = store
        self.channels = channels or config.get_list("NOTIFY_CHANNELS", ["console", "store"])

    def send(self, title: str, body: str, *, priority: str = "normal",
             url: str | None = None, tags: tuple = ()) -> dict:
        n = Notification(title, body, priority, url, tags)
        results = {}
        for ch in self.channels:
            try:
                results[ch] = getattr(self, f"_send_{ch}", self._unknown)(n)
            except Exception as exc:  # noqa: BLE001 - a failed alert must not kill a run
                log.warn(f"notification via {ch} failed: {exc}")
                results[ch] = f"error: {exc}"
        return results

    def _unknown(self, n: Notification) -> str:
        return "unknown channel"

    # -- channels ------------------------------------------------------------
    def _send_console(self, n: Notification) -> str:
        bar = "=" * 60
        print(f"\n{bar}\n  {n.title}\n{bar}\n{n.body}"
              + (f"\n  -> {n.url}" if n.url else "") + f"\n{bar}\n", flush=True)
        return "ok"

    def _send_store(self, n: Notification) -> str:
        if self.store is None:
            return "no store"
        self.store.event("notification", kind_title=n.title, body=n.body,
                         priority=n.priority, url=n.url)
        return "ok"

    def _send_telegram(self, n: Notification) -> str:
        """Post into the agent's own topic in your Telegram group.

        The agent name is read from the notification tags, so a sponsorship
        reply lands in Sponsorship and a job alert lands in Jobs.
        """
        from server.bot import TOPICS, PARENT, get_bot
        from core.telegram import esc
        agent = next((t for t in n.tags
                      if t in TOPICS or t in PARENT), "")
        bot = get_bot(self.store)
        text = f"<b>{esc(n.title)}</b>\n\n{esc(n.body)}"
        if n.url:
            text += f"\n\n{esc(n.url)}"
        return "ok" if bot.say(text, agent=agent) else "no chat bound yet"

    def _send_ntfy(self, n: Notification) -> str:
        base = config.get("NTFY_URL", "https://ntfy.sh").rstrip("/")
        topic = config.require("NTFY_TOPIC")
        headers = {
            "Title": n.title.encode("ascii", "replace").decode(),
            "Priority": str(PRIORITY.get(n.priority, 3)),
            "Content-Type": "text/plain; charset=utf-8",
        }
        if n.tags:
            headers["Tags"] = ",".join(n.tags)
        if n.url:
            headers["Click"] = n.url
        token = config.get("NTFY_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = http.post(f"{base}/{topic}", data=n.body.encode("utf-8"),
                      headers=headers, timeout=15)
        return "ok" if r.ok else f"HTTP {r.status}"

    def _send_webhook(self, n: Notification) -> str:
        url = config.require("NOTIFY_WEBHOOK_URL")
        r = http.post(url, json_body={"title": n.title, "body": n.body,
                                      "priority": n.priority, "url": n.url,
                                      "tags": list(n.tags)}, timeout=15)
        return "ok" if r.ok else f"HTTP {r.status}"

    def _send_slack(self, n: Notification) -> str:
        url = config.require("SLACK_WEBHOOK_URL")
        blocks = [{"type": "header",
                   "text": {"type": "plain_text", "text": n.title[:150]}},
                  {"type": "section",
                   "text": {"type": "mrkdwn", "text": n.body[:2900]}}]
        if n.url:
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": f"<{n.url}|Open>"}})
        r = http.post(url, json_body={"text": f"{n.title}\n{n.body}"[:3000],
                                      "blocks": blocks}, timeout=15)
        return "ok" if r.ok else f"HTTP {r.status}"

    def _send_discord(self, n: Notification) -> str:
        url = config.require("DISCORD_WEBHOOK_URL")
        content = f"**{n.title}**\n{n.body}"[:1900]
        if n.url:
            content += f"\n{n.url}"
        r = http.post(url, json_body={"content": content}, timeout=15)
        return "ok" if r.ok else f"HTTP {r.status}"

    def _send_email(self, n: Notification) -> str:
        from .mailer import Mailer, OutgoingMessage
        to = config.require("OPERATOR_EMAIL")
        m = Mailer(store=self.store)
        m.send(OutgoingMessage(to=to, subject=n.title,
                               body=n.body + (f"\n\n{n.url}" if n.url else ""),
                               tag="notification"), enforce_cap=False)
        return "ok"


_default: Notifier | None = None


def get_notifier(store=None) -> Notifier:
    global _default
    if _default is None:
        from .store import get_store
        _default = Notifier(store=store or get_store())
    return _default


def reset_notifier() -> None:
    global _default
    _default = None


def alert_reply(brand: str, snippet: str, url: str | None = None,
                store=None) -> None:
    """The blueprint's headline alert."""
    operator = config.get("OPERATOR_NAME", "Vineet")
    get_notifier(store).send(
        title=f"{brand} has responded - they are interested!",
        body=f"Hey {operator}, {brand} has responded that they are interested!\n\n"
             f"{snippet[:600]}",
        priority="urgent", url=url, tags=("tada", "incoming_envelope"))
