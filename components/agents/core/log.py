"""Structured logging with run/thread correlation. Stdlib only."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time

_ctx = threading.local()


def set_context(**kw) -> None:
    cur = getattr(_ctx, "data", {})
    cur = dict(cur)
    cur.update({k: v for k, v in kw.items() if v is not None})
    _ctx.data = cur


def clear_context() -> None:
    _ctx.data = {}


def get_context() -> dict:
    return dict(getattr(_ctx, "data", {}))


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(get_context())
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    COLORS = {"DEBUG": "\033[90m", "INFO": "\033[36m", "WARNING": "\033[33m",
              "ERROR": "\033[31m", "CRITICAL": "\033[41m"}
    RESET = "\033[0m"

    def __init__(self, color: bool = True):
        super().__init__()
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        ctx = get_context()
        bits = []
        if ctx.get("agent"):
            bits.append(ctx["agent"])
        if ctx.get("thread_id"):
            bits.append(ctx["thread_id"][:12])
        if ctx.get("node"):
            bits.append(ctx["node"])
        prefix = " ".join(f"[{b}]" for b in bits)
        lvl = record.levelname
        c = self.COLORS.get(lvl, "") if self.color else ""
        r = self.RESET if self.color else ""
        line = f"{ts} {c}{lvl:<7}{r} {prefix} {record.getMessage()}".replace("  ", " ")
        extra = getattr(record, "extra_fields", None)
        if extra:
            line += " " + " ".join(f"{k}={v}" for k, v in extra.items())
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


_configured = False


def configure(level: str | None = None, json_mode: bool | None = None) -> None:
    global _configured
    if _configured:
        return
    lvl = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    if json_mode is None:
        json_mode = (os.environ.get("LOG_FORMAT", "text").lower() == "json")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter() if json_mode
                         else _TextFormatter(color=sys.stderr.isatty()))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, lvl, logging.INFO))
    _configured = True


def get_logger(name: str) -> "Logger":
    configure()
    return Logger(logging.getLogger(name))


class Logger:
    """Thin wrapper letting callers pass arbitrary kwargs as structured fields."""

    def __init__(self, inner: logging.Logger):
        self._l = inner

    def _emit(self, level: int, msg: str, exc_info=None, **fields) -> None:
        self._l.log(level, msg, exc_info=exc_info,
                    extra={"extra_fields": fields} if fields else None)

    def debug(self, msg, **f): self._emit(logging.DEBUG, msg, **f)
    def info(self, msg, **f): self._emit(logging.INFO, msg, **f)
    def warn(self, msg, **f): self._emit(logging.WARNING, msg, **f)
    warning = warn
    def error(self, msg, exc_info=None, **f): self._emit(logging.ERROR, msg, exc_info=exc_info, **f)
    def exception(self, msg, **f): self._emit(logging.ERROR, msg, exc_info=True, **f)
