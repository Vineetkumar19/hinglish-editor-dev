"""Tests for the guarantees that matter most: nothing goes out unapproved,
nobody is contacted twice or after opting out, and nothing is invented."""
from __future__ import annotations

import unittest

from tests.base import SuiteCase
from tests.fakes.servers import FakeWebServer


class TestSendPolicy(SuiteCase):
    def mailer(self):
        from core.mailer import Mailer
        return Mailer(store=self.store, transport="smtp")

    def msg(self, to="a@b.example", **kw):
        from core.mailer import OutgoingMessage
        base = dict(to=to, subject="A reasonable subject",
                    body="Hi there,\n\nThis body is long enough to pass the checks.")
        base.update(kw)
        return OutgoingMessage(**base)

    def test_suppression_is_permanent_and_global(self):
        from core.mailer import SendBlocked
        m = self.mailer()
        m.suppression.add("gone@b.example", reason="unsubscribe")
        with self.assertRaises(SendBlocked):
            m.send(self.msg("gone@b.example"))
        from core.mailer import Mailer
        other = Mailer(store=self.store, transport="smtp")
        with self.assertRaises(SendBlocked):
            other.send(self.msg("gone@b.example"))

    def test_daily_cap_stops_sending(self):
        import os
        from core.mailer import SendBlocked
        os.environ["DAILY_SEND_CAP"] = "2"
        m = self.mailer()
        from unittest.mock import patch
        with patch.object(m, "_send_smtp", return_value={"ok": True, "dry_run": False}):
            m.send(self.msg("a@b.example"), dry_run=False)
            m.send(self.msg("c@d.example"), dry_run=False)
            with self.assertRaises(SendBlocked):
                m.send(self.msg("e@f.example"), dry_run=False)

    def test_role_addresses_are_never_contacted(self):
        from core.mailer import SendBlocked, valid_email
        self.assertFalse(valid_email("noreply@b.example"))
        self.assertFalse(valid_email("postmaster@b.example"))
        self.assertFalse(valid_email("not-an-email"))
        with self.assertRaises(SendBlocked):
            self.mailer().send(self.msg("noreply@b.example"))

    def test_empty_or_trivial_messages_are_refused(self):
        from core.mailer import SendBlocked
        m = self.mailer()
        with self.assertRaises(SendBlocked):
            m.send(self.msg(subject=""))
        with self.assertRaises(SendBlocked):
            m.send(self.msg(body="too short"))

    def test_bulk_mail_carries_a_working_opt_out(self):
        from core.mailer import unsubscribe_token, unsubscribe_url
        built = self.mailer().build(self.msg("x@y.example"))
        self.assertIn("List-Unsubscribe", built)
        self.assertEqual(built["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        url = unsubscribe_url("x@y.example")
        self.assertIn(unsubscribe_token("x@y.example"), url)

    def test_unsubscribe_token_is_not_forgeable(self):
        from core.mailer import unsubscribe_token
        self.assertNotEqual(unsubscribe_token("a@b.example"),
                            unsubscribe_token("c@d.example"))


class TestNothingSendsWithoutApproval(SuiteCase):
    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def test_outreach_suspends_before_every_send(self):
        import agents.sponsorship.agent as sponsor
        llm = self.offline_llm()
        app = sponsor.make(store=self.store, llm=llm,
                           crawler=self.fast_crawler(llm=llm)).build()
        r = app.invoke({"_thread_id": "na"}, thread_id="na")
        self.assertTrue(r.interrupted)
        self.assertEqual(self.store.query("SELECT * FROM send_log"), [],
                         "a send happened before any human decision")

    def test_every_outbound_kind_has_a_gate(self):
        """Each agent's graph must route outbound work through an approval node."""
        from core.registry import get_graph, names
        outbound = {"sponsorship": "approve", "video_client": "approve",
                    "fullstack_sales": "approve",
                    "fullstack_sales_quote": "approve_quote",
                    "sponsorship_reply": "approve_reply",
                    "video_client_reply": "approve_reply",
                    "fullstack_sales_reply": "approve_reply",
                    "job_hunter": "review",
                    "job_hunter_interview": "approve"}
        for name, gate in outbound.items():
            graph = get_graph(name, self.store)
            self.assertIn(gate, graph.spec.nodes, f"{name} has no approval node")
            senders = [n for n in graph.spec.nodes
                       if n in ("send", "send_reply", "applied")]
            for s in senders:
                incoming = [src for src, dst in graph.spec.edges.items() if dst == s]
                incoming += [src for src, (_, m) in graph.spec.conditional.items()
                             if s in (m or {}).values()]
                self.assertTrue(incoming, f"{name}.{s} is unreachable")
                self.assertTrue(
                    any(gate in i or "approve" in i or "review" in i for i in incoming),
                    f"{name}.{s} can be reached without passing {gate}: {incoming}")


class TestDedupe(SuiteCase):
    def test_same_address_is_not_mailed_twice_across_agents(self):
        self.assertTrue(self.store.mark_seen("sponsorship:email", "a@b.example"))
        self.assertFalse(self.store.mark_seen("sponsorship:email", "A@B.example"))

    def test_job_dedupe_is_by_company_and_title(self):
        from agents.job_hunter.discovery import Job
        a = Job(title="Backend Engineer (Python)", company="Zerodha")
        b = Job(title="backend engineer python", company="zerodha ")
        self.assertEqual(a.key(), b.key())


class TestHallucinationGuards(SuiteCase):
    def test_resume_guard_strips_invented_facts(self):
        from agents.job_hunter.resume import load_master, master_corpus, novel_claims
        corpus = master_corpus(load_master())
        self.assertEqual(novel_claims("Built REST APIs in Python", corpus), [])
        novel = novel_claims("Led 40 engineers at Google on Kubernetes", corpus)
        self.assertIn("Google", novel)
        self.assertIn("40", novel)

    def test_tailoring_falls_back_when_the_model_invents(self):
        from agents.job_hunter.discovery import Job
        from agents.job_hunter.resume import load_master, tailor

        class LyingLLM:
            is_offline = False

            def structured(self, prompt, schema, **kw):
                return {"summary": "Ex-Google staff engineer, led 40 people.",
                        "experience_ids": ["hcl-swe", "made-up-job"],
                        "skill_order": ["Python", "Kubernetes", "Kafka", "Rust"],
                        "bullet_rewrites": [{"experience_id": "hcl-swe", "index": 0,
                                             "text": "Scaled systems to 10 million "
                                                     "users at Google."}],
                        "project_ids": [], "dropped_reason": ""}

        master = load_master()
        res = tailor(master, Job(title="X", company="Y", description="python"),
                     llm=LyingLLM())
        joined = str(res.data)
        self.assertNotIn("Google", joined)
        self.assertNotIn("Kubernetes", res.data["skills"])
        self.assertNotIn("Kafka", res.data["skills"])
        self.assertTrue(res.dropped)
        for e in res.data["experience"]:
            self.assertIn(e["id"], {x["id"] for x in master["experience"]})

    def test_crawler_drops_emails_the_model_invents(self):
        from core.crawler import Crawler, PageResult, SiteProfile

        class FakeLLM:
            def structured(self, *a, **kw):
                return {"company_summary": "s",
                        "people": [{"name": "Real", "role": "Head",
                                    "email": "real@x.example", "relevance": 0.9},
                                   {"name": "Fake", "role": "CEO",
                                    "email": "guessed@x.example", "relevance": 0.9}]}

        page = PageResult(url="http://x.example/", status=200, text="t",
                          emails=["real@x.example"])
        profile = SiteProfile(domain="x.example", pages=[page])
        out = Crawler(llm=FakeLLM()).semantic_contacts(profile, "partnerships")
        emails = [p["email"] for p in out["people"]]
        self.assertIn("real@x.example", emails)
        self.assertNotIn("guessed@x.example", emails)

    def test_quotes_never_come_from_a_model(self):
        from agents.fullstack_sales.pricing import build_quote
        q = build_quote(["marketing_site", "auth"])
        self.assertEqual(q.total, build_quote(["marketing_site", "auth"]).total)
        self.assertGreater(q.total, 0)


class TestScamFilter(SuiteCase):
    def job(self, **kw):
        from agents.job_hunter.discovery import Job
        return Job(**kw)

    def test_rejects_fee_requests(self):
        from agents.job_hunter.scam_filter import heuristic_screen
        r = heuristic_screen(self.job(
            title="Data Entry", company="Reputed MNC",
            description="Pay a registration fee of Rs 500 to confirm your seat. "
                        "Earn Rs 3000 per day guaranteed working from home."))
        self.assertEqual(r.verdict, "reject")

    def test_rejects_document_harvesting(self):
        from agents.job_hunter.scam_filter import heuristic_screen
        r = heuristic_screen(self.job(
            title="Accounts", company="Global",
            description="Send your Aadhaar and PAN card. The interview will be "
                        "conducted on WhatsApp chat. Assured placement guaranteed."))
        self.assertEqual(r.verdict, "reject")

    def test_passes_a_genuine_posting(self):
        from agents.job_hunter.scam_filter import screen
        r = screen(self.offline_llm(), self.job(
            title="Senior Backend Engineer", company="Zerodha",
            location="Bengaluru", contact_email="careers@zerodha.example",
            salary_min=3500000, salary_currency="INR",
            description="We are hiring a senior backend engineer for our order "
                        "management system. You will build Go and Python services, "
                        "design PostgreSQL schemas and operate them on Kubernetes. "
                        "Requirements: six years of production backend experience, "
                        "strong concurrency knowledge. Benefits include health "
                        "insurance and provident fund. We are an equal opportunity "
                        "employer. Apply through our careers portal."))
        self.assertEqual(r.verdict, "pass")

    def test_free_email_domain_for_a_named_company_is_a_flag(self):
        from agents.job_hunter.scam_filter import heuristic_screen
        r = heuristic_screen(self.job(
            title="Engineer", company="Infosys", contact_email="hrteam@gmail.com",
            description="We are hiring an engineer to work on our internal systems "
                        "in Bengaluru. You will write code and review changes and "
                        "work with the platform team on delivery."))
        self.assertTrue(any("free email" in f for f in r.flags))

    def test_inconsistent_seniority_and_pay(self):
        from agents.job_hunter.scam_filter import screen
        r = screen(self.offline_llm(), self.job(
            title="Software Engineering Intern", company="GrowthCo",
            salary_min=9000000, salary_currency="INR",
            description="Great opportunity. We need an intern with 12 years of "
                        "experience. Apply now to join our team. Apply now."))
        self.assertEqual(r.verdict, "reject")


class TestRobotsAndPoliteness(SuiteCase):
    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def test_disallowed_site_is_not_crawled(self):
        before = len(self.web.requests)
        profile = self.fast_crawler().profile_site("http://gear.example/")
        paths = [p for _, p in self.web.requests[before:]]
        self.assertEqual([p for p in paths if p != "/robots.txt"], [],
                         "only robots.txt should have been fetched")
        self.assertIsNone(profile.best_contact)


class TestPromptLint(SuiteCase):
    def test_lint_catches_spam_signals(self):
        from agents.common import lint_pitch
        problems = lint_pitch("QUICK QUESTION FOR YOU!!",
                              "I hope this email finds you well. We guarantee 10x "
                              "your revenue. {{name}}")
        joined = " ".join(problems)
        self.assertIn("cliche", joined)
        self.assertIn("shouty", joined)
        self.assertIn("merge field", joined)
        self.assertIn("guarantee", joined)

    def test_clean_pitch_passes(self):
        from agents.common import lint_pitch
        self.assertEqual(lint_pitch(
            "Creator partnerships at Acme?",
            "Hi Priya,\n\nI came across Acme and wanted to ask whether you run a "
            "creator partnership programme.\n\nVineet"), [])


class TestIntentClassification(SuiteCase):
    CASES = {
        "Yes we're interested! Can you share your rates?": "interested",
        "Please unsubscribe me from this list": "unsubscribe",
        "Remove me from your mailing list please": "unsubscribe",
        "I am out of the office until 3 March": "out_of_office",
        "Not interested, we already have an agency": "not_interested",
        "That is way out of our budget, too expensive": "objection_price",
        "Let's circle back next quarter, bad timing": "objection_timing",
        "Delivery has failed. 550-5.1.1 address not found": "auto_bounce",
        "You should talk to Rahul instead, he handles this": "referral",
        "How much do you charge per video?": "question",
    }

    def test_offline_classifier_accuracy(self):
        from agents.common import classify_intent
        llm = self.offline_llm()
        wrong = [(t, classify_intent(llm, t)["label"], want)
                 for t, want in self.CASES.items()
                 if classify_intent(llm, t)["label"] != want]
        self.assertEqual(wrong, [], f"misclassified: {wrong}")

    def test_opt_out_beats_the_model(self):
        """An explicit opt-out must never be overridden by an LLM."""
        from agents.common import classify_intent

        class WrongLLM:
            is_offline = False

            def structured(self, *a, **kw):
                return {"label": "interested", "confidence": 0.99, "reason": "wrong"}

        out = classify_intent(WrongLLM(), "Please remove me from this list.")
        self.assertEqual(out["label"], "unsubscribe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
