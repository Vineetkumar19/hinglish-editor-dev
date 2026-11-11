"""Telegram bot - run and supervise all four agents from your phone.

The terminal is a bad control surface for something that runs all day and
needs a yes/no from you at unpredictable moments. Telegram is a good one: it
is already on your phone, it keeps history forever, and a button is a much
better approval gate than remembering an approval id.

Layout
------
One group with Topics turned on, and one topic per agent:

    Sponsorship    - brand outreach and replies
    Video Clients  - editing client outreach and replies
    Dev Sales      - development enquiries and quotes
    Jobs           - job hunting, resumes and interviews

A bot cannot create a group - the Bot API has no such method, because a bot
must always be added by a person. It can create the topics, so you make the
group once and `/start` does the rest.

Safety
------
Every outbound email, quote and job application still stops at an approval.
The buttons in Telegram are the same approval gate as the dashboard and the
CLI, not a way around it. The bot only obeys its owner: the first person to
send /start is remembered as the owner, and everyone else is ignored.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import threading
import time
import traceback

from core import config
from core.hitl import ApprovalQueue
from core.log import get_logger
from core.store import get_store, now
from core.telegram import Button, Telegram, TelegramError, esc, keyboard

log = get_logger("bot")

KV = "telegram"

# Agent -> (topic title, one-line description). Sub-flows share their parent's
# topic so a quote lands next to the enquiry that produced it.
TOPICS: dict[str, tuple[str, str]] = {
    "community": ("Community", "disclosed public discussion drafts"),
    "sponsorship": ("Sponsorship", "brand and sponsorship outreach"),
    "video_client": ("Video Clients", "video editing client outreach"),
    "fullstack_sales": ("Dev Sales", "development enquiries and quotes"),
    "job_hunter": ("Jobs", "job hunting, resumes and interviews"),
    "saas_sales": ("Product launch", "telling people about your SaaS product"),
}

PARENT = {
    "job_hunter_application": "job_hunter",
    "job_hunter_booking": "job_hunter",
    "sponsorship_reply": "sponsorship",
    "video_client_reply": "video_client",
    "fullstack_sales_reply": "fullstack_sales",
    "fullstack_sales_quote": "fullstack_sales",
    "job_hunter_interview": "job_hunter",
}

COMMANDS = [
    ("start", "Set up the group and create the four topics"),
    ("status", "What each agent is doing and what is waiting on you"),
    ("pending", "Everything waiting for your approval"),
    ("run", "Run an agent now, e.g. /run jobs"),
    ("jobs", "Jobs found recently"),
    ("exp", "Set your years of experience, e.g. /exp 1"),
    ("roles", "Choose which kinds of job to look for"),
    ("leads", "Leads found recently"),
    ("brands", "Sponsorship pipeline - who is left, who is done"),
    ("discover", "Search the web for new sponsors and programmes"),
    ("learned", "What the agent has worked out from your decisions"),
    ("why", "Why something scored the way it did, e.g. /why nakpro.com"),
    ("learned", "The rules each agent has taught itself from your decisions"),
    ("mediakit", "What is still missing from your creator profile"),
    ("resume", "Send the tailored resume for a job"),
    ("doctor", "Check the setup is healthy"),
    ("help", "What the bot can do"),
]

# The short name shown when the bot suggests how to run something.
SHORT = {"community": "community", "sponsorship": "sponsorship", "video_client": "video",
         "fullstack_sales": "dev", "job_hunter": "jobs",
         "saas_sales": "product"}

# Friendly names you can type instead of the internal agent names.
ALIASES = {
    "community": "community", "promoter": "community",
    "jobs": "job_hunter", "job": "job_hunter", "job_hunter": "job_hunter",
    "sponsor": "sponsorship", "sponsorship": "sponsorship",
    "video": "video_client", "video_client": "video_client",
    "dev": "fullstack_sales", "sales": "fullstack_sales",
    "fullstack": "fullstack_sales", "fullstack_sales": "fullstack_sales",
    "product": "saas_sales", "saas": "saas_sales", "launch": "saas_sales",
    "saas_sales": "saas_sales",
}


def _persist_env(key: str, value: str) -> None:
    """Change a setting for this process AND for the next restart.

    Settings you change from your phone should not evaporate when the bot is
    restarted, so the .env file is rewritten too. The key is replaced in place
    if it is there, appended if it is not.
    """
    os.environ[key] = value
    path = config.ROOT / ".env"
    line = f"{key}={value}"
    try:
        if not path.exists():
            path.write_text(line + "\n", encoding="utf-8")
            return
        out, replaced = [], False
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.split("=", 1)[0].strip().lstrip("# ") == key:
                if not replaced:
                    out.append(line)
                    replaced = True
                continue
            out.append(raw)
        if not replaced:
            out.append(line)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    except OSError as exc:
        log.warn(f"could not persist {key} to .env: {exc}")


def _fmt_age(ts) -> str:
    try:
        seconds = max(0, time.time() - float(ts))
    except (TypeError, ValueError):
        return ""
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{int(seconds // size)}{unit} ago"
    return "just now"


class Bot:
    def __init__(self, store=None, telegram=None, queue=None):
        self.store = store or get_store()
        self.tg = telegram or Telegram()
        self.queue = queue or ApprovalQueue(self.store)
        self._running: dict[str, threading.Thread] = {}
        self._workers: list[threading.Thread] = []
        self._stop = threading.Event()

    def join_workers(self, timeout: float = 10.0) -> None:
        """Wait for background work - resuming a graph, running an agent."""
        deadline = time.time() + timeout
        for worker in list(self._workers) + list(self._running.values()):
            worker.join(max(0.0, deadline - time.time()))
        self._workers = [w for w in self._workers if w.is_alive()]

    # -- persisted settings --------------------------------------------------
    def _get(self, key, default=None):
        value = self.store.kv_get(KV, key)
        return default if value is None else value

    def _set(self, key, value) -> None:
        self.store.kv_set(KV, key, value)

    @property
    def chat_id(self):
        return self._get("chat_id")

    @property
    def topics(self) -> dict:
        return self._get("topics", {}) or {}

    @property
    def owner_id(self):
        configured = config.get("TELEGRAM_OWNER_ID", "").strip()
        if configured:
            try:
                return int(configured)
            except ValueError:
                log.warn(f"TELEGRAM_OWNER_ID is not a number: {configured!r}")
        return self._get("owner_id")

    # -- sending -------------------------------------------------------------
    def topic_for(self, agent: str):
        """The thread id for an agent's topic, or None to post in the group."""
        return self.topics.get(PARENT.get(agent, agent))

    def say(self, text: str, *, agent: str | None = None, chat_id=None,
            thread_id=None, buttons=None):
        target = chat_id or self.chat_id
        if target is None:
            log.warn("no chat bound yet; send /start in your group first")
            return None
        if thread_id is None and agent:
            thread_id = self.topic_for(agent)
        try:
            return self.tg.send_message(target, text, thread_id=thread_id,
                                        buttons=buttons)
        except TelegramError as exc:
            # A topic can be deleted from under us. Fall back to the group
            # itself rather than dropping the message on the floor.
            if thread_id is not None and "thread not found" in exc.description.lower():
                return self.tg.send_message(target, text, buttons=buttons)
            log.warn(f"telegram send failed: {exc}")
            return None

    def send_file(self, path, caption: str = "", *, agent: str | None = None,
                  chat_id=None):
        target = chat_id or self.chat_id
        if target is None:
            return None
        try:
            return self.tg.send_document(target, path, caption=caption,
                                         thread_id=self.topic_for(agent or ""))
        except (TelegramError, FileNotFoundError) as exc:
            log.warn(f"could not send {path}: {exc}")
            self.say(f"Could not attach <code>{esc(pathlib.Path(path).name)}</code>: "
                     f"{esc(exc)}", agent=agent)
            return None

    # -- setup ---------------------------------------------------------------
    def setup(self, chat_id, actor_id=None) -> str:
        """Bind this chat and create one topic per agent."""
        self._set("chat_id", chat_id)
        if actor_id and not self._get("owner_id"):
            self._set("owner_id", actor_id)
            log.info(f"owner claimed: {actor_id}")

        try:
            self.tg.set_my_commands(COMMANDS)
        except TelegramError:
            pass

        try:
            chat = self.tg.get_chat(chat_id)
        except TelegramError as exc:
            return f"Could not read this chat: {esc(exc.description)}"

        if not chat.get("is_forum"):
            return (
                "This group does not have <b>Topics</b> turned on, so I cannot "
                "make a topic per agent.\n\n"
                "Open the group, go to <b>Edit -> Topics</b> and switch it on, "
                "then send /start again.\n\n"
                "Everything still works without topics - all four agents will "
                "just share this one chat.")

        created, existing = [], self.topics
        topics = dict(existing)
        for agent, (title, _desc) in TOPICS.items():
            if agent in topics:
                continue
            try:
                topic = self.tg.create_forum_topic(chat_id, title)
            except TelegramError as exc:
                return (f"I could not create the <b>{esc(title)}</b> topic: "
                        f"{esc(exc.description)}\n\nMake me an administrator of "
                        f"this group with the <b>Manage Topics</b> permission, "
                        f"then send /start again.")
            topics[agent] = topic["message_thread_id"]
            created.append(title)
        self._set("topics", topics)

        for agent, (title, desc) in TOPICS.items():
            if title in created:
                self.say(f"<b>{esc(title)}</b>\nThis topic is for {esc(desc)}. "
                         f"Run it with <code>/run {agent}</code>.", agent=agent)

        if not created:
            return "Already set up. All four topics are there."
        return ("Set up. I created these topics: <b>"
                + "</b>, <b>".join(esc(c) for c in created) + "</b>.\n\n"
                "Anything needing your approval will appear in its own topic "
                "with Approve and Reject buttons. Send /help to see the rest.")

    # -- authorisation -------------------------------------------------------
    def authorised(self, update) -> bool:
        owner = self.owner_id
        if owner is None:
            return True  # nobody has claimed the bot yet
        return update.from_id == owner

    # -- command handling ----------------------------------------------------
    def handle(self, update) -> None:
        try:
            if update.is_callback:
                return self._handle_callback(update)
            return self._handle_message(update)
        except Exception as exc:  # noqa: BLE001 - one bad update must not stop the bot
            log.error(f"update failed: {exc}\n{traceback.format_exc()}")
            try:
                self.say(f"Something went wrong handling that: {esc(exc)}",
                         chat_id=update.chat_id, thread_id=update.thread_id)
            except Exception:  # noqa: BLE001
                pass

    def _handle_message(self, update) -> None:
        cmd, rest = update.command()
        if not cmd:
            return
        if cmd == "start":
            reply = self.setup(update.chat_id, update.from_id)
            return self._reply(update, reply)
        if not self.authorised(update):
            log.warn(f"ignoring {cmd} from {update.from_id} ({update.from_name})")
            return
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            return self._reply(update, f"I do not know <code>/{esc(cmd)}</code>. "
                                       f"Send /help for the list.")
        return handler(update, rest)

    def _reply(self, update, text: str, buttons=None) -> None:
        self.say(text, chat_id=update.chat_id, thread_id=update.thread_id,
                 buttons=buttons)

    # -- commands ------------------------------------------------------------
    def cmd_help(self, update, rest) -> None:
        lines = ["<b>What I can do</b>", ""]
        lines += [f"/{c} - {esc(d)}" for c, d in COMMANDS]
        lines += ["", "<b>Agent names</b> for /run:", ""]
        lines += [f"<code>{a}</code> - {esc(d)}" for a, (_t, d) in TOPICS.items()]
        lines += ["", "Nothing is ever sent without you tapping <b>Approve</b>."]
        self._reply(update, "\n".join(lines))

    def cmd_id(self, update, rest) -> None:
        self._reply(update,
                    f"chat id: <code>{update.chat_id}</code>\n"
                    f"your user id: <code>{update.from_id}</code>\n"
                    f"topic id: <code>{update.thread_id}</code>")

    def cmd_status(self, update, rest) -> None:
        pending = self.queue.pending(limit=200)
        by_agent: dict[str, int] = {}
        for row in pending:
            key = PARENT.get(row["agent"], row["agent"])
            by_agent[key] = by_agent.get(key, 0) + 1

        lines = ["<b>Status</b>", ""]
        for agent, (title, _d) in TOPICS.items():
            waiting = by_agent.get(agent, 0)
            running = agent in self._running and self._running[agent].is_alive()
            state = ("running now" if running
                     else f"{waiting} waiting on you" if waiting
                     else "idle")
            lines.append(f"<b>{esc(title)}</b> - {state}")

        try:
            from core.mailer import Mailer
            mailer = Mailer(self.store)
            lines += ["", f"emails bounced: {mailer.bounce_rate():.1%}",
                      f"addresses suppressed: {len(mailer.suppression.all())}"]
        except Exception:  # noqa: BLE001
            pass
        if config.get_bool("DRY_RUN", True):
            lines += ["", "<b>DRY RUN is on</b> - nothing actually leaves your "
                          "machine. Turn it off in .env when you are ready."]
        lines += ["", "/pending to see what needs a decision."]
        self._reply(update, "\n".join(lines))

    LEARN_AGENTS = {"sponsorship": "Sponsorship", "job_hunter": "Jobs",
                    "video_client": "Video clients",
                    "fullstack_sales": "Dev sales",
                    "saas_sales": "Product launch"}

    def cmd_learned(self, update, rest) -> None:
        """The rules each agent now follows, and where each came from.

        Learning that cannot be read cannot be corrected, and an agent that has
        taught itself a superstition looks exactly like one that has learned
        something real until you print the rules.
        """
        from core.lessons import get_lessons
        want = ALIASES.get(rest.strip().lower()) if rest.strip() else None
        agents = [want] if want else list(self.LEARN_AGENTS)
        out = []
        for agent in agents:
            rows = get_lessons(agent, self.store).all()
            if not rows:
                continue
            out.append(f"<b>{esc(self.LEARN_AGENTS.get(agent, agent))}</b>")
            for r in rows[:12]:
                followed = int(r["uses"] or 0)
                out.append(f"- {esc(r['rule'])}")
                bits = []
                if r["evidence"]:
                    bits.append(f"from: {str(r['evidence'])[:90]}")
                bits.append(f"used {followed}x")
                out.append(f"  <i>{esc('  |  '.join(bits))}</i>")
            out.append("")
        if not out:
            return self._reply(
                update, "Nothing learned yet. Every time you reject a draft "
                        "and say why - or edit one before approving - the "
                        "agent turns that into a rule it follows from then on. "
                        "They show up here.")
        out.append("<i>If one of these is wrong, tell me and I will remove it.</i>")
        self._reply(update, "\n".join(out))

    def cmd_pending(self, update, rest) -> None:
        rows = self.queue.pending(limit=25)
        if not rows:
            return self._reply(update, "Nothing is waiting for you. All clear.")
        self._reply(update, f"<b>{len(rows)} waiting for your decision.</b>")
        for row in rows:
            self.post_approval(row, force=True)

    cmd_approvals = cmd_pending

    def cmd_run(self, update, rest) -> None:
        name = ALIASES.get(rest.strip().lower())
        if not name:
            return self._reply(
                update, "Which one? " + ", ".join(f"<code>/run {SHORT[a]}</code>"
                                                  for a in TOPICS))
        thread = self._running.get(name)
        if thread and thread.is_alive():
            return self._reply(update, f"<b>{esc(TOPICS[name][0])}</b> is already "
                                       f"running. I will report when it finishes.")
        waiting = self.pending_for(name)
        if waiting:
            # Every /run used to start a fresh thread, leaving the last one
            # parked forever on a card you had not answered - which is why a
            # card count in the database sat at nine while the topic looked
            # dead. Answer the open one first; the run it belongs to carries on
            # from there.
            self._reply(update, f"There {'is 1 card' if len(waiting) == 1 else f'are {len(waiting)} cards'} "
                                f"still waiting on you from the last run. "
                                f"Posting {'it' if len(waiting) == 1 else 'them'} "
                                f"again - answer and it carries on from there.")
            for row in waiting:
                self.post_approval(row, force=True)
            return
        self._reply(update, f"Starting <b>{esc(TOPICS[name][0])}</b>. "
                            f"I will post results in its topic.")
        worker = threading.Thread(target=self._run_agent, args=(name,), daemon=True)
        self._running[name] = worker
        worker.start()

    def pending_for(self, agent: str | None = None) -> list[dict]:
        """Cards waiting on a decision. A stranded card stops its whole run."""
        rows = self.queue.pending(agent=agent)
        for r in rows:
            if isinstance(r.get("payload"), str):
                try:
                    r["payload"] = json.loads(r["payload"])
                except Exception:  # noqa: BLE001
                    r["payload"] = {}
        return rows

    def _run_agent(self, name: str, **kw) -> None:
        modules = {
            "community": "agents.community.agent",
            "job_hunter": "agents.job_hunter.agent",
            "saas_sales": "agents.saas_sales.agent",
            "sponsorship": "agents.sponsorship.agent",
            "video_client": "agents.video_client.agent",
            "fullstack_sales": "agents.fullstack_sales.agent",
        }
        try:
            mod = __import__(modules[name], fromlist=["make"])
            result = mod.make(store=self.store).run(
                **{k: v for k, v in kw.items() if v is not None})
        except Exception as exc:  # noqa: BLE001
            log.error(f"{name} failed: {exc}\n{traceback.format_exc()}")
            return self.say(f"<b>{esc(TOPICS[name][0])}</b> stopped with an error:\n"
                            f"<code>{esc(str(exc)[:500])}</code>", agent=name)

        if result.interrupted:
            self.say(f"<b>{esc(TOPICS[name][0])}</b> paused for your decision.",
                     agent=name)
            row = self.queue.get(result.approval_id)
            if row:
                self.post_approval(row, force=True)
            return
        state = result.state or {}
        summary = state.get("summary", {})
        body = "\n".join(f"{esc(k.replace('_', ' '))}: <b>{esc(v)}</b>"
                         for k, v in summary.items()) or "nothing to report"
        text = f"<b>{esc(TOPICS[name][0])}</b> finished.\n\n{body}"

        off = state.get("off_target") or []
        if off:
            text += (f"\n\n<b>Filtered out as not your kind of job</b> "
                     f"({len(off)} shown):\n")
            text += "\n".join(f"- {esc(o.get('title', ''))} "
                              f"({esc(o.get('reason', ''))})" for o in off[:8])
        if name == "job_hunter" and not summary.get("queued"):
            text += ("\n\nNothing matched. Widen it with <code>/roles all</code>, "
                     "or raise your level with <code>/exp 1</code>.")
        self.say(text, agent=name)
        self.post_handoffs(state, name)
        skipped = state.get("skipped") or []
        if skipped and name == "sponsorship":
            self.say(self.finished_text(state, name), agent=name)

    # Jobs are stored in the same leads table as everything else, tagged with
    # the job_hunter agent - there is no separate jobs table.
    STATUS_WORDS = {
        "rejected_fraud": "blocked as fake",
        "applied": "applied",
        "skipped": "skipped",
        "new": "found",
    }

    def cmd_jobs(self, update, rest) -> None:
        rows = self.store.query(
            "SELECT * FROM leads WHERE agent=? ORDER BY created_at DESC LIMIT 10",
            ("job_hunter",))
        if not rows:
            return self._reply(update, "No jobs stored yet. Try "
                                       "<code>/run jobs</code>.")
        lines = ["<b>Recent jobs</b>", ""]
        for r in rows:
            status = self.STATUS_WORDS.get(r.get("status", ""), r.get("status", ""))
            entry = [f"<b>{esc(r.get('role', ''))}</b> at {esc(r.get('company', ''))}",
                     f"{esc(status)} - {_fmt_age(r.get('created_at'))}"]
            try:
                data = json.loads(r.get("data_json") or "{}")
            except (TypeError, ValueError):
                data = {}
            match = (data.get("job") or {}).get("match") or {}
            if match.get("skills"):
                entry.append("skills: " + esc(", ".join(match["skills"][:6])))
            if match.get("min_years") == 0:
                entry.append("open to freshers")
            elif match.get("min_years"):
                entry.append(f"wants {match['min_years']}+ years")
            if r.get("source_url"):
                entry.append(esc(r["source_url"]))
            lines.append("\n".join(entry))
        self._reply(update, "\n\n".join(lines))

    def cmd_leads(self, update, rest) -> None:
        rows = self.store.query(
            "SELECT * FROM leads WHERE agent<>? ORDER BY created_at DESC LIMIT 10",
            ("job_hunter",))
        if not rows:
            return self._reply(update, "No leads yet. Run one of the outreach "
                                       "agents, for example <code>/run sponsorship"
                                       "</code>.")
        lines = ["<b>Recent leads</b>", ""]
        for r in rows:
            entry = [f"<b>{esc(r.get('company', ''))}</b>",
                     esc(r.get("email", "") or "no email found"),
                     f"{esc(r.get('status', ''))} - {_fmt_age(r.get('created_at'))}"]
            lines.append("\n".join(entry))
        self._reply(update, "\n\n".join(lines))

    def cmd_brands(self, update, rest) -> None:
        """Where the sponsorship list stands: done, waiting, and what is next."""
        from agents.sponsorship import agent as sp
        from core.search import SeedsProvider

        try:
            brands = SeedsProvider(sp.build_config().seed_file).load()
        except Exception as exc:  # noqa: BLE001
            return self._reply(update, f"Could not read the sponsor list: {esc(exc)}")

        rows = self.store.query(
            "SELECT domain, company, email, status FROM leads WHERE agent=?",
            ("sponsorship",))
        done = {r.get("domain") for r in rows}
        by_status: dict[str, int] = {}
        for r in rows:
            by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1

        seg = rest.strip().lower().replace(" ", "_")
        pool = [b for b in brands
                if not seg or seg in (b.get("segment", "").lower(),
                                      b.get("name", "").lower())]
        remaining = [b for b in pool
                     if (b.get("url", "").split("//")[-1].split("/")[0]
                         .removeprefix("www.")) not in done]

        from collections import Counter
        by_deal = Counter(b.get("deal_type", "cash") for b in remaining)
        lines = [f"<b>Sponsorship pipeline</b>", "",
                 f"On the list       {len(brands)}",
                 f"Worked through    {len(done)}",
                 f"Still to go       {len(remaining)}"]
        if by_deal:
            label = {"cash": "paid promotions to pitch",
                     "agency": "agencies that place paid work",
                     "barter": "product-for-video deals",
                     "affiliate": "affiliate schemes (off by default)"}
            lines += ["", "<b>What is left, by kind of deal</b>"]
            for k in ("affiliate", "agency", "barter", "cash"):
                if by_deal.get(k):
                    lines.append(f"{by_deal[k]:>4}  {esc(label[k])}")
        if by_status:
            lines.append("")
            label = {"contacted": "emailed",
                     "ready_to_send": "message ready, needs you to send",
                     "replied": "replied", "manual_followup": "manual follow-up"}
            for k, v in sorted(by_status.items(), key=lambda kv: -kv[1]):
                lines.append(f"{v:>3}  {esc(label.get(k, k))}")

        waiting = [r for r in rows if r.get("status") == "ready_to_send"]
        if waiting:
            lines += ["", "<b>Waiting on you to send</b>"]
            for r in waiting[:8]:
                lines.append(f"- {esc(r.get('company') or r.get('domain'))}")

        if remaining:
            lines += ["", "<b>Next up</b>"]
            for b in sorted(remaining, key=lambda x: (x.get("tier", 3),
                                                      x.get("name", "")))[:8]:
                lines.append(f"- {esc(b.get('name', ''))}  "
                             f"<i>{esc(str(b.get('segment', '')).replace('_', ' '))}</i>")
            lines += ["", "Run the next batch with <code>/run sponsorship</code>."]
        else:
            lines += ["", "Every brand on the list has been worked through."]
        self._reply(update, "\n".join(lines))

    def cmd_discover(self, update, rest) -> None:
        """Run the sponsorship agent with the web sweep forced on.

        This is the same agent as `/run sponsorship` - it just does not wait
        for the weekly sweep to come round. It looks first, asks what to add,
        and then works the list as usual.
        """
        arg = rest.strip().lower()
        known = {"cuelinks", "admitad", "youtube", "trade_press", "web_search"}
        only = [a for a in re.split(r"[,\s]+", arg) if a in known]
        thread = self._running.get("sponsorship")
        if thread and thread.is_alive():
            return self._reply(update, "<b>Sponsorship</b> is already running. "
                                       "I will report when it finishes.")
        self._reply(update, (
            "Searching the web for sponsors that are not on your list yet"
            + (f" - {esc(', '.join(only))} only" if only else "")
            + ".\n\nThis takes a few minutes. Anything it finds appears here "
              "with an Approve button - approving adds it to your list. Then it "
              "carries on with the usual outreach."))
        worker = threading.Thread(
            target=self._run_agent, args=("sponsorship",),
            kwargs={"discover": True, "only_sources": only or None},
            daemon=True)
        self._running["sponsorship"] = worker
        worker.start()

    def cmd_learned(self, update, rest) -> None:
        """What your decisions have taught it."""
        from agents.sponsorship.brain import Memory
        summary = Memory(self.store).summary()
        if not summary["decisions"]:
            return self._reply(update, (
                "Nothing learned yet. Every time you approve or reject "
                "something it files that as evidence, and starts ranking new "
                "finds by what you have said yes to.\n\nRun "
                "<code>/discover</code> and decide a few."))
        ev = summary.get("events") or {}
        pretty = {"added": "brands you added", "not_added": "brands you skipped",
                  "pitch_approved": "pitches you approved",
                  "pitch_rejected": "pitches you rejected",
                  "sent": "messages sent",
                  "replied_interested": "brands that replied with interest",
                  "replied_no": "brands that said no",
                  "deal_agreed": "deals agreed", "bounced": "bounced",
                  "unsubscribed": "unsubscribed",
                  "unreachable": "no way in found"}
        lines = [f"<b>What I have worked out</b>", "",
                 f"From {summary['decisions']} pieces of evidence.",
                 f"Roughly {summary['base_rate']:.0%} of what I show you "
                 f"turns out to be worth having.", ""]
        if ev:
            lines.append("<b>What has happened so far</b>")
            for k, v in ev.items():
                lines.append(f"{v // 6 or v:>4}  {esc(pretty.get(k, k))}")
            lines.append("")
        if summary["best"]:
            lines.append("<b>You tend to say yes to</b>")
            for r in summary["best"][:6]:
                lines.append(f"<code>{esc(r['feature'])}</code>  "
                             f"+{r['shift']:.2f}  ({r['for']:.0f} for, "
                             f"{r['against']:.0f} against)")
        if summary["worst"]:
            lines += ["", "<b>You tend to say no to</b>"]
            for r in summary["worst"][:6]:
                lines.append(f"<code>{esc(r['feature'])}</code>  "
                             f"{r['shift']:.2f}  ({r['for']:.0f} for, "
                             f"{r['against']:.0f} against)")
        lines += ["", "<i>A reply from a brand counts four times as much as "
                      "an approval, because a reply is what they thought.</i>"]
        self._reply(update, "\n".join(lines))

    def cmd_why(self, update, rest) -> None:
        """Show the arithmetic behind one prospect's score."""
        needle = rest.strip().lower()
        if not needle:
            return self._reply(update, "Give me a domain or name, for example "
                                       "<code>/why nakpro.com</code>.")
        row = self.store.one(
            "SELECT * FROM prospects WHERE domain LIKE ? OR LOWER(name) LIKE ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (f"%{needle}%", f"%{needle}%"))
        if row is None:
            return self._reply(update, f"I have no record of "
                                       f"<code>{esc(needle)}</code>. It may be on "
                                       f"the list already rather than something "
                                       f"I found.")
        try:
            why = json.loads(row.get("why_json") or "[]")
        except ValueError:
            why = []
        lines = [f"<b>{esc(row.get('name') or row['domain'])}</b>",
                 esc(row.get("domain", "")), "",
                 f"Score <b>{float(row.get('score') or 0):.0%}</b>",
                 f"Indian <b>{float(row.get('india_score') or 0):.0%}</b>",
                 f"Found by <i>{esc(row.get('source', ''))}</i>",
                 f"Status <i>{esc(row.get('status', ''))}</i>", ""]
        if why:
            lines.append("<b>Each thing about it, and what it did to the score</b>")
            for w in why[:8]:
                lines.append(
                    f"<code>{esc(str(w.get('feature')))}</code>  "
                    f"{float(w.get('shift') or 0):+.2f}   "
                    f"({float(w.get('for') or 0):.0f} for, "
                    f"{float(w.get('against') or 0):.0f} against)")
            lines += ["", "<i>A plus means things like this have worked out "
                          "before. A minus means they have not.</i>"]
        else:
            lines.append("<i>No history when this was scored - it was a "
                         "starting guess.</i>")
        self._reply(update, "\n".join(lines))

    def cmd_mediakit(self, update, rest) -> None:
        """What is still blank in creator.yaml, and what it costs you."""
        from agents.sponsorship import pitch as pm
        creator = pm.load_creator(refresh=True)
        facts = pm.audience_facts(creator)
        missing = []
        yt = next((c for c in creator.get("channels") or []
                   if c.get("platform") == "youtube"), {})
        ig = next((c for c in creator.get("channels") or []
                   if c.get("platform") == "instagram"), {})
        if not pm._n(yt.get("subscribers")):
            missing.append("YouTube subscribers")
        if not pm._n(yt.get("avg_views")):
            missing.append("average views per video")
        if not pm._n(ig.get("followers")):
            missing.append("Instagram followers")
        aud = creator.get("audience") or {}
        if not pm._n(aud.get("male_share")):
            missing.append("audience split (YouTube Studio > Audience)")
        if not pm.best_work_links(creator):
            missing.append("two links to your best videos")

        lines = ["<b>Your creator profile</b>", ""]
        if facts:
            lines.append("Emails currently say:")
            lines += [f"- {esc(f)}" for f in facts]
        else:
            lines.append("Emails currently claim <b>nothing</b> about your "
                         "audience, because nothing has been filled in. They "
                         "still go out - they just sell the work rather than "
                         "the numbers.")
        if missing:
            lines += ["", "<b>Still blank</b>"]
            lines += [f"- {esc(m)}" for m in missing]
            lines += ["", f"Edit <code>profiles/creator.yaml</code>. Put in real "
                          f"figures only - a brand checks them in thirty seconds."]
        else:
            lines += ["", "Nothing missing. Every pitch carries your real numbers."]
        self._reply(update, "\n".join(lines))

    def cmd_resume(self, update, rest) -> None:
        from agents.job_hunter.agent import output_dir
        files = sorted(pathlib.Path(output_dir()).glob("*.pdf"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if rest.strip():
            needle = rest.strip().lower()
            files = [f for f in files if needle in f.name.lower()] or files
        if not files:
            return self._reply(update, "No resumes built yet. Try "
                                       "<code>/run jobs</code>.")
        for path in files[:3]:
            self.send_file(path, caption=esc(path.stem.replace("-", " ")),
                           agent="job_hunter")

    def cmd_exp(self, update, rest) -> None:
        """Your years of experience. Everything above it is filtered out."""
        from agents.job_hunter import relevance
        current = relevance.max_experience_years()
        slack = relevance.experience_slack()
        want = rest.strip()
        if not want:
            return self._reply(
                update,
                f"You are set to <b>{current} year(s)</b> of experience.\n\n"
                f"I show jobs asking for up to <b>{current + slack}</b> years - "
                f"a posting wanting a bit more than you have is still worth "
                f"seeing, one wanting eight is not.\n\n"
                f"Change it with <code>/exp 1</code>, <code>/exp 2</code>, "
                f"and so on. This survives restarts.")
        try:
            years = max(0, min(30, int(want.split()[0])))
        except ValueError:
            return self._reply(update, "Give me a number, like <code>/exp 1</code>.")

        _persist_env("JOB_EXPERIENCE_YEARS", str(years))
        self._set("experience_years", years)
        self._reply(update,
                    f"Set to <b>{years} year(s)</b>. From now on I will show you "
                    f"jobs asking for up to <b>{years + slack}</b> years and hide "
                    f"the rest.\n\nRun <code>/run jobs</code> to search again.")

    def cmd_roles(self, update, rest) -> None:
        from agents.job_hunter import relevance
        want = rest.strip().lower()
        if not want:
            active = relevance.wanted_families()
            lines = ["<b>Job types I am looking for</b>", ""]
            for name in relevance.ROLE_FAMILIES:
                mark = "on " if name in active else "off"
                lines.append(f"[{mark}] <code>{name}</code>")
            lines += ["", "Change with <code>/roles ai_ml agentic_ai software</code>",
                      "or <code>/roles all</code> for everything."]
            return self._reply(update, "\n".join(lines))

        if want == "all":
            chosen = list(relevance.ROLE_FAMILIES)
        else:
            chosen = [w for w in re.split(r"[\s,]+", want)
                      if w in relevance.ROLE_FAMILIES]
        if not chosen:
            return self._reply(update, "I did not recognise any of those. Send "
                                       "<code>/roles</code> to see the list.")
        _persist_env("JOB_ROLE_FAMILIES", ",".join(chosen))
        self._reply(update, "Now looking for: <b>"
                    + "</b>, <b>".join(esc(c) for c in chosen) + "</b>.\n\n"
                    "Run <code>/run jobs</code> to search again.")

    def cmd_doctor(self, update, rest) -> None:
        import io
        import contextlib
        import run as cli
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                cli.cmd_doctor(type("A", (), {})())
        except SystemExit:
            pass
        except Exception as exc:  # noqa: BLE001
            buf.write(f"\ndoctor failed: {exc}")
        text = buf.getvalue().strip() or "no output"
        self._reply(update, f"<pre>{esc(text)}</pre>")

    # -- approvals -----------------------------------------------------------
    def approval_text(self, row: dict) -> str:
        if row.get("kind") == "apply_to_job":
            return self.job_text(row)
        if row.get("agent") == "saas_sales":
            return self.launch_text(row)
        if row.get("agent") in ("video_client", "fullstack_sales") \
                and (row.get("payload") or {}).get("quote_ask"):
            return self.client_text(row)
        if row.get("agent") == "sponsorship":
            return self.brand_text(row)
        if row.get("kind") == "add_target":
            return self.prospect_text(row)
        payload = row.get("payload") or {}
        lines = [f"<b>{esc(row.get('title', 'Approval needed'))}</b>",
                 f"<i>{esc(row.get('kind', ''))} - {_fmt_age(row.get('created_at'))}"
                 f"</i>", ""]
        interesting = ("to", "company", "subject", "role", "salary", "amount",
                       "total", "url", "apply_url", "when")
        for key in interesting:
            if payload.get(key):
                lines.append(f"{esc(key.replace('_', ' '))}: "
                             f"<b>{esc(payload[key])}</b>")
        body = payload.get("body") or payload.get("preview") or payload.get("text")
        if body:
            lines += ["", f"<pre>{esc(str(body)[:1200])}</pre>"]
        return "\n".join(lines)

    def launch_text(self, row: dict) -> str:
        """A launch card. The stage and any blocked claim come first.

        This is the one agent that can do real damage by being persuasive -
        it is talking about a product that does not exist yet, to the exact
        community that will later be its first customers. So the card leads
        with what stage the product is at and what the draft was caught
        claiming, not with the message.
        """
        p = row.get("payload") or {}
        kind = {"user": "A USER - would they pay for this",
                "promoter": "A PROMOTER - their audience is who this is for",
                "agency": "AN AGENCY - buys seats, thinks in hours per edit",
                "directory": "A DIRECTORY - a submission, not an email",
                "competitor": "A COMPETITOR"}.get(p.get("audience", ""), "")
        lines = [f"<b>{esc(p.get('company', ''))}</b>"]
        if kind:
            lines.append(f"<b>{esc(kind)}</b>")
        if p.get("subscribers"):
            lines.append(f"Audience   {esc(p['subscribers'])}")
        if p.get("evidence"):
            lines.append(f"Found via  <i>{esc(str(p['evidence'])[:120])}</i>")
        if p.get("to"):
            lines.append(f"Email      {esc(p['to'])}")
        lines.append(f"Product is <b>{esc(p.get('stage', '?'))}</b>")

        problems = p.get("claim_problems") or []
        if problems:
            lines += ["", "<b>HELD BACK - this claims something the product "
                          "cannot back yet</b>"]
            lines += [f"- {esc(str(x))}" for x in problems[:6]]
            lines.append("<i>Approving will not send it. Fix product.yaml or "
                         "let it redraft.</i>")
        if p.get("reads_as"):
            lines += ["", "<b>What the model read about them</b>",
                      f"<i>{esc(str(p['reads_as'])[:300])}</i>"]
        if p.get("fallback"):
            lines += ["", "<i>The local model was not reachable - this is the "
                          "plain written note.</i>"]
        if p.get("subject"):
            lines += ["", f"Subject: <b>{esc(p['subject'])}</b>"]
        if p.get("body"):
            lines += ["", f"<pre>{esc(str(p['body'])[:1400])}</pre>"]
        return "\n".join(lines)

    def client_text(self, row: dict) -> str:
        """A freelance gig card. What it is, who they are, and what it is worth.

        The asking price and the floor are both shown. The ask is what the
        agent will open with; the floor is the number it will never go below
        without stopping to ask you - and knowing both before you approve is
        the difference between a negotiation and a surprise.
        """
        p = row.get("payload") or {}
        # The technical read is the thing worth checking before it goes out
        # with his name on it: a confident wrong diagnosis is worse than none.
        if p.get("likely_cause"):
            pass
        kind = {"agency": "AGENCY - repeat work if they like you",
                "brand": "BRAND - pays on invoice, slower to close",
                "creator": "CREATOR - fast to decide, smaller budget",
                "coach": "COURSE / PODCAST - recurring volume",
                "unknown": "CLIENT TYPE UNKNOWN"}.get(
                    p.get("client_kind", "unknown"), "")
        lines = [f"<b>{esc(p.get('title', ''))}</b>",
                 f"{esc(p.get('company', ''))}  |  {esc(p.get('location', ''))}"]
        if kind:
            lines.append(f"<b>{esc(kind)}</b>")
        lines += ["", f"Work       {esc(p.get('quote_tier', ''))}",
                  f"Ask        <b>{esc(p.get('quote_ask', ''))}</b>"]
        if p.get("quote_floor"):
            lines.append(f"Walk away  {esc(p.get('quote_floor', ''))}")
        if p.get("work_kind"):
            lines.append(f"Type       {esc(str(p['work_kind']).replace('_', ' '))}")
        if p.get("likely_cause"):
            lines += ["", "<b>What the model thinks is broken</b>",
                      f"<i>{esc(str(p['likely_cause'])[:300])}</i>",
                      "<i>Check this before it goes out - a confident wrong "
                      "diagnosis is worse than none.</i>"]
        if p.get("source"):
            lines.append(f"Found on   {esc(str(p['source']))}")
        if p.get("reads_as"):
            lines += ["", "<b>What the model read in their posting</b>",
                      f"<i>{esc(str(p['reads_as'])[:400])}</i>"]
        if p.get("fallback"):
            lines += ["", "<i>The local model was not reachable, so this is "
                          "the written template, not a tailored message.</i>"]
        if p.get("subject"):
            lines += ["", f"Subject: <b>{esc(p['subject'])}</b>"]
        if p.get("body"):
            lines += ["", f"<pre>{esc(str(p['body'])[:1400])}</pre>"]
        lines += ["", "<i>This first email carries no price. The rate only goes "
                      "out when they reply.</i>"]
        return "\n".join(lines)

    def job_text(self, row: dict) -> str:
        """A job card built to be decided on from a phone, in ten seconds.

        Ordered by what actually decides it: what the role is, what it pays,
        what experience it wants, then the skills to check yourself against.
        """
        p = row.get("payload") or {}
        exp = str(p.get("experience", "not stated"))
        badge = "FRESHER OK" if exp == "open to freshers" else exp.upper()
        lines = [
            f"<b>{esc(p.get('title', ''))}</b>",
            f"{esc(p.get('company', ''))}  |  <b>{esc(badge)}</b>",
            "",
            f"Pay        {esc(p.get('salary', 'not stated'))}",
            f"Experience {esc(exp)}",
            f"Where      {esc(p.get('location') or 'not stated')}"
            + ("  (remote)" if p.get("remote") else ""),
        ]
        note = str(p.get("location_note") or "")
        # A remote posting that never names a country is worth flagging: it
        # passed the location check by default, not because anyone checked.
        if "not stated" in note:
            lines.append("           <i>remote, but the posting never says "
                         "which countries - check before you spend time on it</i>")
        if p.get("source"):
            lines.append(f"Found on   {esc(str(p['source']))}")
        if p.get("role_family"):
            lines.append(f"Type       {esc(str(p['role_family']).replace('_', ' '))}")

        skills = p.get("skills") or []
        if skills:
            lines += ["", "<b>Skills they ask for</b>",
                      esc(", ".join(str(x) for x in skills))]

        if p.get("reads_as"):
            lines += ["", "<b>What the model read in the posting</b>",
                      f"<i>{esc(str(p['reads_as'])[:400])}</i>"]
        if p.get("strongest_match"):
            lines.append(f"Best fit   {esc(str(p['strongest_match'])[:200])}")
        if p.get("biggest_gap"):
            # The gap is the part he needs before deciding, not after.
            lines.append(f"Gap        {esc(str(p['biggest_gap'])[:200])}")
        if p.get("worth_applying") is False:
            lines += ["", f"<b>The model says do not bother:</b> "
                          f"{esc(str(p.get('why_not', ''))[:200])}"]

        cov = p.get("keyword_coverage")
        if isinstance(cov, (int, float)):
            lines += ["", f"Your resume covers <b>{cov:.0%}</b> of their keywords"]
        if p.get("stripped_claims"):
            lines.append(f"Invented facts removed: {esc(p['stripped_claims'])}")
        else:
            lines.append("Nothing on the resume was made up")

        if p.get("apply_url"):
            lines += ["", esc(p["apply_url"])]
        return "\n".join(lines)

    def prospect_text(self, row: dict) -> str:
        """A brand the agent found on the web, and why it thinks you want it.

        The score is shown with its working. A number on its own asks to be
        trusted; the arithmetic underneath it can be argued with, and arguing
        with it is how the agent learns.
        """
        p = row.get("payload") or {}
        lines = [f"<b>{esc(p.get('company') or p.get('domain', ''))}</b>",
                 esc(p.get("url", "")), ""]
        where = {"cuelinks": "found on Cuelinks - they pay commission right now",
                 "admitad": "found on Admitad, India-targeted offer",
                 "youtube": "already sponsoring another cricket channel",
                 "trade_press": "found in the Indian marketing press",
                 "search": "found by web search"}.get(p.get("source", ""),
                                                      p.get("source", ""))
        lines.append(f"Where      <i>{esc(where)}</i>")
        if p.get("note"):
            lines.append(f"Context    {esc(str(p['note'])[:140])}")
        if p.get("payout"):
            lines.append(f"Pays       <b>{esc(p['payout'])}</b>")
        if p.get("deal_type"):
            lines.append(f"Deal       {esc(p['deal_type'])}")
        if p.get("to"):
            lines.append(f"Contact    {esc(p['to'])}")

        hits = p.get("india_hits") or []
        lines += ["", f"<b>Indian?</b>  {float(p.get('india_score') or 0):.0%}"]
        if hits:
            lines.append(esc(", ".join(str(h) for h in hits[:5])))

        lines += ["", f"<b>Score {float(p.get('score') or 0):.0%}</b> - how it got there"]
        for w in (p.get("why") or [])[:5]:
            lines.append(f"<code>{esc(str(w))}</code>")
        if not p.get("why"):
            lines.append("<i>no history yet - this is its starting guess</i>")

        body = p.get("body")
        if body:
            lines += ["", f"<pre>{esc(str(body)[:400])}</pre>"]
        lines += ["", "<i>Approve adds it to your sponsor list. Nothing is "
                      "contacted until the sponsorship agent runs.</i>"]
        return "\n".join(lines)

    def brand_text(self, row: dict) -> str:
        """A sponsorship card you can decide on from a phone.

        Ordered by what decides it: who they are, why they are worth pitching,
        how you reach them, and how sure we are of that route - then the actual
        message, so nothing is sent that you have not read.
        """
        p = row.get("payload") or {}
        tier = {1: "reachable", 2: "usually via agency",
                3: "large brand"}.get(p.get("tier"), "")
        head = esc(p.get("company") or p.get("domain") or "Brand")
        seg = str(p.get("segment", "")).replace("_", " ")
        # What you are actually asking them for. Worth putting at the top,
        # because "join their affiliate programme" and "send us free product"
        # are very different decisions from "pay me for a video".
        deal = {"cash": "ASKING THEM TO PAY FOR A PROMOTION",
                "agency": "ASKING TO JOIN THEIR ROSTER - they bring paid work",
                "barter": "ASKING FOR PRODUCT IN EXCHANGE FOR A VIDEO",
                "affiliate": "ASKING TO JOIN THEIR AFFILIATE PROGRAMME"}.get(
                    p.get("deal_type", ""), "")
        lines = [f"<b>{head}</b>"]
        if seg or tier:
            lines.append(f"{esc(seg)}{'  |  ' + esc(tier) if tier else ''}")
        if deal:
            lines.append(f"<b>{esc(deal)}</b>")
        lines.append("")

        channel = p.get("channel") or "email"
        route = {"email": "Email", "whatsapp": "WhatsApp", "phone": "Phone",
                 "form": "Their form", "social": "DM"}.get(channel, "Contact")
        lines.append(f"{route:<10} {esc(p.get('to', ''))}")
        if p.get("guessed"):
            lines.append("           <i>guessed address - not published by them</i>")
        # The other route, when they have one. Both buttons are below the card;
        # this is so you can see what they are before you tap.
        other = []
        if p.get("best_email") and p["best_email"] != p.get("to"):
            other.append(str(p["best_email"]))
        if p.get("best_phone") and p["best_phone"] != p.get("to"):
            other.append(str(p["best_phone"]))
        if other:
            lines.append(f"Also       {esc(', '.join(other))}")
        if p.get("evidence"):
            lines.append(f"Found      <i>{esc(p['evidence'])}</i>")
        if p.get("fit"):
            lines += ["", f"<b>Why them</b>", esc(p["fit"])]
        if p.get("reads_as"):
            lines += ["", "<b>What the model read on their site</b>",
                      f"<i>{esc(str(p['reads_as'])[:400])}</i>"]
        if p.get("tools_used"):
            # What it went and looked up before writing. Worth seeing: a draft
            # built on a lookup is a different thing from one built on a guess.
            lines += ["", f"<b>Looked up first</b>  "
                          f"<i>{esc(str(p['tools_used'])[:250])}</i>"]
        if p.get("fallback"):
            lines += ["", "<i>The local model was not reachable, so this is the "
                          "written template, not a tailored message.</i>"]
        if p.get("has_numbers") is False:
            lines += ["", "<i>No channel numbers in your profile yet, so this "
                          "pitch does not claim any. Fill in creator.yaml and "
                          "every later email gets stronger.</i>"]

        if channel == "email" and p.get("subject"):
            lines += ["", f"Subject: <b>{esc(p['subject'])}</b>"]
        body = p.get("body") if channel == "email" else (
            p.get("whatsapp_text") or p.get("body"))
        if body:
            lines += ["", f"<pre>{esc(str(body)[:1400])}</pre>"]
        return "\n".join(lines)

    def approval_buttons(self, approval_id: str, row: dict | None = None) -> dict:
        rows = [[Button("Approve", f"ok:{approval_id}"),
                 Button("Reject", f"no:{approval_id}")]]
        payload = (row or {}).get("payload") or {}
        if (row or {}).get("kind") == "apply_to_job":
            # The PDF is sent with the card, so this is only for when you want
            # it again after scrolling past.
            rows.insert(0, [Button("Send the resume again", f"cv:{approval_id}")])
            url = str(payload.get("apply_url") or "")
            if url.startswith("http"):
                # This is where the application actually happens. Approve
                # records it; this opens the portal with the PDF already on
                # your phone to upload.
                rows.insert(0, [Button("Open the portal and apply", "", url=url)])
        elif (row or {}).get("agent") == "saas_sales" and payload.get("apply_url"):
            url = str(payload["apply_url"])
            if url.startswith("http"):
                label = ("Open the submission page"
                         if payload.get("audience") == "directory"
                         else "Open their channel")
                rows.append([Button(label, "", url=url)])
        elif (row or {}).get("agent") in ("video_client", "fullstack_sales") \
                and payload.get("apply_url"):
            url = str(payload["apply_url"])
            if url.startswith("http"):
                rows.append([Button("Open the posting", "", url=url)])
        elif (row or {}).get("agent") == "sponsorship":
            # Both routes on every card. A brand is worth reaching by mail and
            # by WhatsApp, and which one the qualifier ranked first is no
            # reason to make the other one hard to find. Each link opens the
            # app with the message already written - one tap from sent.
            send = []
            to = payload.get("best_email") or (
                payload.get("to") if payload.get("channel") == "email" else "")
            if to:
                from agents.sponsorship.pitch import gmail_link
                send.append(Button("Open in Gmail", "", url=gmail_link(
                    str(to), str(payload.get("subject", "")),
                    str(payload.get("body", "")))))
            if payload.get("wa_link"):
                send.append(Button("Open WhatsApp", "", url=str(payload["wa_link"])))
            if send:
                rows.append(send)
            extra = []
            if payload.get("contact_form_url"):
                extra.append(Button("Open their form", "",
                                    url=str(payload["contact_form_url"])))
            if payload.get("instagram_dm"):
                extra.append(Button("Show me the DM version", f"dm:{approval_id}"))
            if extra:
                rows.append(extra)
        return keyboard(rows)

    def post_approval(self, row: dict, force: bool = False):
        """Put one approval in its agent's topic. Never posts the same one twice."""
        aid = row["id"]
        if not force and self._get(f"posted:{aid}"):
            return None
        sent = self.say(self.approval_text(row), agent=row.get("agent", ""),
                        buttons=self.approval_buttons(aid, row))
        # A job card is a decision about a document, so the document goes with
        # it. Tapping a button to see the resume, then tapping back to approve,
        # is two taps too many when the resume is the whole point - and he
        # asked to read the actual PDF before every decision, not after.
        payload = row.get("payload") or {}
        if row.get("kind") == "apply_to_job" and payload.get("resume_path"):
            self.send_file(payload["resume_path"], agent=row.get("agent", ""),
                           caption=f"Resume tailored for "
                                   f"{esc(payload.get('title', ''))} at "
                                   f"{esc(payload.get('company', ''))}")
        for attachment in payload.get("attachments") or []:
            self.send_file(attachment, agent=row.get("agent", ""), caption="Review this document before approving the reply.")
        self._set(f"posted:{aid}", True)
        return sent

    def push_pending(self) -> int:
        """Post anything new that is waiting. Called on a timer."""
        posted = 0
        for row in self.queue.pending(limit=50):
            if self._get(f"posted:{row['id']}"):
                continue
            self.post_approval(row)
            posted += 1
        return posted

    def _ack(self, update, text: str = "", alert: bool = False) -> None:
        """Stop the button spinner immediately.

        Telegram invalidates a callback id in seconds, so this has to happen
        before any database or network work - otherwise the tap fails with
        "query is too old" even though the action itself succeeded.
        """
        try:
            self.tg.answer_callback(update.callback_id, text, alert=alert)
        except TelegramError as exc:
            log.warn(f"could not acknowledge the tap: {exc}")

    def _handle_callback(self, update) -> None:
        action, _, aid = update.text.partition(":")
        if not self.authorised(update):
            return self._ack(update, "This bot is not yours.", alert=True)
        if action == "sent":
            # A message you sent by hand. Recording it is what lets the brain
            # count it, and stops the same brand coming back around.
            self._ack(update, "Marked as sent.")
            from core.delivery import mark_manual_sent
            if not mark_manual_sent(self.store, aid):
                return self._reply(update, "Already recorded or no longer awaiting a manual send.")
            lead = self.store.one("SELECT * FROM leads WHERE id=?", (aid,))
            if lead:
                try:
                    from agents.sponsorship.brain import Memory
                    Memory(self.store).record_target(lead, "sent")
                except Exception as exc:  # noqa: BLE001
                    log.debug(f"could not record the send: {exc}")
            return self._reply(update, "Noted - counted as sent.")

        if action not in ("ok", "no", "cv", "dm"):
            return self._ack(update)

        row = self.queue.get(aid)
        if row is None:
            return self._ack(update, "That approval no longer exists.", alert=True)

        if action == "cv":
            self._ack(update, "Sending the resume...")
            path = (row.get("payload") or {}).get("resume_path")
            if not path:
                return self.say("There is no resume attached to that one.",
                                agent=row.get("agent", ""))
            return self.send_file(
                path, caption=f"Resume tailored for "
                              f"{esc((row.get('payload') or {}).get('title', ''))} "
                              f"at {esc((row.get('payload') or {}).get('company', ''))}",
                agent=row.get("agent", ""))

        if action == "dm":
            self._ack(update)
            p = row.get("payload") or {}
            text = p.get("instagram_dm") or "No DM version was drafted for this one."
            handle = (p.get("socials") or {}).get("instagram", "")
            msg = f"<b>Instagram DM - {esc(p.get('company', ''))}</b>\n\n<pre>{esc(text)}</pre>"
            if handle:
                msg += f"\n\n{esc(handle)}"
            # Reply where the tap happened, so the DM text lands directly under
            # the card it belongs to rather than at the bottom of the topic.
            return self._reply(update, msg)

        if row["status"] != "pending":
            self._ack(update, f"Already {row['status']}.", alert=True)
            return self._freeze(update, row, row["status"])

        approve = action == "ok"
        self._ack(update, "Approved" if approve else "Rejected")
        note = f"via telegram by {update.from_name}"
        decision = (self.queue.approve(aid, note=note) if approve
                    else self.queue.reject(aid, note=note))
        self._freeze(update, row, "approved" if approve else "rejected")

        # Waking the graph can take a while (it may send an email), so it does
        # not belong on the callback path - Telegram would retry the tap.
        worker = threading.Thread(target=self._resume, args=(row, decision),
                                  daemon=True)
        self._workers.append(worker)
        worker.start()

    def _freeze(self, update, row: dict, status: str) -> None:
        """Replace the buttons with the outcome so it cannot be tapped twice."""
        mark = "APPROVED" if status == "approved" else "REJECTED"
        try:
            self.tg.edit_message_text(
                update.chat_id, update.message_id,
                f"{self.approval_text(row)}\n\n<b>{mark}</b>", buttons=None)
        except TelegramError as exc:
            log.warn(f"could not update the message: {exc}")

    # -- handing over what the agent cannot send itself ----------------------
    def post_handoffs(self, state: dict, agent: str) -> int:
        """Post the messages that need your hand, once each.

        A WhatsApp message, an enquiry form and an Instagram DM cannot be sent
        by a program. The agent writes them and stops. Until now it wrote them
        to the terminal, so approving a WhatsApp card from a phone produced
        silence and the message was never actually sent by anyone.
        """
        posted = 0
        for h in (state.get("handoff") or []):
            key = str(h.get("lead_id") or h.get("domain") or "")
            if not key or not self.store.mark_seen(f"{agent}:handoff", key):
                continue
            self.say(self.handoff_text(h), agent=agent,
                     buttons=self.handoff_buttons(h))
            posted += 1
        return posted

    HANDOFF_ROUTE = {
        "whatsapp": ("WhatsApp", "Open WhatsApp"),
        "form": ("Their enquiry form", "Open the form"),
        "social": ("Direct message", "Open their profile"),
        "phone": ("Phone", ""),
    }

    def handoff_text(self, h: dict) -> str:
        channel = h.get("channel") or "email"
        label, _ = self.HANDOFF_ROUTE.get(channel, ("Contact", ""))
        company = esc(h.get("company") or h.get("domain") or "this brand")
        body = (h.get("whatsapp_text") if channel == "whatsapp"
                else h.get("instagram_dm") if channel == "social"
                else h.get("body")) or h.get("body") or ""
        lines = [f"<b>Ready to send - {company}</b>",
                 f"{label}   {esc(h.get('route', ''))}", ""]
        if channel == "form" and h.get("subject"):
            lines += [f"Subject: <b>{esc(h['subject'])}</b>", ""]
        lines += [f"<pre>{esc(str(body)[:1400])}</pre>", "",
                  "<i>I cannot send this one myself. Copy it, check it, send "
                  "it - then tell me with the button so it is not offered "
                  "again.</i>"]
        return "\n".join(lines)

    def handoff_buttons(self, h: dict) -> dict | None:
        from agents.sponsorship.pitch import gmail_link
        rows, channel = [], h.get("channel") or ""
        send = []
        if h.get("best_email"):
            send.append(Button("Open in Gmail", "", url=gmail_link(
                str(h["best_email"]), str(h.get("subject", "")),
                str(h.get("body", "")))))
        if h.get("wa_link"):
            send.append(Button("Open WhatsApp", "", url=str(h["wa_link"])))
        if channel in ("form", "social") and str(h.get("route", "")).startswith("http"):
            _, verb = self.HANDOFF_ROUTE.get(channel, ("", "Open it"))
            send.append(Button(verb or "Open it", "", url=str(h["route"])))
        if send:
            rows.append(send)
        if h.get("lead_id"):
            rows.append([Button("I sent it", f"sent:{h['lead_id']}")])
        return keyboard(rows) if rows else None

    def finished_text(self, state: dict, agent: str) -> str:
        """Why the cards stopped coming.

        A brand with no reachable contact is skipped without a card, so a run
        over forty brands can produce four cards and thirty-six silences. From
        the outside that is indistinguishable from the bot dying, which is how
        it was read.
        """
        summary = state.get("summary", {})
        lines = [f"<b>{esc(TOPICS.get(agent, (agent,))[0])}</b> finished."]
        body = "\n".join(f"{esc(k.replace('_', ' '))}: <b>{esc(v)}</b>"
                          for k, v in summary.items())
        if body:
            lines += ["", body]
        skipped = state.get("skipped") or []
        if skipped:
            from collections import Counter
            why = Counter(str(x.get("reason", "no reason given"))[:60]
                          for x in skipped)
            lines += ["", f"<b>{len(skipped)} passed over without a card</b>"]
            lines += [f"- {esc(r)}  ({n})" for r, n in why.most_common(6)]
        return "\n".join(lines)

    def _resume(self, row: dict, decision) -> None:
        from core.registry import resume_thread
        agent = row.get("agent", "")
        try:
            result = resume_thread(row["thread_id"], decision.to_json(), self.store)
        except Exception as exc:  # noqa: BLE001
            log.error(f"resume failed: {exc}\n{traceback.format_exc()}")
            return self.say(f"I recorded your decision, but the agent could not "
                            f"carry on:\n<code>{esc(str(exc)[:400])}</code>",
                            agent=agent)
        state = result.state or {}
        if result.interrupted:
            # Anything already handed over is posted before the next card, so
            # the order on your phone matches the order it happened in.
            self.post_handoffs(state, agent)
            nxt = self.queue.get(result.approval_id)
            if nxt:
                self.post_approval(nxt, force=True)
        elif result.error:
            self.say(f"The agent stopped with an error:\n"
                     f"<code>{esc(str(result.error)[:400])}</code>", agent=agent)
        else:
            # The run ended on your decision. Without this it ended in silence.
            self.post_handoffs(state, agent)
            self.say(self.finished_text(state, agent), agent=agent)

    # -- main loop -----------------------------------------------------------
    def poll_once(self, timeout: int = 0) -> int:
        offset = self._get("offset") or None
        updates = self.tg.get_updates(offset=offset, timeout=timeout)
        for update in updates:
            self.handle(update)
            self._set("offset", update.id + 1)
        return len(updates)

    def run_forever(self, poll_timeout: int = 25, push_every: float = 20.0) -> None:
        me = self.tg.get_me()
        log.info(f"bot online as @{me.get('username')}")
        try:
            self.tg.delete_webhook()
        except TelegramError:
            pass
        if self.chat_id:
            waiting = len(self.pending_for())
            self.say("I am back online. Send /status to see where things stand."
                     + (f"\n\n<b>{waiting} card(s) are waiting on your decision.</b> "
                        f"Each one is holding up its run. Send /pending to see them."
                        if waiting else ""))
        else:
            print("\nNot bound to a group yet.\n"
                  f"  1. Open Telegram and start a chat with @{me.get('username')}\n"
                  "  2. Make a group, turn on Topics, add the bot as an admin\n"
                  "  3. Send /start in that group\n", flush=True)

        last_push = 0.0
        while not self._stop.is_set():
            try:
                self.poll_once(timeout=poll_timeout)
                if time.time() - last_push > push_every:
                    self.push_pending()
                    last_push = time.time()
            except TelegramError as exc:
                if exc.is_fatal:
                    log.error(f"fatal telegram error: {exc}")
                    raise
                log.warn(f"telegram error: {exc}")
                time.sleep(3)
            except KeyboardInterrupt:
                break
            except Exception as exc:  # noqa: BLE001
                log.error(f"bot loop: {exc}\n{traceback.format_exc()}")
                time.sleep(3)
        log.info("bot stopped")

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------
# notifier channel - lets any agent push a line into the right topic
# ---------------------------------------------------------------------------
_BOT: Bot | None = None


def get_bot(store=None) -> Bot:
    global _BOT
    if _BOT is None:
        _BOT = Bot(store=store)
    return _BOT


def notify(title: str, body: str, agent: str = "", url: str = "") -> str:
    bot = get_bot()
    text = f"<b>{esc(title)}</b>\n\n{esc(body)}"
    if url:
        text += f"\n\n{esc(url)}"
    return "ok" if bot.say(text, agent=agent) else "no chat bound"


def main(argv=None) -> int:
    store = get_store()
    try:
        Bot(store=store).run_forever()
    except ValueError as exc:
        print(f"\n{exc}\n")
        return 1
    except TelegramError as exc:
        print(f"\nTelegram rejected the bot: {exc.description}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
