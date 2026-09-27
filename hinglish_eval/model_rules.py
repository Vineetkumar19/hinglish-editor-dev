"""The rules an AI answer must follow, per feature. Each builder returns checker(answer) -> [Problem].

Hard problems send the answer back to the model (see guard.py); soft ones are only reported."""
from .guard import Problem

HEAVY_EMOTIONS = ('sad', 'vulnerab', 'lonely', 'alone', 'serious', 'grief', 'hurt', 'tired', 'depress',
                  'emotional', 'regret', 'fear', 'pain', 'heartbroken', 'helpless', 'somber', 'melanchol')
PLAYFUL = ('poke', 'cute', 'retro', 'awkward', 'glitch')    # same tone rule as the sound director
from .text import (brands_in, english_share, is_filler, numbers_in, quote_share, text_words_in, tokens,
                   word_in)


def _items(answer, key):
    items = (answer or {}).get(key)
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


# ---- B-roll ----------------------------------------------------------------------------------------------
# Hindi / old names a speaker uses for places the model writes in English
PLACE_ALIASES = {'delhi': ['dilli', 'dehli'], 'mumbai': ['bambai', 'bombay'], 'kolkata': ['calcutta', 'kalkatta'],
                 'chennai': ['madras'], 'bengaluru': ['bangalore', 'banglore'], 'bangalore': ['bengaluru'],
                 'india': ['bharat', 'hindustan'], 'varanasi': ['banaras', 'kashi'], 'tamil': ['tamilnadu']}


def broll_summary(phrases):
    spoken = set(tokens(' '.join(p.text for p in phrases)))
    for name, aliases in PLACE_ALIASES.items():
        if any(a in spoken for a in aliases):
            spoken.add(name)

    def check(answer):
        out = []
        if not str((answer or {}).get('topic', '')).strip():
            out.append(Problem('broll.summary.topic', 'topic is empty: say in English what the video is about'))
        if not str((answer or {}).get('visual_world', '')).strip():
            out.append(Problem('broll.summary.visual_world', 'visual_world is empty: describe the filmable setting'))
        if english_share((answer or {}).get('topic', '')) < .8:
            out.append(Problem('broll.summary.english', 'topic must be written in English'))
        for place in (answer or {}).get('places', []) or []:
            if not any(t in spoken or any(s.startswith(t[:4]) for s in spoken if len(t) >= 4)
                       for t in tokens(place)):
                out.append(Problem('broll.summary.invented_place',
                                   f'place "{place}" is not mentioned in the transcript; list only places the '
                                   'speaker names or clearly implies', hard=False))
        return out
    return check


