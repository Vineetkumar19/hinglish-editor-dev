"""A separate, credential-stripped Playwright process, controlled over pipes.

The worker owns all synchronous Playwright objects on its main thread. It never
imports backend configuration or reads .env. No debugging TCP port is opened.
"""
import atexit
import asyncio
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / ".runtime" / "browser-profile"
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
_lock = threading.RLock()
_pid_lock = threading.RLock()
_process = None
_responses = None
_known_processes = {}
_owned_processes = {}
_scan_failed = False
_cancel_generation = 0
RPC_TIMEOUT = 45


class BrowserUnavailable(RuntimeError):
    pass


def _remember_tree_unlocked():
    import psutil
    global _scan_failed
    try:
        if _process and _process.poll() is None:
            parent = psutil.Process(_process.pid)
            for process in [parent, *parent.children(recursive=True)]:
                try:
                    created = process.create_time()
                    _known_processes[process.pid] = created
                    _owned_processes[process.pid] = created
                except psutil.Error:
                    pass
        # Keep orphaned managed Chrome protected even after worker failure.
        profile = str(PROFILE).replace("\\", "/").casefold()
        for process in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            if (process.info["name"] or "").casefold() != "chrome.exe":
                continue
            args = process.info["cmdline"] or []
            if any(arg.replace("\\", "/").casefold() == "--user-data-dir=" + profile for arg in args):
                _known_processes[process.pid] = process.info["create_time"]
                for child in process.children(recursive=True):
                    try:
                        _known_processes[child.pid] = child.create_time()
                    except psutil.Error:
                        pass
        _scan_failed = False
    except psutil.Error:
        _scan_failed = True
    for pid, created in list(_known_processes.items()):
        try:
            if psutil.Process(pid).create_time() != created:
                _known_processes.pop(pid, None)
        except psutil.NoSuchProcess:
            _known_processes.pop(pid, None)
        except psutil.AccessDenied:
            _scan_failed = True
    for pid, created in list(_owned_processes.items()):
        try:
            if psutil.Process(pid).create_time() != created:
                _owned_processes.pop(pid, None)
        except psutil.NoSuchProcess:
            _owned_processes.pop(pid, None)


def _remember_tree():
    with _pid_lock:
        _remember_tree_unlocked()


def managed_browser_active():
    _remember_tree()
    return bool((_process and _process.poll() is None) or _known_processes or _scan_failed)


def managed_browser_process_ids():
    _remember_tree()
    # An incomplete lookup forces the caller to block all generic input.
    return set() if _scan_failed else set(_known_processes)


def _read_responses(process, responses):
    try:
        for line in process.stdout:
            if len(line) > 100000:
                responses.put(None)
                return
            responses.put(json.loads(line))
    except Exception:
        pass
    finally:
        responses.put(None)


