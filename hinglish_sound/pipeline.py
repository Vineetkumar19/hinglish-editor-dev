"""Sound design with a thinking local model:
voice evidence -> story/emotion/music/moment analysis (Ollama qwen3, thinking, sound-design-brain rules)
-> RAG over the library vector index -> the model picks real files -> peak-synced placement ->
edit sounds (B-roll cuts, zoom landings) -> brain-rule mix -> own tracks in the XML + preview."""
from dataclasses import asdict
from datetime import datetime
import json
import math
from pathlib import Path
import uuid

import numpy as np
import torch
import torchaudio.functional as AF

from hinglish_broll.phrases import build_phrases
from hinglish_broll.pipeline import timelines_for, transcripts_for
from hinglish_broll.timeline import timeline_words
from hinglish_clean.detection import write_json
from hinglish_eval import guard, tune

from .brain import Brain
from . import learning
from .cues import Cue, edit_cues, keep_musical, layer_hits, place_cue, word_time
from .director import analyse, pick, validate_moments
from .evaluator import check_effect, check_music, mix_qa
from .library import scan
from .mix import mix
from .prosody import describe_lines
from .report import write_report
from .settings import DENSITY, EDIT_SHARE, OLD_SCAN_CACHE, SFX_BEHAVIOUR, load_settings
from .vectors import SoundIndex
from .xml_export import export_sound_xml

PREVIEW_LIMIT = 300.0
STYLE_PALETTE = {'cinematic': 'serious', 'funny': 'comedic', 'chill': 'informational', 'emotional': 'emotional'}


def zoom_lands(seq):
    """Times where a Smart Zoom finishes pushing in (the scale stops rising), from the XML itself."""
    scale = np.ones(seq.frames)
    for clip in seq.clips:
        scale[max(0, clip.start):min(seq.frames, clip.end)] = clip.base_scale
    lands, rising = [], False
    for f in range(1, seq.frames):
        if scale[f] > scale[f - 1] + 1e-4:
            rising = True
        elif rising:
            if scale[f - 1] > 1.01:
                lands.append(round((f - 1) / float(seq.fps), 3))
            rising = False
    return lands


RESOLVING_MOODS = ('hopeful', 'upbeat')
MAX_SECTIONS = {'short': 2, 'long_per_minute': .5}


def music_sections(plan, lines, seconds, moods):
    """The model's music plan, held to the brain's rule: music is a BED, it changes only at a real
    emotional turn. Reels: one bed for the dominant emotion, plus at most one change where the story
    resolves (e.g. struggle -> hopeful). Long videos: at most one change every ~2 minutes."""
    by_id = {l.id: l for l in lines}
    rows = sorted((m for m in plan if m.get('from_id') in by_id and m.get('mood') in moods),
                  key=lambda m: by_id[m['from_id']].start)
    spans = []
    for i, m in enumerate(rows):
        start = 0.0 if i == 0 else by_id[m['from_id']].start
        end = by_id[rows[i + 1]['from_id']].start if i + 1 < len(rows) else seconds
        spans.append({'start': start, 'end': end, 'mood': m['mood'], 'energy': m.get('energy', 2),
                      'why': m.get('why', '')})
    if not spans:
        return [{'start': 0.0, 'end': seconds, 'mood': moods[0], 'energy': 2, 'why': 'fallback'}] if moods else []
    if seconds <= 180:
        ending = spans[-1] if spans[-1]['mood'] in RESOLVING_MOODS and len(spans) > 1 else None
        body = [s for s in spans if s is not ending]
        weight = {}
        for s in body:
            weight[s['mood']] = weight.get(s['mood'], 0) + s['end'] - s['start']
        main_mood = max(weight, key=weight.get)
        main = next(s for s in body if s['mood'] == main_mood)
        sections = [{'start': 0.0, 'mood': main_mood, 'energy': main['energy'],
                     'why': '; '.join(dict.fromkeys(s['why'] for s in body if s['mood'] == main_mood))}]
        if ending and ending['end'] - ending['start'] >= max(5.0, .12 * seconds):
            sections.append({'start': ending['start'], 'mood': ending['mood'], 'energy': ending['energy'],
                             'why': ending['why'] + ' (the story resolves here)'})
    else:
        sections, limit = [], max(1, int(seconds / 60 * MAX_SECTIONS['long_per_minute']))
        for s in spans:
            if sections and (s['mood'] == sections[-1]['mood'] or s['start'] - sections[-1]['start'] < 120):
                continue
            sections.append(dict(s))
        sections = sections[:limit]
    for a, b in zip(sections, sections[1:] + [None]):
        a['end'] = b['start'] if b else seconds
    return sections


