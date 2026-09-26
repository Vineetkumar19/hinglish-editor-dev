"""Small, explicit real-model smoke test; not an accuracy benchmark."""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hinglish_semantic.core import SemanticSettings, verified, fact_concerns, cleanup_verdict
from hinglish_semantic.models import Verifier

root = Path(__file__).resolve().parents[1]
settings = SemanticSettings()
verifier = Verifier(settings, root)
cases = [
    ('user_paraphrase', 'match', True, {'expected': 'Aaj hum editing ke basics seekhenge.', 'spoken': 'Is video mein main aapko video edit karna sikhaunga.'}),
    ('negation', 'match', False, {'expected': 'Main video editing sikhaunga.', 'spoken': 'Main video editing nahi sikhaunga.'}),
    ('numbers', 'match', False, {'expected': 'Rider 40 rupees extra maangta hai.', 'spoken': 'Rider 60 rupees extra maangta hai.'}),
    ('roles', 'match', False, {'expected': 'Rider mujhse extra paise maangta hai.', 'spoken': 'Main rider se extra paise maangta hoon.'}),
    ('unrelated', 'match', False, {'expected': 'Aaj hum video editing seekhenge.', 'spoken': 'Aaj hum chicken biryani banayenge.'}),
    ('question_paraphrase', 'match', True, {'expected': 'Log mujhse sawal karte hain.', 'spoken': 'Log mujhe poochhate hain.'}),
    ('repeat_full', 'retake', True, {'earlier': 'Aaj hum video editing ka basic kaam seekhenge.', 'later': 'Aaj hum video editing ka basic kaam seekhenge.', 'context': 'One speaker stops, says sorry, and restarts the same sentence.'}),
    ('incomplete_retake', 'retake', False, {'earlier': 'Aaj hum video editing aur color correction seekhenge.', 'later': 'Aaj hum video editing aur...', 'context': 'The second attempt ends mid-sentence.'}),
    ('new_detail', 'retake', False, {'earlier': 'Rider extra paise maangta hai aur mana karne par ride cancel karta hai.', 'later': 'Rider extra paise maangta hai.', 'context': 'Adjacent sentences in a talking-head recording.'}),
    ('hesitation', 'filler', True, {'target': 'um', 'context': 'Aaj um hum video editing seekhenge.'}),
    ('surprise', 'filler', False, {'target': 'oh', 'context': 'Oh! Tum zinda ho! Mujhe laga tum mar gaye.'}),
    ('quiet_command', 'filler', False, {'target': 'shh', 'context': 'Shh! Bachcha so raha hai. Awaaz mat karo.'}),
]
results = []
try:
    for name, kind, expected, data in cases:
        started = time.monotonic()
        try:
            result = verifier.check(kind, **data)
            decision = verified(result, settings)
            if kind in ('filler', 'retake'):
                decision = cleanup_verdict(kind, result, settings, target=data.get('target', ''),
                                           earlier=data.get('earlier', ''), later=data.get('later', ''))
            if kind == 'match':
                decision = decision and not fact_concerns(data['expected'], data['spoken'])
            row = {'case': name, 'expected': expected, 'decision': bool(decision), 'passed': decision == expected,
                   'result': result, 'seconds': round(time.monotonic() - started, 2)}
        except Exception as error:
            row = {'case': name, 'passed': False, 'error': str(error)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        (root / 'validation' / 'phase2-model-check.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
finally:
    verifier.close()
print(f'{sum(r["passed"] for r in results)}/{len(results)} explicit model checks passed', flush=True)
