"""The Motion Graphics run. Script (or your video's speech) -> the local AI plans the scenes and names the assets each
one is built from (rule-checked) -> the assets are found (web / Wikipedia / Pexels / Pixabay / AI Images on your GPU),
checked by the vision model and cut out on this PC -> every scene is rendered in your style: full-screen scenes (MP4)
on V2 and scenes over your video (transparent MOV) on V3 of a copy of your timeline, plus MOTION_GRAPHICS.mp4 (the
whole script told in motion graphics, with your voice)."""
from dataclasses import asdict
from datetime import datetime
from fractions import Fraction
from hinglish_cut.compute_policy import h264_profile,ffmpeg_h264
from hinglish_cut.compute_policy import heavy_device
from pathlib import Path
import json
import re
import uuid

import numpy as np

from hinglish_clean.detection import write_json
from hinglish_eval import guard

from .plan import TEMPLATES, plan_scenes
from .report import write_report
from .settings import SIZES, MotionSettings
from .style import choices, look
from hinglish_niche.documentary import apply_style_settings

OVERLAY_OK = {'big_number', 'stamp', 'object_drop', 'photo_card', 'headline'}   # work over your video
from .creative import TEMPLATES as CREATIVE_TEMPLATES
OVERLAY_OK.update(CREATIVE_TEMPLATES)
CUT_TEMPLATES = {'cutout_hero', 'spotlight', 'object_drop', 'silhouette', 'collage', 'versus_assets', 'asset_hero', 'product_card'}
MIN_SCENE, MAX_SCENE = 3.0, 5.0
PROJECT = 'motion-project.json'
STANDALONE = 'MOTION_GRAPHICS.mp4'
SEQUENCE = 'MOTION_GRAPHICS_SEQUENCE.xml'


def _clock(seconds):
    m, s = divmod(int(max(0, seconds)), 60)
    return f'{m}:{s:02d}'


def scene_mode(template, wanted, setting, has_video):
    """Full screen, or over your video. With no video there is nothing to put it on."""
    if not has_video:
        return 'full'
    mode = wanted if setting == 'auto' else setting
    if mode not in ('full', 'overlay'):
        mode = TEMPLATES.get(template, ('', [], (0, 0), (), 'full'))[4]
    return mode if mode == 'full' or template in OVERLAY_OK else 'full'


def set_durations(scenes, lines, total, full=False):
    """Key moments: a scene stays for its line (+ a beat), 3-5 s. Full video: each scene runs until the next one
    starts (the first from 0 s), so the whole video is graphics. Never past the end."""
    by_id = {l.id: l for l in lines}
    live = sorted((s for s in scenes if not s.get('removed')), key=lambda s: s['start'])
    for n, s in enumerate(live):
        if full:
            if n == 0:
                s['start'] = 0.0
            nxt = live[n + 1]['start'] if n + 1 < len(live) else total
            s['duration'] = round(max(.5, nxt - s['start']), 3)
            continue
        line = by_id.get(s['line'])
        said = (line.end - line.start) if line else MIN_SCENE
        seconds = min(MAX_SCENE, max(MIN_SCENE, said + 1.0))
        entries = s.get('data', {}).get('player_entries', [])
        if entries:
            seconds = max(seconds, max(e['seconds'] for e in entries) - s['start'] + 1.0)
        if n + 1 < len(live):
            seconds = min(seconds, live[n + 1]['start'] - s['start'] - .1)
        s['duration'] = round(max(1.0, min(seconds, total - s['start'])), 2)


def timeline_audio(timeline, total):
    """The sequence's sound as one stereo 48 kHz track (each clip's source audio at its place)."""
    from hinglish_shorts.render import RATE, piece_audio
    buffer = np.zeros((2, round(total * RATE)), np.float32)
    ms = Fraction(1000)
    for clip in sorted(timeline.clips, key=lambda c: (c.track, c.start)):
        if not Path(clip.path).is_file():
            continue
        try:
            part = piece_audio(clip.path, [(round(clip.source_in * 1000), round((clip.end - clip.start) * 1000))], ms)
        except Exception:
            continue                                          # a clip without sound
        at = round(clip.start * RATE)
        size = min(part.shape[1], buffer.shape[1] - at)
        if size > 0:
            buffer[:, at:at + size] = part[:, :size]
    return buffer


