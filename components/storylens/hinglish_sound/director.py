"""The sound director: a thinking local model reads the video (words + voice + edit) with the
sound-design brain's rules, then picks real files from retrieved candidates (RAG)."""

from hinglish_eval import guard, model_rules

RULES = '''SOUND DESIGN RULES (how a professional sound editor "spots" a talking-head video):
1. Dialogue is king. Every sound needs a reason in the story, delivery or measured visual/edit event.
   Choose deliberate music, effects-only and voice-only passages. Density follows this video.
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
6. MUSIC supports the emotional arc. Prefer coherent instrumental passages under speech, with
   intentional entrances/exits and space for dry punchlines, tension or vulnerable delivery.
   Change tracks only for a motivated story turn, never a mechanical per-line rotation.
7. Fewer, better sounds: at most {count} designed sounds for this whole video. Editing events are
   measured timing evidence, not guaranteed sounds; a separate pass selects motivated event sounds.
   Do not double up a spoken emphasis with a nearby editing event.
8. A sound lands on the exact word: copy that word exactly from the line, and give its zero-based
   word_index within that line so repeated words can be distinguished.

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
creator_script (when given) is the creator's own script: use it to understand the meaning and the
right names, but sounds must land on words of the spoken lines.
Read the rhetorical meaning before the literal nouns: deadpan, sarcasm, mock shock and self-deprecating
jokes are comedy even when they mention darkness, empty streets, sleep or disappointment. Do not
score a humorous complaint as a horror documentary. A narrated object is not a request to hear it.
Think carefully first (what is the story, how does the speaker feel line by line, where is the
emotional turn, which few moments truly deserve sound), then answer:
- story: what happens and the emotional arc, in English (max 60 words)
- palette: the overall sound palette
- lines: for EVERY line id: emotion (one or two words), intensity 1-3, role in the story
- music: an ordered spotting map covering every line exactly once, using from_id..to_id.
  Each section has mode music, effects_only (no music) or voice_only (no added music/effects).
  For music choose an available mood; for the other modes use mood ''. Include energy 1-3 and why.
  Keep one coherent bed when it fits, but allow brief intentional dry passages and distinct emotional
  turns. No arbitrary two-section limit or forced continuous music. Never mute the original dialogue.
  If music is disabled/no moods are supplied, return [].
  For clips without dialogue, the supplied lines are visual observations, not spoken words:
  use them for emotion and music, and return no spoken-word moments.
- moments: at most {count} designed sounds, only on real triggers: id, trigger, evidence (the exact words
  from that line that prove the trigger), the exact word it lands on, the effect type, intent (the exact
  sound in plain words, e.g. "deep cinematic boom", "soft phone tap", "clock ticking"), strength 1-3,
  pull_back (true only for the single biggest reveal) and why (tone of the line + why this sound).
{preferences}'''

