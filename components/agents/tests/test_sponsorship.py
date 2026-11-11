"""The sponsorship agent's honesty rules, tested where they can actually fail.

The whole value of this agent is that a brand can check anything it says. So
these tests are mostly about what must NOT appear in a message.
"""
from __future__ import annotations

from tests.base import ROOT, SuiteCase


class TestPitchHonesty(SuiteCase):
    EMPTY = {"name": "Vineet", "channels": [
        {"platform": "youtube", "subscribers": 0, "avg_views": 0},
        {"platform": "instagram", "followers": 0, "avg_reel_views": 0}],
        "audience": {"country_share": 0, "male_share": 0}}

    FULL = {"name": "Vineet Kumar Das",
            "tagline": "Cricket analysis and documentary-style edits",
            "channels": [
                {"platform": "youtube", "url": "https://youtube.com/@v",
                 "subscribers": 12500, "avg_views": 38000},
                {"platform": "instagram", "followers": 24000,
                 "avg_reel_views": 61000}],
            "audience": {"country_share": 82, "male_share": 91,
                         "age_18_34_share": 74},
            "craft": ["written and edited in-house"],
            "best_work": [{"title": "MI 2008-2016", "url": "https://y.example/1"}]}

    def test_an_empty_profile_produces_a_pitch_with_no_numbers(self):
        from agents.sponsorship import pitch
        import re
        out = pitch.email_pitch({"name": "Beardo", "segment": "grooming"},
                                creator=self.EMPTY)
        self.assertFalse(out["has_numbers"])
        body = out["body"]
        # No figure that could be read as an audience claim.
        for pattern in (r"\d+\s*K\b", r"\d+\s*L\b", r"\d+%", r"\d{3,}"):
            self.assertIsNone(re.search(pattern, body),
                              f"a blank profile produced {pattern!r} in: {body}")
        self.assertIn("cricket", body.lower())
        self.assertTrue(out["subject"])

    def test_a_filled_profile_states_exactly_what_is_in_it(self):
        from agents.sponsorship import pitch
        body = pitch.email_pitch({"name": "Beardo", "segment": "grooming"},
                                 creator=self.FULL)["body"]
        self.assertIn("12.5K subscribers", body)
        self.assertIn("38K views", body)
        self.assertNotIn("12.5k subscribers", body)
        self.assertIn("91% male", body)
        self.assertIn("https://y.example/1", body)

    def test_numbers_are_never_rounded_upward(self):
        from agents.sponsorship import pitch
        self.assertEqual(pitch.human_number(12499), "12.5K")
        self.assertEqual(pitch.human_number(999), "999")
        self.assertEqual(pitch.human_number(250000), "2.5L")
        body = pitch.email_pitch(
            {"name": "X", "segment": "nutrition"},
            creator={"channels": [{"platform": "youtube", "subscribers": 900}]}
        )["body"]
        self.assertIn("900 subscribers", body)

    def test_each_segment_gets_its_own_argument(self):
        from agents.sponsorship import pitch
        seen = set()
        for seg in ("nutrition", "grooming", "fintech", "agency", "cricket_gear"):
            body = pitch.email_pitch({"name": "X", "segment": seg},
                                     creator=self.FULL)["body"]
            seen.add(pitch.angle_for(seg))
            self.assertIn(pitch.angle_for(seg), body)
        self.assertEqual(len(seen), 5, "segments must not share one template")

    def test_an_agency_is_asked_a_different_question_to_a_brand(self):
        from agents.sponsorship import pitch
        agency = pitch.email_pitch({"name": "Chtrbox", "segment": "agency"},
                                   creator=self.FULL)
        brand = pitch.email_pitch({"name": "Beardo", "segment": "grooming"},
                                  creator=self.FULL)
        self.assertIn("roster", agency["body"])
        self.assertNotIn("roster", brand["body"])
        self.assertNotEqual(agency["subject"], brand["subject"])

    def test_the_whatsapp_message_fits_a_phone_screen(self):
        from agents.sponsorship import pitch
        msg = pitch.whatsapp_pitch({"name": "Beardo", "segment": "grooming"},
                                   creator=self.FULL)
        self.assertLess(len(msg), 700, "nobody reads a WhatsApp essay")
        self.assertIn("?", msg, "it has to end in a question to get a reply")
        dm = pitch.instagram_dm({"name": "Beardo", "segment": "grooming"},
                                creator=self.FULL)
        self.assertLess(len(dm), 500)

    def test_the_whatsapp_link_carries_the_message(self):
        from agents.sponsorship import pitch
        import urllib.parse
        link = pitch.wa_link("+91 90000 11111", "Hi there & welcome")
        self.assertTrue(link.startswith("https://wa.me/919000011111?text="))
        text = urllib.parse.unquote(link.split("text=", 1)[1])
        self.assertEqual(text, "Hi there & welcome")
        self.assertEqual(pitch.wa_link("", "x"), "",
                         "no number means no link, not a broken one")


