"""Dashboard and webhook tests, driven over real HTTP."""
from __future__ import annotations

import base64
import json
import threading
import time
import unittest
import urllib.parse

from tests.base import SuiteCase
from tests.fakes.servers import FakeWebServer, _free_port


class ServerCase(SuiteCase):
    extra_env = {"DASHBOARD_TOKEN": "s3cret"}

    def setUp(self):
        super().setUp()
        import core.store as store_mod
        store_mod._default = self.store
        from server.app import DashboardServer
        self.port = _free_port()
        self.srv = DashboardServer(("127.0.0.1", self.port), store=self.store)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        for _ in range(100):
            try:
                import socket
                with socket.create_connection(("127.0.0.1", self.port), 0.2):
                    break
            except OSError:
                time.sleep(0.02)
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def get(self, path, **kw):
        from core import http
        return http.get(self.base + path, retries=0, **kw)

    def post(self, path, data, **kw):
        from core import http
        return http.post_form(self.base + path, data, retries=0, **kw)


class TestDashboard(ServerCase):
    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()
        import agents.sponsorship.agent as sponsor
        llm = self.offline_llm()
        self.agent = sponsor.make(store=self.store, llm=llm,
                                  crawler=self.fast_crawler(llm=llm))
        # Walk on until an approval that would actually send an email comes
        # up. The list is ordered by which deal pays soonest, so the first
        # card is often a WhatsApp handoff, which by design writes no message
        # row for the dashboard tests below to look at.
        app = self.agent.build()
        self.run_result = app.invoke({"_thread_id": "srv"}, thread_id="srv")
        guard = 0
        while (self.run_result.interrupted and guard < 8):
            row = self.queue.get(self.run_result.approval_id)
            if (row.get("payload") or {}).get("channel", "email") == "email":
                break
            guard += 1
            decision = self.queue.reject(self.run_result.approval_id,
                                         note="not an email route")
            self.run_result = app.resume("srv", decision.to_json())

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def test_health_needs_no_token(self):
        self.assertTrue(self.get("/health").json()["ok"])

    def test_token_is_enforced(self):
        self.assertEqual(self.get("/").status, 401)
        self.assertEqual(self.get("/?token=s3cret").status, 200)
        self.assertEqual(self.get("/", headers={"Authorization": "Bearer s3cret"}
                                  ).status, 200)

    def test_pending_item_is_listed_and_openable(self):
        body = self.get("/?token=s3cret").text
        self.assertIn("Waiting for you (1)", body)
        detail = self.get(f"/approvals/{self.run_result.approval_id}?token=s3cret")
        self.assertEqual(detail.status, 200)
        self.assertIn("name=body", detail.text)

    def test_approving_through_the_form_resumes_the_graph(self):
        resp = self.post(
            f"/approvals/{self.run_result.approval_id}/decide?token=s3cret",
            {"action": "approve", "subject": "Edited in the browser",
             "body": "Hi there,\n\nThis text was edited before sending.\n\nVineet",
             "note": "looks fine"},
            headers={"Accept": "application/json"})
        self.assertEqual(resp.status, 200)
        msg = self.store.one(
            "SELECT subject, body FROM messages WHERE direction='out'")
        self.assertEqual(msg["subject"], "Edited in the browser")
        self.assertIn("edited before sending", msg["body"])

    def test_rejecting_sends_nothing(self):
        self.post(f"/approvals/{self.run_result.approval_id}/decide?token=s3cret",
                  {"action": "reject", "note": "no"},
                  headers={"Accept": "application/json"})
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [])

    def test_a_decided_item_cannot_be_decided_again(self):
        path = f"/approvals/{self.run_result.approval_id}/decide?token=s3cret"
        self.post(path, {"action": "approve"}, headers={"Accept": "application/json"})
        again = self.post(path, {"action": "reject"},
                          headers={"Accept": "application/json"},
                          allow_status={409})
        self.assertEqual(again.status, 409)

    def test_api_state_is_machine_readable(self):
        data = self.get("/api/state?token=s3cret").json()
        self.assertEqual(len(data["pending"]), 1)
        self.assertIn("events", data)


