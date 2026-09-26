"""The sound director: a thinking local model reads the video (words + voice + edit) with the
sound-design brain's rules, then picks real files from retrieved candidates (RAG)."""

from hinglish_eval import guard, model_rules

RULES = '''SOUND DESIGN RULES (how a professional sound editor "spots" a talking-head video):
1. Dialogue is king. Every sound must have a REASON in the words; no reason, no sound. Silence and the
   music bed carry most of the video. A sound that is not motivated makes a video feel cheap.
2. Spot only real triggers, and name the trigger and its evidence (the exact words that prove it):
   punchline (a joke lands) | reveal (the answer or twist) | shocking_fact | number_or_price | money |
   list_item (one per item in a spoken list) | app_or_device (Zomato, Instagram, phone, laptop) |
   message_or_notification | new_place_or_time_jump ("Mumbai se Delhi", "5 saal baad") | topic_change |
   failure_or_rejection | success_or_win | realisation | tension_or_worry | confusion_or_broken |
   something_gone | question_hook (a question that makes the viewer wait for the answer).
3. The sound must match the TONE of that exact line, read from its words AND how it is said:
   - sad, vulnerable, serious, lonely lines: at most a soft low boom or a gentle riser; never pops, dings,
     game or cartoon sounds; often nothing at all (let the music carry it).
   - funny lines: playful sounds are welcome (pop, boing only in a comedic video, record scratch for fails).
   - excited, energetic lines: punchy hits, whooshes, bright dings.
   - informational lines: clean subtle UI sounds (click, pop, soft whoosh), never dramatic booms.
4. Effect types and what they are for:
   whoosh = movement, a new place/time, a topic change | impact = punchline, reveal, shocking fact, the big
   word | riser = tension building INTO a reveal (ends on the reveal word) | poke = apps, phones, clicks,
   list items, notifications | cute = small win, warm realisation (ding, chime, sparkle) | retro = money,
   coins, prices, score, level up | awkward = failure, rejection, embarrassment (buzzer, record scratch) |
   suspense = worry, time pressure (heartbeat, ticking) | glitch = confusion, something broken, tech |
   vanish = something gone or wasted.
5. PULL BACK AND PUNCH: before the single biggest reveal, the music dips into a vacuum and a low boom lands
   on the key word. At most once per Reel.
6. MUSIC is one instrumental bed chosen by the video's overall emotion and energy (never songs with
   singing: they fight the words). Change it only at a real emotional turn (at most once in a Reel).
7. Fewer, better sounds: about {count} designed sounds for this whole video. B-roll cuts and zoom landings
   already have sounds (listed as editing events): do not add sounds on top of them.
8. A sound lands on the exact word: copy that word exactly from the line.

EXAMPLES (Hinglish lines -> what a pro does):
- "Aur phir maine Zomato khola" -> app_or_device, evidence "Zomato khola", poke: soft phone tap, on "Zomato".
- "Teen cheezein chahiye: laptop, mic aur light" -> list_item x3, poke: one soft pop on each item.
- "Aur result? Zero." (serious) -> reveal, impact: deep cinematic boom on "Zero", pull_back true.
- "Mujhe laga main jeet gaya... par nahi" (funny) -> failure_or_rejection, awkward: record scratch on "nahi".
- "Main bahut akela feel kar raha tha" (sad) -> NO effect; the music carries it.
- "Mumbai se seedha Delhi" -> new_place_or_time_jump, whoosh on "Delhi".
- "500 rupaye bach gaye" (happy) -> money, retro: coin sound on "500".'''

ANALYSIS_SYSTEM = RULES + '''

You are the sound director for this {kind}. You get the lines of the video (with how each one is
SAID), the editing events, and the music moods and effect types that exist in the library.
Think carefully first (what is the story, how does the speaker feel line by line, where is the
emotional turn, which few moments truly deserve sound), then answer:
- story: what happens and the emotional arc, in English (max 60 words)
- palette: the overall sound palette
- lines: for EVERY line id: emotion (one or two words), intensity 1-3, role in the story
- music: the music sections (from_id..to_id covering the whole video, in order), each with a mood from
  the available moods, energy 1-3 and why
- moments: at most {count} designed sounds, only on real triggers: id, trigger, evidence (the exact words
  from that line that prove the trigger), the exact word it lands on, the effect type, intent (the exact
  sound in plain words, e.g. "deep cinematic boom", "soft phone tap", "clock ticking"), strength 1-3,
  pull_back (true only for the single biggest reveal) and why (tone of the line + why this sound).
{preferences}'''

