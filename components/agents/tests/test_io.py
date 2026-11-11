"""Integration tests against fake servers speaking the real protocols."""
from __future__ import annotations

import base64
import datetime as dt
import json
import unittest

from tests.base import SuiteCase
from tests.fakes.servers import (FakeAnthropicServer, FakeGoogleServer,
                                 FakeSMTPServer, FakeWebServer)


class GoogleCase(SuiteCase):
    def setUp(self):
        super().setUp()
        self.google = FakeGoogleServer().start()
        import os
        os.environ.update({
            "GMAIL_API_BASE": self.google.gmail_base,
            "CALENDAR_API_BASE": self.google.calendar_base,
            "GOOGLE_TOKEN_URI": self.google.token_uri,
            "GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csec"})
        from core.oauth import GoogleOAuth
        self.oauth = GoogleOAuth(store=self.store)
        self.oauth.exchange("fake-code", "http://127.0.0.1/cb")

    def tearDown(self):
        self.google.stop()
        super().tearDown()

    def gmail(self):
        from core.gmail import GmailClient
        return GmailClient(store=self.store, oauth=self.oauth)


class TestOAuth(GoogleCase):
    def test_exchange_and_refresh(self):
        tok = self.oauth.load()
        self.assertTrue(tok.refresh_token)
        from core.oauth import Token
        self.oauth.save(Token(access_token="old",
                              refresh_token="fake-refresh-token", expires_at=0))
        self.assertTrue(self.oauth.access_token().startswith("fake-access-"))
        self.assertEqual(self.google.state.refresh_count, 1)

    def test_bad_refresh_token_is_an_error(self):
        from core.oauth import OAuthError, Token
        self.oauth.save(Token(access_token="x", refresh_token="wrong", expires_at=0))
        with self.assertRaises(OAuthError):
            self.oauth.access_token()

    def test_missing_token_message_is_actionable(self):
        from core.oauth import GoogleOAuth, OAuthError
        fresh = GoogleOAuth(store=self.store, account="never-authorised")
        with self.assertRaises(OAuthError) as ctx:
            fresh.access_token()
        self.assertIn("run.py auth google", str(ctx.exception))


class TestGmail(GoogleCase):
    def test_watch_registers_and_reports_expiry(self):
        gm = self.gmail()
        gm.watch("projects/p/topics/t")
        self.assertAlmostEqual(gm.watch_expires_in() / 86400, 7, delta=0.1)
        self.assertFalse(gm.renew_watch_if_needed("projects/p/topics/t"))

    def test_history_delta_returns_only_new_messages(self):
        gm = self.gmail()
        gm.watch("projects/p/topics/t")
        self.google.state.deliver(sender="a@x.example", subject="One", body="body one here")
        first = gm.poll()
        self.assertEqual(len(first), 1)
        self.google.state.deliver(sender="b@x.example", subject="Two", body="body two here")
        second = gm.poll()
        self.assertEqual([m.from_addr for m in second], ["b@x.example"])

    def test_push_notification_fetches_the_delta(self):
        gm = self.gmail()
        gm.set_cursor("1000")
        self.google.state.deliver(sender="c@x.example", subject="Hi", body="hello there")
        payload = {"message": {"data": base64.urlsafe_b64encode(json.dumps(
            {"emailAddress": "me@example.com",
             "historyId": str(self.google.state.next_history)}).encode()).decode()}}
        msgs = gm.handle_push(payload)
        self.assertEqual([m.from_addr for m in msgs], ["c@x.example"])

    def test_quoted_history_is_stripped_and_auto_replies_flagged(self):
        gm = self.gmail()
        gm.set_cursor("0")
        self.google.state.deliver(
            sender="p@x.example", subject="Re: Hi",
            body="Yes interested!\n\nOn Mon someone wrote:\n> old thread\n")
        self.google.state.deliver(
            sender="ooo@x.example", subject="Automatic reply: away",
            body="I am on leave.", headers={"Auto-Submitted": "auto-replied"})
        msgs = {m.from_addr: m for m in gm.poll()}
        self.assertEqual(msgs["p@x.example"].reply_text, "Yes interested!")
        self.assertTrue(msgs["ooo@x.example"].is_auto_reply)
        self.assertFalse(msgs["p@x.example"].is_auto_reply)

    def test_send_threads_the_reply(self):
        from core.mailer import Mailer, OutgoingMessage
        gm = self.gmail()
        m = Mailer(store=self.store, transport="gmail", gmail=gm)
        m.send(OutgoingMessage(to="x@y.example", subject="Re: Hello",
                               body="A reply body that is long enough to pass checks.",
                               in_reply_to="<orig@fake>", gmail_thread_id="thr1",
                               include_footer=False),
               enforce_cap=False, dry_run=False)
        sent = self.google.state.sent[-1]
        self.assertEqual(sent["in_reply_to"], "<orig@fake>")
        self.assertIn("x@y.example", sent["to"])


class TestCalendar(GoogleCase):
    def test_slots_avoid_busy_blocks_and_event_creation(self):
        from core.calendar import CalendarClient
        now = dt.datetime.now(dt.timezone.utc)
        busy_start = (now + dt.timedelta(days=1)).replace(
            hour=11, minute=0, second=0, microsecond=0)
        self.google.state.busy = [
            {"start": busy_start.isoformat().replace("+00:00", "Z"),
             "end": (busy_start + dt.timedelta(hours=4)).isoformat().replace("+00:00", "Z")}]
        cal = CalendarClient(store=self.store, oauth=self.oauth)
        slots = cal.find_slots(days_ahead=6, duration_min=45, max_slots=4)
        self.assertTrue(slots)
        for s in slots:
            self.assertFalse(s.start < busy_start + dt.timedelta(hours=4)
                             and s.end > busy_start, "slot overlaps a busy block")
        ev = cal.create_event(summary="Interview", start=slots[0].start,
                              end=slots[0].end, attendees=["r@x.example"])
        self.assertEqual(ev["attendees"][0]["email"], "r@x.example")