def broll_moments(phrases, count):
    by_id = {p.id: p for p in phrases}
    near = {p.id: ' '.join(q.text for q in phrases if abs(q.id - p.id) <= 1) for p in phrases}

    def check(answer):
        out, seen = [], set()
        items = _items(answer, 'moments')
        if not items:
            out.append(Problem('broll.moments.none', f'no moments returned; choose about {count} phrases'))
        for n, m in enumerate(items, 1):
            pid, ref = m.get('id'), f'moment {n} (id {m.get("id")})'
            if type(pid) is not int or pid not in by_id:
                out.append(Problem('broll.moments.id', f'{ref}: id is not one of the phrase ids given'))
                continue
            if pid in seen:
                out.append(Problem('broll.moments.duplicate', f'{ref}: phrase {pid} was chosen twice'))
            seen.add(pid)
            text = by_id[pid].text
            if quote_share(m.get('quote', ''), text) < .6:
                out.append(Problem('broll.moments.quote',
                                   f'{ref}: quote "{m.get("quote", "")}" is not copied from phrase {pid} '
                                   f'("{text}"). Copy 2-5 words exactly from THAT phrase, or use the id of the '
                                   'phrase you quoted'))
            queries = [str(q) for q in m.get('queries') or []]
            if len(queries) != 3:
                out.append(Problem('broll.moments.queries', f'{ref}: give exactly 3 search phrases', hard=False))
            for q in queries:
                found = brands_in(q)
                if found:
                    out.append(Problem('broll.moments.brand',
                                       f'{ref}: search phrase "{q}" contains the brand/app name {", ".join(found)}; '
                                       'stock sites do not know brands - describe the generic thing'))
                if not 2 <= len(tokens(q)) <= 5:
                    out.append(Problem('broll.moments.query_length', f'{ref}: "{q}" should be 2-4 words',
                                       hard=False))
            visual = str(m.get('visual', ''))
            if text_words_in(visual):
                out.append(Problem('broll.moments.text_visual',
                                   f'{ref}: visual "{visual}" shows written text/logos/captions; describe only '
                                   'what a camera can film'))
            invented = numbers_in(visual + ' ' + ' '.join(queries)) - numbers_in(near[pid])
            if invented:
                out.append(Problem('broll.moments.number',
                                   f'{ref}: numbers {", ".join(sorted(invented))} are not in the speech; never '
                                   'add numbers the speaker does not say'))
            if english_share(m.get('meaning', '')) < .8 or len(tokens(m.get('meaning', ''))) < 3:
                out.append(Problem('broll.moments.meaning',
                                   f'{ref}: meaning must be a plain-English translation of the quoted line'))
        if items and len(seen) < max(1, round(count * .5)):
            out.append(Problem('broll.moments.too_few',
                               f'only {len(seen)} moments; choose about {count} good cutaway moments '
                               '(places, foods, objects, actions)', hard=False))
        return out
    return check


# ---- Smart Zoom --------------------------------------------------------------------------------------------
def zoom_sections(phrases, count):
    by_id = {p.id: p for p in phrases}
    order = [p.id for p in phrases]
    span = max(1e-6, phrases[-1].end - phrases[0].start) if phrases else 1.0

    def check(answer):
        out, ranges = [], []
        items = _items(answer, 'sections')
        for n, s in enumerate(items, 1):
            a, b, word = s.get('from_id'), s.get('to_id', s.get('from_id')), str(s.get('word', ''))
            ref = f'section {n} (from_id {a})'
            if type(a) is not int or a not in by_id:
                out.append(Problem('zoom.sections.id', f'{ref}: from_id is not one of the phrase ids'))
                continue
            if type(b) is not int or b not in by_id or not a <= b <= a + 3:
                out.append(Problem('zoom.sections.to_id', f'{ref}: to_id must be the same phrase or at most 3 '
                                                          'phrases later'))
                b = a
            if not word_in(word, by_id[a].text):
                out.append(Problem('zoom.sections.word',
                                   f'{ref}: word "{word}" is not in phrase {a} ("{by_id[a].text}"); copy the '
                                   'stressed word exactly from that phrase'))
            elif is_filler(word):
                out.append(Problem('zoom.sections.filler', f'{ref}: "{word}" is a filler word; pick the key '
                                                           'noun, number or negation'))
            ranges.append((order.index(a), order.index(b), n))
        ranges.sort()
        for (a1, b1, n1), (a2, b2, n2) in zip(ranges, ranges[1:]):
            if a2 <= b1:
                out.append(Problem('zoom.sections.overlap',
                                   f'section {n1} (phrases {order[a1]}-{order[b1]}) and section {n2} (phrases '
                                   f'{order[a2]}-{order[b2]}) share phrases; each phrase may belong to at most one '
                                   'section - shorten one or remove the weaker one'))
            elif a2 == b1 + 1:
                out.append(Problem('zoom.sections.no_wide_gap', f'sections {n1} and {n2} touch; leave normal WIDE '
                                                                'talk between them', hard=False))
        zoomed = sum(by_id[order[i]].end - by_id[order[i]].start for a, b, _ in ranges for i in range(a, b + 1))
        if zoomed / span > .6:
            out.append(Problem('zoom.sections.too_much', f'{zoomed / span:.0%} of the time is zoomed; most of the '
                                                         'video must stay WIDE - keep only the strongest points'))
        if len(items) > count * 1.8 + 1:
            out.append(Problem('zoom.sections.too_many', f'{len(items)} sections; choose about {count}'))
        return out
    return check


