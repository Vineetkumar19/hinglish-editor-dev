"""Coding-buddy tools — read source files, list a repo's contents, and make
a targeted, previewed, human-approved edit to a file.

The point of this module is the loop the user actually asked for: take a
screenshot of an error -> analyze_screenshot explains it -> read_code_file
pulls up the relevant file -> edit_code_file proposes a fix as a diff ->
the human approves it in the UI -> the file changes on disk (which VS Code
then reloads on its own, same as any external edit).

edit_code_file is HIGH risk and never writes anything by itself. It goes
through the pending-confirmation flow in core/tool_registry.py: dispatch()
builds a diff preview, parks it in the pending_confirmations table, and the
actual write only happens from execute_confirmed() after a human clicks
Approve (POST /api/confirm). See that module's docstring for the full
mechanism — this is Phase 0 of the architecture doc's roadmap (a real
confirmation step for CONFIRM/EXECUTE-tier actions), built now because the
coding buddy is the first feature that actually needs it.

Every path is scoped to config/settings.json's approved_search_roots, the
same allowlist search_files()/read_pdf() already use — the model can never
be pointed at a file outside folders you've explicitly approved.
"""

import difflib
import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from core.app_config import approved_search_roots
from core.config import settings
from core.permissions import RiskLevel
from core.tool_registry import ConfirmedActionStale, tool
from core.tasks import check_cancelled
from core.pathresolve import is_protected_edit_path
from tools.dev import ProjectNotFound, _resolve_project
from tools.files import SKIP_DIRS, within_approved_roots

# A 3B model's context is small, and code needs to be read closely (unlike
# prose, which can be skimmed) — capped lower than documents.py's 8000 so a
# read_code_file call leaves room for the model's own reasoning afterward.
MAX_RETURNED_CHARS = 6000
MAX_LISTED_FILES = 300
MAX_LIST_DEPTH = 6
MAX_SOURCE_BYTES = 2_000_000

# Extensions read_code_file will treat as text. Anything else (images,
# binaries, .pyc, compiled output) is refused rather than dumped as garbage
# into the model's context.
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".css", ".html", ".htm", ".sql", ".sh", ".ps1", ".bat",
    ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs", ".rb", ".php",
    ".env", ".ini", ".cfg", ".xml", ".vue", ".svelte", ".gitignore",
    ".dockerfile", ".env.example",
}

BACKUPS_DIR = Path(settings.memory_dir) / "code_backups"


class PathNotApproved(Exception):
    pass


class NotATextFile(Exception):
    pass


class EditAmbiguous(Exception):
    pass


class EditNotFound(Exception):
    pass


class NoBackupFound(Exception):
    pass


class EditStale(ConfirmedActionStale):
    pass


def _assert_approved(path: str):
    roots = approved_search_roots()
    if not roots or not within_approved_roots(path, roots):
        raise PathNotApproved(
            f"'{path}' is outside the approved search roots (config/settings.json "
            f"permissions.approved_search_roots / approved_folder_aliases)."
        )


def _assert_text_file(path: str):
    file_path = Path(path)
    if (
        file_path.name.lower() == ".env"
        or file_path.name.lower().startswith(".env.") and file_path.name.lower() != ".env.example"
        or any(part.lower() in {".ssh", ".aws", ".azure", ".gnupg", ".codex"} for part in file_path.resolve().parts)
    ):
        raise NotATextFile("Credential and assistant configuration stores are not readable code files.")
    ext = Path(path).suffix.lower()
    if ext and ext not in TEXT_EXTENSIONS:
        raise NotATextFile(
            f"'{path}' (extension '{ext}') isn't a recognized text/code file — refusing to "
            "read/edit it as text. Add the extension to tools/code.py's TEXT_EXTENSIONS if "
            "this is wrong."
        )


def read_code_file(path: str, start_line: int = 0, end_line: int = 0) -> dict:
    """Reads a source file with line numbers. start_line/end_line (1-based,
    both inclusive) narrow the read — leave both 0 for the whole file
    (subject to the char cap)."""
    _assert_approved(path)
    _assert_text_file(path)

    file_path = Path(path)
    if not file_path.is_file():
        return {"path": path, "error": "File not found."}
    if file_path.stat().st_size > MAX_SOURCE_BYTES:
        return {"path": path, "error": "This source file is larger than 2 MB. Split or narrow it before asking Cortana to inspect it."}

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"path": path, "error": f"Couldn't read file: {e}"}

    lines = text.splitlines()
    total_lines = len(lines)

    lo = max(1, start_line) if start_line else 1
    hi = min(total_lines, end_line) if end_line else total_lines
    selected = lines[lo - 1 : hi]

    numbered = "\n".join(f"{lo + i:>5}  {line}" for i, line in enumerate(selected))
    truncated = len(numbered) > MAX_RETURNED_CHARS
    if truncated:
        numbered = numbered[:MAX_RETURNED_CHARS]

    return {
        "path": path,
        "total_lines": total_lines,
        "shown_lines": f"{lo}-{hi}",
        "content": numbered,
        "truncated": truncated,
        "note": "Truncated — pass start_line/end_line to read a narrower range." if truncated else None,
    }


