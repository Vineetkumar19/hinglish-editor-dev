"""Smart Zoom: timeline -> speech -> local AI emphasis -> face-aware eased zooms -> new XML + preview."""
from dataclasses import asdict, replace
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
from .events import build_events, jump_cut_baseline, schedule
from .faces import FaceLocator, source_size
from .planner import plan_zooms
from .report import write_report
from .settings import ZoomSettings, profile_for
from .shots import sequence_shots
from .xml_apply import Sequence, apply_curve, camera_centres

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


def anchors_for(events, anchors_by_event, frames, fps, field='anchor'):
    per_frame = [None] * frames
    for e, anchor in zip(events, anchors_by_event):
        segments = anchor if isinstance(anchor,list) else [dict(start=e.start,end=e.end,**{field:anchor})]
        for part in segments:
            a,b=max(e.start,part['start']),min(e.end,part['end'])
            # Hard cuts lie on frame boundaries. Rounding avoids assigning the
            # next shot's anchor to the last frame before the cut.
            for f in range(max(0,round(a*float(fps))),min(frames,round(b*float(fps)))):
                per_frame[f] = part[field]
    return per_frame


def verified_shot_segments(event, shot_anchors):
    """A continuous cycle is usable only when ALL its shots have safe framing."""
    parts=[]
    for a,b,anchor,kind in shot_anchors:
        start,end=max(event.start,a),min(event.end,b)
        if end-start <= .001:
            continue
        if anchor is None:
            return None
        parts.append(dict(start=start,end=end,anchor=anchor,kind=kind))
    covered=sum(p['end']-p['start'] for p in parts)
    return parts if covered >= event.end-event.start-.002 else None


def subject_anchor(seq, subject, event, shots, sizes):
    fps = float(seq.fps)
    clip = next((c for c in seq.clips if c.zoomable and c.start/fps <= event.word < c.end/fps), None)
    shot = next(((a,b) for a,b in shots if a <= event.word < b), None)
    if clip is None or shot is None:
        return None
    offset = clip.source_seconds(seq.fps)[0] - clip.start/fps
    point = subject.head_during(clip.path, max(shot[0],clip.start/fps)+offset,
                               min(shot[1],clip.end/fps)+offset)
    if point is None:
        return None
    if clip.path not in sizes:
        sizes[clip.path] = source_size(clip.path)
    sw,sh = sizes[clip.path]
    return ((point[0]-.5)*sw,(point[1]-.5)*sh,sw,sh)