def _start():
    global _process, _responses
    if _process and _process.poll() is None:
        return
    from core.processes import public_environment
    _responses = queue.Queue()
    _process = subprocess.Popen(
        [sys.executable, "-I", "-u", str(Path(__file__).resolve()), "--worker", str(os.getpid())],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", env=public_environment(), shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    threading.Thread(target=_read_responses, args=(_process, _responses), daemon=True).start()
    _remember_tree()


def close_browser():
    """Stop only this managed browser tree; retain IDs until death is confirmed."""
    import psutil
    global _process, _cancel_generation
    _cancel_generation += 1
    # Merely importing this module or observing another backend's profile must
    # never grant process-termination ownership.
    if _process is None and not _owned_processes:
        return
    _remember_tree()
    owned = []
    for pid, created in list(_owned_processes.items()):
        try:
            process = psutil.Process(pid)
            if process.create_time() == created:
                owned.append(process)
                process.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(owned, timeout=2)
    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            pass
    if alive:
        _, still_alive = psutil.wait_procs(alive, timeout=2)
        if still_alive:
            raise BrowserUnavailable("The dedicated browser could not be stopped completely. Close it manually before continuing.")
    if _process and _process.poll() is not None:
        _process = None
    _remember_tree()


def browser_request(operation, payload=None):
    generation = _cancel_generation
    if operation not in {"status", "open", "prepare", "resume", "select"}:
        raise BrowserUnavailable("Unsupported browser operation.")
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise BrowserUnavailable("Invalid browser request.")
    if operation == "status" and not (_process and _process.poll() is None):
        return {"integrations": [{"platform": name, "status": "not_open", "note": "Open the app to sign in manually."}
                                 for name in ("whatsapp", "gmail", "instagram")],
                "browser": {"status": "closed", "note": "Dedicated browser has not started."}}
    from core import tasks
    from core.draft_adapters import validate_payload
    from core.tool_registry import serialized_effects
    from contextlib import nullcontext
    if operation == "prepare":
        payload = validate_payload(payload)
    with (serialized_effects() if operation != "status" else nullcontext()), _lock:
        if generation != _cancel_generation:
            raise BrowserUnavailable("Browser action cancelled.")
        tasks.check_cancelled()
        _start()
        process, responses = _process, _responses
        request_id = uuid4().hex
        message = json.dumps({"id": request_id, "operation": operation, "payload": payload}, ensure_ascii=True)
        if len(message) > 65000:
            raise BrowserUnavailable("Browser request is too large.")
        try:
            process.stdin.write(message + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + RPC_TIMEOUT
            while time.monotonic() < deadline:
                tasks.check_cancelled()
                if generation != _cancel_generation:
                    raise BrowserUnavailable("Browser action cancelled.")
                try:
                    response = responses.get(timeout=.15)
                except queue.Empty:
                    continue
                if response is None:
                    raise BrowserUnavailable("The dedicated browser closed. Reopen the app and resume manually.")
                if response.get("id") != request_id:
                    raise BrowserUnavailable("Browser response could not be verified.")
                tasks.check_cancelled()
                if generation != _cancel_generation:
                    raise BrowserUnavailable("Browser action cancelled.")
                _remember_tree()
                if response.get("error"):
                    raise BrowserUnavailable(response["error"])
                return response["result"]
            raise BrowserUnavailable("Browser preparation timed out and was stopped. Review any saved draft before retrying.")
        except asyncio.CancelledError:
            close_browser()
            raise
        except (OSError, BrowserUnavailable):
            close_browser()
            raise BrowserUnavailable("The browser action stopped or timed out. Nothing was sent. Reopen the app to review any draft.") from None


def _parent_watchdog(parent_pids):
    import psutil
    try:
        watched = {pid: psutil.Process(pid).create_time() for pid in parent_pids}
    except psutil.Error:
        os._exit(1)
    while True:
        time.sleep(1)
        try:
            if all(psutil.Process(pid).create_time() == created for pid, created in watched.items()):
                continue
        except psutil.Error:
            pass
        try:
            children = psutil.Process().children(recursive=True)
            for child in reversed(children):
                try:
                    child.terminate()
                except psutil.Error:
                    pass
        finally:
            os._exit(0)


def _worker(backend_pid):
    # -I ignores PYTHONPATH and user site packages. Only this source directory is
    # inserted; draft_adapters imports no settings, secrets or environment files.
    sys.path.insert(0, str(ROOT / "agent"))
    from core.draft_adapters import DraftBrowser, DraftProblem
    from playwright.sync_api import sync_playwright
    import psutil
    if backend_pid not in {process.pid for process in psutil.Process().parents()}:
        raise RuntimeError("Browser worker must be owned by its backend.")
    threading.Thread(target=_parent_watchdog, args=({backend_pid, os.getppid()},), daemon=True).start()
    context = None
    service = None
    with sync_playwright() as playwright:
        try:
            for line in sys.stdin:
                request_id = ""
                try:
                    if len(line) > 65001:
                        raise DraftProblem("Browser request exceeds the size limit.")
                    request = json.loads(line)
                    if not isinstance(request, dict) or set(request) != {"id", "operation", "payload"}:
                        raise DraftProblem("Invalid browser request.")
                    request_id = request["id"]
                    if not isinstance(request_id, str) or len(request_id) != 32:
                        raise DraftProblem("Invalid request identifier.")
                    if request["operation"] not in {"status", "open", "prepare", "resume", "select"} or not isinstance(request["payload"], dict):
                        raise DraftProblem("Unsupported browser operation.")
                    if context is None:
                        if not CHROME.is_file():
                            raise DraftProblem("Chrome is not installed at the configured path.")
                        PROFILE.mkdir(parents=True, exist_ok=True)
                        context = playwright.chromium.launch_persistent_context(
                            str(PROFILE), executable_path=str(CHROME), headless=False,
                            locale="en-US", accept_downloads=False, timeout=20000,
                            chromium_sandbox=True,
                            env={key: value for key, value in os.environ.items() if not key.upper().startswith("CORTANA_")},
                        )
                        service = DraftBrowser(context)
                    result = service.handle(request["operation"], request["payload"])
                    response = {"id": request_id, "result": result}
                except Exception as error:
                    response = {"id": request_id, "error": str(error) if isinstance(error, DraftProblem) else "The browser interface was unavailable. Nothing was sent."}
                print(json.dumps(response, ensure_ascii=True), flush=True)
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--worker" and sys.argv[2].isdigit():
    _worker(int(sys.argv[2]))
elif __name__ != "__main__":
    atexit.register(close_browser)