# ---- assets ------------------------------------------------------------------------------------------------------
def fallback(s):
    """A scene whose pictures could not be found becomes the closest scene that still works (never an empty frame)."""
    s.setdefault('planned', {'template': s['template'], 'data': dict(s['data'])})   # to try again later
    lo, hi = TEMPLATES[s['template']][2]
    found = [a for a in s['assets'] if a.get('file')]
    historical = [a for a in s.get('assets_all', []) if str(a.get('error', '')).startswith('Historical player image needs review')]
    if historical:
        raise ValueError(historical[0]['error'] + ' Add the verified archival image to library/cricket-assets; generic portraits are not substituted.')
    if len(found) >= lo:
        s['assets'] = found
        if s['template'] == 'collage':
            items = s['data'].get('items') or []
            s['data']['items'] = [items[i] for i, a in enumerate(s['assets_all']) if a.get('file') and i < len(items)]
        return s
    words = s['data'].get('word') or s['data'].get('title') or s['data'].get('left_label') or s['data'].get('label') or ''
    if found and s['template'] in ('collage', 'versus_assets'):
        s['template'] = 'cutout_hero' if found[0].get('cutout') else 'photo_card'
        s['data'].setdefault('word', words.split(' ')[0][:12] if words else '')
        s['data'].setdefault('label', words[:34])
        s['assets'] = found[:1]
        return s
    s['template'] = 'headline'           # short: the title only, never the whole sentence
    s['data']['lines'] = [x for x in (s['data'].get('title') or words, s['data'].get('title2')) if x][:2]
    s['data'].pop('subtitle', None)
    s['assets'] = []
    return s


def extract_frames(video, target_dir, seconds, fps, max_side=1100):
    """A clip as JPEG frames at the scene's frame rate (the scene page shows the right one for every frame)."""
    import av
    from PIL import Image
    target_dir.mkdir(parents=True, exist_ok=True)
    need = max(1, round(seconds * float(fps)))
    files = []
    with av.open(str(video)) as c:
        stream = c.streams.video[0]
        k, last = 0, None
        for frame in c.decode(stream):
            if frame.time is None:
                continue
            while k < need and frame.time >= k / float(fps):
                image = frame.to_image()
                image.thumbnail((max_side, max_side), Image.LANCZOS)
                path = target_dir / f'{k:04d}.jpg'
                image.save(path, quality=88)
                files.append(path)
                k += 1
            last = frame
            if k >= need:
                break
    while files and len(files) < need:                         # a short clip holds its last picture
        files.append(files[-1])
    return files


def find_assets(root, folder, project, scenes, settings, progress):
    from .assets import Asset, AssetFinder
    todo = [s for s in scenes if s.get('assets')]
    if not todo:
        return
    connected_assets = any(s['template'] in CREATIVE_TEMPLATES for s in todo)
    finder = AssetFinder(root, progress, use_ai={'all': 'auto', 'web': False, 'ai': 'auto'}[settings.assets],
                         check=settings.check, require_vision=connected_assets and settings.check,
                         prefer_web=connected_assets and settings.assets != 'ai')
    progress(f'Finding the pictures for {len(todo)} scene(s): {finder.describe()}')
    orientation = 'portrait' if project['height'] > project['width'] else 'landscape'
    try:
        for s in todo:
            wanted = [a if isinstance(a, Asset) else Asset(**{k: v for k, v in a.items() if k in Asset.__dataclass_fields__})
                      for a in s['assets']]
            for i, a in enumerate(wanted):
                if a.file:
                    continue
                label = a.name or a.query
                progress(f'  Scene {s["index"]} ({s["template"]}): {a.kind} "{label[:50]}"')
                finder.find(a, folder, f'{s["index"]:02d}-{i}-{uuid.uuid4().hex[:4]}', s['template'] in CUT_TEMPLATES,
                            max(3.0, s.get('duration') or 5), orientation, (project['width'], project['height']))
            s['assets'] = wanted
        finder.make_ai(progress)
    finally:
        finder.close()
    for s in todo:
        s['assets_all'] = [a.to_dict() for a in s['assets']]
        s['assets'] = [dict(a) for a in s['assets_all']]
        for a in s['assets_all']:
            if a.get('error') or not a.get('file'):
                progress(f'  Scene {s["index"]}: no picture for "{a.get("name") or a.get("query")}"' +
                         (f' ({a["error"]})' if a.get('error') else ''))
        before = s['template']
        if s['template'] == 'asset_hero' and (not s['assets'] or any(not a.get('file') for a in s['assets'])):
            raise RuntimeError('Motion assets unavailable: one or more requested pictures did not pass the checks. Try a clearer subject or another source.')
        fallback(s)
        if s['template'] != before:
            progress(f'  Scene {s["index"]}: {before} -> {s["template"]} (with the pictures that were found)')


