"""Persist source-linked Vineet reference evidence and local E5 vectors.

This imports measurements and offline CLIP/CLAP candidates, not new animation
designs or fine-tuned model weights. Original video and reviewed notes stay intact.
"""
import csv
import html
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'output/reference-analysis/cricket-documentaries'
STYLE = 'beneath-documentary-edit'  # Stable saved-job and retrieval identifier.
NAME = 'vineet documentry edit'
from hinglish_niche.reference_dna import StyleDatabase
from hinglish_niche.style_memory import StyleEmbedder, search
from tools.analyze_documentary_reference import facts
from tools.build_crick_edit_dna import aligned_scenes, motion, transitions


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def stamp(t):
    return f'{int(t)//60}:{int(t)%60:02}'


def narration(folder, a, b):
    """ASR uses source-media time. Include intersecting segments, labelled fallible."""
    lines = read(folder / 'transcript.json')
    return ' '.join(s['text'] for s in lines if s['start'] < b and s['end'] > a)


def nearby_chapters(notes, a, b):
    return [c for c in notes.get('chapters', []) if c['start'] < b and c['end'] > a]


def add_vectors(embedder, records):
    for start in range(0, len(records), 128):
        batch = records[start:start + 128]
        vectors = embedder.encode([r['text'] for r in batch])
        for row, vector in zip(batch, vectors):
            row.update(vector=vector, model=embedder.model_name)
    return records


def common_data(item, status):
    return {'source_path': item['path'], 'source_name': item['name'], 'status': status}