def _rank(picked, count):
    """The picker's choice first, then the other candidates (the evaluator walks this list)."""
    first = picked if isinstance(picked, int) and 0 <= picked < count else 0
    return [first] + [j for j in range(count) if j != first]


def open_listener(root, settings, progress):
    if not settings.listen:
        return None
    try:
        from .listen import Listener
        progress('Loading the listening model (CLAP: it hears what each sound really is)')
        return Listener(root, settings.listen_model, settings.device, settings.cpu_threads)
    except Exception as error:
        progress(f'  Listening model unavailable ({error}); choosing by names and tags only')
        return None


def finish(root, folder, plan, seq, voice, sections, cues, pull_backs, settings, progress):
    """Mix, measure (mix QA), export the XML, render the preview and write the report."""
    from hinglish_zoom.preview import render_preview
    progress('Mixing with the sound-design brain rules')
    gain = tune.value('sound', 'effect_gain_db', 0.0)       # quality-check correction: louder effects
    for c in cues:
        c.offset_db += gain
    mixed = mix(voice, sections, cues, folder, pull_backs,
                settings.music_level + tune.value('sound', 'music_trim_db', 0.0))
    qa = mix_qa(voice, mixed['bed'], mixed['effects'], mixed['master'], mixed['speech'], cues,
                plan['budget'], plan['gap'])
    failed = [r for r in qa if not r['passed']]
    progress(f'  Mix check: {len(qa) - len(failed)}/{len(qa)} passed' +
             ('' if not failed else ' (' + '; '.join(f"{r['check']}: {r['value']}" for r in failed[:3]) + ')'))
    xml = export_sound_xml(plan['timeline_xml'], seq.fps, mixed['stems'], Path(folder) / 'SOUND_SEQUENCE.xml')
    preview = None
    if plan['seconds'] <= PREVIEW_LIMIT:
        progress('Rendering a preview with the new sound')
        render_preview(seq, np.ones(seq.frames), [None] * seq.frames, Path(folder) / 'preview.mp4',
                       progress=lambda _: None, audio=mixed['master'].mean(axis=0))
        preview = 'preview.mp4'
    plan.update(music=[{k: v for k, v in s.items()} for s in sections], cues=[c.to_dict() for c in cues],
                pull_backs=pull_backs, voice_db=mixed['voice_db'], voice_peak=mixed['voice_peak'],
                words_db=mixed['words_db'],
                stems=mixed['stems'], mix_qa=qa, preview=preview)
    write_json(Path(folder) / 'sound-plan.json', plan)
    guard.save(folder)
    write_report(Path(folder) / 'report.html', plan['name'], plan, preview)
    return xml