def asset_payload(folder, s, fps):
    """The scene's assets as files the scene page can load (clips as frames)."""
    out = []
    for i, a in enumerate(s.get('assets') or []):
        if not a.get('file'):
            continue
        path = folder / a['file']
        item = {'src': path.as_uri(), 'cut': bool(a.get('cutout'))}
        entry = next((e for e in s.get('data', {}).get('player_entries', []) if e['name'] == a.get('name')), None)
        if entry is not None:
            item['enter_at'] = max(0.0, entry['seconds'] - s['start'])
        if path.suffix.lower() in ('.mp4', '.mov', '.webm'):
            frames_dir = folder / 'assets' / f'{path.stem}-frames-{s["index"]:02d}'
            frames = sorted(frames_dir.glob('*.jpg'))
            need = max(1, round(s['duration'] * float(fps)))
            if len(frames) < need:
                frames = extract_frames(path, frames_dir, s['duration'], fps)
            item.update(frames=[f.as_uri() for f in frames[:need]], fps=float(fps), src=frames[0].as_uri() if frames else '')
        out.append(item)
    return out


def _scene_payload(folder, s, project):
    data = dict(s['data'])
    data['assets'] = asset_payload(folder, s, Fraction(project['fps']))
    return {'template': s['template'], 'mode': s['mode'], 'duration': s['duration'], 'data': data,
            'theme': project['theme'], 'speed': project['speed'], 'quality': project.get('settings', {}).get('quality', 'full'),
            'continuity_audit':project.get('creator_profile')=='cricket' and bool(s.get('assets') or s.get('assets_all'))}


# ---- rendering ---------------------------------------------------------------------------------------------------
def render_scenes(renderer, folder, project, only=None, progress=print):
    """Each scene as its own file (for your timeline), its layout check and a still for the review page."""
    (folder / 'scenes').mkdir(exist_ok=True)
    (folder / 'stills').mkdir(exist_ok=True)
    fps = Fraction(project['fps'])
    live = [s for s in project['scenes'] if not s.get('removed') and (only is None or s['index'] in only)]
    for n, s in enumerate(live, 1):
        payload = _scene_payload(folder, s, project)
        s['layout'] = renderer.check(payload)
        s['sound_events'] = renderer.sound_events() if hasattr(renderer,'sound_events') else renderer.page.evaluate('() => window.mgSoundEvents ? window.mgSoundEvents() : []')
        if s['template'] in CREATIVE_TEMPLATES and s['layout']:
            raise ValueError('Creative motion layout needs adjustment: shorten the scene text or use fewer steps. ' + '; '.join(s['layout']))
        suffix = '.mov' if s['mode'] == 'overlay' else '.mp4'
        name = f'{s["index"]:02d}-{s["template"]}-{uuid.uuid4().hex[:4]}'
        # Versioned media stays available if a later render/rebuild fails.
        progress(f'  Scene {n}/{len(live)}: {s["template"]} at {_clock(s["start"])}' +
                 (f' (layout: {"; ".join(s["layout"])[:100]})' if s['layout'] else ''))
        renderer.render(payload, folder / 'scenes' / f'{name}{suffix}', fps)
        audit=folder/'scenes'/f'{name}.motion'/'review.json'
        if audit.exists():
            s['motion_continuity']=json.loads(audit.read_text(encoding='utf8'))
            s['layout'].extend(s['motion_continuity']['warnings'])
        still = f'stills/{name}.{"png" if s["mode"] == "overlay" else "jpg"}'
        renderer.still(payload, max(.5, min(s['duration'] - .3, 3.5)), folder / still)
        s['file'], s['still'] = f'scenes/{name}{suffix}', still