class TestUnsubscribeEndpoint(ServerCase):
    def test_valid_link_suppresses(self):
        from core.mailer import SuppressionList, unsubscribe_token
        addr = "a@b.example"
        tok = unsubscribe_token(addr)
        r = self.get(f"/unsubscribe?e={urllib.parse.quote(addr)}&t={tok}")
        self.assertEqual(r.status, 200)
        self.assertTrue(SuppressionList(self.store).contains(addr))

    def test_forged_link_is_refused(self):
        from core.mailer import SuppressionList
        r = self.get("/unsubscribe?e=a@b.example&t=forged", allow_status={400})
        self.assertEqual(r.status, 400)
        self.assertFalse(SuppressionList(self.store).contains("a@b.example"))

    def test_one_click_post_works(self):
        from core.mailer import unsubscribe_token
        addr = "c@d.example"
        r = self.post(f"/unsubscribe?e={urllib.parse.quote(addr)}"
                      f"&t={unsubscribe_token(addr)}", {})
        self.assertTrue(r.json()["ok"])

    def test_unsubscribe_needs_no_dashboard_token(self):
        from core.mailer import unsubscribe_token
        addr = "e@f.example"
        self.assertEqual(
            self.get(f"/unsubscribe?e={addr}&t={unsubscribe_token(addr)}").status,
            200)


class TestGmailWebhook(ServerCase):
    def test_push_is_dispatched(self):
        seen = {}
        self.srv.on_gmail_push = lambda payload: seen.setdefault("p", payload) and 2
        data = base64.urlsafe_b64encode(
            json.dumps({"emailAddress": "me@x", "historyId": "42"}).encode()).decode()
        from core import http
        r = http.post(self.base + "/gmail/push",
                      json_body={"message": {"data": data}}, retries=0)
        self.assertEqual(r.status, 200)
        self.assertIn("p", seen)

    def test_handler_failure_still_acks(self):
        def boom(payload):
            raise RuntimeError("downstream broke")
        self.srv.on_gmail_push = boom
        from core import http
        r = http.post(self.base + "/gmail/push", json_body={"message": {}}, retries=0)
        self.assertEqual(r.status, 200, "must ack or Pub/Sub retries forever")
        self.assertFalse(r.json()["ok"])

    def test_token_protected_when_configured(self):
        import os
        os.environ["PUBSUB_TOKEN"] = "psk"
        from core import http
        bad = http.post(self.base + "/gmail/push", json_body={}, retries=0)
        self.assertEqual(bad.status, 401)
        self.srv.on_gmail_push = lambda p: 0
        ok = http.post(self.base + "/gmail/push?token=psk", json_body={}, retries=0)
        self.assertEqual(ok.status, 200)