# ---- Sound Design ------------------------------------------------------------------------------------------
def sound_analysis(lines, count, moods, families, short):
    by_id = {l.id: l for l in lines}
    ids = [l.id for l in lines]

    def check(answer):
        out = []
        described = {i.get('id') for i in _items(answer, 'lines')}
        missing = [i for i in ids if i not in described]
        if missing:
            out.append(Problem('sound.analysis.lines', f'lines {missing[:12]} have no emotion; give emotion, '
                                                       'intensity and role for EVERY line id'))
        music = sorted(_items(answer, 'music'), key=lambda s: (s.get('from_id') if type(s.get('from_id')) is int else 0))
        if not music:
            out.append(Problem('sound.analysis.music', 'no music sections; cover the whole video with sections'))
        else:
            if music[0].get('from_id') != ids[0] or music[-1].get('to_id') != ids[-1]:
                out.append(Problem('sound.analysis.music_cover', f'music must cover the whole video: first section '
                                                                 f'from_id {ids[0]}, last section to_id {ids[-1]}'))
            for s1, s2 in zip(music, music[1:]):
                end, start = s1.get('to_id'), s2.get('from_id')
                if type(end) is not int or type(start) is not int:
                    continue
                if start > end + 1:
                    out.append(Problem('sound.analysis.music_gap', f'no music between line {end} and line {start}; '
                                                                   'sections must follow each other'))
                elif start <= end:
                    out.append(Problem('sound.analysis.music_overlap', f'music sections overlap at line {start}'))
            for s in music:
                if s.get('mood') not in moods:
                    out.append(Problem('sound.analysis.mood', f'music mood "{s.get("mood")}" is not in the library'))
            if short and len(music) > 2:
                out.append(Problem('sound.analysis.music_count', f'{len(music)} music sections; a short Reel gets '
                                                                 'at most 2 (change only at the real emotional turn)'))
        moments = _items(answer, 'moments')
        palette = (answer or {}).get('palette', '')
        feel = {i.get('id'): str(i.get('emotion', '')).casefold() for i in _items(answer, 'lines')}
        kinds = []
        for n, m in enumerate(moments, 1):
            ref = f'moment {n} (id {m.get("id")})'
            line = by_id.get(m.get('id'))
            if line is None:
                out.append(Problem('sound.analysis.moment_id', f'{ref}: id is not a line id'))
                continue
            if not word_in(m.get('word', ''), line.text):
                out.append(Problem('sound.analysis.moment_word', f'{ref}: word "{m.get("word", "")}" is not in line '
                                                                 f'{line.id} ("{line.text}"); copy it exactly'))
            if quote_share(m.get('evidence', m.get('word', '')), line.text) < .6:
                out.append(Problem('sound.analysis.evidence', f'{ref}: evidence "{m.get("evidence", "")}" is not in '
                                                              f'line {line.id}; every sound needs a reason in the '
                                                              'exact words - no reason, no sound'))
            if m.get('type') not in families:
                out.append(Problem('sound.analysis.moment_type', f'{ref}: type "{m.get("type")}" does not exist'))
            if palette != 'comedic' and m.get('type') in PLAYFUL and \
                    any(h in feel.get(line.id, '') for h in HEAVY_EMOTIONS):
                out.append(Problem('sound.analysis.tone', f'{ref}: a playful {m.get("type")} sound on a '
                                                          f'{feel.get(line.id)} line; use a soft boom, a riser or '
                                                          'nothing', hard=False))
            kinds.append(m.get('type'))
        pulls = sum(bool(m.get('pull_back')) for m in moments)
        if pulls > (1 if short else 2):
            out.append(Problem('sound.analysis.pull_back', f'pull_back is true on {pulls} moments; use it only for '
                                                           'the single biggest reveal'))
        if len(moments) > count + 1:
            out.append(Problem('sound.analysis.too_many', f'{len(moments)} sound moments; at most {count} - keep '
                                                          'only the moments with a real trigger in the words'))
        for a, b, c in zip(kinds, kinds[1:], kinds[2:]):
            if a == b == c:
                out.append(Problem('sound.analysis.variety', f'type "{a}" three times in a row; vary the effects',
                                   hard=False))
                break
        return out
    return check


