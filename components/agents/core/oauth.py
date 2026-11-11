"""Google OAuth2 for installed applications, stdlib only.

Implements the loopback-redirect flow (the one Google recommends for desktop
apps) plus refresh-token persistence, so the agents can call Gmail and Calendar
without the google-api-python-client dependency.

First run::

    python run.py auth google

opens a consent URL, catches the redirect on 127.0.0.1, exchanges the code and
stores the refresh token. After that every run refreshes silently.
"""
from __future__ import annotations

import json
import pathlib
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import config, http
from .log import get_logger
from .store import Store, get_store

log = get_logger("oauth")

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class OAuthError(RuntimeError):
    pass


@dataclass
class Token:
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0
    scope: str = ""
    token_type: str = "Bearer"

    @property
    def expired(self) -> bool:
        return time.time() >= (self.expires_at - 120)

    def to_json(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_json(cls, d: dict | None) -> "Token | None":
        return cls(**d) if d else None


class GoogleOAuth:
    def __init__(self, store: Store | None = None, account: str = "default",
                 scopes: list[str] | None = None):
        self.store = store or get_store()
        self.account = account
        self.scopes = scopes or (GMAIL_SCOPES + CALENDAR_SCOPES)
        self.client_id = config.get("GOOGLE_CLIENT_ID", "")
        self.client_secret = config.get("GOOGLE_CLIENT_SECRET", "")
        self.token_uri = config.get("GOOGLE_TOKEN_URI", TOKEN_URI)
        self.auth_uri = config.get("GOOGLE_AUTH_URI", AUTH_URI)
        self._load_client_secrets_file()

    def _load_client_secrets_file(self) -> None:
        """Accept the credentials.json Google Cloud Console hands you."""
        path = config.get("GOOGLE_CLIENT_SECRETS_FILE")
        if not path:
            return
        p = pathlib.Path(path)
        if not p.exists():
            log.warn(f"GOOGLE_CLIENT_SECRETS_FILE points at {p}, which does not exist")
            return
        data = json.loads(p.read_text())
        blob = data.get("installed") or data.get("web") or {}
        self.client_id = self.client_id or blob.get("client_id", "")
        self.client_secret = self.client_secret or blob.get("client_secret", "")
        self.auth_uri = blob.get("auth_uri", self.auth_uri)
        self.token_uri = blob.get("token_uri", self.token_uri)

    # -- persistence ---------------------------------------------------------
    def _key(self) -> str:
        return f"google:{self.account}"

    def load(self) -> Token | None:
        return Token.from_json(self.store.kv_get("oauth", self._key()))

    def save(self, tok: Token) -> None:
        self.store.kv_set("oauth", self._key(), tok.to_json())

    def clear(self) -> None:
        self.store.kv_delete("oauth", self._key())

    # -- flow ----------------------------------------------------------------
    def authorize_url(self, redirect_uri: str, state: str) -> str:
        return self.auth_uri + "?" + urllib.parse.urlencode({
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        })

    def exchange(self, code: str, redirect_uri: str) -> Token:
        resp = http.post_form(self.token_uri, {
            "code": code, "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }, timeout=30)
        if not resp.ok:
            raise OAuthError(f"token exchange failed: {resp.status} {resp.text[:300]}")
        d = resp.json()
        tok = Token(access_token=d["access_token"],
                    refresh_token=d.get("refresh_token", ""),
                    expires_at=time.time() + float(d.get("expires_in", 3600)),
                    scope=d.get("scope", ""), token_type=d.get("token_type", "Bearer"))
        self.save(tok)
        return tok

    def refresh(self, tok: Token) -> Token:
        if not tok.refresh_token:
            raise OAuthError("no refresh token stored - run `python run.py auth google`")
        resp = http.post_form(self.token_uri, {
            "refresh_token": tok.refresh_token, "client_id": self.client_id,
            "client_secret": self.client_secret, "grant_type": "refresh_token",
        }, timeout=30)
        if not resp.ok:
            raise OAuthError(f"token refresh failed: {resp.status} {resp.text[:300]}")
        d = resp.json()
        tok.access_token = d["access_token"]
        tok.expires_at = time.time() + float(d.get("expires_in", 3600))
        if d.get("refresh_token"):
            tok.refresh_token = d["refresh_token"]
        self.save(tok)
        log.debug("refreshed google access token")
        return tok

    def access_token(self) -> str:
        tok = self.load()
        if tok is None:
            raise OAuthError(
                "Google account is not authorised yet. Run: python run.py auth google")
        if tok.expired:
            tok = self.refresh(tok)
        return tok.access_token

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token()}"}

    # -- interactive consent -------------------------------------------------
    def run_installed_flow(self, port: int = 8765, open_browser: bool = True) -> Token:
        if not self.client_id or not self.client_secret:
            raise OAuthError(
                "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set. Create an "
                "OAuth client of type 'Desktop app' in Google Cloud Console, then "
                "either put the values in .env or point "
                "GOOGLE_CLIENT_SECRETS_FILE at the downloaded credentials.json.")
        redirect_uri = f"http://127.0.0.1:{port}/oauth2callback"
        state = secrets.token_urlsafe(24)
        result: dict = {}
        done = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parts = urllib.parse.urlsplit(self.path)
                if parts.path != "/oauth2callback":
                    self.send_response(404)
                    self.end_headers()
                    return
                q = urllib.parse.parse_qs(parts.query)
                result.update({k: v[0] for k, v in q.items()})
                body = (b"<h2>Authorised.</h2><p>You can close this tab and return "
                        b"to the terminal.</p>") if "code" in result else \
                       b"<h2>Authorisation failed.</h2>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                done.set()

            def log_message(self, *a):  # silence
                pass

        server = HTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = self.authorize_url(redirect_uri, state)
        print("\nOpen this URL to authorise Gmail/Calendar access:\n\n" + url + "\n")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                pass
        if not done.wait(timeout=300):
            server.shutdown()
            raise OAuthError("timed out waiting for the OAuth redirect")
        server.shutdown()
        if result.get("state") != state:
            raise OAuthError("state mismatch - possible CSRF, aborting")
        if "code" not in result:
            raise OAuthError(f"consent denied: {result.get('error')}")
        tok = self.exchange(result["code"], redirect_uri)
        print("Authorised. Refresh token stored.\n")
        return tok