def list_repo_files(project: str, extension: str = "") -> dict:
    """Lists files in a project folder (alias, full path, or a folder name
    under an approved root — same resolution open_in_ide uses), skipping
    node_modules/.venv/.git/etc. Doesn't read contents — use read_code_file
    for that."""
    try:
        root_path = _resolve_project(project)
    except ProjectNotFound as e:
        return {"project": project, "error": str(e)}

    ext = extension.strip().lower().lstrip(".")
    results = []
    root = Path(root_path)
    _assert_approved(str(root))
    root_depth = len(root.parts)

    for dirpath, dirnames, filenames in _walk_pruned(root):
        depth = len(Path(dirpath).parts) - root_depth
        if depth >= MAX_LIST_DEPTH:
            dirnames[:] = []
            continue
        for fname in filenames:
            if ext and not fname.lower().endswith("." + ext):
                continue
            full = Path(dirpath) / fname
            if not within_approved_roots(str(full), approved_search_roots()):
                continue
            results.append(str(full.relative_to(root)))
            if len(results) >= MAX_LISTED_FILES:
                return {
                    "project": project,
                    "root": str(root),
                    "count": len(results),
                    "files": results,
                    "note": f"Stopped at {MAX_LISTED_FILES} files — narrow with extension.",
                }

    return {"project": project, "root": str(root), "count": len(results), "files": results}


def _walk_pruned(root: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
            and within_approved_roots(str(Path(dirpath) / d), approved_search_roots())
        ]
        yield dirpath, dirnames, filenames


def _make_diff(path: str, old_text: str, new_text: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"{path} (current)",
            tofile=f"{path} (proposed)",
            n=2,
        )
    )
    diff = "".join(diff_lines)
    return diff if diff else "(no textual difference)"


def _read_source(path: str) -> tuple[Path, bytes, str]:
    _assert_approved(path)  # Before reading, including during preview.
    if is_protected_edit_path(path):
        raise PathNotApproved("Cortana cannot modify Windows, installed programs, or its own runtime/configuration through chat tools.")
    _assert_text_file(path)
    file_path = Path(path).resolve(strict=True)
    if not file_path.is_file() or file_path.stat().st_size > MAX_SOURCE_BYTES:
        raise NotATextFile("Expected a source file smaller than 2 MB.")
    data = file_path.read_bytes()
    return file_path, data, data.decode("utf-8", errors="strict")


def _replacement(text: str, find: str, replace: str) -> str:
    if not find:
        raise EditAmbiguous("The text to replace cannot be empty.")
    normalized = text.replace("\r\n", "\n")
    target = find.replace("\r\n", "\n")
    count = normalized.count(target)
    if count == 0:
        raise EditNotFound("The given text was not found in the file.")
    if count != 1:
        raise EditAmbiguous(f"The given text appears {count} times; include more context.")
    edited = normalized.replace(target, replace.replace("\r\n", "\n"), 1)
    return edited.replace("\n", "\r\n") if "\r\n" in text else edited


def _prepare_edit(path: str, find: str, replace: str, reason: str = "") -> tuple[dict, str]:
    file_path, data, text = _read_source(path)
    new_text = _replacement(text, find, replace)
    if new_text == text:
        raise EditAmbiguous("The proposed edit does not change the file.")
    preview = f"Edit {file_path}" + (f" — {reason}" if reason else "") + "\n\n"
    preview += _make_diff(str(file_path), text, new_text)
    args = {
        "path": str(file_path), "find": find, "replace": replace, "reason": reason,
        "_expected_sha256": hashlib.sha256(data).hexdigest(),
    }
    return args, preview


def _edit_preview(path: str, find: str, replace: str, reason: str = "") -> str:
    return _prepare_edit(path, find, replace, reason)[1]


def _atomic_replace(file_path: Path, content: bytes, expected_hash: str):
    """Stage completely, recheck the source, then replace in one filesystem step."""
    fd, temporary = tempfile.mkstemp(prefix=".cortana-edit-", dir=file_path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        check_cancelled()
        _assert_approved(str(file_path))
        if hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_hash:
            raise EditStale("The file changed since review. Ask Cortana to prepare a new diff.")
        os.replace(temporary, file_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def edit_code_file(path: str, find: str, replace: str, reason: str = "", _expected_sha256: str = "") -> dict:
    """Replaces the first (and required-to-be-only) occurrence of `find`
    with `replace` in a text file. Only runs via execute_confirmed() after
    a human approves the diff — see this module's docstring. Backs up the
    original content first so undo_last_edit can revert it."""
    file_path, data, text = _read_source(path)
    if not _expected_sha256 or hashlib.sha256(data).hexdigest() != _expected_sha256:
        raise EditStale("The file changed since review. Ask Cortana to prepare a new diff.")
    new_text = _replacement(text, find, replace)
    new_data = new_text.encode("utf-8")

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUPS_DIR / f"{uuid.uuid4().hex}__{file_path.name}.bak"
    backup_path.write_bytes(data)
    with (BACKUPS_DIR / "edits.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "path": str(file_path), "backup": str(backup_path),
            "before_sha256": _expected_sha256, "after_sha256": hashlib.sha256(new_data).hexdigest(),
        }) + "\n")
    _atomic_replace(file_path, new_data, _expected_sha256)

    return {
        "path": path,
        "changed": True,
        "backup": str(backup_path),
        "diff": _make_diff(path, text, new_text),
    }