class TestSponsorList(SuiteCase):
    """The shipped list itself, not the fixture."""

    def setUp(self):
        super().setUp()
        from core.yamlite import load_yaml
        self.brands = load_yaml(
            (ROOT / "profiles" / "sponsors.yaml").read_text(encoding="utf-8")
        )["targets"]

    def test_it_is_actually_a_list_worth_running(self):
        self.assertGreaterEqual(len(self.brands), 100,
                                "one reply in fifty means the list has to be big")

    def test_every_entry_is_complete(self):
        for b in self.brands:
            for key in ("name", "url", "category", "segment", "tier", "fit"):
                self.assertTrue(str(b.get(key, "")).strip(),
                                f"{b.get('name', '?')} is missing {key}")
            self.assertTrue(b["url"].startswith("https://"), b["name"])

    def test_no_brand_appears_twice(self):
        names = [b["name"] for b in self.brands]
        dupes = {n for n in names if names.count(n) > 1}
        self.assertEqual(set(), dupes)
        domains = [b["url"].split("//")[-1].split("/")[0].removeprefix("www.")
                   for b in self.brands]
        self.assertEqual(len(set(domains)), len(domains),
                         "the same site listed twice wastes a slot in the run")

    def test_no_real_money_gaming_survived_into_the_list(self):
        """India banned it in 2025. A list built from older advice is full of
        these, so this test is the thing that stops one creeping back in."""
        import agents.sponsorship.agent as sp
        offenders = [(b["name"], sp.blocked_reason(b)) for b in self.brands
                     if sp.blocked_reason(b)]
        self.assertEqual([], offenders)

    def test_the_reachable_ones_are_ranked_first(self):
        import agents.sponsorship.agent as sp
        order = [sp.rank({"meta": b}) for b in self.brands]
        tier_one = sum(1 for b in self.brands if b["tier"] == 1)
        self.assertGreater(tier_one, 50, "most of the list should be brands "
                                         "that will actually answer")
        self.assertEqual(sorted(order)[0][0], 1)


class TestContactLadder(SuiteCase):
    """Which route gets picked when several are available."""

    def test_a_published_phone_beats_a_guessed_address(self):
        from core.crawler import Contact
        from agents.common import OutreachAgent, OutreachConfig
        cfg = OutreachConfig(agent="sponsorship", search_queries=[],
                             allow_non_email=True)
        ag = OutreachAgent(cfg, store=self.store, llm=self.offline_llm())
        contacts = [
            Contact(email="partnerships@x.com", confidence=0.20, guessed=True,
                    channel="email").__dict__,
            Contact(phone="+919000011111", confidence=0.42,
                    channel="whatsapp").__dict__,
        ]
        out = ag.n_qualify({"current": {"domain": "x.com"},
                            "profile": {"pages_ok": 2, "description": "d"},
                            "contacts": contacts})
        chosen = out["qualify"]["contact"]
        self.assertEqual(chosen["channel"], "whatsapp",
                         "a number they published beats an address we invented")

    def test_a_published_address_still_wins_overall(self):
        from core.crawler import Contact
        from agents.common import OutreachAgent, OutreachConfig
        cfg = OutreachConfig(agent="sponsorship", search_queries=[],
                             allow_non_email=True)
        ag = OutreachAgent(cfg, store=self.store, llm=self.offline_llm())
        contacts = [
            Contact(email="hello@x.com", confidence=0.55, channel="email").__dict__,
            Contact(phone="+919000011111", confidence=0.42,
                    channel="whatsapp").__dict__,
        ]
        out = ag.n_qualify({"current": {"domain": "x.com"},
                            "profile": {"pages_ok": 2, "description": "d"},
                            "contacts": contacts})
        self.assertEqual(out["qualify"]["contact"]["email"], "hello@x.com")

    def test_a_guess_is_only_made_when_nothing_was_published(self):
        from core.crawler import Crawler, SiteProfile, PageResult
        prof = SiteProfile(domain="x.com")
        page = PageResult(url="https://x.com/", status=200, text="hi",
                          emails=["hello@x.com"])
        prof.pages = [page]
        contacts = Crawler()._build_contacts(prof)
        self.assertTrue(contacts)
        self.assertFalse(any(c.guessed for c in contacts),
                         "a published address means there is nothing to guess at")


