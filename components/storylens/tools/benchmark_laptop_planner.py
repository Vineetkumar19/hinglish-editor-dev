"""Check real editor planning contracts without executing edits or publishing."""
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--think', action='store_true')
    args = parser.parse_args()
    from hinglish_app.assistant_plan import plan
    from hinglish_visuals.brain import OllamaBrain
    class BenchmarkBrain(OllamaBrain):
        def __init__(self, root, model):
            # Benchmarks must use their explicit candidate even when its name
            # equals the project's legacy default and a laptop override exists.
            with patch('hinglish_cut.model_preferences.resolve_model',
                       lambda root, role, requested, legacy: requested):
                super().__init__(root, model)

        def json(self, system, data, schema, max_tokens=2400, think=False):
            from hinglish_cut.model_preferences import preferences
            local = dict(preferences(self.root), planning_think=False)
            with patch('hinglish_cut.model_preferences.preferences', return_value=local):
                return super().json(system, data, schema, max_tokens=max_tokens, think=args.think)
    cases = [
        ('clean_captions', 'Clean these clips, combine them in order, then add Typography 4 captions.', ['clean', 'captions']),
        ('hinglish_request', 'Mere video ke unnecessary pauses hata do, phir Typography 4 mein captions lagaa do.', ['clean', 'captions']),
        ('negated_tool', 'Do not add captions. Just remove the silent parts from my video.', ['clean']),
        ('followup', 'Now add smooth subtle zooms to the finished video.', ['zoom']),
        ('help_only', 'How can I make short clips for Instagram?', []),
    ]
    folder = ROOT / 'output/validation/new-laptop'
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for name, message, expected in cases:
        started = time.monotonic()
        entry = {'case': name, 'request': message, 'expected_tools': expected}
        try:
            with patch('hinglish_visuals.brain.open_brain', lambda root, *a, **kw: BenchmarkBrain(root, args.model)):
                value, brain = plan(ROOT, message, [], [{'name': 'fixture.mp4', 'kind': 'video'}], name == 'followup')
            tools = [row['tool'] for row in value['steps']]
            entry.update(plan=value, brain=brain)
            if tools != expected:
                raise ValueError('Unexpected tool sequence: ' + str(value))
            if name == 'clean_captions' and not value['combine']:
                raise ValueError('Requested ordered combination was not selected')
            if name in ('clean_captions', 'hinglish_request') and value['steps'][-1]['options'].get('caption_style') != 'typography_4':
                raise ValueError('Wrong requested caption style')
            entry.update(passed=True, plan=value, brain=brain)
        except Exception as error:
            entry.update(passed=False, error=f'{type(error).__name__}: {error}')
        entry['seconds'] = round(time.monotonic() - started, 2)
        results.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        suffix = '-thinking' if args.think else ''
        (folder / ('planner-' + args.model.replace(':', '-') + suffix + '.json')).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0 if all(row['passed'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
