"""One-click Smart Visuals: timeline -> speech -> the agent thinks (who/what, story memory) -> finds the
right Wikidata item -> real logos / photos / footage from the internet, each proven to be about it ->
the agent judges -> rendered clips -> new XML (full-screen on V2, pop-ups on V3) + review page + credits."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import uuid

from hinglish_broll.phrases import build_phrases
from hinglish_broll.pipeline import timeline_to_dict, timelines_for, transcripts_for
from hinglish_broll.placement import line_span
from hinglish_broll.planner import summarize
from hinglish_broll.stock import PexelsClient, PixabayClient, download
from hinglish_broll.timeline import parse_xmeml, timeline_words
from hinglish_broll.xml_export import build_track, export_tracks_xml
from hinglish_clean.detection import write_json

from .brain import open_brain
from .evaluator import info_for, open_evaluator
from .gather import gather
from .layout import avoid_zone, face_box, to_canvas
from .planner import judge, plan_visuals, resolve_entity
from .render import choose_offset, popup_card, popup_clip, probe_duration, still_clip, video_clip
from .report import write_credits, write_index, write_report
from .settings import load_settings, profiles_for
from .timing import full_slots, popup_slots
from .web import Entity, Media, Web
from .websearch import WebSearch

PREVIEW_LIMIT = 300.0       # seconds; longer timelines get the XML without a preview render
RENDER_TRIES = 5            # alternatives tried when a download or decode fails (web sites often refuse)


def _ext(url, kind):
    ext = Path(re.sub(r'[?#].*$', '', url)).suffix.lower()
    known = ('.png', '.jpg', '.jpeg', '.webp', '.gif') if kind == 'image' else ('.webm', '.ogv', '.mp4', '.mov', '.mpg')
    return ext if ext in known else ('.png' if kind == 'image' else '.webm')


def fetch(root, media, session, finder=None):
    """Download an image or a Wikimedia/stock video once into cache/visuals/media (shared between runs)."""
    name = hashlib.sha1(media.url.encode()).hexdigest()[:20] + _ext(media.url, media.kind)
    target = Path(root) / 'cache' / 'visuals' / 'media' / name
    if media.source == 'web':
        return (finder or WebSearch(root)).download_image(media, target)
    return download(media.url, target, session=session)


def blocked_ranges(xml_path):
    """B-roll / cutaways already above the talking head (captions and full-length layers ignored)."""
    try:
        from hinglish_zoom.xml_apply import Sequence
        return Sequence(xml_path).blocked_seconds()
    except Exception:
        return []


def open_face_locator(root, progress=print):
    try:
        from hinglish_zoom.faces import FaceLocator
        return FaceLocator(root)
    except Exception as error:
        progress(f'  Face finder unavailable ({error}); pop-ups use the default top position')
        return None


def face_zone(locator, timeline, start, end):
    """Canvas box around the speaker's face while a pop-up shows (None when no clear face)."""
    if locator is None:
        return None
    mid = (start + end) / 2
    clip = next((c for c in timeline.clips if c.start <= mid < c.end), None)
    if clip is None:
        return None
    t0 = clip.source_in + max(start, clip.start) - clip.start
    t1 = clip.source_in + min(end, clip.end) - clip.start
    try:
        from hinglish_zoom.faces import source_size
        box = face_box(locator, clip.path, t0, max(t1, t0 + .2))
        if box is None:
            return None
        zone = avoid_zone(to_canvas(box, source_size(clip.path), (timeline.width, timeline.height)),
                          (timeline.width, timeline.height))
        return [round(v, 1) for v in zone]
    except Exception:
        return None


class Rejected(Exception):
    """The evaluator looked at the file and failed it."""

    def __init__(self, verdict):
        super().__init__('; '.join(verdict.reasons))
        self.verdict = verdict