class TestDealTypes(SuiteCase):
    """At 1-2K followers the deal that earns is rarely a cash sponsorship, so
    the agent has to ask each target for the thing it actually offers."""

    CREATOR = {"name": "Vineet", "tagline": "Cricket documentaries",
               "channels": [{"platform": "youtube", "subscribers": 1213},
                            {"platform": "instagram", "followers": 2014}],
               "deliverables": ["60 to 90 second integrated read inside a video"],
               "accepts_barter": True}

    def test_an_affiliate_target_is_asked_to_be_joined_not_to_pay(self):
        from agents.sponsorship import pitch
        out = pitch.email_pitch({"name": "EarnKaro", "segment": "affiliate_network",
                                 "deal_type": "affiliate"}, creator=self.CREATOR)
        self.assertIn("affiliate", out["subject"].lower())
        body = out["body"].lower()
        self.assertIn("programme i can join", body)
        self.assertNotIn("proposal for the coming series", body)

    def test_a_barter_target_is_offered_a_video_for_product(self):
        from agents.sponsorship import pitch
        out = pitch.email_pitch({"name": "Nakpro", "segment": "nutrition",
                                 "deal_type": "barter"}, creator=self.CREATOR)
        self.assertIn("collaboration", out["subject"].lower())
        self.assertIn("in exchange for product", out["body"])
        self.assertIn("a 60 to 90 second", out["body"],
                      "the deliverable needs an article to read as a sentence")

    def test_a_cash_target_is_asked_about_partnerships(self):
        from agents.sponsorship import pitch
        out = pitch.email_pitch({"name": "CricHeroes", "segment": "cricket_tech",
                                 "deal_type": "cash"}, creator=self.CREATOR)
        self.assertIn("partnership", out["subject"].lower())
        self.assertIn("who looks after them", out["body"])
        self.assertNotIn("in exchange for product", out["body"])

    def test_the_four_deal_types_produce_four_different_asks(self):
        from agents.sponsorship import pitch
        asks = set()
        for kind in ("affiliate", "barter", "agency", "cash"):
            out = pitch.email_pitch({"name": "X", "segment": "nutrition",
                                     "deal_type": kind}, creator=self.CREATOR)
            # The ask is the paragraph immediately before the signature.
            asks.add(out["body"].strip().split("\n\n")[-2])
        self.assertEqual(len(asks), 4, "each deal type needs its own ask")

    def test_an_unknown_deal_type_falls_back_to_a_paid_partnership(self):
        from agents.sponsorship import pitch
        self.assertEqual("cash", pitch.deal_type({"deal_type": "nonsense"}))
        self.assertEqual("cash", pitch.deal_type({}))

    def test_the_short_channels_change_too(self):
        from agents.sponsorship import pitch
        wa = pitch.whatsapp_pitch({"name": "Nakpro", "segment": "nutrition",
                                   "deal_type": "barter"}, self.CREATOR)
        self.assertIn("in exchange for product", wa)
        dm = pitch.instagram_dm({"name": "EarnKaro", "segment": "affiliate_network",
                                 "deal_type": "affiliate"}, self.CREATOR)
        self.assertIn("affiliate programme", dm.lower())

    def test_brands_that_pay_are_worked_first(self):
        """The point of the agent is brands paying to be promoted, so that
        comes first. Affiliate - earning a cut of someone else's sales - is a
        different job and goes last."""
        import agents.sponsorship.agent as sp
        queue = [{"meta": {"tier": 1, "deal_type": "affiliate", "segment": "x", "name": "D"}},
                 {"meta": {"tier": 1, "deal_type": "barter", "segment": "x", "name": "C"}},
                 {"meta": {"tier": 1, "deal_type": "agency", "segment": "x", "name": "B"}},
                 {"meta": {"tier": 1, "deal_type": "cash", "segment": "x", "name": "A"}}]
        queue.sort(key=sp.rank)
        self.assertEqual([q["meta"]["name"] for q in queue], ["A", "B", "C", "D"])

    def test_affiliate_is_not_worked_at_all_by_default(self):
        import agents.sponsorship.agent as sp
        self.assertNotIn("affiliate", sp.wanted_deals())
        for kind in ("cash", "agency", "barter"):
            self.assertIn(kind, sp.wanted_deals())


