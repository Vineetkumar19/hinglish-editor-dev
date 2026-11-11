"""open_folder — spec section 8.2. Friendly-name -> approved absolute path,
opened in Explorer. Same allowlist-only pattern as apps.py.

Two robustness fixes over the first version, both of which were causing
"open my downloads" to silently do nothing:

1. Name resolution is fuzzy (core.alias_match) instead of exact-key, so
   "downloads", "my Downloads" and "the downloads folder" all resolve to
   the configured "Downloads" alias. This loosens naming only — the
   returned key always comes from the allowlist, so permissions are
   unchanged.

2. Path resolution falls back across OneDrive-redirected locations. On
   Windows 11 with OneDrive backup enabled (this machine), the real
   Desktop/Documents live at %USERPROFILE%\\OneDrive\\Desktop rather than
   %USERPROFILE%\\Desktop, so a config pointing at the latter resolved to
   a directory that does not exist.
"""

import os
import platform
import subprocess

from core.alias_match import resolve_alias
from core.app_config import approved_folder_aliases, approved_search_roots
from core.pathresolve import resolve_dir
from core.tool_registry import tool
from core.permissions import RiskLevel
from core.processes import public_environment
from tools.files import within_approved_roots


class FolderNotApproved(Exception):
    pass


def open_folder(name: str) -> dict:
    aliases = approved_folder_aliases()
    key = resolve_alias(name, aliases)

    if key is None:
        raise FolderNotApproved(
            f"'{name}' is not an approved folder alias "
            f"(config/settings.json permissions.approved_folder_aliases). "
            f"Known: {', '.join(sorted(aliases)) or '(none configured)'}"
        )

    configured = aliases[key]
    path = resolve_dir(configured)

    if path is None:
        return {
            "opened": False,
            "alias": key,
            "path": configured,
            "note": (
                f"'{key}' is configured as {configured} but no such folder exists "
                "on this machine. Fix the path in config/settings.json."
            ),
        }
    if not within_approved_roots(path, approved_search_roots()):
        raise FolderNotApproved("This folder is outside the current approved scope or is a protected credential store.")

    if platform.system() != "Windows":
        return {
            "opened": False,
            "alias": key,
            "path": path,
            "note": "Not running on Windows — skipped actual launch (sandbox verification only).",
        }

    # explorer.exe is fussy about forward slashes and trailing separators.
    explorer = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
    subprocess.Popen([explorer, os.path.normpath(path)], shell=False, env=public_environment())
    return {"opened": True, "alias": key, "path": path}


tool(
    name="open_folder",
    description=(
        "Open an approved local folder in Windows Explorer by its friendly name "
        "(e.g. 'Downloads', 'Documents', 'Desktop'). Use this whenever the user "
        "asks to open or show a folder."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Friendly folder alias from the approved list."}
        },
        "required": ["name"],
    },
)(open_folder)
