"""Unit tests for the core framework."""
from __future__ import annotations

import json
import pathlib
import time
import unittest

from tests.base import SuiteCase


class TestSchema(SuiteCase):
    def test_validation_and_coercion(self):
        from core.schema import ValidationError, validate
        s = {"type": "object", "required": ["name"],
             "properties": {"name": {"type": "string", "min_length": 2},
                            "n": {"type": "integer", "minimum": 0, "default": 1},
                            "k": {"type": "string", "enum": ["a", "b"]}}}
        self.assertEqual(validate({"name": "Ok", "n": "5"}, s),
                         {"name": "Ok", "n": 5})
        with self.assertRaises(ValidationError):
            validate({"name": "x", "k": "z"}, s)

    def test_bool_is_not_a_number(self):
        from core.schema import ValidationError, validate
        with self.assertRaises(ValidationError):
            validate(True, {"type": "integer"})


class TestYaml(SuiteCase):
    def test_round_trip(self):
        from core.yamlite import dump_yaml, load_yaml
        for src in ("a: 1\nb: [1, 2]\n",
                    "t:\n  - name: A\n    tags: [x, y]\n  - name: B\n",
                    "block: |\n  one\n  two\n",
                    "q: \"has: colon\"\n"):
            data = load_yaml(src)
            self.assertEqual(load_yaml(dump_yaml(data)), data, src)

    def test_rejects_anchors(self):
        from core.yamlite import YamlError, load_yaml
        with self.assertRaises(YamlError):
            load_yaml("a: &x 1")

    def test_url_value_is_not_split_as_key(self):
        from core.yamlite import load_yaml
        self.assertEqual(load_yaml("u: https://a.example/x?y=1")["u"],
                         "https://a.example/x?y=1")


class TestStore(SuiteCase):
    def test_kv_and_dedupe(self):
        self.store.kv_set("ns", "k", {"v": 1})
        self.assertEqual(self.store.kv_get("ns", "k"), {"v": 1})
        self.assertTrue(self.store.mark_seen("emails", "A@B.com"))
        self.assertFalse(self.store.mark_seen("emails", "a@b.com"))
        self.assertTrue(self.store.seen("emails", "A@b.COM"))

    def test_event_payload_can_use_reserved_names(self):
        self.store.event("test", "agent", "tid", kind="x", agent="y")
        self.assertEqual(self.store.recent_events(1)[0]["payload"],
                         {"kind": "x", "agent": "y"})

    def test_creates_missing_parent_directory(self):
        """A fresh checkout has no data/ folder; sqlite will not make one.

        Regression: `run.py demo` sets DB_URL directly, bypassing the helper
        that used to be the only thing creating data/, and died with the
        opaque "unable to open database file".
        """
        import sqlite3
        from core.store import Store
        target = pathlib.Path(self.tmp) / "absent" / "deeper" / "x.db"
        self.assertFalse(target.parent.exists())
        st = Store(url=f"sqlite:///{target}")
        try:
            st.kv_set("ns", "k", {"v": 1})
            self.assertEqual(st.kv_get("ns", "k"), {"v": 1})
            self.assertTrue(target.exists())
        finally:
            st.close()
        with self.assertRaises(sqlite3.OperationalError) as cm:
            Store(url=f"sqlite:///{target / 'not-a-dir' / 'y.db'}")
        self.assertIn("cannot create the folder", str(cm.exception))