def sound_pick(moments, effect_candidates, sections, music_candidates):
    def check(answer):
        out = []
        effects = {p.get('moment'): p for p in _items(answer, 'effects')}
        for i, cands in enumerate(effect_candidates):
            p = effects.get(i)
            if p is None:
                out.append(Problem('sound.pick.missing', f'moment {i} has no pick; answer for every moment',
                                   hard=False))
            elif not isinstance(p.get('choice'), int) or not -1 <= p['choice'] < len(cands):
                out.append(Problem('sound.pick.choice', f'moment {i}: choice {p.get("choice")} is not a candidate '
                                                        f'number (0-{len(cands) - 1}, or -1 for none)'))
        music = {p.get('section'): p for p in _items(answer, 'music')}
        for i, cands in enumerate(music_candidates):
            p = music.get(i)
            if cands and (p is None or not isinstance(p.get('choice'), int) or not 0 <= p['choice'] < len(cands)):
                out.append(Problem('sound.pick.music', f'music section {i} needs a choice between 0 and '
                                                       f'{len(cands) - 1}'))
        return out
    return check


# ---- Repairs: when the model cannot fix an answer, the rules fix it (never invent, only drop/trim) ------------
def zoom_repair(phrases):
    by_id = {p.id: p for p in phrases}
    order = [p.id for p in phrases]
    span = max(1e-6, phrases[-1].end - phrases[0].start) if phrases else 1.0

    def repair(answer):
        kept, taken, notes, zoomed = [], set(), [], 0.0
        items = _items(answer, 'sections')
        ranked = sorted(range(len(items)), key=lambda i: (-(items[i].get('strength') or 0), i))
        for i in ranked:
            s = items[i]
            a, b = s.get('from_id'), s.get('to_id', s.get('from_id'))
            if a not in by_id or not word_in(s.get('word', ''), by_id[a].text) or is_filler(s.get('word', '')):
                notes.append(f'dropped section {i + 1}: word not in its phrase')
                continue
            if b not in by_id or not a <= b <= a + 3:
                b = a
            lo, hi = order.index(a), order.index(b)
            while hi > lo and any(j in taken for j in range(lo - 1, hi + 2)):
                hi -= 1                                   # trim the end until it no longer touches another point
            if any(j in taken for j in range(lo - 1, hi + 2)):
                notes.append(f'dropped section {i + 1}: overlaps a stronger point')
                continue
            length = sum(by_id[order[j]].end - by_id[order[j]].start for j in range(lo, hi + 1))
            if (zoomed + length) / span > .5:
                notes.append(f'dropped section {i + 1}: the video must stay mostly wide')
                continue
            if order[hi] != b:
                notes.append(f'trimmed section {i + 1} to end at phrase {order[hi]}')
            taken.update(range(lo, hi + 1))
            zoomed += length
            kept.append({**s, 'to_id': order[hi]})
        kept.sort(key=lambda s: order.index(s['from_id']))
        return {**(answer or {}), 'sections': kept}, notes
    return repair