def _latest_edit(path: str) -> dict:
    pointer_path = BACKUPS_DIR / "edits.jsonl"
    if not pointer_path.is_file():
        raise NoBackupFound("No verified backups recorded yet.")
    canonical = str(Path(path).resolve())
    for line in reversed(pointer_path.read_text(encoding="utf-8").splitlines()):
        record = json.loads(line)
        if record.get("path") == canonical:
            backup = Path(record["backup"]).resolve()
            if not backup.is_relative_to(BACKUPS_DIR.resolve()) or not backup.is_file():
                raise NoBackupFound("The backup is missing or outside the backup directory.")
            return record
    raise NoBackupFound(f"No backup found for {path}.")


def _prepare_undo(path: str) -> tuple[dict, str]:
    file_path, data, text = _read_source(path)
    record = _latest_edit(str(file_path))
    if hashlib.sha256(data).hexdigest() != record["after_sha256"]:
        raise EditStale("The file has changes after Cortana's edit. Undo would overwrite them.")
    restored = Path(record["backup"]).read_bytes()
    if hashlib.sha256(restored).hexdigest() != record["before_sha256"]:
        raise EditStale("Backup verification failed.")
    args = {
        "path": str(file_path), "_expected_sha256": record["after_sha256"],
        "_backup": record["backup"], "_backup_sha256": record["before_sha256"],
    }
    return args, "Undo edit\n\n" + _make_diff(str(file_path), text, restored.decode("utf-8"))


def undo_last_edit(path: str, _expected_sha256: str = "", _backup: str = "", _backup_sha256: str = "") -> dict:
    """Restores a file from the most recent backup edit_code_file made for
    it. The safety net for the case a human approved something that turned
    out to be wrong."""
    file_path, data, _ = _read_source(path)
    if not _expected_sha256 or hashlib.sha256(data).hexdigest() != _expected_sha256:
        raise EditStale("The file changed since the undo preview.")
    backup = Path(_backup).resolve()
    if not _backup or not backup.is_relative_to(BACKUPS_DIR.resolve()):
        raise NoBackupFound("No approved backup was selected.")
    restored = backup.read_bytes()
    if hashlib.sha256(restored).hexdigest() != _backup_sha256:
        raise EditStale("Backup verification failed.")
    _atomic_replace(file_path, restored, _expected_sha256)
    return {"path": path, "restored_from": str(backup)}


tool(
    name="read_code_file",
    description=(
        "Read a source/code/text file with line numbers, scoped to approved project "
        "folders. Use start_line/end_line to read just a range of a large file."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full path to the file."},
            "start_line": {"type": "integer", "description": "1-based, optional."},
            "end_line": {"type": "integer", "description": "1-based inclusive, optional."},
        },
        "required": ["path"],
    },
)(read_code_file)

tool(
    name="list_repo_files",
    description=(
        "List the files inside a project folder (by alias, full path, or folder name under "
        "an approved location), skipping node_modules/.venv/.git/build/etc. Optionally filter "
        "by extension, e.g. 'py'."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "Project folder alias, name, or full path."},
            "extension": {"type": "string", "description": "Only list files with this extension, e.g. 'py'."},
        },
        "required": ["project"],
    },
)(list_repo_files)

tool(
    name="edit_code_file",
    description=(
        "Propose a targeted find-and-replace edit to a source file. `find` must match "
        "exactly one place in the file (include enough surrounding lines to make it unique) "
        "— this never runs immediately, it shows the user a diff and only applies once they "
        "approve it. Use read_code_file first so `find` matches the file exactly."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full path to the file to edit."},
            "find": {"type": "string", "description": "Exact existing text to replace — must be unique in the file."},
            "replace": {"type": "string", "description": "Text to replace it with."},
            "reason": {"type": "string", "description": "One line: why this change fixes the problem."},
        },
        "required": ["path", "find", "replace"],
    },
    prepare=_prepare_edit,
)(edit_code_file)

tool(
    name="undo_last_edit",
    description="Restore a file to its state before the most recent edit_code_file change to it.",
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Full path to the file to restore."}},
        "required": ["path"],
    },
    prepare=_prepare_undo,
)(undo_last_edit)