class TestGraph(SuiteCase):
    def _graph(self):
        from core.graph import END, StateGraph, append, interrupt
        g = StateGraph(reducers={"log": append})
        g.add_node("a", lambda s: {"log": "a", "n": s.get("n", 0) + 1})

        def b(s):
            ok = interrupt({"q": "?"})
            return {"log": f"b:{ok}", "ok": ok}
        g.add_node("b", b)
        g.add_node("c", lambda s: {"log": "c"})
        g.set_entry_point("a")
        g.add_edge("a", "b")
        g.add_conditional_edges("b", lambda s: "y" if s.get("ok") else "n",
                                {"y": "c", "n": "a"})
        g.add_edge("c", END)
        return g.compile(store=self.store, name="t")

    def test_interrupt_resume_and_cycle(self):
        app = self._graph()
        r = app.invoke({"n": 0}, thread_id="T")
        self.assertTrue(r.interrupted)
        r = app.resume("T", False)
        self.assertTrue(r.interrupted)
        r = app.resume("T", True)
        self.assertTrue(r.complete)
        self.assertEqual(r.state["log"], ["a", "b:False", "a", "b:True", "c"])

    def test_no_stale_resume_replay(self):
        app = self._graph()
        app.invoke({"n": 0}, thread_id="S")
        app.resume("S", False)
        r = app.resume("S", True)
        self.assertEqual(r.state["n"], 2, "resume values must not be replayed")

    def test_recursion_limit_is_a_circuit_breaker(self):
        from core.graph import END, GraphRecursionError, StateGraph
        g = StateGraph()
        g.add_node("loop", lambda s: {"i": s.get("i", 0) + 1})
        g.set_entry_point("loop")
        g.add_edge("loop", "loop")
        app = g.compile(store=self.store, name="loopy", recursion_limit=5)
        with self.assertRaises(GraphRecursionError):
            app.invoke({}, thread_id="L")

    def test_unserialisable_state_is_rejected_with_a_useful_message(self):
        from core.graph import END, StateGraph
        g = StateGraph()
        g.add_node("n", lambda s: {"sock": object()})
        g.set_entry_point("n")
        g.add_edge("n", END)
        app = g.compile(store=self.store, name="bad")
        with self.assertRaises(TypeError) as ctx:
            app.invoke({}, thread_id="B")
        self.assertIn("__sock", str(ctx.exception))

    def test_transient_keys_are_not_persisted(self):
        from core.graph import END, StateGraph
        g = StateGraph()
        g.add_node("n", lambda s: {"__live": object(), "keep": 1})
        g.set_entry_point("n")
        g.add_edge("n", END)
        app = g.compile(store=self.store, name="transient")
        r = app.invoke({}, thread_id="TR")
        self.assertTrue(r.complete)
        saved = app.latest_checkpoint("TR")["state"]
        self.assertIn("keep", saved)
        self.assertNotIn("__live", saved)

    def test_node_failure_is_recorded_not_raised(self):
        from core.graph import END, StateGraph
        g = StateGraph()

        def boom(s):
            raise RuntimeError("kaboom")
        g.add_node("n", boom)
        g.set_entry_point("n")
        g.add_edge("n", END)
        app = g.compile(store=self.store, name="boom")
        r = app.invoke({}, thread_id="E")
        self.assertEqual(r.status, "error")
        self.assertIn("kaboom", r.error)

    def test_retry_then_succeed(self):
        from core.graph import END, StateGraph
        calls = {"n": 0}

        def flaky(s):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return {"done": True}
        g = StateGraph()
        g.add_node("n", flaky, retries=3, backoff=0.001)
        g.set_entry_point("n")
        g.add_edge("n", END)
        r = g.compile(store=self.store, name="retry").invoke({}, thread_id="R")
        self.assertTrue(r.complete)
        self.assertEqual(calls["n"], 3)

    def test_crashed_run_resumes_from_last_checkpoint(self):
        from core.graph import END, StateGraph, append
        hits = {"a": 0, "b": 0}

        def a(s):
            hits["a"] += 1
            return {"step": "a"}

        def b(s):
            hits["b"] += 1
            if hits["b"] == 1:
                raise RuntimeError("crash")
            return {"step": "b"}
        g = StateGraph()
        g.add_node("a", a)
        g.add_node("b", b)
        g.set_entry_point("a")
        g.add_edge("a", "b")
        g.add_edge("b", END)
        app = g.compile(store=self.store, name="crash")
        first = app.invoke({}, thread_id="C")
        self.assertEqual(first.status, "error")
        second = app.invoke(thread_id="C")
        self.assertTrue(second.complete)
        self.assertEqual(hits["a"], 1, "completed node must not re-run")

    def test_graph_validation_catches_dead_ends(self):
        from core.graph import StateGraph
        g = StateGraph()
        g.add_node("a", lambda s: None)
        g.set_entry_point("a")
        with self.assertRaises(ValueError):
            g.compile(store=self.store)


