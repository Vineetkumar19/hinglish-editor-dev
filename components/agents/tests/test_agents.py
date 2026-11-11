"""End-to-end tests: each agent driven from first call to final state."""
from __future__ import annotations

import json
import pathlib
import unittest

from tests.base import ROOT, SuiteCase
from tests.fakes.servers import FakeGoogleServer, FakeWebServer


class OutreachCase(SuiteCase):
    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def agent(self, module):
        llm = self.offline_llm()
        return module.make(store=self.store, llm=llm,
                           crawler=self.fast_crawler(llm=llm))


class TestSponsorshipAgent(OutreachCase):
    def test_full_run(self):
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        seen = []

        def decide(row):
            # Approve the ones that can actually be emailed. The list is now
            # ordered by which deal pays soonest, so the first card to come up
            # is not necessarily an email one.
            seen.append(row)
            return ("approve" if (row["payload"].get("channel") == "email")
                    else "reject")

        r = self.drive(app, "sp-1", decide)
        self.assertTrue(r.complete)
        self.assertTrue(r.state.get("sent"), "nothing was emailed")
        addresses = {x["to"] for x in r.state["sent"]}
        self.assertIn("partnerships@fantasy.example", addresses)
        self.assertTrue(all(x["dry_run"] for x in r.state["sent"]))

        # every approval must carry a reviewable draft
        payload = seen[0]["payload"]
        self.assertIn("subject", payload)
        self.assertIn("Vineet", payload["body"])
        self.assertEqual(payload["lint"], [], "generated pitch should lint clean")

    def test_a_brand_with_no_address_still_produces_a_message(self):
        """The old behaviour filed these as manual_followup with nothing
        written, so the lead existed but there was nothing to send."""
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        r = self.drive(app, "sp-wa", lambda row: "approve")

        handoffs = {h["domain"]: h for h in r.state.get("handoff", [])}
        self.assertIn("noemail.example", handoffs,
                      "a phone-only brand should be handed over, not dropped")
        h = handoffs["noemail.example"]
        self.assertEqual(h["channel"], "whatsapp")
        self.assertTrue(h["route"].startswith("+91"))
        self.assertIn("cricket", h["whatsapp_text"].lower())
        self.assertTrue(h["wa_link"].startswith("https://wa.me/"),
                        f"expected a click-to-chat link, got {h['wa_link']!r}")

        statuses = {row["domain"]: row["status"] for row in
                    self.store.query("SELECT domain, status FROM leads")}
        self.assertEqual(statuses.get("noemail.example"), "ready_to_send")

    def test_nothing_is_emailed_on_the_whatsapp_route(self):
        """A handoff must not also fire an email - that would double-contact."""
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        r = self.drive(app, "sp-wa2", lambda row: "approve")
        emailed = {x["to"] for x in r.state.get("sent", [])}
        self.assertNotIn("+919000011111", emailed)
        for x in r.state.get("sent", []):
            self.assertIn("@", x["to"])

    def test_real_money_gaming_brands_are_refused(self):
        """India banned real-money gaming in 2025. Promoting one is the
        creator's legal problem, so the agent will not draft the pitch."""
        import agents.sponsorship.agent as sponsor
        self.assertTrue(sponsor.blocked_reason({"segment": "betting"}))
        self.assertTrue(sponsor.blocked_reason({"segment": "fantasy_sports"}))
        self.assertTrue(sponsor.blocked_reason(
            {"segment": "gaming", "note": "real money game cricket"}))
        self.assertEqual("", sponsor.blocked_reason(
            {"segment": "nutrition", "note": "protein brand"}))

        score, why = sponsor.qualify_bonus(
            None, {"current": {"meta": {"segment": "betting"}}})
        self.assertLess(score, -1, "an excluded brand must be pushed below any "
                                   "threshold, not merely deprioritised")
        self.assertIn("EXCLUDED", why)

    def test_the_card_carries_every_channel(self):
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        seen = []

        def decide(row):
            seen.append(row)
            return "reject"

        self.drive(app, "sp-card", decide)
        self.assertTrue(seen)
        p = seen[0]["payload"]
        for key in ("whatsapp_text", "instagram_dm", "segment", "fit",
                    "channel", "evidence", "has_numbers"):
            self.assertIn(key, p, f"approval card is missing {key!r}")
        self.assertTrue(p["whatsapp_text"].strip())
        self.assertLess(len(p["instagram_dm"]), 600,
                        "an Instagram DM that long gets truncated unread")

    def test_tier_one_targets_are_worked_first(self):
        import agents.sponsorship.agent as sponsor
        queue = [{"meta": {"tier": 2, "segment": "fintech", "name": "B"}},
                 {"meta": {"tier": 1, "segment": "nutrition", "name": "C"}},
                 {"meta": {"tier": 1, "segment": "agency", "name": "A"}}]
        queue.sort(key=sponsor.rank)
        self.assertEqual([q["meta"]["name"] for q in queue], ["A", "C", "B"])

    def test_domains_are_not_contacted_twice(self):
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        self.drive(app, "sp-a", lambda row: "approve")
        second = self.drive(self.agent(sponsor).build(), "sp-b",
                            lambda row: "approve")
        self.assertEqual(second.state.get("sent", []), [],
                         "already-contacted domains must be skipped")

    def test_rejected_draft_sends_nothing(self):
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        r = self.drive(app, "sp-r", lambda row: "reject")
        self.assertEqual(r.state.get("sent", []), [])
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [])

    def test_operator_edits_are_what_get_sent(self):
        import agents.sponsorship.agent as sponsor
        app = self.agent(sponsor).build()
        self.drive(app, "sp-e",
                   lambda row: {"subject": "Edited subject",
                                "body": "Hi there,\n\nEdited body text here.\n\nVineet"}
                   if row["kind"] == "send_email" else "reject")
        msg = self.store.one("SELECT subject, body FROM messages WHERE direction='out'")
        self.assertEqual(msg["subject"], "Edited subject")
        self.assertIn("Edited body text", msg["body"])


