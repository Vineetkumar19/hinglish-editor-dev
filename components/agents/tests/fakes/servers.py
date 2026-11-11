"""Local servers that speak the real protocols the agents talk to.

These are not mocks of our own code - they are stand-in *servers*. The agents
make genuine HTTP requests, parse genuine responses, and run every line of the
production code path. Only the base URLs differ from production.

  FakeWebServer      - prospect websites, robots.txt, contact/about pages
  FakeGoogleServer   - OAuth2 token endpoint + the Gmail v1 REST surface we use
                       (profile, watch, history.list, messages.get/send/modify)
                       and the Calendar events endpoint
  FakeAnthropicServer- the Messages API, so the LLM layer is exercised for real
  FakeSMTPServer     - an SMTP server that accepts and records mail
"""
from __future__ import annotations

import base64
import email
import email.policy
import json
import re
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


_real_getaddrinfo = socket.getaddrinfo
_dns_overrides: dict[str, int] = {}
_dns_lock = threading.Lock()


def _patched_getaddrinfo(host, port, *args, **kwargs):
    """Resolve the fake domains to loopback, for this process only.

    The alternative is editing /etc/hosts, which needs admin rights and does
    not travel with the repo. Patching resolution here means the crawler still
    builds real absolute URLs, does a real DNS lookup and opens a real socket -
    the only thing that changes is where the name points. Tests therefore run
    on any machine, as any user, with no setup.
    """
    with _dns_lock:
        mapped = _dns_overrides.get(str(host).lower().removeprefix("www."))
    if mapped is not None:
        return _real_getaddrinfo("127.0.0.1", mapped, *args, **kwargs)
    return _real_getaddrinfo(host, port, *args, **kwargs)


def install_dns_override(domains, port: int) -> None:
    with _dns_lock:
        for d in domains:
            _dns_overrides[d.lower()] = port
    if socket.getaddrinfo is not _patched_getaddrinfo:
        socket.getaddrinfo = _patched_getaddrinfo


def remove_dns_override(domains) -> None:
    with _dns_lock:
        for d in domains:
            _dns_overrides.pop(d.lower(), None)
        empty = not _dns_overrides
    if empty:
        socket.getaddrinfo = _real_getaddrinfo


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Base(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class BaseFake:
    handler_cls = None

    def __init__(self, port: int | None = None):
        self.port = port or _free_port()
        self.requests: list[tuple[str, str]] = []
        self.server = _Base(("127.0.0.1", self.port), self._make_handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _make_handler(self):
        outer = self

        class Handler(self.handler_cls):
            fake = outer

            def log_message(self, *a):
                pass

        return Handler

    def start(self) -> "BaseFake":
        self.thread.start()
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", self.port), 0.2):
                    return self
            except OSError:
                time.sleep(0.02)
        raise RuntimeError("fake server did not come up")

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()


class _HTTPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8",
              extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj).encode(), "application/json")

    def _record(self) -> None:
        self.fake.requests.append((self.command, self.path))


# --------------------------------------------------------------------------
# fake prospect websites
# --------------------------------------------------------------------------
SITES: dict[str, dict[str, str]] = {}


def _site_page(title: str, body: str, extra_head: str = "") -> str:
    return (f"<!doctype html><html><head><title>{title}</title>{extra_head}"
            f"</head><body>{body}</body></html>")