def compile_source(item):
    folder = BASE / item['slug']
    receipt = read(folder / 'dna-coverage.json')
    if receipt['source'] != facts(Path(item['path'])):
        raise ValueError('Reference changed after scanning: ' + item['name'])
    scenes, offset = aligned_scenes(folder)
    visual = read(folder / 'scene-interpretations.json')
    audio = read(folder / 'audio-interpretations.json')
    audio_metrics = read(folder / 'audio-analysis.json')
    events = read(folder / 'sound-event-candidates.json')
    notes = read(folder / 'review-notes.json')
    if not (folder / 'transcript.txt').exists():
        lines = read(folder / 'transcript.json')
        (folder / 'transcript.txt').write_text('\n'.join(
            f'[{s["start"]:.2f}–{s["end"]:.2f}] {s["text"]}' for s in lines), encoding='utf-8')
    if visual['source'] != receipt['source']:
        raise ValueError('Stale semantic scene analysis: ' + item['name'])
    if len(scenes) != len(visual['scenes']) or sum(s['frames'] for s in scenes) != receipt['native_frames_measured']:
        raise ValueError('Incomplete frame/scene coverage: ' + item['name'])
    if audio.get('audio_available', True) and abs(audio['analysed_seconds'] - audio_metrics['duration']) > .025:
        raise ValueError('Incomplete audio interpretation: ' + item['name'])
    if abs(sum(s['duration'] for s in scenes) - item['seconds']) > .02:
        raise ValueError('Incomplete scene timeline: ' + item['name'])
    records = []
    layouts, typefaces, textures, movement = Counter(), Counter(), Counter(), Counter()
    candidate_status = ('Native-frame metrics are measurements. CLIP/CLAP labels are similarity candidates. '
                        'Chapter notes are earlier reviewed samples, not semantic inspection of every frame. '
                        'Narration is automatic ASR; names and statistics are not verified facts.')
    for scene, interpretation in zip(scenes, visual['scenes']):
        if scene['index'] != interpretation['index']:
            raise ValueError('Scene index mismatch')
        a, b = scene['start'], scene['end']
        candidates = interpretation['candidates']
        layout = candidates['layout'][0]['label']
        typography = candidates['typography'][0]['label']
        texture = candidates['texture'][0]['label']
        cues = motion(scene)
        for counter, label in [(layouts, layout), (typefaces, typography), (textures, texture)]:
            counter[label] += scene['duration']
        for cue in cues:
            movement[cue] += scene['duration']
        windows = [w for w in audio['windows'] if w['start'] < b and w['end'] > a]
        heard = list(dict.fromkeys(w['candidates'][0]['label'] for w in windows))
        chapters = nearby_chapters(notes, a, b)
        reviewed = '; '.join(c['look'] + ': ' + c['observations'] for c in chapters)
        text = (f'{NAME}. {item["name"]} {stamp(a)}–{stamp(b)}. '
                f'Scene/layout candidate {layout}; typography family candidate {typography}; '
                f'overlay/texture candidate {texture}. Image/camera movement cues: {", ".join(cues)}. '
                f'Colour mean RGB {scene["colour"]["mean_rgb"]}, saturation {scene["colour"]["saturation"]:.1f}. '
                f'Editing pace: scene lasts {scene["duration"]:.2f}s. Mixed audio candidates: {", ".join(heard)}. '
                f'Reviewed chapter context: {reviewed[:650]}. ASR narration: {narration(folder, a, b)[:700]}')
        records.append({'start': a, 'end': b, 'kind': 'scene-evidence', 'text': text,
                        'data': {**common_data(item, candidate_status), 'scene': scene['index'],
                                 'representative': scene['representative'], 'visual_candidates': candidates,
                                 'motion_cues': cues, 'camera_estimate': scene['camera_estimate'],
                                 'colour': scene['colour'], 'reviewed_chapters': chapters,
                                 'audio_candidates': heard}})
    for chapter in notes.get('chapters', []):
        records.append({'start': chapter['start'], 'end': min(chapter['end'], item['seconds']),
                        'kind': 'reviewed-chapter',
                        'text': f'{NAME}. {item["name"]} {stamp(chapter["start"])}–{stamp(chapter["end"])}. '
                                f'Reviewed chapter: {chapter["look"]}. {chapter["observations"]}',
                        'data': {**common_data(item, notes['coverage_limit']), 'chapter': chapter,
                                 'visual_review': notes.get('visual_review', {})}})
    for window in audio['windows']:
        labels = ', '.join(c['label'] for c in window['candidates'])
        records.append({'start': window['start'], 'end': window['end'], 'kind': 'audio-window',
                        'text': f'{NAME}. {item["name"]} {stamp(window["start"])}–{stamp(window["end"])}. '
                                f'Voice activity {window["speech_fraction"]:.3f}. '
                                f'Background music, ambience and mixed-audio candidates: {labels}. '
                                'No isolated stems or confirmed track identity.',
                        'data': {**common_data(item, audio['status']), 'window': window}})
    boundaries = [s['start'] for s in scenes[1:]]
    for event in events['events']:
        nearest = min(boundaries, key=lambda t: abs(t - event['seconds'])) if boundaries else None
        event.update(nearest_scene_boundary=nearest,
                     offset_from_scene_boundary=round(event['seconds'] - nearest, 4) if nearest is not None else None)
        labels = ', '.join(c['label'] for c in event['candidates'])
        records.append({'start': max(0, event['seconds'] - .5), 'end': min(item['seconds'], event['seconds'] + 1.2),
                        'kind': 'sound-event-candidate',
                        'text': f'{NAME}. {item["name"]} at {event["seconds"]:.2f}s. '
                                f'Short sound effect / impact / riser / whoosh candidates: {labels}. '
                                f'Nearest cut candidate offset {event["offset_from_scene_boundary"]}s. '
                                'Unverified mixed sound; speech, crowd or drums may resemble an effect.',
                        'data': {**common_data(item, event['status']), 'event': event}})
    write(folder / 'aligned-sound-events.json', events)
    regions = audio_metrics.get('tempo_regions', [])
    for region in regions:
        records.append({'start': region['start'], 'end': region['end'], 'kind': 'rhythm-region',
                        'text': f'{NAME}. {item["name"]} {stamp(region["start"])}–{stamp(region["end"])}. '
                                f'Beat timing: mixed-track BPM estimate {region["bpm_estimate"]}; '
                                f'periodicity {region["periodicity_confidence"]:.3f}; '
                                f'{len(region["beat_candidates_seconds"])} beat candidates. '
                                'This is not a confirmed musical beat or downbeat.',
                        'data': {**common_data(item, region['status']), 'rhythm': region}})
    changes = transitions(folder, scenes)
    for change in changes:
        for key in ('seconds', 'start', 'end'):
            if key in change:
                change[key] += offset
        a = change.get('seconds', change.get('start', 0))
        records.append({'start': a, 'end': change.get('end', a), 'kind': 'transition-candidate',
                        'text': f'{NAME}. {item["name"]} at {a:.2f}s. {change["kind"]}. '
                                'Measured flash or near-black interval; may be source exposure or graphics, not an intentional transition.',
                        'data': {**common_data(item, 'Unverified transition candidate'), 'transition': change}})
    write(folder / 'transition-candidates.json', changes)
    durations = np.asarray([s['duration'] for s in scenes])
    onsets = audio_metrics.get('onsets', [])
    close_onsets = sum(any(abs(b - o['seconds']) <= .15 for o in onsets) for b in boundaries)
    beats = [b for r in regions for b in r['beat_candidates_seconds']]
    close_beats = sum(any(abs(b - beat) <= .15 for beat in beats) for b in boundaries)
    stats = {'source': item['slug'], 'name': item['name'], 'seconds': item['seconds'],
             'native_frames': receipt['native_frames_measured'], 'scene_candidates': len(scenes),
             'classified_scenes': len(visual['scenes']), 'median_scene_seconds': float(np.median(durations)),
             'scene_duration_quartiles': np.percentile(durations, [25, 50, 75]).tolist(),
             'candidate_changes_per_minute': len(boundaries) / item['seconds'] * 60,
             'layout_candidate_seconds': dict(layouts), 'typography_candidate_seconds': dict(typefaces),
             'texture_candidate_seconds': dict(textures), 'movement_cue_seconds': dict(movement),
             'reviewed_chapters': len(notes.get('chapters', [])), 'transition_candidates': len(changes),
             'sound_event_candidates': len(events['events']), 'audio_available': audio.get('audio_available', True),
             'audio_measured_seconds': audio_metrics['duration'] if audio.get('audio_available', True) else 0,
             'audio_classified_seconds': audio['analysed_seconds'], 'speech_seconds': audio['speech_seconds'],
             'transcript_segments': len(read(folder / 'transcript.json')), 'onset_candidates': len(onsets),
             'rhythm_regions': len(regions), 'estimated_beats': len(beats),
             'boundaries_near_onsets_150ms': close_onsets, 'boundaries_near_estimated_beats_150ms': close_beats,
             'timing_note': 'Temporal coincidences between unverified candidates, not evidence of editorial intention.',
             'records_by_kind': dict(Counter(r['kind'] for r in records))}
    records.append({'kind': 'editing-pace',
                    'text': f'{NAME}. {item["name"]}: {len(scenes)} scene-change candidates; '
                            f'median duration {stats["median_scene_seconds"]:.2f}s; '
                            f'{stats["candidate_changes_per_minute"]:.2f} candidate changes per minute. '
                            f'{close_onsets} boundaries within 150ms of audio onset candidates; '
                            f'{close_beats} boundaries near estimated beats. Chapter looks can last much longer than a photo shot.',
                    'data': {**common_data(item, stats['timing_note']), 'statistics': stats}})
    stats['records_by_kind']['editing-pace'] = 1
    write(folder / 'editing-dna.json', stats)
    return records, stats, scenes, visual, audio


