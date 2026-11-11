"""Token-bucket rate limiting and polite crawling controls. Stdlib only."""
from __future__ import annotations

import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .log import get_logger

log = get_logger("ratelimit")


class TokenBucket:
    """Classic token bucket. `rate` tokens/second up to `capacity` burst."""

    def __init__(self, rate: float, capacity: float | None = None):
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else max(1.0, rate))
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        t = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (t - self._last) * self.rate)
        self._last = t

    def try_acquire(self, n: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def acquire(self, n: float = 1.0, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return True
                need = (n - self._tokens) / self.rate
            if deadline is not None and time.monotonic() + need > deadline:
                return False
            time.sleep(min(need, 1.0))


class HostLimiter:
    """Per-hostname politeness: a minimum gap between requests, plus robots.txt."""

    def __init__(self, min_interval: float = 1.5, respect_robots: bool = True,
                 user_agent: str = "*"):
        self.min_interval = min_interval
        self.respect_robots = respect_robots
        self.user_agent = user_agent
        self._last: dict[str, float] = {}
        self._robots: dict[str, "_Robots"] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        host = urllib.parse.urlsplit(url).netloc
        with self._lock:
            last = self._last.get(host, 0.0)
            delay = self.min_interval - (time.monotonic() - last)
        if delay > 0:
            time.sleep(delay)
        with self._lock:
            self._last[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            robots = self._robots.get(origin)
        if robots is None:
            robots = _Robots.fetch(origin, self.user_agent)
            with self._lock:
                self._robots[origin] = robots
        return robots.allowed(parts.path or "/")

    def crawl_delay(self, url: str) -> float | None:
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        r = self._robots.get(origin)
        return r.delay if r else None


@dataclass
class _Robots:
    rules: list[tuple[str, bool]] = field(default_factory=list)  # (path prefix, allowed)
    delay: float | None = None
    ok: bool = True

    @classmethod
    def fetch(cls, origin: str, user_agent: str, timeout: float = 8.0) -> "_Robots":
        url = origin.rstrip("/") + "/robots.txt"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(200_000).decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            log.debug(f"no robots.txt for {origin}: {exc}")
            return cls(ok=False)
        return cls.parse(body, user_agent)

    @classmethod
    def parse(cls, body: str, user_agent: str) -> "_Robots":
        ua = user_agent.lower()
        groups: list[tuple[list[str], list[tuple[str, bool]], float | None]] = []
        cur_agents: list[str] = []
        cur_rules: list[tuple[str, bool]] = []
        cur_delay: float | None = None
        expecting_agent = True
        for raw in body.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field_name, _, value = line.partition(":")
            field_name = field_name.strip().lower()
            value = value.strip()
            if field_name == "user-agent":
                if not expecting_agent:
                    groups.append((cur_agents, cur_rules, cur_delay))
                    cur_agents, cur_rules, cur_delay = [], [], None
                    expecting_agent = True
                cur_agents.append(value.lower())
            elif field_name in ("allow", "disallow"):
                expecting_agent = False
                cur_rules.append((value, field_name == "allow"))
            elif field_name == "crawl-delay":
                expecting_agent = False
                try:
                    cur_delay = float(value)
                except ValueError:
                    pass
        groups.append((cur_agents, cur_rules, cur_delay))

        chosen: tuple[list[tuple[str, bool]], float | None] | None = None
        for agents, rules, delay in groups:
            if any(a and a in ua for a in agents):
                chosen = (rules, delay)
                break
        if chosen is None:
            for agents, rules, delay in groups:
                if "*" in agents:
                    chosen = (rules, delay)
                    break
        if chosen is None:
            return cls()
        rules, delay = chosen
        rules.sort(key=lambda r: len(r[0]), reverse=True)  # longest match wins
        return cls(rules=rules, delay=delay)

    def allowed(self, path: str) -> bool:
        for prefix, is_allow in self.rules:
            if prefix == "":
                continue
            if path.startswith(prefix):
                return is_allow
        return True


class DailyCap:
    """Per-key daily counter, persisted, used to cap outbound email volume."""

    def __init__(self, store, namespace: str = "daily_cap"):
        self.store = store
        self.ns = namespace

    def _key(self, name: str) -> str:
        return f"{name}:{time.strftime('%Y-%m-%d')}"

    def count(self, name: str) -> int:
        return int(self.store.kv_get(self.ns, self._key(name), 0) or 0)

    def remaining(self, name: str, limit: int) -> int:
        return max(0, limit - self.count(name))

    def check_and_increment(self, name: str, limit: int) -> bool:
        c = self.count(name)
        if c >= limit:
            return False
        self.store.kv_set(self.ns, self._key(name), c + 1)
        return True