def broll_repair(phrases):
    by_id = {p.id: p for p in phrases}
    near = {p.id: ' '.join(q.text for q in phrases if abs(q.id - p.id) <= 1) for p in phrases}

    def repair(answer):
        kept, seen, notes = [], set(), []
        for n, m in enumerate(_items(answer, 'moments'), 1):
            pid = m.get('id')
            if pid not in by_id or pid in seen or quote_share(m.get('quote', ''), by_id[pid].text) < .6:
                notes.append(f'dropped moment {n}: not tied to its own line')
                continue
            if text_words_in(m.get('visual', '')) or english_share(m.get('meaning', '')) < .8:
                notes.append(f'dropped moment {n}: visual not filmable or meaning not in English')
                continue
            if numbers_in(m.get('visual', '')) - numbers_in(near[pid]):
                notes.append(f'dropped moment {n}: invented a number')
                continue
            queries = [q for q in m.get('queries') or [] if not brands_in(q)
                       and not numbers_in(q) - numbers_in(near[pid])]
            if not queries:
                notes.append(f'dropped moment {n}: no usable search phrase')
                continue
            if len(queries) < len(m.get('queries') or []):
                notes.append(f'moment {n}: removed search phrases with brands or invented numbers')
            seen.add(pid)
            kept.append({**m, 'queries': queries})
        return {**(answer or {}), 'moments': kept}, notes
    return repair


def sound_repair(lines, families, count=99, short=True):
    by_id = {l.id: l for l in lines}

    def repair(answer):
        answer = dict(answer or {})
        notes, kept = [], []
        for n, m in enumerate(_items(answer, 'moments'), 1):
            line = by_id.get(m.get('id'))
            if line is None or m.get('type') not in families or not word_in(m.get('word', ''), line.text):
                notes.append(f'dropped sound moment {n}: its word is not in its line')
                continue
            if quote_share(m.get('evidence', m.get('word', '')), line.text) < .6:
                notes.append(f'dropped sound moment {n}: no reason in the words of its line')
                continue
            kept.append(m)
        if len(kept) > count:
            ranked = sorted(kept, key=lambda m: -(m.get('strength') or 0))[:count]
            notes.append(f'kept the {count} strongest of {len(kept)} sound moments (budget)')
            kept = [m for m in kept if m in ranked]
        pulls, limit = 0, 1 if short else 2
        for i, m in enumerate(kept):
            if m.get('pull_back'):
                if pulls >= limit:
                    kept[i] = {**m, 'pull_back': False}
                    notes.append(f'pull-back removed on "{m.get("word")}" (max {limit})')
                pulls += 1
        answer['moments'] = kept
        described = {i.get('id') for i in _items(answer, 'lines')}
        missing = [l.id for l in lines if l.id not in described]
        if missing:
            answer['lines'] = _items(answer, 'lines') + [
                {'id': i, 'emotion': 'neutral', 'intensity': 1, 'role': 'filler'} for i in missing]
            notes.append(f'{len(missing)} line(s) without an emotion set to neutral')
        return answer, notes
    return repair



# ---- Smart Visuals: only things the speaker really names ---------------------------------------------------
def _named_where(entity, phrases, mentions):
    """Ids of the phrases that name this entity (its name, or a mention copied from that phrase)."""
    words = [t for t in tokens(entity.get('name', '')) if len(t) > 3]
    found = set()
    for p in phrases:
        have = tokens(p.text)
        if any(w in have or any(len(h) >= 4 and (h.startswith(w[:5]) or w.startswith(h[:5])) for h in have)
               for w in words):
            found.add(p.id)
    for pid, mention in mentions:
        # a naming word only counts when it sounds like THIS name ("Jomato" = Zomato, "Kamilnaadu" = Tamil
        # Nadu, but "Kamilnaadu" is not Karnataka); nicknames still work when the real name is said somewhere
        if mention and word_in(mention, next((p.text for p in phrases if p.id == pid), ''))                 and sounds_like(mention, entity.get('name', '')):
            found.add(pid)
    return found


def sounds_like(mention, name, threshold=.72):
    from difflib import SequenceMatcher
    a, b = ''.join(tokens(mention)), ''.join(tokens(name))
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    said = set(tokens(mention))
    if any(key in tokens(name) and said & set(aliases) for key, aliases in PLACE_ALIASES.items()):
        return True                                    # Hindi / old names: "Dilli" = Delhi, "Bambai" = Mumbai
    parts = [t for t in tokens(name) if len(t) > 3] + [b]
    return any(SequenceMatcher(None, a, part).ratio() >= threshold for part in parts)


