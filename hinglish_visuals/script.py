"""Your script, used to understand the speech: names the speech recogniser misheard ("Madhu rahi" -> Madurai,
"rapid ho" -> Rapido) get their script spelling. The script only fixes spellings; your spoken words and
timing stay (it may differ from what you really said)."""
from dataclasses import replace
from difflib import SequenceMatcher
import re

MERGE_SIMILARITY = .8


def _normal(text):
    return re.sub(r'[^a-z0-9]', '', str(text).casefold())


def script_names(script):
    """Capitalised words in the script that look like names (Madurai, Rapido, HCL, Zomato)."""
    clean = re.sub(r'\[[^\]]*\]', ' ', script or '')
    names = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", clean):
        if (token[0].isupper() and len(token) >= 4) or (token.isupper() and len(token) >= 2):
            if token not in names:
                names.append(token)
    return names


def apply_script(words, script):
    """-> (words, changes). Single words use the caption spelling fixer; two misheard words that together
    sound like one name in the script ("Madhu rahi") become that name."""
    if not (script or '').strip() or not words:
        return list(words), []
    from hinglish_captions.core import correct_with_reference
    fixed, changes = correct_with_reference(words, script)
    known = {_normal(n) for n in script_names(script)}
    keep = [c for c in changes if _normal(c['script_spelling']) in known]
    kept = {round(c['start'], 3) for c in keep}
    out = [replace(w, text=f.text) if round(w.start, 3) in kept else w for w, f in zip(words, fixed)]
    changes = keep
    changed = {round(c['start'], 3) for c in changes}
    names = [(n, _normal(n)) for n in script_names(script) if len(_normal(n)) >= 5]
    merged, i = [], 0
    while i < len(out):
        w = out[i]
        nxt = out[i + 1] if i + 1 < len(out) else None
        # only two real parts of a misheard name merge ("Madhu rahi"), never "ki North" or "ho, Zomato"
        mergeable = (nxt is not None and round(w.start, 3) not in changed and round(nxt.start, 3) not in changed
                     and min(len(_normal(w.text)), len(_normal(nxt.text))) >= 3
                     and _normal(w.text) not in known and _normal(nxt.text) not in known)
        if mergeable:
            joined = _normal(w.text + nxt.text)
            best = max(((SequenceMatcher(None, joined, key).ratio(), name) for name, key in names
                        if abs(len(key) - len(joined)) <= 3), default=(0, ''))
            if best[0] >= MERGE_SIMILARITY:
                tail = re.search(r'\W*$', nxt.text).group(0)
                merged.append(replace(w, text=best[1] + tail, end=nxt.end))
                changes.append({'heard': f'{w.text} {nxt.text}', 'script_spelling': best[1], 'start': w.start,
                                'end': nxt.end})
                i += 2
                continue
        merged.append(w)
        i += 1
    return merged, changes


def script_context(script, limit=3000):
    """The script as context for the AI (what the creator means), without camera directions."""
    return re.sub(r'\s+', ' ', re.sub(r'\[[^\]]*\]', ' ', script or '')).strip()[:limit]