PICK_SYSTEM = '''You are the sound editor. For each moment you get the director's intent and the real
candidate files retrieved from the library. Each file says what it SOUNDS like (a listening model heard
it) plus its type, genre, length, shape and quality. Trust "sounds like" over the file name. Pick the ONE
candidate that best matches the intent AND the tone of that line: prefer professional studio sounds,
punchy short hits for impacts, crisp short sounds for pops and clicks, a riser that builds up, never a
cartoon/silly sound in a serious or emotional story. If none fits, answer -1.
Do the same for each music section: an instrumental bed (never one marked HAS SINGING) whose energy
fits the section, without a strong lead melody that competes with talking.
Write why first, then the choice.'''

# Which effect types may answer which trigger (a pro never puts a coin sound on a joke).
TRIGGERS = {
    'punchline': ('impact', 'awkward', 'cute'), 'reveal': ('impact', 'riser'), 'shocking_fact': ('impact', 'riser'),
    'number_or_price': ('retro', 'poke', 'impact'), 'money': ('retro',), 'list_item': ('poke',),
    'app_or_device': ('poke', 'glitch'), 'message_or_notification': ('poke',),
    'new_place_or_time_jump': ('whoosh',), 'topic_change': ('whoosh',),
    'failure_or_rejection': ('awkward', 'vanish'), 'success_or_win': ('cute', 'retro'),
    'realisation': ('cute', 'impact'), 'tension_or_worry': ('suspense', 'riser'),
    'confusion_or_broken': ('glitch', 'awkward'), 'something_gone': ('vanish',), 'question_hook': ('riser', 'whoosh'),
}
HEAVY_EMOTIONS = ('sad', 'vulnerab', 'lonely', 'alone', 'serious', 'grief', 'hurt', 'tired', 'depress', 'emotional',
                  'regret', 'fear', 'pain', 'heartbroken', 'helpless', 'somber', 'melanchol')
PLAYFUL = ('poke', 'cute', 'retro', 'awkward', 'glitch')    # never on a heavy line in a non-comedic video

ROLES = ['hook', 'setup', 'conflict', 'realisation', 'punchline', 'twist', 'resolution', 'call_to_action',
         'filler']
PALETTES = ['serious', 'emotional', 'comedic', 'energetic', 'informational']


def analysis_schema(moods, families):
    return {'type': 'object', 'properties': {
        'story': {'type': 'string', 'maxLength': 500},
        'palette': {'type': 'string', 'enum': PALETTES},
        'lines': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'emotion': {'type': 'string', 'maxLength': 30},
            'intensity': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'role': {'type': 'string', 'enum': ROLES}},
            'required': ['id', 'emotion', 'intensity', 'role']}},
        'music': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'from_id': {'type': 'integer'}, 'to_id': {'type': 'integer'}, 'mood': {'type': 'string', 'enum': moods},
            'energy': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'why': {'type': 'string', 'maxLength': 200}},
            'required': ['from_id', 'to_id', 'mood', 'energy', 'why']}},
        'moments': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'trigger': {'type': 'string', 'enum': list(TRIGGERS)},
            'evidence': {'type': 'string', 'maxLength': 60}, 'word': {'type': 'string', 'maxLength': 40},
            'type': {'type': 'string', 'enum': families}, 'intent': {'type': 'string', 'maxLength': 80},
            'strength': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'pull_back': {'type': 'boolean'},
            'why': {'type': 'string', 'maxLength': 200}},
            'required': ['id', 'trigger', 'evidence', 'word', 'type', 'intent', 'strength', 'pull_back', 'why']}}},
        'required': ['story', 'palette', 'lines', 'music', 'moments']}


PICK_SCHEMA = {'type': 'object', 'properties': {
    'effects': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'moment': {'type': 'integer'}, 'why': {'type': 'string', 'maxLength': 160},
        'choice': {'type': 'integer'}}, 'required': ['moment', 'why', 'choice']}},
    'music': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'section': {'type': 'integer'}, 'why': {'type': 'string', 'maxLength': 160},
        'choice': {'type': 'integer'}}, 'required': ['section', 'why', 'choice']}}},
    'required': ['effects', 'music']}


MOOD_MEANING = {  # the user's own mood taxonomy, shortened
    'reflective': 'quiet introspection, melancholy, calm sadness, looking back',
    'upbeat': 'energetic, fun, light, playful momentum, happy',
    'tense': 'building unease, serious, dramatic, something is wrong',
    'lofi': 'relaxed everyday routine, chill background, casual vlog',
    'cinematic': 'sweeping, important, a serious story being told',
    'neutral': 'calm factual background, understated, does not pull attention',
    'hopeful': 'warm resolution, things get better, uplifting, optimistic',
    'thriller': 'dark suspense, mystery, investigation',
    'funny': 'comedic, silly, playful, cartoon',
}
FAMILY_MEANING = {
    'impact': 'hits, booms, sub drops, punches',
    'riser': 'risers, whooshes, swooshes, transitions that build',
    'awkward': 'awkward stings, record scratch, fail sounds',
    'cute': 'soft pops, bubbles, chimes, twinkles',
    'retro': '8-bit game sounds, coins, level up',
    'suspense': 'drones, ticking clocks, tension beds',
    'vanish': 'poof, disappear, reverse swell, sparkle',
    'poke': 'taps, clicks, pops, notifications, blips, typing, camera',
    'whoosh': 'whooshes, swooshes, transitions, fast air movement',
    'glitch': 'digital glitches, stutters, static, error-like tech sounds',
}


