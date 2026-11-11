"""The sponsorship agent's discovery half: finding, filtering, learning.

The interesting tests here are the ones that could fail. It is easy to write a
"learning" component that stores numbers nobody reads, so these check that a
decision actually changes the next ranking, and that the explanation matches
the score it explains.
"""
from __future__ import annotations

from tests.base import ROOT, SuiteCase
from tests.fakes.servers import FakeWebServer


class TestIndiaFilter(SuiteCase):
    def test_rupee_prices_and_a_91_number_are_enough(self):
        from agents.sponsorship.india import india_score
        score, hits = india_score(
            "Buy now for ₹1,299. Call us on +91 98765 43210.", domain="brand.com")
        self.assertGreaterEqual(score, 0.5)
        self.assertIn("prices in rupees", hits)
        self.assertIn("+91 phone number", hits)

    def test_an_american_shop_does_not_pass(self):
        from agents.sponsorship.india import india_score, is_indian
        score, _ = india_score(
            "Free shipping across the US. Pay $49.99 at checkout. "
            "Call (415) 555-0100.", domain="brandshop.com")
        self.assertLess(score, 0.3)
        self.assertFalse(is_indian("Only $20 in our Boston store", domain="x.com"))

    def test_saying_it_does_not_ship_to_india_overrides_the_rest(self):
        from agents.sponsorship.india import is_indian
        text = ("Prices in ₹ shown for reference. Contact +91 90000 11111. "
                "We do not ship to India.")
        self.assertFalse(is_indian(text, domain="x.com"),
                         "an explicit no should beat every weak signal")

    def test_an_in_domain_alone_is_not_enough(self):
        from agents.sponsorship.india import india_score
        score, _ = india_score("A website about things.", domain="something.in")
        self.assertLess(score, 0.31)

    def test_hindi_text_counts(self):
        from agents.sponsorship.india import india_score
        score, hits = india_score("हमारे उत्पाद खरीदें", domain="brand.com")
        self.assertIn("Hindi text on the page", hits)
        self.assertGreater(score, 0)

    def test_a_word_like_transfer_is_not_a_rupee_price(self):
        from agents.sponsorship.india import india_score
        score, hits = india_score("Fast transfers and low costs", domain="x.com")
        self.assertNotIn("prices in rupees", hits)
        self.assertEqual(0.0, score)


class TestHeadlineExtraction(SuiteCase):
    def test_it_finds_the_brand_in_a_campaign_headline(self):
        from agents.sponsorship.sources import _brand_from_headline as brand
        self.assertEqual("Max Cement", brand(
            "Max Cement launches Mil Kar Banate Hai campaign"))
        self.assertEqual("Jockey", brand(
            "Jockey celebrates 150 years with a new campaign"))
        self.assertEqual("BabyOrgano", brand(
            "BabyOrgano's latest campaign sparks a conversation"))

    def test_it_does_not_mistake_a_person_for_a_brand(self):
        from agents.sponsorship.sources import _brand_from_headline as brand
        self.assertEqual("", brand(
            "Sai Ganesh joins Emergent as Global Head of Brand"),
            "appointment news names a person, not a company")
        self.assertEqual("", brand(
            "5 ways India's economic slowdown will help digital growth"))
        self.assertEqual("", brand(
            "The best marketing campaigns of the year so far"))

    def test_section_labels_are_stripped(self):
        from agents.sponsorship.sources import _brand_from_headline as brand
        self.assertEqual("Zomato", brand(
            "STORY OF THE DAY Zomato launches a festive campaign"))


class TestBannedCategories(SuiteCase):
    def test_betting_never_reaches_the_list(self):
        from agents.sponsorship.discover import banned_reason
        for name in ("Crickex", "Royal Casino", "BetWay India",
                     "Teen Patti Gold"):
            self.assertTrue(banned_reason(name),
                            f"{name} should be refused")
        self.assertEqual("", banned_reason("Nakpro Nutrition"))

    def test_a_clean_name_with_a_dirty_page_is_still_caught(self):
        from agents.sponsorship.discover import banned_reason
        self.assertTrue(banned_reason(
            "Sunrise Sports", "deposit and win real money game daily"))