CSS = '''*{box-sizing:border-box}body{margin:0;background:#10151c;color:#ecf0f4;font:16px/1.6 system-ui}main{max-width:1220px;margin:auto;padding:36px 24px}h1{font-size:40px;line-height:1.2}a{color:#8edcda}h2{margin-top:38px}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #334050;text-align:left;vertical-align:top}.notice,article{background:#1b2430;border:1px solid #334050;border-radius:10px;padding:18px;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:14px}.grid img{width:100%;display:block}small{color:#b8c4ca}input{width:100%;padding:14px;background:#253244;color:white;border:1px solid #64748b;border-radius:8px;margin-bottom:20px}article[hidden]{display:none}nav{display:flex;gap:18px;flex-wrap:wrap}video{width:100%;max-height:600px}'''


def page(title, body, css):
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(title)}</title><link rel="stylesheet" href="{css}"><main>{body}</main></html>'


def source_report(item, stats, scenes, visual, audio):
    esc = html.escape
    folder = BASE / item['slug']
    tiles = []
    for scene, row in zip(scenes, visual['scenes']):
        labels = ' · '.join(row['candidates'][k][0]['label'] for k in ('layout', 'typography', 'texture'))
        detail = ', '.join(motion(scene))
        tiles.append(f'<article data-search="{esc((labels + " " + detail).lower())}"><a href="{esc(Path(item["path"]).as_uri())}#t={scene["start"]:.3f}"><img loading="lazy" src="{esc(scene["representative"]["file"])}"></a><b>{stamp(scene["start"])}–{stamp(scene["end"])}</b><p>{esc(labels)}</p><small>{esc(detail)}</small></article>')
    windows = ''.join(f'<tr><td><button type="button" data-start="{w["start"]}" data-end="{w["end"]}">{stamp(w["start"])}–{stamp(w["end"])}</button></td><td>{w["speech_fraction"]:.3f}</td><td>{esc(", ".join(c["label"] for c in w["candidates"]))}</td></tr>' for w in audio['windows'])
    events = read(folder / 'aligned-sound-events.json')['events']
    event_rows = ''.join(f'<tr><td><button type="button" data-start="{max(0,e["seconds"]-.5)}" data-end="{min(item["seconds"],e["seconds"]+1.2)}">{e["seconds"]:.2f}s</button></td><td>{esc(", ".join(c["label"] for c in e["candidates"]))}</td><td>{e["offset_from_scene_boundary"]}</td></tr>' for e in events)
    audio_body = f'<nav><a href="dna-report.html">Visual scenes</a><a href="../dna-report.html">All videos</a></nav><h1>{esc(item["name"])} · Audio</h1><div class="notice">Complete mixed audio measured every 20ms; local voice detection; CLAP similarity in ten-second windows and selected short onset windows. These candidates overlap and are not separated stems or confirmed sound identities.</div><h2>Voice, music, ambience</h2><table><tr><th>Time</th><th>Voice fraction</th><th>Sound candidates</th></tr>{windows}</table><h2>Impacts, risers, whooshes and other onset candidates</h2><table><tr><th>Time</th><th>Candidates</th><th>Nearest boundary offset (s)</th></tr>{event_rows}</table><p><a href="audio-analysis.json">All onsets, tempo regions and beat candidates</a> · <a href="transcript.txt">Automatic narration</a></p>'
    player = '<audio id="listen" controls preload="none" src="analysis-audio.wav"></audio><p>Select a time to listen to the same mixed-audio window analysed by the local model.</p>'
    controls = '<script>const listen=document.querySelector("#listen");let stop=null;document.querySelectorAll("[data-start]").forEach(b=>b.onclick=()=>{listen.currentTime=Number(b.dataset.start);stop=Number(b.dataset.end);listen.play();});listen.ontimeupdate=()=>{if(stop!==null&&listen.currentTime>=stop){listen.pause();stop=null;}};</script>'
    audio_body = audio_body.replace('<h2>Voice, music, ambience</h2>', player + '<h2>Voice, music, ambience</h2>') + controls
    (folder / 'dna-audio-report.html').write_text(page(item['name'] + ' · Audio', audio_body, '../dna-review.css'), encoding='utf-8')
    body = f'<nav><a href="../dna-report.html">All videos</a><a href="dna-audio-report.html">Audio review</a></nav><h1>{esc(item["name"])} · Editing DNA</h1><p>{stats["native_frames"]:,} native frames measured · {len(scenes):,} scene candidates · median shot {stats["median_scene_seconds"]:.2f}s.</p><div class="notice">The image is one native frame inside its scene. Local-model labels are candidates, not calibrated probabilities or exact fonts. Camera and parallax cues describe image motion; separate 3D layers cannot be recovered from the flattened video.</div><p><a href="editing-dna.json">Statistics</a> · <a href="aligned-scenes.json">Camera/motion measurements</a> · <a href="scene-interpretations.json">Visual candidates</a> · <a href="transition-candidates.json">Flash/fade candidates</a> · <a href="review-notes.json">Earlier reviewed chapter notes</a></p><input id="filter" placeholder="Find camera, typography, texture or scene"><div class="grid">{"".join(tiles)}</div><script>document.querySelector("#filter").oninput=e=>document.querySelectorAll("article").forEach(s=>s.hidden=!s.dataset.search.includes(e.target.value.toLowerCase()));</script>'
    (folder / 'dna-report.html').write_text(page(item['name'] + ' · Editing DNA', body, '../dna-review.css'), encoding='utf-8')