class TestSmtp(SuiteCase):
    def setUp(self):
        super().setUp()
        self.smtp = FakeSMTPServer().start()
        import os
        os.environ.update({"SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(self.smtp.port),
                           "SMTP_STARTTLS": "false", "SMTP_REQUIRE_TLS": "false",
                           "DRY_RUN": "false"})

    def tearDown(self):
        self.smtp.stop()
        super().tearDown()

    def mailer(self):
        from core.mailer import Mailer
        return Mailer(store=self.store, transport="smtp")

    def test_send_includes_compliance_headers_and_footer(self):
        from core.mailer import OutgoingMessage
        self.mailer().send(OutgoingMessage(
            to="a@b.example", subject="Partnership enquiry",
            body="Hi there,\n\nA body long enough to satisfy the minimum length.\n\nVineet",
            tag="test"))
        got = self.smtp.messages[-1]
        self.assertIn("List-Unsubscribe", got["raw"])
        self.assertIn("One-Click", got["raw"])
        # PUBLIC_BASE_URL is localhost in tests, as it is on a laptop: a link
        # the recipient cannot open is worse than no link, so the footer asks
        # for a reply instead. The header still carries a machine-readable one.
        self.assertIn("unsubscribe", got["body"].lower())
        self.assertIn("mailto:", got["headers"].get("List-Unsubscribe", "")
                      if isinstance(got.get("headers"), dict) else str(got))
        self.assertIn("Badlapur", got["body"])

    def test_hard_bounce_suppresses_the_address(self):
        from core.mailer import OutgoingMessage, SendBlocked
        m = self.mailer()
        self.smtp.refuse.add("dead@b.example")
        with self.assertRaises(SendBlocked):
            m.send(OutgoingMessage(to="dead@b.example", subject="Hello",
                                   body="A body long enough to pass the checks here."))
        self.assertTrue(m.suppression.contains("dead@b.example"))


class TestLlmOverHttp(SuiteCase):
    def test_anthropic_provider_real_request_and_repair_loop(self):
        import os
        attempts = {"n": 0}

        def responder(system, prompt, payload):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return "Sure! Here you go: {\"label\": \"not-a-valid-label\"}"
            return '{"label": "interested", "confidence": 0.9, "reason": "clear yes"}'

        srv = FakeAnthropicServer(responder=responder).start()
        try:
            os.environ.update({"LLM_PROVIDER": "anthropic",
                               "ANTHROPIC_API_KEY": "test-key",
                               "ANTHROPIC_BASE_URL": srv.url,
                               "LLM_MODEL": "claude-test"})
            from core.llm import LLM
            llm = LLM(store=self.store)
            out = llm.classify("Yes we are interested!", ["interested", "not_interested"])
            self.assertEqual(out["label"], "interested")
            self.assertEqual(attempts["n"], 2, "invalid output should trigger a repair")
            self.assertGreater(llm.usage.calls, 0)
        finally:
            srv.stop()

    def test_missing_api_key_is_a_clear_error(self):
        import os
        os.environ["LLM_PROVIDER"] = "anthropic"
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from core.llm import LLM
        with self.assertRaises(RuntimeError) as ctx:
            LLM(store=self.store).complete("hi")
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))


class TestCrawlerLive(SuiteCase):
    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def test_profiles_a_real_site(self):
        p = self.fast_crawler().profile_site("http://fantasy.example/")
        self.assertEqual(p.domain, "fantasy.example")
        self.assertGreaterEqual(len(p.pages), 3)
        self.assertEqual(p.best_contact.email, "partnerships@fantasy.example")
        self.assertIn("Next.js", p.tech)
        self.assertIn("linkedin", p.socials)

    def test_robots_disallow_is_honoured(self):
        p = self.fast_crawler().profile_site("http://gear.example/")
        self.assertIsNone(p.best_contact)
        self.assertTrue(all(not x.ok for x in p.pages))

    def test_phone_only_site_keeps_the_lead(self):
        p = self.fast_crawler().profile_site("http://noemail.example/")
        self.assertEqual(p.best_contact.phone, "+919000011111")
        self.assertEqual(p.best_contact.channel, "whatsapp")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestUnsubscribeRoute(SuiteCase):
    """A link the brand cannot open is worse than no link."""

    def test_a_localhost_dashboard_asks_for_a_reply_instead_of_linking(self):
        from core.mailer import compliance_footer
        with self.env(PUBLIC_BASE_URL="http://localhost:8080"):
            foot = compliance_footer("hi@brand.in")
        self.assertNotIn("localhost", foot)
        self.assertIn("unsubscribe", foot.lower())

    def test_a_real_public_url_is_linked(self):
        from core.mailer import compliance_footer
        with self.env(PUBLIC_BASE_URL="https://reach.vineet.in"):
            foot = compliance_footer("hi@brand.in")
        self.assertIn("https://reach.vineet.in/unsubscribe", foot)

    def test_the_example_postal_address_is_not_printed_as_if_it_were_real(self):
        from core.mailer import compliance_footer
        with self.env(SENDER_POSTAL_ADDRESS="Street, City, State, India"):
            self.assertNotIn("Street, City", compliance_footer("hi@brand.in"))
        with self.env(SENDER_POSTAL_ADDRESS="Badlapur, Maharashtra 421503, India"):
            self.assertIn("Badlapur", compliance_footer("hi@brand.in"))