class TestHitl(SuiteCase):
    def _app(self):
        from core.graph import END, StateGraph
        from core.hitl import require_approval

        def gate(s):
            d = require_approval(agent="t", thread_id=s["_thread_id"],
                                 kind="send_email", title="Send it",
                                 payload={"subject": "S", "body": "B"},
                                 store=self.store)
            return {"approved": d.approved, "final": d.apply_to({"subject": "S"}),
                    "note": d.note}
        g = StateGraph()
        g.add_node("gate", gate)
        g.set_entry_point("gate")
        g.add_edge("gate", END)
        return g.compile(store=self.store, name="t")

    def test_approve_with_edits(self):
        app = self._app()
        r = app.invoke({"_thread_id": "H"}, thread_id="H")
        d = self.queue.approve(r.approval_id, edits={"subject": "Edited"})
        r2 = app.resume("H", d.to_json())
        self.assertEqual(r2.state["final"]["subject"], "Edited")
        self.assertEqual(len(self.queue.pending()), 0, "no orphan approval rows")

    def test_reject_blocks(self):
        app = self._app()
        r = app.invoke({"_thread_id": "H2"}, thread_id="H2")
        d = self.queue.reject(r.approval_id, note="no")
        r2 = app.resume("H2", d.to_json())
        self.assertFalse(r2.state["approved"])

    def test_cannot_decide_twice(self):
        app = self._app()
        r = app.invoke({"_thread_id": "H3"}, thread_id="H3")
        self.queue.approve(r.approval_id)
        with self.assertRaises(RuntimeError):
            self.queue.reject(r.approval_id)