def main():
    began = time.time()
    items = read(BASE / 'inventory.json')
    for item in items:
        folder = BASE / item['slug']
        for name in ['dna-coverage.json', 'scene-interpretations.json', 'audio-interpretations.json',
                     'sound-event-candidates.json', 'transcript.json']:
            if not (folder / name).is_file():
                raise ValueError('Missing ' + item['name'] + ': ' + name)
    embedder = StyleEmbedder(ROOT)
    db = StyleDatabase(ROOT / 'library/creator-profiles/editing-dna.sqlite3')
    # Capture other-style content to prove this operation cannot silently overwrite it.
    other_before = db.db.execute('SELECT id,text,data,embedding FROM records WHERE style!=? ORDER BY id', (STYLE,)).fetchall()
    profile_path = ROOT / 'library/creator-profiles/beneath-documentary-edit.json'
    profile = read(profile_path)
    approved = [{'kind': 'approved-animation', 'text': a['name'] + '. ' + a['description'],
                 'data': {'status': 'user-approved animation setting', 'animation': a}}
                for a in profile['animation_settings']]
    db.replace_source(STYLE, 'approved-settings', add_vectors(embedder, approved))
    stats_rows = []
    try:
        for n, item in enumerate(items, 1):
            print(f'COMPILE MEMORY {n}/{len(items)}: {item["name"]}', flush=True)
            records, stats, scenes, visual, audio = compile_source(item)
            db.replace_source(STYLE, item['slug'], add_vectors(embedder, records))
            source_report(item, stats, scenes, visual, audio)
            stats_rows.append(stats)
            print(f'INDEXED {item["name"]}: {len(records)} source-linked vectors', flush=True)
        other_after = db.db.execute('SELECT id,text,data,embedding FROM records WHERE style!=? ORDER BY id', (STYLE,)).fetchall()
        if other_before != other_after:
            raise AssertionError('Another documentary style was changed')
        counts = dict(db.db.execute('SELECT kind,COUNT(*) FROM records WHERE style=? GROUP BY kind', (STYLE,)).fetchall())
        dimensions = db.db.execute('SELECT DISTINCT LENGTH(embedding)/4 FROM records WHERE style=?', (STYLE,)).fetchall()
        assert dimensions == [(384,)], dimensions
        assert db.db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        assert db.db.execute('SELECT COUNT(*) FROM records WHERE style=?', (STYLE,)).fetchone()[0] == db.db.execute('SELECT COUNT(*) FROM search_index WHERE style=?', (STYLE,)).fetchone()[0]
    finally:
        db.close()
    test_queries = ['camera travel and photo parallax', 'serif typography on paper with colour treatment',
                    'voice background music ambience whoosh impact riser beat timing', 'scorecard readable hold and editing pace']
    retrieval = []
    for query in test_queries:
        rows = search(ROOT, STYLE, query, limit=3, embedder=embedder)
        assert rows and all(r['id'].startswith(STYLE + '/') for r in rows)
        retrieval.append({'query': query, 'results': [{k: r[k] for k in ['id', 'source', 'start', 'end', 'kind', 'similarity']} for r in rows]})
    receipt = {'style': NAME, 'documentary_set': STYLE, 'source_folder': profile['source_folder'],
               'source_videos': len(items), 'source_seconds': sum(i['seconds'] for i in items),
               'native_frames_measured': sum(s['native_frames'] for s in stats_rows),
               'scene_candidates': sum(s['scene_candidates'] for s in stats_rows),
               'classified_scenes': sum(s['classified_scenes'] for s in stats_rows),
               'reviewed_chapters': sum(s['reviewed_chapters'] for s in stats_rows),
               'audio_available_sources': sum(s['audio_available'] for s in stats_rows),
               'audio_measured_seconds': sum(s['audio_measured_seconds'] for s in stats_rows),
               'audio_classified_seconds': sum(s['audio_classified_seconds'] for s in stats_rows),
               'sound_event_candidates': sum(s['sound_event_candidates'] for s in stats_rows),
               'vector_records': sum(counts.values()), 'records_by_kind': counts,
               'vector_model': embedder.model_name, 'vector_dimensions': 384,
               'database': str(ROOT / 'library/creator-profiles/editing-dna.sqlite3'),
               'cloud_model_calls': 0, 'model_weight_fine_tuning': False,
               'original_videos_modified': False, 'other_style_records_unchanged': True,
               'saved_animation_settings': len(profile['animation_settings']),
               'elapsed_build_seconds': time.time() - began, 'retrieval_checks': retrieval,
               'visual_scope': 'Every native decoded frame measured at 256x144. Sparse affine flow up to 5 Hz. CLIP uses one in-scene keyframe per candidate, supplemented by previously reviewed chapters and detail windows.',
               'audio_scope': 'Entire mixed track measured at 20ms cadence. Complete Silero VAD, ten-second CLAP windows, up to three short onset windows per 30 seconds, full onset/tempo estimates, existing full-track ASR transcripts.',
               'learning_method': 'Persistent source-linked editing measurements, reviewed notes and local semantic retrieval. No model weights were fine-tuned.',
               'limits': ['Scene, transition and sound labels are candidates; effect stems and exact sound identities are not recovered.',
                          'Font families and image-space motion are inferred, not exact font files, physical cameras or reconstructed 3D rigs.',
                          'All native frames have measurements, but not every frame has an individual semantic interpretation.',
                          'Beat grids are mixed-track periodicity estimates, not verified musical beats or downbeats.',
                          'ASR names, years, scores and player identity need independent factual verification.']}
    write(BASE / 'dna-coverage.json', receipt)
    write(BASE / 'editing-dna.json', {'coverage': receipt, 'videos': stats_rows})
    profile.update(name=NAME, analysis_status='analysis-complete', learning_method=receipt['learning_method'],
                   coverage_summary={k: receipt[k] for k in ['native_frames_measured', 'scene_candidates',
                                                          'audio_available_sources', 'audio_measured_seconds', 'vector_records']},
                   style_database=receipt['database'], report=str(BASE / 'dna-report.html'),
                   editing_dna=str(BASE / 'editing-dna.json'), dna_coverage=str(BASE / 'dna-coverage.json'),
                   retrieval_sources=[i['slug'] for i in items] + ['approved-settings'],
                   visual_analysis_scope=receipt['visual_scope'], audio_analysis_scope=receipt['audio_scope'],
                   interpretation_limits=receipt['limits'])
    sound_rule = ('Use retrieved source-linked audio windows, onset/cut offsets and rhythm regions when planning sound. '
                  'Protect narration; distinguish music, ambience and short effects. CLAP labels and beat grids are candidates, '
                  'not verified isolated stems. Do not reuse a reference sound unless the local asset library has an appropriate licensed file.')
    if sound_rule not in profile['rules']:
        profile['rules'].append(sound_rule)
    write(profile_path, profile)
    write(ROOT / 'library/creator-profiles/cricket-documentary.json', profile)
    rows = ''.join(f'<tr><td><a href="{s["source"]}/dna-report.html">{html.escape(s["name"])}</a></td><td>{stamp(s["seconds"])}</td><td>{s["native_frames"]:,}</td><td>{s["scene_candidates"]:,}</td><td>{s["median_scene_seconds"]:.2f}s</td><td><a href="{s["source"]}/dna-audio-report.html">{s["sound_event_candidates"]} short events</a></td></tr>' for s in stats_rows)
    mappings = [('Cuts / transitions', 'Native pixel and histogram changes; flash/near-black candidates'),
                ('Motion graphics', f'Local layout candidates and {receipt["reviewed_chapters"]} previously reviewed chapter contexts'),
                ('Typography', 'Local family/emphasis candidates and reviewed text treatment; exact font unknown'),
                ('Camera movement', 'Phase shift every frame; sparse affine pan, zoom and rotation'),
                ('Image animation', 'Motion samples and reviewed image entrances / masks / page and reel observations'),
                ('Overlays / textures', 'Local paper, grain, photo-background and light-leak candidates'),
                ('Zoom / parallax', 'Scale, rotation and residual image motion; depth is an inference'),
                ('Color treatment', 'Brightness, contrast, saturation, RGB and reviewed grade context'),
                ('Editing pace', 'Scene durations, chapter holds, changes per minute and source timestamps'),
                ('Voice', 'Full-track local VAD and existing automatic narration transcripts'),
                ('Background music / ambience', 'Full-track mixed-audio features and ten-second local CLAP candidates'),
                ('Sound effects / impacts / risers / whooshes', 'Distributed short onset clips ranked locally; not isolated stems'),
                ('Beat timing', 'Full onset/periodicity grids and cut-to-onset / estimated-beat offsets')]
    coverage_rows = ''.join(f'<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>' for k, v in mappings)
    body = f'<nav><a href="report.html">Earlier visual study</a><a href="motion-stories/report.html">Five approved animations</a></nav><h1>{NAME} · Editing DNA</h1><p>{len(items)} videos · {stamp(receipt["source_seconds"])} of reference footage · {receipt["native_frames_measured"]:,} native frames · {receipt["scene_candidates"]:,} scene candidates · {receipt["vector_records"]:,} local searchable records.</p><div class="notice"><b>Saved locally, available to the local editor.</b><p>{receipt["learning_method"]}</p><p>{receipt["visual_scope"]}</p><p>{receipt["audio_scope"]}</p></div><p><a href="editing-dna.json">Complete editing DNA</a> · <a href="dna-coverage.json">Coverage and retrieval checks</a> · <a href="style-memory.md">Readable memory guide</a></p><h2>What the memory contains</h2><table><tr><th>Category</th><th>Evidence saved</th></tr>{coverage_rows}</table><h2>Every source video</h2><table><tr><th>Video</th><th>Length</th><th>Frames</th><th>Scene candidates</th><th>Median scene</th><th>Audio review</th></tr>{rows}</table><h2>What remains uncertain</h2><ul>{"".join("<li>" + html.escape(x) + "</li>" for x in receipt["limits"])}</ul><p>cricAddict and the five approved vineet animations remain separate and intact. General and Gaming do not inherit these personal style defaults.</p>'
    (BASE / 'dna-report.html').write_text(page(NAME + ' · Editing DNA', body, 'dna-review.css'), encoding='utf-8')
    (BASE / 'dna-review.css').write_text(CSS, encoding='utf-8')
    original_report = BASE / 'report.html'
    if original_report.exists():
        original = original_report.read_text(encoding='utf-8')
        if 'href="dna-report.html"' not in original:
            original = original.replace('<h1>', '<nav><a href="dna-report.html">Open the complete local editing DNA →</a></nav><h1>', 1)
            original_report.write_text(original, encoding='utf-8')
    guide = [f'# {NAME} — local editing memory', '', receipt['learning_method'], '',
             f'{receipt["source_videos"]} videos, {receipt["native_frames_measured"]:,} measured native frames, '
             f'{receipt["vector_records"]:,} searchable records.', '', '## Visual analysis', '', receipt['visual_scope'],
             '', '## Audio analysis', '', receipt['audio_scope'], '', '## Memory database', '', receipt['database'],
             f'Local embedding model: {embedder.model_name}; 384-dimensional normalized vectors.',
             'The Cricket profile supplies this named style, and the local planner retrieves relevant source-linked examples.',
             'Existing reusable animations remain the executable renderer. Reference analysis does not create new rigs.',
             '', '## Saved editing rules', ''] + ['- ' + r for r in profile['rules']]
    guide += ['', '## Evidence types', ''] + [f'- {k}: {v:,}' for k, v in counts.items()]
    guide += ['', '## Limits', ''] + ['- ' + x for x in receipt['limits']]
    (BASE / 'style-memory.md').write_text('\n'.join(guide), encoding='utf-8')
    print('VINEET EDITING DNA COMPLETE: ' + str(receipt['vector_records']) + ' records', flush=True)


if __name__ == '__main__':
    main()
