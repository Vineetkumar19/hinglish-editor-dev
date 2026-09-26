"""Sound design with a thinking local model:
voice evidence -> story/emotion/music/moment analysis (Ollama qwen3, thinking, sound-design-brain rules)
-> RAG over the library vector index -> the model picks real files -> peak-synced placement ->
edit sounds (B-roll cuts, zoom landings) -> brain-rule mix -> own tracks in the XML + preview."""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import uuid

import numpy as np
import torch
import torchaudio.functional as AF

from hinglish_broll.phrases import build_phrases
from hinglish_broll.pipeline import timelines_for, transcripts_for
from hinglish_broll.timeline import timeline_words
from hinglish_clean.detection import write_json

from .brain import Brain
from .cues import edit_cues, keep_musical, layer_hits, place_cue, word_time
from .director import analyse, pick
from .library import scan
from .mix import mix
from .prosody import describe_lines
from .report import write_report
from .settings import DENSITY, OLD_SCAN_CACHE, SFX_BEHAVIOUR, load_settings
from .vectors import SoundIndex, document
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


def run(root, input_path, output_format=None, overrides=None, progress=print):
    root = Path(root).resolve()
    settings = load_settings(root, **(overrides or {}))
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'sound' / stamp
    output.mkdir(parents=True)
    progress('Reading your sound library')
    music_assets = scan(settings.music_folder, 'music', root / 'cache' / 'sound', OLD_SCAN_CACHE, progress) \
        if settings.music else []
    sfx_assets = []
    if settings.effects or settings.transitions:
        pro = Path(settings.pro_folder) if settings.pro_folder else root / 'library' / 'sfx-pro'
        for folder in (settings.sfx_folder, pro):          # your library + the professional pack
            sfx_assets += scan(folder, 'sfx', root / 'cache' / 'sound', OLD_SCAN_CACHE, progress)
    brain = Brain(root, settings.think_model, settings.embed_model, progress=progress)
    progress('Building the vector index of your library (first time only)')
    sfx_index, music_index = SoundIndex(sfx_assets, brain), SoundIndex(music_assets, brain)
    moods = sorted({a.category for a in music_assets})
    families = sorted({a.category for a in sfx_assets} & set(SFX_BEHAVIOUR))
    progress(f'  {len(music_assets)} music tracks, {len(sfx_assets)} effects indexed')

    progress('Reading the timeline')
    jobs = timelines_for(root, input_path, output, output_format, progress)
    sources = sorted({s for t, _ in jobs for s in t.sources()})
    progress('Understanding your speech (reusing saved transcripts when available)')
    words_by_source, notes = transcripts_for(root, sources, settings.device, progress)

    from hinglish_zoom.preview import _audio_track, render_preview
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
        count = max(4, round(seconds / every) - (len(broll) + len(lands) if settings.transitions else 0))

        analysis = analyse(brain, kind, lines, voice_notes, events, moods, families, count)
        palette = STYLE_PALETTE.get(settings.style, analysis.get('palette', 'informational'))
        feel = {l['id']: l for l in analysis.get('lines', []) if isinstance(l, dict)}
        progress(f'  Story: {analysis.get("story", "")[:140]}')
        progress(f'  Palette: {palette}')

        by_id = {l.id: l for l in lines}
        moments = []
        for m in analysis.get('moments', []) if settings.effects else []:
            line = by_id.get(m.get('id'))
            if line is None or m.get('type') not in families:
                continue
            moments.append({**m, 'line_text': line.text, 'target': word_time(line, words, m.get('word', '')),
                            'emotion': feel.get(line.id, {}).get('emotion', '')})
        sections = music_sections(analysis.get('music', []), lines, seconds, moods) if settings.music else []

        # RAG: retrieve real candidates for every moment and music section from the vector index.
        exclude = () if palette == 'comedic' else ('funny',)
        effect_candidates = []
        for m in moments:
            query = f"{m['intent']}. {m['type']} sound effect. Feeling: {m['emotion']}. {palette} video."
            hits = sfx_index.search(query, top=6, categories=[m['type']], exclude_genres=exclude,
                                    max_duration=SFX_BEHAVIOUR[m['type']]['max_len'])
            if len(hits) < 3:
                hits += [h for h in sfx_index.search(query, top=6, exclude_genres=exclude) if h not in hits]
            effect_candidates.append([{'asset': a, 'doc': document(a)[:220]} for a, _, _ in hits[:6]])
        music_candidates = []
        for s in sections:
            query = f"{s['mood']} instrumental background music bed for talking, no vocals, no strong melody. {s['why']}"
            hits = music_index.search(query, top=5, categories=[s['mood']]) or music_index.search(query, top=5)
            music_candidates.append([{'asset': a, 'doc': document(a)[:220]} for a, _, _ in hits])

        picks = pick(brain, analysis.get('story', ''), palette, moments, effect_candidates, sections,
                     music_candidates) if moments or sections else {'effects': [], 'music': []}

        cues, used, pull_backs = [], set(), []
        choice = {p.get('moment'): p for p in picks.get('effects', []) if isinstance(p, dict)}
        for i, (m, cands) in enumerate(zip(moments, effect_candidates)):
            p = choice.get(i, {'choice': 0, 'why': 'best vector match'})
            j = p.get('choice', 0)
            if not isinstance(j, int) or not 0 <= j < len(cands):
                continue
            asset = cands[j]['asset']
            if asset.path in used:
                continue
            used.add(asset.path)
            cue = place_cue(asset, m['target'], asset.category if asset.category in SFX_BEHAVIOUR else m['type'],
                            f"{m.get('why', '')} | pick: {p.get('why', '')}", m.get('word', ''), m.get('intent', ''),
                            strength=m.get('strength', 2), emotion=m['emotion'])
            cue.pull_back = bool(m.get('pull_back'))
            cues.append(cue)
        cues = keep_musical(cues, seconds, every, gap)
        pull_backs = [c.target for c in cues if getattr(c, 'pull_back', False)][:2]
        cues += layer_hits(cues, sfx_index, palette, used)
        if settings.transitions:
            cues += edit_cues(sfx_index, palette, [a for a, _ in broll], lands, cues, used)
        cues.sort(key=lambda c: c.time)

        mchoice = {p.get('section'): p for p in picks.get('music', []) if isinstance(p, dict)}
        for i, (s, cands) in enumerate(zip(sections, music_candidates)):
            j = mchoice.get(i, {}).get('choice', 0)
            j = j if isinstance(j, int) and 0 <= j < len(cands) else 0
            if cands:
                s.update(path=cands[j]['asset'].path, loudness=cands[j]['asset'].loudness,
                         pick_why=mchoice.get(i, {}).get('why', ''))
        sections = [s for s in sections if s.get('path')]
        progress(f'  {len(cues)} sounds, {len(sections)} music section(s)')

        progress('Mixing with the sound-design brain rules')
        mixed = mix(voice, sections, cues, folder, pull_backs, settings.music_level)
        xml = export_sound_xml(timeline.xml_path, seq.fps, mixed['stems'], folder / 'SOUND_SEQUENCE.xml')
        preview = None
        if seconds <= PREVIEW_LIMIT:
            progress('Rendering a preview with the new sound')
            render_preview(seq, np.ones(seq.frames), [None] * seq.frames, folder / 'preview.mp4',
                           progress=lambda _: None, audio=mixed['master'].mean(axis=0))
            preview = 'preview.mp4'
        lines_out = [{'id': l.id, 'start': l.start, 'end': l.end, 'text': l.text,
                      'voice': next((n['voice'] for n in voice_notes if n['id'] == l.id), ''),
                      **{k: feel.get(l.id, {}).get(k, '') for k in ('emotion', 'intensity', 'role')}} for l in lines]
        plan = {'settings': asdict(settings), 'story': analysis.get('story', ''), 'palette': palette,
                'thinking': analysis.get('_thinking', ''), 'lines': lines_out, 'events': events,
                'music': [{k: v for k, v in s.items()} for s in sections],
                'cues': [c.to_dict() for c in cues], 'pull_backs': pull_backs,
                'voice_db': mixed['voice_db'], 'voice_peak': mixed['voice_peak'], 'stems': mixed['stems']}
        write_json(folder / 'sound-plan.json', plan)
        write_report(folder / 'report.html', timeline.name, plan, preview)
        results.append({'name': timeline.name, 'folder': folder.name, 'sounds': len(cues), 'xml': str(xml)})
    if not results:
        raise ValueError('No speech could be understood in the supplied timeline')
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    return output / results[0]['folder'] / 'report.html'
