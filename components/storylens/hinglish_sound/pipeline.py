"""Sound design with a thinking local model:
voice evidence -> story/emotion/music/moment analysis (Ollama qwen3, thinking, sound-design-brain rules)
-> RAG over the library vector index -> the model picks real files -> peak-synced placement ->
edit sounds (B-roll cuts, zoom landings) -> brain-rule mix -> own tracks in the XML + preview."""
from dataclasses import asdict, replace
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


MAX_SECTIONS = {'short': 2, 'long_per_minute': .5}


def music_sections(plan, lines, seconds, moods):
    """New spotting maps retain deliberate music gaps; old saved answers retain their bed policy."""
    from .spotting import explicit, resolve_sections
    if explicit(plan):
        return [s for s in resolve_sections(plan,lines,seconds,moods) if s['mode']=='music']
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
        return []
    if seconds <= 180:
        ending = spans[-1] if len(spans) > 1 else None
        body = [s for s in spans if s is not ending]
        weight = {}
        for s in body:
            weight[s['mood']] = weight.get(s['mood'], 0) + s['end'] - s['start']
        main_mood = max(weight, key=weight.get)
        main = next(s for s in body if s['mood'] == main_mood)
        sections = [{'start': 0.0, 'mood': main_mood, 'energy': main['energy'],
                     'why': '; '.join(dict.fromkeys(s['why'] for s in body if s['mood'] == main_mood))}]
        if ending and ending['mood'] != main_mood and ending['end'] - ending['start'] >= max(5.0, .12 * seconds):
            sections.append({'start': ending['start'], 'mood': ending['mood'], 'energy': ending['energy'],
                             'why': ending['why'] + ' (sustained emotional turn)'})
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
    if type(picked) is not int or not 0 <= picked < count:
        return []
    first = picked
    return [first] + [j for j in range(count) if j != first]


def selection_order(picked, count, human_review=False):
    ranked = _rank(picked, count)
    return ranked[:1] if human_review else ranked


def open_listener(root, settings, progress):
    if not settings.listen:
        return None
    try:
        from .listen import Listener
        progress('Loading the listening model (CLAP: it hears what each sound really is)')
        return Listener(root, settings.listen_model, settings.device, settings.cpu_threads)
    except Exception as error:
        from hinglish_cut.model_preferences import preferences
        if preferences(root).get('require_cuda_inference'):
            raise RuntimeError('RTX sound matching failed; automatic tag-only fallback is disabled') from error
        progress(f'  Listening model unavailable ({error}); choosing by names and tags only')
        return None


