"""Contrast checks against the actual local model, not mocked verdicts."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json
from hinglish_semantic.local_judge import MeaningJudge
from hinglish_semantic.core import SemanticSettings

CASES = [
    ('Aaj hum editing ke basics seekhenge.', [
        'Is video mein main aapko video edit karna sikhaunga.',
        'Maine naya camera khareeda.',
        'Main aapko video edit karna nahi sikhaunga.'], ['complete', 'different', 'contradiction']),
    ('Madurai me Rapido book karna ek psychological warfare hai.', [
        'Madurai mein Rapido book karna ek alag struggle hai.',
        'Madurai mein Rapido book karna ek.',
        'Madurai mein Rapido book karna bahut aasaan hai.'], ['complete', 'partial', 'contradiction']),
    ('Bhaiya 40 rupee extra do, warna cancel.', [
        'Chaalis rupaye aur dene honge, nahi toh ride cancel.',
        'Saath rupaye extra do warna cancel.',
        'Chaalis rupaye extra dena.'], ['complete', 'contradiction', 'partial']),
    ('Koi club nahi. Koi lounge nahi. Late-night cafe bhool jao.', [
        'Yahan club lounge aur der raat ke cafe kuch bhi nahi milta.',
        'Late night cafe nahi hai.',
        'Yahan clubs aur lounge raat bhar khule hain.'], ['complete', 'partial', 'contradiction']),
]
judge = MeaningJudge(SemanticSettings(), ROOT)
results = []
try:
    for idea, candidates, expected in CASES:
        verdicts = judge.compare(idea, candidates)
        # A false-negative wording label is less severe than accepting a negative.
        passed = verdicts[0]['status'] == 'complete' and all(v['status'] != 'complete' for v in verdicts[1:])
        results.append({'idea': idea, 'candidates': candidates, 'expected': expected,
                        'verdicts': verdicts, 'passed': passed})
        print(json.dumps(results[-1], ensure_ascii=True), flush=True)
finally:
    judge.close()
(ROOT / 'validation/meaning-model-contrasts.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
assert all(r['passed'] for r in results), 'Model accepted an incomplete/contradictory option or rejected the paraphrase'
