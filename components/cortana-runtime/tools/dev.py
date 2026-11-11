"""GitHub and IDE tools — Phase 15, credential-free half.

What's here works with no token: opening GitHub pages, searching repos and
code, and opening a local project folder directly in VS Code or IntelliJ.

What's deliberately NOT here: creating issues, opening pull requests,
pushing commits, reading private repos. Those need a GitHub personal
access token, and a token with write scope sitting in a config file is a
meaningful risk to hand a 3B model that occasionally mis-hears words. If
you want those, generate a read-only token first and we can wire the read
side up separately.
"""

import os
import platform
import subprocess
import urllib.parse

from core.app_config import approved_folder_aliases, approved_search_roots
from core.alias_match import resolve_alias
from core.pathresolve import resolve_dir
from core.tool_registry import tool
from core.permissions import RiskLevel
from core.processes import public_environment, shell_open

GITHUB = "https://github.com"

IDE_COMMANDS = {
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "intellij": "idea64.exe",
    "intellij idea": "idea64.exe",
    "idea": "idea64.exe",
    "pycharm": "pycharm64.exe",
    "webstorm": "webstorm64.exe",
}


class ProjectNotFound(Exception):
    pass


def _launch_url(url: str) -> bool:
    if platform.system() != "Windows":
        return False
    shell_open(url)
    return True


def open_github(user: str = "", repo: str = "", query: str = "", section: str = "") -> dict:
    """Open a GitHub profile, repo, search, or a repo sub-page."""
    if query:
        url = f"{GITHUB}/search?q={urllib.parse.quote_plus(query)}"
    elif user and repo:
        url = f"{GITHUB}/{urllib.parse.quote(user)}/{urllib.parse.quote(repo)}"
        sec = (section or "").strip().lower()
        if sec in {"issues", "pulls", "actions", "commits", "releases", "settings", "wiki"}:
            url += f"/{sec}"
    elif user:
        url = f"{GITHUB}/{urllib.parse.quote(user)}"
    else:
        url = GITHUB

    launched = _launch_url(url)
    return {
        "opened": launched,
        "url": url,
        "note": None if launched else "Not running on Windows — skipped launch (sandbox verification only).",
    }


def _resolve_project(project: str) -> str:
    """Find a project folder: an alias, a full path, or a folder name under an approved root."""
    aliases = approved_folder_aliases()
    from tools.files import within_approved_roots

    roots = approved_search_roots()
    direct = resolve_dir(project)
    if direct and within_approved_roots(direct, roots):
        return direct

    if any(separator in project for separator in ('/', '\\')) or os.path.splitdrive(project)[0]:
        raise ProjectNotFound(f"Couldn't open project path '{project}' inside an approved root.")

    key = resolve_alias(project, aliases)
    if key:
        real = resolve_dir(aliases[key])
        if real and within_approved_roots(real, roots):
            return real

    # Search one level down inside each approved root for a folder by that name.
    wanted = (project or "").strip().lower()
    for root in approved_search_roots():
        try:
            for entry in os.scandir(root):
                if entry.is_dir() and entry.name.lower() == wanted and within_approved_roots(entry.path, roots):
                    return entry.path
        except OSError:
            continue

    raise ProjectNotFound(
        f"Couldn't find a project called '{project}'. Give the full folder path, "
        "or add it to approved_folder_aliases in config/settings.json."
    )


def open_in_ide(project: str, ide: str = "vscode") -> dict:
    path = _resolve_project(project)

    ide_key = (ide or "vscode").strip().lower()
    command = IDE_COMMANDS.get(ide_key)
    if command is None:
        return {
            "opened": False,
            "error": f"'{ide}' isn't a known IDE. Try: {', '.join(sorted(set(IDE_COMMANDS)))}.",
        }

    if platform.system() != "Windows":
        return {
            "opened": False,
            "project": path,
            "ide": ide_key,
            "note": "Not running on Windows — skipped launch (sandbox verification only).",
        }

    try:
        import shutil

        executable = shutil.which(command)
        if not executable or executable.lower().endswith((".cmd", ".bat")):
            # VS Code's shell shim is not an executable. Resolve Code.exe
            # explicitly instead of interpolating model text into cmd.exe.
            if ide_key in {"vscode", "vs code", "code"}:
                candidates = [
                    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
                    os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft VS Code", "Code.exe"),
                ]
                executable = next((p for p in candidates if os.path.isfile(p)), None)
        if not executable:
            return {"opened": False, "error": f"Could not locate the executable for {ide_key}."}
        subprocess.Popen([executable, os.path.normpath(path)], shell=False, env=public_environment())
    except Exception as e:
        return {"opened": False, "error": f"Couldn't start {ide_key}: {e}"}

    return {"opened": True, "project": path, "ide": ide_key}


tool(
    name="open_github",
    description=(
        "Open GitHub — a user's profile, a specific repository (optionally its "
        "issues/pulls/actions page), or a code search. Read-only browsing; this "
        "cannot create issues or push code."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "user": {"type": "string", "description": "GitHub username or org."},
            "repo": {"type": "string", "description": "Repository name (needs user too)."},
            "query": {"type": "string", "description": "Search GitHub for this instead."},
            "section": {"type": "string", "description": "issues | pulls | actions | commits | releases"},
        },
        "required": [],
    },
)(open_github)

tool(
    name="open_in_ide",
    description=(
        "Open a local project folder in an IDE. project can be a folder alias "
        "('Cortana'), a full path, or a folder name inside an approved location. "
        "ide is vscode (default), intellij, pycharm or webstorm."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "Project folder name, alias, or full path."},
            "ide": {"type": "string", "description": "vscode | intellij | pycharm | webstorm"},
        },
        "required": ["project"],
    },
)(open_in_ide)