def run(root, input_path, output_format=None, overrides=None, progress=print):
    root = Path(root).resolve()
    settings = load_settings(root, **(overrides or {}))
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'sound' / stamp
    output.mkdir(parents=True)
    taste_data = learning.load(root)
    banned = learning.banned(taste_data)
    if banned:
        progress(f'  {len(banned)} sounds you removed before are never used again')
    progress('Reading your sound library')
    music_assets = scan(settings.music_folder, 'music', root / 'cache' / 'sound', OLD_SCAN_CACHE, progress) \
        if settings.music else []
    if settings.music and not music_assets:
        progress(f'  No music found in {settings.music_folder}. Put instrumental tracks (mp3/wav) there, one '
                 'folder per mood (e.g. reflective, upbeat, tense), or choose your music folder in the app')
    sfx_assets = []
    if settings.effects or settings.transitions:
        pro = Path(settings.pro_folder) if settings.pro_folder else root / 'library' / 'sfx-pro'
        for folder in (settings.sfx_folder, pro):          # your library + the professional pack
            sfx_assets += scan(folder, 'sfx', root / 'cache' / 'sound', OLD_SCAN_CACHE, progress)
    brain = Brain(root, settings.think_model, settings.embed_model, progress=progress)
    listener = open_listener(root, settings, progress)
    progress('Building the library index: names + what each file sounds like (first time only)')
    sfx_index = SoundIndex(sfx_assets, brain, listener, progress)
    music_index = SoundIndex(music_assets, brain, listener, progress)
    moods = sorted({a.category for a in music_assets})
    families = sorted({a.category for a in sfx_assets} & set(SFX_BEHAVIOUR))
    progress(f'  {len(music_assets)} music tracks, {len(sfx_assets)} effects indexed')
    if listener is not None and music_assets:
        singing = sum(1 for f in music_index.facts if f and f.get('vocals'))
        progress(f'  Heard {singing} music tracks with singing: they are kept out of speech beds')

    progress('Reading the timeline')
    jobs = timelines_for(root, input_path, output, output_format, progress)
    sources = sorted({s for t, _ in jobs for s in t.sources()})
    progress('Understanding your speech (reusing saved transcripts when available)')
    words_by_source, notes = transcripts_for(root, sources, settings.device, progress)

    from hinglish_zoom.preview import _audio_track
    from hinglish_zoom.xml_apply import Sequence
    results = []
    for timeline, folder in jobs:
        words = timeline_words(timeline, words_by_source)
        lines = build_phrases(words)
        if not lines:
            progress(f'  No speech found in {timeline.name}; skipped'); continue
        seq = Sequence(timeline.xml_path)
        seconds = seq.frames / float(seq.fps)
        voice = _audio_track(seq.path, seconds)[:int(seconds * 48000)]
        progress('Listening to how each line is said (loudness, pitch, pace)')
        voice16 = AF.resample(torch.from_numpy(voice), 48000, 16000).numpy()
        voice_notes = describe_lines(voice16, lines)
        broll = seq.blocked_seconds()
        lands = zoom_lands(seq)
        events = [f'B-roll cutaway {a:.1f}-{b:.1f}s' for a, b in broll] + \
                 [f'zoom-in on the face lands at {t:.1f}s' for t in lands]
        form = 'short' if seconds <= 180 else 'long'
        kind = ('vertical Instagram Reel / YouTube Short' if form == 'short' and seq.height > seq.width
                else 'short video' if form == 'short' else 'long-form YouTube video')
        if settings.style != 'auto':
            events.append(f'The editor asked for a {settings.style} sound style.')
        every, gap = DENSITY[form][settings.density]
        budget = max(2, math.ceil(seconds / every * tune.value('sound', 'count_scale', 1.0)))
        edit_limit = min(len(broll) + len(lands), int(budget * EDIT_SHARE)) if settings.transitions else 0
        ai_count = max(1, budget - edit_limit)
        progress(f'  Sound budget: {budget} sounds ({ai_count} on your words, up to {edit_limit} on cuts/zooms), '
                 f'at least {gap:.1f}s apart')

        analysis = analyse(brain, kind, lines, voice_notes, events, moods, families, ai_count,
                           learning.taste(taste_data), progress)
        palette = STYLE_PALETTE.get(settings.style, analysis.get('palette', 'informational'))
        feel = {l['id']: l for l in analysis.get('lines', []) if isinstance(l, dict)}
        progress(f'  Story: {analysis.get("story", "")[:140]}')
        progress(f'  Palette: {palette}')

        kept_moments, dropped = validate_moments(analysis, lines, families, palette) if settings.effects else ([], [])
        for m, why in dropped:
            progress(f'  Skipped a sound on "{m.get("word", "")}": {why}')
        by_id = {l.id: l for l in lines}
        moments = [{**m, 'line_text': by_id[m['id']].text, 'target': word_time(by_id[m['id']], words, m.get('word', '')),
                    'emotion': feel.get(m['id'], {}).get('emotion', '')} for m in kept_moments]
        sections = music_sections(analysis.get('music', []), lines, seconds, moods) if settings.music else []

        # RAG: retrieve real candidates for every moment and music section (names + what they sound like).
        exclude = () if palette == 'comedic' else ('funny',)
        effect_candidates = []
        for m in moments:
            query = f"{m['intent']}. {m['type']} sound effect. Feeling: {m['emotion']}. {palette} video."
            hits = sfx_index.search(query, top=6, categories=[m['type']], exclude_genres=exclude,
                                    max_duration=SFX_BEHAVIOUR[m['type']]['max_len'], banned=banned)
            if len(hits) < 3:
                hits += [h for h in sfx_index.search(query, top=6, exclude_genres=exclude, banned=banned)
                         if h not in hits]
            effect_candidates.append([{'asset': a, 'doc': sfx_index.docs[sfx_index.assets.index(a)][:260]}
                                      for a, _, _ in hits[:6]])
        music_candidates = []
        for s in sections:
            query = f"{s['mood']} instrumental background music bed for talking, no vocals, no strong melody. {s['why']}"
            hits = (music_index.search(query, top=5, categories=[s['mood']], instrumental_only=True, banned=banned)
                    or music_index.search(query, top=5, instrumental_only=True, banned=banned)
                    or music_index.search(query, top=5, banned=banned))
            music_candidates.append([{'asset': a, 'doc': music_index.docs[music_index.assets.index(a)][:260]}
                                     for a, _, _ in hits])

        picks = pick(brain, analysis.get('story', ''), palette, moments, effect_candidates, sections,
                     music_candidates, progress) if moments or sections else {'effects': [], 'music': []}

        # The evaluator listens to the picked file; a failed one is replaced by the next candidate.
        cues, used = [], set()
        choice = {p.get('moment'): p for p in picks.get('effects', []) if isinstance(p, dict)}
        for i, (m, cands) in enumerate(zip(moments, effect_candidates)):
            p = choice.get(i, {'choice': 0, 'why': 'best match'})
            rejected, chosen, verdict = [], None, None
            for j in _rank(p.get('choice', 0), len(cands)):
                asset = cands[j]['asset']
                if asset.path in used:
                    continue
                if settings.evaluate:
                    k = sfx_index.assets.index(asset)
                    verdict = check_effect(listener, None if sfx_index.audio is None else sfx_index.audio[k],
                                           sfx_index.facts[k], m['type'], m.get('intent', ''), palette)
                    if verdict.passed is False:
                        rejected.append({'file': Path(asset.path).name, **verdict.to_dict()})
                        progress(f'  Evaluator FAIL {Path(asset.path).name}: {"; ".join(verdict.reasons)}')
                        continue
                chosen = asset
                break
            if chosen is None:
                progress(f'  No file really sounds like "{m.get("intent", "")}"; no sound on "{m.get("word", "")}"')
                continue
            used.add(chosen.path)
            cue = place_cue(chosen, m['target'], chosen.category if chosen.category in SFX_BEHAVIOUR else m['type'],
                            f"{m.get('why', '')} | pick: {p.get('why', '')}", m.get('word', ''), m.get('intent', ''),
                            strength=m.get('strength', 2), emotion=m['emotion'])
            cue.pull_back, cue.trigger, cue.line = bool(m.get('pull_back')), m.get('trigger', ''), m['line_text']
            cue.evaluation = {**(verdict.to_dict() if verdict else {'passed': None}), 'rejected': rejected}
            cues.append(cue)
        cues = keep_musical(cues, seconds, seconds / ai_count, gap)
        pull_backs = [c.target for c in cues if c.pull_back][:1]
        cues += layer_hits(cues, sfx_index, palette, used)
        if settings.transitions:
            cues += edit_cues(sfx_index, palette, [a for a, _ in broll], lands, cues, used, edit_limit, gap, banned)
        cues.sort(key=lambda c: c.time)

        mchoice = {p.get('section'): p for p in picks.get('music', []) if isinstance(p, dict)}
        for i, (s, cands) in enumerate(zip(sections, music_candidates)):
            for j in _rank(mchoice.get(i, {}).get('choice', 0), len(cands)):
                asset = cands[j]['asset']
                verdict = check_music(music_index.facts_for(asset), s.get('energy', 2), s['mood']) \
                    if settings.evaluate else None
                if verdict is not None and verdict.passed is False:
                    progress(f'  Evaluator FAIL music {Path(asset.path).name}: {"; ".join(verdict.reasons)}')
                    continue
                s.update(path=asset.path, loudness=asset.loudness, pick_why=mchoice.get(i, {}).get('why', ''),
                         evaluation=verdict.to_dict() if verdict else None)
                break
        sections = [s for s in sections if s.get('path')]
        progress(f'  {len(cues)} sounds, {len(sections)} music section(s)')

        lines_out = [{'id': l.id, 'start': l.start, 'end': l.end, 'text': l.text,
                      'voice': next((n['voice'] for n in voice_notes if n['id'] == l.id), ''),
                      **{k: feel.get(l.id, {}).get(k, '') for k in ('emotion', 'intensity', 'role')}} for l in lines]
        plan = {'name': timeline.name, 'settings': asdict(settings), 'story': analysis.get('story', ''),
                'palette': palette, 'thinking': analysis.get('_thinking', ''), 'lines': lines_out, 'events': events,
                'timeline_xml': timeline.xml_path, 'seconds': seconds, 'budget': budget, 'gap': gap,
                'listener': settings.listen_model if listener else '',
                'dropped': [{'word': m.get('word', ''), 'type': m.get('type', ''), 'why': why} for m, why in dropped]}
        xml = finish(root, folder, plan, seq, voice, sections, cues, pull_backs, settings, progress)
        results.append({'name': timeline.name, 'folder': folder.name, 'sounds': len(cues), 'xml': str(xml)})
    if not results:
        raise ValueError('No speech could be understood in the supplied timeline')
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    return output / results[0]['folder'] / 'report.html'


