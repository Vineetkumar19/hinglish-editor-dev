"""Run the complete suite in isolated storage with external networking blocked.

On Windows this needs normal localhost access; an AppContainer sandbox can
block even connections to the fake servers. Never loads the operator's .env.
"""
from __future__ import annotations

import argparse
import io
import ipaddress
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import platform
import datetime
import re

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def local_only(event, args):
    if event not in ("socket.connect", "socket.getaddrinfo"):
        return
    address = args[1] if event == "socket.connect" else args[0]
    host = address[0] if isinstance(address, tuple) else address
    if str(host) == "localhost":
        return
    try:
        if ipaddress.ip_address(str(host)).is_loopback:
            return
    except ValueError:
        pass
    raise OSError("External networking is disabled by the isolated test runner")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="test_*.py")
    args = parser.parse_args(argv)
    temp_root = ROOT / "tmp" / "tests"
    temp_root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temp_root)
    # `run.py test` may already have loaded .env while configuring logging.
    # Strip project settings before tests set their own isolated configuration.
    for env_path in (ROOT / ".env", ROOT / ".env.example"):
        for line in env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []:
            match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
            if match:
                os.environ.pop(match[1], None)
    os.environ.update({"DRY_RUN": "true", "LLM_PROVIDER": "offline",
                       "NOTIFY_CHANNELS": "store", "LOG_LEVEL": "CRITICAL",
                       "VIDEO_GIGS_ENABLED": "false", "DEV_GIGS_ENABLED": "false",
                       "DISCOVER_ENABLED": "false", "SAAS_ENABLED": "false"})
    from core import config
    config._LOADED = True
    sys.addaudithook(local_only)
    suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern=args.pattern)
    print(f"Running {suite.countTestCases()} isolated tests", flush=True)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (temp_root / "results.txt").write_text(log.getvalue(), encoding="utf-8")
    report = {"tests": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "skipped": len(result.skipped),
              "pattern": args.pattern, "python": platform.python_version(),
              "external_networking": "blocked", "production_env_loaded": False,
              "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if args.pattern == "test_*.py":
        (ROOT / "data" / "test-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Ran {result.testsRun}; failures={len(result.failures)}, "
          f"errors={len(result.errors)}, skipped={len(result.skipped)}")
    for test, trace in result.failures + result.errors:
        print(test, "\n", trace[-2400:])
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
