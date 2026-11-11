"""Configuration loading. Stdlib only.

Reads a .env file (if present) then the process environment. Environment
always wins over the file, so container/CI overrides work as expected.
"""
from __future__ import annotations

import os
import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
_LOADED = False


def load_dotenv(path: str | os.PathLike | None = None, override: bool = False) -> dict:
    """Parse a .env file into os.environ. Returns the parsed mapping."""
    global _LOADED
    p = pathlib.Path(path) if path else ROOT / ".env"
    parsed: dict[str, str] = {}
    # Keys this call put into os.environ, so a later line in the same file may
    # correct an earlier one without ever clobbering a real environment
    # variable that was already there.
    ours: set[str] = set()
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if val and val[0] in "\"'" and val[-1] == val[0] and len(val) > 1:
                val = val[1:-1]
            else:
                # Allow an inline comment on an unquoted value - and keep the
                # rest of the value. This used to be shlex.split(val)[0], which
                # took only the FIRST token: SENDER_NAME=Vineet Kumar Das
                # became "Vineet", and a postal address became its first word,
                # in the footer of every email sent.
                cut = re.search(r"(?:^|\s)#", val)
                if cut:
                    val = val[:cut.start()]
                val = val.strip()
            # A key repeated inside the file: the LAST line wins. People add a
            # setting by pasting it at the bottom rather than hunting for the
            # existing line, and having the stale one above silently win is a
            # bad way to spend an afternoon. The real environment still beats
            # the file either way - that is what `override` is for.
            parsed[key] = val
            if override or key in ours or key not in os.environ:
                os.environ[key] = val
                ours.add(key)
    _LOADED = True
    return parsed


def _ensure() -> None:
    if not _LOADED:
        load_dotenv()


def get(key: str, default: Any = None) -> Any:
    _ensure()
    v = os.environ.get(key)
    return default if v is None or v == "" else v


def get_bool(key: str, default: bool = False) -> bool:
    v = get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on", "y")


def get_int(key: str, default: int = 0) -> int:
    v = get(key)
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float = 0.0) -> float:
    v = get(key)
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return default


def get_list(key: str, default: list | None = None, sep: str = ",") -> list[str]:
    v = get(key)
    if v is None:
        return list(default or [])
    return [x.strip() for x in str(v).split(sep) if x.strip()]


def require(key: str) -> str:
    v = get(key)
    if v is None:
        raise RuntimeError(
            f"Required setting {key!r} is missing. Add it to {ROOT / '.env'} "
            f"(see .env.example) or export it in the environment."
        )
    return str(v)


def data_dir() -> pathlib.Path:
    d = pathlib.Path(get("DATA_DIR", str(ROOT / "data")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_dir() -> pathlib.Path:
    d = pathlib.Path(get("PROFILES_DIR", str(ROOT / "profiles")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def dry_run() -> bool:
    """Global kill switch. When true nothing leaves the machine."""
    return get_bool("DRY_RUN", True)
