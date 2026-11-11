"""Shared test scaffolding: isolated env, fresh database, fake servers."""
from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE_ENV = {
    "DRY_RUN": "true",
    "LLM_PROVIDER": "offline",
    "LLM_CACHE": "false",
    "SEARCH_PROVIDER": "seeds",
    "SEEDS_FILE": str(ROOT / "tests" / "fixtures" / "targets.yaml"),
    "SPONSOR_FILE": str(ROOT / "tests" / "fixtures" / "sponsors.yaml"),
    "CREATOR_PROFILE": str(ROOT / "tests" / "fixtures" / "creator.yaml"),
    # Guessing an address requires a live DNS-over-HTTPS lookup. Tests must not
    # depend on the network, and they must not vary with what a real domain
    # happens to have configured today.
    "CONTACT_GUESS_ENABLED": "false",
    # The sponsorship agent decides for itself whether a web sweep is due, and
    # with no history it decides yes. Tests must never reach the internet, so
    # the sweep is off unless a test asks for it with discover=True.
    "DISCOVER_ENABLED": "false",
    "VIDEO_GIGS_ENABLED": "false",
    "DEV_GIGS_ENABLED": "false",
    "SAAS_ENABLED": "false",
    "RESUME_MASTER_FILE": str(ROOT / "profiles" / "master_resume.yaml"),
    "PRICING_FILE": str(ROOT / "profiles" / "dev_rate_card.yaml"),
    "VIDEO_RATES_FILE": str(ROOT / "profiles" / "video_rates.yaml"),
    "JOB_FIXTURE_FILE": str(ROOT / "tests" / "fixtures" / "jobs.json"),
    "JOB_SOURCES": "fixture",
    "JOB_MAX_AGE_DAYS": "3650",
    "SENDER_EMAIL": "vineet@example.com",
    "SENDER_NAME": "Vineet Das",
    "SENDER_POSTAL_ADDRESS": "Badlapur, Maharashtra, India",
    "OPERATOR_NAME": "Vineet",
    "OPERATOR_EMAIL": "vineet@example.com",
    "YOUTUBE_CHANNEL_URL": "https://youtube.com/@vineetcricket",
    "PORTFOLIO_URL": "https://drive.example/folder",
    "NOTIFY_CHANNELS": "store",
    "CRAWL_MIN_INTERVAL": "0",
    "RESPECT_ROBOTS": "true",
    "DAILY_SEND_CAP": "40",
    "UNSUBSCRIBE_SECRET": "test-secret",
    "TIMEZONE": "Asia/Kolkata",
    "LOG_LEVEL": "CRITICAL",
    "PUBLIC_BASE_URL": "http://localhost:8080",
    "DRY_RUN_PRINT": "false",
}


class SuiteCase(unittest.TestCase):
    """Base case: a private temp directory, clean env, fresh singletons."""

    extra_env: dict = {}

    def setUp(self):
        self._saved_env = dict(os.environ)
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="agentsuite-test-"))
        env = dict(BASE_ENV)
        env["DATA_DIR"] = str(self.tmp / "data")
        env["DB_URL"] = f"sqlite:///{self.tmp / 'test.db'}"
        env["RESUME_OUTPUT_DIR"] = str(self.tmp / "resumes")
        env.update(self.extra_env)
        os.environ.update(env)

        import core.config as cfg
        cfg._LOADED = True                      # do not read the real .env

        # core.log.configure() runs once, at first import - which happens
        # before this env is applied - so LOG_LEVEL above would otherwise be
        # ignored and the suite would print application logs as it runs.
        import logging
        logging.getLogger().setLevel(
            getattr(logging, env["LOG_LEVEL"], logging.CRITICAL))

        self._reset_singletons()

        from core.store import Store
        self.store = Store(env["DB_URL"])
        import core.store as store_mod
        store_mod._default = self.store

        from core.hitl import ApprovalQueue
        self.queue = ApprovalQueue(self.store)

    def tearDown(self):
        self._reset_singletons()
        try:
            self.store.close()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.clear()
        os.environ.update(self._saved_env)

    @staticmethod
    def _reset_singletons():
        import core.llm as llm_mod
        import core.notify as notify_mod
        import core.store as store_mod
        store_mod._default = None
        llm_mod._default = None
        notify_mod._default = None
        try:
            import server.bot as bot_mod
            bot_mod._BOT = None
        except ImportError:
            pass

    # -- helpers -------------------------------------------------------------
    def env(self, **overrides):
        """Temporarily set environment variables inside a `with` block."""
        import contextlib
        import os as _os

        @contextlib.contextmanager
        def _ctx():
            saved = {k: _os.environ.get(k) for k in overrides}
            _os.environ.update({k: str(v) for k, v in overrides.items()})
            self._reset_singletons()
            import core.store as store_mod
            store_mod._default = self.store
            try:
                yield
            finally:
                for k, v in saved.items():
                    if v is None:
                        _os.environ.pop(k, None)
                    else:
                        _os.environ[k] = v
                self._reset_singletons()
                store_mod._default = self.store
        return _ctx()

    def offline_llm(self):
        from core.llm import LLM
        return LLM("offline", store=self.store)

    def fast_crawler(self, llm=None):
        from core.crawler import Crawler
        from core.ratelimit import HostLimiter
        return Crawler(limiter=HostLimiter(min_interval=0), llm=llm)

    def drive(self, app, thread_id: str, decide, initial: dict | None = None,
              max_gates: int = 25):
        """Run a graph to completion, calling `decide(payload)` at each gate.

        `decide` returns "approve", "reject", or a dict of edits.
        """
        state = dict(initial or {})
        state.setdefault("_thread_id", thread_id)
        result = app.invoke(state, thread_id=thread_id)
        gates = 0
        while result.interrupted and gates < max_gates:
            gates += 1
            row = self.queue.get(result.approval_id)
            choice = decide(row)
            if choice == "reject":
                d = self.queue.reject(result.approval_id, note="test rejection")
            elif isinstance(choice, dict):
                d = self.queue.approve(result.approval_id, edits=choice)
            else:
                d = self.queue.approve(result.approval_id)
            result = app.resume(thread_id, d.to_json())
        self.assertLess(gates, max_gates, "graph did not settle")
        return result