def run(root, input_path, output_format=None, settings=None, progress=print):
    root = Path(root).resolve()
    settings = settings or ZoomSettings()
    from hinglish_cut.compute_policy import heavy_device
    settings.device=heavy_device(root,settings.device)
    saved=None
    source_video=None
    if settings.sounds or settings.overlays:
        from .provenance import load
        saved=load(root,input_path)
        if saved:
            from hinglish_broll.pipeline import _videos
            candidates=_videos(input_path)
            if len(candidates)==1 and candidates[0].suffix.lower()!='.xml':source_video=candidates[0]
            progress('Reusing the approved zoom timing and fixed focal points; adding effects only')
            input_path=saved['timeline']
            settings=replace(settings,**{key:saved['settings'][key] for key in
                ('style','strength','frequency','face','jump_cuts')})
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'zoom' / stamp
    output.mkdir(parents=True)
    progress('Reading the timeline')
    jobs = timelines_for(root, input_path, output, output_format, progress)
    sources = sorted({s for t, _ in jobs for s in t.sources()})
    if not saved:progress('Understanding your speech (reusing saved transcripts when available)')
    words_by_source, notes = transcripts_for(root, sources, settings.device, progress) if not saved else ({},[])

    plans = []
    llm = LocalLLM(root, threads=settings.cpu_threads)
    try:
        for timeline, folder in jobs:
            words = timeline_words(timeline, words_by_source) if not saved else []
            phrases = build_phrases(words)
            if not phrases and not saved:
                progress(f'  No speech found in {timeline.name}; skipped'); continue
            profile = profile_for(timeline.duration, settings.frequency)
            progress('Using the approved camera plan without changing its zooms' if saved else
                     f'Local AI is finding the key moments in "{timeline.name}" ({profile.name}-form pacing)')
            summary = summarize(llm, phrases) if not saved else {}  # no second camera planning pass on follow-ups
            if not saved:progress(f'  Topic: {summary.get("topic", "")}')
            if saved:
                from .settings import ZoomProfile
                profile=ZoomProfile(**saved['profile'])
                moments=[]
            elif profile.pacing == 'cuts':
                progress('  Short video: alternate one smooth move at each cut and hold until the next cut')
                moments = []
            else:
                moments = plan_zooms(llm, phrases, profile, timeline.orientation, progress, summary, words)
            plans.append((timeline, folder, words, phrases, profile, moments))
            guard.save(folder)   # the model checks for this timeline (quality report)
    finally:
        llm.close()
    if not plans:
        raise ValueError('No speech could be understood in the supplied timeline')

    locator = FaceLocator(root) if settings.face and not saved else None
    results = []
    for timeline, folder, words, phrases, profile, moments in plans:
        seq = Sequence(timeline.xml_path)
        blocked = seq.blocked_seconds(include_popups=False)   # pop-up cards do not hide the face
        progress('  Finding shot changes')
        shots = saved['shots'] if saved else sequence_shots(seq, root / 'cache' / 'zoom' / 'shots')
        if saved:
            from .curve import ZoomEvent
            events=[ZoomEvent(**e) for e in saved['events']]
        elif profile.pacing == 'cuts':
            from .cut_pacing import cut_events
            events = cut_events(shots, settings, profile, float(seq.fps), words)
        else:
            events = build_events(moments, phrases, words, settings, profile, seq.frames / float(seq.fps), blocked, shots,
                                  select=False)
        fitted_events = list(events)
        anchors_by_event, anchor_kinds, sizes = [], [], {}
        if locator:
            # Verify one anchor per actual shot, including shots crossed during
            # a plateau or ramp. Looking only at the stressed word left later
            # shots with the previous person's position or truncated the hold.
            shot_anchors=[]
            probes=[]
            for a,b in shots:
                if not any(e.start < b and e.end > a for e in events):
                    continue
                probe=replace(events[0],start=a,word=(a+b)/2,hold_end=b,end=b)
                anchor=event_anchor(seq,locator,probe,sizes)
                probes.append(probe)
                shot_anchors.append((a,b,anchor,'face' if anchor is not None else None))
            if any(anchor is None for a,b,anchor,kind in shot_anchors):
                subject = None
                try:
                    from .subjects import SubjectLocator
                    progress('  Local vision is checking speaker positions where the face turns away')
                    subject = SubjectLocator(root)
                    for i,(a,b,anchor,kind) in enumerate(shot_anchors):
                        if anchor is not None:
                            continue
                        anchor = subject_anchor(seq,subject,probes[i],shots,sizes)
                        if anchor is not None:
                            shot_anchors[i]=(a,b,anchor,'speaker')
                except Exception as error:
                    write_json(folder / 'speaker-check-error.json', {'technical_details': str(error)})
                    progress('  Local vision could not verify the speaker. Those shots stay unchanged; the timing check will flag any missing zooms.')
                finally:
                    if subject is not None: subject.close()
            kept=[]
            for e in events:
                parts=verified_shot_segments(e,shot_anchors)
                if parts:
                    kept.append(e); anchors_by_event.append(parts)
                    anchor_kinds.append('speaker' if any(p['kind']=='speaker' for p in parts) else 'face')
            if len(kept) < len(events):
                progress(f'  Skipped {len(events) - len(kept)} candidate zooms because a crossed shot had no verified speaker')
            events = kept
        elif saved:
            anchors_by_event=saved.get('anchor_segments') or [None]*len(events)
            anchor_kinds=[saved['anchor_kinds'][min(seq.frames-1,round(e.word*float(seq.fps)))] for e in events]
        else:
            anchors_by_event = [None] * len(events)
            anchor_kinds = ['centre'] * len(events)
        candidates = list(zip(events, anchors_by_event, anchor_kinds))
        if profile.pacing != 'cuts' and not saved:
            events = schedule(events, profile, seq.frames / float(seq.fps), blocked)
        anchors_by_event = [next(anchor for candidate, anchor, kind in candidates if candidate is e) for e in events]
        anchor_kinds = [next(kind for candidate, anchor, kind in candidates if candidate is e) for e in events]
        write_json(folder / 'zoom-candidates.json', {
            'moments': [asdict(m) for m in moments], 'fitted': [asdict(e) for e in fitted_events],
            'verified_candidates': [asdict(e) for e, _, _ in candidates],
            'selected': [dict(asdict(e),anchor_kind=kind) for e,kind in zip(events,anchor_kinds)]})
        progress(f'  {len(events)} zooms placed in {len(shots)} shots'
                 + (f' ({len(blocked)} B-roll moments left alone)' if blocked else ''))
        baseline = (jump_cut_baseline([(c.start, c.end) for c in seq.clips if c.zoomable], seq.frames,
                                      float(seq.fps), settings.level) if settings.jump_cuts and profile.pacing != 'cuts' else None)
        curve = quantize(saved['curve'] if saved else build_curve(events, seq.frames, seq.fps, baseline))
        anchors = saved['anchors'] if saved else anchors_for(events, anchors_by_event, seq.frames, seq.fps)
        frame_kinds = saved['anchor_kinds'] if saved else (anchors_for(events, anchors_by_event, seq.frames, seq.fps,field='kind') if locator
                       else anchors_for(events, anchor_kinds, seq.frames, seq.fps))
        skipped = [c for c in seq.clips if not c.zoomable]
        clip_notes = list(notes) + [f'{len(skipped)} clip(s) left unzoomed ({skipped[0].reason})'] if skipped else list(notes)
        if 'speaker' in anchor_kinds:
            clip_notes.append('Local vision verified the visible speaker in turned-away shots; these anchors are not frontal face detections.')
        xml = folder / 'ZOOMED_SEQUENCE.xml'
        pieces = apply_curve(seq, curve, anchors, xml)
        from .effects import apply as apply_effects
        locked_overlays=(saved.get('effects',{}).get('overlays') or None) if saved and settings.sounds and settings.overlays else None
        audio,layers,effects=apply_effects(root,folder,xml,seq,events,settings,progress,shots=shots,
                                         locked_overlays=locked_overlays,previous_effects=saved.get('effects') if saved else None,
                                         source_video=source_video)
        preview = None
        if seq.frames / float(seq.fps) <= PREVIEW_LIMIT:
            progress('Rendering a preview')
            from .preview import render_preview
            render_preview(Sequence(timeline.xml_path), curve, anchors, folder / 'preview.mp4', progress=progress,
                           audio=audio,extra_layers=layers,device=settings.device)
            preview = 'preview.mp4'
        write_report(folder / 'report.html', timeline.name, events, settings, seq.width, seq.height, preview, clip_notes, effects=effects)
        write_json(folder / 'zoom-plan.json', {
            'settings': asdict(settings), 'profile': asdict(profile), 'pacing': profile.pacing, 'framing':'fixed_focal',
            'camera_centres': camera_centres(seq,curve,anchors), 'timeline': timeline.xml_path,
            'fps': float(seq.fps),
            'events': [asdict(e) for e in events], 'zoomed_pieces': pieces, 'shots': shots,
            'anchor_segments': anchors_by_event if locator or saved else [], 'effects':effects,
            'curve': [round(float(z), 4) for z in curve], 'anchors': [list(a) if a else None for a in anchors],
            'anchor_kinds': frame_kinds})
        guard.save(folder)
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