def standalone_segments(scenes, total, fps):
    """The whole video: every scene from its start to the next one (full screen), frames adding up exactly."""
    fps = float(fps)
    end_frame = max(1, round(total * fps))
    live = sorted((s for s in scenes if not s.get('removed')), key=lambda s: s['start'])
    marks = [max(0, round(s['start'] * fps)) for s in live]
    if marks:
        marks[0] = 0
    return [(s, (marks[n + 1] if n + 1 < len(marks) else end_frame) - marks[n]) for n, s in enumerate(live)
            if (marks[n + 1] if n + 1 < len(marks) else end_frame) > marks[n]]


def render_standalone(renderer, folder, project, audio, progress=print):
    """MOTION_GRAPHICS.mp4: the scene files are simply joined (they were rendered full length) with your voice."""
    import av
    from hinglish_shorts.render import RATE, _Video
    fps = Fraction(project['fps'])
    segments = standalone_segments(project['scenes'], project['seconds'], fps)
    frames = sum(f for _, f in segments)
    progress(f'Joining {STANDALONE}: {len(segments)} scenes, {_clock(frames / float(fps))}')
    writer = _Video(folder / STANDALONE, project['width'], project['height'], fps, h264_profile(getattr(renderer,'device','cpu'))[0], audio=audio is not None)
    try:
        for s, count in segments:
            written = 0
            if s['mode'] == 'full' and s.get('file') and (folder / s['file']).is_file():
                with av.open(str(folder / s['file'])) as c:
                    for frame in c.decode(video=0):
                        if written >= count:
                            break
                        writer.write(frame.to_ndarray(format='rgb24'))
                        written += 1
            if written < count:                               # an overlay scene is rendered full screen here
                payload = {**_scene_payload(folder, s, project), 'mode': 'full', 'duration': count / float(fps)}
                renderer.load(payload)
                for n in range(written, count):
                    writer.write(renderer.frame(n / float(fps)))
        if audio is not None:
            need = round(frames / float(fps) * RATE)
            samples = np.zeros((2, need), np.float32)
            samples[:, :min(need, audio.shape[1])] = audio[:, :need]
            writer.write_audio(samples)
        writer.finish()
    except BaseException:
        writer.abort()
        raise
    project['standalone_file'] = STANDALONE


def export_timeline(folder, project, progress=print):
    from hinglish_broll.timeline import parse_xmeml
    from hinglish_broll.xml_export import build_track, export_tracks_xml
    info = project['timeline']
    timeline = parse_xmeml(info['xml'])
    timeline.name = info['name']
    tracks = []
    for mode, prefix in (('full', 'motion'), ('overlay', 'motion-over')):
        placements = [{'path': str(folder / s['file']), 'start': s['start'], 'end': s['start'] + s['duration'],
                       'name': f'Motion {s["index"]} {s["template"]}'}
                      for s in project['scenes'] if not s.get('removed') and s.get('file') and s['mode'] == mode]
        if placements:
            tracks.append(build_track(placements, timeline.fps, timeline.width, timeline.height, prefix))
    if not tracks:
        project['xml'] = ''
        return
    xml = export_tracks_xml(timeline, tracks, folder / SEQUENCE, '_MOTION')
    project['xml'] = xml.name
    live = [s for s in project['scenes'] if not s.get('removed')]
    full = sum(1 for s in live if s['mode'] == 'full')
    progress(f'  Timeline: {full} full-screen scene(s) on V2, {len(live) - full} over your video above -> {xml.name}')


