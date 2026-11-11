"""open_path — open a specific file or folder by its full path.

This exists because of a real gap: open_folder only accepts *aliases*
("Downloads"), so when the user said "open C:/Users/vinee/OneDrive/
Documents/Vineet-16-Scripts-Season2.pdf" the model had nothing to call.
It guessed open_folder("OneDrive"), which isn't an alias, and reported
failure — even though that path is inside an approved root.

Behaviour:
  - a directory  -> opened in Explorer
  - a file       -> opened in whatever Windows has associated with it
                    (PDF in the PDF reader, .docx in Word, ...)

Safety is unchanged: the path must resolve inside one of the approved
search roots from config/settings.json, so this is a convenience over the
same allowlist, not a way around it.
"""

import os
import platform
import subprocess
from pathlib import Path

from core.app_config import approved_search_roots
from core.pathresolve import candidate_paths
from core.tool_registry import tool
from core.permissions import RiskLevel
from core.processes import public_environment, shell_open
from tools.files import within_approved_roots

SAFE_OPEN_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp",
    ".txt", ".md", ".csv", ".tsv", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".mp3", ".wav", ".m4a", ".flac", ".mp4", ".mkv", ".avi", ".mov",
}


class PathNotApproved(Exception):
    pass


def _resolve_existing(path: str) -> str | None:
    """The first variant of this path that exists (file or directory)."""
    for candidate in candidate_paths(path):
        if os.path.exists(candidate):
            return str(Path(candidate).resolve())
    return None


def _within_roots(path: str, roots: list[str]) -> bool:
    return within_approved_roots(path, roots)


def open_path(path: str) -> dict:
    roots = approved_search_roots()
    if not roots:
        raise PathNotApproved("No approved folders are configured in config/settings.json.")

    real = _resolve_existing(path)
    if real is None:
        return {
            "opened": False,
            "path": path,
            "note": "No file or folder exists at that path on this machine.",
        }

    if not _within_roots(path, roots) or not _within_roots(real, roots):
        raise PathNotApproved(
            f"'{real}' is outside your approved folders. Approved locations: "
            f"{', '.join(roots)}."
        )

    is_dir = os.path.isdir(real)
    if not is_dir and Path(real).suffix.lower() not in SAFE_OPEN_EXTENSIONS:
        raise PathNotApproved(
            "This file type cannot be launched by file tools. Use an approved application "
            "or open a source project with open_in_ide; scripts, installers and shortcuts are blocked."
        )

    if platform.system() != "Windows":
        return {
            "opened": False,
            "path": real,
            "kind": "folder" if is_dir else "file",
            "note": "Not running on Windows — skipped actual launch (sandbox verification only).",
        }

    normalized = os.path.normpath(real)
    if is_dir:
        explorer = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
        subprocess.Popen([explorer, normalized], shell=False, env=public_environment())
    else:
        # A stale Store file association can show an Open With chooser while
        # ShellExecute still reports success. Plain local text has a known,
        # approved viewer; launch it explicitly without changing associations.
        if Path(real).suffix.lower() in {'.txt', '.md', '.csv', '.tsv', '.json'}:
            from core.app_config import approved_apps
            viewer = approved_apps().get('notepad')
            if not isinstance(viewer, list) or not viewer or not Path(viewer[0]).is_file():
                raise PathNotApproved('The approved text viewer is unavailable.')
            subprocess.Popen([*viewer, normalized], shell=False, env=public_environment())
        else:
            shell_open(normalized)

    return {"opened": True, "path": normalized, "kind": "folder" if is_dir else "file"}


tool(
    name="open_path",
    description=(
        "Open a specific file or folder using its full path (e.g. "
        "'C:/Users/vinee/OneDrive/Documents/report.pdf'). Files open in their "
        "default app, folders open in Explorer. Use this whenever the user gives "
        "a complete path, or after search_files returns the path of a file the "
        "user asked you to open."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full path to the file or folder to open."}
        },
        "required": ["path"],
    },
)(open_path)