class TestPdf(SuiteCase):
    def test_text_is_extractable_and_paginates(self):
        from core.pdf import PDF
        d = PDF()
        d.title("Vineet Das", "Senior Software Engineer")
        d.heading("Experience")
        for i in range(120):
            d.bullet(f"Bullet number {i} with enough words to occupy a line.")
        path = d.save(self.tmp / "out.pdf")
        raw = open(path, "rb").read()
        self.assertTrue(raw.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", raw[-16:])
        self.assertGreater(len(d.pages), 1, "should paginate")
        try:
            import pypdf
        except ImportError:
            self.skipTest("pypdf not installed")
        reader = pypdf.PdfReader(path)
        text = "\n".join(p.extract_text() for p in reader.pages)
        self.assertIn("Vineet Das", text)
        self.assertIn("Bullet number 119", text)

    def test_width_measurement(self):
        from core.pdf import text_width, wrap_text
        self.assertGreater(text_width("MMMM", "Helvetica", 10),
                           text_width("iiii", "Helvetica", 10))
        lines = wrap_text("word " * 50, "Helvetica", 10, 100)
        self.assertGreater(len(lines), 1)


class TestRateLimit(SuiteCase):
    def test_token_bucket(self):
        from core.ratelimit import TokenBucket
        b = TokenBucket(rate=100, capacity=2)
        self.assertTrue(b.try_acquire())
        self.assertTrue(b.try_acquire())
        self.assertFalse(b.try_acquire())

    def test_robots_precedence(self):
        from core.ratelimit import _Robots
        r = _Robots.parse("User-agent: *\nDisallow: /private\nAllow: /private/ok\n",
                          "AgentSuite")
        self.assertTrue(r.allowed("/x"))
        self.assertFalse(r.allowed("/private/secret"))
        self.assertTrue(r.allowed("/private/ok"))

    def test_daily_cap(self):
        from core.ratelimit import DailyCap
        cap = DailyCap(self.store)
        self.assertTrue(all(cap.check_and_increment("m", 3) for _ in range(3)))
        self.assertFalse(cap.check_and_increment("m", 3))


class TestLlmLayer(SuiteCase):
    def test_json_extraction(self):
        from core.llm import extract_json
        self.assertEqual(extract_json('```json\n{"a":1}\n```'), {"a": 1})
        self.assertEqual(extract_json('Sure: {"a":{"b":[1,2]}} done'),
                         {"a": {"b": [1, 2]}})
        self.assertEqual(extract_json('text {"s":"a } b"} end'), {"s": "a } b"})

    def test_structured_validates_offline(self):
        llm = self.offline_llm()
        out = llm.classify("Yes we are interested", ["interested", "no"])
        self.assertIn(out["label"], ["interested", "no"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDotenvLoading(SuiteCase):
    def test_the_last_line_wins_when_a_key_is_repeated(self):
        """People add a setting by pasting it at the bottom of .env."""
        import os
        from core.config import load_dotenv
        env = self.tmp / "dup.env"
        env.write_text("JOB_SOURCES=remotive\n# later edit\nJOB_SOURCES=greenhouse\n",
                       encoding="utf-8")
        os.environ.pop("JOB_SOURCES", None)
        try:
            parsed = load_dotenv(env, override=True)
            self.assertEqual(parsed["JOB_SOURCES"], "greenhouse")
            self.assertEqual(os.environ["JOB_SOURCES"], "greenhouse")
        finally:
            os.environ.pop("JOB_SOURCES", None)

    def test_the_real_environment_still_beats_the_file(self):
        import os
        from core.config import load_dotenv
        env = self.tmp / "beat.env"
        env.write_text("SOME_SETTING=from_file\nSOME_SETTING=from_file_again\n",
                       encoding="utf-8")
        os.environ["SOME_SETTING"] = "from_shell"
        try:
            load_dotenv(env)
            self.assertEqual(os.environ["SOME_SETTING"], "from_shell")
        finally:
            os.environ.pop("SOME_SETTING", None)

    def test_a_commented_line_is_still_ignored(self):
        import os
        from core.config import load_dotenv
        env = self.tmp / "c.env"
        env.write_text("# JOB_SOURCES=commented\nJOB_SOURCES=real\n", encoding="utf-8")
        os.environ.pop("JOB_SOURCES", None)
        try:
            self.assertEqual(load_dotenv(env, override=True)["JOB_SOURCES"], "real")
        finally:
            os.environ.pop("JOB_SOURCES", None)


class TestImapInbox(SuiteCase):
    """Replies read over IMAP, using the same app password that sends."""

    def test_it_knows_the_host_for_common_providers(self):
        from core.imapbox import default_host
        self.assertEqual("imap.gmail.com", default_host("me@gmail.com"))
        self.assertEqual("outlook.office365.com", default_host("me@outlook.com"))
        self.assertEqual("imap.mydomain.in", default_host("me@mydomain.in"))
        self.assertEqual("", default_host(""))

    def test_a_reply_is_parsed_into_the_shape_the_agents_expect(self):
        from core.imapbox import ImapBox
        raw = (b"From: Priya Rao <priya@brand.in>\r\n"
               b"To: you@example.com\r\n"
               b"Subject: Re: Cricket content partnership\r\n"
               b"Message-ID: <reply-1@brand.in>\r\n"
               b"In-Reply-To: <original-1@example.com>\r\n"
               b"Date: Wed, 17 Sep 2026 10:00:00 +0530\r\n\r\n"
               b"Yes, interested. What are your rates?\r\n"
               b"\r\nOn Tue, you wrote:\r\n> my original pitch\r\n")
        m = ImapBox._to_message(raw)
        self.assertEqual("priya@brand.in", m.from_addr)
        self.assertEqual("Priya Rao", m.from_name)
        self.assertEqual("<original-1@example.com>", m.thread_id,
                         "a reply belongs to the thread it answers")
        self.assertIn("What are your rates", m.reply_text)
        self.assertNotIn("my original pitch", m.reply_text,
                         "the quoted original should be stripped")

    def test_an_out_of_office_is_recognised(self):
        from core.imapbox import ImapBox
        raw = (b"From: a@b.com\r\nTo: you@example.com\r\n"
               b"Subject: Automatic reply: out of office\r\n"
               b"Message-ID: <ooo@b.com>\r\n\r\nBack Monday.\r\n")
        self.assertTrue(ImapBox._to_message(raw).is_auto_reply)

    def test_an_html_only_reply_still_yields_text(self):
        from core.imapbox import ImapBox
        raw = (b"From: a@b.com\r\nTo: you@example.com\r\n"
               b"Subject: Re: hello\r\nMessage-ID: <h@b.com>\r\n"
               b"Content-Type: text/html; charset=utf-8\r\n\r\n"
               b"<html><body><p>We can do <b>25,000</b> for one video.</p>"
               b"</body></html>\r\n")
        m = ImapBox._to_message(raw)
        self.assertIn("25,000", m.reply_text)
        self.assertNotIn("<b>", m.reply_text)

    def test_nothing_is_polled_when_it_is_not_configured(self):
        from core.imapbox import ImapBox
        box = ImapBox(self.store)
        box.address, box.password = "", ""
        self.assertFalse(box.configured)
        self.assertEqual([], box.poll(),
                         "an unconfigured inbox must be quiet, not an error")
        self.assertEqual("not configured", box.check())


class TestLocalModel(SuiteCase):
    """A model running on this machine, and what happens when it is not.

    The provider is exercised against a stub server rather than a real one:
    what these tests protect is the three settings that decide whether a small
    local model can do this job at all, and the promise that a switched-off
    model never ends a run.
    """

    def _stub(self, reply: dict | str, status: int = 200):
        """A one-request Ollama stand-in. Returns (base_url, seen_bodies)."""
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        seen: list[dict] = []
        payload = reply

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = json.dumps({"models": [{"name": "qwen2.5:7b"}]}).encode()
                self.send_response(200)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get("content-length", 0))
                seen.append(json.loads(self.rfile.read(n) or b"{}"))
                if status != 200:
                    self.send_error(status)
                    return
                content = payload if isinstance(payload, str) else json.dumps(payload)
                raw = json.dumps({"message": {"content": content}}).encode()
                self.send_response(200)
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}", seen

    def test_the_context_window_is_big_enough_for_a_brands_own_words(self):
        # Ollama defaults to 2048 tokens, which silently truncates the site text
        # the whole approach depends on.
        from core.llm import OllamaProvider
        base, seen = self._stub({"ok": True})
        with self.env(LLM_PROVIDER="ollama", OLLAMA_BASE_URL=base):
            OllamaProvider().complete("sys", [self._msg("hello")],
                                      max_tokens=200, temperature=0.2)
        self.assertGreaterEqual(seen[0]["options"]["num_ctx"], 8192)
        self.assertTrue(seen[0].get("keep_alive"))

    def test_the_schema_is_sent_as_a_grammar_not_just_described(self):
        from core.llm import LLM
        base, seen = self._stub({"label": "yes", "confidence": 0.9})
        schema = {"type": "object", "required": ["label"],
                  "properties": {"label": {"type": "string", "min_length": 2},
                                 "confidence": {"type": "number", "default": 0.5}}}
        with self.env(LLM_PROVIDER="ollama", OLLAMA_BASE_URL=base):
            out = LLM().structured("decide", schema)
        self.assertEqual("yes", out["label"])
        fmt = seen[0].get("format")
        self.assertEqual("object", fmt["type"])
        self.assertIn("label", fmt["properties"])
        # Bounds are dropped on the way out - grammar compilers handle them
        # inconsistently - but validate() still applies them on the way back.
        self.assertNotIn("min_length", fmt["properties"]["label"])

    def test_a_switched_off_model_falls_back_instead_of_ending_the_run(self):
        from core.llm import LLM, offline_handler
        schema = {"type": "object", "required": ["subject", "body"],
                  "properties": {"subject": {"type": "string"},
                                 "body": {"type": "string"}}}

        @offline_handler("test:fallback")
        def _written(ctx):
            return {"subject": "written", "body": "from the template"}

        with self.env(LLM_PROVIDER="ollama",
                      OLLAMA_BASE_URL="http://127.0.0.1:1"):
            out = LLM().structured("x", schema, task="test:fallback")
        self.assertEqual("written", out["subject"])
        self.assertIn("cannot reach Ollama", out["_fallback"])

    def test_a_local_openai_server_does_not_demand_an_api_key(self):
        # LM Studio and llama.cpp ignore the key; requiring one stops a working
        # local setup from starting at all.
        from core.llm import OpenAIProvider
        with self.env(LLM_PROVIDER="openai", OPENAI_API_KEY="",
                      OPENAI_BASE_URL="http://localhost:1234/v1"):
            self.assertTrue(OpenAIProvider().local)

    @staticmethod
    def _msg(text):
        from core.llm import Message
        return Message("user", text)


class TestDotenvValues(SuiteCase):
    """A value with spaces in it must survive the .env parser.

    It did not: every unquoted value was cut at its first token, so
    SENDER_NAME=Vineet Kumar Das arrived as "Vineet" and the postal address in
    the footer of every email was one word long.
    """

    def _parse(self, text: str) -> dict:
        import core.config as cfg
        path = self.tmp / "sample.env"
        path.write_text(text, encoding="utf-8")
        return cfg.load_dotenv(path, override=True)

    def test_spaces_are_kept(self):
        got = self._parse("SENDER_NAME=Vineet Kumar Das\n"
                          "SENDER_POSTAL_ADDRESS=Badlapur, Maharashtra, India\n")
        self.assertEqual("Vineet Kumar Das", got["SENDER_NAME"])
        self.assertEqual("Badlapur, Maharashtra, India",
                         got["SENDER_POSTAL_ADDRESS"])

    def test_an_inline_comment_is_still_removed(self):
        got = self._parse("MAIL_TRANSPORT=smtp     # smtp | gmail\n"
                          "SENDER_NAME=Vineet Kumar Das   # as brands see it\n")
        self.assertEqual("smtp", got["MAIL_TRANSPORT"])
        self.assertEqual("Vineet Kumar Das", got["SENDER_NAME"])

    def test_a_hash_inside_a_quoted_value_is_not_a_comment(self):
        got = self._parse('DASHBOARD_TOKEN="a#b c#d"\n')
        self.assertEqual("a#b c#d", got["DASHBOARD_TOKEN"])


class TestLessons(SuiteCase):
    """The agents change what they write, not only who they write to.

    The brains rank targets. Ranking alone cannot stop an agent repeating a
    sentence he rejected, because nothing about a rejection ever reached the
    prompt. These cover the half that does.
    """

    def lessons(self, agent="sponsorship"):
        from core.lessons import get_lessons
        return get_lessons(agent, self.store)

    def test_a_rule_reaches_the_next_prompt(self):
        lx = self.lessons()
        lx.add("Keep every first email under 90 words.", evidence="he said too long")
        block = lx.prompt_block()
        self.assertIn("under 90 words", block)
        self.assertIn("rejected again", block)

    def test_no_rules_means_no_block_at_all(self):
        # An empty "what you have learned" heading is noise in the prompt and a
        # small model will try to fill it.
        self.assertEqual("", self.lessons().prompt_block())

    def test_saying_the_same_thing_twice_strengthens_one_rule(self):
        lx = self.lessons()
        lx.add("Never claim award-winning work he has not done.")
        lx.add("Do not mention award winning work that he has never done.")
        rules = lx.all()
        self.assertEqual(1, len(rules), "near-duplicates crowd out everything else")
        self.assertGreater(float(rules[0]["weight"]), 1.0)

    def test_each_agent_learns_only_its_own_rules(self):
        self.lessons("sponsorship").add("Never quote a price in a first email.")
        self.assertEqual([], self.lessons("job_hunter").all())
        self.assertEqual("", self.lessons("video_client").prompt_block())

    def test_a_rule_he_rejects_can_be_removed(self):
        lx = self.lessons()
        lid = lx.add("Always open with a compliment.")
        lx.forget(lid)
        self.assertEqual([], lx.all())

    def test_the_prompt_budget_is_capped(self):
        lx = self.lessons()
        for i in range(40):
            lx.add(f"Rule number {i} about a completely separate subject {i}.")
        shown = lx.prompt_block().count("\n- ")
        self.assertLessEqual(shown, 10,
                             "past a dozen rules a local model ignores the list")

    def test_following_a_rule_is_counted(self):
        lx = self.lessons()
        lx.add("Keep it under 90 words.")
        lx.prompt_block()
        self.assertEqual(1, int(lx.all()[0]["uses"]))


class TestReflection(SuiteCase):
    """Turning what he said into something the agent obeys."""

    def test_a_rejection_note_becomes_a_rule_without_a_model(self):
        # Offline there is no model to generalise the complaint, so his words
        # become the rule verbatim. Blunter, still works.
        from core.hitl import Decision
        from core.lessons import get_lessons
        from core.reflect import learn_from_decision
        d = Decision("rejected", {}, note="Too long and too salesy.")
        learn_from_decision("sponsorship", d, {"body": "a long draft"},
                            store=self.store)
        rules = get_lessons("sponsorship", self.store).all()
        self.assertEqual(1, len(rules))
        self.assertIn("Too long", rules[0]["rule"])

    def test_an_approval_with_nothing_said_teaches_nothing(self):
        # Inventing a rule from a silent approval is how an agent acquires
        # superstitions.
        from core.hitl import Decision
        from core.lessons import get_lessons
        from core.reflect import learn_from_decision
        learn_from_decision("sponsorship", Decision("approved", {}, note=""),
                            {"body": "a draft"}, store=self.store)
        self.assertEqual([], get_lessons("sponsorship", self.store).all())

    def test_an_edit_is_learned_from_even_with_no_note(self):
        from core.hitl import Decision
        from core.lessons import get_lessons
        from core.reflect import learn_from_decision
        d = Decision("edited", {"body": "Short version."}, note="")
        learn_from_decision("video_client", d,
                            {"body": "A very long original version indeed."},
                            store=self.store)
        # Offline with no note there is nothing quotable, so nothing is stored
        # rather than something invented.
        self.assertEqual([], get_lessons("video_client", self.store).all())

    def test_the_diff_shows_what_he_changed(self):
        from core.reflect import _diff
        out = _diff("I guarantee results.\nSecond line.",
                    "I do not guarantee anything.\nSecond line.")
        self.assertIn("-I guarantee results.", out)
        self.assertIn("+I do not guarantee anything.", out)
        self.assertNotIn("Second line", out.replace(" Second line.", ""))


class TestToolBinding(SuiteCase):
    """Hands for the model, and the line they must not cross.

    Until this existed the model had a brain and no hands: Python decided what
    to look up, put it in the prompt, and the model wrote text back. It could
    not say "I do not know enough about this brand, let me go and read their
    pricing page".
    """

    def setUp(self):
        super().setUp()
        import core.toolbelt  # noqa: F401  (registers the tools)

    def test_the_toolbelt_is_registered(self):
        from core.tools import all_tools
        for name in ("my_numbers", "read_page", "rate_card", "what_i_learned"):
            self.assertIn(name, all_tools())

    def test_a_tool_that_can_act_is_never_bindable(self):
        # The failure mode of forgetting the flag must be a tool that does not
        # work, not a tool that does damage.
        from core.tools import Tool, bind, register
        register(Tool(name="pretend_send", description="sends mail",
                      parameters={"type": "object", "properties": {}},
                      run=lambda **k: "SENT", safe=False))
        self.assertEqual([], [t.name for t in bind(["pretend_send"])])

    def test_executing_an_unsafe_tool_refuses_rather_than_running_it(self):
        from core.tools import Tool, execute, register
        fired = []
        register(Tool(name="pretend_spend", description="spends money",
                      parameters={"type": "object", "properties": {}},
                      run=lambda **k: fired.append(1), safe=False))
        out = execute("pretend_spend", {})
        self.assertIn("not available", out)
        self.assertEqual([], fired, "an unsafe tool must never actually run")

    def test_every_bound_tool_in_every_belt_is_read_only(self):
        from core.tools import all_tools
        from core.toolbelt import BELTS
        known = all_tools()
        for agent, names in BELTS.items():
            for name in names:
                self.assertIn(name, known, f"{agent} binds unknown {name}")
                self.assertTrue(known[name].safe,
                                f"{agent} binds {name}, which can act")

    def test_a_tool_that_raises_hands_back_an_error_not_an_exception(self):
        # A model that gets an error can try something else. An exception ends
        # the whole draft.
        from core.tools import Tool, execute, register
        register(Tool(name="always_breaks", description="breaks",
                      parameters={"type": "object", "properties": {}},
                      run=lambda **k: 1 / 0, safe=True))
        self.assertIn("failed", execute("always_breaks", {}))

    def test_wrong_arguments_are_explained_back_to_the_model(self):
        from core.tools import execute
        out = execute("read_page", {"nonsense": 1})
        self.assertIn("Wrong arguments", out)
        self.assertIn("url", out, "it should say what the tool actually takes")

    def test_an_unknown_tool_lists_the_real_ones(self):
        from core.tools import execute
        self.assertIn("my_numbers", execute("teleport", {}))

    def test_the_call_log_records_what_it_did(self):
        from core.tools import CallLog, execute
        log = CallLog()
        execute("what_i_learned", {"agent": "sponsorship"}, log_to=log)
        self.assertEqual(1, len(log.calls))
        self.assertIn("what_i_learned", log.summary())

    def test_offline_falls_back_to_a_plain_call(self):
        from core.llm import LLM
        answer, log = LLM("offline", store=self.store).with_tools(
            "say something", ["my_numbers"])
        self.assertEqual([], log.calls)
        self.assertIsInstance(answer, str)

    def test_a_message_without_tools_looks_exactly_as_it_did_before(self):
        # Providers that know nothing about tools must see the old wire shape.
        from core.llm import Message
        self.assertEqual({"role": "user", "content": "hi"},
                         Message("user", "hi").to_api())
        with_call = Message("assistant", "", tool_calls=[{"x": 1}]).to_api()
        self.assertIn("tool_calls", with_call)


class TestParkedLaunchAgent(SuiteCase):
    """Built, tested, and not running until he says the product is ready."""

    def test_it_refuses_to_run_while_parked(self):
        from agents.saas_sales.agent import make
        agent = make(store=self.store)
        out = agent.n_check_product({"_thread_id": "t"})
        self.assertFalse(out["ready"])
        self.assertIn("parked", out["blocked_reason"])

    def test_the_switch_turns_it_back_on(self):
        from agents.saas_sales.agent import make
        with self.env(SAAS_ENABLED="true"):
            out = make(store=self.store).n_check_product({"_thread_id": "t"})
            # Now it is gated on the profile being filled in, not on the switch.
            self.assertNotIn("parked", out["blocked_reason"])