def render_slot(root, folder, timeline, slot, media, session, device, scorer=None, finder=None, evaluator=None,
                info=None):
    """Download, CHECK and render one media into this slot's clip -> (clip path, verdict or None).
    With an evaluator the pixels are checked first (the exact seconds for a video); a failed file raises
    Rejected and nothing is rendered."""
    verdict = None
    if media.kind == 'video' and media.source == 'web':    # YouTube / any site: only the useful part
        path, _ = (finder or WebSearch(root)).download_video(media, slot['end'] - slot['start'])
        media.duration = 0.0                               # the downloaded part, not the whole video
    else:
        path = fetch(root, media, session, finder)
    safe = re.sub(r'[^A-Za-z0-9]+', '-', media.id)[-36:].strip('-')
    seconds = slot['end'] - slot['start']
    size = (timeline.width, timeline.height, timeline.fps)
    if media.kind == 'video':
        duration = media.duration or probe_duration(path)
        media.offset = choose_offset(path, seconds, duration, scorer)
    if evaluator is not None:
        verdict = (evaluator.video(path, media.offset, seconds, info) if media.kind == 'video'
                   else evaluator.image(path, info))
        if verdict.passed is False:
            raise Rejected(verdict)
    if slot['display'] == 'popup':
        card, position = popup_card(path, timeline.width, timeline.height,
                                    'logo' if slot['show'] == 'logo' else 'photo',
                                    '' if slot['show'] == 'logo' else slot['label'], slot.get('avoid'))
        clip = Path(folder) / 'media' / f'popup-{slot["index"] + 1:02d}-{safe}.mov'
        card_png = Path(folder) / 'thumbs' / f'popup-{slot["index"] + 1:02d}.png'
        card_png.parent.mkdir(parents=True, exist_ok=True)
        card.save(card_png)
        if not clip.exists():
            popup_clip(card, position, seconds, *size, clip)
        return clip, verdict
    clip = Path(folder) / 'media' / f'visual-{slot["index"] + 1:02d}-{safe}.mp4'
    if not clip.exists():
        if media.kind == 'video':
            video_clip(path, media.offset, seconds, *size, clip, device)
        else:
            still_clip(path, seconds, *size, clip, device)
    return clip, verdict


def report_thumb(folder, media, session):
    """Small local preview for the review page."""
    if not media.thumb:
        return ''
    target = Path(folder) / 'thumbs' / (hashlib.sha1(media.id.encode()).hexdigest()[:16] + '.jpg')
    if not target.exists():
        try:
            from PIL import Image
            raw = download(media.thumb, target.with_suffix('.download'), session=session, timeout=30)
            with Image.open(raw) as image:
                image.seek(0)
                image = image.convert('RGBA')
                flat = Image.new('RGB', image.size, (255, 255, 255))
                flat.paste(image, mask=image.getchannel('A'))
                flat.thumbnail((320, 320))
                flat.save(target, quality=85)
            raw.unlink(missing_ok=True)
        except Exception:
            return ''
    return target.relative_to(folder).as_posix()


class ClipScorer:
    """Optional CLIP ranking: how well a picture matches what the moment should show."""

    def __init__(self, settings, root, progress):
        from hinglish_broll.vision import Vision
        self.vision = Vision(settings.vision_model, root, settings.device, settings.cpu_threads)
        self.progress = progress

    def rerank(self, moment, candidates, session, folder, limit=10):
        from PIL import Image
        text = self.vision.texts([f'a photo of {moment.visual}'])[0]
        images, owners = [], []
        for media in candidates[:limit]:
            thumb = report_thumb(folder, media, session)
            if thumb:
                with Image.open(Path(folder) / thumb) as image:
                    images.append(image.convert('RGB')); owners.append(media)
        if images:
            for media, sim in zip(owners, self.vision.images(images) @ text):
                media.score = round(media.score + 6.0 * float(sim), 3)
        return sorted(candidates, key=lambda m: -m.score)

    def scorer(self, visual):
        text = self.vision.texts([f'a photo of {visual}'])[0]
        return lambda images: list(self.vision.images(images) @ text)

    def close(self):
        self.vision.close()