def finish(root, folder, plan, seq, voice, sections, cues, pull_backs, settings, progress):
    """Mix, measure (mix QA), export the XML, render the preview and write the report."""
    from hinglish_zoom.preview import render_preview
    from .credits import write as write_credits
    from copy import deepcopy
    plan.setdefault('all_music',deepcopy(sections))
    plan['sound_sources'] = write_credits(folder, sections, cues)
    progress('Mixing with the sound-design brain rules')
    gain = tune.value('sound', 'effect_gain_db', 0.0)       # quality-check correction: louder effects
    render_cues = [replace(c, offset_db=c.offset_db + gain) for c in cues]
    source_audio=None
    if plan.get('preserved_source_audio'):
        from .library import decode
        source_audio=decode(plan['preserved_source_audio']['path'])
    mixed = mix(voice, sections, render_cues, folder, pull_backs,
                settings.music_level + tune.value('sound', 'music_trim_db', 0.0),
                layered=settings.layered, dialogue_present=plan.get('has_dialogue'),
                composed=bool(plan.get('composition_version',0)),source_audio=source_audio)
    qa = mix_qa(voice, mixed['bed'], mixed['effects'], mixed['master'], mixed['speech'], cues,
                plan['budget'], plan['gap'], layered=settings.layered,composed=bool(plan.get('composition_version',0)))
    failed = [r for r in qa if not r['passed']]
    progress(f'  Mix check: {len(qa) - len(failed)}/{len(qa)} passed' +
             ('' if not failed else ' (' + '; '.join(f"{r['check']}: {r['value']}" for r in failed[:3]) + ')'))
    xml = export_sound_xml(plan['timeline_xml'], seq.fps, mixed['stems'].get('editor',mixed['stems']), Path(folder) / 'SOUND_SEQUENCE.xml')
    preview = None
    if plan['seconds'] <= PREVIEW_LIMIT:
        progress('Rendering a preview with the new sound')
        render_preview(seq, np.ones(seq.frames), [None] * seq.frames, Path(folder) / 'preview.mp4',
                       progress=lambda _: None, audio=mixed['master'],device=settings.device)
        preview = 'preview.mp4'
    plan.update(music=[{k: v for k, v in s.items()} for s in sections], cues=[c.to_dict() for c in cues],
                pull_backs=pull_backs, voice_db=mixed['voice_db'], voice_peak=mixed['voice_peak'],
                words_db=mixed['words_db'],
                words_full_db=mixed['words_full_db'],
                stems=mixed['stems'], mix_qa=qa, preview=preview)
    if plan.get('human_review'):
        from .human_review import bind_timeline
        bind_timeline(plan['human_review'], plan['cues'])
    plan['notices'] = list(plan.get('provider_notes', []))
    if plan.get('source_audio'):plan['notices'].append(plan['source_audio']['notice'])
    if plan.get('preserved_source_audio'):
        plan['notices'].append('Your original stereo audio is retained, including its existing song. Added effects are separate layers.')
    expected_music=not plan.get('spotting') or any(s['mode']=='music' for s in plan['spotting'])
    if settings.music and not sections and expected_music:
        plan['notices'].append('No music candidate matched this story. Effects are saved; add suitable instrumental tracks and regenerate.')
    if plan.get('spotting'):
        labels={'music':'Music and effects','effects_only':'Effects without music','voice_only':'Voice alone'}
        plan['notices'].append('Sound plan: '+'; '.join(f"{s['start']:.1f}–{s['end']:.1f}s {labels[s['mode']]}" for s in plan['spotting']))
    if not settings.vision:
        plan['notices'].append('Scene reading was disabled; this result used speech and editor events only.')
    if any(c.timing_precision == 'visual_interval' for c in cues):
        plan['notices'].append('Visible action sounds use sampled frame intervals (about half a second). Review precise contacts; saved editor events keep their measured timing.')
    write_json(Path(folder) / 'sound-plan.json', plan)
    if plan.get('human_review'):
        from .keyword_folders import premiere_project
        progress('Saving Sound Design keyword folders and the separate draft timeline')
        premiere_project(Path(folder)/'sound-plan.json')
    guard.save(folder)
    write_report(Path(folder) / 'report.html', plan['name'], plan, preview)
    return xml