class TestMemory(SuiteCase):
    def prospect(self, **kw):
        base = {"domain": "a.com", "source": "cuelinks", "segment": "nutrition",
                "deal_type": "affiliate", "india_score": 0.8,
                "data": {"has_email": True}}
        base.update(kw)
        return base

    def test_one_decision_changes_the_next_score(self):
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        before, _ = mem.score(self.prospect())
        mem.record(self.prospect(), "approved")
        after, _ = mem.score(self.prospect(domain="b.com"))
        self.assertGreater(after, before,
                           "an approval must make the next similar find rank higher")

    def test_a_rejection_pushes_it_the_other_way(self):
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        for i in range(4):
            mem.record(self.prospect(domain=f"r{i}.com"), "rejected")
        score, why = mem.score(self.prospect(domain="new.com"))
        self.assertLess(score, 0.35)
        self.assertTrue(any(w["shift"] < 0 for w in why))

    def test_a_reply_counts_for_more_than_an_approval(self):
        from agents.sponsorship.brain import Memory
        a = Memory(self.store)
        a.record(self.prospect(segment="approved_only"), "approved")
        approved, _ = a.score(self.prospect(segment="approved_only",
                                            domain="x1.com"))
        a.record(self.prospect(segment="replied_only"), "replied_interested")
        replied, _ = a.score(self.prospect(segment="replied_only",
                                           domain="x2.com"))
        self.assertGreater(replied, approved,
                           "a brand replying is stronger evidence than your guess")

    def test_the_explanation_adds_up_to_the_score(self):
        import math
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        for i in range(3):
            mem.record(self.prospect(domain=f"y{i}.com"), "approved")
        score, why = mem.score(self.prospect(domain="z.com"))
        base = mem.base_rate()
        logit = math.log(base / (1 - base)) + sum(w["shift"] for w in why)
        rebuilt = 1 / (1 + math.exp(-logit))
        self.assertAlmostEqual(score, rebuilt, places=2,
                               msg="the working shown must produce the number shown")

    def test_one_lucky_approval_does_not_dominate(self):
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        mem.record(self.prospect(source="trade_press"), "approved")
        score, _ = mem.score(self.prospect(source="trade_press", domain="n.com"))
        self.assertLess(score, 0.85, "a single example should not become a law")

    def test_sources_that_work_get_more_of_the_budget(self):
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        for i in range(12):
            mem.record(self.prospect(domain=f"g{i}.com", source="cuelinks"),
                       "approved")
            mem.record(self.prospect(domain=f"b{i}.com", source="trade_press"),
                       "rejected")
        wins = sum(1 for _ in range(60)
                   if mem.source_weights(["cuelinks", "trade_press"])["cuelinks"]
                   > 0.5)
        self.assertGreater(wins, 45,
                           "the source that keeps working should usually win "
                           "the budget, while the other still gets a chance")

    def test_it_says_what_it_learned(self):
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        mem.record(self.prospect(), "approved")
        mem.record(self.prospect(domain="q.com", segment="gambling"), "rejected")
        s = mem.summary()
        self.assertEqual(s["decisions"], 12)     # 6 features x 2 decisions
        self.assertTrue(s["best"])
        self.assertTrue(s["worst"])