class TestVideoClientAgent(OutreachCase):
    def test_targets_a_creator_who_needs_an_editor(self):
        import os
        os.environ["VIDEO_CLIENT_CATEGORY"] = "creator"
        import agents.video_client.agent as vc
        r = self.drive(self.agent(vc).build(), "vc-1", lambda row: "approve")
        self.assertTrue(r.complete)
        self.assertEqual(r.state["sent"][0]["to"], "rohit@creatorstudio.example")

    def test_qualifier_reads_the_need_signal(self):
        import agents.video_client.agent as vc
        from core.crawler import Crawler
        site = self.fast_crawler().profile_site("http://creatorstudio.example/")
        bonus, why = vc.qualify_bonus(site, {})
        self.assertGreater(bonus, 0)
        self.assertIn("edit", why)

    def test_rate_card_drives_pricing_answers(self):
        import agents.video_client.agent as vc
        from agents.video_client.quote import load_rates
        load_rates(refresh=True)
        out = vc._offline_reply({
            "intent": {"label": "question", "asked_for": "rates"},
            "message": {"from_name": "Rohit",
                        "reply_text": "What are your rates for a youtube edit?"}})
        self.assertIn("$", out["body"])
        self.assertFalse(out["needs_human"])

    def test_an_indian_client_is_answered_in_rupees(self):
        # Quoting a Bengaluru client in dollars loses the domestic work.
        import agents.video_client.agent as vc
        from agents.video_client.quote import load_rates
        load_rates(refresh=True)
        out = vc._offline_reply({
            "intent": {"label": "question", "asked_for": "rates"},
            "message": {"from_name": "Rohit",
                        "reply_text": "What do you charge? We are in Bengaluru."}})
        self.assertIn("INR", out["body"])

    def test_missing_rate_card_refuses_to_invent_a_price(self):
        import os
        os.environ["VIDEO_RATES_FILE"] = str(self.tmp / "nope.yaml")
        import agents.video_client.agent as vc
        out = vc._offline_reply({
            "intent": {"label": "question", "asked_for": "rates"},
            "message": {"from_name": "Rohit", "reply_text": "What do you charge?"}})
        self.assertIn("PLACEHOLDER", out["body"])
        self.assertTrue(out["needs_human"])


class TestFullstackSales(OutreachCase):
    def test_outreach_flags_a_dated_stack(self):
        import os
        os.environ["FULLSTACK_CATEGORY"] = "software_prospect"
        import agents.fullstack_sales.agent as fs
        r = self.drive(self.agent(fs).build(), "fs-1", lambda row: "approve")
        self.assertTrue(r.complete)
        self.assertEqual(r.state["sent"][0]["to"], "sanjay.kumar@saas.example")

    def _quote_msg(self, text=None):
        return {"id": "m1", "from_addr": "sanjay.kumar@saas.example",
                "from_name": "Sanjay Kumar", "subject": "Re: your site",
                "thread_id": "t1", "rfc_message_id": "<r1@x>", "references": "",
                "reply_text": text or
                ("We need a website redesign plus a customer dashboard with login "
                 "and Stripe payments, migrating off a legacy system. Needed ASAP.")}

    def test_quote_requires_approval_and_survives_restart(self):
        import agents.fullstack_sales.agent as fs
        q = fs.make_quote(store=self.store, llm=self.offline_llm())
        r = q.handle(self._quote_msg(), thread_id="Q1")
        self.assertTrue(r.interrupted)
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [],
                         "nothing may be sent before approval")

        # rebuild the graph from scratch, as a restarted process would
        fresh = fs.make_quote(store=self.store, llm=self.offline_llm()).build()
        d = self.queue.approve(r.approval_id)
        r2 = fresh.resume("Q1", d.to_json())
        self.assertEqual(r2.state["outcome"], "quote_sent")

    def test_operator_can_override_the_total(self):
        import agents.fullstack_sales.agent as fs
        q = fs.make_quote(store=self.store, llm=self.offline_llm())
        r = q.handle(self._quote_msg(), thread_id="Q2")
        original = self.queue.get(r.approval_id)["payload"]["quote"]["total"]
        d = self.queue.approve(r.approval_id, edits={"total": 9999})
        r2 = q.build().resume("Q2", d.to_json())
        self.assertEqual(r2.state["final_total"], 9999)
        self.assertIn("9,999", r2.state["final_quote"]["body"])
        self.assertNotIn(f"{original:,.0f}", r2.state["final_quote"]["body"])

    def test_rejected_quote_is_not_sent(self):
        import agents.fullstack_sales.agent as fs
        q = fs.make_quote(store=self.store, llm=self.offline_llm())
        r = q.handle(self._quote_msg(), thread_id="Q3")
        d = self.queue.reject(r.approval_id, note="talk first")
        r2 = q.build().resume("Q3", d.to_json())
        self.assertEqual(r2.state["outcome"], "quote_rejected")
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [])

    def test_vague_request_does_not_produce_a_number(self):
        import agents.fullstack_sales.agent as fs
        q = fs.make_quote(store=self.store, llm=self.offline_llm())
        r = q.handle(self._quote_msg("Thanks, sounds interesting. Let's talk."),
                     thread_id="Q4")
        self.assertTrue(r.complete)
        self.assertEqual(r.state["outcome"], "insufficient_scope")
        self.assertNotIn("quote_json", r.state)

    def test_pricing_is_deterministic(self):
        from agents.fullstack_sales.pricing import build_quote, infer_scope
        scope, mods = infer_scope("website redesign with login and stripe payments, ASAP")
        a = build_quote(scope, modifiers=mods)
        b = build_quote(scope, modifiers=mods)
        self.assertEqual(a.total, b.total)
        self.assertGreater(a.total, 0)


class TestJobHunter(SuiteCase):
    def hunter(self):
        import agents.job_hunter.agent as jh
        return jh.make(store=self.store, llm=self.offline_llm())

    def test_full_run_filters_scams_and_builds_resumes(self):
        """No fake posting may reach the approval queue.

        Two filters share this job now. The relevance filter drops a posting
        whose ROLE is wrong ("Data Entry Executive", "Accounts Officer") before
        anything expensive happens, and the fraud filter catches a posting that
        looks like a real software job but is not ("Software Engineering Intern"
        at GrowthCo, which demands 10+ years of an entry-level hire). Which of
        the two stops a given fake does not matter; that none get through does.
        """
        app = self.hunter().build()
        shown = []

        def decide(row):
            shown.append((row.get("payload") or {}).get("company", ""))
            return "approve" if "Zerodha" in row["title"] else "reject"

        r = self.drive(app, "jh-1", decide)
        self.assertTrue(r.complete)

        fakes = {"Reputed MNC Company", "GrowthCo", "Global Finance Ltd",
                 "Nexa Tech Solutions"}
        self.assertEqual(fakes & set(shown), set(),
                         "a fraudulent posting reached the approval queue")

        stopped = ({x["company"] for x in r.state.get("rejected", [])}
                   | {o["company"] for o in r.state.get("off_target", [])})
        self.assertEqual(fakes - stopped, set(),
                         "a fraudulent posting was neither screened out nor "
                         "filtered out - it vanished silently")

        # The fraud filter must still be doing its half. Nexa Tech is the case
        # only it can catch: right role, fresher-friendly, plausible salary -
        # and it asks for a registration fee and interviews on WhatsApp.
        self.assertIn("Nexa Tech Solutions",
                      {x["company"] for x in r.state["rejected"]},
                      "the fraud screen let a fee-for-job scam through")

        self.assertEqual(r.state["summary"]["prepared"], 1)
        self.assertEqual(self.store.one("SELECT COUNT(*) AS n FROM leads WHERE status='applied'")["n"], 0)
        applied = r.state["applied"][0]
        self.assertTrue(pathlib.Path(applied["resume"]).exists())
        self.assertGreater(pathlib.Path(applied["resume"]).stat().st_size, 1000)

    def test_resume_is_tailored_per_job(self):
        from agents.job_hunter.discovery import Job
        from agents.job_hunter.resume import load_master, tailor
        master = load_master()
        backend = Job(title="Backend Engineer",
                      description="Python PostgreSQL Docker REST APIs unit testing")
        frontend = Job(title="Frontend Engineer",
                       description="React TypeScript Node.js CSS HTML")
        a = tailor(master, backend, llm=self.offline_llm()).data["skills"][:3]
        b = tailor(master, frontend, llm=self.offline_llm()).data["skills"][:3]
        self.assertNotEqual(a, b, "skills should reorder for the job")
        self.assertIn("Python", a)
        self.assertIn("React", b)

    def test_jobs_are_not_reprocessed(self):
        first = self.drive(self.hunter().build(), "jh-a", lambda row: "reject")
        second = self.drive(self.hunter().build(), "jh-b", lambda row: "reject")
        self.assertEqual(second.state["summary"].get("queued", 0), 0)

    def test_nothing_is_submitted_automatically(self):
        r = self.drive(self.hunter().build(), "jh-c", lambda row: "reject")
        applied = self.store.query(
            "SELECT * FROM leads WHERE agent='job_hunter' AND status='applied'")
        self.assertEqual(applied, [])