def visuals_plan(group, phrases, known):
    """known: entities found in earlier parts of the video (key -> dict)."""
    from hinglish_broll.planner import phrase_for_quote      # (local import: the planners import this module)
    order = {p.id: n for n, p in enumerate(phrases)}

    def line_of(m):
        """Like the planner: the quote decides the line (the id is only a hint)."""
        hint = m.get('id') if type(m.get('id')) is int else None
        return phrase_for_quote(m.get('quote', ''), group, hint)

    def check(answer):
        out = []
        entities = {**{k: v for k, v in known.items()}}
        for e in _items(answer, 'entities'):
            if e.get('key'):
                entities.setdefault(str(e['key']).casefold(), e)
        moments = _items(answer, 'moments')
        mentions = {}
        for m in moments:
            line = line_of(m)
            if line is not None and str(m.get('mention', '')).strip():
                mentions.setdefault(str(m.get('entity', '')).casefold(), []).append((line.id, m['mention']))
        named = {k: _named_where(e, phrases, mentions.get(k, [])) for k, e in entities.items()}
        for key, e in entities.items():
            if key not in known and not named[key]:
                out.append(Problem('visuals.entity_not_said',
                                   f'entity "{e.get("name")}" is never said in the speech; choose only people, '
                                   'brands, places and events the speaker really names (never guess a place)'))
        for n, m in enumerate(moments, 1):
            ref = f'moment {n} (id {m.get("id")}, entity {m.get("entity")})'
            line = line_of(m)
            key = str(m.get('entity', '')).casefold()
            if line is None:
                out.append(Problem('visuals.quote', f'{ref}: quote "{m.get("quote")}" is not copied from any '
                                                    'phrase; copy 2-5 words exactly from the line you mean'))
                continue
            if key not in entities:
                out.append(Problem('visuals.entity', f'{ref}: entity key is not in your entities list'))
                continue
            mention = str(m.get('mention', '')).strip()
            if mention and not word_in(mention, line.text):
                out.append(Problem('visuals.mention', f'{ref}: mention "{mention}" is not in phrase {line.id} '
                                                      f'("{line.text}"); copy the naming word exactly, or use ""'))
            elif not mention and not any(order.get(pid, 1e9) <= order.get(line.id, -1) for pid in named.get(key, ())):
                out.append(Problem('visuals.unnamed_line',
                                   f'{ref}: this line does not name {entities[key].get("name")} and it was not '
                                   'named before it; attach a line only to what it is really about'))
        return out
    return check


def visuals_repair(group, phrases, known):
    checker = visuals_plan(group, phrases, known)

    def repair(answer):
        answer = dict(answer or {})
        notes = []
        problems = checker(answer)
        bad_names = {p.message.split('"')[1] for p in problems if p.rule == 'visuals.entity_not_said'}
        keep_entities = []
        for e in _items(answer, 'entities'):
            if e.get('name') in bad_names:
                notes.append(f'dropped "{e.get("name")}": never said in the speech')
            else:
                keep_entities.append(e)
        dropped_keys = {str(e.get('key', '')).casefold() for e in _items(answer, 'entities') if e.get('name') in bad_names}
        answer['entities'] = keep_entities
        moments = [m for m in _items(answer, 'moments') if str(m.get('entity', '')).casefold() not in dropped_keys]
        problems = [p for p in checker({**answer, 'moments': moments}) if p.hard and p.message.startswith('moment ')]
        bad = {int(p.message.split()[1]): p.rule for p in problems}
        kept = []
        for n, m in enumerate(moments, 1):
            if n in bad:
                notes.append(f'dropped moment "{m.get("quote")}": {bad[n]}')
            else:
                kept.append(m)
        answer['moments'] = kept
        return answer, notes
    return repair
