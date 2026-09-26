"""Run a feature, check its result against the spec, and redo it with corrections until the rules pass.

    python -m hinglish_eval run --attempts 3 -- -m hinglish_sound --root . --input timeline.xml

Each attempt gets a tune file (HINGLISH_EVAL_TUNE) with the corrections the failed rules asked for, e.g.
louder effects, fewer zooms, more B-roll moments, and plain-English feedback that the feature's AI model
reads. The best attempt wins; its folder gets quality-check.html + quality-check.json."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import uuid

from .report import FEATURE_NAME, write_report
from .specs import Check, Evaluation, check_xml, evaluate

FEATURE_OF_MODULE = {'hinglish_clean': 'clean', 'hinglish_captions': 'captions', 'hinglish_broll': 'broll',
                     'hinglish_zoom': 'zoom', 'hinglish_sound': 'sound', 'hinglish_eyecontact': 'eyecontact',
                     'hinglish_semantic': 'script', 'hinglish_visuals': 'visuals'}
LIMITS = {'count_scale': (.4, 2.5), 'effect_gain_db': (-6.0, 10.0), 'music_trim_db': (-10.0, 6.0)}


def merge(tune, fixes, feature):
    """Scales multiply, dB values add, feedback is replaced by the latest findings."""
    tune = json.loads(json.dumps(tune))
    notes = []
    for fix in fixes:
        for key, values in fix.items():
            if key == 'feedback':
                notes += values
                continue
            part = tune.setdefault(key, {})
            for name, v in values.items():
                if name.endswith('_scale'):
                    part[name] = part.get(name, 1.0) * v
                elif name.endswith('_db'):
                    part[name] = part.get(name, 0.0) + v
                else:
                    part[name] = v
                lo, hi = LIMITS.get(name, (-1e9, 1e9))
                part[name] = round(min(hi, max(lo, part[name])), 3)
    if notes:
        tune.setdefault(feature, {})['feedback'] = list(dict.fromkeys(notes))
    return tune


def _generic(folder):
    """Features without a dedicated spec still get their timelines checked."""
    xmls = sorted(Path(folder).rglob('*.xml'))
    if not xmls:
        return []
    checks = [c for x in xmls[:6] for c in check_xml(x)]
    return [Evaluation('script', str(folder), checks)]


def _rank(entry):
    evals = entry.get('evaluations') or []
    if entry.get('error') or not evals:
        return (0, -999, 0)
    hard = sum(len(e.hard_failed) for e in evals)
    return (1 if hard == 0 else 0.5, -hard, min(e.score for e in evals))


def run(root, command, attempts=3, progress=print):
    root = Path(root).resolve()
    module = command[command.index('-m') + 1] if '-m' in command else ''
    feature = FEATURE_OF_MODULE.get(module, module)
    name = FEATURE_NAME.get(feature, feature)
    work = root / 'cache' / 'eval'
    work.mkdir(parents=True, exist_ok=True)
    tune, history = {}, []
    for n in range(1, attempts + 1):
        tune_file = work / f'tune-{uuid.uuid4().hex[:8]}.json'
        tune_file.write_text(json.dumps({'attempt': n, **tune}, indent=1), encoding='utf-8')
        if n > 1:
            progress(f'Quality check: redoing {name} with corrections (attempt {n}/{attempts})')
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'HINGLISH_EVAL_TUNE': str(tune_file)}
        process = subprocess.Popen([sys.executable, '-u', *command], cwd=str(root), env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        result = None
        for line in process.stdout:
            found = re.search(r'Results:\s*(.+?)\s*$', line)
            if found:
                result = Path(found.group(1).strip())
                continue                         # the runner prints the chosen result at the end
            print(line, end='', flush=True)
        code = process.wait()
        tune_file.unlink(missing_ok=True)
        entry = {'attempt': n, 'fixes': {k: v for k, v in tune.items()}, 'result': str(result) if result else ''}
        if code not in (0, 2) or result is None or not result.exists():
            entry['error'] = f'{name} stopped (code {code})'
            history.append(entry)
            break                                # an engine error is not a quality problem: never loop on it
        folder = result if result.is_dir() else result.parent
        evals = evaluate(folder) or _generic(folder)
        entry['evaluations'], entry['folder'] = evals, str(folder)
        history.append(entry)
        for e in evals:
            failed = e.hard_failed
            progress(f'Quality check: {FEATURE_NAME.get(e.feature, e.feature)} {e.score}/100 - ' +
                     ('all rules passed' if not failed else f'{len(failed)} rule(s) failed: ' +
                      '; '.join(f'{c.title} ({c.value})' for c in failed[:4])))
        if all(e.passed for e in evals):
            break
        fixes = [c.fix for e in evals for c in e.checks if not c.passed and c.fix]
        if not fixes:
            progress('Quality check: these problems have no automatic correction; keeping the best result')
            break
        if n < attempts:
            tune = merge(tune, fixes, feature)
    good = [h for h in history if h.get('evaluations')]
    if not good:
        err = history[-1].get('error', 'no result') if history else 'no result'
        print(f'Error: {err}', flush=True)
        return None
    best = max(range(len(history)), key=lambda i: _rank(history[i]))
    chosen = history[best]
    pages = [{**h, 'evaluations': [e.to_dict() for e in h.get('evaluations', [])]} for h in history]
    folder = Path(chosen['folder'])
    page = write_report(folder / 'quality-check.html', pages, best)
    (folder / 'quality-check.json').write_text(json.dumps({'chosen_attempt': chosen['attempt'], 'attempts': pages},
                                                          ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    passed = all(e.passed for e in chosen['evaluations'])
    progress(f'Quality check: using attempt {chosen["attempt"]} - ' + ('all rules passed' if passed else
             'best result; some rules still fail (see the quality report)') + f' · {page}')
    print(f'Results: {chosen["result"]}', flush=True)
    return Path(chosen['result'])


def check_folder(folder, progress=print):
    folder = Path(folder)
    evals = evaluate(folder) or _generic(folder)
    if not evals:
        raise ValueError(f'No feature result found in {folder}')
    pages = [{'attempt': 1, 'evaluations': [e.to_dict() for e in evals]}]
    page = write_report(folder / 'quality-check.html', pages, 0)
    for e in evals:
        progress(f'{FEATURE_NAME.get(e.feature, e.feature)}: {e.score}/100 - ' +
                 ('all rules passed' if e.passed else f'{len(e.hard_failed)} rule(s) failed'))
        for c in e.checks:
            if not c.passed:
                progress(f'   {"FAIL" if c.hard else "note"}  {c.title}: {c.value}')
    return page
