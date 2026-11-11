"""Loader for config/settings.json — the human-editable allowlists
(approved apps, folder aliases, search roots) described in spec section 11
(permissions/safety) and section 19 (folder structure).

Falls back to config/settings.example.json if the user hasn't copied it to
settings.json yet, so the app still boots with sane example values on a
fresh checkout.
"""

import json
from pathlib import Path
from threading import Lock

from core.config import settings

_lock = Lock()
_cache: dict | None = None
_cache_mtime: float | None = None


def _config_file() -> Path:
    real = Path(settings.app_config_path)
    if real.exists():
        return real
    return Path(settings.app_config_example_path)


def load_app_config(force: bool = False) -> dict:
    """Loads config/settings.json (or the example fallback), cached until
    the file's mtime changes so tools don't re-read it on every call."""
    global _cache, _cache_mtime

    path = _config_file()
    with _lock:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return {}

        if force or _cache is None or mtime != _cache_mtime:
            with open(path, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            _cache_mtime = mtime

        return _cache


def approved_apps() -> dict:
    return load_app_config().get("permissions", {}).get("approved_app_allowlist", {})


def approved_folder_aliases() -> dict:
    return load_app_config().get("permissions", {}).get("approved_folder_aliases", {})


def approved_search_roots() -> list[str]:
    """Configured search roots, resolved to paths that actually exist.

    Resolution matters because OneDrive redirection means a configured
    C:/Users/you/Desktop may really live at C:/Users/you/OneDrive/Desktop.
    Unresolvable roots are dropped rather than returned, so search_files
    doesn't waste a walk on directories that aren't there — and so the
    approved-root containment check compares real paths against real paths.
    """
    from core.pathresolve import resolve_dir

    cfg = load_app_config().get("permissions", {})
    roots = cfg.get("approved_search_roots")
    if not roots:
        # Default to the folder aliases themselves if no explicit roots given.
        roots = list(approved_folder_aliases().values())

    resolved = []
    for r in roots:
        real = resolve_dir(r)
        if real and real not in resolved:
            resolved.append(real)
    return resolved