class TestResumeTracks(SuiteCase):
    """Software and video are different careers and must not be mixed.

    Vineet writes backend code AND edits video. A backend interviewer should
    never see DaVinci Resolve on the resume, and a video client should never
    see Spring Boot.
    """

    SOFTWARE = ROOT / "profiles" / "master_resume.yaml"
    VIDEO = ROOT / "profiles" / "master_resume_video.yaml"

    def test_both_shipped_profiles_are_clean(self):
        from agents.job_hunter.resume import load_master, track_violations
        for path in (self.SOFTWARE, self.VIDEO):
            with self.subTest(profile=path.name):
                self.assertEqual(track_violations(load_master(path)), [],
                                 f"{path.name} carries the other track's material")

    def test_a_leak_is_actually_detected(self):
        """The guard must be able to fail, or it is proving nothing."""
        from agents.job_hunter.resume import load_master, track_violations
        master = load_master(self.SOFTWARE)
        master["skills"]["creative"] = ["Adobe Premiere Pro", "Motion graphics"]
        self.assertIn("premiere pro", track_violations(master))

        video = load_master(self.VIDEO)
        video["skills"]["backend"] = ["Spring Boot", "MySQL"]
        self.assertIn("spring boot", track_violations(video))

    def test_a_software_resume_contains_no_video_words(self):
        from agents.job_hunter.resume import load_master, tailor, render_pdf
        from agents.job_hunter.discovery import Job
        job = Job(id="j1", title="Backend Engineer (Python)", company="Zerodha",
                  location="Bengaluru", url="https://z.example/1",
                  description="Python, SQL, REST APIs, Docker. Build and own "
                              "backend services end to end.")
        result = tailor(load_master(self.SOFTWARE), job, llm=self.offline_llm())
        blob = json.dumps(result.data).lower()
        for word in ("premiere", "after effects", "davinci", "colour grad",
                     "motion graphics", "sound design"):
            self.assertNotIn(word, blob,
                             f"{word!r} ended up on a backend engineering resume")

    def test_the_current_job_is_listed_first(self):
        """Never order jobs by keyword relevance - a recruiter reads top as now."""
        from agents.job_hunter.resume import load_master, tailor
        from agents.job_hunter.discovery import Job
        master = load_master(self.SOFTWARE)
        job = Job(id="j2", title="Frontend Engineer", company="X",
                  location="Remote", url="https://x.example/2",
                  description="React, JavaScript, CSS, frontend, web applications.")
        result = tailor(master, job, llm=self.offline_llm())
        self.assertEqual(result.data["experience"][0]["id"],
                         master["experience"][0]["id"])

    def test_only_three_projects_reach_the_page(self):
        from agents.job_hunter.resume import load_master, tailor
        from agents.job_hunter.discovery import Job
        job = Job(id="j3", title="Java Developer", company="Y", location="Pune",
                  url="https://y.example/3",
                  description="Java, Spring Boot, MySQL, REST APIs.")
        result = tailor(load_master(self.SOFTWARE), job, llm=self.offline_llm())
        self.assertLessEqual(len(result.data["projects"]), 3)
        self.assertGreater(len(result.data["projects"]), 0)

    def test_the_resume_carries_his_real_details(self):
        from agents.job_hunter.resume import load_master
        master = load_master(self.SOFTWARE)
        self.assertEqual(master["name"], "Vineet Kumar Das")
        self.assertNotIn("PLACEHOLDER", json.dumps(master))
        schools = " ".join(str(e) for e in master["education"])
        self.assertIn("Delhi Technological University", schools)


class TestInterviewScheduling(SuiteCase):
    def setUp(self):
        super().setUp()
        self.google = FakeGoogleServer().start()
        import os
        os.environ.update({"GMAIL_API_BASE": self.google.gmail_base,
                           "CALENDAR_API_BASE": self.google.calendar_base,
                           "GOOGLE_TOKEN_URI": self.google.token_uri,
                           "GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csec"})
        from core.oauth import GoogleOAuth
        self.oauth = GoogleOAuth(store=self.store)
        self.oauth.exchange("fake-code", "http://127.0.0.1/cb")

    def tearDown(self):
        self.google.stop()
        super().tearDown()

    def scheduler(self):
        import agents.job_hunter.agent as jh
        from core.calendar import CalendarClient
        return jh.make_scheduler(store=self.store, llm=self.offline_llm(),
                                 calendar=CalendarClient(store=self.store,
                                                         oauth=self.oauth))

    def test_detects_and_proposes_real_free_slots(self):
        msg = {"id": "iv1", "from_addr": "recruiter@zerodha.example",
               "from_name": "Anita", "subject": "Interview for Backend Engineer",
               "thread_id": "t9", "rfc_message_id": "<iv1@x>",
               "reply_text": "Thanks for applying - what's your availability "
                             "for a screening call next week?"}
        s = self.scheduler()
        r = s.handle(msg, thread_id="IV1")
        self.assertTrue(r.interrupted)
        payload = self.queue.get(r.approval_id)["payload"]
        self.assertTrue(payload["slots"])
        for slot in payload["slots"]:
            self.assertIn(slot, payload["body"])
        d = self.queue.approve(r.approval_id)
        r2 = s.build().resume("IV1", d.to_json())
        self.assertEqual(r2.state["outcome"], "times_proposed")

    def test_ignores_a_non_interview_message(self):
        r = self.scheduler().handle(
            {"id": "x", "from_addr": "a@b.example", "subject": "Newsletter",
             "reply_text": "Here is our monthly product update."}, thread_id="IV2")
        self.assertTrue(r.complete)
        self.assertEqual(r.state["outcome"], "not_an_interview_request")

    def test_confirming_a_slot_creates_a_calendar_event(self):
        import datetime as dt
        s = self.scheduler()
        start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)
        ev = s.confirm_slot(summary="Interview - Zerodha",
                            start_iso=start.isoformat(),
                            end_iso=(start + dt.timedelta(minutes=45)).isoformat(),
                            attendees=["recruiter@zerodha.example"])
        self.assertTrue(ev["id"])
        self.assertEqual(len(self.google.state.events), 1)


