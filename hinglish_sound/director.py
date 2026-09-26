"""The sound director: a thinking local model reads the video (words + voice + edit) with the
sound-design brain's rules, then picks real files from retrieved candidates (RAG)."""

from hinglish_eval import guard, model_rules

RULES = '''SOUND DESIGN RULES (the editor's sound-design brain, tuned for engaging Reels):
1. Dialogue is king: a sound supports the words, never fights them. But in a Reel the sound design IS
   part of the entertainment and the viewer must HEAR it: a designed sound roughly every 2-3 seconds
   keeps attention. Leave silence only where the story needs weight.
2. Read each line's emotion from its words AND the voice evidence ("louder/higher/fast" = excited, angry
   or shocked; "quieter/lower/slow/monotone" = sad, tired, serious, vulnerable). Hinglish: Hindi in
   Latin letters mixed with English; speech recognition may misspell words.
3. MUSIC is a bed chosen by emotion, never by keywords:
   - personal struggle / vulnerability / serious realisation -> ambient, slow strings or solo piano,
     no percussion (moods like reflective, tense, cinematic)
   - sad -> piano / strings (reflective)
   - informational, casual -> lo-fi / chill / neutral
   - hopeful resolution, things get better -> hopeful / upbeat
   - comedy -> funny / upbeat; tension, mystery -> tense / thriller
   Change music only at a real emotional turn (max 2 sections in a short Reel, a few in long videos);
   a transformation can START ambient and RESOLVE to hopeful/uplifting at the reveal.
4. PULL BACK AND PUNCH: before the single biggest realisation/reveal, the music dips into a vacuum and a
   low sub boom lands on the key word - felt, not heard. Use it at most once or twice per Reel.
5. Effect vocabulary - choose the type, then describe the exact sound:
   - whoosh: moving to a new point or place ("Mumbai se Delhi"), a quick turn in the story, anything moving
   - impact: punchline, realisation, strong statement, shocking fact, a number, the big word
     -> cinematic hit / deep boom / bass drop (a whoosh is layered in automatically)
   - riser: tension building towards a punchline or reveal (it ends on the punch word)
   - poke: every concrete thing you could "click": app names, phone, message, notification, typing,
     camera, and items in a list (one pop per item)
   - cute: a positive realisation, a small win, a warm moment -> ding / chime / sparkle
   - retro: money, coins, prices, gaming, achievement, score
   - awkward: failure, rejection, embarrassment, sarcasm -> error buzzer / fail sting / record scratch
   - suspense: worry, fear, time pressure, uncertainty -> heartbeat / clock ticking
   - glitch: confusion, something broken or not working, a system failing, tech
   - vanish: something gone, wasted, disappeared
6. Match the palette: serious or emotional stories get cinematic, clean sounds, never cartoon/silly ones;
   comedic stories may use cartoon sounds.
7. Spacing and variety: never two sounds within 0.8 s; do not use the same type three times in a row.
8. A sound lands on the exact word: copy that word exactly from the line.'''

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
- moments: about {count} designed sounds on the speech, spread over the whole video (B-roll cuts and
  zoom landings already get their own whoosh/boom automatically - do not add those): id, the exact word
  it lands on, the effect type, intent (the exact sound in plain words, e.g. "deep cinematic boom",
  "phone notification ping", "clock ticking"), strength 1-3, pull_back (true only for the one or two
  biggest reveals) and why'''

PICK_SYSTEM = '''You are the sound editor. For each moment you get the director's intent and the real
candidate files retrieved from the library (with type, genre, length, shape and quality). Pick the ONE
candidate that best matches the intent AND the emotion of the video: prefer professional studio sounds,
punchy short hits for impacts, crisp short sounds for pops and clicks, a riser that builds up, never a
cartoon/silly sound in a serious or emotional story. If none fits, answer -1.
Do the same for each music section (prefer calm instrumental beds without a strong melody for talking).
Write why first, then the choice.'''

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
            'id': {'type': 'integer'}, 'word': {'type': 'string', 'maxLength': 40},
            'type': {'type': 'string', 'enum': families}, 'intent': {'type': 'string', 'maxLength': 80},
            'strength': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'pull_back': {'type': 'boolean'},
            'why': {'type': 'string', 'maxLength': 200}},
            'required': ['id', 'word', 'type', 'intent', 'strength', 'pull_back', 'why']}}},
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


def analyse(brain, kind, lines, voice_notes, events, moods, families, count=8, progress=print):
    voice = {n['id']: n['voice'] for n in voice_notes}
    data = {'lines': [{'id': l.id, 'time': f'{l.start:.1f}-{l.end:.1f}s', 'text': l.text,
                       'voice': voice.get(l.id, 'normal delivery')} for l in lines],
            'editing_events': events,
            'music_moods_in_library': {m: MOOD_MEANING.get(m, m) for m in moods},
            'effect_types_in_library': {f: FAMILY_MEANING.get(f, f) for f in families}}
    ask = lambda system, payload, schema: brain.ask(system, payload, schema, think=True, max_tokens=7000,
                                                    label='Thinking about the story, emotions and sound')
    short = 'Reel' in kind or 'short' in kind
    return guard.ask_checked(ask, ANALYSIS_SYSTEM.format(kind=kind, count=count), data, analysis_schema(moods, families),
                             model_rules.sound_analysis(lines, count, moods, families, short),
                             label='story and sound moments', feature='sound', progress=progress,
                             repair=model_rules.sound_repair(lines, families))


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
