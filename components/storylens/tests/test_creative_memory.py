import copy
import json
from pathlib import Path
import unittest

from hinglish_cut.creative_memory import MARKER, configure, context, inject

ROOT = Path(__file__).resolve().parents[1]


class CreativeMemoryTests(unittest.TestCase):
    def test_scoped_and_bounded(self):
        self.assertIsNone(context(ROOT, 'Schedule the saved clip tomorrow'))
        memory = context(ROOT, 'GSAP Hyperframes animation engine for smart visuals')
        self.assertIn('gsap-hyperframes', [r['id'] for r in memory['entries']])
        self.assertLess(len(json.dumps(memory)), 4500)

    def test_original_request_and_creator_profile_untouched(self):
        from hinglish_niche.profiles import inject as profile_inject, use
        creator = {'profile': 'gaming', 'name': 'Gaming', 'brief': 'Owner full guidance', 'feedback': 'Exact preference'}
        request = {'question': 'Use Taste design guidance for typography', 'words': ['do', 'not', 'rewrite']}
        original = copy.deepcopy(request)
        with use(creator):
            system, payload = profile_inject('Return this schema.', request, ROOT)
        self.assertIn(MARKER, system)
        self.assertEqual(payload['creator_profile'], creator)
        self.assertEqual(request, original)
        self.assertEqual(payload['words'], original['words'])

    def test_direct_vision_and_duplicate_injection(self):
        body = {'model': 'storylens-planner:9b-q6', 'messages': [
            {'role': 'system', 'content': 'Judge only observed pixels.'},
            {'role': 'user', 'content': 'Inspect the typography and spacing.', 'images': ['unchanged-base64']}]}
        configure(ROOT, body)
        first = copy.deepcopy(body)
        configure(ROOT, body)
        self.assertEqual(body, first)
        self.assertIn(MARKER, body['messages'][0]['content'])
        self.assertEqual(body['messages'][1]['images'], ['unchanged-base64'])

    def test_foreground_beats_tool_inventory(self):
        system, _ = inject('Tools include GSAP and OpenCut.', {'question': 'What time is it?'}, ROOT)
        self.assertNotIn(MARKER, system)

    def test_reference_hash_in_prompt_for_cache_invalidation(self):
        memory = context(ROOT, 'OpenCut timeline editor')
        system, _ = inject('Answer briefly.', 'OpenCut timeline editor', ROOT)
        self.assertIn(memory['revision'], system)
        self.assertIn('upcoming', system)


if __name__ == '__main__':
    unittest.main()