def register_default_sites() -> None:
    SITES.clear()
    SITES["fantasy.example"] = {
        "/": _site_page(
            "Example Fantasy - Fantasy Cricket India",
            "<h1>Example Fantasy</h1><p>Daily fantasy cricket contests for Indian "
            "fans. Over two million players.</p>"
            "<a href='/partnerships'>Creator partnerships</a> "
            "<a href='/about'>About</a> <a href='/contact'>Contact</a>"
            "<a href='https://linkedin.com/company/examplefantasy'>LinkedIn</a>"
            "<script src='/_next/static/chunk.js'></script>",
            "<meta name='description' content='Example Fantasy is an Indian fantasy "
            "cricket platform running daily contests for two million players.'>"),
        "/partnerships": _site_page(
            "Creator partnerships - Example Fantasy",
            "<h1>Creator partnership programme</h1><p>We work with cricket creators "
            "across YouTube and Instagram. For sponsorship enquiries write to "
            "<a href='mailto:partnerships@fantasy.example'>partnerships@fantasy.example</a>.</p>"),
        "/about": _site_page(
            "About - Example Fantasy",
            "<h1>Our team</h1><p>Priya Rao, Head of Partnerships - "
            "priya.rao@fantasy.example</p><p>Arjun Mehta, Marketing Director</p>"),
        "/contact": _site_page(
            "Contact", "<p>Call +91 98765 43210. General: hello@fantasy.example</p>"),
        "/robots.txt": "User-agent: *\nDisallow: /admin\nCrawl-delay: 0\n",
    }
    SITES["gear.example"] = {
        "/": _site_page(
            "Example Cricket Gear",
            "<h1>Example Cricket Gear</h1><p>Bats, pads and kit since 1998.</p>"
            "<a href='/contact'>Contact us</a>",
            "<meta name='description' content='Example Cricket Gear sells bats, pads "
            "and club kit across India.'>"),
        "/contact": _site_page(
            "Contact",
            "<p>Write to sales (at) gear (dot) example or call 022-2345 6789</p>"),
        "/robots.txt": "User-agent: *\nDisallow: /\n",     # opts out entirely
    }
    SITES["analytics.example"] = {
        "/": _site_page(
            "Example Sports Analytics",
            "<h1>Ball-by-ball cricket data</h1><p>An API for cricket statistics used "
            "by broadcasters.</p><a href='/media'>Media partnerships</a>",
            "<meta name='description' content='Example Sports Analytics provides a "
            "ball-by-ball cricket statistics API used by broadcasters.'>"),
        "/media": _site_page(
            "Media partnerships",
            "<p>Media and collaboration enquiries: media@analytics.example</p>"),
        "/robots.txt": "User-agent: *\nCrawl-delay: 0\n",
    }
    SITES["creatorstudio.example"] = {
        "/": _site_page(
            "Rohit's Cricket Channel",
            "<h1>Rohit's Cricket Channel</h1><p>Match breakdowns twice a week. "
            "Currently editing everything myself and looking for help.</p>"
            "<a href='/contact'>Work with me</a>"
            "<a href='https://youtube.com/@rohitcricket'>YouTube</a>",
            "<meta name='description' content='Rohit publishes cricket match "
            "breakdown videos twice a week on YouTube.'>"),
        "/contact": _site_page(
            "Work with me", "<p>Business: rohit@creatorstudio.example</p>"),
        "/robots.txt": "User-agent: *\nCrawl-delay: 0\n",
    }
    SITES["saas.example"] = {
        "/": _site_page(
            "Example SaaS - Invoicing for freelancers",
            "<h1>Example SaaS</h1><p>Invoicing software for Indian freelancers. "
            "Our site was last redesigned in 2016.</p>"
            "<a href='/about'>About</a>",
            "<meta name='description' content='Example SaaS is invoicing software "
            "for Indian freelancers.'><script src='/js/jquery-1.9.min.js'></script>"
            "<link rel='stylesheet' href='/css/bootstrap.min.css'>"),
        "/about": _site_page(
            "About", "<p>Founded by Sanjay Kumar, CEO. Reach him at "
            "sanjay.kumar@saas.example</p>"),
        "/robots.txt": "User-agent: *\nCrawl-delay: 0\n",
    }
    SITES["noemail.example"] = {
        "/": _site_page("No Email Co", "<h1>No Email Co</h1>"
                        "<p>Phone only: +91 90000 11111</p>"),
        "/robots.txt": "User-agent: *\nCrawl-delay: 0\n",
    }


class _WebHandler(_HTTPHandler):
    """Routes by the Host header, exactly like a real virtual-host web server.

    The test domains resolve to 127.0.0.1 via /etc/hosts, so the crawler builds
    and follows ordinary absolute URLs - no test-only code path in the crawler.
    """

    def do_GET(self):  # noqa: N802
        self._record()
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        host = host.removeprefix("www.")
        path = urllib.parse.urlsplit(self.path).path or "/"
        site = SITES.get(host)
        if site is None:
            self._send(404, b"<h1>unknown host</h1>")
            return
        content = site.get(path)
        if content is None and path != "/":
            content = site.get(path.rstrip("/"))
        if content is None and path in ("", "/"):
            content = site.get("/")
        if content is None:
            self._send(404, b"<h1>404</h1>")
            return
        ctype = ("text/plain; charset=utf-8" if path.endswith(".txt")
                 else "text/html; charset=utf-8")
        self._send(200, content.encode(), ctype, {"Server": "fakeweb"})