def run(root, input_path, output_format=None, density=None, device=None, popups=None, brain_choice=None,
        progress=print, web=None, brain=None, scorer=None, use_web=None, finder=None, evaluator=None,
        evaluator_choice=None, script=''):
    root = Path(root).resolve()
    settings = load_settings(root, density=density, device=device, popups=popups, brain=brain_choice,
                             use_web=use_web, evaluator=evaluator_choice)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'visuals' / stamp
    output.mkdir(parents=True)
    progress('Reading the timeline')
    jobs = timelines_for(root, input_path, output, output_format, progress)
    all_sources = sorted({s for t, _ in jobs for s in t.sources()})
    progress('Understanding your speech (reusing saved transcripts when available)')
    words_by_source, notes = transcripts_for(root, all_sources, settings.device, progress)
    for note in notes: progress('  ' + note)

    web = web or Web(root, settings.language)
    if finder is None and settings.use_web:
        finder = WebSearch(root, progress)
    progress('Searching: ' + ('the whole web (images + YouTube/web videos) + ' if finder else '') +
             'Wikipedia/Wikimedia Commons' + (' + Pexels/Pixabay' if settings.pexels_key or settings.pixabay_key else ''))
    stock = []
    if settings.use_stock and settings.pexels_key: stock.append(PexelsClient(settings.pexels_key, root))
    if settings.use_stock and settings.pixabay_key: stock.append(PixabayClient(settings.pixabay_key, root))
    own_brain = brain is None
    brain = brain or open_brain(root, settings.brain, settings.think_model, settings.cpu_threads, progress)
    progress(f'Brain: {brain.name}')
    plans = []
    try:
        for timeline, folder in jobs:
            for warning in timeline.warnings: progress('  ' + warning)
            words = timeline_words(timeline, words_by_source)
            if script.strip():
                from .script import apply_script
                words, fixed = apply_script(words, script)
                if fixed:
                    progress('  Names fixed from your script: ' + ', '.join(
                        f'"{c["heard"]}" -> {c["script_spelling"]}' for c in fixed[:12]))
            phrases, lines = build_phrases(words), build_phrases(words, merge=False)
            if not phrases:
                progress(f'  No speech found in {timeline.name}; skipped')
                continue
            full_p, pop_p = profiles_for(timeline.duration, settings.density)
            progress(f'The agent is reading "{timeline.name}" ({len(phrases)} phrases)')
            summary = summarize(brain, phrases)
            progress(f'  Topic: {summary["topic"]}')
            moments, specs, stories = plan_visuals(brain, phrases, summary, full_p, timeline.orientation, progress,
                                                   script)
            if not settings.popups:
                for m in moments: m.display = 'fullscreen'
            progress(f'Looking up {len(specs)} names on Wikipedia/Wikidata')
            entities = {}
            for key in sorted({m.entity for m in moments}):
                spec = specs[key]
                try:
                    entity = resolve_entity(brain, web, spec, summary)
                except Exception as error:
                    progress(f'  {spec["name"]}: lookup failed ({error})')
                    entity = None
                if entity is None and (spec['kind'] in ('place', 'thing', 'event') or
                                       (spec['kind'] == 'brand' and finder is not None)):
                    # searched by its name; for a brand the vision check must read the name in the logo
                    entity = Entity(key, spec['name'], spec['kind'], label=spec['name'],
                                    description=spec.get('about', ''))
                if entity is None:
                    progress(f'  {spec["name"]}: not clearly identified, skipped (wrong person/brand is worse than none)')
                    continue
                entities[key] = entity
                progress(f'  {spec["name"]} = {entity.label} ({entity.description or entity.kind})'
                         + (f' [{entity.qid}]' if entity.qid else ''))
            moments = [m for m in moments if m.entity in entities]
            plans.append((timeline, folder, summary, stories, full_p, pop_p, words, phrases, lines, moments, entities))

        if scorer is None:
            try:
                progress('Loading the visual matching model')
                scorer = ClipScorer(settings, root, progress)
            except Exception as error:
                progress(f'  Visual matching unavailable ({error}); ranking by Wikipedia facts only')
                scorer = None

        results = []
        for timeline, folder, summary, stories, full_p, pop_p, words, phrases, lines, moments, entities in plans:
            by_id = {p.id: p for p in phrases}
            for n, m in enumerate(moments, 1):
                entity = entities[m.entity]
                span = line_span(m, by_id[m.phrase_id], lines) if m.phrase_id in by_id else None
                need = min(full_p.max_len, (span[1] - span[0]) if span else full_p.ideal)
                progress(f'Searching the internet {n}/{len(moments)}: {m.visual}')
                m.candidates = gather(web, m, entity, need, timeline.orientation, (timeline.width, timeline.height),
                                      stock, progress, finder)
                if m.show == 'video' and not any(c.kind == 'video' for c in m.candidates):
                    m.show = 'photo'        # no real footage exists: a full-screen photo tells it instead
                if scorer and len(m.candidates) > 1:
                    try:
                        m.candidates = scorer.rerank(m, m.candidates, web.session, folder)
                    except Exception as error:
                        progress(f'  Visual ranking skipped: {error}')
                progress(f'  {len(m.candidates)} verified files about {entity.label or entity.name}')
            usable = [m for m in moments if m.candidates]
            names = {k: e.names() for k, e in entities.items()}
            judged = {}
            while True:
                full = full_slots([m for m in usable if m.display == 'fullscreen'], phrases, lines, full_p,
                                  timeline.duration, blocked_ranges(timeline.xml_path))
                placed = {id(s.moment) for s in full}
                for m in usable:        # a full-screen idea that does not fit (e.g. in the opening seconds) pops up
                    if m.display == 'fullscreen' and id(m) not in placed:
                        m.display = 'popup'
                pops = popup_slots([m for m in usable if m.display == 'popup'], phrases, lines, words, pop_p,
                                   timeline.duration, [(s.start, s.end) for s in full], names)
                slots = sorted(full + pops, key=lambda s: s.start)
                progress(f'  {len(full)} full-screen visuals and {len(pops)} pop-ups fit the timing rules')
                empty = []
                for i, slot in enumerate(slots):
                    m = slot.moment
                    if id(m) in judged:
                        continue
                    ordered = m.candidates
                    official_pick = ordered[0].official and (m.show == 'logo' or m.display == 'popup')
                    if not official_pick:
                        progress(f'Checking the best match {i + 1}/{len(slots)}: {m.visual}')
                        try:
                            ordered = judge(brain, m, entities[m.entity], ordered)
                        except Exception as error:
                            progress(f'  Check skipped ({error}); using the best-ranked file')
                    judged[id(m)] = ordered
                    if not ordered:
                        progress(f'  None of the files really shows "{m.visual}"')
                        empty.append(m)
                if not empty:
                    break
                # a moment with no fitting file gives its time back: moments it pushed aside get their turn
                usable = [m for m in usable if m not in empty]
                progress('  Choosing the timing again without the moments that had no fitting file')
            project = {'version': 1, 'timeline': timeline_to_dict(timeline), 'summary': summary, 'stories': stories,
                       'density': settings.density, 'device': settings.device, 'brain': brain.name,
                       'entities': {k: e.to_dict() for k, e in entities.items()}, 'slots': []}
            for i, slot in enumerate(slots):
                m, entity = slot.moment, entities[slot.moment.entity]
                ordered = judged[id(m)]
                entry = {'index': i, 'start': slot.start, 'end': slot.end, 'text': slot.text, 'quote': m.quote,
                         'meaning': m.meaning, 'visual': m.visual, 'queries': m.queries, 'priority': m.priority,
                         'entity': m.entity, 'label': entity.label or entity.name, 'show': m.show,
                         'display': m.display, 'category': m.category, 'chosen': None, 'clip': None,
                         'evaluation': None, 'rejected': [],
                         'alternatives': [c.to_dict() for c in ordered[:8]]}
                project['slots'].append(entry)
            plans_render = project['slots']
            for entry in plans_render:
                for data in entry['alternatives']:
                    data['report_thumb'] = report_thumb(folder, Media(**{k: v for k, v in data.items()
                                                                         if k in Media.__dataclass_fields__}),
                                                        web.session)
            results.append((timeline, folder, project))
    finally:
        if own_brain:
            brain.close()

    summaries = []
    if evaluator is None:       # evaluator=False: switched off by the caller
        evaluator = open_evaluator(root, settings.evaluator, settings.vision_check_model,
                                   getattr(scorer, 'vision', None), progress)
    evaluator = evaluator or None
    if evaluator is not None:
        progress(f'Evaluator: {evaluator.name}. Every file must pass TYPE, IDENTITY and QUALITY before it is used')
    locator = open_face_locator(root, progress) if any(e['display'] == 'popup' for _, _, p in results
                                                       for e in p['slots']) else None
    for timeline, folder, project in results:
        for entry in project['slots']:
            if entry['display'] == 'popup':
                entry['avoid'] = face_zone(locator, timeline, entry['start'], entry['end'])
            info = info_for(entry, project['entities'].get(entry['entity']))
            for n, data in enumerate(entry['alternatives'][:RENDER_TRIES]):
                media = Media(**{k: v for k, v in data.items() if k in Media.__dataclass_fields__})
                progress(f'Preparing visual {entry["index"] + 1}/{len(project["slots"])}: {entry["label"]} '
                         f'({"pop-up" if entry["display"] == "popup" else media.kind}, {media.source})')
                try:
                    clip, verdict = render_slot(
                        root, folder, timeline, entry, media, web.session, settings.device,
                        scorer.scorer(entry['visual']) if scorer and media.kind == 'video' else None,
                        finder, evaluator, info)
                except Rejected as rejected:
                    progress(f'  Evaluator FAIL: {rejected}. Trying the next file')
                    entry['rejected'].append({'id': media.id, 'title': media.title, 'source': media.source,
                                              **rejected.verdict.to_dict()})
                    data['evaluation'] = rejected.verdict.to_dict()
                    continue
                except Exception as error:
                    progress(f'  Could not use this file ({error}); trying the next one')
                    continue
                if verdict is not None:
                    progress(f'  Evaluator {verdict.label}' + (f': saw {verdict.seen[:110]}' if verdict.seen else ''))
                    data['evaluation'] = entry['evaluation'] = verdict.to_dict()
                data['offset'] = media.offset
                entry['chosen'], entry['clip'] = data, clip.relative_to(folder).as_posix()
                break
            if not entry['clip'] and entry['rejected']:
                progress(f'  The evaluator rejected all {len(entry["rejected"])} files; you stay on screen here')
        xml = write_outputs(root, folder, project, progress)
        filled = sum(1 for s in project['slots'] if s['clip'])
        progress(f'  {filled}/{len(project["slots"])} visuals placed')
        summaries.append({'name': timeline.name, 'folder': folder.name, 'filled': filled,
                          'moments': len(project['slots']), 'xml': str(xml)})
    if scorer and hasattr(scorer, 'close'):
        scorer.close()
    if not summaries:
        raise ValueError('No speech could be understood in the supplied timeline')
    write_index(output / 'index.html', summaries, notes)
    (output / 'result.json').write_text(json.dumps({'results': summaries, 'notes': notes}, indent=2), encoding='utf-8')
    return output / (summaries[0]['folder'] + '/report.html' if len(summaries) == 1 else 'index.html')