PICK_SYSTEM = '''You are the sound editor. For each moment you get the director's intent and the real
candidate files retrieved from the library. Each file says what it SOUNDS like (a listening model heard
it) plus its type, genre, length, shape and quality. Listening labels are approximate classifier guesses;
compare them with the actual title/tags and reject contradictions. Never pick footsteps for fabric,
doors for a phone gesture, or wildlife for an indoor narration. Pick the ONE
candidate that best matches the intent AND the tone of that line: prefer professional studio sounds,
punchy hits for impacts, crisp sounds for actual pops and clicks, a riser that builds up, resonant
tonal stings and decays, sustained water/surface/engine sounds when supported. Honor requested duration:
a 0.1-second click cannot replace a 2-second evolving sound. Do not prefer UI/camera sounds merely
because they are easy to find. Keep useful natural body and tail; do not stretch source recordings. Never a
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
REPAIRED_INTENTS = {
    'whoosh':'soft short whoosh', 'impact':'short low impact', 'riser':'gentle rising swell',
    'poke':'soft short click', 'cute':'gentle chime', 'retro':'short coin chime',
    'awkward':'short record scratch', 'suspense':'low tension drone',
    'glitch':'short digital glitch', 'vanish':'soft disappearing poof',
}
INTENT_TERMS = {
    'whoosh':{'whoosh','swoosh','swish','sweep'}, 'impact':{'boom','hit','impact','thud','punch'},
    'riser':{'riser','rising','swell'}, 'poke':{'click','tap','pop','notification','typing','camera'},
    'cute':{'chime','ding','sparkle','bell'}, 'retro':{'coin','game','arcade','retro'},
    'awkward':{'scratch','buzzer','fail'}, 'suspense':{'heartbeat','ticking','drone','tension'},
    'glitch':{'glitch','static','stutter'}, 'vanish':{'poof','disappear','disappearing','vanish'},
    'foley':{'footsteps','cloth','door','fabric','knock'},
    'ambience':{'birds','wind','rain','traffic','forest'},
}

ROLES = ['hook', 'setup', 'conflict', 'realisation', 'punchline', 'twist', 'resolution', 'call_to_action',
         'filler']
PALETTES = ['serious', 'emotional', 'comedic', 'energetic', 'informational']


def analysis_schema(moods, families):
    from .acoustic import palette_schema
    schema = {'type': 'object', 'properties': {
        'story': {'type': 'string', 'maxLength': 500},
        'palette': {'type': 'string', 'enum': PALETTES},
        'sound_palette':palette_schema(),
        'lines': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'emotion': {'type': 'string', 'maxLength': 30},
            'intensity': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'role': {'type': 'string', 'enum': ROLES}},
            'required': ['id', 'emotion', 'intensity', 'role']}},
        'music': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'from_id': {'type': 'integer'}, 'to_id': {'type': 'integer'}, 'mood': {'type': 'string', 'enum': list(moods)+['']},
            'mode':{'type':'string','enum':['music','effects_only','voice_only']},
            'energy': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'why': {'type': 'string', 'maxLength': 200}},
            'required': ['from_id', 'to_id', 'mode', 'mood', 'energy', 'why']}},
        'moments': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'trigger': {'type': 'string', 'enum': list(TRIGGERS)},
            'evidence': {'type': 'string', 'maxLength': 60}, 'word': {'type': 'string', 'maxLength': 40},
            'word_index': {'type': 'integer', 'minimum': 0},
            'type': {'type': 'string', 'enum': families}, 'intent': {'type': 'string', 'maxLength': 80},
            'strength': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'pull_back': {'type': 'boolean'},
            'why': {'type': 'string', 'maxLength': 200}},
            'required': ['id', 'trigger', 'evidence', 'word', 'word_index', 'type', 'intent', 'strength', 'pull_back', 'why']}}},
        'required': ['story', 'palette', 'sound_palette', 'lines', 'music', 'moments']}
    if not moods:schema['properties']['music']['maxItems']=0
    return schema


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
    'foley': 'physical action sounds such as footsteps, cloth and doors',
    'ambience': 'quiet sustained environment such as room tone, rain, birds or traffic',
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
            # Keep retrieval consistent with the repaired trigger family. A boom
            # query inside a whoosh-only search cannot yield a relevant match.
            m = {**m, 'type': allowed[0], 'intent': REPAIRED_INTENTS[allowed[0]]}
        intent_words=set(_words(m.get('intent','')))
        named_families={family for family,terms in INTENT_TERMS.items() if intent_words & terms}
        if named_families and m['type'] not in named_families:
            m={**m,'intent':REPAIRED_INTENTS[m['type']]}
        emotion = str(feel.get(line.id, {}).get('emotion', '')).casefold()
        if palette != 'comedic' and m['type'] in PLAYFUL and any(h in emotion for h in HEAVY_EMOTIONS):
            dropped.append((m, f'a playful {m["type"]} sound does not fit a {emotion} line'))
            continue
        kept.append(m)
    return kept, dropped


def normalize_music_boundaries(answer, lines):
    """Resolve only shared inclusive endpoints; do not change music choices."""
    import copy
    if not isinstance(answer,dict) or not isinstance(answer.get('music'),list):return answer
    result=copy.deepcopy(answer)
    ids=[l.id for l in lines];positions={v:i for i,v in enumerate(ids)}
    sections=result['music'];repairs=[]
    for current,following in zip(sections,sections[1:]):
        if not isinstance(current,dict) or not isinstance(following,dict):continue
        start,end,next_start=current.get('from_id'),current.get('to_id'),following.get('from_id')
        if (type(start) is int and type(end) is int and type(next_start) is int
                and end==next_start and start in positions and next_start in positions
                and positions[start]<positions[next_start]):
            current['to_id']=ids[positions[next_start]-1]
            repairs.append({'from_id':start,'previous_to_id':end,'to_id':current['to_id']})
    if repairs:result['_music_boundary_repairs']=repairs
    return result


def analyse(brain, kind, lines, voice_notes, events, moods, families, count=8, preferences='', progress=print,
            script='', observations=None, composition=None):
    if composition:
        # Composed effects have a separate measured-anchor authoring pass. A
        # sparse preliminary cue list must not bias or restrict that pass.
        count=0
    # Long videos keep timeline ids and all creator guidance in each bounded planning call.
    if len(lines) > 35:
        answers = []
        for start in range(0, len(lines), 35):
            chunk = lines[start:start + 35]
            obs = [o for o in (observations or []) if chunk[0].start <= o['time'] <= chunk[-1].end]
            edits = [e for e in events if not isinstance(e, dict) or chunk[0].start <= e['time'] <= chunk[-1].end]
            answers.append(analyse(brain, kind, chunk, voice_notes, edits, moods, families,
                max(1, round(count * len(chunk) / len(lines))), preferences, progress, script, obs,composition))
        merged = dict(answers[0])
        for key in ('lines', 'music', 'moments'):
            merged[key] = [row for a in answers for row in a.get(key, [])]
        merged['moments'] = sorted(merged['moments'], key=lambda r: -r.get('strength', 1))[:count]
        merged['story'] = ' '.join(a.get('story', '') for a in answers)
        merged['_thinking'] = '\n'.join(a.get('_thinking', '') for a in answers)
        return merged
    voice = {n['id']: n['voice'] for n in voice_notes}
    data = {'workflow': 'sound design', 'lines': [{'id': l.id, 'time': f'{l.start:.1f}-{l.end:.1f}s', 'text': l.text,
                       'voice': voice.get(l.id, 'normal delivery')} for l in lines],
            'editing_events': events,
            'visual_observations': observations or [],
            'music_moods_in_library': {m: MOOD_MEANING.get(m, m) for m in moods},
            'effect_types_in_library': {f: FAMILY_MEANING.get(f, f) for f in families}}
    if hasattr(brain, 'root'):
        from hinglish_niche.style_memory import planning_examples
        references = planning_examples(brain.root, 'Documentary sound design, narration, music and motivated effects: ' +
                                        (script or ' '.join(l.text for l in lines)), purpose='sound')
        if references:
            data['documentary_sound_examples'] = references
    if script.strip():
        from hinglish_visuals.script import script_context
        data['creator_script'] = script_context(script)     # what the creator means (the lines are what was said)
    system=ANALYSIS_SYSTEM.format(kind=kind,count=count,preferences=preferences)
    system+=(' Define sound_palette for THIS story and delivery: a concise sonic identity, '
             'preferred acoustic textures and textures to avoid. This is not a list of mandatory effects. '
             'Different projects need different palettes: a comic complaint, vulnerable story and energetic '
             'promo must not automatically share the same UI/bell set. Preserve coherent character while '
             'allowing distinct tonal, low, airy, rough or dry functions when motivated. Do not invent assets.')
    if composition:
        data['composition']=composition
        system+='''\nCOMPOSED SOUNDTRACK: this call identifies the story, emotional/rhetorical delivery