class FakeWebServer(BaseFake):
    """Serves the fake prospect sites on their real-looking hostnames.

    Binds an ephemeral loopback port (so no admin rights and no clash with
    anything already on port 80) and redirects DNS for the fake domains to it,
    so `http://fantasy.example/` resolves here and nowhere else.
    """
    handler_cls = _WebHandler

    def __init__(self, port: int | None = None):
        register_default_sites()
        super().__init__(port)

    def start(self):
        install_dns_override(SITES.keys(), self.port)
        return super().start()

    def stop(self) -> None:
        remove_dns_override(SITES.keys())
        super().stop()

    def site_url(self, domain: str) -> str:
        return f"http://{domain}/"


# --------------------------------------------------------------------------
# fake Google: OAuth2 token endpoint + Gmail v1 + Calendar v3
# --------------------------------------------------------------------------
def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


class _GoogleState:
    """In-memory Gmail mailbox with a real history log."""

    def __init__(self):
        self.messages: dict[str, dict] = {}
        self.history: list[dict] = []       # [{id, messagesAdded:[{message}]}]
        self.next_history = 1000
        self.sent: list[dict] = []
        self.watch: dict = {}
        self.events: list[dict] = []
        self.busy: list[dict] = []
        self.access_tokens: dict[str, float] = {}
        self.refresh_count = 0

    def deliver(self, *, sender: str, subject: str, body: str, to: str = "me@example.com",
                message_id: str | None = None, in_reply_to: str = "",
                thread_id: str | None = None, headers: dict | None = None,
                html_body: str | None = None) -> dict:
        self.next_history += 1
        mid = f"msg{len(self.messages) + 1:04d}"
        tid = thread_id or f"thr{len(self.messages) + 1:04d}"
        hdrs = [{"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "To", "value": to},
                {"name": "Message-ID", "value": message_id or f"<{mid}@fake>"},
                {"name": "Date", "value": time.strftime("%a, %d %b %Y %H:%M:%S +0000")}]
        if in_reply_to:
            hdrs.append({"name": "In-Reply-To", "value": in_reply_to})
            hdrs.append({"name": "References", "value": in_reply_to})
        for k, v in (headers or {}).items():
            hdrs.append({"name": k, "value": v})
        parts = [{"mimeType": "text/plain",
                  "body": {"data": base64.urlsafe_b64encode(
                      body.encode()).decode().rstrip("=")}}]
        if html_body:
            parts.append({"mimeType": "text/html",
                          "body": {"data": base64.urlsafe_b64encode(
                              html_body.encode()).decode().rstrip("=")}})
        msg = {"id": mid, "threadId": tid, "historyId": str(self.next_history),
               "labelIds": ["INBOX", "UNREAD"],
               "snippet": body[:120].replace("\n", " "),
               "internalDate": str(int(time.time() * 1000)),
               "payload": {"mimeType": "multipart/alternative",
                           "headers": hdrs, "parts": parts}}
        self.messages[mid] = msg
        self.history.append({"id": str(self.next_history),
                             "messagesAdded": [{"message": {
                                 "id": mid, "threadId": tid,
                                 "labelIds": ["INBOX", "UNREAD"]}}]})
        return msg


GOOGLE = _GoogleState()


class _GoogleHandler(_HTTPHandler):
    def _auth_ok(self) -> bool:
        return (self.headers.get("Authorization", "")
                .lower().startswith("bearer "))

    def do_POST(self):  # noqa: N802
        self._record()
        parts = urllib.parse.urlsplit(self.path)
        path = parts.path
        body = self._read_body()
        st = GOOGLE

        if path == "/token":
            form = {k: v[0] for k, v in
                    urllib.parse.parse_qs(body.decode()).items()}
            if form.get("grant_type") == "refresh_token":
                if form.get("refresh_token") != "fake-refresh-token":
                    return self._json(400, {"error": "invalid_grant"})
                st.refresh_count += 1
                return self._json(200, {"access_token": f"fake-access-{st.refresh_count}",
                                        "expires_in": 3600, "token_type": "Bearer"})
            if form.get("grant_type") == "authorization_code":
                if form.get("code") != "fake-code":
                    return self._json(400, {"error": "invalid_grant"})
                return self._json(200, {"access_token": "fake-access-0",
                                        "refresh_token": "fake-refresh-token",
                                        "expires_in": 3600, "token_type": "Bearer",
                                        "scope": "gmail calendar"})
            return self._json(400, {"error": "unsupported_grant_type"})

        if not self._auth_ok():
            return self._json(401, {"error": {"code": 401,
                                              "message": "missing credentials"}})

        if re.match(r"^/gmail/v1/users/[^/]+/watch$", path):
            payload = json.loads(body or b"{}")
            st.watch = {"historyId": str(st.next_history),
                        "expiration": str(int((time.time() + 7 * 86400) * 1000)),
                        "topic": payload.get("topicName")}
            return self._json(200, {"historyId": st.watch["historyId"],
                                    "expiration": st.watch["expiration"]})
        if re.match(r"^/gmail/v1/users/[^/]+/stop$", path):
            st.watch = {}
            return self._json(204, {})
        if re.match(r"^/gmail/v1/users/[^/]+/messages/send$", path):
            payload = json.loads(body or b"{}")
            raw = payload.get("raw", "")
            decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
            parsed = email.message_from_bytes(decoded, policy=email.policy.default)
            st.sent.append({"to": parsed["To"], "subject": parsed["Subject"],
                            "from": parsed["From"],
                            "in_reply_to": parsed["In-Reply-To"],
                            "body": parsed.get_body(("plain",)).get_content()
                            if parsed.get_body(("plain",)) else "",
                            "raw": decoded.decode("utf-8", "replace")})
            return self._json(200, {"id": f"sent{len(st.sent)}",
                                    "threadId": payload.get("threadId")
                                    or f"thr-sent-{len(st.sent)}"})
        m = re.match(r"^/gmail/v1/users/[^/]+/messages/([^/]+)/modify$", path)
        if m:
            msg = st.messages.get(m.group(1))
            if msg is None:
                return self._json(404, {"error": "not found"})
            payload = json.loads(body or b"{}")
            labels = set(msg.get("labelIds", []))
            labels |= set(payload.get("addLabelIds", []))
            labels -= set(payload.get("removeLabelIds", []))
            msg["labelIds"] = sorted(labels)
            return self._json(200, msg)

        if path == "/calendar/v3/freeBusy":
            return self._json(200, {"calendars": {"primary": {"busy": st.busy}}})
        m = re.match(r"^/calendar/v3/calendars/([^/]+)/events$", path)
        if m:
            payload = json.loads(body or b"{}")
            ev = {**payload, "id": f"evt{len(st.events) + 1}",
                  "htmlLink": f"https://calendar.example/evt{len(st.events) + 1}"}
            st.events.append(ev)
            return self._json(200, ev)
        self._json(404, {"error": {"message": f"no route {path}"}})

    def do_GET(self):  # noqa: N802
        self._record()
        parts = urllib.parse.urlsplit(self.path)
        path = parts.path
        query = urllib.parse.parse_qs(parts.query)
        st = GOOGLE
        if not self._auth_ok():
            return self._json(401, {"error": {"code": 401, "message": "unauthorised"}})

        if re.match(r"^/gmail/v1/users/[^/]+/profile$", path):
            return self._json(200, {"emailAddress": "me@example.com",
                                    "messagesTotal": len(st.messages),
                                    "historyId": str(st.next_history)})
        if re.match(r"^/gmail/v1/users/[^/]+/history$", path):
            start = int(query.get("startHistoryId", ["0"])[0])
            items = [h for h in st.history if int(h["id"]) > start]
            return self._json(200, {"history": items,
                                    "historyId": str(st.next_history)})
        m = re.match(r"^/gmail/v1/users/[^/]+/messages/([^/]+)$", path)
        if m:
            msg = st.messages.get(m.group(1))
            return (self._json(200, msg) if msg
                    else self._json(404, {"error": "not found"}))
        if re.match(r"^/gmail/v1/users/[^/]+/messages$", path):
            return self._json(200, {"messages": [{"id": i, "threadId":
                                                  st.messages[i]["threadId"]}
                                                 for i in st.messages]})
        m = re.match(r"^/calendar/v3/calendars/([^/]+)/events$", path)
        if m:
            return self._json(200, {"items": st.events})
        self._json(404, {"error": {"message": f"no route {path}"}})


class FakeGoogleServer(BaseFake):
    handler_cls = _GoogleHandler

    def __init__(self, port: int | None = None, reset: bool = True):
        if reset:
            global GOOGLE
            GOOGLE = _GoogleState()
        super().__init__(port)

    @property
    def state(self) -> _GoogleState:
        return GOOGLE

    @property
    def gmail_base(self) -> str:
        return f"{self.url}/gmail/v1"

    @property
    def calendar_base(self) -> str:
        return f"{self.url}/calendar/v3"

    @property
    def token_uri(self) -> str:
        return f"{self.url}/token"


# --------------------------------------------------------------------------
# fake Anthropic Messages API
# --------------------------------------------------------------------------
class _AnthropicHandler(_HTTPHandler):
    def do_POST(self):  # noqa: N802
        self._record()
        if self.path != "/v1/messages":
            return self._json(404, {"error": {"message": "no route"}})
        if not self.headers.get("x-api-key"):
            return self._json(401, {"type": "error",
                                    "error": {"type": "authentication_error",
                                              "message": "missing x-api-key"}})
        payload = json.loads(self._read_body() or b"{}")
        system = payload.get("system", "")
        last = payload["messages"][-1]["content"]
        responder = getattr(self.fake, "responder", None)
        text = responder(system, last, payload) if responder else "{}"
        self._json(200, {
            "id": "msg_fake", "type": "message", "role": "assistant",
            "model": payload.get("model", "fake"),
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": len(str(payload)) // 4,
                      "output_tokens": len(text) // 4}})


class FakeAnthropicServer(BaseFake):
    handler_cls = _AnthropicHandler

    def __init__(self, port: int | None = None, responder=None):
        super().__init__(port)
        self.responder = responder or (lambda system, prompt, payload: "{}")


# --------------------------------------------------------------------------
# fake SMTP
# --------------------------------------------------------------------------
class FakeSMTPServer:
    """A minimal SMTP server that accepts mail and records it."""

    def __init__(self, port: int | None = None):
        self.port = port or _free_port()
        self.messages: list[dict] = []
        self.refuse: set[str] = set()
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self._sock.listen(8)
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,),
                             daemon=True).start()

    def _session(self, conn):
        f = conn.makefile("rwb")

        def say(line: str):
            f.write((line + "\r\n").encode())
            f.flush()

        say("220 fake.smtp ESMTP ready")
        sender, rcpts, refused = "", [], {}
        while True:
            raw = f.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            up = line.upper()
            if up.startswith(("HELO", "EHLO")):
                say("250-fake.smtp greets you")
                say("250 SIZE 35882577")
            elif up.startswith("MAIL FROM"):
                sender = line.split(":", 1)[1].strip().strip("<>")
                say("250 2.1.0 Ok")
            elif up.startswith("RCPT TO"):
                addr = line.split(":", 1)[1].strip().strip("<>")
                if addr in self.refuse:
                    refused[addr] = (550, "No such user here")
                    say("550 5.1.1 No such user here")
                else:
                    rcpts.append(addr)
                    say("250 2.1.5 Ok")
            elif up == "DATA":
                say("354 End data with <CR><LF>.<CR><LF>")
                chunks = []
                while True:
                    dl = f.readline()
                    if not dl or dl.strip() == b".":
                        break
                    chunks.append(dl)
                data = b"".join(chunks).decode("utf-8", "replace")
                parsed = email.message_from_string(data, policy=email.policy.default)
                self.messages.append({
                    "from": sender, "rcpts": list(rcpts),
                    "subject": parsed["Subject"], "to": parsed["To"],
                    "list_unsubscribe": parsed["List-Unsubscribe"],
                    "message_id": parsed["Message-ID"],
                    "in_reply_to": parsed["In-Reply-To"],
                    "body": (parsed.get_body(("plain",)).get_content()
                             if parsed.get_body(("plain",)) else ""),
                    "raw": data})
                say("250 2.0.0 Ok: queued")
                sender, rcpts = "", []
            elif up == "QUIT":
                say("221 2.0.0 Bye")
                break
            elif up == "RSET":
                sender, rcpts = "", []
                say("250 2.0.0 Ok")
            elif up.startswith("NOOP"):
                say("250 2.0.0 Ok")
            else:
                say("502 5.5.2 Command not implemented")
        try:
            conn.close()
        except OSError:
            pass


# --------------------------------------------------------------------------
# fake Telegram Bot API
# --------------------------------------------------------------------------
class _TelegramState:
    """Everything the fake Bot API remembers, so a test can assert on it."""

    def __init__(self):
        self.token = "123456:TEST-TOKEN"
        self.me = {"id": 777, "is_bot": True, "first_name": "Agent Suite",
                   "username": "agentsuite_test_bot"}
        self.sent: list[dict] = []          # outgoing sendMessage calls
        self.documents: list[dict] = []     # outgoing sendDocument calls
        self.edits: list[dict] = []         # editMessageText calls
        self.answered: list[dict] = []      # answerCallbackQuery calls
        self.topics: list[dict] = []        # createForumTopic calls
        self.commands: list[dict] = []      # setMyCommands
        self.pending: list[dict] = []       # updates waiting to be polled
        self.is_forum = True
        self._next_update = 1
        self._next_message = 1000
        self._next_thread = 50

    # -- test-side helpers --------------------------------------------------
    def queue_command(self, text: str, *, chat_id: int = -100999, user_id: int = 42,
                      thread_id=None) -> int:
        """Simulate the user typing a message to the bot."""
        self._next_update += 1
        self._next_message += 1
        msg = {
            "message_id": self._next_message,
            "from": {"id": user_id, "is_bot": False, "first_name": "Vineet"},
            "chat": {"id": chat_id,
                     "type": "supergroup" if chat_id < 0 else "private",
                     "is_forum": self.is_forum},
            "date": int(time.time()), "text": text,
        }
        if thread_id is not None:
            msg["message_thread_id"] = thread_id
        self.pending.append({"update_id": self._next_update, "message": msg})
        return self._next_update

    def queue_button(self, data: str, *, chat_id: int = -100999, user_id: int = 42,
                     message_id: int = 1001) -> int:
        """Simulate the user tapping an inline button."""
        self._next_update += 1
        self.pending.append({
            "update_id": self._next_update,
            "callback_query": {
                "id": f"cb{self._next_update}",
                "from": {"id": user_id, "is_bot": False, "first_name": "Vineet"},
                "data": data,
                "message": {"message_id": message_id,
                            "chat": {"id": chat_id, "type": "supergroup"},
                            "date": int(time.time()), "text": "..."},
            }})
        return self._next_update

    def texts(self) -> list[str]:
        return [m.get("text", "") for m in self.sent]

    def last_text(self) -> str:
        return self.sent[-1].get("text", "") if self.sent else ""


TELEGRAM = _TelegramState()


class _TelegramHandler(_HTTPHandler):
    def do_POST(self):  # noqa: N802
        self._record()
        state = self.fake.state
        parts = self.path.strip("/").split("/")
        if len(parts) != 2 or not parts[0].startswith("bot"):
            return self._json(404, {"ok": False, "error_code": 404,
                                    "description": "Not Found"})
        token, method = parts[0][3:], parts[1]
        if token != state.token:
            return self._json(401, {"ok": False, "error_code": 401,
                                    "description": "Unauthorized"})

        ctype = self.headers.get("Content-Type", "")
        raw = self._read_body()
        if ctype.startswith("multipart/form-data"):
            fields = _parse_multipart(raw, ctype)
        else:
            fields = {k: v[0] for k, v in
                      urllib.parse.parse_qs(raw.decode("utf-8"),
                                            keep_blank_values=True).items()}

        handler = getattr(self, f"m_{method}", None)
        if handler is None:
            return self._json(404, {"ok": False, "error_code": 404,
                                    "description": f"Method {method} not found"})
        try:
            result = handler(state, fields)
        except _TgFail as fail:
            return self._json(fail.code, {"ok": False, "error_code": fail.code,
                                          "description": fail.description})
        return self._json(200, {"ok": True, "result": result})

    do_GET = do_POST  # noqa: N815 - the real API accepts both

    # -- methods ------------------------------------------------------------
    def m_getMe(self, state, f):  # noqa: N802
        return state.me

    def m_setMyCommands(self, state, f):  # noqa: N802
        state.commands.append(json.loads(f.get("commands", "[]")))
        return True

    def m_deleteWebhook(self, state, f):  # noqa: N802
        return True

    def m_getChat(self, state, f):  # noqa: N802
        return {"id": int(f.get("chat_id", 0)), "type": "supergroup",
                "title": "Agents", "is_forum": state.is_forum}

    def m_getUpdates(self, state, f):  # noqa: N802
        # Real semantics: `offset` is the first update_id to return, and
        # anything below it is confirmed and dropped. Polling twice with the
        # same offset returns the same updates, exactly like the real API.
        offset = int(f.get("offset") or 0)
        if offset:
            state.pending = [u for u in state.pending
                             if u["update_id"] >= offset]
        return list(state.pending)

    def m_sendMessage(self, state, f):  # noqa: N802
        if not f.get("text"):
            raise _TgFail(400, "Bad Request: message text is empty")
        if len(f["text"]) > 4096:
            raise _TgFail(400, "Bad Request: message is too long")
        state._next_message += 1
        record = dict(f, message_id=state._next_message)
        state.sent.append(record)
        return {"message_id": state._next_message,
                "chat": {"id": int(f.get("chat_id", 0))}, "text": f["text"]}

    def m_editMessageText(self, state, f):  # noqa: N802
        state.edits.append(f)
        return {"message_id": int(f.get("message_id", 0)), "text": f.get("text", "")}

    def m_answerCallbackQuery(self, state, f):  # noqa: N802
        state.answered.append(f)
        return True

    def m_sendDocument(self, state, f):  # noqa: N802
        if "document" not in f:
            raise _TgFail(400, "Bad Request: there is no document in the request")
        state._next_message += 1
        state.documents.append(f)
        return {"message_id": state._next_message,
                "document": {"file_name": f.get("document_filename", ""),
                             "file_size": len(f.get("document", b""))}}

    def m_createForumTopic(self, state, f):  # noqa: N802
        if not state.is_forum:
            raise _TgFail(400, "Bad Request: the chat is not a forum")
        state._next_thread += 1
        topic = {"message_thread_id": state._next_thread,
                 "name": f.get("name", "")}
        state.topics.append(topic)
        return topic

    def m_editForumTopic(self, state, f):  # noqa: N802
        return True


class _TgFail(Exception):
    def __init__(self, code: int, description: str):
        self.code, self.description = code, description
        super().__init__(description)


def _parse_multipart(raw: bytes, content_type: str) -> dict:
    """Pull fields and the uploaded file out of a multipart body."""
    boundary = content_type.split("boundary=", 1)[1].strip().encode()
    out: dict = {}
    for part in raw.split(b"--" + boundary):
        if not part.strip(b"-\r\n"):
            continue
        head, _, body = part.partition(b"\r\n\r\n")
        disp = head.decode("utf-8", "replace")
        if 'name="' not in disp:
            continue
        name = disp.split('name="', 1)[1].split('"', 1)[0]
        body = body.rstrip(b"\r\n")
        if 'filename="' in disp:
            out[name] = body
            out[f"{name}_filename"] = disp.split('filename="', 1)[1].split('"', 1)[0]
        else:
            out[name] = body.decode("utf-8", "replace")
    return out


class FakeTelegramServer(BaseFake):
    handler_cls = _TelegramHandler

    def __init__(self, port: int | None = None, reset: bool = True):
        if reset:
            global TELEGRAM
            TELEGRAM = _TelegramState()
        super().__init__(port)

    @property
    def state(self) -> _TelegramState:
        return TELEGRAM

    @property
    def token(self) -> str:
        return TELEGRAM.token