def write_outputs(root, folder, project, progress=print, preview=True):
    timeline = parse_xmeml(project['timeline']['xml_path'])
    timeline.name = project['timeline']['name']
    placed = [s for s in project['slots'] if s.get('chosen') and s.get('clip')]
    placements = lambda display: [{'path': str(Path(folder) / s['clip']), 'start': s['start'], 'end': s['end'],
                                   'name': f"{s['label']} ({'pop-up' if display == 'popup' else 'visual'})"[:60]}
                                  for s in placed if s['display'] == display]
    tracks = []
    full, pops = placements('fullscreen'), placements('popup')
    if full: tracks.append(build_track(full, timeline.fps, timeline.width, timeline.height, 'visual'))
    if pops: tracks.append(build_track(pops, timeline.fps, timeline.width, timeline.height, 'popup'))
    xml = export_tracks_xml(timeline, tracks, Path(folder) / 'VISUALS_SEQUENCE.xml', '_VISUALS')
    preview_file = Path(folder) / 'preview.mp4'
    if preview and timeline.duration <= PREVIEW_LIMIT and placed:
        try:
            import numpy as np
            from hinglish_zoom.preview import render_preview
            from hinglish_zoom.xml_apply import Sequence
            progress('Rendering preview.mp4')
            seq = Sequence(xml)
            render_preview(seq, np.ones(seq.frames), [None] * seq.frames, preview_file, progress=progress)
        except Exception as error:
            progress(f'  Preview skipped: {error}')
    write_json(Path(folder) / 'visuals-project.json', project)
    write_report(Path(folder) / 'report.html', project, preview_file.exists())
    write_credits(Path(folder) / 'CREDITS.txt', project)
    rows = [{'index': s['index'], 'label': s['label'], 'start': s['start'], 'used': bool(s.get('clip')),
             'verdict': s.get('evaluation'), 'rejected': s.get('rejected', [])} for s in project['slots']]
    (Path(folder) / 'EVALUATION.json').write_text(json.dumps({
        'passed': sum(1 for r in rows if r['used'] and (r['verdict'] or {}).get('passed')),
        'rejected_files': sum(len(r['rejected']) for r in rows), 'results': rows},
        ensure_ascii=False, indent=1), encoding='utf-8')
    return xml