class TestDiscoveryRun(SuiteCase):
    """The whole graph, against fixture websites rather than the real web."""

    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def sponsor_file(self, body: str = "targets:\n"):
        """Every test gets its own list. The shared fixture already contains
        the example domains, which would make every find look like a duplicate."""
        import os
        path = self.tmp / f"sponsors-{self.id().rsplit('.', 1)[-1]}.yaml"
        path.write_text(body, encoding="utf-8")
        os.environ["SPONSOR_FILE"] = str(path)
        return path

    def build(self, candidates=None):
        import agents.sponsorship.agent as P
        from agents.sponsorship.sources import Candidate
        self.sponsor_file()
        cands = candidates if candidates is not None else [
            Candidate(name="Example Sports Analytics", url="http://analytics.example/",
                      source="cuelinks", deal_type="affiliate",
                      payout="8% per sale", note="Live affiliate campaign"),
        ]
        import os
        # These have to be set BEFORE make(), because the outreach config reads
        # them once at construction. The fixture sites are not Indian, and the
        # outreach half has its own tests - this file is about discovery.
        os.environ["PROSPECT_INDIA_MIN"] = "0.0"
        os.environ["SPONSORSHIP_MAX_LEADS"] = "0"
        return P.make(store=self.store, crawler=self.fast_crawler(),
                      discovery_crawler=self.fast_crawler(),
                      source_fns={"fake": lambda *a, **k: list(cands)})

    def test_a_find_is_proposed_before_anything_is_added(self):
        agent = self.build()
        result = agent.build().invoke({"_thread_id": "p1", "discover": True}, thread_id="p1")
        self.assertTrue(result.interrupted,
                        "it must ask before touching the sponsor list")
        row = self.queue.get(result.approval_id)
        self.assertEqual(row["kind"], "add_target")
        self.assertIn("analytics.example", row["payload"]["domain"])

    def test_approving_writes_it_into_the_list_and_teaches_the_memory(self):
        import pathlib
        from agents.sponsorship.brain import Memory
        agent = self.build()
        target = self.sponsor_file()
        app = agent.build()
        result = app.invoke({"_thread_id": "p2", "discover": True}, thread_id="p2")
        decision = self.queue.approve(result.approval_id, note="yes")
        app.resume("p2", decision.to_json())

        text = pathlib.Path(target).read_text(encoding="utf-8")
        self.assertIn("Example Sports Analytics", text)
        self.assertIn("deal_type: affiliate", text)
        self.assertGreaterEqual(Memory(self.store).summary()["decisions"], 6,
                                "the decision should have taught every feature")

    def test_rejecting_writes_nothing_but_still_teaches(self):
        import pathlib
        from agents.sponsorship.brain import Memory
        agent = self.build()
        target = self.sponsor_file()
        app = agent.build()
        result = app.invoke({"_thread_id": "p3", "discover": True}, thread_id="p3")
        decision = self.queue.reject(result.approval_id, note="no thanks")
        app.resume("p3", decision.to_json())

        self.assertNotIn("Example Sports Analytics",
                         pathlib.Path(target).read_text(encoding="utf-8"))
        self.assertGreaterEqual(Memory(self.store).summary()["decisions"], 6,
                                "the decision should have taught every feature")

    def test_a_brand_already_on_the_list_is_not_proposed_again(self):
        from agents.sponsorship.sources import Candidate
        agent = self.build([Candidate(name="Example Sports Analytics",
                                      url="http://analytics.example/",
                                      source="cuelinks")])
        self.sponsor_file(
            "targets:\n  - name: Example Fantasy\n"
            "    url: http://analytics.example/\n    category: sponsor\n")
        result = agent.build().invoke({"_thread_id": "p4", "discover": True}, thread_id="p4")
        self.assertFalse(result.interrupted)
        reasons = [d["reason"] for d in (result.state.get("skipped") or [])]
        self.assertIn("already on the list", reasons)

    def test_a_betting_brand_is_dropped_without_being_shown(self):
        from agents.sponsorship.sources import Candidate
        agent = self.build([
            Candidate(name="Crickex Betting", url="http://analytics.example/",
                      source="cuelinks", note="real money game"),
        ])
        result = agent.build().invoke({"_thread_id": "p5", "discover": True}, thread_id="p5")
        self.assertFalse(result.interrupted,
                         "a betting brand must never reach an approval card")
        self.assertTrue(result.state.get("skipped"))

    def test_a_site_that_is_not_indian_is_dropped(self):
        from agents.sponsorship.sources import Candidate
        import agents.sponsorship.agent as P
        self.sponsor_file()
        import os
        os.environ["PROSPECT_INDIA_MIN"] = "0.9"   # nothing clears this
        os.environ["SPONSORSHIP_MAX_LEADS"] = "0"
        agent = P.make(store=self.store, crawler=self.fast_crawler(),
                       discovery_crawler=self.fast_crawler(),
                       source_fns={"fake": lambda *a, **k: [
                           Candidate(name="Example Sports Analytics",
                                     url="http://analytics.example/",
                                     source="cuelinks")]})
        result = agent.build().invoke({"_thread_id": "p6", "discover": True}, thread_id="p6")
        self.assertFalse(result.interrupted)
        reasons = " ".join(d["reason"] for d in (result.state.get("skipped") or []))
        self.assertIn("Indian", reasons)


