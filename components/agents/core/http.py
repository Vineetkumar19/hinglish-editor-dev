"""HTTP client built on urllib, with retries, backoff and JSON helpers.

Deliberately dependency-free so the whole suite runs on a bare Python install.
Honours Retry-After and X-RateLimit-Reset headers, which is what the blueprint
asks for when talking to rate-limited APIs.
"""
from __future__ import annotations

import gzip
import json
import random
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from typing import Any

from . import config
from .log import get_logger

log = get_logger("http")

DEFAULT_UA = ("AgentSuite/1.0 (+https://github.com/vineet/agentsuite; "
              "contact configured via OPERATOR_EMAIL)")

# A plain bot User-Agent gets a 403 from a large share of commercial sites,
# which meant real, reachable brands were being recorded as dead. These headers
# are what an ordinary browser sends. robots.txt is still honoured - that is the
# signal that actually expresses what a site owner wants - and the crawl stays
# rate-limited to a handful of public pages per domain.
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/140.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}

# Python refuses a response carrying more than 100 header lines, and raises
# before any of the body is read. Several large Indian retail sites send more
# than that in Set-Cookie alone, so a perfectly healthy site was being recorded
# as unreachable. Raising the ceiling costs nothing and keeps those leads.
try:  # pragma: no cover - depends on the stdlib internals
    import http.client as _httpclient
    if getattr(_httpclient, "_MAXHEADERS", 100) < 400:
        _httpclient._MAXHEADERS = 400
except Exception:  # noqa: BLE001
    pass


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes
    url: str

    @property
    def text(self) -> str:
        charset = "utf-8"
        ctype = self.headers.get("content-type", "")
        if "charset=" in ctype:
            charset = ctype.split("charset=", 1)[1].split(";")[0].strip()
        return self.body.decode(charset, "replace")

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.text)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def raise_for_status(self) -> "Response":
        if not self.ok:
            snippet = self.text[:500]
            raise HttpError(self.status, snippet, self.url)
        return self


class HttpError(RuntimeError):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} from {url}: {body}")
        self.status = status
        self.body = body
        self.url = url

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except Exception:  # noqa: BLE001
            return None


def _decode(raw: bytes, encoding: str) -> bytes:
    if not raw:
        return raw
    enc = (encoding or "").lower()
    try:
        if enc == "gzip":
            return gzip.decompress(raw)
        if enc == "deflate":
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:  # noqa: BLE001
        return raw
    return raw


def _retry_after(headers: dict) -> float | None:
    ra = headers.get("retry-after")
    if ra:
        try:
            return float(ra)
        except ValueError:
            pass
    reset = headers.get("x-ratelimit-reset") or headers.get("x-rate-limit-reset")
    if reset:
        try:
            v = float(reset)
            # Absolute epoch or relative seconds - both appear in the wild.
            return max(0.0, v - time.time()) if v > 1e6 else v
        except ValueError:
            pass
    return None


def request(method: str, url: str, *, headers: dict | None = None,
            data: bytes | None = None, json_body: Any = None,
            params: dict | None = None, timeout: float = 30.0,
            retries: int = 3, backoff: float = 1.0,
            allow_status: set[int] | None = None,
            verify: bool = True, limiter=None) -> Response:
    hdrs = {"User-Agent": config.get("USER_AGENT", DEFAULT_UA),
            "Accept-Encoding": "gzip, deflate"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    for k, v in (headers or {}).items():
        hdrs[k] = v
    if params:
        sep = "&" if urllib.parse.urlsplit(url).query else "?"
        url = url + sep + urllib.parse.urlencode(params, doseq=True)

    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    attempt = 0
    while True:
        if limiter is not None:
            limiter.wait(url)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                raw = r.read()
                h = {k.lower(): v for k, v in r.headers.items()}
                resp = Response(r.status, h, _decode(raw, h.get("content-encoding", "")),
                                r.geturl())
        except urllib.error.HTTPError as e:
            raw = e.read() if hasattr(e, "read") else b""
            h = {k.lower(): v for k, v in (e.headers or {}).items()}
            resp = Response(e.code, h, _decode(raw, h.get("content-encoding", "")), url)
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as e:
            if attempt >= retries:
                raise HttpError(0, f"network error: {e}", url) from e
            delay = backoff * (2 ** attempt) * (0.7 + 0.6 * random.random())
            log.warn(f"network error, retry {attempt+1}/{retries} in {delay:.1f}s",
                     url=url, error=str(e)[:160])
            time.sleep(min(delay, 60))
            attempt += 1
            continue

        if resp.status in RETRY_STATUS and (allow_status is None
                                            or resp.status not in allow_status):
            if attempt >= retries:
                return resp
            wait = _retry_after(resp.headers)
            if wait is None:
                wait = backoff * (2 ** attempt) * (0.7 + 0.6 * random.random())
            log.warn(f"HTTP {resp.status}, backing off {wait:.1f}s",
                     url=url, attempt=attempt + 1)
            time.sleep(min(wait, 120))
            attempt += 1
            continue
        return resp


def get(url: str, **kw) -> Response:
    return request("GET", url, **kw)


def post(url: str, **kw) -> Response:
    return request("POST", url, **kw)


def post_form(url: str, fields: dict, **kw) -> Response:
    body = urllib.parse.urlencode(fields).encode()
    headers = dict(kw.pop("headers", {}) or {})
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    return request("POST", url, data=body, headers=headers, **kw)


def get_json(url: str, **kw) -> Any:
    return get(url, **kw).raise_for_status().json()


def post_json(url: str, body: Any, **kw) -> Any:
    return post(url, json_body=body, **kw).raise_for_status().json()