class TestConsole(ServerCase):
    """The two-pane console: the rail, the per-agent pane, and running."""

    def setUp(self):
        super().setUp()
        self.aid = self.queue.create(
            thread_id="t-console", agent="video_client", kind="send_email",
            title="Pitch to Acme Films",
            payload={"to": "hiring@acmefilms.example",
                     "subject": "Editing for your channel",
                     "body": "Hello - I edit long-form cricket breakdowns.",
                     "best_phone": "+91 98765 43210",
                     "fit": "They post three long videos a week."})

    def test_rail_lists_every_agent_on_every_page(self):
        from server import console
        body = self.get("/?token=s3cret").text
        for a in console.AGENTS:
            self.assertIn(f"/agent/{a['key']}", body)
            self.assertIn(a["name"], body)

    def test_rail_counts_what_is_waiting(self):
        body = self.get("/?token=s3cret").text
        # The card created above belongs to the video agent, so its own count
        # must be non-zero and it must not be attributed to another agent.
        self.assertRegex(body, r"/agent/video_client[^<]*'>.*?count'?>[1-9]")

    def test_agent_pane_shows_only_that_agents_cards(self):
        other = self.queue.create(
            thread_id="t-other", agent="fullstack_sales", kind="send_email",
            title="Quote for a Razorpay integration",
            payload={"to": "x@y.example", "subject": "s", "body": "b"})
        body = self.get("/agent/video_client?token=s3cret").text
        self.assertIn("Pitch to Acme Films", body)
        self.assertNotIn("Razorpay integration", body)
        self.assertIn(other, self.get("/agent/fullstack_sales?token=s3cret").text)

    def test_agent_pane_shows_what_it_learned(self):
        from core.lessons import get_lessons
        get_lessons("video_client", self.store).add(
            "Never quote below the floor on a first reply.",
            evidence="he rejected a discount")
        body = self.get("/agent/video_client?token=s3cret").text
        self.assertIn("Never quote below the floor", body)
        # and it stays on that agent's page
        self.assertNotIn("Never quote below the floor",
                         self.get("/agent/job_hunter?token=s3cret").text)

    def test_a_retired_agent_name_still_has_a_home(self):
        """The prospector was folded into the sponsorship agent. Its old
        cards are still decisions he never made, so they must not vanish."""
        from server import console
        aid = self.queue.create(
            thread_id="t-old", agent="prospector", kind="add_target",
            title="Add Myntra to the sponsor list?",
            payload={"company": "Myntra"})
        self.assertEqual(console.home_for("prospector"), "sponsorship")
        body = self.get("/agent/sponsorship?token=s3cret").text
        self.assertIn("Add Myntra", body)
        # and it is counted, on the rail and in the overview
        self.assertIn("Add Myntra", self.get("/?token=s3cret").text)
        self.assertEqual(self.get(f"/approvals/{aid}?token=s3cret").status, 200)

    def test_pages_are_never_cached(self):
        """A stale approval queue is worse than none - he would act on it."""
        for path in ("/?token=s3cret", "/agent/video_client?token=s3cret",
                     f"/approvals/{self.aid}?token=s3cret",
                     "/api/state?token=s3cret"):
            r = self.get(path)
            got = (r.headers.get("cache-control")
                   or r.headers.get("Cache-Control") or "").lower()
            self.assertIn("no-store", got, path)

    def test_a_running_agent_makes_the_page_refresh_itself(self):
        import time as _t
        self.store.run(
            "INSERT INTO threads (thread_id, agent, status, created_at, "
            "updated_at, meta_json) VALUES (?,?,?,?,?,'{}')",
            ("t-live", "video_client", "running", _t.time(), _t.time()))
        body = self.get("/agent/video_client?token=s3cret").text
        self.assertIn("http-equiv=refresh", body)
        self.assertIn("class=working", body)
        # and a quiet agent does not spin the browser for no reason
        self.assertNotIn("http-equiv=refresh",
                         self.get("/agent/job_hunter?token=s3cret").text)

    def test_a_run_that_went_quiet_stops_claiming_to_work(self):
        import time as _t
        old = _t.time() - 4000
        self.store.run(
            "INSERT INTO threads (thread_id, agent, status, created_at, "
            "updated_at, meta_json) VALUES (?,?,?,?,?,'{}')",
            ("t-stale", "fullstack_sales", "running", old, old))
        body = self.get("/agent/fullstack_sales?token=s3cret").text
        self.assertIn("quiet for a while", body)
        self.assertNotIn("http-equiv=refresh", body)

    def test_the_page_says_what_the_agent_just_did(self):
        self.store.event("notification", "video_client", "t-console",
                         body="Found 168 open gigs, 168 of them new.")
        body = self.get("/agent/video_client?token=s3cret").text
        self.assertIn("Found 168 open gigs", body)

    def test_a_paused_agent_says_a_card_is_waiting(self):
        import time as _t
        self.store.run(
            "INSERT INTO threads (thread_id, agent, status, created_at, "
            "updated_at, meta_json) VALUES (?,?,?,?,?,'{}')",
            ("t-paused", "video_client", "interrupted", _t.time(), _t.time()))
        self.assertIn("card waiting for you",
                      self.get("/agent/video_client?token=s3cret").text)

    def test_unknown_agent_is_a_404_not_a_crash(self):
        r = self.get("/agent/not_an_agent?token=s3cret", allow_status={404})
        self.assertEqual(r.status, 404)

    def test_agent_pane_needs_the_token(self):
        self.assertEqual(
            self.get("/agent/video_client", allow_status={401}).status, 401)

    def test_card_opens_with_handoff_buttons(self):
        body = self.get(f"/approvals/{self.aid}?token=s3cret").text
        self.assertIn("mailto:hiring@acmefilms.example", body)
        self.assertIn("wa.me/919876543210", body)
        self.assertIn("Approve and send", body)

    def test_api_state_reports_every_agent(self):
        data = self.get("/api/state?token=s3cret").json()
        keys = {a["key"] for a in data["agents"]}
        self.assertEqual(len(keys), 6)
        counts = {a["key"]: a["pending"] for a in data["agents"]}
        self.assertGreaterEqual(counts["video_client"], 1)

    def test_running_a_parked_agent_is_refused(self):
        r = self.post("/agent/saas_sales/run?token=s3cret", {},
                      allow_status={409})
        self.assertEqual(r.status, 409)

    def test_running_an_unknown_agent_is_refused(self):
        r = self.post("/agent/nope/run?token=s3cret", {}, allow_status={404})
        self.assertEqual(r.status, 404)

    def test_run_needs_the_token(self):
        r = self.post("/agent/video_client/run", {}, allow_status={401})
        self.assertEqual(r.status, 401)
        self.assertNotIn("video_client", self.srv.runs)


