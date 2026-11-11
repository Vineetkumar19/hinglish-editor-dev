"""Small CPU-only regression checks; no model, media or host execution."""
import builtins
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch


class AnalysisReached(Exception):
    pass


class SoundEventEvidenceTests(unittest.TestCase):
    def setUp(self):
        original_import = builtins.__import__

        def limited_import(name, *args, **kwargs):
            if name.split('.')[0] in {
                    'torch', 'transformers', 'numpy', 'av', 'requests', 'llama_cpp'}:
                raise AssertionError('Heavy/model/media import forbidden in this test: ' + name)
            return original_import(name, *args, **kwargs)

        self.import_guard = patch('builtins.__import__', side_effect=limited_import)
        self.import_guard.start()
        self.addCleanup(self.import_guard.stop)

    def captured_plan_events(self, observations=(), raw=()):
        from hinglish_sound.recommendation_pipeline import LocalRuntime
        runtime = LocalRuntime.__new__(LocalRuntime)  # Never construct real adapters.
        runtime.root = Path(__file__).resolve().parents[1]
        runtime.raw_events = list(raw)
        runtime.observations = list(observations)
        runtime.proxy = object()
        runtime.lines = []
        runtime.progress = lambda *args: None
        captured = []

        def stop_before_model(*args, **kwargs):
            captured.extend(args[4])
            raise AnalysisReached()

        with patch('hinglish_sound.composition.policy', return_value={}), \
                patch('hinglish_sound.learning.load', return_value={}), \
                patch('hinglish_sound.learning.taste', return_value={}), \
                patch('hinglish_sound.director.analyse', side_effect=stop_before_model):
            with self.assertRaises(AnalysisReached):
                runtime._plan({'prepare': {'duration': 10.}, 'inventory': {
                    'moods': [], 'families': []}, 'density': 'low',
                    'prosody': [], 'script': ''})
        return captured

    def test_actual_saved_long_ambience_retains_its_confidence(self):
        source = (Path(__file__).resolve().parents[1] / 'output' /
                  'sound-recommendations/20261025-064938-f348668ccc/scene-evidence.json')
        observation = json.loads(source.read_text('utf-8-sig'))['observations'][1]
        self.assertGreater(len(observation['ambience']), 160)
        events = self.captured_plan_events([observation])
        ambience = next(event for event in events if event['kind'] == 'ambience')
        self.assertEqual(ambience.get('confidence'), observation['confidence'])
        self.assertEqual(ambience['label'], observation['ambience'].strip()[:160])

    def test_distinct_phases_cannot_borrow_each_others_confidence(self):
        raw = [dict(time=1., end=2., kind='foley', label='observed movement',
                    phase=phase, confidence=confidence, sound_evidence=phase)
               for phase, confidence in [('entrance', .4), ('exit', .9)]]
        events = self.captured_plan_events(raw=raw)
        self.assertEqual([(e['phase'], e.get('confidence'), e.get('sound_evidence'))
                          for e in events], [('entrance', .4, 'entrance'), ('exit', .9, 'exit')])

    def test_normalized_identity_and_first_duplicate_are_preserved(self):
        from hinglish_sound.events import normalize, normalize_evidence
        raw = [dict(time=1.234567, end=3., kind='ambience', label='x' * 180,
                    confidence=.8, sound_evidence='first', arbitrary='excluded'),
               dict(time=1.234567, end=4., kind='ambience', label='x' * 190,
                    confidence=.99, sound_evidence='second')]
        before = copy.deepcopy(raw)
        result = normalize_evidence(raw, 10.)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['confidence'], .8)
        self.assertEqual(result[0]['sound_evidence'], 'first')
        ordinary = {k: v for k, v in result[0].items()
                    if k not in ('confidence', 'sound_evidence')}
        self.assertEqual(ordinary, normalize(raw, 10.)[0])
        self.assertNotIn('arbitrary', result[0])
        self.assertEqual(raw, before)

    def test_invalid_rows_and_missing_confidence_cannot_supply_evidence(self):
        from hinglish_sound.events import normalize_evidence
        result = normalize_evidence([
            {'time': -1., 'kind': 'foley', 'label': 'movement', 'confidence': 1.},
            {'time': 1., 'kind': 'foley', 'label': 'movement'}, None], 10.)
        self.assertEqual(len(result), 1)
        self.assertNotIn('confidence', result[0])

    def test_generator_input_keeps_event_order_and_intervals(self):
        from hinglish_sound.events import normalize, normalize_evidence
        raw = [dict(time=t, end=t + .5, kind='foley', label=str(t), confidence=.9)
               for t in (4., 1., 3.)]
        result = normalize_evidence(iter(raw), 10.)
        self.assertEqual([{k: v for k, v in e.items() if k != 'confidence'} for e in result],
                         normalize(raw, 10.))


if __name__ == '__main__':
    unittest.main()
