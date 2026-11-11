"""Security regressions. These tests never send mouse/keyboard input."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import threading
import time
import json
import subprocess
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT)]

from core import db
from core.permissions import RiskLevel
from core import processes, tasks
from core.security import LocalSessionAuth
from core.tool_registry import (
    REGISTRY, ConfirmationExpiredOrResolved, ToolArgumentsInvalid,
    Tool, ToolDenied, ToolNeedsConfirmation, dispatch, execute_confirmed, reject_confirmed, tool,
)
from core.communication_policy import DraftOnlyViolation, assert_generic_input_allowed
from tools import code, computer, dev, files, openpath, web


TOKEN = "security-test-token-" + "a" * 48


def request_auth(monkeypatch, path="/private", *, token=TOKEN, headers=None, peer="127.0.0.1", host="127.0.0.1"):
    monkeypatch.setenv("CORTANA_API_TOKEN", token)
    app = FastAPI()
    app.add_middleware(LocalSessionAuth)

    @app.get("/{path:path}")
    async def any_route(path):
        return {"ok": True}

    async def run():
        transport = httpx.ASGITransport(app=app, client=(peer, 1234))
        async with httpx.AsyncClient(transport=transport, base_url=f"http://{host}") as client:
            return await client.get(path, headers=headers or {})
    return asyncio.run(run())


def test_auth_required_and_valid_session(monkeypatch):
    assert request_auth(monkeypatch).status_code == 401
    assert request_auth(monkeypatch, headers={"Authorization": "Bearer wrong"}).status_code == 401
    result = request_auth(monkeypatch, headers={"Authorization": f"Bearer {TOKEN}"})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"


def test_auth_fail_closed_if_launcher_did_not_supply_token(monkeypatch):
    assert request_auth(monkeypatch, token="").status_code == 503
    assert request_auth(monkeypatch, token="short").status_code == 503
    assert request_auth(monkeypatch, "/api/health", token="").status_code == 200


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:5173", "null", ""])
def test_origin_rejected_even_with_valid_token(monkeypatch, origin):
    result = request_auth(monkeypatch, headers={"Authorization": f"Bearer {TOKEN}", "Origin": origin})
    assert result.status_code == 403


def test_dns_rebinding_and_remote_client_rejected(monkeypatch):
    assert request_auth(monkeypatch, host="attacker.example", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 403
    assert request_auth(monkeypatch, peer="192.168.1.7", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 403


def test_duplicate_security_headers_rejected(monkeypatch):
    headers = [("Authorization", f"Bearer {TOKEN}"), ("Authorization", f"Bearer {TOKEN}")]
    assert request_auth(monkeypatch, headers=headers).status_code == 403


def test_every_real_api_route_requires_session_auth(monkeypatch):
    import main
    monkeypatch.setenv("CORTANA_API_TOKEN", TOKEN)
    monkeypatch.setattr(main.app, "middleware_stack", None)
    paths = [
        ("POST", "/api/chat"), ("POST", "/api/stt"), ("POST", "/api/confirm/1"),
        ("GET", "/api/memory/facts"), ("POST", "/api/screen/capture"),
        ("POST", "/api/tasks/request-123/cancel"), ("GET", "/api/status"),
        ("GET", "/api/integrations/status"), ("POST", "/api/integrations/gmail/open"),
        ("POST", "/api/drafts/prepare"), ("POST", "/api/drafts/abc/select"),
        ("POST", "/api/drafts/cancel"),
        ("GET", "/docs"), ("GET", "/openapi.json"),
    ]
    async def run():
        transport = httpx.ASGITransport(app=main.app, client=("127.0.0.1", 1234))
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            for method, path in paths:
                result = await client.request(method, path)
                assert result.status_code == 401, (method, path, result.text)
            assert (await client.get("/api/health")).status_code == 200
            for path in ["/docs", "/openapi.json"]:
                assert (await client.get(path, headers={"Authorization": f"Bearer {TOKEN}"})).status_code == 404
    asyncio.run(run())


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTANA_API_TOKEN", TOKEN)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "state" / "test.db")
    monkeypatch.setattr(db, "_schema_ready", False)
    db.init_db()
    approved = tmp_path / "Approved"
    approved.mkdir()
    monkeypatch.setattr(files, "approved_search_roots", lambda: [str(approved)])
    monkeypatch.setattr(code, "approved_search_roots", lambda: [str(approved)])
    monkeypatch.setattr(dev, "approved_search_roots", lambda: [str(approved)])
    monkeypatch.setattr(dev, "approved_folder_aliases", lambda: {})
    monkeypatch.setattr(openpath, "approved_search_roots", lambda: [str(approved)])
    monkeypatch.setattr(code, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setitem(sys.modules, "core.browser_session", SimpleNamespace(
        managed_browser_active=lambda: False, managed_browser_process_ids=lambda: set(),
    ))
    yield approved


def test_component_path_boundaries_and_traversal(isolated):
    roots = [str(isolated)]
    assert files.within_approved_roots(str(isolated / "example.py"), roots)
    assert files.within_approved_roots(str(isolated), roots)
    assert not files.within_approved_roots(str(isolated.parent / "Approved-Other" / "private.py"), roots)
    assert not files.within_approved_roots(str(isolated / ".." / "private.py"), roots)
    assert not files.within_approved_roots(str(isolated / "ok.txt") + ":secret", roots)


def test_symlink_escape_is_rejected(isolated):
    outside = isolated.parent / "private"
    outside.mkdir()
    link = isolated / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"Symbolic-link privilege unavailable: {error}")
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    assert not files.within_approved_roots(str(link / "private.py"), [str(isolated)])


@pytest.mark.parametrize("relative", [
    ".env", ".env.production", ".git/config", ".codex/auth.json",
    ".ssh/id_rsa", ".aws/credentials", "private.pem", "credentials.json",
    "AppData/Local/Google/Chrome/User Data/Default/Login Data",
    "AppData/Roaming/Mozilla/Firefox/Profiles/user/logins.json",
    "Windows/System32/config/SAM",
    ".runtime/browser-profile/Default/Session Storage/data.txt",
    ".runtime/browser-profile/Default/Preferences",
])
def test_sensitive_stores_are_blocked_inside_approved_root(isolated, relative):
    assert not files.within_approved_roots(str(isolated / relative), [str(isolated)])
    assert files.within_approved_roots(str(isolated / ".env.example"), [str(isolated)])


def test_project_resolution_cannot_bypass_roots(isolated):
    outside = isolated.parent / "unapproved"
    outside.mkdir()
    with pytest.raises(dev.ProjectNotFound):
        dev._resolve_project(str(outside))


def test_explicit_project_path_takes_priority_over_a_matching_alias(isolated, monkeypatch):
    documents = isolated / "Documents"
    project = documents / "terraform-demo"
    project.mkdir(parents=True)
    monkeypatch.setattr(dev, "approved_folder_aliases", lambda: {"documents": str(documents)})
    monkeypatch.setattr(dev, "approved_search_roots", lambda: [str(isolated)])
    assert dev._resolve_project(str(project)) == str(project)
    with pytest.raises(dev.ProjectNotFound):
        dev._resolve_project(str(documents / "missing-project"))


def test_own_runtime_cannot_be_modified_even_if_drive_is_approved(isolated, monkeypatch):
    monkeypatch.setattr(code, "approved_search_roots", lambda: [str(ROOT)])
    path = ROOT / "agent" / "core" / "tool_registry.py"
    with pytest.raises(code.PathNotApproved, match="own runtime"):
        dispatch("edit_code_file", {"path": str(path), "find": "dispatch", "replace": "bypass"})


def test_system_edits_blocked_even_if_read_scope_contains_them(isolated, monkeypatch):
    system = isolated / "Windows"
    system.mkdir()
    source = system / "settings.ini"
    source.write_text("old")
    monkeypatch.setenv("SystemRoot", str(system))
    with pytest.raises(code.PathNotApproved, match="Windows"):
        pending_edit(source)
    assert source.read_text() == "old"


@pytest.mark.parametrize("suffix", [".exe", ".cmd", ".ps1", ".bat", ".py", ".lnk", ".url", ".reg", ".vbs", ".html"])
def test_file_open_cannot_launch_executable_or_script(isolated, suffix):
    path = isolated / ("danger" + suffix)
    path.write_text("not executed")
    with pytest.raises(openpath.PathNotApproved, match="file type"):
        openpath.open_path(str(path))


def test_preview_does_not_read_outside_scope(isolated, monkeypatch):
    outside = isolated.parent / "private.py"
    outside.write_text("private source")
    original = Path.read_bytes
    touched = []
    def record(path):
        touched.append(path)
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", record)
    with pytest.raises(code.PathNotApproved):
        dispatch("edit_code_file", {"path": str(outside), "find": "private", "replace": "changed"})
    assert outside not in touched


def pending_edit(path, find="old", replacement="new"):
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch("edit_code_file", {"path": str(path), "find": find, "replace": replacement})
    return caught.value.confirmation_id


def test_reviewed_edit_applies_once_and_keeps_exact_backup(isolated):
    path = isolated / "example.py"
    original = b"old = 1\r\nprint(old)\r\n"
    path.write_bytes(original)
    confirmation = pending_edit(path, "old = 1", "new = 2")
    assert path.read_bytes() == original
    result = execute_confirmed(confirmation)
    assert path.read_bytes() == b"new = 2\r\nprint(old)\r\n"
    assert Path(result["backup"]).read_bytes() == original
    with pytest.raises(ConfirmationExpiredOrResolved):
        execute_confirmed(confirmation)


def test_modified_file_invalidates_approved_diff(isolated):
    path = isolated / "example.py"
    path.write_text("old\n", encoding="utf-8")
    confirmation = pending_edit(path)
    path.write_text("old\n# user added this after review\n", encoding="utf-8")
    with pytest.raises(code.EditStale):
        execute_confirmed(confirmation)
    assert path.read_text() == "old\n# user added this after review\n"
    assert db.get_pending_confirmation(confirmation)["status"] == "failed"


def test_undo_requires_review_and_preserves_later_user_changes(isolated):
    path = isolated / "example.py"
    path.write_text("old\n", encoding="utf-8")
    execute_confirmed(pending_edit(path))
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch("undo_last_edit", {"path": str(path)})
    path.write_text("new\n# more work\n", encoding="utf-8")
    with pytest.raises(code.EditStale):
        execute_confirmed(caught.value.confirmation_id)
    assert path.read_text() == "new\n# more work\n"


def test_undo_success_restores_original(isolated):
    path = isolated / "example.py"
    path.write_text("old\n", encoding="utf-8")
    execute_confirmed(pending_edit(path))
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch("undo_last_edit", {"path": str(path)})
    execute_confirmed(caught.value.confirmation_id)
    assert path.read_text() == "old\n"


def test_invalid_tool_arguments_never_create_approval(isolated):
    path = isolated / "example.py"
    path.write_text("old")
    for args in [
        {"path": str(path), "find": "old"},
        {"path": str(path), "find": 3, "replace": "new"},
        {"path": str(path), "find": "old", "replace": "new", "_expected_sha256": "bypass"},
    ]:
        with pytest.raises(ToolArgumentsInvalid):
            dispatch("edit_code_file", args)
    assert path.read_text() == "old"


def test_confirmation_cannot_survive_desktop_session_restart(isolated, monkeypatch):
    path = isolated / "example.py"
    path.write_text("old")
    confirmation = pending_edit(path)
    monkeypatch.setenv("CORTANA_API_TOKEN", "different-session-" + "z" * 40)
    with pytest.raises(ConfirmationExpiredOrResolved):
        execute_confirmed(confirmation)
    assert path.read_text() == "old"


def test_rejection_is_final(isolated):
    path = isolated / "example.py"
    path.write_text("old")
    confirmation = pending_edit(path)
    assert reject_confirmed(confirmation)["rejected"]
    with pytest.raises(ConfirmationExpiredOrResolved):
        execute_confirmed(confirmation)
    assert path.read_text() == "old"


def test_atomic_claim_only_executes_once_under_concurrent_approval(isolated):
    calls = []
    lock = threading.Lock()
    name = "_test_atomic_approval"
    @tool(name=name, description="test", risk=RiskLevel.HIGH, parameters={"type": "object", "properties": {}})
    def action():
        with lock:
            calls.append(1)
        time.sleep(0.03)
        return {"done": True}
    try:
        with pytest.raises(ToolNeedsConfirmation) as caught:
            dispatch(name, {})
        confirmation = caught.value.confirmation_id
        def approve(_):
            try:
                execute_confirmed(confirmation)
                return True
            except ConfirmationExpiredOrResolved:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(approve, range(8)))
        assert sum(outcomes) == 1
        assert len(calls) == 1
    finally:
        REGISTRY.pop(name, None)


@pytest.mark.parametrize("name,args", [
    ("press_keys", {"keys": "enter"}),
    ("type_text", {"text": "hello"}),
    ("click_at", {"x": 4, "y": 5}),
    ("click_element", {"name": "Send"}),
    ("browser_control", {"action": "reload"}),
])
def test_generic_input_never_runs_without_approval(isolated, monkeypatch, name, args):
    snapshot = {"handle": 1, "process": 123, "title": "Test editor", "rect": [0, 0, 500, 500]}
    monkeypatch.setattr(computer, "_window_snapshot", lambda handle=None: snapshot)
    assert REGISTRY[name].risk == RiskLevel.HIGH
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch(name, args)
    assert "Test editor" in caught.value.preview
    row = db.get_pending_confirmation(caught.value.confirmation_id)
    assert row["args"]["_target_window"] == snapshot


def test_generic_input_stale_window_prevents_execution(isolated, monkeypatch):
    snapshot = {"handle": 1, "process": 123, "title": "Test editor", "rect": [0, 0, 500, 500]}
    monkeypatch.setattr(computer, "_window_snapshot", lambda handle=None: snapshot)
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch("type_text", {"text": "hello"})
    snapshot = {**snapshot, "title": "Different app"}
    with pytest.raises(Exception, match="window changed"):
        execute_confirmed(caught.value.confirmation_id)


@pytest.mark.parametrize("owner", ["desktop", "backend", "launcher"])
def test_generic_input_cannot_target_cortana_processes_with_disguised_title(isolated, monkeypatch, owner):
    monkeypatch.setenv("CORTANA_DESKTOP_PID", "432100")
    process = {"desktop": 432100, "backend": os.getpid(), "launcher": os.getppid()}[owner]
    snapshot = {"handle": 1, "process": process, "title": "Untitled", "rect": [0, 0, 500, 500]}
    monkeypatch.setattr(computer, "_window_snapshot", lambda handle=None: snapshot)
    with pytest.raises(RuntimeError, match="Focus the application"):
        dispatch("type_text", {"text": "approve"})


def test_source_read_refuses_oversized_file_before_loading_contents(isolated, monkeypatch):
    path = isolated / "large.py"
    with path.open("wb") as output:
        output.seek(code.MAX_SOURCE_BYTES)
        output.write(b"\n")
    def fail_read(*args, **kwargs):
        pytest.fail("Oversized source must be rejected before reading it into memory.")
    monkeypatch.setattr(Path, "read_text", fail_read)
    assert "larger than 2 MB" in code.read_code_file(str(path))["error"]


@pytest.mark.parametrize("name,args", [
    ("press_keys", {"keys": "enter"}),
    ("type_text", {"text": "send\n"}),
    ("click_at", {"x": 10, "y": 10}),
    ("click_element", {"name": "Send"}),
    ("browser_control", {"action": "next tab"}),
    ("scroll_screen", {"direction": "down"}),
])
@pytest.mark.parametrize("title,executable", [
    ("Inbox - Gmail", "chrome.exe"),
    ("WhatsApp", "chrome.exe"),
    ("Instagram", "chrome.exe"),
    ("Contact name", "WhatsApp.Root.exe"),
])
def test_generic_input_cannot_bypass_draft_only_policy(isolated, monkeypatch, name, args, title, executable):
    snapshot = {
        "handle": 1, "process": 123, "title": title, "executable": executable,
        "rect": [0, 0, 500, 500],
    }
    monkeypatch.setattr(computer, "_window_snapshot", lambda handle=None: snapshot)
    with pytest.raises(DraftOnlyViolation):
        dispatch(name, args)


def test_previous_approval_cannot_send_after_browser_becomes_protected(isolated, monkeypatch):
    snapshot = {"handle": 1, "process": 123, "title": "New Tab", "rect": [0, 0, 500, 500]}
    monkeypatch.setattr(computer, "_window_snapshot", lambda handle=None: snapshot)
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch("press_keys", {"keys": "enter"})
    monkeypatch.setitem(sys.modules, "core.browser_session", SimpleNamespace(
        managed_browser_active=lambda: True, managed_browser_process_ids=lambda: {123},
    ))
    with pytest.raises(DraftOnlyViolation):
        execute_confirmed(caught.value.confirmation_id)
    assert db.get_pending_confirmation(caught.value.confirmation_id)["status"] == "failed"


def test_unknown_managed_browser_owner_fails_closed(isolated, monkeypatch):
    monkeypatch.setitem(sys.modules, "core.browser_session", SimpleNamespace(
        managed_browser_active=lambda: True, managed_browser_process_ids=lambda: set(),
    ))
    with pytest.raises(DraftOnlyViolation):
        assert_generic_input_allowed({"process": 123, "title": "Unknown"})


def test_explicit_communication_task_cannot_use_generic_input(isolated):
    context = tasks.current.set(tasks.Work(task=None, communication_allowed=True))
    try:
        with pytest.raises(DraftOnlyViolation):
            assert_generic_input_allowed({"process": 123, "title": "Text editor"})
    finally:
        tasks.current.reset(context)


def test_draft_tool_requires_explicit_user_intent_before_any_work(isolated, monkeypatch):
    called = []
    monkeypatch.setitem(REGISTRY, "prepare_message_draft", Tool(
        name="prepare_message_draft", description="test draft", risk=RiskLevel.MEDIUM,
        parameters={"type": "object", "properties": {}},
        func=lambda: called.append(True) or {"drafted": True},
    ))
    with pytest.raises(ToolDenied):
        dispatch("prepare_message_draft", {})
    assert called == []
    context = tasks.current.set(tasks.Work(task=None, communication_allowed=True))
    try:
        assert dispatch("prepare_message_draft", {})["drafted"]
    finally:
        tasks.current.reset(context)
    assert called == [True]


def test_forged_confirmation_cannot_grant_communication_intent(isolated, monkeypatch):
    called = []
    monkeypatch.setitem(REGISTRY, "prepare_message_draft", Tool(
        name="prepare_message_draft", description="test draft", risk=RiskLevel.MEDIUM,
        parameters={"type": "object", "properties": {}}, func=lambda: called.append(True),
    ))
    confirmation = db.create_pending_confirmation("prepare_message_draft", {}, "test")
    with pytest.raises(ToolDenied):
        execute_confirmed(confirmation)
    assert called == []


def test_keyboard_tool_refuses_window_switch_followed_by_enter(monkeypatch):
    monkeypatch.setattr(computer, "WINDOWS", True)
    assert computer.press_keys("alt+tab+enter")["pressed"] is False


@pytest.mark.parametrize("text", ["hello\n", "hello\r", "hello\t", "hello\x1b"])
def test_generic_text_cannot_embed_submit_or_navigation_keys(monkeypatch, text):
    monkeypatch.setattr(computer, "WINDOWS", True)
    assert computer.type_text(text)["typed"] is False


def test_coordinate_click_cannot_target_a_different_window(monkeypatch):
    import ctypes
    class ApiFunction:
        def __init__(self, result):
            self.result = result
        def __call__(self, *args):
            return self.result
    user32 = SimpleNamespace(
        WindowFromPoint=ApiFunction(22), GetAncestor=ApiFunction(22),
    )
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)
    monkeypatch.setattr(computer, "_window_snapshot", lambda handle=None: {
        "handle": 11, "process": 123, "title": "Reviewed editor",
    })
    with pytest.raises(Exception, match="outside the reviewed"):
        computer._assert_point_target(100, 100)


def test_model_website_requests_need_review_but_exact_user_launch_can_proceed(isolated, monkeypatch):
    called = []
    monkeypatch.setattr(REGISTRY["open_website"], "func", lambda **args: called.append(args) or {"opened": True})
    with pytest.raises(ToolNeedsConfirmation) as caught:
        dispatch("open_website", {"url": "https://example.org/search?q=private"})
    assert "https://example.org/search?q=private" in caught.value.preview
    assert called == []
    result = dispatch("open_website", {"site": "youtube"}, user_requested_launch=True)
    assert result["opened"]
    assert called == [{"site": "youtube"}]


def test_launch_exception_cannot_bypass_file_edit_review(isolated):
    path = isolated / "example.py"
    path.write_text("old")
    with pytest.raises(ToolNeedsConfirmation):
        dispatch("edit_code_file", {"path": str(path), "find": "old", "replace": "new"}, user_requested_launch=True)
    assert path.read_text() == "old"


def test_cancelled_task_cannot_start_another_tool(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(REGISTRY["open_website"], "func", lambda **args: calls.append(args))
    work = tasks.Work(task=None)
    work.cancelled.set()
    token = tasks.current.set(work)
    try:
        with pytest.raises(asyncio.CancelledError):
            dispatch("open_website", {"site": "youtube"}, user_requested_launch=True)
    finally:
        tasks.current.reset(token)
    assert calls == []


def test_keyboard_tool_refuses_unsupported_unicode_and_unbounded_input(monkeypatch):
    monkeypatch.setattr(computer, "WINDOWS", True)
    assert computer.type_text("हिन्दी")["typed"] is False
    assert computer.type_text("a" * 501)["typed"] is False


def test_external_launches_do_not_inherit_session_credentials(monkeypatch):
    monkeypatch.setenv("CORTANA_API_TOKEN", TOKEN)
    monkeypatch.setenv("CORTANA_CLOUD_FALLBACK_API_KEY", "test-cloud-secret")
    monkeypatch.setenv("CORTANA_DESKTOP_PID", "123")
    called = []
    monkeypatch.setattr(processes.subprocess, "run", lambda argv, **kwargs: called.append((argv, kwargs)))
    processes.shell_open("https://example.org/test?literal=%26")
    argv, kwargs = called[0]
    assert argv[-1] == "https://example.org/test?literal=%26"
    assert "-I" in argv
    assert kwargs.get("shell", False) is False
    assert not any(key.upper().startswith("CORTANA_") for key in kwargs["env"])


def test_real_app_lifespan_refuses_missing_auth_token(monkeypatch):
    import main
    monkeypatch.delenv("CORTANA_API_TOKEN", raising=False)
    async def run():
        with pytest.raises(RuntimeError, match="authentication token"):
            async with main.lifespan(main.app):
                pytest.fail("An unauthenticated backend must not start.")
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows process supervision")
@pytest.mark.parametrize("mode", ["desktop", "launcher"])
def test_backend_exits_when_desktop_or_intermediate_launcher_dies(tmp_path, mode):
    """Only toy subprocesses are launched and terminated; no live apps touched."""
    import ctypes
    from ctypes import wintypes
    from core.parent_watchdog import _windows_api

    ready = tmp_path / "watchdog-ready.json"
    base_python = getattr(sys, "_base_executable", sys.executable)
    child_script = (
        "import os,sys,time\n"
        f"sys.path.insert(0, {str(ROOT / 'agent')!r})\n"
        "from core.parent_watchdog import start_parent_watchdog\n"
        "stop=start_parent_watchdog()\n"
        "print(os.getpid(), flush=True)\n"
        "time.sleep(30)\n"
        "stop()\n"
    )
    launcher_script = (
        "import os,subprocess,json,time\n"
        f"env=dict(os.environ, CORTANA_DESKTOP_PID=str(os.getpid() if {mode!r} == 'desktop' else {os.getpid()}))\n"
        f"child=subprocess.Popen([{base_python!r}, '-I', '-u', '-c', {child_script!r}], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)\n"
        "line=child.stdout.readline().strip()\n"
        f"with open({str(ready)!r}, 'w') as f: json.dump({{'pid':child.pid,'ready':line}},f)\n"
        "time.sleep(30)\n"
    )
    launcher = subprocess.Popen(
        [base_python, "-I", "-c", launcher_script],
        env=processes.public_environment(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    child_handle = None
    kernel = _windows_api()
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    try:
        deadline = time.monotonic() + 8
        while not ready.exists() and time.monotonic() < deadline:
            assert launcher.poll() is None, "Toy launcher exited before readiness."
            time.sleep(0.05)
        assert ready.exists(), "Watchdog child failed to report readiness."
        info = json.loads(ready.read_text())
        assert int(info["ready"]) == info["pid"]
        # The process handle is owned before the test kills its parent, so
        # cleanup can never accidentally target a subsequently reused PID.
        child_handle = kernel.OpenProcess(0x00100000 | 0x1, False, info["pid"])
        assert child_handle
        launcher.terminate()
        launcher.wait(timeout=5)
        handle_array = (wintypes.HANDLE * 1)(child_handle)
        assert kernel.WaitForMultipleObjects(1, handle_array, False, 5000) == 0
    finally:
        if launcher.poll() is None:
            launcher.terminate()
            launcher.wait(timeout=5)
        if child_handle:
            kernel.TerminateProcess(child_handle, 1)  # Only this test-owned process, if still alive.
            kernel.CloseHandle(child_handle)
