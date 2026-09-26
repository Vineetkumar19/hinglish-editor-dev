"""One-click B-roll: timeline -> speech -> local AI plan -> footage -> conformed clips -> new XML."""
from datetime import datetime
from pathlib import Path
import json
import math
import re
import shutil
import uuid

from hinglish_cut.media import prepare_media
from hinglish_cut.model import Cut
from hinglish_cut.xml_export import export_xml
from hinglish_clean.detection import write_json
from hinglish_eval import guard

from .conform import make_clip
from .library import Library, VIDEO_EXTENSIONS, read_frames
from .llm import LocalLLM
from .phrases import build_phrases
from .placement import Moment, Slot, place
from .places import conflicts, is_template, video_country, with_country
from .planner import plan_moments, summarize
from .ranker import GENERIC_SCENES, add_specificity, choose, fetch_thumbs, moment_embedding, score_stock
from .report import write_index, write_report
from .settings import load_settings, profile_for
from .stock import Candidate, PexelsClient, PixabayClient, cached_name, download
from .timeline import Timeline, parse_xmeml, path_key, timeline_words
from .xml_export import export_broll_xml

STOCK_OFFSET = 1.0     # skip the first second of stock clips (often fades / camera settling)


def _videos(path):
    path = Path(path)
    if path.is_file(): return [path]
    return sorted((p for p in path.rglob('*') if p.suffix.lower() in VIDEO_EXTENSIONS),
                  key=lambda p: str(p).casefold())


def timelines_for(root, input_path, output, output_format, progress):
    """An XML sequence is used as-is; each video file becomes a one-clip sequence."""
    input_path = Path(input_path)
    if input_path.suffix.lower() == '.xml':
        folder = output / f'001-{re.sub(r"[^A-Za-z0-9_-]+", "-", input_path.stem)[:40]}'
        folder.mkdir(parents=True)
        return [(parse_xmeml(input_path), folder)]
    found = []
    for n, video in enumerate(_videos(input_path), 1):
        media, _ = prepare_media(video, Path(root) / 'cache' / 'conformed', progress)
        folder = output / f'{n:03d}-{re.sub(r"[^A-Za-z0-9_-]+", "-", video.stem)[:40]}'
        folder.mkdir(parents=True)
        base = folder / 'source-timeline.xml'
        export_xml(base, [Cut(media.id, 0, math.floor(media.duration * float(media.rate) + 1e-6), 0)],
                   {media.id: media}, output_format)
        timeline = parse_xmeml(base)
        timeline.name = video.stem
        found.append((timeline, folder))
    if not found:
        raise ValueError('No supported videos or XML timeline were found')
    return found


def transcripts_for(root, sources, device, progress):
    from hinglish_semantic.analysis import analyze_sources
    from hinglish_semantic.core import SemanticSettings
    data = json.loads((Path(root) / 'config.phase2.json').read_text(encoding='utf-8-sig'))
    data.update(device=device, speech_backend='swift', matching_backend='word_coverage')
    paths = [Path(p) for p in sources if Path(p).is_file()]
    missing = [str(p) for p in sources if not Path(p).is_file()]
    transcripts, _, errors = analyze_sources(paths, root, SemanticSettings(**data), progress)
    failed = {e['source'] for e in errors}
    mapping = {}
    for path, transcript in zip([p for p in paths if str(p) not in failed], transcripts):
        mapping[path_key(path)] = transcript.words
        mapping[path_key(transcript.media.path)] = transcript.words
    for e in errors:   # duplicate copies share the original's words
        same = re.search(r'same video as (.+)$', e['error'])
        if same and path_key(same.group(1)) in mapping:
            mapping[path_key(e['source'])] = mapping[path_key(same.group(1))]
    notes = [f'Media offline: {m}' for m in missing] + [f"{Path(e['source']).name}: {e['error']}" for e in errors
                                                         if 'same video as' not in e['error']]
    return mapping, notes


def gather_candidates(slot, embedding, library, clients, orientation, timeline, per_query, thumbs, progress,
                      country=''):
    need = slot.duration
    found = list(library.search(embedding, need)) if library else []
    for client in list(clients):
        for n, query in enumerate(with_country(slot.moment.queries, country)):
            try:
                results = client.search(query, orientation, timeline.width, timeline.height, per_query)
            except PermissionError as error:
                # A wrong key must not stop the run: drop that site, keep the other sources.
                progress(f'  {error} Skipping {client.name.title()} for this run.')
                clients.remove(client)
                break
            except Exception as error:
                progress(f'  {client.name.title()} search skipped: {error}')
                results = []
            # Wrong country (Seoul traffic for a Delhi story) is worse than no B-roll.
            found += [c for c in results if c.duration >= need + STOCK_OFFSET * 0.5
                      and not conflicts(f'{c.title} {c.page_url}', country)
                      and not is_template(f'{c.title} {c.page_url}')]
            if n == 0 and len(results) >= 8:   # the specific query found plenty; save API quota
                break
    unique = {}
    for c in found:
        unique.setdefault(c.id, c)
    return list(unique.values())