class TestOneAgentOneBrain(SuiteCase):
    """The merge: finding and pitching are one agent sharing one memory."""

    def setUp(self):
        super().setUp()
        self.web = FakeWebServer().start()

    def tearDown(self):
        self.web.stop()
        super().tearDown()

    def agent(self, **kw):
        import agents.sponsorship.agent as sponsor
        llm = self.offline_llm()
        return sponsor.make(store=self.store, llm=llm,
                            crawler=self.fast_crawler(llm=llm),
                            discovery_crawler=self.fast_crawler(), **kw)

    def test_there_is_no_separate_prospector_left(self):
        import importlib
        with self.assertRaises(ImportError,
                               msg="discovery should live inside the "
                                   "sponsorship agent, not beside it"):
            importlib.import_module("agents.prospector.agent")

    def test_one_run_can_both_find_and_pitch(self):
        from agents.sponsorship.sources import Candidate
        import os
        target = self.tmp / "merged.yaml"
        target.write_text(
            "targets:\n  - name: Example Sports Analytics\n"
            "    url: http://analytics.example/\n    category: sponsor\n"
            "    segment: cricket_tech\n    tier: 1\n    deal_type: cash\n"
            "    fit: already on the list\n    tags: [india]\n    hints: []\n",
            encoding="utf-8")
        os.environ["SPONSOR_FILE"] = str(target)
        os.environ["PROSPECT_INDIA_MIN"] = "0.0"

        agent = self.agent(source_fns={"fake": lambda *a, **k: [
            Candidate(name="Rohits Cricket Channel",
                      url="http://creatorstudio.example/",
                      source="cuelinks", deal_type="affiliate")]})
        app = agent.build()
        result = app.invoke({"_thread_id": "m1", "discover": True},
                            thread_id="m1")

        kinds, guard = [], 0
        while result.interrupted and guard < 12:
            guard += 1
            row = self.queue.get(result.approval_id)
            kinds.append(row["kind"])
            decision = self.queue.approve(result.approval_id, note="yes")
            result = app.resume("m1", decision.to_json())

        self.assertIn("add_target", kinds,
                      "the run should have offered a brand to add")
        self.assertTrue(any(k in ("send_email", "send_message") for k in kinds),
                        "the same run should then have offered a pitch to send")

    def test_approving_a_pitch_teaches_the_same_brain_as_adding_a_brand(self):
        from agents.sponsorship.brain import Memory
        import os
        os.environ["SPONSORSHIP_MAX_LEADS"] = "4"
        agent = self.agent()
        app = agent.build()
        result = app.invoke({"_thread_id": "m2", "discover": False},
                            thread_id="m2")
        guard = 0
        while result.interrupted and guard < 8:
            guard += 1
            decision = self.queue.approve(result.approval_id, note="send it")
            result = app.resume("m2", decision.to_json())

        events = Memory(self.store).summary()["events"]
        self.assertIn("pitch_approved", events,
                      "approving a pitch must be filed as evidence too")

    def test_a_rejected_pitch_is_filed_as_a_negative(self):
        from agents.sponsorship.brain import Memory
        import os
        os.environ["SPONSORSHIP_MAX_LEADS"] = "4"
        agent = self.agent()
        app = agent.build()
        result = app.invoke({"_thread_id": "m3", "discover": False},
                            thread_id="m3")
        guard = 0
        while result.interrupted and guard < 8:
            guard += 1
            decision = self.queue.reject(result.approval_id, note="no")
            result = app.resume("m3", decision.to_json())
        self.assertIn("pitch_rejected", Memory(self.store).summary()["events"])

    def test_what_it_learns_from_one_brand_moves_the_other_kind(self):
        """The point of one brain: a reply from a nutrition brand should lift
        the next nutrition brand found on the web, and vice versa."""
        from agents.sponsorship.brain import Memory
        mem = Memory(self.store)
        listed = {"meta": {"url": "https://a.com", "segment": "nutrition",
                           "deal_type": "barter", "tier": 1, "tags": []}}
        fresh = {"domain": "b.com", "source": "cuelinks",
                 "segment": "nutrition", "deal_type": "barter",
                 "india_score": 0.9, "data": {}}

        before, _ = mem.score(fresh)
        for _ in range(3):
            mem.record_target(listed, "replied_interested")
        after, _ = mem.score(fresh)
        self.assertGreater(after, before,
                           "a reply to a listed brand should lift a similar "
                           "brand found on the web")

        listed2 = {"meta": {"url": "https://c.com", "segment": "nutrition",
                            "deal_type": "barter", "tier": 1, "tags": []}}
        target_score, _ = mem.score_target(listed2)
        self.assertGreater(target_score, 0.5,
                           "and it should lift the untouched listed brands too")

    def test_the_queue_order_shifts_with_what_it_has_learned(self):
        from agents.sponsorship.brain import Memory
        import agents.sponsorship.agent as sponsor
        mem = Memory(self.store)
        for _ in range(6):
            mem.record_target({"meta": {"url": "https://x.com",
                                        "segment": "nutrition",
                                        "deal_type": "cash", "tier": 1,
                                        "tags": []}}, "replied_interested")
            mem.record_target({"meta": {"url": "https://y.com",
                                        "segment": "merch",
                                        "deal_type": "cash", "tier": 1,
                                        "tags": []}}, "replied_no")
        good = mem.score_target({"meta": {"url": "https://n.com",
                                          "segment": "nutrition",
                                          "deal_type": "cash", "tier": 1,
                                          "tags": []}})[0]
        bad = mem.score_target({"meta": {"url": "https://m.com",
                                         "segment": "merch",
                                         "deal_type": "cash", "tier": 1,
                                         "tags": []}})[0]
        self.assertGreater(good, bad,
                           "the segment that replies should outrank the one "
                           "that says no")
        self.assertTrue(hasattr(sponsor.SponsorshipAgent, "n_refresh"),
                        "the sponsorship agent owns the discovery nodes now")