class TestDemoMode(ServerCase):
    """Safe to put on a screen in front of a stranger."""
    extra_env = {"DASHBOARD_TOKEN": "s3cret", "DEMO_MODE": "true"}

    def setUp(self):
        super().setUp()
        self.aid = self.queue.create(
            thread_id="t-demo", agent="sponsorship", kind="send_email",
            title="Pitch to Acme",
            payload={"to": "deals@acme.example",
                     "subject": "Sponsoring the channel",
                     "body": "Write to me on vineet@example.com or "
                             "+91 98765 43210.",
                     "best_phone": "+91 98765 43210"})

    def test_addresses_and_numbers_are_hidden(self):
        body = self.get(f"/approvals/{self.aid}?token=s3cret").text
        self.assertNotIn("deals@acme.example", body)
        self.assertNotIn("vineet@example.com", body)
        self.assertNotIn("98765 43210", body)
        # the shape survives, so the demo still shows what the agent did
        self.assertIn("Sponsoring the channel", body)

    def test_nothing_can_be_decided(self):
        r = self.post(f"/approvals/{self.aid}/decide?token=s3cret",
                      {"action": "approve"}, allow_status={403})
        self.assertEqual(r.status, 403)
        self.assertEqual(self.queue.get(self.aid)["status"], "pending")

    def test_nothing_can_be_run(self):
        r = self.post("/agent/sponsorship/run?token=s3cret", {},
                      allow_status={403})
        self.assertEqual(r.status, 403)
        self.assertEqual(self.srv.runs, {})

    def test_the_resume_is_not_downloadable(self):
        r = self.get("/resumes/anything.pdf?token=s3cret", allow_status={403})
        self.assertEqual(r.status, 403)

    def test_there_are_no_send_buttons(self):
        body = self.get(f"/approvals/{self.aid}?token=s3cret").text
        self.assertNotIn("mailto:", body)
        self.assertNotIn("wa.me", body)
        self.assertNotIn("value=approve", body)


class TestRedaction(unittest.TestCase):
    """The redactor itself, without a server in the way."""

    def _with(self, on: bool):
        import os
        from server import console
        os.environ["DEMO_MODE"] = "true" if on else "false"
        from core import config
        config.reload() if hasattr(config, "reload") else None
        return console

    def test_off_by_default_leaves_text_alone(self):
        console = self._with(False)
        self.assertEqual(console.redact("a@b.com"), "a@b.com")

    def test_on_hides_emails_phones_and_keys(self):
        console = self._with(True)
        out = console.redact("mail a.b+c@d.co.in or 98765 43210, key sk-abcdef123456")
        self.assertNotIn("a.b+c@d.co.in", out)
        self.assertNotIn("98765 43210", out)
        self.assertNotIn("sk-abcdef123456", out)
        self.assertIn("or", out)
        self._with(False)



class TestReviewedAttachments(ServerCase):
    def test_reviewed_pdf_requires_token_and_is_downloadable(self):
        from core import config
        path = config.data_dir() / "invoice-test.pdf"
        path.write_bytes(b"%PDF-1.4 reviewed document")
        aid = self.queue.create(thread_id="attachment", agent="video_client", kind="send_reply",
                                title="Review", payload={"attachments": [str(path)]})
        self.assertEqual(self.get(f"/attachments/{aid}/0", allow_status={401}).status, 401)
        result = self.get(f"/attachments/{aid}/0?token=s3cret")
        self.assertEqual(result.body, path.read_bytes())
        self.assertIn("application/pdf", result.headers["content-type"])

    def test_attachment_cannot_expose_a_file_outside_data_directory(self):
        path = self.tmp / "private.pdf"
        path.write_bytes(b"private")
        aid = self.queue.create(thread_id="outside", agent="video_client", kind="send_reply",
                                title="Review", payload={"attachments": [str(path)]})
        self.assertEqual(self.get(f"/attachments/{aid}/0?token=s3cret", allow_status={403}).status, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