class TestBigList(SuiteCase):
    def setUp(self):
        super().setUp()
        from core.yamlite import load_yaml
        self.brands = load_yaml(
            (ROOT / "profiles" / "sponsors.yaml").read_text(encoding="utf-8")
        )["targets"]

    def test_the_list_is_big_enough_to_be_a_real_income_source(self):
        self.assertGreaterEqual(len(self.brands), 350)

    def test_every_entry_declares_what_deal_is_on_offer(self):
        allowed = {"affiliate", "barter", "agency", "cash"}
        for b in self.brands:
            self.assertIn(b.get("deal_type"), allowed,
                          f"{b.get('name')} has deal_type {b.get('deal_type')!r}")

    def test_the_list_is_mostly_brands_that_can_pay(self):
        from collections import Counter
        by_deal = Counter(b["deal_type"] for b in self.brands)
        # Cash has to be the biggest category - that is the job. The bar was
        # 200 while 88 entries were labelled cash but were on the list for
        # their affiliate programme; a number that only held because of
        # mislabelled entries was measuring nothing.
        self.assertGreater(by_deal["cash"], by_deal["barter"],
                           "brands that pay should outnumber barter")
        self.assertGreaterEqual(by_deal["cash"], 150)
        self.assertGreaterEqual(by_deal["agency"], 25)
        self.assertGreaterEqual(by_deal["barter"], 80)

    def test_nothing_on_the_list_is_there_for_its_affiliate_programme(self):
        """The label is not the point - the evidence is.

        Changing deal_type from "affiliate" to "cash" left 88 brands whose
        stated reason for being here was a commission programme, and the agent
        went on pitching them. This checks what the entry SAYS, not what it is
        labelled.
        """
        from agents.sponsorship.discover import salesman_reason
        bad = [b["name"] for b in self.brands
               if salesman_reason(b.get("fit", ""), b.get("why", ""),
                                  " ".join(str(h) for h in (b.get("hints") or [])))]
        self.assertEqual([], bad[:10], "these are commission deals, not promotions")

    def test_no_shopping_link_schemes_are_on_the_list(self):
        """Affiliate networks and marketplaces make you a salesman for someone
        else's catalogue. They are not sponsors and do not belong here."""
        bad = [b["name"] for b in self.brands
               if b["segment"] in ("affiliate_network", "marketplace")
               or b["deal_type"] == "affiliate"]
        self.assertEqual([], bad)

    def test_no_duplicate_names_or_domains(self):
        names = [b["name"] for b in self.brands]
        self.assertEqual(len(set(names)), len(names))
        doms = [b["url"].split("//")[-1].split("/")[0].removeprefix("www.")
                for b in self.brands]
        dupes = {d for d in doms if doms.count(d) > 1}
        self.assertEqual(set(), dupes)

    def test_still_no_real_money_gaming(self):
        import agents.sponsorship.agent as sp
        offenders = [b["name"] for b in self.brands if sp.blocked_reason(b)]
        self.assertEqual([], offenders)


