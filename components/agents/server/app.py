"""Control panel and webhook endpoint. Stdlib http.server, no framework.

Routes
  GET  /                       overview: every agent, everything waiting
  GET  /agent/<name>           one agent: its cards, its rules, its brain
  POST /agent/<name>/run       start that agent from the browser
  GET  /approvals              same as /
  GET  /approvals/<id>         one item, with an edit form
  POST /approvals/<id>/decide  approve / edit / reject, then resume the graph
  GET  /resumes/<file>         download a generated resume PDF
  POST /gmail/push             Gmail Pub/Sub push notifications
  GET  /unsubscribe            one-click opt-out landing page
  POST /unsubscribe            List-Unsubscribe-Post one-click target
  GET  /health                 liveness
  GET  /api/state              JSON snapshot for scripting

Access control: if DASHBOARD_TOKEN is set, every route except /health,
/unsubscribe and /gmail/push requires it - as ?token= or an
Authorization: Bearer header. Bind to 127.0.0.1 unless you have put the
service behind a reverse proxy with TLS.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import config
from core.hitl import APPROVED, EDITED, PENDING, REJECTED, ApprovalQueue
from core.log import get_logger
from core.mailer import SuppressionList, unsubscribe_token
from core.registry import resume_thread
from core.store import get_store
from server import console

log = get_logger("server")

STYLE = """
:root{--bg:#faf9f7;--fg:#1c1b1a;--mut:#6b6a67;--line:#e3e1dd;--card:#fff;
--accent:#b4552d;--ok:#2f7d4f;--bad:#a33;--warn:#8a6d1f}
@media (prefers-color-scheme:dark){:root{--bg:#17161a;--fg:#eceae6;--mut:#a09e99;
--line:#2e2c31;--card:#201f24;--accent:#e07a4e}}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;
background:var(--bg);color:var(--fg)}
.wrap{max-width:1000px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px} h2{font-size:15px;margin:28px 0 10px;
text-transform:uppercase;letter-spacing:.07em;color:var(--mut);font-weight:600}
a{color:var(--accent)} .sub{color:var(--mut);font-size:13px;margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 16px;margin-bottom:10px}
.card h3{margin:0 0 6px;font-size:15px}
.meta{color:var(--mut);font-size:12.5px;margin-bottom:8px}
.badge{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11.5px;
border:1px solid var(--line);margin-right:5px}
.b-pending{color:var(--warn);border-color:var(--warn)}
.b-approved,.b-edited{color:var(--ok);border-color:var(--ok)}
.b-rejected{color:var(--bad);border-color:var(--bad)}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;
overflow-x:auto;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
white-space:pre-wrap;word-break:break-word;margin:8px 0}
textarea,input[type=text]{width:100%;font:13px/1.5 ui-monospace,monospace;padding:8px;
border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
textarea{min-height:220px}
button{font:14px inherit;padding:8px 16px;border-radius:8px;border:1px solid var(--line);
background:var(--card);color:var(--fg);cursor:pointer;margin-right:8px}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.danger{color:var(--bad);border-color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.stat b{display:block;font-size:22px} .stat span{color:var(--mut);font-size:12px}
.empty{color:var(--mut);padding:24px;text-align:center;border:1px dashed var(--line);
border-radius:10px}
label{display:block;font-size:12.5px;color:var(--mut);margin:12px 0 4px}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600}
@media(max-width:560px){.wrap{padding:16px 12px 48px}}
"""


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def page(title: str, body: str) -> bytes:
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><style>{STYLE}</style></head>"
            f"<body><div class='wrap'>{body}</div></body></html>").encode()


def ago(ts: float) -> str:
    d = max(0, time.time() - (ts or 0))
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if d >= n:
            return f"{int(d // n)}{unit} ago"
    return "just now"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AgentSuite"

    # -- plumbing ------------------------------------------------------------
    @property
    def store(self):
        return self.server.store

    @property
    def queue(self) -> ApprovalQueue:
        return self.server.queue

    def log_message(self, fmt, *args):
        # Request lines and malformed-request messages can contain access tokens.
        log.debug("HTTP request", method=self.command)

    def _send(self, status: int, body: bytes, ctype="text/html; charset=utf-8",
              extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store, max-age=0")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, default=str).encode(), "application/json")

    def _redirect(self, to: str):
        self._send(303, b"", extra={"Location": to})

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _form(self) -> dict:
        raw = self._body().decode("utf-8", "replace")
        ctype = self.headers.get("Content-Type", "")
        if "json" in ctype:
            try:
                return json.loads(raw or "{}")
            except json.JSONDecodeError:
                return {}
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def _authorised(self, query: dict) -> bool:
        token = config.get("DASHBOARD_TOKEN", "")
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        given = (header[7:].strip() if header.lower().startswith("bearer ")
                 else (query.get("token", [""])[0] if query else ""))
        return given == token

    # -- routing -------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        parts = urllib.parse.urlsplit(self.path)
        path, query = parts.path.rstrip("/") or "/", urllib.parse.parse_qs(parts.query)

        if path == "/health":
            return self._json(200, {
                "ok": True, "ts": time.time(),
                "service": "storylens-agent-suite" if self.server.integrated else "agent-suite",
                "integrated": self.server.integrated,
            })
        if path == "/api/storylens/status":
            from server.storylens import status
            return status(self)
        if path == "/unsubscribe":
            return self._unsubscribe_page(query)
        if not self._authorised(query):
            return self._send(401, page("Unauthorised",
                                        "<h1>Unauthorised</h1><p class=sub>Append "
                                        "?token=... or send a bearer token.</p>"))
        if path.startswith(('/workflows', '/api/workflows')):
            from server.workflows import WorkflowViews
            if WorkflowViews(self, query).get(path):
                return
        if path in ("/", "/approvals"):
            return self._overview(query)
        if path == "/api/state":
            return self._api_state()
        m = re.match(r"^/agent/([a-z_]+)$", path)
        if m:
            return self._agent_page(m.group(1), query)
        m = re.match(r"^/approvals/([\w.-]+)$", path)
        if m:
            return self._approval_detail(m.group(1), query)
        m = re.match(r"^/resumes/([\w.\- ]+\.pdf)$", path)
        if m:
            return self._serve_resume(m.group(1))
        m = re.match(r"^/attachments/([\w.-]+)/(\d+)$", path)
        if m:
            return self._serve_attachment(m.group(1), int(m.group(2)))
        self._send(404, page("Not found", "<h1>404</h1>"))

    def do_POST(self):  # noqa: N802
        parts = urllib.parse.urlsplit(self.path)
        path, query = parts.path.rstrip("/") or "/", urllib.parse.parse_qs(parts.query)

        if path == "/api/storylens/run":
            from server.storylens import run
            return run(self)
        if path == "/gmail/push":
            return self._gmail_push()
        if path == "/unsubscribe":
            return self._unsubscribe_post(query)
        if not self._authorised(query):
            return self._json(401, {"error": "unauthorised"})
        if path.startswith(('/workflows', '/api/workflows')):
            from server.workflows import WorkflowViews
            if WorkflowViews(self, query).post(path):
                return
        manual = re.match(r"^/leads/([\w.-]+)/sent$", path)
        if manual:
            if console.demo_mode():
                return self._json(403, {"error": "demo mode is read-only"})
            from core.delivery import mark_manual_sent
            mark_manual_sent(self.store, manual.group(1))
            return self._redirect("/" + self._token_qs(query))
        m = re.match(r"^/approvals/([\w.-]+)/decide$", path)
        if m:
            return self._decide(m.group(1), query)
        m = re.match(r"^/agent/([a-z_]+)/run$", path)
        if m:
            return self._run_agent(m.group(1), query)
        self._json(404, {"error": "not found"})

    do_HEAD = do_GET

    # -- views ---------------------------------------------------------------
    def _token_qs(self, query) -> str:
        t = (query.get("token", [""])[0] if query else "")
        return f"?token={urllib.parse.quote(t)}" if t else ""

    # -- the two panes -------------------------------------------------------
    def _counts(self) -> dict:
        """How many cards each agent is holding, for the rail."""
        rows = self.store.query(
            "SELECT agent, COUNT(*) AS n FROM approvals WHERE status=? "
            "GROUP BY agent", (PENDING,))
        counts: dict = {"_all": 0}
        for r in rows:
            n = int(r["n"])
            counts["_all"] += n
            home = console.home_for(r["agent"])
            if home:
                counts[home] = counts.get(home, 0) + n
        return counts

    def _rail(self, active: str, query) -> str:
        return console.rail(active, self._counts(), self._token_qs(query),
                            self.server.runs, integrated=self.server.integrated)

    def _overview(self, query):
        """Everything, across all five. The page he lands on."""
        pending = self.queue.pending()
        recent = self.queue.recent(25)
        qs = self._token_qs(query)
        leads = self.store.query("SELECT COUNT(*) AS n FROM leads") or [{"n": 0}]

        decided_today = sum(1 for a in recent if a["status"] != PENDING
                            and (a.get("decided_at") or 0) > time.time() - 86400)
        stats = [(len(pending), "waiting on you"),
                 (decided_today, "decided today"),
                 (int(leads[0]["n"]), "targets found"),
                 (sum(1 for a in console.AGENTS if a["runnable"]), "agents live")]
        tiles = "".join(f"<div class=stat><b>{v}</b><span>{k}</span></div>"
                        for v, k in stats)

        if pending:
            cards = "".join(console.pending_card(a, qs) for a in pending[:12])
            more = (f"<p class=hint>{len(pending) - 12} more - open an agent on "
                    f"the left to see the rest.</p>" if len(pending) > 12 else "")
        else:
            cards = console.empty(
                "Nothing waiting on you",
                "Open an agent on the left and press Run to put it to work.")
            more = ""

        rows = "".join(
            f"<tr><td><span class='tag {console.esc(a['status'])}'>"
            f"{console.esc(a['status'])}</span></td>"
            f"<td>{console.esc(a['title'][:70])}</td>"
            f"<td>{console.esc(console.display_name(a['agent']))}</td>"
            f"<td>{console.ago(a.get('decided_at') or a['created_at'])}</td></tr>"
            for a in recent if a["status"] != PENDING) or (
            "<tr><td colspan=4 class=meta>Nothing decided yet.</td></tr>")

        pane = f"""
            <div class=ptop><h1>Everything</h1></div>
            <p class=lede>Your agents look for work, draft what they would
            send, and stop. Nothing leaves this machine until you say so.</p>
            {self._demo_note()}
            <div class=stats>{tiles}</div>
            <h2>How it works</h2>{console.how_it_works()}
            <h2>Waiting for you ({len(pending)})</h2>{cards}{more}
            <h2>What you decided</h2>
            <div class='panelbox scroll'><table><tr><th>You said</th><th>About</th>
            <th>Agent</th><th>When</th></tr>{rows}</table></div>"""
        self._send(200, console.shell("Agent Suite",
                                      self._rail("home", query), pane))

    def _demo_note(self) -> str:
        if not console.demo_mode():
            return ""
        return ("<p class=note><b>Demo mode.</b> Email addresses and phone "
                "numbers are hidden and nothing can be approved, rejected or "
                "run. Turn it off with DEMO_MODE=false.</p>")

    def _agent_page(self, key: str, query):
        meta = console.agent_meta(key)
        if meta is None:
            return self._send(404, console.shell(
                "Not found", self._rail("home", query),
                "<h1>No such agent</h1><p class=lede>Pick one from the left.</p>"))
        qs = self._token_qs(query)
        pending = [a for a in self.queue.pending()
                   if console.home_for(a["agent"]) == key]
        recent = [a for a in self.queue.recent(60)
                  if console.home_for(a["agent"]) == key]

        # what it taught itself
        try:
            from core.lessons import get_lessons
            rules = get_lessons(key, self.store).all()
        except Exception as exc:  # noqa: BLE001
            log.warn(f"lessons unavailable for {key}: {exc}")
            rules = []

        # what it has come to believe
        try:
            mod_name, cls_name = meta["brain"]
            mod = __import__(mod_name, fromlist=[cls_name])
            brain = getattr(mod, cls_name)(self.store).summary()
        except Exception as exc:  # noqa: BLE001
            log.warn(f"brain unavailable for {key}: {exc}")
            brain = {}

        run_state = self._agent_state(key)
        updates = self.store.query("SELECT payload_json FROM events WHERE agent=? "
                                    "AND kind='notification' ORDER BY ts DESC LIMIT 4", (key,))
        activity = "".join(f"<p class=hint>{console.esc(json.loads(r['payload_json']).get('body', ''))}</p>"
                           for r in updates)
        handoffs = self.store.query("SELECT * FROM leads WHERE agent=? AND status=? "
                                     "ORDER BY updated_at DESC LIMIT 30", (key, "ready_to_send"))
        handoff_html = ""
        for lead in handoffs:
            data = json.loads(lead.get("data_json") or "{}")
            draft = data.get("draft") or {}
            if draft:
                handoff_html += (f"<article class=card><h3>{console.esc(lead['company'])}</h3>"
                    f"<pre>{console.esc(draft.get('subject', ''))}\n\n{console.esc(draft.get('body', ''))}</pre>"
                    f"<a class=btn href='{html.escape(lead['source_url'], quote=True)}' target=_blank "
                    f"rel=noopener>Open destination</a>"
                    + ("" if console.demo_mode() else
                       f"<form method=post action='/leads/{console.esc(lead['id'])}/sent{qs}'>"
                       "<button class=go>I've sent this</button></form>") + "</article>")
        research_link = (f"<p><a class=btn href='/workflows{qs}#saas-demand'>Open SaaS demand research</a></p>"
                         if self.server.integrated and key == "saas_sales" else "")
        pane = f"""
            <div class=ptop><h1>{console.esc(meta['name'])}</h1>
            {self._run_box(meta, run_state, qs)}</div>
            <p class=lede>{console.esc(meta['does'])}</p>
            {research_link}
            {self._demo_note()}
            {self._run_status(run_state, qs)}{activity}
            {('<h2>Ready for you to send</h2>' + handoff_html) if handoff_html else ''}
            <h2>Waiting for you ({len(pending)})</h2>
            {"".join(console.pending_card(a, qs) for a in pending)
             or console.empty("Nothing waiting",
                              "Press Run and it will go and find some.")}
            <h2>What it learned from you</h2>
            <p class=hint>Every rule here was written by the agent itself after
            you rejected or rewrote one of its drafts.</p>
            {console.lessons_block(rules)}
            <h2>What it has come to believe</h2>
            {console.brain_block(brain)}
            <h2>History</h2>
            {console.history_table(recent, PENDING)}"""
        self._send(200, console.shell(f"{meta['name']} - Agent Suite",
                                      self._rail(key, query), pane))

    def _agent_state(self, key):
        memory = self.server.runs.get(key)
        if memory and memory["status"] == "running":
            return memory
        row = self.store.one("SELECT status,updated_at FROM threads WHERE agent=? "
                              "ORDER BY updated_at DESC LIMIT 1", (key,))
        if row and (not memory or row["updated_at"] > memory["finished"]):
            status = row["status"]
            if status in ("running", "ok"):
                status = "stale" if time.time() - row["updated_at"] > 900 else "running"
            elif status == "interrupted":
                status = "waiting for you"
            return {"status": status, "finished": row["updated_at"]}
        return memory or {}

    def _run_box(self, meta: dict, state: dict, qs: str) -> str:
        if not meta["runnable"]:
            return "<span class=tag>parked</span>"
        if console.demo_mode():
            return "<span class=tag>read-only demo</span>"
        busy = state.get("status") == "running"
        return (f"<form method=post action='/agent/{meta['key']}/run{qs}'>"
                f"<button class=go {'disabled' if busy else ''}>"
                f"{'Working...' if busy else 'Find editing work' if self.server.integrated and meta['key'] == 'video_client' else 'Run it now'}</button></form>")

    def _run_status(self, state: dict, qs: str) -> str:
        if not state:
            return ""
        status = state.get("status", "")
        if status == "running":
            return ("<meta http-equiv=refresh content=8><p class=working>Working. It reads pages and drafts text, "
                    "so give it a minute, then reload this page.</p>")
        if status == "stale":
            return "<p class=note>This run has been quiet for a while. Check its logs before restarting.</p>"
        if status == "waiting for you":
            return "<p class=note>A card waiting for you is holding up this run.</p>"
        if status == "error":
            return (f"<p class=note><b>That run stopped.</b> "
                    f"{console.esc(state.get('error', ''))}</p>")
        if status:
            return (f"<p class=note>Last run: <b>{console.esc(status)}</b>, "
                    f"{console.ago(state.get('finished'))}.</p>")
        return ""

    def _run_agent(self, key: str, query):
        """Start an agent in the background and come straight back."""
        meta = console.agent_meta(key)
        if meta is None:
            return self._json(404, {"error": "no such agent"})
        if console.demo_mode():
            return self._json(403, {"error": "demo mode is read-only"})
        if not meta["runnable"]:
            return self._json(409, {"error": "this agent is parked"})
        code, payload = self._start_agent(key, meta)
        if "json" in (self.headers.get("Accept", "")
                      + self.headers.get("Content-Type", "")):
            return self._json(code, payload)
        return self._redirect(payload["url"] + self._token_qs(query))

    def _start_agent(self, key: str, meta: dict):
        store, srv = self.store, self.server
        url = f"/agent/{key}"
        with srv.runs_lock:
            names = (key, *(alias for alias, home in console.ALIASES.items() if home == key))
            slots = ",".join("?" for _ in names)
            waiting = self.store.one(
                f"SELECT id FROM approvals WHERE status=? AND agent IN ({slots}) ORDER BY created_at LIMIT 1",
                (PENDING, *names),
            )
            if waiting and not (srv.integrated and key == "video_client"):
                return 409, {"status": "waiting for you", "error": "A review is pending.",
                             "url": f"/approvals/{waiting['id']}"}
            if (srv.runs.get(key) or {}).get("status") == "running":
                return 409, {"status": "running", "error": "This agent is already running.", "url": url}
            srv.runs[key] = {"status": "running", "started": time.time()}

        def work():
            started = time.time()
            try:
                mod = __import__(meta["module"], fromlist=["make"])
                options = {"sweep": True} if srv.integrated and key == "video_client" else {}
                result = mod.make(store=store).run(thread_id=f"{key}-{time.time_ns()}", **options)
                status = ("waiting for you" if result.interrupted
                          else result.status)
                srv.runs[key] = {"status": status, "started": started,
                                 "finished": time.time(),
                                 "approval_id": result.approval_id or "",
                                 "error": result.error or ""}
            except Exception as exc:  # noqa: BLE001
                log.exception(f"browser-started run of {key} failed")
                srv.runs[key] = {"status": "error", "started": started,
                                 "finished": time.time(), "error": str(exc)[:300]}

        threading.Thread(target=work, daemon=True, name=f"run-{key}").start()
        return 202, {"started": key, "status": "running", "url": url}

    def _preview(self, a: dict) -> str:
        return console.preview(a)

    def _approval_detail(self, aid: str, query):
        a = self.queue.get(aid)
        if a and a['kind'] == 'workflow_review':
            return self._redirect('/workflows/' + a['thread_id'] + self._token_qs(query))
        if a is None:
            return self._send(404, console.shell(
                "Not found", self._rail("home", query),
                "<h1>No such card</h1>"))
        p = a["payload"]
        qs = self._token_qs(query)
        decided = a["status"] != PENDING
        meta = (console.agent_meta(console.home_for(a["agent"]))
                or {"name": a["agent"], "key": a["agent"]})

        extra = ""
        if a["kind"] == "send_quote":
            q = p.get("quote", {}) or {}
            extra = (f"<label>How the price was worked out</label>"
                     f"<pre>{console.esc(p.get('breakdown', ''))}</pre>"
                     f"<label>Change the total ({console.esc(q.get('currency', ''))}) "
                     f"- leave it blank to keep {console.money(q.get('total'))}</label>"
                     f"<input type=text name=total inputmode=decimal "
                     f"placeholder='{console.money(q.get('total'))}'>")
        if a["kind"] == "apply_to_job":
            fname = pathlib.Path(p.get("resume_path", "")).name
            extra = (f"<label>Why it is not a scam</label>"
                     f"<pre class=code>{console.esc(json.dumps(p.get('screen'), indent=1, default=str))}</pre>"
                     f"<label>How the resume was tailored</label>"
                     f"<pre class=code>keyword coverage: {p.get('keyword_coverage', 0):.0%}\n"
                     f"claims removed: {console.esc(p.get('stripped_claims'))}\n"
                     f"notes: {console.esc(p.get('tailoring_notes'))}</pre>")
            if fname:
                extra += (f"<div class=row><a class=btn href='/resumes/"
                          f"{console.esc(fname)}{qs}'>Download the tailored "
                          f"resume</a></div>")
        if p.get("lint"):
            extra += ("<label>Checks</label><pre class=code>"
                      + console.esc("\n".join(p["lint"])) + "</pre>")
        for index, attachment in enumerate(p.get("attachments") or []):
            extra += (f"<a class=btn href='/attachments/{console.esc(aid)}/{index}{qs}' target=_blank "
                      f"rel=noopener>Review {console.esc(pathlib.Path(attachment).name)}</a>")
        if p.get("their_message"):
            extra += ("<label>What they wrote to you</label>"
                      f"<pre>{console.esc(p['their_message'])}</pre>")
        if p.get("tools_used"):
            extra += ("<label>What it looked up before writing</label>"
                      f"<pre class=code>{console.esc(str(p['tools_used'])[:600])}"
                      f"</pre>")

        hand = console.handoff_links(dict(p, _kind=a["kind"]))
        hand_html = ("<div class=row>" + "".join(
            f"<a class=btn target=_blank rel=noopener href='{html.escape(u, quote=True)}'>"
            f"{html.escape(label)}</a>" for label, u in hand) + "</div>"
            if hand else "")

        editable = a["kind"] != "apply_to_job"
        if decided:
            # What actually went out, not just the verdict - this is the page
            # he comes back to when he wants to know what he already said.
            sent = ""
            if p.get("subject"):
                sent += (f"<label>Subject</label>"
                         f"<pre>{console.esc(p['subject'])}</pre>")
            text = p.get("body") or p.get("whatsapp_text")
            if text:
                sent += f"<label>Message</label><pre>{console.esc(text)}</pre>"
            form = (sent + f"<label>What you decided</label><pre>"
                    f"{console.esc(json.dumps(a.get('decision'), indent=1, default=str))}"
                    f"</pre>{extra}").replace(
                        "<label>What you decided</label><pre>",
                        "<label>What you decided</label><pre class=code>")
        elif console.demo_mode():
            form = ("<p class=note>Demo mode - this card can be read but not "
                    "decided.</p>"
                    + (f"<label>Subject</label><pre>{console.esc(p.get('subject', ''))}</pre>"
                       if p.get("subject") else "")
                    + (f"<label>Message</label><pre>{console.esc(p.get('body', ''))}</pre>"
                       if p.get("body") else "") + extra)
        else:
            sub = (f"<label>Subject</label><input type=text name=subject "
                   f"value='{html.escape(str(p.get('subject', '')), quote=True)}'>"
                   if editable and p.get("subject") else "")
            bod = (f"<label>Message - edit it and your edit is what gets sent"
                   f"</label><textarea name=body>{console.esc(p.get('body', ''))}"
                   f"</textarea>" if editable and p.get("body") else "")
            yes, no = console.verbs(a["kind"])
            if a["kind"] == "submit_application":
                bod = (f"<label>Observed form fields</label><pre>{console.esc(p.get('body', ''))}</pre>"
                       f"<label>Answers by exact field label (JSON)</label>"
                       f"<textarea name=answers_json>{console.esc(json.dumps(p.get('answers', {}), indent=2))}</textarea>"
                       f"<p class=note>Missing: {console.esc(', '.join(p.get('missing_fields', [])))} "
                       f"{console.esc(p.get('blocked', ''))}</p>")
            form = (f"<form method=post action='/approvals/{console.esc(aid)}/decide{qs}'>"
                    f"{sub}{bod}{extra}"
                    f"<label>Tell it why (optional - this is what it learns from)"
                    f"</label><input type=text name=note "
                    f"placeholder='not a fit / too long / wrong person / price is low'>"
                    f"<div class=row>"
                    f"<button class=go name=action value=approve>{yes}</button>"
                    f"<button class=no name=action value=reject>{no}</button>"
                    f"</div></form>")

        pane = (f"<p class=hint><a href='/agent/{console.esc(meta['key'])}{qs}'>"
                f"&larr; {console.esc(meta['name'])}</a></p>"
                f"<h1>{console.esc(a['title'])}</h1>"
                f"<div class=meta><span class='tag {console.esc(a['status'])}'>"
                f"{console.esc(a['status'])}</span>"
                f"<span class=tag>{console.esc(a['kind'])}</span>"
                f"<span>{console.ago(a['created_at'])}</span></div>"
                f"{self._context_block(p)}{hand_html}{form}")
        self._send(200, console.shell(
            a["title"], self._rail(console.home_for(a["agent"]), query), pane))

    def _context_block(self, p: dict) -> str:
        """Why this target, in his words rather than the model's JSON."""
        bits = []
        why = p.get("why")
        if isinstance(why, list) and why:
            # The brain's working, not prose. Shown as what it counted.
            bits.append("<label>How it scored them</label><pre class=code>"
                        + console.esc("\n".join(str(w) for w in why[:10]))
                        + "</pre>")
        elif isinstance(why, str) and why.strip() and why != p.get("fit"):
            bits.append("<label>How it decided</label>"
                        f"<pre>{console.esc(why[:600])}</pre>")
        for key, label in (("note", "What was found"),
                           ("payout", "What they pay"),
                           ("fit", "Why them"),
                           ("reads_as", "What it read on their site"),
                           ("evidence", "Where the address came from"),
                           ("location", "Where"),
                           ("salary", "Pay")):
            if p.get(key):
                bits.append(f"<label>{label}</label>"
                            f"<pre>{console.esc(str(p[key])[:600])}</pre>")
        if p.get("invoice_status"):
            bits.append(f"<p class=note>Invoice: {console.esc(p['invoice_status'].replace('_', ' '))}</p>")
        if p.get("guessed"):
            bits.append("<p class=note>This address was worked out, not "
                        "published by them. Worth a look before you send.</p>")
        return "".join(bits)

    def _decide(self, aid: str, query):
        if console.demo_mode():
            return self._json(403, {"error": "demo mode is read-only"})
        form = self._form()
        action = (form.get("action") or "").lower()
        note = form.get("note", "")
        a = self.queue.get(aid)
        if a is None:
            return self._json(404, {"error": "no such approval"})
        if a["status"] != PENDING:
            return self._json(409, {"error": f"already {a['status']}"})
        if a['kind'] == 'workflow_review':
            from core.workflow_service import WorkflowService
            try:
                if action not in ('approve', 'reject'):
                    raise ValueError('Choose approve or reject; revise the task to change its payload')
                if any(k in form for k in ('body', 'subject', 'total', 'answers_json')):
                    raise ValueError('Exact workflow reviews cannot be edited; create a task revision')
                task = WorkflowService(self.store).decide(a['thread_id'], action == 'approve', aid)
                if 'json' in self.headers.get('Accept', '') + self.headers.get('Content-Type', ''):
                    return self._json(200, task)
                return self._redirect('/workflows/' + a['thread_id'] + self._token_qs(query))
            except (ValueError, RuntimeError, PermissionError) as exc:
                return self._json(409, {'error': str(exc)})

        if action in ("reject", "no", "decline"):
            decision = self.queue.reject(aid, note=note)
        else:
            edits = {}
            original = a["payload"]
            if "answers_json" in form:
                try:
                    answers = json.loads(form["answers_json"])
                    if not isinstance(answers, dict):
                        raise ValueError("Answers must be a JSON object")
                    edits["answers"] = answers
                except (ValueError, TypeError) as exc:
                    return self._json(400, {"error": str(exc)})
            for field in ("subject", "body"):
                if field in form and form[field] != original.get(field):
                    edits[field] = form[field]
            if form.get("total"):
                try:
                    edits["total"] = float(str(form["total"]).replace(",", ""))
                except ValueError:
                    pass
            decision = self.queue.approve(aid, edits=edits or None, note=note)

        try:
            result = resume_thread(a["thread_id"], decision.to_json(), self.store)
            outcome = result.status
        except Exception as exc:  # noqa: BLE001
            log.exception("resume failed")
            outcome = f"error: {exc}"

        if "json" in (self.headers.get("Accept", "") + self.headers.get("Content-Type", "")):
            return self._json(200, {"decision": decision.to_json(), "run": outcome})
        self._redirect("/" + self._token_qs(query))

    def _api_state(self):
        counts = self._counts()
        self._json(200, {
            "agents": [{"key": a["key"], "name": a["name"],
                        "runnable": a["runnable"],
                        "pending": counts.get(a["key"], 0)}
                       for a in console.AGENTS],
            "runs": getattr(self.server, "runs", {}),
            "pending": self.queue.pending(),
            "recent": self.queue.recent(25),
            "events": self.store.recent_events(25),
            "leads": self.store.query(
                "SELECT agent, status, COUNT(*) AS n FROM leads GROUP BY agent, status"),
        })

    def _serve_attachment(self, aid: str, index: int):
        if console.demo_mode():
            return self._json(403, {"error": "Documents are hidden in demo mode"})
        approval = self.queue.get(aid)
        paths = ((approval or {}).get("payload") or {}).get("attachments") or []
        if index >= len(paths):
            return self._json(404, {"error": "No such attachment"})
        target = pathlib.Path(paths[index]).resolve()
        try:
            target.relative_to(config.data_dir().resolve())
        except ValueError:
            return self._json(403, {"error": "Attachment is outside the document directory"})
        if target.suffix.lower() != ".pdf" or not target.is_file():
            return self._json(404, {"error": "No such PDF"})
        self._send(200, target.read_bytes(), "application/pdf")

    def _serve_resume(self, filename: str):
        if console.demo_mode():
            # His actual resume, with his actual phone number on it.
            return self._send(403, console.shell(
                "Hidden", "", "<h1>Hidden in demo mode</h1><p class=lede>"
                "The tailored resume is a real document with real contact "
                "details on it.</p>"))
        base = pathlib.Path(config.get("RESUME_OUTPUT_DIR",
                                       str(config.data_dir() / "resumes"))).resolve()
        target = (base / filename).resolve()
        if not str(target).startswith(str(base)) or not target.exists():
            return self._send(404, page("Not found", "<h1>No such file</h1>"))
        self._send(200, target.read_bytes(), "application/pdf",
                   {"Content-Disposition": f'inline; filename="{filename}"'})

    # -- webhooks ------------------------------------------------------------
    def _gmail_push(self):
        """Pub/Sub push. Acknowledge fast; the delta fetch happens inline."""
        expected = config.get("PUBSUB_TOKEN", "")
        if expected:
            got = urllib.parse.parse_qs(
                urllib.parse.urlsplit(self.path).query).get("token", [""])[0]
            if got != expected:
                return self._json(401, {"error": "bad token"})
        try:
            payload = json.loads(self._body() or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        handler = getattr(self.server, "on_gmail_push", None)
        if handler is None:
            log.warn("gmail push received but no handler is wired up")
            return self._json(204, {})
        try:
            count = handler(payload)
        except Exception as exc:  # noqa: BLE001
            log.exception("gmail push handler failed")
            # 200 anyway: Pub/Sub retries aggressively and a poison message
            # would otherwise loop forever. The error is logged and alertable.
            return self._json(200, {"ok": False, "error": str(exc)})
        return self._json(200, {"ok": True, "processed": count})

    def _unsubscribe_page(self, query):
        addr = (query.get("e", [""])[0] or "").strip().lower()
        tok = query.get("t", [""])[0]
        if not addr or tok != unsubscribe_token(addr):
            return self._send(400, page("Unsubscribe",
                                        "<h1>That link is not valid</h1>"
                                        "<p class=sub>Reply to the email with the "
                                        "word unsubscribe and you will be removed."
                                        "</p>"))
        SuppressionList(self.store).add(addr, reason="one-click unsubscribe")
        self._send(200, page("Unsubscribed", f"""
            <h1>Removed</h1>
            <p class=sub>{esc(addr)} will not be contacted again.</p>"""))

    def _unsubscribe_post(self, query):
        addr = (query.get("e", [""])[0] or "").strip().lower()
        tok = query.get("t", [""])[0]
        if addr and tok == unsubscribe_token(addr):
            SuppressionList(self.store).add(addr, reason="one-click unsubscribe")
            return self._json(200, {"ok": True})
        return self._json(400, {"ok": False})


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, store=None, on_gmail_push=None):
        super().__init__(addr, Handler)
        self.store = store or get_store()
        self.queue = ApprovalQueue(self.store)
        self.on_gmail_push = on_gmail_push
        # What a browser-started run is doing right now, per agent. In memory
        # on purpose: a run that was going when the process died is not going
        # any more, and saying so in the database would be a lie that outlives
        # the restart.
        self.runs: dict = {}
        self.runs_lock = threading.Lock()
        self.integrated = config.get_bool("SUITE_STORYLENS_INTEGRATED")


def serve(host: str | None = None, port: int | None = None, store=None,
          on_gmail_push=None) -> DashboardServer:
    host = host or config.get("DASHBOARD_HOST", "127.0.0.1")
    port = port or config.get_int("DASHBOARD_PORT", 8080)
    srv = DashboardServer((host, port), store=store, on_gmail_push=on_gmail_push)
    token = config.get("DASHBOARD_TOKEN", "")
    log.info(f"dashboard on http://{host}:{port}"
             + ("  (no token set - bind to localhost only)" if not token else ""))
    return srv