def render_choice(root, folder, timeline, slot_index, slot, candidate, device):
    """Download (stock) and conform one chosen candidate; returns the new clip path."""
    source = candidate.path
    offset = candidate.offset
    if candidate.source != 'library':
        target = Path(root) / 'cache' / 'broll' / 'stock' / cached_name(candidate)
        source = str(download(candidate.download_url, target))
        offset = min(STOCK_OFFSET, max(0.0, (candidate.duration - slot['end'] + slot['start']) / 2))
    safe = re.sub(r'[^A-Za-z0-9]+', '-', candidate.id)[-40:]
    clip = Path(folder) / 'media' / f'broll-{slot_index + 1:02d}-{safe}.mp4'
    if not clip.exists():
        make_clip(source, offset, slot['end'] - slot['start'], timeline.width, timeline.height,
                  timeline.fps, clip, device)
    return clip


def report_thumb(root, folder, candidate, need):
    """Local jpg for the review page (copied so the page works from its own folder)."""
    target = Path(folder) / 'thumbs' / cached_name(candidate, 'thumb')
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if candidate.source == 'library':
            frames = read_frames(candidate.path, [candidate.offset + need / 2], size=480)
            if frames: frames[0][1].convert('RGB').save(target, quality=85)
        elif candidate.thumb and Path(candidate.thumb).is_file():
            shutil.copyfile(candidate.thumb, target)
    except Exception:
        return None
    return target if target.exists() else None


def timeline_fingerprint(vision, timelines, every=1.5, limit=300):
    """CLIP embeddings of frames from the timelines' own footage (to spot raw takes in the library)."""
    clips = [clip for timeline in timelines for clip in timeline.clips]
    total = sum(max(0.0, c.source_out - c.source_in) for c in clips) or 1.0
    step = max(every, total / limit)          # one frame every 1.5 s, at most ~300 frames per run
    images = []
    for clip in clips:
        span = max(0.0, clip.source_out - clip.source_in)
        count = max(1, round(span / step))
        times = [clip.source_in + span * (k + .5) / count for k in range(count)]
        try:
            images += [im for _, im in read_frames(clip.path, times)]
        except Exception:
            continue
    return vision.images(images) if images else None


def timeline_to_dict(t):
    return {'name': t.name, 'fps': f'{t.fps.numerator}/{t.fps.denominator}', 'width': t.width, 'height': t.height,
            'duration': t.duration, 'xml_path': t.xml_path}


def write_outputs(root, folder, project):
    timeline = parse_xmeml(project['timeline']['xml_path'])
    timeline.name = project['timeline']['name']
    placements = [{'path': str(Path(folder) / s['clip']), 'start': s['start'], 'end': s['end'],
                   'name': s['chosen']['title'][:60] if s.get('chosen') else 'B-roll'}
                  for s in project['slots'] if s.get('chosen') and s.get('clip')]
    xml = export_broll_xml(timeline, placements, Path(folder) / 'BROLL_SEQUENCE.xml')
    write_json(Path(folder) / 'broll-project.json', project)
    write_report(Path(folder) / 'report.html', project)
    return xml