def run(root, input_path, output_format=None, overrides=None, progress=print, script=''):
    root = Path(root).resolve()
    settings = load_settings(root, **(overrides or {}))
    if settings.human_review:
        settings.evaluate = False
        settings.listen = False
        progress('Qwen chooses the first take and alternatives. You review; no second-model veto.')
    from hinglish_cut.compute_policy import heavy_device
    settings.device=heavy_device(root,settings.device)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'sound' / stamp
    output.mkdir(parents=True)
    taste_data = learning.load(root)
    banned = learning.banned(taste_data)
    if banned:
        progress(f'  {len(banned)} sounds you removed before are never used again')
    progress('Reading your sound library')
    music_assets = []
    if settings.music:
        for library in dict.fromkeys((settings.music_folder, str(root/'library/owner-sound-packs/music'),str(root/'library/music-online'))):
            music_assets += scan(library, 'music', root/'cache/sound', OLD_SCAN_CACHE, progress)
    if settings.music and not music_assets:
        raise ValueError('Sound music library empty: ' + str(settings.music_folder))
    sfx_assets = []
    if settings.effects or settings.transitions:
        pro = Path(settings.pro_folder) if settings.pro_folder else root / 'library' / 'sfx-pro'
        for folder in (settings.sfx_folder, pro, root / 'library/sound-online', root/'library/owner-sound-packs/sfx'):
            sfx_assets += scan(folder, 'sfx', root / 'cache' / 'sound', OLD_SCAN_CACHE, progress)
        sfx_assets = list({str(Path(a.path).resolve()): a for a in sfx_assets}.values())
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
        if script.strip():                       # misheard names ("Madhu rahi", "rapid ho") get the script spelling
            from hinglish_visuals.script import apply_script
            words, fixed = apply_script(words, script)
            if fixed:
                progress('  Names fixed from your script: ' + ', '.join(
                    f'"{c["heard"]}" -> {c["script_spelling"]}' for c in fixed[:12]))
        lines = build_phrases(words)
        seq = Sequence(timeline.xml_path)
        seconds = seq.frames / float(seq.fps)
        from .events import collect, normalize, choose
        measured = collect(seq, input_path)
        from .tool_bridge import clipwing_motion
        picture_events,clipwing_note=clipwing_motion(root,input_path,folder,seconds,measured,progress) \
            if settings.effects and settings.layered else ([], 'Clipwing motion analysis not requested')
        measured+=picture_events
        from .scenes import inspect
        observations = inspect(root, seq, folder, measured, progress, temporal=settings.layered) if settings.vision else []
        spoken = bool(lines)
        if not spoken:
            from hinglish_broll.phrases import Phrase
            lines = [Phrase(i, o['time'], min(seconds, o['time'] + 15),
                            'No spoken dialogue. Visible scene: ' + o.get('setting', '') + '. ' + o.get('action', ''))
                     for i, o in enumerate(observations)]
            if not lines:
                raise ValueError('Sound needs scene evidence for silent video')
        voice = _audio_track(seq.path, seconds)[:int(seconds * 48000)]
        separated,preserved=None,None
        if settings.remove_source_music:
            from .separation import isolate
            voice,separated=isolate(root,voice,folder,progress,settings.device)
        else:
            from .source_audio import original_mix
            from .mix import write_wav
            base=original_mix(seq.path,seconds)
            preserved={'path':str(write_wav(Path(folder)/'original-audio.wav',base)),
                       'kind':'original stereo mix','source_music_removed':False,'channels':2}
        progress('Listening to how each line is said (loudness, pitch, pace)')
        voice16 = AF.resample(torch.from_numpy(voice), 48000, 16000).numpy()
        voice_notes = describe_lines(voice16, lines) if spoken else []
        broll = seq.blocked_seconds()
        lands = zoom_lands(seq)
        measured += [dict(time=t, end=min(seconds, t + .1), kind='zoom', label='zoom landing') for t in lands]
        measured += [dict(time=a, end=b, kind='broll', label='B-roll cut-in') for a, b in broll]
        if settings.effects:
            from .composition import ambience_events
            measured+=ambience_events(observations,seconds)
            if settings.layered:
                measured += [event for o in observations for event in o.get('action_events',[])]
        measured = normalize(measured, seconds)
        if not settings.transitions:
            measured = [e for e in measured if e['kind'] in ('ambience','foley')]
        if not settings.effects:
            measured = [e for e in measured if e['kind'] not in ('ambience','foley')]
        events = list(measured)
        form = settings.content_form if settings.content_form!='auto' else ('short' if seconds <= 180 else 'long')
        keyword_review = settings.human_review
        kind = ('vertical Instagram Reel / YouTube Short' if form == 'short' and seq.height > seq.width
                else 'short video' if form == 'short' else 'long-form YouTube video')
        if settings.style != 'auto':
            events.append(f'The editor asked for a {settings.style} sound style.')
        every, gap = DENSITY[form][settings.density]
        budget = max(2, math.ceil(seconds / every * tune.value('sound', 'count_scale', 1.0)))
        edit_limit = min(len(measured), max(1, int(budget * EDIT_SHARE)))
        ai_count = max(1, budget - edit_limit)
        if settings.layered:
            gap = min(gap, {'low':1.5,'medium':.65,'high':.3}[settings.density])
            budget=max(budget,math.ceil(seconds / {'low':6.,'medium':2.,'high':1.}[settings.density]))
            progress(f'Planning up to {budget} action groups, with complementary layers and separate ambience')
        else:
            progress(f'  Sound budget: {budget} sounds, at least {gap:.1f}s apart')
        from .composition import policy, speech_events
        composition=policy(root,seconds,settings.density) if settings.layered else None
        from .reference_memory import context as sound_guidance
        from hinglish_cut.creative_memory import context as creative_guidance
        guide_query='sound design soundtrack '+(script or ' '.join(l.text for l in lines))
        write_json(Path(folder)/'sound-guidance.json',{
            'kind':'Available retrieved reference guidance; not model-weight training or a listening receipt',
            'sound_references':sound_guidance(root,guide_query),
            'workflow_references':creative_guidance(root,guide_query),
            'processing':'Bounded filters, pan, fades and speech ducking baked into editable stems',
            'models':{'planning':brain.model,'vision':'configured local Vision','audio_matching':settings.listen_model if listener else 'title/tag retrieval'},
            'creator_profile':'Preserved through the existing full-profile injection on model calls'})
        if composition:
            ai_count=budget
            gap=.08  # prevent exact double-triggering without pruning nearby edit/word beats
        analysis = analyse(brain, kind, lines, voice_notes, events, moods, families, ai_count,
                           learning.taste(taste_data), progress, script, observations,composition)
        from .composition import rhetorical_palette
        palette_review=rhetorical_palette(brain,analysis,settings.style,composition,observations)
        palette=palette_review['palette']
        from .acoustic import project_palette, palette_query, reusable, source_identity
        sound_palette=project_palette(analysis.get('sound_palette'),palette)
        if composition:
            composition.update(authoring='contextual_layers',sound_palette=sound_palette)
        feel = {l['id']: l for l in analysis.get('lines', []) if isinstance(l, dict)}
        progress(f'  Story: {analysis.get("story", "")[:140]}')
        progress(f'  Palette: {palette}')

        kept_moments, dropped = validate_moments(analysis, lines, families, palette) if settings.effects and spoken else ([], [])
        for m, why in dropped:
            progress(f'  Skipped a sound on "{m.get("word", "")}": {why}')
        by_id = {l.id: l for l in lines}
        moments = [{**m, 'line_text': by_id[m['id']].text, 'target': word_time(by_id[m['id']], words, m.get('word', ''), m.get('word_index')),
                    'emotion': feel.get(m['id'], {}).get('emotion', '')} for m in kept_moments]
        dropped += [(m, 'Word timing was missing or ambiguous; no effect placed') for m in moments if m['target'] is None]
        moments = [m for m in moments if m['target'] is not None]
        if settings.layered:
            from .layers import augment_moments
            anchors=speech_events(lines,words,moments) if settings.effects and spoken else []
            for anchor in anchors:
                anchor['emotion']=feel.get(anchor['line_id'],{}).get('emotion',palette)
            moments=augment_moments(brain,measured,moments,analysis.get('story',''),palette,budget,families,
                                    speech_events=anchors,composition=composition)
        else:
            for start in range(0, len(measured), 30):
                chunk = measured[start:start + 30]
                moments += choose(brain, chunk, analysis.get('story', ''), palette,
                                  max(0, edit_limit - sum('event_id' in m for m in moments)), families)
        from .spotting import explicit,resolve_sections,mask_cues
        spotting=resolve_sections(analysis['music'],lines,seconds,moods) if settings.music and explicit(analysis.get('music')) else []
        sections = music_sections(analysis.get('music', []), lines, seconds, moods) if settings.music else []
        if spotting:
            moments=[m for m in moments if not any(s['mode']=='voice_only' and s['start']<=m['target']<s['end'] for s in spotting)]

        from .providers import status as provider_status
        from .online_sources import Fallback
        online=Fallback(root,enabled=settings.online_sounds)
        provider_notes=online.notes

        # RAG: retrieve real candidates for every moment and music section (names + what they sound like).
        from .relevance import delivery_label_only
        descriptive=[]
        for moment in moments:
            if delivery_label_only(moment.get('intent'),moment.get('emotion')):
                dropped.append((moment,'The proposed sound only repeats the delivery emotion; no acoustic source was described.'))
            else:descriptive.append(moment)
        moments=descriptive
        exclude = () if palette == 'comedic' else ('funny',)
        effect_candidates,source_rejections,offered_candidates = [],[],{}
        from .relevance import source_matches
        acoustic_direction=palette_query(sound_palette)
        effect_queries=[f"{m['intent']}. {m['type']} sound effect. Feeling: {m['emotion']}. {palette} video. {acoustic_direction}" for m in moments]
        context='under narration, no competing lead melody' if spoken else 'cinematic instrumental foreground score'
        music_queries=[f"{s['mood']} {palette} instrumental background music, {context}. {s['why']}. {acoustic_direction}" for s in sections]
        from .composition import warm_queries
        progress(f'Matching {len(moments)} designed layers to the saved sound library')
        warm_queries(brain,effect_queries,music_queries)
        for m,query in zip(moments,effect_queries):
            from .retrieval import effect_candidates as retrieve_effects
            accepted,rejections=retrieve_effects(sfx_index,query,m,exclude,banned,folder_options=keyword_review)
            if not accepted:
                sfx_index=online.extend(sfx_index,m['intent'],m['type'],'sfx',brain,listener,progress,m.get('duration',3.))
                accepted,extra=retrieve_effects(sfx_index,query,m,exclude,banned,folder_options=keyword_review)
                rejections+=extra
            source_rejections.extend(rejections)
            from .acoustic import candidate_slate
            hits=candidate_slate(accepted,m,offered_candidates,limit=20 if keyword_review else 6)
            # An empty/small category is a coverage gap, not permission to suggest
            # a random physical recording as a rhetorical accent.
            effect_candidates.append([{'asset': a, 'doc': sfx_index.docs[sfx_index.assets.index(a)]}
                                      for a, _, _ in hits])
        music_candidates = []
        for s,query in zip(sections,music_queries):
            candidate_moods=[s['mood']]+(['funny','lofi'] if palette=='comedic' else [])
            hits = (music_index.search(query, top=5, categories=candidate_moods, instrumental_only=True, banned=banned)
                    or music_index.search(query, top=5, instrumental_only=True, banned=banned))
            if not hits:
                music_index=online.extend(music_index,query,s['mood'],'music',brain,listener,progress,3.)
                hits=music_index.search(query,top=5,categories=candidate_moods,instrumental_only=True,banned=banned)
            music_candidates.append([{'asset': a, 'doc': music_index.docs[music_index.assets.index(a)][:260]}
                                     for a, _, _ in hits])

        from .tool_bridge import earshot_evidence
        earshot_note=earshot_evidence(root,folder,moments,effect_candidates,progress) if settings.effects else {'status':'not_requested','count':0}
        picks = pick(brain, analysis.get('story', ''), palette, moments, effect_candidates, sections,
                     music_candidates, progress,sound_palette=sound_palette,human_review=keyword_review) if moments or sections else {'effects': [], 'music': []}
        write_json(Path(folder) / 'sound-decisions.json', {
            'planning_model': brain.model, 'embedding_model': brain.embed_model,
            'local_tools':{'clipwing':clipwing_note,'earshot':earshot_note,'openverse':provider_status(root).get('openverse')},
            'analysis': analysis, 'sound_palette':sound_palette,'moments': moments, 'picks': picks,
            'source_subject_rejections':source_rejections,
            'effects': [[c['asset'].path for c in cs] for cs in effect_candidates],
            'music': [[c['asset'].path for c in cs] for cs in music_candidates]})

        # The evaluator listens to the picked file; a failed one is replaced by the next candidate.
        cues, used, grouped_used = [], set(), set()
        source_history,selection_audit={},[]
        choice = {p.get('moment'): p for p in picks.get('effects', []) if isinstance(p, dict)}
        for i, (m, cands) in enumerate(zip(moments, effect_candidates)):
            p = choice.get(i, {'choice': -1, 'why': 'No explicit selection'})
            rejected, chosen, verdict, cue = [], None, None, None
            for j in selection_order(p.get('choice', -1), len(cands), settings.human_review):
                asset = cands[j]['asset']
                if not settings.human_review and ((m.get('group_id'),asset.path) in grouped_used if settings.layered else asset.path in used):
                    continue
                if settings.layered and not settings.human_review:
                    identity=source_identity(asset.path)
                    allowed,reuse_why=reusable(identity,m,source_history)
                    if not allowed:
                        rejected.append({'file':Path(asset.path).name,'passed':False,'reasons':[reuse_why]})
                        selection_audit.append(dict(event_id=m.get('event_id'),group_id=m.get('group_id'),
                            file=asset.path,source_identity=identity,accepted=False,reason=reuse_why))
                        continue
                if settings.evaluate:
                    k = sfx_index.assets.index(asset)
                    verdict = check_effect(listener, None if sfx_index.audio is None else sfx_index.audio[k],
                                           sfx_index.facts[k], m['type'], m.get('intent', ''), palette)
                    if verdict.passed is False:
                        rejected.append({'file': Path(asset.path).name, **verdict.to_dict()})
                        progress(f'  Evaluator FAIL {Path(asset.path).name}: {"; ".join(verdict.reasons)}')
                        continue
                try:
                    cue=place_cue(asset,m['target'],m['type'],
                        f"{m.get('why','')} | pick: {p.get('why','')}",m.get('word',''),m.get('intent',''),
                        strength=m.get('strength',2),emotion=m['emotion'],source=m.get('source','ai'),
                        requested_length=m.get('duration'))
                except ValueError:
                    rejected.append({'file':Path(asset.path).name,'passed':False,
                                     'reasons':['The requested short excerpt contains no usable sound.']})
                    continue
                chosen = asset
                break
            if chosen is None:
                progress(f'  No file really sounds like "{m.get("intent", "")}"; no sound on "{m.get("word", "")}"')
                dropped.append((m,'No candidate was accepted for this layer; skipped instead of substituting unrelated audio.'))
                continue
            used.add(chosen.path)
            grouped_used.add((m.get('group_id'),chosen.path))
            if settings.layered:
                identity=source_identity(chosen.path)
                allowed,reuse_why=reusable(identity,m,source_history)
                source_history.setdefault(identity,[]).append({k:m.get(k) for k in
                    ('group_id','type','role','reuse_key','reuse_reason','word','intent')})
                selection_audit.append(dict(event_id=m.get('event_id'),group_id=m.get('group_id'),
                    file=chosen.path,source_identity=identity,accepted=True,reason=reuse_why,reuse_key=m.get('reuse_key','')))
            cue.offset_db+=m.get('level_db',0.)
            from .processing import validate as validate_processing
            cue.processing=validate_processing(m.get('processing',{}))
            cue.alternatives=[dict(path=c['asset'].path,name=c['asset'].name,
                status='selected' if c['asset'].path==chosen.path else 'rejected' if any(r['file']==Path(c['asset'].path).name for r in rejected) else 'not_selected') for c in cands]
            cue.sync=dict(method='measured_energy_peak' if SFX_BEHAVIOUR[m['type']]['align']=='peak' else 'event_start',timeline_target=cue.target,
                          timeline_start=cue.time,source_offset=cue.source_offset,
                          source_event_time=cue.source_offset+cue.target-cue.time,
                          semantic_hitpoint_verified=False)
            cue.anchor_time=m.get('anchor_time',m['target'])
            cue.timing_offset=m.get('offset',0.)
            if m['type'] == 'ambience':
                cue.length = min(cue.length, m.get('length', cue.length))
            if settings.layered:
                cue.group_id=m.get('group_id','')
                cue.role=m.get('role','detail')
                cue.timing_precision=m.get('timing_precision','editor')
                cue.uncertainty=m.get('uncertainty',0.)
                if cue.timing_precision=='visual_interval':
                    cue.length=min(cue.length,m['length'])
            cue.pull_back, cue.trigger, cue.line = bool(m.get('pull_back')), m.get('trigger', ''), m['line_text']
            cue.evaluation = {**(verdict.to_dict() if verdict else {'passed': None}), 'rejected': rejected}
            cues.append(cue)
        if settings.layered:
            from .layers import select_layers
            cues = select_layers(cues,seconds,budget,gap,composed=True)
        else:
            cues = keep_musical(cues, seconds, seconds / max(1, budget), gap)
        pull_backs = [c.target for c in cues if c.pull_back][:1]
        if not settings.layered:
            cues += layer_hits(cues, sfx_index, palette, used, banned=banned, evaluate=settings.evaluate)
        cues.sort(key=lambda c: c.time)
        if spotting:
            cues,quiet_dropped=mask_cues(cues,spotting)
            dropped.extend((d,d['why']) for d in quiet_dropped)
            for cue in cues:
                cue.sync.update(timeline_start=cue.time,source_offset=cue.source_offset)

        mchoice = {p.get('section'): p for p in picks.get('music', []) if isinstance(p, dict)}
        for i, (s, cands) in enumerate(zip(sections, music_candidates)):
            for j in selection_order(mchoice.get(i, {}).get('choice', -1), len(cands), settings.human_review):
                asset = cands[j]['asset']
                verdict = check_music(music_index.facts_for(asset), s.get('energy', 2), s['mood']) \
                    if settings.evaluate else None
                if verdict is not None and verdict.passed is False:
                    progress(f'  Evaluator FAIL music {Path(asset.path).name}: {"; ".join(verdict.reasons)}')
                    continue
                s.update(path=asset.path, loudness=asset.loudness, pick_why=mchoice.get(i, {}).get('why', ''),
                         evaluation=verdict.to_dict() if verdict else None)
                from .music import passage
                reveals = [c.target - s['start'] for c in cues if c.pull_back and s['start'] <= c.target < s['end']]
                s.update(passage(asset.path, s['end'] - s['start'], s.get('energy', 2),
                                 reveals[0] if reveals else None))
                break
        sections = [s for s in sections if s.get('path')]
        if not sections and not cues and not (spotting and all(s['mode']=='voice_only' for s in spotting)):
            raise ValueError('Sound no suitable layers: no library candidates matched the requested story and actions')
        progress(f'  {len(cues)} sounds, {len(sections)} music section(s)')

        lines_out = [{'id': l.id, 'start': l.start, 'end': l.end, 'text': l.text,
                      'voice': next((n['voice'] for n in voice_notes if n['id'] == l.id), ''),
                      **{k: feel.get(l.id, {}).get(k, '') for k in ('emotion', 'intensity', 'role')}} for l in lines]
        plan = {'name': timeline.name, 'settings': asdict(settings), 'story': analysis.get('story', ''),
                'composition_version':3 if composition else 0,'composition':composition,
                'palette_review':palette_review,
                'sound_palette':sound_palette,'selection_policy':'contextual-layers-explicit-reuse-v1',
                'spotting':spotting,'arrangement_version':1,
                'selection_audit':selection_audit,
                'palette': palette, 'thinking': analysis.get('_thinking', ''), 'lines': lines_out, 'events': events,
                'timeline_xml': timeline.xml_path, 'seconds': seconds, 'budget': budget, 'gap': gap,
                'visual_observations': observations, 'measured_events': measured, 'has_dialogue': spoken,
                'source_audio':separated,
                'preserved_source_audio':preserved,
                'providers': provider_status(root), 'provider_notes': provider_notes,
                'local_tools':{'clipwing':clipwing_note,'earshot':earshot_note,'openverse':provider_status(root).get('openverse')},
                'listener': settings.listen_model if listener else '',
                'dropped': [{'word': m.get('word', ''), 'type': m.get('type', ''), 'why': why} for m, why in dropped]}
        plan['content_form']=form
        if keyword_review:
            from .human_review import build
            plan['human_review'] = build(moments, effect_candidates, picks)
            plan['selection_policy'] = 'qwen-first-human-review-v1'
        xml = finish(root, folder, plan, seq, voice, sections, cues, pull_backs, settings, progress)
        results.append({'name': timeline.name, 'folder': folder.name, 'sounds': len(cues), 'xml': str(xml)})
    if not results:
        raise ValueError('No speech could be understood in the supplied timeline')
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    return output / results[0]['folder'] / 'report.html'


