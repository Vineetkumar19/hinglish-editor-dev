"""search_files — spec section 8.3.

Filename/extension search scoped to approved directories only, metadata
before content, sorted by modified time, no unrestricted full-disk scan.
"""

import os
import time
from pathlib import Path

from core.app_config import approved_search_roots
from core.pathresolve import is_protected_path
from core.tool_registry import tool
from core.permissions import RiskLevel

MAX_RESULTS = 25
MAX_SCAN_DEPTH = 6  # guard against pathological directory trees

# Directories that are huge, uninteresting, and would otherwise make a
# search of Desktop/Documents take minutes instead of a second. The
# Cortana project itself lives on the Desktop and carries node_modules
# and a .venv, so without this a simple "find my PDFs" walked ~100k files.
SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", ".idea",
    ".vscode", "dist", "build", "release", ".next", ".cache", "site-packages",
    "AppData", "$RECYCLE.BIN", "System Volume Information",
    "Windows", "Program Files", "Program Files (x86)", "ProgramData",
    "models", "tmp", "logs", "memory", "recovery", "code_backups",
}
SKIP_DIRS_CASEFOLD = {name.casefold() for name in SKIP_DIRS}

# Time budget so a pathological tree can never hang a chat turn.
MAX_SCAN_SECONDS = 6.0


def within_approved_roots(path: str, roots: list[str]) -> bool:
    """Resolve symlinks/junctions and compare whole path components.

    String-prefix checks allow `Approved-Other` through an `Approved` rule.
    Windows device paths and alternate data streams are never normal files.
    """
    if not isinstance(path, str) or not path.strip():
        return False
    normalized = path.replace("/", "\\")
    if normalized.startswith(("\\\\?\\", "\\\\.\\", "\\\\")):
        return False
    if ":" in normalized[2:]:
        return False
    try:
        target = Path(os.path.expandvars(os.path.expanduser(path))).resolve()
        if is_protected_path(path) or is_protected_path(target):
            return False
        for root in roots:
            approved = Path(os.path.expandvars(os.path.expanduser(root))).resolve()
            if target.is_relative_to(approved):
                return True
    except (OSError, ValueError, RuntimeError):
        return False
    return False


def search_files(query: str = "", extension: str = "") -> dict:
    roots = approved_search_roots()
    if not roots:
        return {
            "results": [],
            "note": "No approved_search_roots / approved_folder_aliases configured in config/settings.json.",
        }

    query_lower = query.strip().lower()
    ext = extension.strip().lower().lstrip(".")
    matches = []
    started = time.monotonic()
    truncated = False

    for root in roots:
        if not os.path.isdir(root):
            continue
        root_depth = root.rstrip("/\\").count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            if time.monotonic() - started > MAX_SCAN_SECONDS:
                truncated = True
                dirnames[:] = []
                break
            # Prune heavy/irrelevant trees in place so os.walk never
            # descends into them at all.
            dirnames[:] = [
                d for d in dirnames
                if d.casefold() not in SKIP_DIRS_CASEFOLD and not d.startswith(".")
                and within_approved_roots(os.path.join(dirpath, d), roots)
            ]
            depth = dirpath.rstrip("/\\").count(os.sep) - root_depth
            if depth >= MAX_SCAN_DEPTH:
                dirnames[:] = []
                continue
            for fname in filenames:
                if query_lower and query_lower not in fname.lower():
                    continue
                if ext and not fname.lower().endswith("." + ext):
                    continue
                full_path = os.path.join(dirpath, fname)
                if not within_approved_roots(full_path, roots):
                    continue  # belt-and-suspenders, should be unreachable
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                matches.append(
                    {
                        "name": fname,
                        "path": full_path,
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                    }
                )

    matches.sort(key=lambda m: m["modified_at"], reverse=True)
    trimmed = matches[:MAX_RESULTS]
    for m in trimmed:
        m["modified_at_iso"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["modified_at"]))

    result = {"query": query, "extension": extension, "count": len(trimmed), "results": trimmed}
    if truncated:
        result["note"] = "Search hit its time budget — results may be incomplete."
    if not trimmed:
        result["note"] = (
            "No matching files found in the approved folders "
            f"({', '.join(roots)}). Try a different name or extension."
        )
    return result


tool(
    name="search_files",
    description=(
        "Search for files by (partial) filename and/or extension, scoped to approved "
        "directories only. Returns metadata (name, path, size, modified time) sorted "
        "by most recently modified first — does not read file contents."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Substring to match in the filename. Empty matches all."},
            "extension": {"type": "string", "description": "File extension without the dot, e.g. 'pdf'."},
        },
        "required": [],
    },
)(search_files)
