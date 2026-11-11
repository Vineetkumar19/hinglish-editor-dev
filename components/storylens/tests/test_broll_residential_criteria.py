"""Request-contract TDD; negative answers only, no model/media acceptance."""
import copy
import json
import unittest

from tests import test_broll_residential_verdict_replay as replay


MARKER='\nB-roll physical criteria (data):\n'


class ResidentialCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.fixture=replay.ResidentialVerdictReplayTests()
        self.fixture.setUp()

    def criteria(self,checker):
        prompt=checker.model.look.call_args_list[0].args[1]
        if MARKER not in prompt:return None
        return json.JSONDecoder().raw_decode(prompt.split(MARKER,1)[1])[0]

    def test_actual_apartment_request_has_explicit_physical_criteria(self):
        checker,result=self.fixture.replay()
        criteria=self.criteria(checker)
        self.assertIsNotNone(criteria,'The actual apartment request needs bounded physical criteria.')
        self.assertEqual(criteria['revision'],'broll-residential-v2')
        self.assertEqual(criteria['required_visual'],'visible residential indoor space')
        self.assertIn('residential living area',criteria['permitted_spaces'])
        self.assertIn('rental status',criteria['nonclaims'])
        self.assertIn('commercial salon',criteria['excluded_visuals'])
        self.assertEqual(criteria['narrated_country'],'India')
        self.assertFalse(result['passed'])

    def test_room_request_uses_same_bounded_family_without_losing_keyword(self):
        slot=copy.deepcopy(self.fixture.observed['slot']);slot['visual']='room interior'
        checker,_=self.fixture.replay(slot=slot)
        criteria=self.criteria(checker)
        self.assertIsNotNone(criteria)
        self.assertEqual(criteria['requested_keyword'],'room interior')

    def test_named_places_and_other_physical_claims_do_not_enter_generic_family(self):
        for visual,subject in [('apartment interior','Buckingham Palace'),('empty room',''),
                ('person sleeping',''),('salon interior',''),('refrigerator',''),('apartment interior with no bed','')]:
            with self.subTest(visual=visual,subject=subject):
                slot=copy.deepcopy(self.fixture.observed['slot']);slot.update(visual=visual,subject=subject)
                checker,result=self.fixture.replay(slot=slot)
                self.assertIsNone(self.criteria(checker))
                self.assertFalse(result['passed'])

    def test_criteria_call_preserves_full_source_fields_and_independent_vetoes(self):
        checker,result=self.fixture.replay()
        _,prompt,schema=checker.model.look.call_args.args
        for field in ['text','meaning','context','direction']:
            self.assertIn(self.fixture.observed['slot'][field],prompt)
        for field in ['related','context_compatible','identity_compatible','real_clear_footage','no_intrusive_text']:
            self.assertIn(field,schema['required'])
            self.assertEqual(result[field],self.fixture.raw[field])
        self.assertEqual(result['frame_checks'],self.fixture.raw['frame_checks'])
        self.assertEqual(result.get('physical_criteria_revision'),'broll-residential-v2')

    def test_negative_criteria_answer_is_not_reasked_for_an_approval(self):
        answer=copy.deepcopy(self.fixture.raw)
        answer.update(seen='An apartment interior with a sofa.',context_compatible=True)
        checker,result=self.fixture.replay(answer=answer)
        self.assertFalse(result['passed'])
        self.assertEqual(checker.model.look.call_count,1)
        self.assertNotIn('recheck',result)

    def test_nonreview_modes_never_receive_the_residential_hook(self):
        from hinglish_broll.verify import _review_physical_criteria
        for review in (False,None,1,'true'):
            with self.subTest(review=review):
                slot=copy.deepcopy(self.fixture.observed['slot']);slot['review_options']=review
                self.assertIsNone(_review_physical_criteria(slot))

    def test_generic_room_does_not_require_occupancy_furniture_or_tenant_gender(self):
        slot=copy.deepcopy(self.fixture.observed['slot']);slot['visual']='room interior'
        checker,result=self.fixture.replay(slot=slot)
        criteria=self.criteria(checker)
        self.assertIn('unfurnished residential room',criteria['permitted_spaces'])
        self.assertIn('occupancy or lived-in appearance',criteria['nonclaims'])
        self.assertIn('incidental occupant gender',criteria['nonclaims'])
        self.assertIn('tidiness or luxury level',criteria['nonclaims'])
        self.assertFalse(result['passed'],'Changing the request must never flip the recorded negative model answer.')


if __name__=='__main__':
    unittest.main()
