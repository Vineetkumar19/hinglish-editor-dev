import copy
import unittest
from types import SimpleNamespace

from hinglish_eval.model_rules import visuals_plan, visuals_repair


class VisualPlanGroundingTests(unittest.TestCase):
    def plan(self, spoken='Kolkata ne Delhi ko haraya'):
        phrase = SimpleNamespace(id=0, start=0., end=3., text=spoken)
        plan = {'entities': [{'key': 'kkr', 'name': 'Kolkata Knight Riders',
            'kind': 'person', 'about': 'Indian Premier League cricket team based in Kolkata'}],
            'moments': [{'id': 0, 'quote': 'Kolkata ne', 'mention': 'Kolkata',
                'entity': 'kkr', 'meaning': 'Kolkata defeated Delhi',
                'visual': 'Kolkata Knight Riders in 2023',
                'search': ['Kolkata Knight Riders vs Delhi 2023'],
                'reference_type': 'identity', 'evidence_terms': []}]}
        return [phrase], plan

    def test_live_draft_cannot_invent_a_year_or_classify_a_team_as_person(self):
        phrases, plan = self.plan()
        rules = {p.rule for p in visuals_plan(phrases, phrases, {})(plan)}
        self.assertIn('visuals.unsupported_year', rules)
        self.assertIn('visuals.entity_kind', rules)
        repaired, notes = visuals_repair(phrases, phrases, {})(plan)
        self.assertEqual(repaired['entities'][0]['kind'], 'brand')
        self.assertEqual(len(repaired['moments']), 1)
        self.assertNotIn('2023', str(repaired))
        self.assertTrue(notes)
        self.assertEqual(visuals_plan(phrases, phrases, {})(repaired), [])

    def test_spoken_year_stays_and_original_model_draft_is_preserved(self):
        phrases, plan = self.plan('2023 mein Kolkata ne Delhi ko haraya')
        original = copy.deepcopy(plan)
        repaired, _ = visuals_repair(phrases, phrases, {})(plan)
        self.assertIn('2023', repaired['moments'][0]['visual'])
        self.assertIn('2023', repaired['moments'][0]['search'][0])
        self.assertEqual(plan, original)
        self.assertNotIn('visuals.unsupported_year',
            {p.rule for p in visuals_plan(phrases, phrases, {})(repaired)})

    def test_portrait_does_not_count_as_evidence_of_numeric_performance(self):
        phrases, plan = self.plan('Kolkata ne 195 runs banaye')
        plan['moments'][0].update(visual='Kolkata Knight Riders scored 195 runs')
        rules = {p.rule for p in visuals_plan(phrases, phrases, {})(plan)}
        self.assertIn('visuals.statistical_evidence', rules)
        repaired, _ = visuals_repair(phrases, phrases, {})(plan)
        self.assertEqual(repaired['moments'][0]['reference_type'], 'evidence')
        self.assertEqual(len(repaired['moments']), 1)
        self.assertEqual(visuals_plan(phrases, phrases, {})(repaired), [])

    def test_exact_team_is_not_filtered_out_in_favor_of_a_season_page(self):
        from hinglish_visuals.planner import resolve_entity
        class Web:
            def search_entities(self, name):
                return [
                    {'id': 'Q_TEAM', 'label': 'Chennai Super Kings',
                     'description': 'Chennai based franchise of the Indian Premier League'},
                    {'id': 'Q_SEASON', 'label': 'Chennai Super Kings in 2013',
                     'description': 'Indian Premier League cricket team season'}]
            def entity(self, key, name, kind, qid):
                return SimpleNamespace(qid=qid)
        result = resolve_entity(None, Web(), {'key': 'csk', 'name': 'Chennai Super Kings',
            'kind': 'brand', 'about': 'Indian Premier League cricket team'}, {'topic': 'IPL final'})
        self.assertEqual(result.qid, 'Q_TEAM')

    def test_changed_score_is_rejected_but_split_asr_score_is_supported(self):
        phrases, plan = self.plan('Kolkata ne 1 95 runs aur Delhi ne 71 runs banaye')
        plan['moments'][0].update(visual='Kolkata scored 61 runs', reference_type='evidence')
        self.assertIn('visuals.unsupported_score',
            {p.rule for p in visuals_plan(phrases, phrases, {})(plan)})
        plan['moments'][0]['visual'] = 'Kolkata scored 195 runs'
        self.assertNotIn('visuals.unsupported_score',
            {p.rule for p in visuals_plan(phrases, phrases, {})(plan)})

    def test_uncertain_name_is_searched_as_spoken_instead_of_discarded(self):
        phrases, plan = self.plan('jaykaalis banaate hain 69 run')
        plan['entities'] = [{'key': 'player', 'name': 'Jayakar', 'kind': 'person', 'about': 'Cricket player'}]
        plan['moments'][0].update(entity='player', mention='jaykaalis', quote='jaykaalis banaate hain',
            visual='Jayakar photo', search=['Jayakar photo'])
        repaired, _ = visuals_repair(phrases, phrases, {})(plan)
        self.assertEqual(repaired['entities'][0]['name'], 'jaykaalis')
        self.assertEqual(len(repaired['moments']), 1)
        self.assertIn('jaykaalis', repaired['moments'][0]['search'][0])

    def test_scorecard_request_keeps_a_separate_player_identity_bank(self):
        from hinglish_visuals.references import research_slots
        from hinglish_visuals.planner import VisualMoment
        from hinglish_visuals.web import Entity
        from hinglish_cut.model import Word
        phrase = SimpleNamespace(id=0, start=0., end=3., text='Suresh Raina ne 71 runs banaye')
        moment = VisualMoment(0, 'Suresh Raina scored 71 runs for Chennai Super Kings',
            ['Suresh Raina 71 runs'], 3, 'Suresh Raina', 'Spoken score',
            'raina', 'Suresh Raina', 'photo', 'popup', reference_type='evidence')
        entities = {'raina': Entity('raina', 'Suresh Raina', 'person'),
            'csk': Entity('csk', 'Chennai Super Kings', 'brand')}
        slots = research_slots([moment], [phrase], [Word('Suresh', 0., .5), Word('Raina', .5, 1.)], entities, 3.)
        self.assertEqual(len(slots), 2)
        photo = next(s for s in slots if s['reference_type'] == 'identity')
        self.assertEqual(photo['visual'], 'Suresh Raina in Chennai Super Kings kit')
        self.assertEqual(photo['evidence_terms'], [])
        self.assertEqual(next(s for s in slots if s['reference_type'] == 'evidence')['visual'], moment.visual)

    def test_invalid_factual_quote_does_not_erase_a_named_person(self):
        from hinglish_visuals.planner import validate_plan
        phrases = [SimpleNamespace(id=0, start=0., end=2., text='Gautam Gambhir ka wicket gir gaya')]
        raw = {'entities': [{'key': 'gambhir', 'name': 'Gautam Gambhir', 'kind': 'person',
                            'about': 'Indian cricketer'}],
               'moments': [{'id': 0, 'quote': 'an invented century', 'entity': 'gambhir',
                            'visual': 'Gautam Gambhir century'}]}
        moments = validate_plan(raw, phrases, {})
        self.assertEqual(len(moments), 1)
        self.assertEqual(moments[0].reference_type, 'identity')
        self.assertEqual(moments[0].visual, 'Gautam Gambhir photo')
        self.assertNotIn('century', str(moments[0]))

    def test_same_sport_does_not_make_an_unrelated_person_a_name_match(self):
        from hinglish_visuals.planner import resolve_entity
        class Web:
            def search_entities(self, name):
                return [{'id': 'Q_BISLA', 'label': 'Manvinder Bisla', 'description': 'Indian cricketer'}]
        self.assertIsNone(resolve_entity(None, Web(), {'key': 'player', 'name': 'jaykaalis',
            'kind': 'person', 'about': 'Cricket player'}, {'topic': 'IPL final'}))

    def test_real_source_alias_can_resolve_a_nickname(self):
        from hinglish_visuals.planner import resolve_entity
        class Web:
            def search_entities(self, name):
                return [{'id': 'Q_GANDHI', 'label': 'Mahatma Gandhi', 'description': 'Indian independence leader',
                         'matched_name': 'Bapu'}]
            def entity(self, key, name, kind, qid):
                return SimpleNamespace(qid=qid)
        class Brain:
            def json(self, *args, **kwargs): return {'id': 'Q_GANDHI'}
        self.assertEqual(resolve_entity(Brain(), Web(), {'key': 'bapu', 'name': 'Bapu',
            'kind': 'person', 'about': 'Indian independence leader'}, {'topic': 'Indian independence'}).qid, 'Q_GANDHI')


if __name__ == '__main__':
    unittest.main()
