"""Windows path resolution that survives OneDrive folder redirection.

On Windows 11 with OneDrive backup turned on (this machine), the real
Desktop/Documents/Pictures live under %USERPROFILE%\\OneDrive\\... rather
than directly under %USERPROFILE%. A config file that points at
C:/Users/you/Desktop therefore resolves to a folder that does not exist,
and every folder-open and file-search against it silently returns
nothing. This module tries the configured path and both redirection
variants, returning the first one that actually exists.
"""

import os
from pathlib import Path


def is_protected_path(path: str | Path) -> bool:
    """Credential/version-control internals are outside ordinary file tools."""
    own_root = Path(__file__).resolve().parents[2]
    try:
        target = Path(path).resolve()
        if target.is_relative_to(own_root):
            relative = target.relative_to(own_root)
            if relative.parts and relative.parts[0].casefold() in {'memory','logs'}:
                return True
    except (OSError, RuntimeError, ValueError):
        return True
    parts = [part.lower() for part in Path(path).parts]
    if any(part in {".git", ".ssh", ".aws", ".azure", ".gnupg", ".codex", "browser-profile"} for part in parts):
        return True
    # Browser/OS credential stores need a dedicated integration, never file tools.
    if any(part in {"user data", "vault", "credentials"} for part in parts):
        return True
    if "mozilla" in parts and "profiles" in parts:
        return True
    if "system32" in parts and "config" in parts:
        return True
    name = parts[-1] if parts else ""
    if name in {
        ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519", "credentials", "credentials.json",
        "ntuser.dat", "usrclass.dat", "login data", "local state", "cookies", "cookies.sqlite",
        "logins.json", "key4.db", "wallet.dat",
    }:
        return True
    if (name == ".env" or name.startswith(".env.")) and name != ".env.example":
        return True
    return Path(name).suffix in {".pem", ".key", ".pfx", ".p12"}


def is_protected_edit_path(path: str | Path) -> bool:
    """Ordinary code edits cannot alter Windows or Cortana's trust boundary."""
    from core.config import ROOT_DIR

    target = Path(path).resolve()
    if is_protected_path(target):
        return True
    for name in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        value = os.environ.get(name)
        if value and target.is_relative_to(Path(value).resolve()):
            return True
    own_root = ROOT_DIR.resolve()
    if target.is_relative_to(own_root):
        relative = target.relative_to(own_root)
        if relative.parts and relative.parts[0].lower() in {"agent", "tools", "desktop", "config", "scripts", "models", "memory", "logs", "tmp", ".runtime"}:
            return True
        if len(relative.parts) == 1 and target.suffix.lower() not in {".md", ".txt"}:
            return True
    return False


def candidate_paths(path: str) -> list[str]:
    expanded = os.path.expandvars(os.path.expanduser(path or "")).replace("/", os.sep)
    if not expanded:
        return []

    candidates = [expanded]
    home = os.path.expanduser("~")
    onedrive = os.environ.get("OneDrive") or os.path.join(home, "OneDrive")

    try:
        rel = os.path.relpath(expanded, home)
    except ValueError:
        rel = None

    if rel and not rel.startswith(".."):
        candidates.append(os.path.join(onedrive, rel))

    if onedrive and expanded.lower().startswith(onedrive.lower()):
        tail = expanded[len(onedrive) :].lstrip(os.sep)
        if tail:
            candidates.append(os.path.join(home, tail))

    seen, unique = set(), []
    for c in candidates:
        key = os.path.normcase(c)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def resolve_dir(path: str) -> str | None:
    """First existing directory among the configured path and its variants."""
    for candidate in candidate_paths(path):
        if os.path.isdir(candidate):
            return candidate
    return None
