"""Blank-browser lifecycle smoke. No service/account or real recipient is opened."""
import json
import os
from pathlib import Path
import sys
import time
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
import psutil
from core import browser_session

if __name__ == "__main__":
    if sys.argv[1:] == ["--crash-owner"]:
        browser_session._start()
        browser_session.browser_request("status")
        owned = dict(browser_session._owned_processes)
        print(json.dumps(owned), flush=True)
        os._exit(0)  # Deliberate backend crash; bypass atexit to test the watchdog.
    report = {}
    try:
        os.environ["CORTANA_BROWSER_SMOKE_SECRET"] = "synthetic-never-forward"
        browser_session._start()
        status = browser_session.browser_request("status")
        report["status"] = status
        ids = browser_session.managed_browser_process_ids()
        report["owned_process_count"] = len(ids)
        report["active"] = browser_session.managed_browser_active()
        assert report["active"] and ids
        chromium = []
        for pid in ids:
            try:
                process = psutil.Process(pid)
                assert not any(key.startswith("CORTANA_") for key in process.environ())
                if process.name().lower() == "chrome.exe":
                    args = process.cmdline()
                    assert "--no-sandbox" not in args
                    assert not any(arg.startswith("--remote-debugging-port") for arg in args)
                    chromium.append(pid)
            except psutil.NoSuchProcess:
                pass
        assert chromium
        report["environment_sanitized"] = True
        report["chromium_sandbox_enabled"] = True
        report["debugging_tcp_port_absent"] = True
    finally:
        browser_session.close_browser()
    time.sleep(.5)
    report["owned_processes_after_close"] = len(browser_session._owned_processes)
    report["active_after_close"] = browser_session.managed_browser_active()
    assert not browser_session._owned_processes
    assert not report["active_after_close"]
    crashed = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), "--crash-owner"],
        text=True, encoding="utf-8", capture_output=True, timeout=30, check=True,
        env={k: v for k, v in os.environ.items() if not k.startswith("CORTANA_")},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    old = json.loads(crashed.stdout)
    deadline = time.monotonic() + 8
    survivors = {}
    while time.monotonic() < deadline:
        survivors = {}
        for pid, created in old.items():
            try:
                if psutil.Process(int(pid)).create_time() == created:
                    survivors[pid] = created
            except psutil.NoSuchProcess:
                pass
        if not survivors:
            break
        time.sleep(.2)
    report["owned_processes_after_backend_crash"] = len(survivors)
    assert not survivors, "Parent watchdog left owned browser processes running"
    print(json.dumps(report, indent=2))