def _words(text):
    import re
    return [w for w in re.sub(r'[^\w]+', ' ', str(text).casefold()).split() if w]


def validate_moments(analysis, lines, families, palette):
    """The director's moments held to the rules in code -> (kept, dropped with reasons).
    - the trigger's evidence must really be in that line (no invented reasons)
    - the effect type must suit the trigger (else the closest allowed type that exists)
    - TONE: no playful sound on a sad/serious/vulnerable line unless the video is comedic"""
    feel = {l.get('id'): l for l in analysis.get('lines', []) if isinstance(l, dict)}
    by_id = {l.id: l for l in lines}
    kept, dropped = [], []
    for m in analysis.get('moments', []):
        if not isinstance(m, dict):
            continue
        line = by_id.get(m.get('id'))
        if line is None:
            continue
        said = set(_words(line.text))
        evidence = _words(m.get('evidence', ''))
        if not evidence or sum(w in said for w in evidence) / len(evidence) < .6:
            dropped.append((m, 'no trigger in the words of that line'))
            continue
        allowed = [t for t in TRIGGERS.get(m.get('trigger'), ()) if t in families]
        if not allowed:
            dropped.append((m, f'no fitting sound type for a {m.get("trigger")}'))
            continue
        if m.get('type') not in allowed:
            m = {**m, 'type': allowed[0]}
        emotion = str(feel.get(line.id, {}).get('emotion', '')).casefold()
        if palette != 'comedic' and m['type'] in PLAYFUL and any(h in emotion for h in HEAVY_EMOTIONS):
            dropped.append((m, f'a playful {m["type"]} sound does not fit a {emotion} line'))
            continue
        kept.append(m)
    return kept, dropped


def analyse(brain, kind, lines, voice_notes, events, moods, families, count=8, preferences='', progress=print):
    voice = {n['id']: n['voice'] for n in voice_notes}
    data = {'lines': [{'id': l.id, 'time': f'{l.start:.1f}-{l.end:.1f}s', 'text': l.text,
                       'voice': voice.get(l.id, 'normal delivery')} for l in lines],
            'editing_events': events,
            'music_moods_in_library': {m: MOOD_MEANING.get(m, m) for m in moods},
            'effect_types_in_library': {f: FAMILY_MEANING.get(f, f) for f in families}}
    ask = lambda system, payload, schema: brain.ask(system, payload, schema, think=True, max_tokens=7000,
                                                    label='Thinking about the story, emotions and sound')
    short = 'Reel' in kind or 'short' in kind
    return guard.ask_checked(ask, ANALYSIS_SYSTEM.format(kind=kind, count=count, preferences=preferences), data,
                             analysis_schema(moods, families),
                             model_rules.sound_analysis(lines, count, moods, families, short),
                             label='story and sound moments', feature='sound', progress=progress,
                             repair=model_rules.sound_repair(lines, families, count, short))


def pick(brain, story, palette, moments, effect_candidates, sections, music_candidates, progress=print):
    data = {'story': story, 'palette': palette,
            'moments': [{'moment': i, 'line': m['line_text'], 'word': m['word'], 'type': m['type'],
                         'intent': m['intent'], 'emotion': m.get('emotion', ''),
                         'candidates': [{'choice': j, 'file': c['doc']} for j, c in enumerate(cands)]}
                        for i, (m, cands) in enumerate(zip(moments, effect_candidates))],
            'music_sections': [{'section': i, 'mood': s['mood'], 'why': s['why'],
                                'candidates': [{'choice': j, 'file': c['doc']} for j, c in enumerate(cands)]}
                               for i, (s, cands) in enumerate(zip(sections, music_candidates))]}
    ask = lambda system, payload, schema: brain.ask(system, payload, schema, think=False, max_tokens=3000,
                                                    label='Choosing the exact files from your library')
    return guard.ask_checked(ask, PICK_SYSTEM, data, PICK_SCHEMA,
                             model_rules.sound_pick(moments, effect_candidates, sections, music_candidates),
                             label='file choices', feature='sound', progress=progress)