of EVERY supplied line, and music. Return moments: [] here. A separate measured-word/edit-anchor
composer owns ALL effects and will design short approaches, list details, motion accents, contacts
and tails. Do not author a preliminary sparse sound plan. Preserve dry humor/mock shock as delivery
information; a comic complaint is not automatically a horror story. Music supports that delivery.'''
    def ask(system,payload,schema):
        answer=brain.ask(system,payload,schema,think=True,max_tokens=7000,
                         label='Thinking about the story, emotions and sound')
        return normalize_music_boundaries(answer,lines)
    short = 'Reel' in kind or 'short' in kind
    schema=analysis_schema(moods,families)
    if composition:schema['properties']['moments']['maxItems']=0
    return guard.ask_checked(ask, system, data,
                             schema,
                             model_rules.sound_analysis(lines, count, moods, families, short),
                             label='story and sound moments', feature='sound', progress=progress,
                             repair=model_rules.sound_repair(lines, families, count, short))


def pick(brain, story, palette, moments, effect_candidates, sections, music_candidates, progress=print, *, _palette_grouped=False, sound_palette=None, human_review=False):
    # Coherence is a project direction, not permission to erase distinct line
    # contexts and copy one source choice into all repeated intent strings.
    # Layered/long videos produce more candidates; keep each model call bounded.
    chunk_size=4 if human_review else 8
    if len(moments)>chunk_size or len(sections)>4:
        combined={'effects':[],'music':[]}
        for i in range(0,len(moments),chunk_size):
            part=pick(brain,story,palette,moments[i:i+chunk_size],effect_candidates[i:i+chunk_size],[],[],progress,sound_palette=sound_palette,human_review=human_review)
            combined['effects'] += [dict(row,moment=row['moment']+i) for row in part.get('effects',[])]
        for i in range(0,len(sections),4):
            part=pick(brain,story,palette,[],[],sections[i:i+4],music_candidates[i:i+4],progress,sound_palette=sound_palette,human_review=human_review)
            combined['music'] += [dict(row,section=row['section']+i) for row in part.get('music',[])]
        return combined
    data = {'story': story, 'palette': palette, 'sound_palette':sound_palette or {},
            'moments': [{'moment': i, 'line': m['line_text'], 'word': m['word'], 'type': m['type'],
                         'intent': m['intent'], 'emotion': m.get('emotion', ''),
                         'duration':m.get('duration'),'duration_reason':m.get('duration_reason',''),
                         'layer_role': m.get('role',''), 'layer_group':m.get('group_id',''),
                         'reuse_key':m.get('reuse_key',''),'reuse_reason':m.get('reuse_reason',''),
                         'context_examples':m.get('context_examples',[]),
                         'candidates': [{'choice': j, 'file': c['doc']} for j, c in enumerate(cands)]}
                        for i, (m, cands) in enumerate(zip(moments, effect_candidates))],
            'music_sections': [{'section': i, 'mood': s['mood'], 'why': s['why'],
                                'candidates': [{'choice': j, 'file': c['doc']} for j, c in enumerate(cands)]}
                               for i, (s, cands) in enumerate(zip(sections, music_candidates))]}
    ask = lambda system, payload, schema: brain.ask(system, payload, schema, think=False, max_tokens=3000,
                                                    label='Choosing the exact files from your library')
    system=PICK_SYSTEM+(' Follow this project acoustic identity and each exact line context. '
        'A shared category or identical intent wording does not require the same source file. '
        'Reuse is deliberate only when a matching reuse_key and narrative reuse_reason are supplied. '
        'Do not force novelty by choosing irrelevant audio; -1 remains valid when no candidate fits.')
    import copy
    schema=copy.deepcopy(PICK_SCHEMA)
    if human_review:
        system+=' HUMAN REVIEW: keep choice as your single best file for the initial timeline. Return alternatives: ALL other suitable candidate numbers in preference order, up to 20. Do not limit to 2-5; offer broad genuinely related options for the human. Do not pad with irrelevant sounds. A shorter related recording can be a folder option even if it cannot cover the whole timeline event. The best choice must fit its authored duration. Do not invent candidates or include the best choice twice. For each effect return keyword: a concise 2-5 word sound source/action folder name. Reuse exactly the same keyword for equivalent repeated sources; separate engines, rain, wet footsteps, waterfall, typography etc according to actual evidence. These are examples, not a fixed taxonomy. Earshot acoustic estimates, when present, describe recordings but do not prove that a sound belongs in the visible scene. You make the final choice from the actual source/action evidence; no other model will veto it. The owner will audition and decide.'
        for key in ('effects','music'):
            item=schema['properties'][key]['items']
            item['properties']['alternatives']={'type':'array','items':{'type':'integer'},'maxItems':20}
            item['required'].append('alternatives')
        item=schema['properties']['effects']['items']
        item['properties']['keyword']={'type':'string','maxLength':64}
        item['required'].append('keyword')
    for key,id_key,candidates in (('effects','moment',effect_candidates),('music','section',music_candidates)):
        part=schema['properties'][key]
        part.update(minItems=len(candidates),maxItems=len(candidates))
        props=part['items']['properties']
        if candidates:
            props[id_key]['enum']=list(range(len(candidates)))
        props['choice']['enum']=list(range(-1,max((len(c) for c in candidates),default=0)))
    system+=' Answer for EVERY supplied moment and music section exactly once in their supplied order, using -1 when no file fits. Never copy the moment number into choice; choice is the candidate number inside that moment.'
    return guard.ask_checked(ask, system, data, schema,
                             model_rules.sound_pick(moments, effect_candidates, sections, music_candidates),
                             label='file choices', feature='sound', progress=progress)
