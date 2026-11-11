"""The job relevance filter.

These are written against the exact postings that made it through before the
filter existed - Inside Sales Contractor, Tier III Service Desk Engineer,
Freelance Writer - because those are what the complaint was about.
"""
from __future__ import annotations

import unittest

from agents.job_hunter import relevance
from agents.job_hunter.discovery import Job
from tests.base import SuiteCase


def job(title, description="", company="Acme"):
    return Job(id="x", title=title, company=company, description=description)


class TestRoleFiltering(SuiteCase):
    def test_rejects_the_exact_junk_that_got_through_before(self):
        for title in ("Inside Sales Contractor",
                      "Tier III Service Desk Engineer",
                      "Freelance Writer",
                      "Freelance Copywriter",
                      "Content Reviewer - English US"):
            with self.subTest(title=title):
                m = relevance.classify(job(title))
                self.assertFalse(m.relevant, f"{title!r} should not reach him")
                self.assertTrue(m.reason, "a rejection must say why")

    def test_keeps_the_roles_he_asked_for(self):
        wanted = {
            "Software Engineer - New Grad": "software",
            "Java Full Stack Developer": "java",
            "Python Developer": "python",
            "Machine Learning Engineer": "ai_ml",
            "AI Engineer - FDE (Forward Deployed Engineer)": "forward_deployed",
            "Data Engineer": "data_engineering",
            "Data Analyst": "data_analysis",
            "Generative AI Engineer": "agentic_ai",
        }
        for title, family in wanted.items():
            with self.subTest(title=title):
                m = relevance.classify(job(title))
                self.assertTrue(m.relevant, f"{title!r} should have been kept")
                self.assertEqual(m.family, family)

    def test_sales_engineer_is_not_a_sales_job(self):
        """'Solutions Engineer' is an FDE role; 'Sales Engineer' is not."""
        self.assertTrue(relevance.classify(job("Solutions Engineer")).relevant)
        self.assertFalse(relevance.classify(job("Sales Engineer")).relevant)

    def test_role_families_can_be_narrowed(self):
        import os
        os.environ["JOB_ROLE_FAMILIES"] = "ai_ml,agentic_ai"
        try:
            self.assertTrue(relevance.classify(job("AI Engineer")).relevant)
            self.assertFalse(relevance.classify(job("Data Analyst")).relevant)
        finally:
            os.environ.pop("JOB_ROLE_FAMILIES")


