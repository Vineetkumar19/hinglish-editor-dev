import unittest
from unittest.mock import Mock
from hinglish_publish.prepare_post_audit import citation_audit


class CopyToleranceTests(unittest.TestCase):
    def test_minor_wording_is_recorded_but_does_not_block(self):
        brain=Mock();brain.json.return_value={'approved':False,'issues':[
            {'draft_id':0,'reason':'Small spelling mistake','severity':'minor'}]}
        result=citation_audit(brain,{'draft':{'title':'Punjab journey'},'speech':'Punjab journey'})
        self.assertTrue(result['approved']);self.assertEqual(result['issues'],[])
        self.assertEqual(len(result['warnings']),1)
        self.assertIn('Do not request a rewrite',brain.json.call_args.args[0])

    def test_material_claim_and_unclassified_legacy_issue_still_block(self):
        for extra in ({'severity':'material'},{}):
            brain=Mock();brain.json.return_value={'approved':True,'issues':[
                {'draft_id':0,'reason':'Wrong winning team',**extra}]}
            result=citation_audit(brain,{'draft':{'title':'Wrong winner'},'speech':'Actual winner'})
            self.assertFalse(result['approved']);self.assertEqual(len(result['issues']),1)

    def test_invalid_citation_is_not_hidden_as_minor(self):
        brain=Mock();brain.json.return_value={'approved':True,'issues':[
            {'draft_id':19,'reason':'Typo','severity':'minor'}]}
        with self.assertRaises(ValueError):
            citation_audit(brain,{'draft':{'title':'Punjab'},'speech':'Punjab'})