def rebuild_project(project_file, choices, progress=print):
    """choices: {slot_index: media id or ''}. '' removes the visual from that moment."""
    import requests
    from .web import USER_AGENT
    project_file = Path(project_file)
    folder, root = project_file.parent, project_file.parents[4]
    project = json.loads(project_file.read_text(encoding='utf-8'))
    timeline = parse_xmeml(project['timeline']['xml_path'])
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    for key, wanted in (choices or {}).items():
        slot = project['slots'][int(key)]
        if wanted == (slot.get('chosen') or {}).get('id', ''):
            continue
        if not wanted:
            slot['chosen'], slot['clip'] = None, None
            continue
        data = next((c for c in slot['alternatives'] if c['id'] == wanted), None)
        if data is None:
            raise ValueError('That file is not one of the suggestions for this moment')
        media = Media(**{k: v for k, v in data.items() if k in Media.__dataclass_fields__})
        clip, _ = render_slot(root, folder, timeline, slot, media, session, project.get('device', 'cpu'))
        data['offset'] = media.offset
        slot['evaluation'] = {'passed': True, 'score': 1.0, 'reasons': [], 'warnings': [], 'judge': 'chosen by you',
                              'seen': '', 'checks': {}}
        slot['chosen'], slot['clip'] = data, clip.relative_to(folder).as_posix()
    preview = Path(folder) / 'preview.mp4'
    preview.unlink(missing_ok=True)
    xml = write_outputs(root, folder, project, progress)
    return {'xml_files': [str(xml.resolve())], 'filled': sum(1 for s in project['slots'] if s.get('clip'))}