class TestExperienceGate(SuiteCase):
    def test_a_fresher_does_not_see_senior_roles(self):
        for title in ("Senior React Full-stack Developer", "Staff Software Engineer",
                      "Principal Engineer", "Engineering Manager",
                      "Lead Data Engineer"):
            with self.subTest(title=title):
                m = relevance.classify(job(title), max_years=0)
                self.assertFalse(m.relevant)

    def test_years_are_read_out_of_the_description(self):
        cases = {
            "We need 5+ years of backend experience.": 5,
            "Minimum of 3 years building web apps.": 3,
            "3-5 years of experience required": 3,
            "At least 2 years in data engineering": 2,
            "Great for freshers and recent graduates": 0,
            "This is an entry level position": 0,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(relevance.required_years(text), expected)

    def test_silence_about_experience_is_not_a_rejection(self):
        """Most postings never state years. Dropping them all would be wrong."""
        m = relevance.classify(job("Software Engineer", "Build things with us."),
                               max_years=0)
        self.assertIsNone(m.min_years)
        self.assertTrue(m.relevant)

    def test_a_bit_above_your_level_still_gets_through(self):
        """0 years + 2 slack: a '2+ years' posting is still worth seeing."""
        m = relevance.classify(job("Backend Engineer", "2+ years of experience"),
                               max_years=0)
        self.assertTrue(m.relevant)
        m = relevance.classify(job("Backend Engineer", "8+ years of experience"),
                               max_years=0)
        self.assertFalse(m.relevant)

    def test_raising_your_experience_opens_more_up(self):
        senior = job("Backend Engineer", "5+ years of experience needed")
        self.assertFalse(relevance.classify(senior, max_years=0).relevant)
        self.assertTrue(relevance.classify(senior, max_years=3).relevant)

    def test_a_company_age_is_not_an_experience_demand(self):
        m = relevance.classify(job("Software Engineer",
                                   "We have served customers for 20 years."),
                               max_years=0)
        self.assertTrue(m.relevant)


class TestExtraction(SuiteCase):
    def test_skills_come_out_of_the_posting(self):
        skills = relevance.extract_skills(
            "You will work with Java, Spring Boot and MySQL, plus some React "
            "on the front end. Kubernetes experience is a plus.")
        for expected in ("Java", "Spring Boot", "MySQL", "React", "Kubernetes"):
            self.assertIn(expected, skills)

    def test_the_broader_term_is_dropped_when_the_specific_one_is_there(self):
        skills = relevance.extract_skills("We use Spring Boot for services.")
        self.assertIn("Spring Boot", skills)
        self.assertNotIn("Spring", skills)

    def test_ai_vocabulary_is_recognised(self):
        skills = relevance.extract_skills(
            "Build agents with LangChain and RAG over a vector database, "
            "fine-tuning open models with PyTorch.")
        for expected in ("LangChain", "RAG", "PyTorch"):
            self.assertIn(expected, skills)

    def test_fresher_roles_rank_above_ones_that_merely_tolerate_you(self):
        fresher = relevance.classify(job("Software Engineer",
                                         "Open to freshers. Python, SQL."))
        experienced = relevance.classify(job("Software Engineer",
                                             "2+ years needed. Python, SQL."))
        ranked = sorted([experienced, fresher], key=relevance.sort_key)
        self.assertIs(ranked[0], fresher)


class TestAgentIntegration(SuiteCase):
    """The filter has to actually be wired into the run, not just exist."""

    extra_env = {"JOB_SOURCES": "fixture", "JOB_EXPERIENCE_YEARS": "0"}

    def test_off_target_jobs_never_reach_the_queue(self):
        import json
        import pathlib
        fixture = self.tmp / "jobs.json"
        fixture.write_text(json.dumps([
            {"id": "1", "title": "Inside Sales Contractor", "company": "Credit Co",
             "url": "https://a.example/1", "description": "Sell our product."},
            {"id": "2", "title": "Software Engineer - New Grad", "company": "Good Co",
             "url": "https://a.example/2",
             "description": "Python, SQL, REST APIs. Open to freshers."},
            {"id": "3", "title": "Freelance Writer", "company": "Words Inc",
             "url": "https://a.example/3", "description": "Write articles."},
        ]), encoding="utf-8")
        import os
        os.environ["JOB_FIXTURE_FILE"] = str(fixture)

        import agents.job_hunter.agent as jh
        agent = jh.make(store=self.store)
        state = agent.n_aggregate({"_thread_id": "t"})

        titles = [j["title"] for j in state["queue"]]
        self.assertEqual(titles, ["Software Engineer - New Grad"])
        self.assertEqual(state["stats"]["off_target"], 2)
        reasons = {o["title"]: o["reason"] for o in state["off_target"]}
        self.assertIn("Inside Sales Contractor", reasons)
        self.assertIn("sales", reasons["Inside Sales Contractor"])

    def test_the_queued_job_carries_what_the_card_needs(self):
        import json
        import os
        fixture = self.tmp / "jobs2.json"
        fixture.write_text(json.dumps([
            {"id": "9", "title": "Java Developer", "company": "Bank Co",
             "url": "https://a.example/9",
             "description": "Spring Boot, MySQL, REST APIs. Freshers welcome."},
        ]), encoding="utf-8")
        os.environ["JOB_FIXTURE_FILE"] = str(fixture)

        import agents.job_hunter.agent as jh
        state = jh.make(store=self.store).n_aggregate({"_thread_id": "t"})
        match = state["queue"][0]["match"]
        self.assertEqual(match["family"], "java")
        self.assertEqual(match["min_years"], 0)
        self.assertIn("Spring Boot", match["skills"])


class TestSalaryDisplay(SuiteCase):
    def test_an_unknown_salary_says_so_instead_of_zero(self):
        from agents.job_hunter.agent import _fmt_salary
        self.assertEqual(_fmt_salary({"salary_min": 0, "salary_max": 0}),
                         "not stated")

    def test_a_real_range_is_formatted_with_separators(self):
        from agents.job_hunter.agent import _fmt_salary
        self.assertEqual(
            _fmt_salary({"salary_min": 2800000, "salary_max": 4200000,
                         "salary_currency": "INR"}),
            "INR 2,800,000 - 4,200,000")


if __name__ == "__main__":
    unittest.main()


class TestWhereHeCanWork(SuiteCase):
    """Nothing filtered by location before this, so a run tailored a resume
    with a local model for San Francisco postings he was never going to take."""

    def ok(self, **job):
        from agents.job_hunter import location
        return location.acceptable(job)

    def test_his_cities_pass(self):
        for place in ("Bengaluru, India", "Pune, Maharashtra", "Navi Mumbai",
                      "Hyderabad, Telangana", "Gurugram, Haryana",
                      "Chennai (Hybrid)", "Noida, Uttar Pradesh"):
            self.assertTrue(self.ok(location=place)[0], place)

    def test_foreign_offices_do_not(self):
        for place in ("San Francisco, CA", "London, UK", "Berlin, Germany",
                      "Singapore", "Austin, TX"):
            self.assertFalse(self.ok(location=place)[0], place)

    def test_indianapolis_is_not_in_india(self):
        # "india" is a prefix of "indianapolis", and substring matching let a
        # US posting through as an Indian one.
        self.assertFalse(self.ok(location="Indianapolis, IN")[0])

    def test_a_us_address_is_recognised_without_being_listed(self):
        # There are too many US towns to list. A trailing two-letter state code
        # is the tell - nobody writes "Bangalore, KA".
        self.assertFalse(self.ok(location="San Mateo, CA")[0])
        self.assertTrue(self.ok(location="Bangalore, Karnataka")[0])

    def test_remote_that_is_not_open_to_india_is_refused(self):
        self.assertFalse(self.ok(location="Remote - US")[0])
        self.assertFalse(self.ok(location="Remote",
                                 description="Must be based in the US.")[0])
        self.assertFalse(self.ok(location="Remote", description="EU only.")[0])

    def test_the_location_field_beats_a_mention_lower_down(self):
        # An InMobi role in San Mateo passed because the ad mentioned the
        # India office further down the page.
        ok, why = self.ok(location="San Mateo, CA",
                          description="InMobi has offices in Bangalore, India.")
        self.assertFalse(ok, why)

    def test_remote_with_no_country_is_shown_but_flagged(self):
        ok, why = self.ok(location="Remote", remote=True,
                          description="Join our distributed team.")
        self.assertTrue(ok)
        self.assertIn("not stated", why)

    def test_a_blank_location_falls_back_to_the_ad_text(self):
        self.assertTrue(self.ok(location="",
                                description="Our Hyderabad team is hiring.")[0])
