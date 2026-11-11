import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from hinglish_publish.discovery import research, validate_plan, lint_pair, attach, build


class DiscoveryTests(unittest.TestCase):
    def test_live_suggestions_are_cached_and_never_claim_volume(self):
        get = Mock(return_value=Mock(status_code=200, json=lambda: ['camera setup', ['camera setup for beginners']]))
        with tempfile.TemporaryDirectory() as tmp:
            first = research(Path(tmp), 'camera setup', get=get, now=100)
            second = research(Path(tmp), 'camera setup', get=get, now=110)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first['status'], 'observed')
        self.assertEqual(second['suggestions'], ['camera setup for beginners'])
        self.assertIsNone(first['search_volume'])

    def test_network_failure_preserves_honest_research_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            answer = research(Path(tmp), 'camera setup', get=Mock(side_effect=TimeoutError()), now=100)
        self.assertEqual(answer['status'], 'unavailable')
        self.assertEqual(answer['suggestions'], [])

    def test_empty_or_instruction_like_suggestions_are_filtered(self):
        get = Mock(return_value=Mock(status_code=200, json=lambda: ['camera', ['', '<script>run()</script>', 'camera settings']]))
        with tempfile.TemporaryDirectory() as tmp:
            answer = research(Path(tmp), 'camera', get=get)
        self.assertEqual(answer['suggestions'], ['camera settings'])

    def plan(self):
        return {'primary_query': 'first job in Madurai', 'secondary_queries': ['living in Madurai'],
                'description': 'My first job brought me to Madurai, outside my comfort zone.\n#Madurai #FirstJob #ComfortZone',
                'tags': ['Madurai', 'First job', 'Comfort zone'],
                'intent': 'experience', 'titles': [
                    {'angle': 'search', 'title': 'My First Job in Madurai', 'reason': 'Names the actual topic'},
                    {'angle': 'browse', 'title': 'Why I Stayed in Madurai', 'reason': 'Matches the story question'},
                    {'angle': 'hybrid', 'title': 'First Job in Madurai: Leaving My Comfort Zone', 'reason': 'Topic and personal story'}],
                'thumbnail': {'text': 'FIRST JOB', 'subject': 'The creator', 'composition': 'Readable subject and short text', 'style': 'Restrained contrast'}}

    def test_plan_preserves_three_angles_and_rejects_invented_years(self):
        source = 'My first job brought me to Madurai, outside my comfort zone. I stayed.'
        self.assertEqual(len(validate_plan(self.plan(), source)['titles']), 3)
        bad = self.plan();bad['titles'][0]['title'] += ' in 2039'
        with self.assertRaises(ValueError): validate_plan(bad, source)

    def test_lint_is_advisory_and_does_not_require_numbers(self):
        self.assertEqual(lint_pair('My First Job in Madurai', 'OUTSIDE MY COMFORT ZONE')['blocking'], [])
        self.assertTrue(lint_pair('My First Job in Madurai', 'My First Job in Madurai')['warnings'])

    def test_duplicate_title_options_are_rejected(self):
        p=self.plan();p['titles'][1]['title']=p['titles'][0]['title']
        with self.assertRaises(ValueError): validate_plan(p, 'My first job brought me to Madurai.')

    def test_production_visual_style_failure_and_long_queries_are_rejected(self):
        source='My first job brought me to Madurai, outside my comfort zone.'
        for field,value in [('style','restrained cinematic sound'),('text','This is a very long thumbnail hook')]:
            p=self.plan();p['thumbnail'][field]=value
            with self.assertRaises(ValueError):validate_plan(p,source)
        p=self.plan();p['primary_query']='Why my very first job brought me to Madurai outside my comfort zone'
        with self.assertRaises(ValueError):validate_plan(p,source)

    def test_old_preparations_do_not_start_extra_inference(self):
        result={'metadata':{'title':'Saved title'},'paired_instagram':{'metadata':{'instagram_caption':'Saved caption'}}}
        with patch('hinglish_publish.discovery.build') as build:
            self.assertIs(attach('.',result,None,'speech',{},[],{}),result)
            build.assert_not_called()

    def test_review_failure_keeps_copy_and_paired_instagram(self):
        result={'metadata':{'title':'Saved title'},'paired_instagram':{'metadata':{'instagram_caption':'Saved caption'}}}
        with patch('hinglish_publish.discovery.build',side_effect=RuntimeError('Model unavailable')):
            reviewed=attach('.',result,None,'speech',{},[],{'discovery_review':True})
        self.assertEqual(reviewed['metadata'],result['metadata'])
        self.assertEqual(reviewed['paired_instagram'],result['paired_instagram'])
        self.assertEqual(reviewed['discovery']['status'],'needs_review')

    def test_real_builder_contract_keeps_full_creator_context_and_requires_grounding(self):
        brain=Mock();brain.json.side_effect=[self.plan(),{'approved':True,'issues':[]}]
        source='My first job brought me to Madurai, outside my comfort zone. I stayed.'
        context={'profile':'general','saved_guidance':'never delete this'}
        result=build(brain,'.',source,{'title':'My First Job in Madurai'},context,['creator voice'],lambda _:None,live_research=False)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['research']['status'],'disabled')
        self.assertEqual(brain.json.call_args_list[0].args[1]['creator_profile'],context)
        self.assertIn('Thumbnail wording:',brain.json.call_args_list[1].args[1]['draft']['description'])
        self.assertEqual(len(result['titles']),3)

    def test_rejected_grounding_cannot_be_presented_as_ready(self):
        brain=Mock();brain.json.side_effect=[self.plan(),{'approved':False,'issues':['Unsupported promise']},self.plan(),{'approved':False,'issues':['Unsupported promise']}]
        result=build(brain,'.','My first job brought me to Madurai, outside my comfort zone.',{'title':'My First Job'}, {},[],lambda _:None,live_research=False)
        self.assertEqual(result['status'],'needs_review')

    def test_research_uses_model_query_then_refines_from_observations(self):
        brain=Mock();brain.json.side_effect=[self.plan(),self.plan(),{'approved':True,'issues':[]}]
        source='My first job brought me to Madurai, outside my comfort zone.'
        with patch('hinglish_publish.discovery.research',return_value={
                'status':'observed','suggestions':['first job in Madurai'],'search_volume':None}) as lookup:
            result=build(brain,'.',source,{'title':'A much longer source title'}, {},[],lambda _:None)
        lookup.assert_called_once_with('.',self.plan()['primary_query'])
        self.assertEqual(brain.json.call_count,3)
        self.assertEqual(result['status'],'ready')


if __name__ == '__main__': unittest.main()