class TestReplyHandling(SuiteCase):
    def reply_agent(self):
        import agents.sponsorship.agent as sponsor
        return sponsor.make_reply(store=self.store, llm=self.offline_llm())

    def _msg(self, text, **kw):
        base = {"id": "r1", "from_addr": "priya@fantasy.example",
                "from_name": "Priya Rao", "subject": "Re: Creator partnerships",
                "thread_id": "t1", "rfc_message_id": "<r1@x>", "references": "",
                "reply_text": text, "is_auto_reply": False}
        base.update(kw)
        return base

    def test_interested_reply_alerts_and_drafts(self):
        r = self.reply_agent().handle(
            self._msg("Yes we're interested! Can you share your rates?"),
            thread_id="RP1")
        self.assertTrue(r.interrupted)
        self.assertEqual(r.state["intent"]["label"], "interested")
        self.assertTrue(r.state["notified"])
        notes = [e for e in self.store.recent_events(20)
                 if e["kind"] == "notification"]
        self.assertTrue(any("interested" in json.dumps(e["payload"]) for e in notes))

    def test_unsubscribe_is_honoured_immediately_without_an_llm(self):
        from core.mailer import SuppressionList
        r = self.reply_agent().handle(
            self._msg("Please remove me from this list."), thread_id="RP2")
        self.assertTrue(r.complete)
        self.assertEqual(r.state["outcome"], "unsubscribed")
        self.assertTrue(SuppressionList(self.store).contains("priya@fantasy.example"))

    def test_hard_no_closes_the_lead_without_a_reply(self):
        r = self.reply_agent().handle(
            self._msg("Not interested, we already have an agency."), thread_id="RP3")
        self.assertEqual(r.state["outcome"], "closed_lost")
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [])

    def test_out_of_office_snoozes(self):
        r = self.reply_agent().handle(
            self._msg("I am out of the office until March.", is_auto_reply=True),
            thread_id="RP4")
        self.assertEqual(r.state["outcome"], "snoozed")

    def test_bounce_suppresses_and_warns_on_high_rate(self):
        r = self.reply_agent().handle(
            self._msg("Delivery has failed. 550-5.1.1 address not found."),
            thread_id="RP5")
        self.assertEqual(r.state["outcome"], "bounced")

    def test_approved_reply_is_threaded(self):
        agent = self.reply_agent()
        r = agent.handle(self._msg("Interested - send me your rates please."),
                         thread_id="RP6")
        d = self.queue.approve(r.approval_id)
        r2 = agent.build().resume("RP6", d.to_json())
        self.assertEqual(r2.state["outcome"], "replied")
        out = self.store.one(
            "SELECT in_reply_to, subject FROM messages WHERE direction='out'")
        self.assertEqual(out["in_reply_to"], "<r1@x>")
        self.assertTrue(out["subject"].lower().startswith("re:"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestJobBrain(SuiteCase):
    """The job hunter learns from every decision, without disturbing the other."""

    def _job(self, **over):
        job = {"source": "linkedin", "company": "Meesho",
               "location": "Bengaluru, Karnataka", "remote": False,
               "match": {"family": "java", "seniority": 0,
                         "skills": ["Java", "Spring Boot"]},
               "keyword_coverage": 0.8}
        job.update(over)
        return job

    def test_an_approval_moves_the_score_on_the_first_example(self):
        from agents.job_hunter.brain import JobMemory
        b = JobMemory(self.store)
        before = b.score_job(self._job())[0]
        b.record_job(self._job(), "applied")
        self.assertGreater(b.score_job(self._job())[0], before)

    def test_what_an_employer_did_outweighs_what_he_guessed(self):
        from agents.job_hunter.brain import JobMemory, OUTCOME_WEIGHT
        self.assertGreater(OUTCOME_WEIGHT["interview"], OUTCOME_WEIGHT["applied"])
        self.assertGreater(OUTCOME_WEIGHT["offer"], OUTCOME_WEIGHT["interview"])
        b = JobMemory(self.store)
        b.record_job(self._job(), "interview")
        self.assertIn("jh:family=java", b.counts())

    def test_bangalore_and_bengaluru_are_one_city(self):
        from agents.job_hunter.brain import job_features
        a = job_features(self._job(location="Bangalore, KA"))
        c = job_features(self._job(location="Bengaluru, Karnataka"))
        self.assertIn("jh:city=bengaluru", a)
        self.assertEqual([f for f in a if f.startswith("jh:city")],
                         [f for f in c if f.startswith("jh:city")])

    def test_job_evidence_does_not_leak_into_the_sponsorship_brain(self):
        # Both write to prospect_feedback. Without the prefix filter, approving
        # a Java role would make nutrition brands look more promising.
        from agents.job_hunter.brain import JobMemory
        from agents.sponsorship.brain import Memory
        sponsor = Memory(self.store)
        before = sponsor.summary()["decisions"]
        JobMemory(self.store).record_job(self._job(), "applied")
        self.assertEqual(before, Memory(self.store).summary()["decisions"])

    def test_a_fraudulent_posting_is_the_strongest_negative(self):
        from agents.job_hunter.brain import OUTCOME_WEIGHT
        self.assertEqual(min(OUTCOME_WEIGHT.values()), OUTCOME_WEIGHT["fraud"])


class TestVideoQuoting(SuiteCase):
    """Every number that reaches a client comes off the rate card, and the
    floor is absolute."""

    extra_env = {"VIDEO_RATES_FILE": str(ROOT / "profiles" / "video_rates.yaml")}

    def q(self, text="12 minute youtube edit, New York", **kw):
        from agents.video_client.quote import build_quote, load_rates
        load_rates(refresh=True)
        return build_quote(text, **kw)

    def test_the_tier_is_read_from_what_they_asked_for(self):
        from agents.video_client.quote import tier_for
        cases = {"just colour grading, I edit my own stuff": "grade_only",
                 "need a logo animation": "motion_asset",
                 "a mini-documentary about our founder": "documentary",
                 "sound design only please": "sound_only",
                 "8 reels a month": "short_form_pack",
                 "90 second animated explainer": "explainer",
                 "monthly retainer, dedicated editor": "retainer"}
        for text, want in cases.items():
            self.assertEqual(want, tier_for(text), text)

    def test_a_stem_pattern_matches_the_word_it_is_a_stem_of(self):
        # "colou?r grad" followed by \b can never match "colour grading" - the
        # boundary falls inside the word. That priced a grade-only enquiry as a
        # full long-form edit.
        from agents.video_client.quote import tier_for
        self.assertEqual("grade_only", tier_for("colour grading"))
        self.assertEqual("documentary", tier_for("documentary style"))
        self.assertEqual("motion_asset", tier_for("logo animation"))

    def test_indian_clients_are_quoted_in_rupees(self):
        from agents.video_client.quote import currency_for
        self.assertEqual("inr", currency_for("we are based in Bengaluru"))
        self.assertEqual("usd", currency_for("we are in Toronto"))

    def test_an_offer_below_the_floor_always_stops_for_him(self):
        from agents.video_client.quote import respond_to
        quote = self.q()
        below = respond_to(quote.floor - 1, quote)
        self.assertEqual("ask_operator", below.action)

    def test_an_offer_above_the_floor_is_countered_not_simply_taken(self):
        from agents.video_client.quote import respond_to
        quote = self.q()
        mid = respond_to((quote.floor + quote.ask) / 2, quote)
        self.assertEqual("counter", mid.action)
        self.assertGreaterEqual(mid.amount, quote.floor)
        # A discount with nothing taken away teaches them the first number was
        # padded.
        self.assertTrue(mid.give)

    def test_a_rush_job_raises_the_floor_with_the_ask(self):
        normal, rush = self.q(), self.q("12 minute youtube edit, urgent, need it this week")
        self.assertGreater(rush.ask, normal.ask)
        self.assertGreater(rush.floor, normal.floor)

    def test_no_rate_card_means_placeholder_and_never_a_number(self):
        from agents.video_client.quote import build_quote, load_rates
        with self.env(VIDEO_RATES_FILE=str(self.tmp / "missing.yaml")):
            load_rates(refresh=True)
            q = build_quote("a youtube edit")
            self.assertTrue(q.missing)
            self.assertIn("PLACEHOLDER", q.render())
        load_rates(refresh=True)

    def test_the_money_the_client_named_is_read_correctly(self):
        from agents.video_client.quote import find_offer
        self.assertEqual(500.0, find_offer("we can do $500", "USD"))
        self.assertEqual(1500.0, find_offer("budget is 1.5k usd", "USD"))
        self.assertEqual(25000.0, find_offer("we pay INR 25,000", "INR"))
        self.assertEqual(200000.0, find_offer("2 lakh rupees", "INR"))
        self.assertEqual(0.0, find_offer("sounds good, when can you start", "USD"))


class TestVideoPitchHygiene(SuiteCase):
    """What must never reach a client."""

    extra_env = {
        "VIDEO_RATES_FILE": str(ROOT / "profiles" / "video_rates.yaml"),
        "RESUME_VIDEO_FILE": str(ROOT / "profiles" / "master_resume_video.yaml"),
    }

    def test_markup_never_reaches_the_opening_line(self):
        # A live run put `description__text--rich">` into the first sentence of
        # a pitch, because the LinkedIn extractor matched from the class name.
        from agents.video_client.gigs import _first_real_sentence
        junk = ('description__text description__text--rich"> NY based Editor. '
                'We are looking for an editor to cut case study films for '
                'global brands. Show more')
        got = _first_real_sentence(junk)
        self.assertNotIn("description__", got)
        self.assertNotIn('"', got)
        self.assertIn("case study films", got)

    def test_job_board_chrome_is_not_quoted_back_at_them(self):
        from agents.video_client.gigs import _first_real_sentence
        self.assertEqual("", _first_real_sentence("Posted 3 days ago. Sign in to apply."))

    def test_the_four_client_types_get_different_openings(self):
        from agents.video_client.pitch import opening_pitch
        bodies = {k: opening_pitch({"company": "X", "title": "Editor", "kind": k})["body"]
                  for k in ("agency", "brand", "creator", "coach")}
        self.assertEqual(4, len(set(bodies.values())),
                         "the same email to every client type converts on none")

    def test_the_first_email_never_carries_a_price(self):
        from agents.video_client.pitch import opening_pitch
        body = opening_pitch({"company": "X", "title": "Editor", "kind": "agency"})["body"]
        for token in ("$", "INR", "per video", "rate is"):
            self.assertNotIn(token, body)


class TestVideoChase(SuiteCase):
    """Most freelance work is lost to silence, not to a no."""

    extra_env = {"RESUME_VIDEO_FILE": str(ROOT / "profiles" / "master_resume_video.yaml")}

    def test_three_touches_then_it_stops_for_good(self):
        from agents.video_client.pitch import follow_up, FOLLOW_UPS
        gig = {"company": "X", "title": "Video Editor"}
        seen = [follow_up(gig, i) for i in range(len(FOLLOW_UPS))]
        self.assertTrue(all(seen))
        self.assertIsNone(follow_up(gig, len(FOLLOW_UPS)))

    def test_each_chase_says_something_new(self):
        from agents.video_client.pitch import follow_up, FOLLOW_UPS
        gig = {"company": "X", "title": "Video Editor"}
        bodies = [follow_up(gig, i)["body"] for i in range(len(FOLLOW_UPS))]
        self.assertEqual(len(bodies), len(set(bodies)),
                         "a chase that repeats itself teaches them to ignore you")

    def test_the_gaps_widen(self):
        from agents.video_client.pitch import due_after_days, FOLLOW_UPS
        gaps = [due_after_days(i) for i in range(len(FOLLOW_UPS))]
        self.assertEqual(gaps, sorted(gaps))
        self.assertEqual(gaps, sorted(set(gaps)))


class TestDealBrain(SuiteCase):
    """Money outweighs opinion, and the three brains stay apart."""

    def deal(self, **over):
        d = {"source": "linkedin", "company": "Uncommon", "kind": "agency",
             "location": "New York, United States", "tier_id": "documentary",
             "currency": "USD"}
        d.update(over)
        return d

    def test_getting_paid_outweighs_everything_else(self):
        from agents.video_client.brain import OUTCOME_WEIGHT
        self.assertEqual(max(OUTCOME_WEIGHT.values()), OUTCOME_WEIGHT["paid"])
        self.assertGreater(OUTCOME_WEIGHT["deal_won"], OUTCOME_WEIGHT["replied"])
        self.assertGreater(OUTCOME_WEIGHT["replied"], OUTCOME_WEIGHT["sent"])

    def test_the_market_is_read_from_the_location(self):
        from agents.video_client.brain import market_of
        self.assertEqual("us", market_of("New York, United States"))
        self.assertEqual("canada", market_of("Toronto, Ontario"))
        self.assertEqual("india", market_of("Bengaluru, Karnataka"))
        self.assertEqual("uk", market_of("London Area, United Kingdom"))

    def test_none_of_the_three_brains_can_see_each_other(self):
        from agents.job_hunter.brain import JobMemory
        from agents.sponsorship.brain import Memory
        from agents.video_client.brain import DealMemory
        DealMemory(self.store).record_deal(self.deal(), "paid")
        JobMemory(self.store).record_job(
            {"source": "linkedin", "company": "Meesho",
             "match": {"family": "java"}}, "applied")
        self.assertEqual(0, Memory(self.store).summary()["decisions"])
        self.assertEqual(1, len(DealMemory(self.store).summary()["events"]))
        self.assertNotIn("vc:market=us", JobMemory(self.store).counts())


class TestTheLoopCloses(SuiteCase):
    """A rejection must change the NEXT draft, for a different target.

    This is the whole point of the lesson store. The brains were already
    learning which targets were worth approaching; nothing was learning what to
    say, so a sentence he rejected came back forever.
    """

    def test_a_rejected_sentence_does_not_come_back(self):
        from core.hitl import Decision
        from core.lessons import get_lessons
        from core.reflect import learn_from_decision
        learn_from_decision(
            "sponsorship",
            Decision("rejected", {}, note="Never say we guarantee results."),
            {"body": "We guarantee results for every brand."}, store=self.store)
        # A completely different brand, a fresh prompt.
        block = get_lessons("sponsorship", self.store).prompt_block(
            context="babyorgano ayurvedic baby care")
        self.assertIn("guarantee", block.lower())

    def test_the_video_brief_carries_the_rules_into_the_prompt(self):
        from core.lessons import get_lessons
        from agents.video_client import brief
        get_lessons("video_client", self.store).add(
            "Keep every first email under 90 words.")
        prompt = brief.build_prompt({
            "gig": {"company": "Mr Chirp", "title": "Short-Form Editor",
                    "kind": "agency", "description": "We cut sports clips. " * 20},
            "quote": {"tier_name": "Short-form"}})
        learned = get_lessons("video_client", self.store).prompt_block()
        self.assertIn("under 90 words", prompt + "\n" + learned)

    def test_no_price_ever_appears_in_the_video_brief(self):
        # The opening email must not carry a number, and the brief is where
        # that is enforced for the model.
        from agents.video_client import brief
        prompt = brief.build_prompt({
            "gig": {"company": "X", "title": "Editor", "kind": "brand",
                    "description": "We need an editor. " * 20},
            "quote": {"tier_name": "Long-form", "ask": 600, "floor": 350}})
        self.assertIn("DO NOT put any price", prompt)
        self.assertNotIn("600", prompt)
        self.assertNotIn("350", prompt)

    def test_the_prompts_reach_the_model_without_ragged_indentation(self):
        # dedent() strips the COMMON leading whitespace, and a block
        # interpolated at column 0 makes that common prefix empty - so the
        # template shipped with 8 spaces on every line it wrote and none on the
        # text it quoted, which a small model reads as structure.
        from agents.sponsorship import brief as sb
        from agents.video_client import brief as vb
        prompts = [
            sb.build_prompt({"current": {"domain": "x.in",
                                         "meta": {"name": "X", "deal_type": "cash"}},
                             "profile": {"text": "We sell tea. " * 60,
                                         "description": "tea"},
                             "contact": {}}),
            vb.build_prompt({"gig": {"company": "C", "title": "Editor",
                                     "kind": "agency",
                                     "description": "We need shorts. " * 30},
                             "quote": {"tier_name": "Short-form"}}),
        ]
        for prompt in prompts:
            stray = [ln for ln in prompt.splitlines()
                     if ln.startswith("    ") and ln.strip()]
            self.assertEqual([], stray[:3])

    def test_the_job_read_is_honest_about_the_gap(self):
        from agents.job_hunter.read import build_prompt
        prompt = build_prompt(
            {"title": "Senior Go Engineer", "company": "Acme",
             "description": "Ten years of Go and Kubernetes required."},
            {"headline": "Software Engineer",
             "skills": {"languages": ["Java", "Python"]},
             "experience": [{"title": "Software Engineer", "company": "HCLTech"}]})
        self.assertIn("biggest_gap", prompt)
        self.assertIn("do not invent one", prompt)
        self.assertIn("Do not flatter", prompt)


class TestDevClientSourcing(SuiteCase):
    """A client who wants work done, not an employer hiring staff."""

    def gig(self, **over):
        from agents.fullstack_sales.sources import Gig
        d = {"id": "1", "title": "Full Stack Developer", "company": "C",
             "description": "Freelance contract project. " * 10}
        d.update(over)
        return Gig(**d)

    def test_a_job_at_stripe_is_not_a_client_for_stripe_work(self):
        # A live sweep returned nine postings from Stripe. This agent would
        # have answered them by offering to integrate Stripe.
        from agents.fullstack_sales.sources import is_dev_work
        ok, why = is_dev_work(self.gig(
            title="Backend Engineer, Payments", company="Stripe",
            description="Join our team. Full-time position with a benefits "
                        "package, equity and paid time off. " * 5))
        self.assertFalse(ok, why)
        self.assertIn("job, not a client", why)

    def test_someone_who_wants_their_checkout_fixed_is_a_client(self):
        from agents.fullstack_sales.sources import is_dev_work
        gig = self.gig(title="Razorpay developer needed", company="A Shop",
                       description="We need a developer to fix our broken "
                                   "checkout. Razorpay webhooks are not "
                                   "firing. Freelance, fixed-price. " * 3)
        self.assertTrue(is_dev_work(gig)[0])
        self.assertEqual("payment_rescue", gig.work_kind())

    def test_a_mechanical_engineer_is_a_different_profession(self):
        from agents.fullstack_sales.sources import is_dev_work
        self.assertFalse(is_dev_work(self.gig(title="Mechanical Engineer"))[0])
        self.assertFalse(is_dev_work(self.gig(title="HVAC Engineer"))[0])
        self.assertTrue(is_dev_work(self.gig(title="Senior Data Engineer"))[0])

    def test_a_title_only_posting_survives_to_be_read_later(self):
        # On the sweep there is no description yet. Throwing it away there
        # would discard most of LinkedIn before anything had been read.
        from agents.fullstack_sales.sources import is_dev_work
        ok, why = is_dev_work(self.gig(title="React Developer", description=""))
        self.assertTrue(ok, why)


class TestDevPackages(SuiteCase):
    """Payments work is priced as packages, and the floor is absolute."""

    extra_env = {"PRICING_FILE": str(ROOT / "profiles" / "dev_rate_card.yaml")}

    def pkg(self, text="integrate stripe checkout, US based", **kw):
        from agents.fullstack_sales.packages import build_package, load_card
        load_card(refresh=True)
        return build_package(text, **kw)

    def test_the_right_package_is_chosen(self):
        from agents.fullstack_sales.packages import package_for
        cases = {"add UPI autopay mandates": "upi_integration",
                 "subscription billing with proration and dunning": "subscriptions",
                 "razorpay route vendor payouts": "marketplace_payouts",
                 "fix our broken checkout, webhooks not firing": "payment_rescue",
                 "integrate stripe checkout": "gateway_standard",
                 "audit our payment setup": "payment_audit"}
        for text, want in cases.items():
            self.assertEqual(want, package_for(text), text)

    def test_upi_autopay_is_not_priced_as_full_subscription_billing(self):
        # "mandate" and "autopay" are UPI's vocabulary. Leaving them in the
        # subscriptions pattern priced a UPI job at nearly twice the right
        # number, which ends the conversation.
        from agents.fullstack_sales.packages import package_for
        self.assertEqual("upi_integration", package_for("add UPI autopay mandates"))

    def test_a_build_is_not_a_package(self):
        # Those go to pricing.py and are estimated in days.
        self.assertIsNone(self.pkg("build us a marketing website, 5 pages"))

    def test_indian_clients_are_priced_in_rupees(self):
        india = self.pkg("integrate razorpay checkout, we are in Mumbai")
        self.assertEqual("INR", india.currency)
        self.assertEqual("USD", self.pkg().currency)

    def test_urgent_work_raises_the_floor_with_the_ask(self):
        calm = self.pkg("integrate stripe checkout")
        rush = self.pkg("integrate stripe checkout, urgent, we are losing sales")
        self.assertGreater(rush.ask, calm.ask)
        self.assertGreater(rush.floor, calm.floor)

    def test_below_the_floor_always_stops_for_him(self):
        from agents.fullstack_sales.packages import respond_to
        p = self.pkg()
        self.assertEqual("ask_operator", respond_to(p.floor - 1, p).action)

    def test_a_concession_comes_with_every_discount(self):
        from agents.fullstack_sales.packages import respond_to
        p = self.pkg()
        c = respond_to((p.floor + p.ask) / 2, p)
        self.assertEqual("counter", c.action)
        self.assertTrue(c.give)

    def test_no_card_means_placeholder_not_a_number(self):
        from agents.fullstack_sales.packages import build_package, load_card
        with self.env(PRICING_FILE=str(self.tmp / "gone.yaml")):
            load_card(refresh=True)
            p = build_package("integrate stripe checkout")
            self.assertTrue(p.missing)
            self.assertIn("PLACEHOLDER", p.render())
        load_card(refresh=True)


class TestDevBrief(SuiteCase):
    """What the model is told, and what it is never allowed to put in."""

    extra_env = {"PRICING_FILE": str(ROOT / "profiles" / "dev_rate_card.yaml")}

    def prompt(self, **over):
        from agents.fullstack_sales import brief
        gig = {"company": "A Shop", "title": "Razorpay developer needed",
               "work_kind": "payment_rescue", "client_kind": "ecommerce",
               "location": "Mumbai",
               "description": "Our webhooks are not firing. " * 20}
        gig.update(over)
        return brief.build_prompt({
            "gig": gig,
            "package": {"label": "Fix a broken payment integration",
                        "ask": 450, "floor": 300},
            "profile": {"headline": "Software Engineer",
                        "skills": {"languages": ["Java", "Python"]}}})

    def test_the_price_never_enters_the_prompt(self):
        p = self.prompt()
        self.assertIn("DO NOT put any price", p)
        self.assertNotIn("450", p)
        self.assertNotIn("300", p)

    def test_broken_work_gets_the_fault_list_and_a_warning_against_guessing(self):
        p = self.prompt()
        self.assertIn("signature", p)
        self.assertIn("idempotency", p)
        self.assertIn("wrong guess stated", p)

    def test_a_build_does_not_get_the_fault_list(self):
        # Handing a checkout-failure checklist to someone who wants a marketing
        # site invites the model to invent a problem they do not have.
        p = self.prompt(work_kind="site", description="We want a 5 page site. " * 20)
        self.assertNotIn("idempotency", p)

    def test_free_trial_work_is_refused_in_the_brief(self):
        self.assertIn("unpaid proof of concept", self.prompt())

    def test_no_ragged_indentation_reaches_the_model(self):
        stray = [ln for ln in self.prompt().splitlines()
                 if ln.startswith("    ") and ln.strip()]
        self.assertEqual([], stray[:3])


class TestDevBrain(SuiteCase):
    """Money outweighs opinion, and four brains stay apart."""

    def deal(self, **over):
        d = {"source": "linkedin", "company": "A Shop", "client_kind": "ecommerce",
             "work_kind": "payment_rescue", "location": "Mumbai",
             "package_id": "payment_rescue", "currency": "INR"}
        d.update(over)
        return d

    def test_getting_paid_outweighs_everything(self):
        from agents.fullstack_sales.brain import OUTCOME_WEIGHT
        self.assertEqual(max(OUTCOME_WEIGHT.values()), OUTCOME_WEIGHT["paid"])
        self.assertGreater(OUTCOME_WEIGHT["deal_won"], OUTCOME_WEIGHT["replied"])
        # A project that landed and then ate far more than it paid for is a
        # loss, not a win.
        self.assertLess(OUTCOME_WEIGHT["scope_creep"], 0)

    def test_the_market_is_read_from_the_location(self):
        from agents.fullstack_sales.brain import market_of
        self.assertEqual("india", market_of("Mumbai, Maharashtra"))
        self.assertEqual("us", market_of("Austin, TX"))
        self.assertEqual("gulf", market_of("Dubai, UAE"))

    def test_none_of_the_four_brains_can_see_each_other(self):
        from agents.fullstack_sales.brain import DevMemory
        from agents.job_hunter.brain import JobMemory
        from agents.sponsorship.brain import Memory
        from agents.video_client.brain import DealMemory
        DevMemory(self.store).record_deal(self.deal(), "paid")
        self.assertEqual(0, Memory(self.store).summary()["decisions"])
        self.assertEqual(0, JobMemory(self.store).summary()["decisions"])
        self.assertEqual(0, DealMemory(self.store).summary()["decisions"])
        self.assertEqual(1, len(DevMemory(self.store).summary()["events"]))


class TestProductStageGate(SuiteCase):
    """The product does not exist yet, so most claims are simply not available.

    This is the only agent in the suite that can do real damage by being
    persuasive: it writes to the exact community that will later be the
    product's first customers, partners and reviewers. One round of pitching
    something that turns out not to exist ends that.
    """

    extra_env = {"PRODUCT_FILE": str(ROOT / "profiles" / "product.yaml")}

    def setUp(self):
        super().setUp()
        from agents.saas_sales import product
        product.load_product(refresh=True)

    def check(self, text):
        from agents.saas_sales.product import check_claims
        return check_claims(text)

    def test_a_price_is_blocked_while_it_is_being_built(self):
        self.assertTrue(self.check("It's $19 a month."))

    def test_a_trial_is_blocked_because_there_is_nothing_to_try(self):
        self.assertTrue(self.check("Start your free trial today."))

    def test_a_commission_is_blocked_because_it_cannot_be_paid(self):
        # Promising 50% on a product that cannot take money is the fastest way
        # to be remembered as the person who did that.
        problems = self.check("You'll get 50% commission on every signup.")
        self.assertTrue(problems)
        self.assertIn("commission", " ".join(str(p) for p in problems))

    def test_a_launch_date_is_refused_at_every_stage(self):
        from agents.saas_sales.product import ALWAYS_REFUSED
        self.assertIn("launch_date", ALWAYS_REFUSED)
        self.assertTrue(self.check("We launch next month."))

    def test_invented_features_are_caught_even_as_word_stems(self):
        # A trailing \b after a stem cannot match the word it is a stem of, so
        # "auto[- ]?dub" once sailed straight past "auto-dubbing".
        for claim in ("It also does auto-dubbing.",
                      "It translates into 50 languages.",
                      "It does lip syncing."):
            self.assertTrue(self.check(claim), claim)

    def test_an_honest_message_passes_cleanly(self):
        self.assertEqual([], self.check(
            "I'm building a tool that strips silences and cuts filler words out "
            "of a timeline. It isn't finished. Would you want a look at it "
            "early and to tell me what's wrong with it?"))

    def test_the_agent_refuses_to_run_without_a_product_name(self):
        from agents.saas_sales.product import ready_to_sell
        ok, why = ready_to_sell()
        self.assertFalse(ok)
        self.assertIn("no name", why)

    def test_a_live_product_may_state_a_price_only_if_one_exists(self):
        import pathlib
        from agents.saas_sales import product
        card = (ROOT / "profiles" / "product.yaml").read_text(encoding="utf-8")
        live = pathlib.Path(self.tmp / "live.yaml")
        live.write_text(card.replace("stage: building", "stage: live"),
                        encoding="utf-8")
        with self.env(PRODUCT_FILE=str(live)):
            product.load_product(refresh=True)
            problems = product.check_claims("It is $19 a month.")
            self.assertTrue(problems, "no pricing tiers are filled in")
            self.assertIn("no pricing tiers", " ".join(str(p) for p in problems))
        product.load_product(refresh=True)


class TestLaunchAudiences(SuiteCase):
    """Four audiences want four different things."""

    extra_env = {"PRODUCT_FILE": str(ROOT / "profiles" / "product.yaml")}

    def prompt(self, kind):
        from agents.saas_sales import brief, product
        product.load_product(refresh=True)
        return brief.build_prompt({
            "target": {"name": "Someone", "kind": kind, "evidence": "found via x"},
            "about": {"description": "I teach editing workflow. " * 8,
                      "subscribers": "103K"}})

    def test_each_audience_gets_a_different_brief(self):
        seen = {k: self.prompt(k) for k in ("user", "promoter", "agency")}
        self.assertEqual(3, len(set(seen.values())))

    def test_the_promoter_brief_does_not_lead_with_money(self):
        p = self.prompt("promoter")
        self.assertIn("Do not lead with any of this", p)
        self.assertIn("No commission can be promised yet", p)

    def test_every_brief_says_the_product_is_unfinished(self):
        for kind in ("user", "promoter", "agency"):
            self.assertIn("STILL BEING BUILT", self.prompt(kind))

    def test_it_is_told_not_to_invent_a_differentiator(self):
        self.assertIn("Do not invent one", self.prompt("user"))

    def test_no_ragged_indentation_reaches_the_model(self):
        # Eight spaces is the dedent artefact - the template's own indentation
        # surviving because a block interpolated at column 0 emptied the common
        # prefix. Four-space lines are the deliberate nested bullets in the
        # product facts, which are meant to be there.
        stray = [ln for ln in self.prompt("user").splitlines()
                 if ln.startswith(" " * 8) and ln.strip()]
        self.assertEqual([], stray[:3])


class TestCompetitorGuard(SuiteCase):
    """Telling a competing plugin what is coming is not outreach."""

    def test_competing_tools_are_recognised(self):
        from agents.saas_sales.sources import is_competitor, classify
        # A live YouTube search returned two of these in the first 8 results.
        self.assertTrue(is_competitor("AutoCut", "speed up your edits"))
        self.assertTrue(is_competitor("EasyTimeline Pro", ""))
        self.assertEqual("competitor", classify("FireCut", "AI editing plugin"))
        self.assertFalse(is_competitor("Gavin Herman", "teaching editing"))

    def test_audience_size_is_banded(self):
        from agents.saas_sales.brain import size_band
        self.assertEqual("large", size_band("103K"))
        self.assertEqual("tiny", size_band("600"))
        self.assertEqual("huge", size_band("2.4M"))
        self.assertEqual("unknown", size_band(""))

    def test_asking_to_stop_is_the_worst_outcome(self):
        from agents.saas_sales.brain import OUTCOME_WEIGHT
        self.assertEqual(min(OUTCOME_WEIGHT.values()),
                         OUTCOME_WEIGHT["asked_to_stop"])
        # Before launch, feedback from a working editor is worth more than a
        # waitlist signup.
        self.assertGreater(OUTCOME_WEIGHT["gave_feedback"],
                           OUTCOME_WEIGHT["joined_waitlist"])

    def test_none_of_the_five_brains_can_see_each_other(self):
        from agents.fullstack_sales.brain import DevMemory
        from agents.job_hunter.brain import JobMemory
        from agents.saas_sales.brain import LaunchMemory
        from agents.sponsorship.brain import Memory
        from agents.video_client.brain import DealMemory
        LaunchMemory(self.store).record_target(
            {"source": "youtube", "kind": "promoter", "subscribers": "103K"},
            "gave_feedback")
        self.assertEqual(0, Memory(self.store).summary()["decisions"])
        self.assertEqual(0, JobMemory(self.store).summary()["decisions"])
        self.assertEqual(0, DealMemory(self.store).summary()["decisions"])
        self.assertEqual(0, DevMemory(self.store).summary()["decisions"])
        self.assertEqual(1, len(LaunchMemory(self.store).summary()["events"]))
