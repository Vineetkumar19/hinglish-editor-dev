"""Inventory installed Start Menu applications without opening them.

By default this prints an inventory. --apply --approve <aliases> adds reviewed,
unambiguous, zero-argument EXE shortcuts and preserves all other configuration.
It never follows URL/script shortcuts, executes commands, or saves a shortcut.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_NAMES = re.compile(
    r"\b(uninstall|uninstaller|setup|installer|install|repair|update|updater|remove|reset|"
    r"developer command|command prompt|powershell|terminal|registry|regedit|disk cleanup)\b",
    re.IGNORECASE,
)
EXCLUDED_EXECUTABLES = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe",
    "mshta.exe", "rundll32.exe", "regsvr32.exe", "regedit.exe", "msiexec.exe",
    "installutil.exe", "update.exe", "uninstall.exe", "setup.exe",
}


def safe_candidate(record: dict) -> tuple[str, str] | None:
    name = re.sub(r"\s+", " ", str(record.get("name", ""))).strip().casefold()
    target = Path(str(record.get("target", "")))
    if not name or EXCLUDED_NAMES.search(name):
        return None
    if str(record.get("arguments", "")).strip():
        return None
    # UNC/network executables and relative shortcuts are never promoted.
    if not target.is_absolute() or str(target).startswith(("\\\\", "//")):
        return None
    if target.suffix.casefold() != ".exe" or target.name.casefold() in EXCLUDED_EXECUTABLES:
        return None
    if EXCLUDED_NAMES.search(target.stem):
        return None
    try:
        resolved = target.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_file():
        return None
    return name, str(resolved)


def proposed_aliases(records: list[dict]) -> dict[str, list[str]]:
    candidates: dict[str, set[str]] = {}
    for record in records:
        candidate = safe_candidate(record)
        if candidate is None:
            continue
        name, target = candidate
        aliases = {name}
        if name.startswith("intellij idea"):
            aliases.update({"intellij", "intellij idea"})
        elif name.startswith("pycharm"):
            aliases.add("pycharm")
        elif name == "visual studio code":
            aliases.update({"vs code", "vscode"})
        elif name == "google chrome":
            aliases.add("chrome")
        elif name == "microsoft edge":
            aliases.add("edge")
        elif name.startswith("adobe photoshop"):
            aliases.update({"photoshop", "adobe photoshop"})
        elif name.startswith("adobe premiere pro"):
            aliases.update({"premiere", "premiere pro", "adobe premiere pro"})
        elif name.startswith("adobe media encoder"):
            aliases.update({"media encoder", "adobe media encoder"})
        elif name.startswith("maxon cinema 4d"):
            aliases.update({"cinema 4d", "cinema4d"})
        elif name == "obs studio":
            aliases.add("obs")
        for alias in aliases:
            candidates.setdefault(alias, set()).add(target)
    # An alias that points at two installations needs a human choice.
    return {alias: [next(iter(targets))] for alias, targets in sorted(candidates.items()) if len(targets) == 1}


def merge_config(configuration: dict, discovered: dict[str, list[str]]) -> tuple[dict, dict]:
    result = json.loads(json.dumps(configuration))
    allowlist = result.setdefault("permissions", {}).setdefault("approved_app_allowlist", {})
    existing = {alias.casefold() for alias in allowlist}
    added = {}
    for alias, command in discovered.items():
        if alias.casefold() in existing:
            continue
        allowlist[alias] = command
        added[alias] = command
    return result, added


def inventory() -> list[dict]:
    if sys.platform != "win32":
        raise RuntimeError("Application discovery is supported on Windows.")
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    directories = [
        Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    records = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for link in sorted(directory.rglob("*.lnk")):
            try:
                shortcut = shell.CreateShortcut(str(link))
                records.append({
                    "name": link.stem,
                    "target": shortcut.TargetPath,
                    "arguments": shortcut.Arguments,
                    "shortcut": str(link),
                })
            except Exception:
                records.append({"name": link.stem, "target": "", "arguments": "", "error": "Shortcut could not be read."})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve", nargs="+", default=[], help="Exact reviewed aliases from the inventory to add.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "settings.json")
    parser.add_argument("--report", type=Path, default=ROOT / "tmp" / "installed-app-inventory.json")
    args = parser.parse_args()
    records = inventory()
    candidates = proposed_aliases(records)
    if args.apply and not args.approve:
        parser.error("--apply requires explicit --approve aliases from the reviewed inventory.")
    unknown = set(args.approve) - candidates.keys()
    if unknown:
        parser.error("These approved aliases have no unique safe executable: " + ", ".join(sorted(unknown)))
    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    reviewed = {alias: command for alias, command in candidates.items() if alias in args.approve}
    updated, added = merge_config(configuration, reviewed if args.apply else candidates)
    report = {
        "shortcut_count": len(records),
        "eligible_aliases": candidates,
        "new_aliases": added,
        "skipped": [
            {"name": item["name"], "target": item["target"], "has_arguments": bool(item.get("arguments")), "error": item.get("error")}
            for item in records if safe_candidate(item) is None
        ],
        "applied": args.apply,
    }
    if args.apply and added:
        # Atomic replacement after a recoverable copy, preserving every permission.
        backup = args.config.with_name("settings.before-app-discovery.json")
        if not backup.exists():
            backup.write_bytes(args.config.read_bytes())
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.config.parent, suffix=".json", delete=False) as temporary:
            json.dump(updated, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary_name = temporary.name
        os.replace(temporary_name, args.config)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "shortcut_count": len(records),
        "eligible_aliases": candidates if not args.apply else None,
        "added_aliases": added if args.apply else None,
        "applied": args.apply,
        "report": str(args.report),
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
