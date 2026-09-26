"""Model guard: an AI answer that breaks a hard rule is sent back with the exact problems and asked again.

    answer = ask_checked(llm.json, system, data, schema, checker, label='B-roll moments', feature='broll')

`checker(answer)` returns a list of Problem. The best attempt (fewest hard, then soft problems) is used,
so a retry can never make the result worse. Every call is recorded; `save(folder)` writes
model-checks.json next to the feature's output for the quality report."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from . import tune

ATTEMPTS = 3
_journal = []


@dataclass
class Problem:
    rule: str
    message: str
    hard: bool = True


def _compact(answer, limit=6000):
    clean = {k: v for k, v in (answer or {}).items() if not str(k).startswith('_')}
    text = json.dumps(clean, ensure_ascii=False)
    return clean if len(text) <= limit else {'note': 'previous answer too long to repeat', 'start': text[:limit]}


def ask_checked(ask, system, data, schema, checker, label='AI answer', feature='', attempts=None,
                progress=print, repair=None, **ask_options):
    attempts = attempts or ATTEMPTS
    base = dict(data)
    earlier = tune.feedback(feature) if feature else []
    if earlier:
        base['quality_check_feedback'] = earlier       # what the output check found on the last run
    payload, best, tries = base, None, []
    for n in range(1, attempts + 1):
        answer = ask(system, payload, schema, **ask_options)
        problems = checker(answer)
        hard = [p for p in problems if p.hard]
        tries.append({'attempt': n, 'hard': len(hard), 'soft': len(problems) - len(hard),
                      'problems': [asdict(p) for p in problems[:40]]})
        if best is None or (len(hard), len(problems)) < best[0]:
            best = ((len(hard), len(problems)), answer, problems)
        if not hard:
            break
        if n < attempts:
            progress(f'  Quality check: {label} broke {len(hard)} rule(s); asking the model to fix them ({n}/{attempts - 1})')
            payload = {**base, 'your_previous_answer': _compact(answer),
                       'fix_these_problems': [p.message for p in hard][:20],
                       'instruction': 'Your previous answer broke the rules listed in fix_these_problems. Return '
                                      'the COMPLETE answer again, keeping everything that was right and fixing '
                                      'every listed problem. Follow all rules in the system message.'}
    (score, answer, problems) = best
    left = [p for p in problems if p.hard]
    repaired = []
    if left and repair is not None:
        # the model could not fix everything: apply the rules ourselves (drop/trim the items that break them)
        answer, repaired = repair(answer)
        problems = checker(answer)
        left = [p for p in problems if p.hard]
    if len(tries) > 1 or left or repaired:
        done = 'all rules met' + (f' ({len(repaired)} fix(es) applied by the rules)' if repaired else '')
        progress(f'  Quality check: {label}: ' + (done if not left else
                 f'{len(left)} problem(s) left after {len(tries)} tries (bad items are dropped)'))
    _journal.append({'label': label, 'feature': feature, 'tries': tries, 'repaired': repaired[:30],
                     'final_hard': len(left), 'final_soft': len(problems) - len(left),
                     'final_problems': [asdict(p) for p in left[:20]]})
    return answer


def save(folder):
    """Write this run's model checks next to the feature output and start a fresh record."""
    global _journal
    if _journal:
        path = Path(folder) / 'model-checks.json'
        path.write_text(json.dumps(_journal, ensure_ascii=False, indent=1), encoding='utf-8')
    _journal = []