class TestModelWrittenPitch(SuiteCase):
    """What the model is allowed to decide, and what it is not.

    The value of a model here is that it reads the brand. The risk is that it
    also invents the sender. These tests hold that line.
    """

    def _ctx(self, site_text="We make ayurvedic baby care. Tulsi drops, "
                             "balm and baby oil, made in Ahmedabad. " * 40):
        return {
            "current": {"domain": "babyorgano.in",
                        "meta": {"name": "BabyOrgano", "segment": "wellness",
                                 "deal_type": "cash", "tier": 2,
                                 "fit": "small brand, quick to answer"}},
            "profile": {"description": "Ayurvedic baby care", "text": site_text},
            "contact": {"name": "Riya Shah", "email": "hello@babyorgano.in"},
        }

    def test_the_brief_carries_the_brands_own_words_and_the_real_numbers(self):
        from agents.sponsorship import brief
        prompt = brief.build_prompt(self._ctx())
        self.assertIn("Tulsi drops", prompt)
        self.assertIn("BabyOrgano", prompt)
        self.assertIn("reads_as", prompt)
        # The ask must match the deal type, not be left to the model.
        self.assertIn("paid promotion", prompt)
        # And the categories that are refused must be refused in the brief too,
        # not only in the target list.
        self.assertIn("real-money", prompt.lower())

    def test_an_unreadable_site_is_admitted_rather_than_filled_in(self):
        from agents.sponsorship import brief
        prompt = brief.build_prompt(self._ctx(site_text=""))
        self.assertIn("could not be read", prompt)
        self.assertIn("Invent nothing", prompt)

    def test_the_signature_is_the_codes_job_not_the_models(self):
        from agents.sponsorship import brief
        from agents.sponsorship import pitch as pitch_mod
        # A model that signed off as the wrong person, with the wrong address.
        draft = {"reads_as": "ayurvedic baby care",
                 "subject": "Cricket content partnership - BabyOrgano",
                 "body": "Hi Riya,\n\nYour tulsi drops caught my eye. Do you run "
                         "creator partnerships?\n\nBest regards,\nRahul Sharma\n"
                         "rahul@notmine.com",
                 "whatsapp": "Hi, do you work with cricket creators?\n\nRahul",
                 "instagram_dm": "Hi! Do you do creator collabs?"}
        out = brief.finish(draft, self._ctx())
        self.assertNotIn("Rahul", out["body"])
        self.assertNotIn("notmine.com", out["body"])
        self.assertTrue(out["body"].endswith(pitch_mod.signature()))
        # A brand reading the DM still needs somewhere to reply.
        self.assertIn("@", out["instagram_dm"])

    def test_signing_an_already_signed_message_does_not_double_it(self):
        from agents.sponsorship import agent as sa
        from agents.sponsorship import brief
        from agents.sponsorship import pitch as pitch_mod
        ctx = self._ctx()
        written = sa._offline_pitch(ctx)
        once = brief.finish(written, ctx)
        twice = brief.finish(once, ctx)
        self.assertEqual(once["body"], twice["body"])
        self.assertEqual(1, once["body"].count(pitch_mod.signature()))

    def test_the_written_fallback_answers_the_same_shape_as_the_model(self):
        # If it did not, the fallback would fail validation exactly when the
        # model is unavailable - the one moment it has to work.
        from core.schema import validate
        from agents.sponsorship import agent as sa
        from agents.sponsorship import brief
        out = validate(sa._offline_pitch(self._ctx()), brief.PITCH_SCHEMA)
        for key in ("reads_as", "subject", "body", "whatsapp", "instagram_dm"):
            self.assertTrue(str(out.get(key) or "").strip(), f"{key} is empty")

    def test_the_card_shows_what_the_model_read_before_you_approve(self):
        # A wrong read of the brand is the cheapest mistake to catch, and the
        # only place to catch it is the card you approve from.
        card = self._bot().brand_text({"payload": {
            "company": "BabyOrgano", "to": "hello@babyorgano.in",
            "channel": "email", "subject": "s", "body": "b",
            "reads_as": "They sell ayurvedic baby care and mention no creators.",
            "deal_type": "cash", "score": 0.6}})
        self.assertIn("ayurvedic baby care", card)

    def test_the_card_says_so_when_the_model_was_not_reachable(self):
        card = self._bot().brand_text({"payload": {
            "company": "BabyOrgano", "channel": "email", "subject": "s",
            "body": "b", "deal_type": "cash",
            "fallback": "cannot reach Ollama at http://localhost:11434"}})
        self.assertIn("written template", card)

    def _bot(self):
        from core.telegram import Telegram
        from server.bot import Bot
        from tests.fakes.servers import FakeTelegramServer
        fake = FakeTelegramServer().start()
        self.addCleanup(fake.stop)
        return Bot(store=self.store, queue=self.queue,
                   telegram=Telegram(token=fake.token, api_base=fake.url))
