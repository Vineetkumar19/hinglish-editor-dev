"""Regression coverage for delivery, factual form answers and durable workflows."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import threading
from unittest.mock import patch

from tests.base import SuiteCase
from tests.fakes.servers import FakeSMTPServer


class DeliveryCase(SuiteCase):
    def setUp(self):
        super().setUp()
        self.smtp = FakeSMTPServer().start()
        os.environ.update({"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(self.smtp.port),
            "SMTP_STARTTLS": "false", "SMTP_REQUIRE_TLS": "false", "DRY_RUN": "false",
            "SMTP_USER": "", "SMTP_PASSWORD": ""})
        from core.mailer import Mailer
        self.mailer = Mailer(self.store, transport="smtp")

    def tearDown(self):
        self.smtp.stop()
        super().tearDown()

    def deliver(self, **kwargs):
        from core.delivery import deliver_reviewed
        args = dict(store=self.store, agent="video_client", thread_id="reviewed-gig",
            target={"id": "a", "company": "Acme", "email": "client@example.com", "url": "https://example.com/job"},
            draft={"subject": "Original", "body": "Original message with enough detail to send."}, decision={"status": "approved"}, mailer=self.mailer)
        return deliver_reviewed(**{**args, **kwargs})

    def test_reviewed_email_is_delivered_once_with_edits(self):
        result = self.deliver(decision={"status": "edited", "edits": {"body": "The reviewed message with all the approved details."}})
        self.assertEqual(result["status"], "contacted")
        self.deliver()
        self.assertEqual(len(self.smtp.messages), 1)
        self.assertIn("The reviewed message", self.smtp.messages[0]["body"])

    def test_unapproved_email_never_sends(self):
        from core.mailer import SendBlocked
        with self.assertRaises(SendBlocked):
            self.deliver(decision={"status": "pending"})
        self.assertEqual(self.smtp.messages, [])

    def test_form_handoff_is_not_reported_as_a_sent_email(self):
        from core.delivery import mark_manual_sent
        result = self.deliver(target={"id": "form", "url": "https://example.com/form"})
        self.assertEqual(result["status"], "ready_to_send")
        self.assertEqual(self.smtp.messages, [])
        self.assertTrue(mark_manual_sent(self.store, result["lead_id"]))
        self.assertFalse(mark_manual_sent(self.store, result["lead_id"]))

    def test_mailer_receipt_survives_a_delivery_replay(self):
        from core.mailer import OutgoingMessage
        message = OutgoingMessage(to="client@example.com", subject="Receipt", body="Reviewed body with all the agreed details.", idempotency_key="same")
        a = self.mailer.send(message)
        b = self.mailer.send(message)
        self.assertEqual(a["message_id"], b["message_id"])
        self.assertEqual(len(self.smtp.messages), 1)

    def test_unknown_delivery_attempt_is_not_automatically_retried(self):
        from core.mailer import OutgoingMessage, SendBlocked
        self.store.kv_set("send_receipts", "live:uncertain", {"status": "sending"})
        with self.assertRaises(SendBlocked):
            self.mailer.send(OutgoingMessage(to="client@example.com", subject="Test", body="Body", idempotency_key="uncertain"))
        self.assertEqual(self.smtp.messages, [])

    def test_video_close_sends_the_agreed_amount_and_two_attachments(self):
        os.environ["PAYMENT_DETAILS"] = "UPI: validation@example"
        from agents.video_client.agent import make_reply
        from agents.video_client.quote import build_quote
        delivery = self.deliver()
        quote = build_quote("India long form edit")
        agreed = quote.floor + 123
        self.store.kv_set("video_client", "deal:agreed", {"lead_id": delivery["lead_id"],
            "stage": "quoted", "amount": agreed, "quote": quote.to_json(),
            "gig": {"company": "Acme", "description": "India long form edit"}})
        agent = make_reply(store=self.store, llm=self.offline_llm())
        result = agent.handle({"id": "accepted", "from_addr": "client@example.com", "subject": "Our edit",
            "reply_text": "Agreed, happy to proceed. Please send an invoice.", "rfc_message_id": "<client@acme>"}, thread_id="accepted-video")
        self.assertTrue(result.interrupted, result.error)
        payload = self.queue.get(result.approval_id)["payload"]
        self.assertIn(quote.money(agreed), payload["body"])
        self.assertEqual(len(payload["attachments"]), 2)
        result = agent.build().resume(result.thread_id, self.queue.approve(result.approval_id).to_json())
        self.assertTrue(result.complete, result.error)
        self.assertEqual(self.store.kv_get("video_client", "deal:agreed")["stage"], "won")
        self.assertIn("multipart/mixed", self.smtp.messages[-1]["raw"])
        self.assertEqual(self.store.one("SELECT status FROM leads WHERE id=?", (delivery["lead_id"],))["status"], "closed_won")

    def test_dry_run_does_not_spend_the_live_send_cap(self):
        from core.mailer import OutgoingMessage
        self.mailer.send(OutgoingMessage(to="client@example.com", subject="Preview",
                          body="A complete preview of this message for review."), dry_run=True)
        self.assertEqual(self.mailer.sent_today(), 0)
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [])

    def test_missing_payment_details_hold_invoice_but_allow_deal_closure(self):
        from agents.video_client.agent import make_reply
        from agents.video_client.quote import build_quote
        os.environ.pop("PAYMENT_DETAILS", None)
        delivery = self.deliver()
        quote = build_quote("India long form editing")
        self.store.kv_set("video_client", "deal:needs-payment", {"lead_id": delivery["lead_id"],
            "stage": "quoted", "amount": quote.ask, "quote": quote.to_json(),
            "gig": {"company": "Acme"}})
        agent = make_reply(store=self.store, llm=self.offline_llm())
        result = agent.handle({"id": "payment-setup", "from_addr": "client@example.com",
            "subject": "Edit", "reply_text": "Agreed, send an invoice.", "rfc_message_id": "<yes>"}, thread_id="payment-setup")
        self.assertTrue(result.interrupted, result.error)
        self.assertEqual(self.queue.get(result.approval_id)["kind"], "send_reply")
        self.assertEqual(len(self.queue.get(result.approval_id)["payload"]["attachments"]), 1)
        self.assertEqual(result.state["deal_update"]["invoice_status"], "awaiting_payment_details")
        result = agent.build().resume(result.thread_id, self.queue.approve(result.approval_id).to_json())
        self.assertTrue(result.complete, result.error)
        self.assertEqual(self.store.kv_get("video_client", "deal:needs-payment")["stage"], "won")


class WorkflowCase(SuiteCase):
    def test_inbox_failure_preserves_the_message_for_a_later_poll(self):
        from core.inbox import process
        from types import SimpleNamespace
        from unittest.mock import Mock
        message = SimpleNamespace(id="msg", thread_id="t", from_addr="a@example.com", from_name="A",
            to_addr="test@example.com", subject="Hello", rfc_message_id="<msg>", in_reply_to="", references="",
            reply_text="Interested in a project", is_auto_reply=False)
        inbox = Mock()
        inbox.poll.side_effect = [[message], []]
        with patch("core.inbox.route", side_effect=RuntimeError("temporarily unavailable")):
            self.assertEqual(process(self.store, inbox=inbox), 0)
        inbox.mark_read.assert_not_called()
        self.assertTrue(self.store.kv_list("inbox_pending"))
        with patch("core.inbox.route") as route:
            self.assertEqual(process(self.store, inbox=inbox), 1)
            route.assert_called_once()
        self.assertFalse(self.store.kv_list("inbox_pending"))
        inbox.mark_read.assert_called_once_with("msg")

    def test_recruiter_choice_only_matches_an_offered_slot(self):
        from core.inbox import selected_slot
        offer = {"slots": ["Tue 27 Oct, 10:00-10:45 Asia/Kolkata", "Tue 27 Oct, 12:00-12:45 Asia/Kolkata"],
                 "slot_iso": [["a", "b"], ["c", "d"]]}
        self.assertEqual(selected_slot("Option 2 works for me", offer), 1)
        self.assertIsNone(selected_slot("Option 2 or option 1 might work", offer))
        self.assertIsNone(selected_slot("Option 3 works", offer))

    def test_approval_can_only_be_decided_once_under_concurrency(self):
        aid = self.queue.create(thread_id="decision", agent="community", kind="send_message", title="Review", payload={})
        def decide(_):
            try:
                self.queue.approve(aid)
                return True
            except RuntimeError:
                return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(decide, range(2))), 1)

    def test_salary_and_project_limits_use_the_correct_period(self):
        from core.work_policy import budget_check
        self.assertTrue(budget_check({"salary_max": 599999, "salary_currency": "INR"})["reject"])
        self.assertFalse(budget_check({"salary_max": 600000, "salary_currency": "INR"})["reject"])
        self.assertTrue(budget_check({"salary_max": 49000, "salary_currency": "INR", "salary_period": "month"})["reject"])
        self.assertTrue(budget_check({"title": "Freelance project", "description": "Budget INR 9,000 per project"})["reject"])
        self.assertFalse(budget_check({"title": "Freelance project", "description": "Budget INR 10,000 per project"})["reject"])
        self.assertFalse(budget_check({"title": "Developer", "description": "Competitive pay"})["reject"])

    def test_project_floor_survives_first_project_discount(self):
        from agents.video_client.quote import build_quote
        from agents.fullstack_sales.packages import build_package
        q = build_quote("India short form video", first_project=True)
        self.assertGreaterEqual(q.floor, 10000)
        self.assertGreaterEqual(q.ask, q.floor)
        for q in (build_quote("India sound design"), build_package("India payment audit")):
            self.assertGreaterEqual(q.floor, 10000)

    def test_community_always_discloses_affiliation_and_stays_a_handoff(self):
        from agents.community.agent import CommunityAgent
        agent = CommunityAgent(store=self.store, llm=self.offline_llm())
        result = agent.run(thread_id="community-review", contexts=[{
            "id": "one", "title": "Cricket analysis", "description": "How do you judge a batting collapse?",
            "url": "https://example.com/discussion", "platform": "forum", "promotion_allowed": False}])
        self.assertTrue(result.interrupted, result.error)
        decision = self.queue.approve(result.approval_id, edits={"body": "My reviewed analysis."})
        result = agent.build().resume(result.thread_id, decision.to_json())
        self.assertTrue(result.complete, result.error)
        handoff = result.state["handoff"][0]
        self.assertIn("Disclosure:", handoff["body"])
        self.assertEqual(handoff["status"], "ready_to_send")
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [])

    def test_graph_resume_values_do_not_cross_threads(self):
        from core.graph import StateGraph, END, interrupt
        barrier = threading.Barrier(2)
        def node(state):
            barrier.wait(timeout=10)
            return {"answer": interrupt({"thread": state["_thread_id"]})}
        graph = StateGraph()
        graph.add_node("gate", node)
        graph.set_entry_point("gate")
        graph.add_edge("gate", END)
        app = graph.compile(store=self.store, name="concurrent")
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda tid: app.invoke({"_thread_id": tid}, thread_id=tid), ["a", "b"]))
            self.assertTrue(all(r.interrupted for r in results))
            results = list(pool.map(lambda tid: app.resume(tid, tid + "-answer"), ["a", "b"]))
        self.assertEqual([r.state["answer"] for r in results], ["a-answer", "b-answer"])

    def test_skipping_a_resumed_gate_cannot_approve_the_next_gate(self):
        from core.graph import StateGraph, END, interrupt
        external = {"skip": False}
        def first(state):
            if not external["skip"]:
                interrupt({"gate": "first"})
            return {}
        graph = StateGraph()
        graph.add_node("first", first)
        graph.add_node("second", lambda state: {"answer": interrupt({"gate": "second"})})
        graph.set_entry_point("first")
        graph.add_edge("first", "second")
        graph.add_edge("second", END)
        app = graph.compile(store=self.store, name="changed-gate")
        self.assertTrue(app.invoke({}, thread_id="changed").interrupted)
        external["skip"] = True
        result = app.resume("changed", {"status": "approved"})
        self.assertTrue(result.interrupted)
        self.assertEqual(result.interrupt["gate"], "second")

    def test_followup_waits_for_approval_and_stops_if_a_reply_arrives(self):
        from core.followups import queue_due, FollowUpAgent
        from core.store import now
        from core.delivery import deliver_reviewed, mark_manual_sent
        result = deliver_reviewed(store=self.store, agent="video_client", thread_id="original",
            target={"id": "job", "url": "https://example.com/job"},
            draft={"subject": "Hi", "body": "Pitch"}, decision={"status": "approved"})
        mark_manual_sent(self.store, result["lead_id"])
        self.store.run("UPDATE leads SET email=?,updated_at=? WHERE id=?",
                       ("client@example.com", now()-6*86400, result["lead_id"]))
        self.assertEqual(queue_due(self.store), 1)
        self.assertEqual(queue_due(self.store), 0)
        row = self.queue.pending()[0]
        self.store.run("UPDATE leads SET status='engaged' WHERE id=?", (result["lead_id"],))
        decision = self.queue.approve(row["id"])
        result = FollowUpAgent(store=self.store).build().resume(row["thread_id"], decision.to_json())
        self.assertEqual(result.state["outcome"], "no_longer_due")

    def test_calendar_hours_are_local_not_utc(self):
        from core.calendar import CalendarClient
        client = CalendarClient(self.store)
        with patch.object(client, "freebusy", return_value=[]):
            slots = client.find_slots(duration_min=45, now=dt.datetime(2026,10,20,6,tzinfo=dt.timezone.utc))
        self.assertTrue(slots)
        for slot in slots:
            self.assertGreaterEqual(slot.start.hour, 10)
            self.assertLessEqual((slot.end.hour, slot.end.minute), (18, 0))
            self.assertIn("Asia/Kolkata", slot.human("Asia/Kolkata"))

    def test_booking_requires_review_and_checks_for_calendar_conflicts(self):
        from agents.job_hunter.booking import BookingAgent
        from unittest.mock import Mock
        calendar = Mock()
        calendar.freebusy.return_value = [(dt.datetime(2026,11,1,10,tzinfo=dt.timezone.utc),
                                          dt.datetime(2026,11,1,11,tzinfo=dt.timezone.utc))]
        agent = BookingAgent(store=self.store, calendar=calendar)
        result = agent.run("Interview", "2026-11-01T10:00:00+00:00", "2026-11-01T10:45:00+00:00", ["recruiter@example.com"])
        self.assertTrue(result.interrupted)
        calendar.create_event.assert_not_called()
        os.environ["DRY_RUN"] = "false"
        result = agent.build().resume(result.thread_id, self.queue.approve(result.approval_id).to_json())
        self.assertEqual(result.state["result"]["outcome"], "conflict")
        calendar.create_event.assert_not_called()


class ApplicationCase(SuiteCase):
    def test_a_changed_form_requires_a_fresh_approval(self):
        from agents.job_hunter.application import ApplicationAgent
        from unittest.mock import Mock
        browser = Mock()
        browser.inspect.return_value = {"url": "https://example.com/form", "fingerprint": "a", "fields": []}
        browser.submit.return_value = {"outcome": "form_changed", "inspection": {
            "url": "https://example.com/form", "fingerprint": "b", "fields": [
                {"label": "New question", "type": "text", "required": True, "index": 0}]}}
        path = self.tmp / "resume.pdf"
        path.write_bytes(b"%PDF")
        agent = ApplicationAgent(store=self.store, browser=browser)
        result = agent.run("https://example.com/form", str(path), master={"name": "Test Person"})
        first = result.approval_id
        result = agent.build().resume(result.thread_id, self.queue.approve(first).to_json())
        self.assertTrue(result.interrupted, result.error)
        self.assertNotEqual(result.approval_id, first)
        self.assertEqual(self.queue.get(result.approval_id)["payload"]["missing_fields"], ["New question"])
    def test_unknown_sponsorship_answer_is_never_invented(self):
        from agents.job_hunter.application import plan_answers
        plan = plan_answers({"fields": [
            {"label": "Full Name", "type": "text", "required": True, "index": 0},
            {"label": "Do you require visa sponsorship?", "type": "text", "required": True, "index": 1}]},
            {"name": "Test Person"}, {}, "resume.pdf")
        self.assertEqual(plan["fields"][0]["answer"], "Test Person")
        self.assertEqual(plan["missing"], ["Do you require visa sponsorship?"])

    def test_reviewed_answers_are_the_only_ones_submitted(self):
        from agents.job_hunter.application import ApplicationAgent
        from unittest.mock import Mock
        browser = Mock()
        browser.inspect.return_value = {"url": "https://example.com/apply", "fingerprint": "abc", "fields": [
            {"label": "Visa sponsorship", "type": "text", "required": True, "index": 0}]}
        browser.submit.return_value = {"outcome": "submitted"}
        resume = self.tmp / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4 test")
        agent = ApplicationAgent(store=self.store, browser=browser)
        result = agent.run("https://example.com/apply", str(resume), master={"name": "Test Person"})
        self.assertTrue(result.interrupted, result.error)
        browser.submit.assert_not_called()
        decision = self.queue.approve(result.approval_id, edits={"answers": {"Visa sponsorship": "No"}})
        result = agent.build().resume(result.thread_id, decision.to_json())
        self.assertEqual(result.state["result"]["outcome"], "submitted")
        self.assertEqual(browser.submit.call_args.args[0]["fields"][0]["answer"], "No")

    def test_dry_run_does_not_upload_files_or_even_open_browser(self):
        from core.browser import ApplicationBrowser
        with patch("core.browser.browser_page", side_effect=AssertionError("Should not open a page")):
            self.assertEqual(ApplicationBrowser().submit({}, "file.pdf", dry_run=True)["outcome"], "preview")

    def test_real_browser_reaches_local_ats_only_after_review(self):
        if importlib.util.find_spec("playwright") is None:
            self.skipTest("Install requirements-browser.txt for the browser integration test")
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from agents.job_hunter.application import ApplicationAgent
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                body = b'''<html><body><h1>Apply</h1><form method="post" enctype="multipart/form-data">
                <label>Full name<input name="name" required></label>
                <label>Email<input name="email" type="email" required></label>
                <label>Resume<input name="resume" type="file" required></label>
                <button type="submit">Submit application</button></form></body></html>'''
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def do_POST(self):
                received.append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200); self.end_headers(); self.wfile.write(b"Thank you for applying. Application received.")
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            os.environ["DRY_RUN"] = "false"
            resume = self.tmp / "resume.pdf"
            resume.write_bytes(b"%PDF-1.4 factual-resume-test")
            agent = ApplicationAgent(store=self.store)
            result = agent.run(f"http://127.0.0.1:{server.server_port}/apply", str(resume),
                master={"name": "Test Person", "contact": {"email": "test@example.com"}})
            self.assertTrue(result.interrupted, result.error)
            self.assertEqual(received, [])
            result = agent.build().resume(result.thread_id, self.queue.approve(result.approval_id).to_json())
            self.assertTrue(result.complete, result.error)
            self.assertEqual(result.state["result"]["outcome"], "submitted")
            self.assertEqual(len(received), 1)
            self.assertIn(b"Test Person", received[0])
            self.assertIn(b"factual-resume-test", received[0])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)