def finish(folder, project, renderer, audio=None, progress=print):
    if project.get('timeline'):
        export_timeline(folder, project, progress)
    if project.get('full'):
        render_standalone(renderer, folder, project, audio, progress)
        if not project.get('timeline'):
            # Keep each finished scene independently movable in Premiere and CapCut.
            from hinglish_cut.model import Media, Cut
            from hinglish_cut.xml_export import export_xml
            fps = Fraction(project['fps'])
            segments = standalone_segments(project['scenes'], project['seconds'], fps)
            media, cuts = {}, []
            for i, (scene, frames) in enumerate(segments, 1):
                key = str(i)
                media[key] = Media(key, str((folder / scene['file']).resolve()), frames / float(fps),
                                   str(fps), project['width'], project['height'], 0, 48000)
                cuts.append(Cut(key, 0, frames, i - 1))
            export_xml(folder / SEQUENCE, cuts, media)
            project['xml'] = SEQUENCE
    else:
        project.pop('standalone_file', None)
    write_json(folder / PROJECT, project)
    write_report(folder / 'report.html', project)


def run(root, input_path=None, script='', settings=None, progress=print):
    from hinglish_aigen.plan import script_lines, speech_lines
    from .render import SceneRenderer
    root = Path(root).resolve()
    settings = settings or MotionSettings()
    from .engines import validate_style
    validate_style(settings.engine,settings.style)
    if settings.engine!='hyperframes' and settings.mode=='overlay':
        raise ValueError('Motion engine format unavailable: choose All full screen for Remotion / Motion Canvas, or Hyperframes for transparent overlays.')
    if settings.style=='theme:elements':
        if input_path:raise ValueError('Element motion plan invalid: use the supplied script without a source video.')
        from .element_motion import run as element_run
        return element_run(root,script,settings,progress)
    theme, speed, style_name = look(root, settings.style)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'motion' / stamp
    output.mkdir(parents=True)
    jobs = []
    if input_path:
        from hinglish_broll.pipeline import timelines_for, transcripts_for
        from hinglish_broll.timeline import timeline_words
        for timeline, folder in timelines_for(root, input_path, output, None, progress):
            words, notes = transcripts_for(root, timeline.sources(), 'cpu', progress)
            for note in notes:
                progress(f'  {note}')
            words = timeline_words(timeline, words)
            if script.strip():
                from hinglish_visuals.script import apply_script
                words, _ = apply_script(words, script)
            jobs.append((folder, speech_lines(words), timeline, words))
    else:
        if not script.strip():
            raise ValueError('Paste your script (or choose a video)')
        folder = output / '001-script'
        folder.mkdir()
        jobs.append((folder, script_lines(script), None, []))
    pages = []
    for folder, lines, timeline, spoken_words in jobs:
        if not lines:
            progress('  No speech was found here')
            continue
        if timeline is not None:
            width, height, fps, total = timeline.width, timeline.height, timeline.fps, timeline.duration
        else:
            width, height = SIZES['16:9' if settings.aspect == 'auto' else settings.aspect]
            fps, total = Fraction(settings.fps), lines[-1].end + .6
        if settings.quality == 'preview':
            ratio = min(1.0, 360 / min(width, height))
            width, height = max(2, round(width * ratio / 2) * 2), max(2, round(height * ratio / 2) * 2)
        full = settings.full(total, timeline is not None)
        progress('Making ' + ('a full motion-graphics video (every line)' if full else 'motion graphics for the key moments'))
        from hinglish_visuals.brain import open_brain
        brain = open_brain(root, settings.brain, settings.brain_model, settings.cpu_threads, progress)
        try:
            progress(f'  AI brain: {brain.name}')
            planned = plan_scenes(brain, lines, settings, progress, full=full)
        finally:
            if getattr(brain, 'last_creative_plan', None):
                write_json(folder / 'creative-plan.json', brain.last_creative_plan)
            brain.close()
        guard.save(folder)
        scenes = []
        archive_counts = {}
        for p in planned:
            s = p.to_dict()
            if s['template'] == 'archive_board':
                archive_look = s['data'].get('archive_style', 'slate')
                s['data']['archive_variant'] = archive_counts.get(archive_look, 0) % 2
                archive_counts[archive_look] = archive_counts.get(archive_look, 0) + 1
                apply_style_settings(root, settings.style, s)
            s['mode'] = scene_mode(s['template'], s['mode'], settings.mode, timeline is not None)
            if settings.engine!='hyperframes':s['mode']='full'
            scenes.append(s)
        if spoken_words:
            from hinglish_niche.historical import anchor_player_scenes
            anchor_player_scenes(scenes, lines, spoken_words, move_scene=not full)
        set_durations(scenes, lines, total, full)
        project = {'version': 2, 'tool': 'Motion Graphics', 'settings': asdict(settings), 'style': settings.style,
                   'style_name': style_name, 'theme': theme, 'speed': speed, 'width': width, 'height': height,
                   'fps': str(fps), 'seconds': round(total, 3), 'scenes': scenes, 'full': full,
                   'lines': [{'id': l.id, 'start': l.start, 'end': l.end, 'text': l.text} for l in lines],
                   'timeline': ({'xml': timeline.xml_path, 'name': timeline.name} if timeline else None),
                   'style_choices': choices(root)}
        from .creative import STYLES as creative_styles, receipt, planning_guidance
        if settings.style in creative_styles:
            project['creative_tools'] = receipt(settings.style)
        project['creative_guidance'] = planning_guidance('motion', script)
        from .capabilities import connections
        project['connected_tools'] = connections(root)
        from hinglish_niche.profiles import current_profile
        if current_profile() != 'general':
            project['creator_profile'] = current_profile()
        find_assets(root, folder, project, scenes, settings, progress)
        progress(f'Rendering {len(scenes)} scene(s) in "{style_name}" at {width}x{height}')
        renderer = SceneRenderer(width, height, engine=settings.engine,device=heavy_device(root))
        try:
            progress(f'  Renderer: {renderer.name}')
            render_scenes(renderer, folder, project, progress=progress)
            audio = timeline_audio(timeline, total) if timeline is not None and full else None
            finish(folder, project, renderer, audio, progress)
        finally:
            renderer.close()
        pages.append(folder / 'report.html')
        pictured = sum(1 for s in scenes if s.get('assets'))
        bad = sum(1 for s in scenes if s.get('layout'))
        progress(f'Done: {len(scenes)} scene(s), {pictured} built from pictures' +
                 (f', {bad} with a layout warning (see the review page)' if bad else ''))
    if not pages:
        raise ValueError('No speech or script text was found')
    return pages[0]


