"""App-first draft sessions. Cancel stops our worker, never the user's apps."""
import asyncio
import atexit
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
_lock = threading.RLock()
_worker_lock = threading.RLock()
_process = None
_responses = None
_generation = 0
_drafts = {}


class DesktopDraftUnavailable(RuntimeError):
    pass


def _read(process, responses):
    try:
        for line in process.stdout:
            responses.put(json.loads(line))
    except Exception:
        pass
    finally:
        responses.put(None)


def cancel_drafts():
    global _generation, _process
    with _worker_lock:
        _generation += 1
        process, _process = _process, None
        _drafts.clear()
    if process and process.poll() is None:
        # The worker never launches user applications. Only this Python worker
        # and its venv interpreter child belong to us.
        import psutil
        try:
            children = psutil.Process(process.pid).children(recursive=True)
            for child in children:
                if child.name().casefold() in {"python.exe", "pythonw.exe"}:
                    child.terminate()
        except psutil.Error:
            pass
        try:
            process.terminate()
        except OSError:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def _start():
    global _process, _responses
    if _process and _process.poll() is None:
        return
    from core.processes import public_environment
    _responses = queue.Queue()
    _process = subprocess.Popen(
        [sys.executable, "-I", "-u", str(Path(__file__).resolve()), "--worker", str(os.getpid())],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        encoding="utf-8", text=True, shell=False, env=public_environment(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    threading.Thread(target=_read, args=(_process, _responses), daemon=True).start()


def _prepare_in_app(draft, generation):
    from core import tasks
    with _worker_lock:
        tasks.check_cancelled()
        if generation != _generation:
            raise DesktopDraftUnavailable("Draft preparation stopped.")
        _start()
        process, responses = _process, _responses
        request_id = uuid4().hex
        process.stdin.write(json.dumps({"id": request_id, "draft": draft}, ensure_ascii=True) + "\n")
        process.stdin.flush()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        tasks.check_cancelled()
        if generation != _generation:
            raise DesktopDraftUnavailable("Draft preparation stopped.")
        try:
            result = responses.get(timeout=.1)
        except queue.Empty:
            continue
        tasks.check_cancelled()
        if generation != _generation:
            raise DesktopDraftUnavailable("Draft preparation stopped.")
        if result is None or result.get("id") != request_id:
            raise DesktopDraftUnavailable("The app worker stopped. Your apps were left open.")
        return result["result"]
    raise DesktopDraftUnavailable("The app did not respond in time. Your apps were left open.")


def draft_request(operation, payload=None):
    from core import tasks
    from core.communication_targets import open_target, target, sender_email, preferences
    from core.draft_adapters import validate_payload, DraftProblem
    from core.tool_registry import serialized_effects
    payload = payload or {}
    generation = _generation
    if operation == "status":
        return {
            "integrations": [{**target(platform), "status": "available",
                              "note": ("Installed app preferred." if target(platform)["transport"] == "application"
                                       else "Uses your normal Chrome profile.")
                              + (f" Sender: {sender_email()}." if platform == "gmail" else "")}
                             for platform in ("whatsapp", "gmail", "instagram")],
            "browser": {"status": "normal", "note": "Installed apps first. Websites reuse your Chrome profile and logins."},
        }
    with serialized_effects(), _lock:
        tasks.check_cancelled()
        if generation != _generation:
            raise DesktopDraftUnavailable("Queued draft action was cancelled.")
        now = time.monotonic()
        for key in list(_drafts):
            if now - _drafts[key]["created"] >= 900:
                _drafts.pop(key, None)
        if operation == "open":
            if set(payload) != {"platform"}:
                raise DraftProblem("Unexpected app-open fields.")
            return open_target(payload["platform"])
        if operation == 'calendar_availability':
            from datetime import date
            from tools.communication import _open_calendar_route
            day = date.fromisoformat(payload['date'])
            sender = _open_calendar_route(f'r/agenda/{day.year}/{day.month}/{day.day}')
            try:
                return _prepare_in_app({'platform':'calendar','transport':'chrome',
                    'operation':'calendar_availability','sender':sender,'date':day.isoformat()}, generation)
            except (asyncio.CancelledError, DesktopDraftUnavailable):
                cancel_drafts()
                raise
        if operation == 'close_site':
            if set(payload) != {'host'} or not isinstance(payload['host'], str):
                raise DraftProblem('Choose the exact website to close.')
            try:
                return _prepare_in_app({'platform': 'browser', 'operation': 'close_site', **payload}, generation)
            except (asyncio.CancelledError, DesktopDraftUnavailable):
                cancel_drafts()
                raise
        if operation == "inbox":
            if set(payload) != {'platform'} or payload['platform'] not in {'whatsapp', 'instagram'}:
                raise DraftProblem('Choose WhatsApp or Instagram messages.')
            destination = open_target(payload['platform'])
            return _prepare_in_app({**target(payload['platform']), 'operation':'inbox'}, generation)
        if operation == "prepare":
            data = validate_payload(payload)
            draft = next((item for item in _drafts.values()
                          if all(item.get(key) == value for key, value in data.items())), None)
            if draft is None:
                if len(_drafts) >= 50:
                    raise DraftProblem("Too many pending drafts.")
                draft = {**data, **target(data["platform"]), "draft_id": uuid4().hex,
                         "created": now, "prepared": False}
                if data["platform"] == "gmail":
                    draft["sender"] = sender_email()
                _drafts[draft["draft_id"]] = draft
                destination = open_target(data["platform"])
                if destination.get('window_handle'):
                    draft['window_handle'] = destination['window_handle']
        elif operation == "resume":
            if set(payload) != {"draft_id"} or payload.get("draft_id") not in _drafts:
                raise DraftProblem("This draft expired or Cortana restarted. Prepare it again.")
            draft = _drafts[payload["draft_id"]]
        elif operation == "select":
            raise DraftProblem("Select the intended conversation in the installed app, then resume.")
        else:
            raise DraftProblem("Unsupported draft operation.")
        if draft.get('platform') == 'gmail':
            previous = [item for item in _drafts.values() if item.get('platform') == 'gmail'
                        and item.get('prepared') and item['draft_id'] != draft['draft_id']]
            if previous:
                last = max(previous, key=lambda item: item['created'])
                # Trusted verified records stay in backend RAM across a private
                # worker restart. Only these fields enter the worker; never let
                # user payloads claim that an arbitrary draft was prepared.
                draft['_previous_gmail'] = {key: last[key] for key in (
                    'platform', 'transport', 'recipient', 'body', 'subject', 'sender', 'draft_id', 'prepared')}
        try:
            request = {**draft, 'recipient': draft.get('selected_recipient', draft['recipient'])}
            if draft['platform'] == 'whatsapp':
                request['top_result'] = preferences().get('whatsapp_contact_order') == 'top_result'
            result = _prepare_in_app(request, generation)
        except (asyncio.CancelledError, DesktopDraftUnavailable):
            cancel_drafts()
            raise
        except OSError as error:
            cancel_drafts()
            raise DesktopDraftUnavailable("The app worker could not complete this draft. Your apps were left open.") from error
        if result.get("status") == "draft_ready":
            draft["prepared"] = True
            if result.get('selected_recipient'):
                draft['selected_recipient'] = result['selected_recipient']
        return {**result, "draft_id": draft["draft_id"], "platform": draft["platform"],
                "recipient": draft.get('selected_recipient', draft['recipient']), "transport": draft["transport"],
                "sender": draft.get("sender", ""),
                "preview": {"body": draft["body"], "subject": draft["subject"]}}


def _watch_parent(parent_pid):
    import psutil
    try:
        created = psutil.Process(parent_pid).create_time()
    except psutil.Error:
        os._exit(1)
    while True:
        time.sleep(1)
        try:
            if psutil.Process(parent_pid).create_time() == created:
                continue
        except psutil.Error:
            pass
        os._exit(0)


def worker(parent_pid):
    sys.path.insert(0, str(ROOT / "agent"))
    from core.native_draft_ui import NativeDraftUI
    from core.draft_adapters import DraftProblem
    threading.Thread(target=_watch_parent, args=(parent_pid,), daemon=True).start()
    ui = NativeDraftUI()
    for line in sys.stdin:
        request = json.loads(line)
        try:
            draft = request['draft']
            operation = draft.get('operation')
            if operation == 'calendar_availability':
                result = ui.calendar_availability(draft)
            else:
                result = ui.prepare(draft)
        except DraftProblem as error:
            ui.diagnose(request['draft'])
            result = {"status": "needs_app", "note": str(error)}
        except Exception:
            import traceback
            (ROOT / 'tmp' / 'live-native-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            ui.diagnose(request['draft'])
            result = {"status": "needs_app",
                      "note": "The app's accessibility controls could not be verified. Bring the intended conversation to the front and resume. No Send action is available."}
        try:
            (ROOT / 'tmp' / 'live-draft-timing.json').write_text(json.dumps({
                'platform': request['draft']['platform'], 'status': result.get('status'),
                'recipient': request['draft'].get('recipient', ''),
                'note': result.get('note', ''),
                'trace': ui.trace,
            }), encoding='utf-8')
        except Exception:
            pass
        print(json.dumps({"id": request["id"], "result": result}, ensure_ascii=True), flush=True)


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--worker":
    worker(int(sys.argv[2]))
elif __name__ != "__main__":
    atexit.register(cancel_drafts)
