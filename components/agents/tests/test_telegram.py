"""The Telegram bot, driven against a fake Bot API that speaks the real protocol.

Nothing here talks to Telegram. The fake server accepts the same requests the
real API accepts, rejects the same things it rejects (empty text, oversized
messages, a non-forum chat), and records what was sent so the tests can assert
on it.
"""
from __future__ import annotations

import pathlib
import time
import unittest

from tests.base import SuiteCase
from tests.fakes.servers import FakeTelegramServer

OWNER = 42
STRANGER = 99
CHAT = -100999


class BotCase(SuiteCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeTelegramServer().start()
        from core.telegram import Telegram
        from server.bot import Bot
        self.tg = Telegram(token=self.fake.token, api_base=self.fake.url)
        self.bot = Bot(store=self.store, telegram=self.tg, queue=self.queue)

    def tearDown(self):
        self.fake.stop()
        super().tearDown()

    # -- helpers ------------------------------------------------------------
    def send(self, text: str, user_id: int = OWNER, thread_id=None):
        self.fake.state.queue_command(text, chat_id=CHAT, user_id=user_id,
                                      thread_id=thread_id)
        return self.bot.poll_once()

    def tap(self, data: str, user_id: int = OWNER, message_id: int = 1001):
        self.fake.state.queue_button(data, chat_id=CHAT, user_id=user_id,
                                     message_id=message_id)
        return self.bot.poll_once()

    def make_approval(self, agent: str = "job_hunter", title: str = "Apply to Zerodha",
                      company: str = "Zerodha", to: str = "jobs@z.example"):
        return self.queue.create(thread_id=f"t-{agent}", agent=agent, kind="apply",
                                 title=title,
                                 payload={"company": company, "to": to,
                                          "body": "Dear team, <b>hello</b>"})

    def all_text(self) -> str:
        return "\n".join(self.fake.state.texts())


class TestClient(BotCase):
    def test_talks_the_real_protocol(self):
        self.assertEqual(self.tg.get_me()["username"], "agentsuite_test_bot")

    def test_rejects_a_bad_token(self):
        from core.telegram import Telegram, TelegramError
        bad = Telegram(token="000:WRONG", api_base=self.fake.url)
        with self.assertRaises(TelegramError) as cm:
            bad.get_me()
        self.assertTrue(cm.exception.is_fatal)

    def test_long_messages_are_split_not_truncated(self):
        from core.telegram import MAX_MESSAGE
        body = "\n".join(f"line {i}" for i in range(2000))
        self.tg.send_message(CHAT, body)
        sent = self.fake.state.texts()
        self.assertGreater(len(sent), 1)
        for chunk in sent:
            self.assertLessEqual(len(chunk), MAX_MESSAGE)
        # every line survives the split
        self.assertEqual(len(body.split("\n")),
                         sum(len(c.split("\n")) for c in sent))

    def test_html_in_user_content_cannot_break_the_message(self):
        from core.telegram import esc
        self.assertEqual(esc("<b>x</b> & y"), "&lt;b&gt;x&lt;/b&gt; &amp; y")

    def test_sends_a_real_file(self):
        pdf = self.tmp / "resume.pdf"
        pdf.write_bytes(b"%PDF-1.4 hello")
        self.tg.send_document(CHAT, pdf, caption="tailored")
        doc = self.fake.state.documents[-1]
        self.assertEqual(doc["document_filename"], "resume.pdf")
        self.assertEqual(doc["document"], b"%PDF-1.4 hello")
        self.assertEqual(doc["caption"], "tailored")

    def test_missing_file_fails_loudly(self):
        with self.assertRaises(FileNotFoundError):
            self.tg.send_document(CHAT, self.tmp / "nope.pdf")


class TestSetup(BotCase):
    def test_start_creates_one_topic_per_agent(self):
        from server.bot import TOPICS
        self.send("/start")
        names = [t["name"] for t in self.fake.state.topics]
        self.assertEqual(sorted(names), sorted(t for t, _ in TOPICS.values()))
        self.assertEqual(self.bot.chat_id, CHAT)
        self.assertEqual(len(self.bot.topics), len(TOPICS))

    def test_start_twice_does_not_duplicate_topics(self):
        self.send("/start")
        first = len(self.fake.state.topics)
        self.send("/start")
        self.assertEqual(len(self.fake.state.topics), first)
        self.assertIn("Already set up", self.all_text())

    def test_group_without_topics_gets_an_explanation_not_a_crash(self):
        self.fake.state.is_forum = False
        self.send("/start")
        self.assertIn("Topics", self.all_text())
        self.assertEqual(self.fake.state.topics, [])
        # and the chat is still bound, so the bot is usable without topics
        self.assertEqual(self.bot.chat_id, CHAT)

    def test_first_user_to_start_becomes_the_owner(self):
        self.send("/start", user_id=OWNER)
        self.assertEqual(self.bot.owner_id, OWNER)

    def test_commands_are_registered_with_telegram(self):
        self.send("/start")
        registered = {c["command"] for c in self.fake.state.commands[-1]}
        self.assertIn("pending", registered)
        self.assertIn("run", registered)


class TestAuthorisation(BotCase):
    def test_a_stranger_cannot_drive_the_bot(self):
        self.send("/start", user_id=OWNER)
        before = len(self.fake.state.sent)
        self.send("/status", user_id=STRANGER)
        self.assertEqual(len(self.fake.state.sent), before,
                         "the bot replied to someone who is not its owner")

    def test_a_stranger_cannot_approve_anything(self):
        self.send("/start", user_id=OWNER)
        aid = self.make_approval()
        self.tap(f"ok:{aid}", user_id=STRANGER)
        self.assertEqual(self.queue.get(aid)["status"], "pending")
        self.assertTrue(self.fake.state.answered[-1]["show_alert"])

    def test_owner_from_config_overrides_the_claimed_one(self):
        import os
        self.send("/start", user_id=OWNER)
        os.environ["TELEGRAM_OWNER_ID"] = str(STRANGER)
        try:
            self.assertEqual(self.bot.owner_id, STRANGER)
        finally:
            os.environ.pop("TELEGRAM_OWNER_ID")


class TestCommands(BotCase):
    def setUp(self):
        super().setUp()
        self.send("/start")

    def test_help_lists_every_command(self):
        from server.bot import COMMANDS
        self.send("/help")
        text = self.fake.state.last_text()
        for name, _ in COMMANDS:
            self.assertIn(f"/{name}", text)

    def test_status_reports_what_is_waiting(self):
        self.make_approval(agent="job_hunter")
        self.make_approval(agent="sponsorship")
        self.send("/status")
        text = self.fake.state.last_text()
        self.assertIn("1 waiting on you", text)
        self.assertIn("DRY RUN", text)

    def test_pending_posts_each_item_with_buttons(self):
        self.make_approval(title="Apply to Zerodha")
        # A sponsorship card is rendered by company rather than by the queue
        # title, because that is what you recognise on a phone.
        self.make_approval(agent="sponsorship", title="Email Nutrabay",
                           company="Nutrabay", to="hello@nutrabay.com")
        self.send("/pending")
        self.assertIn("Apply to Zerodha", self.all_text())
        self.assertIn("Nutrabay", self.all_text())
        with_buttons = [m for m in self.fake.state.sent if m.get("reply_markup")]
        self.assertEqual(len(with_buttons), 2)

    def test_pending_when_there_is_nothing(self):
        self.send("/pending")
        self.assertIn("All clear", self.fake.state.last_text())

    def test_unknown_command_does_not_crash(self):
        self.send("/wibble")
        self.assertIn("do not know", self.fake.state.last_text())

    def test_run_needs_a_name_it_recognises(self):
        self.send("/run")
        text = self.fake.state.last_text()
        self.assertIn("/run jobs", text)
        self.assertIn("/run sponsorship", text)

    def test_id_reports_the_ids_you_need(self):
        self.send("/id")
        self.assertIn(str(CHAT), self.fake.state.last_text())
        self.assertIn(str(OWNER), self.fake.state.last_text())

    def test_jobs_and_leads_read_the_right_rows(self):
        from core.store import new_id, now
        for agent, company, status in (("job_hunter", "Zerodha", "applied"),
                                       ("sponsorship", "Nutrabay", "contacted")):
            self.store.upsert("leads", ("id",), {
                "id": new_id("x"), "agent": agent, "company": company,
                "domain": "", "person": "", "role": "Backend Engineer",
                "email": "a@b.example", "phone": "", "source_url": "",
                "score": 1.0, "status": status, "thread_id": "t",
                "data_json": "{}", "created_at": now(), "updated_at": now()})
        self.send("/jobs")
        self.assertIn("Zerodha", self.fake.state.last_text())
        self.assertNotIn("Nutrabay", self.fake.state.last_text())
        self.send("/leads")
        self.assertIn("Nutrabay", self.fake.state.last_text())
        self.assertNotIn("Zerodha", self.fake.state.last_text())

    def test_resume_sends_the_pdf_file(self):
        from agents.job_hunter.agent import output_dir
        out = pathlib.Path(output_dir())
        out.mkdir(parents=True, exist_ok=True)
        (out / "Vineet-zerodha.pdf").write_bytes(b"%PDF-1.4 x")
        self.send("/resume")
        self.assertEqual(self.fake.state.documents[-1]["document_filename"],
                         "Vineet-zerodha.pdf")

    def test_resume_says_so_when_there_are_none(self):
        self.send("/resume")
        self.assertIn("No resumes built yet", self.fake.state.last_text())


class TestApprovalFlow(BotCase):
    def setUp(self):
        super().setUp()
        self.send("/start")

    def test_approval_lands_in_its_own_agent_topic(self):
        jobs_thread = self.bot.topics["job_hunter"]
        sponsor_thread = self.bot.topics["sponsorship"]
        self.bot.post_approval(self.queue.get(self.make_approval("job_hunter")))
        self.bot.post_approval(self.queue.get(self.make_approval("sponsorship")))
        threads = [m.get("message_thread_id") for m in self.fake.state.sent[-2:]]
        self.assertEqual(threads, [str(jobs_thread), str(sponsor_thread)])

    def test_sub_flows_share_their_parent_topic(self):
        quote_thread = self.bot.topic_for("fullstack_sales_quote")
        self.assertEqual(quote_thread, self.bot.topics["fullstack_sales"])
        self.assertEqual(self.bot.topic_for("job_hunter_interview"),
                         self.bot.topics["job_hunter"])

    def test_push_pending_posts_each_approval_exactly_once(self):
        self.make_approval()
        self.assertEqual(self.bot.push_pending(), 1)
        self.assertEqual(self.bot.push_pending(), 0,
                         "the same approval was posted twice")

    def test_approve_button_decides_and_freezes_the_message(self):
        aid = self.make_approval()
        self.bot.post_approval(self.queue.get(aid))
        self.tap(f"ok:{aid}")
        self._settle()
        self.assertEqual(self.queue.get(aid)["status"], "approved")
        self.assertIn("APPROVED", self.fake.state.edits[-1]["text"])
        self.assertNotIn("reply_markup", self.fake.state.edits[-1])

    def test_reject_button_decides_the_other_way(self):
        aid = self.make_approval()
        self.bot.post_approval(self.queue.get(aid))
        self.tap(f"no:{aid}")
        self._settle()
        self.assertEqual(self.queue.get(aid)["status"], "rejected")
        self.assertIn("REJECTED", self.fake.state.edits[-1]["text"])

    def test_the_same_button_cannot_be_tapped_twice(self):
        aid = self.make_approval()
        self.bot.post_approval(self.queue.get(aid))
        self.tap(f"ok:{aid}")
        self._settle()
        self.tap(f"no:{aid}")          # the message is stale but still tappable
        self._settle()
        self.assertEqual(self.queue.get(aid)["status"], "approved",
                         "a second tap changed a decision that was already made")
        self.assertIn("Already approved", self.fake.state.answered[-1]["text"])

    def test_a_stale_approval_id_is_handled(self):
        self.tap("ok:ap_does_not_exist")
        self.assertIn("no longer exists", self.fake.state.answered[-1]["text"])

    def test_the_decision_note_records_it_came_from_telegram(self):
        aid = self.make_approval()
        self.bot.post_approval(self.queue.get(aid))
        self.tap(f"ok:{aid}")
        self._settle()
        self.assertIn("telegram",
                      str(self.queue.get(aid)["decision"]).lower())

    def _settle(self, timeout: float = 5.0):
        """The graph is resumed on a background thread; wait for it to finish."""
        self.bot.join_workers(timeout)


class TestNotifierChannel(BotCase):
    def test_agents_can_push_into_their_own_topic(self):
        import core.notify as notify_mod
        self.send("/start")
        notifier = notify_mod.Notifier(store=self.store, channels=["telegram"])
        import server.bot as bot_mod
        bot_mod._BOT = self.bot
        notifier.send("Nutrabay replied", "They want the media kit.",
                      tags=("sponsorship",))
        last = self.fake.state.sent[-1]
        self.assertIn("Nutrabay replied", last["text"])
        self.assertEqual(last.get("message_thread_id"),
                         str(self.bot.topics["sponsorship"]))

    def test_a_failed_notification_never_kills_the_run(self):
        import core.notify as notify_mod
        notifier = notify_mod.Notifier(store=self.store, channels=["telegram"])
        # no chat bound, so there is nowhere to post
        result = notifier.send("x", "y", tags=("job_hunter",))
        self.assertIn("telegram", result)


if __name__ == "__main__":
    unittest.main()


class TestJobControls(BotCase):
    """The controls Vineet asked for: set my level, pick my roles."""

    def setUp(self):
        super().setUp()
        self.send("/start")
        # keep .env writes inside the test's temp directory
        import core.config as cfg
        self._real_root = cfg.ROOT
        cfg.ROOT = self.tmp
        import server.bot as bot_mod
        bot_mod.config.ROOT = self.tmp

    def tearDown(self):
        import core.config as cfg
        import server.bot as bot_mod
        cfg.ROOT = self._real_root
        bot_mod.config.ROOT = self._real_root
        super().tearDown()

    def test_exp_shows_the_current_level(self):
        self.send("/exp")
        text = self.fake.state.last_text()
        self.assertIn("0 year", text)

    def test_exp_changes_the_level_and_says_what_changed(self):
        from agents.job_hunter import relevance
        self.send("/exp 2")
        self.assertEqual(relevance.max_experience_years(), 2)
        self.assertIn("2 year", self.fake.state.last_text())

    def test_exp_survives_a_restart(self):
        """It is written back to .env, not just held in memory."""
        self.send("/exp 3")
        written = (self.tmp / ".env").read_text(encoding="utf-8")
        self.assertIn("JOB_EXPERIENCE_YEARS=3", written)

    def test_exp_rejects_nonsense_without_crashing(self):
        from agents.job_hunter import relevance
        self.send("/exp banana")
        self.assertEqual(relevance.max_experience_years(), 0)
        self.assertIn("number", self.fake.state.last_text())

    def test_raising_experience_actually_opens_jobs_up(self):
        """The command has to change what the filter does, not just a setting."""
        from agents.job_hunter import relevance
        from agents.job_hunter.discovery import Job
        senior = Job(id="1", title="Backend Engineer", company="X",
                     description="We need 5+ years of experience.")
        self.assertFalse(relevance.classify(senior).relevant)
        self.send("/exp 4")
        self.assertTrue(relevance.classify(senior).relevant)

    def test_roles_lists_what_is_on(self):
        self.send("/roles")
        text = self.fake.state.last_text()
        self.assertIn("agentic_ai", text)
        self.assertIn("data_analysis", text)

    def test_roles_narrows_the_search(self):
        from agents.job_hunter import relevance
        from agents.job_hunter.discovery import Job
        self.send("/roles ai_ml agentic_ai")
        self.assertEqual(sorted(relevance.wanted_families()),
                         ["agentic_ai", "ai_ml"])
        self.assertFalse(relevance.classify(
            Job(id="1", title="Data Analyst", company="X")).relevant)
        self.assertTrue(relevance.classify(
            Job(id="2", title="AI Engineer", company="X")).relevant)

    def test_roles_all_turns_everything_back_on(self):
        from agents.job_hunter import relevance
        self.send("/roles ai_ml")
        self.send("/roles all")
        self.assertEqual(len(relevance.wanted_families()),
                         len(relevance.ROLE_FAMILIES))

    def test_an_unknown_role_name_is_refused(self):
        self.send("/roles quantum_wizard")
        self.assertIn("did not recognise", self.fake.state.last_text())


class TestJobCard(BotCase):
    def test_the_card_leads_with_what_decides_it(self):
        aid = self.queue.create(
            thread_id="t", agent="job_hunter", kind="apply_to_job",
            title="Apply: Backend Engineer at Razorpay",
            payload={"title": "Backend Engineer", "company": "Razorpay",
                     "salary": "INR 2,800,000 - 4,200,000",
                     "experience": "open to freshers", "location": "Bengaluru",
                     "remote": True, "role_family": "software",
                     "skills": ["Python", "Django", "PostgreSQL"],
                     "keyword_coverage": 0.43, "stripped_claims": [],
                     "apply_url": "https://r.example/apply",
                     "resume_path": str(self.tmp / "cv.pdf")})
        text = self.bot.approval_text(self.queue.get(aid))
        self.assertIn("Backend Engineer", text)
        self.assertIn("FRESHER OK", text)
        self.assertIn("INR 2,800,000 - 4,200,000", text)
        self.assertIn("Python, Django, PostgreSQL", text)
        self.assertIn("43%", text)
        self.assertIn("Nothing on the resume was made up", text)

    def test_a_job_card_offers_the_resume_and_the_application(self):
        aid = self.queue.create(
            thread_id="t", agent="job_hunter", kind="apply_to_job",
            title="Apply: X at Y",
            payload={"title": "X", "company": "Y",
                     "apply_url": "https://y.example/apply",
                     "resume_path": "/tmp/cv.pdf"})
        rows = self.bot.approval_buttons(aid, self.queue.get(aid))["inline_keyboard"]
        flat = [b for row in rows for b in row]
        self.assertTrue(any(b.get("callback_data") == f"cv:{aid}" for b in flat))
        self.assertTrue(any(b.get("url") == "https://y.example/apply" for b in flat))

    def test_an_email_card_has_no_resume_button(self):
        aid = self.queue.create(thread_id="t", agent="sponsorship",
                                kind="send_email", title="Email someone",
                                payload={"to": "a@b.example", "subject": "Hi"})
        rows = self.bot.approval_buttons(aid, self.queue.get(aid))["inline_keyboard"]
        flat = [b for row in rows for b in row]
        self.assertFalse(any(b.get("callback_data", "").startswith("cv:")
                             for b in flat))

    def test_the_resume_button_sends_the_pdf(self):
        pdf = self.tmp / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")
        self.send("/start")
        aid = self.queue.create(
            thread_id="t", agent="job_hunter", kind="apply_to_job",
            title="Apply: X at Y",
            payload={"title": "X", "company": "Y", "resume_path": str(pdf)})
        self.tap(f"cv:{aid}")
        self.assertEqual(self.fake.state.documents[-1]["document"], b"%PDF-1.4 test")
        self.assertEqual(self.queue.get(aid)["status"], "pending",
                         "asking for the resume must not decide the approval")


class TestBrandCard(BotCase):
    """The sponsorship card is what the whole agent is for - if it does not
    show the route and the message, nothing else matters."""

    def _card(self, **payload):
        base = {"company": "Nutrabay", "domain": "nutrabay.com",
                "segment": "nutrition", "tier": 1, "channel": "email",
                "to": "hello@nutrabay.com", "subject": "Cricket partnership",
                "body": "Hi,\n\nI run a cricket channel.",
                "fit": "Runs a creator programme year round",
                "evidence": "published on https://nutrabay.com/contact",
                "whatsapp_text": "Hi, this is Vineet. I run a cricket channel.",
                "instagram_dm": "Hi - Vineet here, I make cricket breakdowns.",
                "has_numbers": True}
        base.update(payload)
        return self.queue.create(thread_id="t", agent="sponsorship",
                                 kind="send_email",
                                 title=f"Email {base['to']}", payload=base)

    def test_the_card_shows_who_why_and_how_to_reach_them(self):
        row = self.queue.get(self._card())
        text = self.bot.approval_text(row)
        self.assertIn("Nutrabay", text)
        self.assertIn("nutrition", text)
        self.assertIn("hello@nutrabay.com", text)
        self.assertIn("Runs a creator programme", text)
        self.assertIn("published on", text, "the card must say where the "
                                            "address came from")
        self.assertIn("I run a cricket channel", text)

    def test_a_guessed_address_is_labelled_as_one(self):
        row = self.queue.get(self._card(
            to="marketing@nutrabay.com", guessed=True,
            evidence="not published on the site - standard address pattern"))
        text = self.bot.approval_text(row)
        self.assertIn("guessed", text.lower(),
                      "a guessed address must never look like a published one")

    def test_a_whatsapp_lead_shows_the_whatsapp_message_not_the_email(self):
        row = self.queue.get(self._card(
            channel="whatsapp", to="+919000011111",
            wa_link="https://wa.me/919000011111?text=Hi"))
        text = self.bot.approval_text(row)
        self.assertIn("WhatsApp", text)
        self.assertIn("+919000011111", text)
        self.assertIn("this is Vineet", text)

        rows = self.bot.approval_buttons(row["id"], row)["inline_keyboard"]
        flat = [b for r in rows for b in r]
        self.assertTrue(any("wa.me" in (b.get("url") or "") for b in flat),
                        "a WhatsApp lead needs a one-tap link to send it")

    def test_the_dm_version_is_one_tap_away(self):
        aid = self._card()
        rows = self.bot.approval_buttons(aid, self.queue.get(aid))["inline_keyboard"]
        flat = [b for r in rows for b in r]
        self.assertTrue(any(b.get("callback_data") == f"dm:{aid}" for b in flat))

    def test_asking_for_the_dm_does_not_decide_the_approval(self):
        aid = self._card()
        self.tap(f"dm:{aid}")
        self.bot.join_workers()
        self.assertEqual(self.queue.get(aid)["status"], "pending",
                         "reading the DM version must not count as approving it")
        self.assertIn("Instagram DM", self.all_text())

    def test_a_pitch_with_no_numbers_says_so_on_the_card(self):
        row = self.queue.get(self._card(has_numbers=False))
        text = self.bot.approval_text(row)
        self.assertIn("creator.yaml", text,
                      "if the pitch carries no figures, the card should say "
                      "why and how to fix it")


class TestSponsorshipCommands(BotCase):
    def test_brands_reports_the_pipeline(self):
        self.store.run(
            "INSERT INTO leads (id, agent, domain, company, email, status, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("l1", "sponsorship", "fantasy.example", "Example Fantasy",
             "a@b.example", "contacted", "2026-01-01T00:00:00Z",
             "2026-01-01T00:00:00Z"))
        self.store.run(
            "INSERT INTO leads (id, agent, domain, company, email, status, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("l2", "sponsorship", "noemail.example", "No Email Co", "",
             "ready_to_send", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        self.send("/brands")
        text = self.all_text()
        self.assertIn("Sponsorship pipeline", text)
        self.assertIn("No Email Co", text)
        self.assertIn("needs you to send", text)

    def test_mediakit_names_what_is_missing(self):
        self.send("/mediakit")
        text = self.all_text()
        self.assertIn("creator profile", text.lower())
        # the test fixture has numbers, so it should quote them back
        self.assertIn("12.5K", text)


class TestDealTypeOnCard(BotCase):
    def _card(self, deal):
        return self.queue.create(
            thread_id="t", agent="sponsorship", kind="send_email",
            title="Email x", payload={
                "company": "Nakpro", "domain": "nakpro.com",
                "segment": "nutrition", "tier": 1, "deal_type": deal,
                "channel": "email", "to": "hi@nakpro.com",
                "subject": "S", "body": "B", "has_numbers": True})

    def test_the_card_says_what_is_being_asked_for(self):
        # The wording is deliberately blunt: "join their affiliate programme"
        # and "send us free product" are very different decisions from "pay me
        # for a video", and the difference has to be readable on a phone.
        wanted = {
            "affiliate": "AFFILIATE PROGRAMME",
            "barter": "PRODUCT IN EXCHANGE FOR A VIDEO",
            "agency": "ROSTER",
            "cash": "PAY FOR A PROMOTION",
        }
        for deal, needle in wanted.items():
            text = self.bot.approval_text(self.queue.get(self._card(deal)))
            self.assertIn(needle, text,
                          f"a {deal} card should say so at the top")

    def test_an_unknown_deal_type_does_not_break_the_card(self):
        text = self.bot.approval_text(self.queue.get(self._card("wat")))
        self.assertIn("Nakpro", text)

    def test_brands_breaks_the_pipeline_down_by_deal(self):
        self.send("/brands")
        text = self.all_text()
        self.assertIn("by kind of deal", text)
        self.assertIn("product-for-video deals", text)


class TestHandoff(BotCase):
    """The messages the agent cannot send itself must reach you.

    A WhatsApp message, an enquiry form and an Instagram DM all need a human
    hand. They were being written to the terminal only, so approving a WhatsApp
    card from a phone produced silence and the message was never sent by
    anyone.
    """

    def setUp(self):
        super().setUp()
        self.send("/start")          # binds the chat, so say() has somewhere to go

    def _state(self, channel="whatsapp"):
        return {"handoff": [{
            "domain": "cricketcentral.in", "company": "Cricket Central",
            "channel": channel, "route": "+917204779337", "lead_id": "ld_1",
            "subject": "Cricket content partnership",
            "body": "The email version.",
            "whatsapp_text": "Cricket Central offers a wide range of gear. "
                             "Do you run creator partnerships?",
            "instagram_dm": "Saw your range. Do you do creator collabs?",
            "wa_link": "https://wa.me/917204779337?text=hi",
        }]}

    def test_a_whatsapp_handoff_is_posted_with_its_link(self):
        self.bot.post_handoffs(self._state(), "sponsorship")
        sent = self.all_text()
        self.assertIn("Ready to send", sent)
        self.assertIn("Cricket Central", sent)
        self.assertIn("creator partnerships", sent)
        self.assertIn("+917204779337", sent)
        buttons = str(self.fake.state.sent[-1])
        self.assertIn("wa.me", buttons)

    def test_the_whatsapp_wording_is_used_not_the_email_body(self):
        self.bot.post_handoffs(self._state(), "sponsorship")
        sent = self.fake.state.last_text()
        self.assertNotIn("The email version.", sent)

    def test_a_dm_handoff_uses_the_dm_wording(self):
        self.bot.post_handoffs(self._state(channel="social"), "sponsorship")
        self.assertIn("creator collabs", self.fake.state.last_text())

    def test_the_same_handoff_is_not_posted_twice(self):
        state = self._state()
        self.assertEqual(1, self.bot.post_handoffs(state, "sponsorship"))
        self.assertEqual(0, self.bot.post_handoffs(state, "sponsorship"))


class TestBothRoutesOnEveryCard(BotCase):
    """Mail and WhatsApp, on the same card, both one tap from sent."""

    def _card(self, **extra):
        payload = {"company": "Cricket Central", "domain": "cricketcentral.in",
                   "channel": "whatsapp", "to": "+917204779337",
                   "subject": "Cricket content partnership - Cricket Central",
                   "body": "Hi,\n\nYour site says you ship to 130 countries.",
                   "best_email": "hi@cricketcentral.in",
                   "best_phone": "+917204779337",
                   "wa_link": "https://wa.me/917204779337?text=hi",
                   "deal_type": "cash"}
        payload.update(extra)
        return self.queue.get(self.queue.create(
            thread_id="t", agent="sponsorship", kind="send_message",
            title="WhatsApp Cricket Central", payload=payload))

    def test_a_whatsapp_card_still_offers_the_email_route(self):
        row = self._card()
        buttons = str(self.bot.approval_buttons(row["id"], row))
        self.assertIn("Open in Gmail", buttons)
        self.assertIn("Open WhatsApp", buttons)
        # Gmail's compose URL, addressed and pre-written.
        self.assertIn("mail.google.com", buttons)
        self.assertIn("to=hi%40cricketcentral.in", buttons)
        self.assertIn("130%20countries", buttons)

    def test_the_card_names_the_route_it_did_not_pick(self):
        self.assertIn("hi@cricketcentral.in",
                      self.bot.brand_text(self._card()))

    def test_a_brand_with_only_an_email_gets_only_that_button(self):
        row = self._card(channel="email", to="hi@cricketcentral.in",
                         best_phone="", wa_link="")
        buttons = str(self.bot.approval_buttons(row["id"], row))
        self.assertIn("Open in Gmail", buttons)
        self.assertNotIn("Open WhatsApp", buttons)

    def test_telegram_only_ever_gets_https_button_links(self):
        # mailto: is rejected by Telegram with BUTTON_URL_INVALID, which would
        # make the whole card fail to post - not just the button.
        import re
        row = self._card()
        for url in re.findall(r"'url': '([^']+)'",
                              str(self.bot.approval_buttons(row["id"], row))):
            self.assertTrue(url.startswith("https://"), url)


class TestRunEndsOutLoud(BotCase):
    """Four cards out of forty brands is not a crash - but it looked like one."""

    def setUp(self):
        super().setUp()
        self.send("/start")

    def test_the_end_of_a_run_says_why_the_rest_got_no_card(self):
        state = {"summary": {"queued": 40, "contacted": 4},
                 "skipped": [{"domain": f"b{i}.in", "reason": "no contact published"}
                             for i in range(30)]
                          + [{"domain": "x.in", "reason": "site refused to load"}] * 6}
        text = self.bot.finished_text(state, "sponsorship")
        self.assertIn("36 passed over without a card", text)
        self.assertIn("no contact published", text)
        self.assertIn("site refused to load", text)


class TestStrandedCards(BotCase):
    """A card you never answered parks its whole run, permanently.

    Every /run started a new thread, so an unanswered card meant the previous
    run sat interrupted for good. Nine of them had built up in the database
    while the topic looked dead.
    """

    def setUp(self):
        super().setUp()
        self.send("/start")

    def _pending(self):
        return self.queue.create(
            thread_id="t-sponsorship", agent="sponsorship", kind="send_email",
            title="Email hi@brand.in at brand.in",
            payload={"company": "Brand", "to": "hi@brand.in", "channel": "email",
                     "subject": "S", "body": "B", "deal_type": "cash"})

    def test_run_reposts_the_open_card_instead_of_starting_over(self):
        self._pending()
        self.send("/run sponsorship")
        text = self.all_text()
        self.assertIn("still waiting on you", text)
        self.assertNotIn("Starting", text)

    def test_pending_reposts_everything_waiting(self):
        self._pending()
        self._pending()
        self.send("/pending")
        self.assertIn("2 waiting for your decision", self.all_text())

    def test_the_bot_says_on_startup_how_many_are_holding_up_a_run(self):
        self._pending()
        self.assertEqual(1, len(self.bot.pending_for("sponsorship")))