def rebuild_project(project_file, changes, progress=print):
    """Review page: {scenes: {index: {template?, mode?, removed?, data?: {field: text}, find?: [new search words per
    asset]}}, style?}. Only the changed scenes are rendered again (all of them when the style changes); then the
    timeline, the full video and the page are redone."""
    from .assets import Asset, AssetFinder
    from .render import SceneRenderer
    project_file = Path(project_file)
    folder = project_file.parent
    root = folder.parents[3]                      # <root>/output/motion/<run>/<job>
    project = json.loads(project_file.read_text(encoding='utf-8'))
    settings = MotionSettings(**{k: v for k, v in project['settings'].items() if k in MotionSettings.__dataclass_fields__})
    by_index = {s['index']: s for s in project['scenes']}
    redo = set()
    if changes.get('style') and changes['style'] != project['style']:
        project['theme'], project['speed'], project['style_name'] = look(root, changes['style'])
        project['style'] = changes['style']
        settings.style = changes['style']
        project['settings']['style'] = changes['style']
        from .creative import apply_style as apply_creative_style, STYLES as creative_styles, receipt
        if changes['style'] in creative_styles:
            project['creative_tools'] = receipt(changes['style'])
        for scene in project['scenes']:
            apply_style_settings(root, changes['style'], scene)
            apply_creative_style(scene, changes['style'])
        redo = set(by_index)
    project['style_choices'] = choices(root)
    has_video = project.get('timeline') is not None
    refind = []
    for index, change in (changes.get('scenes') or {}).items():
        s = by_index.get(int(index))
        if s is None or not isinstance(change, dict):
            continue
        before = json.dumps([s['template'], s['mode'], s['data']], sort_keys=True)
        if change.get('template') in TEMPLATES:
            s['template'] = change['template']
        if change.get('mode') in ('full', 'overlay'):
            s['mode'] = scene_mode(s['template'], change['mode'], 'auto', has_video)
        if isinstance(change.get('data'), dict):
            for key, value in change['data'].items():
                if isinstance(value, str):
                    s['data'][key] = ' '.join(value.split())[:160]
                elif isinstance(value, list):
                    s['data'][key] = value[:6]
            if s['template'] in ('headline', 'end_card'):
                s['data']['lines'] = [x for x in (s['data'].get('title'), s['data'].get('title2')) if x]
        if isinstance(change.get('find'), list):
            for i, words in enumerate(change['find'][:4]):
                words = ' '.join(str(words or '').split())[:80]
                if not words:
                    continue
                while len(s.setdefault('assets_all', [])) <= i:
                    s['assets_all'].append(Asset('object', words).to_dict())
                old = s['assets_all'][i]
                s['assets_all'][i] = Asset(old.get('kind', 'object'), words, old.get('name', ''), historical=old.get('historical', {})).to_dict()
                refind.append(s)
                redo.add(s['index'])
        if change.get('retry') and any(not a.get('file') for a in s.get('assets_all') or []):
            refind.append(s)                          # search again for the pictures that were not found
            redo.add(s['index'])
        if 'removed' in change:
            s['removed'] = bool(change['removed'])
        if json.dumps([s['template'], s['mode'], s['data']], sort_keys=True) != before or \
                (not s.get('removed') and not s.get('file')):
            redo.add(s['index'])
    if refind:
        finder = AssetFinder(root, progress, use_ai={'all': 'auto', 'web': False, 'ai': 'auto'}[settings.assets],
                             check=settings.check)
        orientation = 'portrait' if project['height'] > project['width'] else 'landscape'
        try:
            for s in {id(s): s for s in refind}.values():
                found = []
                for i, a in enumerate(s['assets_all']):
                    asset = Asset(**{k: v for k, v in a.items() if k in Asset.__dataclass_fields__})
                    if not asset.file:
                        progress(f'  Scene {s["index"]}: finding "{asset.query}"')
                        finder.find(asset, folder, f'{s["index"]:02d}-{i}-{uuid.uuid4().hex[:4]}',
                                    s['template'] in CUT_TEMPLATES, s['duration'], orientation,
                                    (project['width'], project['height']))
                    found.append(asset)
                s['_found'] = found
            finder.make_ai(progress)
        finally:
            finder.close()
        for s in {id(s): s for s in refind}.values():
            s['assets_all'] = [a.to_dict() for a in s.pop('_found')]
            s['assets'] = [dict(a) for a in s['assets_all']]
            if s.get('planned'):                      # the scene it was meant to be, now that pictures may exist
                s['template'], s['data'] = s['planned']['template'], dict(s['planned']['data'])
            fallback(s)
    from hinglish_broll.phrases import Phrase
    lines = [Phrase(l['id'], l['start'], l['end'], l['text']) for l in project['lines']]
    lengths = {s['index']: (s['start'], s['duration']) for s in project['scenes']}
    set_durations(project['scenes'], lines, project['seconds'], project.get('full', False))
    # a full video: scenes stretch to meet their neighbours, so a removed scene changes the one before it
    redo |= {s['index'] for s in project['scenes'] if (s['start'], s['duration']) != lengths[s['index']]}
    renderer = SceneRenderer(project['width'], project['height'], engine=settings.engine,device=heavy_device(root))
    try:
        live = {s['index'] for s in project['scenes'] if not s.get('removed')}
        if redo & live:
            progress(f'Rendering {len(redo & live)} scene(s)')
            render_scenes(renderer, folder, project, redo & live, progress)
        audio = None
        if project.get('full') and project.get('timeline'):
            from hinglish_broll.timeline import parse_xmeml
            audio = timeline_audio(parse_xmeml(project['timeline']['xml']), project['seconds'])
        finish(folder, project, renderer, audio, progress)
    finally:
        renderer.close()
    return {'scenes': len(project['scenes']), 'rendered': len(redo & live),
            'shown': sum(1 for s in project['scenes'] if not s.get('removed'))}