def remix(plan_file, keep, music=True, progress=print, *, remember_choices=True):
    """Save & remix from the report: only the kept sounds, music on/off. Your choices are remembered."""
    from hinglish_zoom.preview import _audio_track
    from hinglish_zoom.xml_apply import Sequence
    plan_file = Path(plan_file)
    folder, root = plan_file.parent, plan_file.parents[4]
    plan = json.loads(plan_file.read_text(encoding='utf-8'))
    # every sound ever proposed stays in the plan, so a sound you untick can be ticked back later
    all_cues = plan.get('all_cues') or plan['cues']
    keep = sorted({int(i) for i in keep if 0 <= int(i) < len(all_cues)})
    fields = Cue.__dataclass_fields__
    cues = [Cue(**{k: v for k, v in all_cues[i].items() if k in fields}) for i in keep]
    from .processing import validate as validate_processing
    for cue in cues:validate_processing(cue.processing)
    if remember_choices:learning.record(root, all_cues, keep, video=str(plan_file.resolve()))
    plan.update(all_cues=all_cues, kept=keep)
    from .spotting import music_for_remix
    sections = music_for_remix(plan,music)
    seq = Sequence(plan['timeline_xml'])
    voice = _audio_track(seq.path, plan['seconds'])[:int(plan['seconds'] * 48000)]
    if plan.get('source_audio'):
        import soundfile as sf
        source=Path(plan['source_audio']['path'])
        if not source.is_file():raise ValueError('The separated voice is missing. Regenerate Sound Design before remixing; your original is kept.')
        audio,sr=sf.read(source,always_2d=True,dtype='float32')
        if sr!=48000 or len(audio)!=len(voice):raise ValueError('The saved voice has different timing. Regenerate Sound Design before remixing.')
        voice=audio.mean(axis=1)
    settings = load_settings(root, **{k: v for k, v in plan['settings'].items()
                                     if k in ('music_level', 'vision', 'music', 'layered', 'human_review', 'content_form')})
    settings.music = music
    (folder / 'preview.mp4').unlink(missing_ok=True)
    xml = finish(root, folder, plan, seq, voice, sections, cues, [c.target for c in cues if c.pull_back][:1],
                 settings, progress)
    return {'xml_files': [str(xml.resolve())], 'sounds': len(cues)}