def run(root, input_path, output_format=None, density=None, device=None, progress=print):
    root = Path(root).resolve()
    settings = load_settings(root, density=density, device=device)
    sources = settings.sources()
    if not sources:
        raise ValueError('Add a Pexels/Pixabay API key or a footage folder in B-roll settings first')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'broll' / stamp
    output.mkdir(parents=True)
    progress('Reading the timeline')
    jobs = timelines_for(root, input_path, output, output_format, progress)
    all_sources = sorted({s for t, _ in jobs for s in t.sources()})
    progress('Understanding your speech (reusing saved transcripts when available)')
    words_by_source, notes = transcripts_for(root, all_sources, settings.device, progress)
    for note in notes: progress('  ' + note)

    plans = []
    llm = LocalLLM(root, threads=settings.cpu_threads)
    try:
        for timeline, folder in jobs:
            for warning in timeline.warnings: progress('  ' + warning)
            words = timeline_words(timeline, words_by_source)
            phrases = build_phrases(words)
            if not phrases:
                progress(f'  No speech found in {timeline.name}; skipped')
                continue
            profile = profile_for(timeline.duration, settings.density)
            progress(f'Local AI is reading "{timeline.name}" ({len(phrases)} phrases, {profile.name}-form rules)')
            summary = summarize(llm, phrases)
            progress(f'  Topic: {summary["topic"]}')
            moments = plan_moments(llm, phrases, summary, profile, timeline.orientation, progress)
            # Exact spoken lines: each B-roll plays only while its own line is being said.
            slots = place(moments, phrases, profile, timeline.duration, build_phrases(words, merge=False))
            progress(f'  {len(slots)} B-roll moments chosen')
            plans.append((timeline, folder, summary, profile, slots))
            guard.save(folder)   # the model checks for this timeline (quality report)
    finally:
        llm.close()
    if not plans:
        raise ValueError('No speech could be understood in the supplied timeline')

    from .vision import Vision
    progress('Loading the visual matching model')
    vision = Vision(settings.vision_model, root, settings.device, settings.cpu_threads)
    library = None
    if 'library' in sources:
        progress('Checking your footage library')
        library = Library(root, settings.library_folders, vision, exclude=all_sources, progress=progress).build()
        removed = library.exclude_lookalikes(timeline_fingerprint(vision, [t for t, _ in jobs]))
        if removed:
            progress(f'  Skipped {removed} of your clips that are takes of this same video')
        progress(f'  {len(library.entries)} of your clips are searchable')
    clients = []
    if 'pexels' in sources: clients.append(PexelsClient(settings.pexels_key, root))
    if 'pixabay' in sources: clients.append(PixabayClient(settings.pixabay_key, root))
    thumbs = root / 'cache' / 'broll' / 'thumbs'

    results = []
    generic = vision.texts([f'a photo of {scene}' for scene in GENERIC_SCENES])
    for timeline, folder, summary, profile, slots in plans:
        pairs, embeddings = [], []
        country = video_country(summary)
        if country:
            progress(f'  Video is set in {country.title()}: searching local footage, rejecting other countries')
        for n, slot in enumerate(slots, 1):
            progress(f'Finding footage {n}/{len(slots)}: {slot.moment.visual}')
            embedding = moment_embedding(vision, slot, summary.get('visual_world', ''))
            candidates = gather_candidates(slot, embedding, library, clients, timeline.orientation, timeline,
                                           settings.results_per_query, thumbs, progress, country)
            fetch_thumbs(candidates, thumbs)
            score_stock(vision, embedding, candidates)
            pairs.append((slot, candidates)); embeddings.append(embedding)
        add_specificity(pairs, embeddings, generic)
        picks = choose(pairs, timeline.orientation, settings.min_similarity)
        project = {'version': 1, 'timeline': timeline_to_dict(timeline), 'summary': summary,
                   'profile': profile.name, 'density': settings.density, 'device': settings.device, 'slots': []}
        for i, (slot, _) in enumerate(pairs):
            chosen, others = picks[i]
            entry = {'index': i, 'start': slot.start, 'end': slot.end, 'text': slot.text,
                     'meaning': slot.moment.meaning, 'visual': slot.moment.visual, 'queries': slot.moment.queries,
                     'priority': slot.moment.priority, 'chosen': None, 'clip': None, 'alternatives': []}
            for c in ([chosen] if chosen else []) + others:
                thumb = report_thumb(root, folder, c, slot.duration)
                data = c.to_dict()
                data['report_thumb'] = thumb.relative_to(folder).as_posix() if thumb else ''
                entry['alternatives'].append(data)
            if chosen:
                progress(f'Preparing B-roll {i + 1}/{len(pairs)} ({chosen.source})')
                try:
                    clip = render_choice(root, folder, timeline, i, entry, chosen, settings.device)
                    entry['chosen'] = entry['alternatives'][0]
                    entry['clip'] = clip.relative_to(folder).as_posix()
                except Exception as error:
                    progress(f'  Could not prepare this clip: {error}')
            project['slots'].append(entry)
        filled = sum(1 for s in project['slots'] if s['clip'])
        xml = write_outputs(root, folder, project)
        progress(f'  {filled}/{len(project["slots"])} moments received B-roll')
        results.append({'name': timeline.name, 'folder': folder.name, 'filled': filled,
                        'moments': len(project['slots']), 'xml': str(xml)})
    vision.close()
    write_index(output / 'index.html', results, notes)
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    return output / (results[0]['folder'] + '/report.html' if len(results) == 1 else 'index.html')


def rebuild_project(project_file, choices, progress=print):
    """choices: {slot_index: candidate_id or ''}. '' removes B-roll from that moment."""
    project_file = Path(project_file)
    folder, root = project_file.parent, project_file.parents[4]
    project = json.loads(project_file.read_text(encoding='utf-8'))
    timeline = parse_xmeml(project['timeline']['xml_path'])
    for key, wanted in (choices or {}).items():
        slot = project['slots'][int(key)]
        current = (slot.get('chosen') or {}).get('id', '')
        if wanted == current:
            continue
        if not wanted:
            slot['chosen'], slot['clip'] = None, None
            continue
        data = next((c for c in slot['alternatives'] if c['id'] == wanted), None)
        if data is None:
            raise ValueError('That clip is not one of the suggestions for this moment')
        candidate = Candidate(**{k: v for k, v in data.items() if k in Candidate.__dataclass_fields__})
        clip = render_choice(root, folder, timeline, slot['index'], slot, candidate, project.get('device', 'cpu'))
        slot['chosen'], slot['clip'] = data, clip.relative_to(folder).as_posix()
    xml = write_outputs(root, folder, project)
    return {'xml_files': [str(xml.resolve())], 'filled': sum(1 for s in project['slots'] if s.get('clip'))}
