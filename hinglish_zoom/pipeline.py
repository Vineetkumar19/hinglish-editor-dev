"""Smart Zoom: timeline -> speech -> local AI emphasis -> face-aware eased zooms -> new XML + preview."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
import uuid

from hinglish_broll.llm import LocalLLM
from hinglish_broll.phrases import build_phrases
from hinglish_broll.planner import summarize
from hinglish_broll.pipeline import timelines_for, transcripts_for
from hinglish_broll.timeline import timeline_words
from hinglish_clean.detection import write_json
from hinglish_eval import guard

from .curve import build_curve, quantize
from .events import build_events, jump_cut_baseline
from .faces import FaceLocator, source_size
from .planner import plan_zooms
from .report import write_report
from .settings import ZoomSettings, profile_for
from .shots import sequence_shots
from .xml_apply import Sequence, apply_curve

PREVIEW_LIMIT = 300.0   # seconds; longer timelines skip the preview render


def event_anchor(seq, locator, event, sizes):
    """The speaker's face during this zoom, as (dx, dy, source_w, source_h), or None if not clear.

    Measured at the zoom's own time (not once per video): the face moves between shots."""
    fps = float(seq.fps)
    clip = next((c for c in seq.clips if c.zoomable and c.start / fps <= event.word < c.end / fps), None)
    if clip is None:
        return None
    src_in = clip.source_seconds(seq.fps)[0]
    t0 = src_in + max(event.start, clip.start / fps) - clip.start / fps
    t1 = src_in + min(event.end, clip.end / fps) - clip.start / fps
    face = locator.face_during(clip.path, t0, max(t1, t0 + .2))
    if face is None:
        return None
    if clip.path not in sizes:
        sizes[clip.path] = source_size(clip.path)
    sw, sh = sizes[clip.path]
    return ((face[0] - .5) * sw, (face[1] - .5) * sh, sw, sh)


def anchors_for(events, anchors_by_event, frames, fps):
    per_frame = [None] * frames
    for e, anchor in zip(events, anchors_by_event):
        for f in range(max(0, int(e.start * float(fps))), min(frames, int(-(-e.end * float(fps) // 1)))):
            per_frame[f] = anchor
    return per_frame


def run(root, input_path, output_format=None, settings=None, progress=print):
    root = Path(root).resolve()
    settings = settings or ZoomSettings()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'zoom' / stamp
    output.mkdir(parents=True)
    progress('Reading the timeline')
    jobs = timelines_for(root, input_path, output, output_format, progress)
    sources = sorted({s for t, _ in jobs for s in t.sources()})
    progress('Understanding your speech (reusing saved transcripts when available)')
    words_by_source, notes = transcripts_for(root, sources, settings.device, progress)

    plans = []
    llm = LocalLLM(root, threads=settings.cpu_threads)
    try:
        for timeline, folder in jobs:
            words = timeline_words(timeline, words_by_source)
            phrases = build_phrases(words)
            if not phrases:
                progress(f'  No speech found in {timeline.name}; skipped'); continue
            profile = profile_for(timeline.duration, settings.frequency)
            progress(f'Local AI is finding the key moments in "{timeline.name}" ({profile.name}-form pacing)')
            summary = summarize(llm, phrases)          # whole-video context for every decision
            progress(f'  Topic: {summary.get("topic", "")}')
            moments = plan_zooms(llm, phrases, profile, timeline.orientation, progress, summary)
            plans.append((timeline, folder, words, phrases, profile, moments))
            guard.save(folder)   # the model checks for this timeline (quality report)
    finally:
        llm.close()
    if not plans:
        raise ValueError('No speech could be understood in the supplied timeline')

    locator = FaceLocator(root) if settings.face else None
    results = []
    for timeline, folder, words, phrases, profile, moments in plans:
        seq = Sequence(timeline.xml_path)
        blocked = seq.blocked_seconds()
        progress('  Finding shot changes')
        shots = sequence_shots(seq, root / 'cache' / 'zoom' / 'shots')
        events = build_events(moments, phrases, words, settings, profile, seq.frames / float(seq.fps), blocked, shots)
        anchors_by_event, sizes = [], {}
        if locator:
            kept = []
            for e in events:
                anchor = event_anchor(seq, locator, e, sizes)
                if anchor is not None:          # no clear face -> no zoom (never zoom into a random area)
                    kept.append(e); anchors_by_event.append(anchor)
            if len(kept) < len(events):
                progress(f'  Skipped {len(events) - len(kept)} zoom(s) where no clear face was on screen')
            events = kept
        else:
            anchors_by_event = [None] * len(events)
        progress(f'  {len(events)} zooms placed in {len(shots)} shots'
                 + (f' ({len(blocked)} B-roll moments left alone)' if blocked else ''))
        baseline = (jump_cut_baseline([(c.start, c.end) for c in seq.clips if c.zoomable], seq.frames,
                                      float(seq.fps), settings.level) if settings.jump_cuts else None)
        curve = quantize(build_curve(events, seq.frames, seq.fps, baseline))
        anchors = anchors_for(events, anchors_by_event, seq.frames, seq.fps)
        skipped = [c for c in seq.clips if not c.zoomable]
        clip_notes = list(notes) + [f'{len(skipped)} clip(s) left unzoomed ({skipped[0].reason})'] if skipped else list(notes)
        xml = folder / 'ZOOMED_SEQUENCE.xml'
        pieces = apply_curve(seq, curve, anchors, xml)
        preview = None
        if seq.frames / float(seq.fps) <= PREVIEW_LIMIT:
            progress('Rendering a preview')
            from .preview import render_preview
            render_preview(Sequence(timeline.xml_path), curve, anchors, folder / 'preview.mp4', progress=progress)
            preview = 'preview.mp4'
        write_report(folder / 'report.html', timeline.name, events, settings, seq.width, seq.height, preview, clip_notes)
        write_json(folder / 'zoom-plan.json', {
            'settings': asdict(settings), 'profile': asdict(profile), 'timeline': timeline.xml_path,
            'events': [asdict(e) for e in events], 'zoomed_pieces': pieces, 'shots': shots,
            'curve': [round(float(z), 4) for z in curve], 'anchors': [list(a) if a else None for a in anchors]})
        results.append({'name': timeline.name, 'folder': folder.name, 'zooms': len(events), 'xml': str(xml)})
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    if len(results) == 1:
        return output / results[0]['folder'] / 'report.html'
    index = output / 'index.html'
    index.write_text('<!doctype html><meta charset="utf-8"><title>Smart Zoom</title><body style="background:#0d0f12;'
                     'color:#fff;font:16px Segoe UI;max-width:800px;margin:40px auto">' + ''.join(
                         f'<p><a style="color:#ff6a2b" href="{r["folder"]}/report.html">{r["name"]}</a> · {r["zooms"]} zooms</p>'
                         for r in results), encoding='utf-8')
    return index