def remix(plan_file, keep, music=True, progress=print):
    """Save & remix from the report: only the kept sounds, music on/off. Your choices are remembered."""
    from hinglish_zoom.preview import _audio_track
    from hinglish_zoom.xml_apply import Sequence
    plan_file = Path(plan_file)
    folder, root = plan_file.parent, plan_file.parents[4]
    plan = json.loads(plan_file.read_text(encoding='utf-8'))
    # every sound ever proposed stays in the plan, so a sound you untick can be ticked back later
    all_cues = plan.get('all_cues') or plan['cues']
    keep = sorted({int(i) for i in keep if 0 <= int(i) < len(all_cues)})
    learning.record(root, all_cues, keep, video=str(plan_file.resolve()))
    fields = Cue.__dataclass_fields__
    cues = [Cue(**{k: v for k, v in all_cues[i].items() if k in fields}) for i in keep]
    plan.update(all_cues=all_cues, kept=keep)
    sections = [s for s in plan['music'] if s.get('path')] if music else []
    seq = Sequence(plan['timeline_xml'])
    voice = _audio_track(seq.path, plan['seconds'])[:int(plan['seconds'] * 48000)]
    settings = load_settings(root, **{k: v for k, v in plan['settings'].items() if k in ('music_level',)})
    (folder / 'preview.mp4').unlink(missing_ok=True)
    xml = finish(root, folder, plan, seq, voice, sections, cues, [c.target for c in cues if c.pull_back][:1],
                 settings, progress)
    return {'xml_files': [str(xml.resolve())], 'sounds': len(cues)}
