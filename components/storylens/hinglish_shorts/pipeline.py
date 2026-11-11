"""Long to Shorts: long video -> words -> local AI hook moments (rule-checked) -> vertical MP4s + one editable
sequence per short + a review page where you change, remove or add shorts and rebuild."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
import re
import uuid

from hinglish_clean.detection import write_json
from hinglish_cut.model import Word
from hinglish_eval import guard, tune

from .find import Short, find_shorts, snap, cap_padding
from .render import caption_cues, face_position, render_short, template_overlay
from .report import write_report
from .settings import ShortsSettings
from .source import LongVideo, open_video, transcribe
from .xml import export_short_xml

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.mts', '.m2ts', '.webm'}


def _videos(path):
    path = Path(path)
    if path.is_file():
        return [path]
    return sorted((p for p in path.rglob('*') if p.suffix.lower() in VIDEO_EXTENSIONS), key=lambda p: str(p).casefold())


def slug(text, limit=48):
    return re.sub(r'[^A-Za-z0-9]+', '-', str(text)).strip('-')[:limit] or 'short'


def _locator(root, look):
    if look != 'face':
        return None
    try:
        from hinglish_zoom.faces import FaceLocator
        return FaceLocator(root)
    except Exception:
        return None


def build_short(root, folder, video, words, item, settings, locator=None, progress=print,*,reuse_captions=False,caption_words=None,source_lineage=None):
    """Render one short (MP4 + layers + XML) from its plan item; returns the item with file names."""
    n = item['index']
    if caption_words is not None:
        item={**item,'source_text':item.get('source_text',item['text']),
              'text':_text_between(caption_words,item['pieces'])}
    title = settings.title.strip() or item['title']
    pieces = cap_padding(words,[tuple(p) for p in item['pieces']],settings.max_length)
    item={**item,'pieces':[list(p) for p in pieces],'duration':round(sum(e-s for s,e in pieces),3)}
    overlay = template_overlay(title, settings.handle, settings.cta, video.width, video.height) \
        if settings.look == 'template' else None
    face_x, faced = .5, 0.0
    if settings.look == 'face':
        face_x, faced = face_position(locator, video.path, pieces) if locator else (.5, 0.0)
    cues = caption_cues(caption_words if caption_words is not None else words, pieces) if settings.captions else None
    name = f'{n:02d} - {slug(title)}'
    progress(f'Making short {n}: "{title}" ({sum(e - s for s, e in pieces):.0f}s)')
    facts = render_short(video, pieces, settings.look, folder / f'{name}.mp4', folder / 'assets', n, overlay,
                         face_x, cues, settings.caption_style, settings.device, progress,reuse_captions=reuse_captions)
    xml = export_short_xml(folder / f'SHORT_{n:02d}_{slug(title, 40)}.xml', f'{title} (short {n})', video,
                           facts['frames'], settings.look, facts['layers'], face_x)
    (folder/f'{name}.txt').write_text(item['text'],'utf-8')
    from hinglish_niche.gaming_lineage import capture_short
    lineage = capture_short(source_lineage, video.path, folder / f'{name}.mp4', facts['frames'], facts['fps'])
    return {**item, 'title': item['title'], 'shown_title': title, 'mp4': f'{name}.mp4', 'xml': xml.name,
            'thumb': facts['thumb'], 'layers': {k: Path(v).name for k, v in facts['layers'].items()},
            'frames': facts['frames'], 'fps': facts['fps'], 'face_x': round(face_x, 3), 'faced': round(faced, 2),
            'look': settings.look, 'captions': settings.captions, 'lineage':lineage}


def _project_file(folder):
    return Path(folder) / 'shorts-project.json'


def run(root, input_path, settings=None, progress=print, script=''):
    root = Path(root).resolve()
    settings = settings or ShortsSettings()
    from hinglish_cut.compute_policy import heavy_device
    settings.device=heavy_device(root,settings.device)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'shorts' / stamp
    output.mkdir(parents=True)
    videos = _videos(input_path)
    if not videos:
        raise ValueError('Choose your long video (MP4, MOV...)')
    results, notes = [], []
    for number, path in enumerate(videos, 1):
        folder = output / f'{number:03d}-{slug(path.stem, 40)}'
        folder.mkdir(parents=True)
        video = open_video(path)
        from hinglish_niche.gaming_lineage import load_highlights
        source_lineage = load_highlights(path)
        progress(f'Long video: {path.name} ({video.duration / 60:.1f} min, {video.width}x{video.height}, '
                 f'{float(video.fps):g} fps)')
        progress('Understanding your speech (saved after the first time)')
        from hinglish_niche.profiles import current_profile
        if current_profile()=='gaming':
            # Game effects/overlapping voices can produce placeholder ASR.
            # Exclude those windows, as the gaming highlights tool already does;
            # never feed invalid text to the local selector. Other edits stay strict.
            words = transcribe(root, video, settings.device, progress,skip_invalid_recognition=True)
        else:
            words = transcribe(root, video, settings.device, progress)
        if script.strip():
            from hinglish_visuals.script import apply_script
            words, fixed = apply_script(words, script)
            if fixed:
                progress('  Names fixed from your script: ' + ', '.join(
                    f'"{c["heard"]}" -> {c["script_spelling"]}' for c in fixed[:12]))
        from hinglish_publish.memory import correct_words
        words, learned_changes = correct_words(root, words, script)
        if learned_changes:
            progress(f'Applied {len(learned_changes)} approved creator spelling corrections')
        from hinglish_visuals.brain import open_brain
        brain = open_brain(root, settings.brain, 'qwen3:8b', settings.cpu_threads, progress)
        brain.context_feature = 'shorts'
        excluded=[]
        if settings.fresh:
            from .published_moments import intervals
            excluded=intervals(root,path)
            progress(f'Keeping {len(excluded)} previously published source moments out of this new selection')
        try:
            progress(f'  AI brain: {brain.name}')
            shorts, summary, lines = find_shorts(brain, words, settings, progress, script,
                                                 scale=tune.value('shorts', 'count_scale', 1.0),
                                                 source_duration=video.duration,excluded=excluded)
            from .title_review import review as review_titles
            title_review=review_titles(brain,[{'index':i+1,**s.to_dict()} for i,s in enumerate(shorts)],progress) if shorts else {}
            for i,short in enumerate(shorts,1):short.title=title_review[i]['title']
            caption_words,caption_changes=words,[]
            if shorts and settings.captions:
                from hinglish_captions.proofread import selected as review_captions
                caption_words,caption_changes=review_captions(brain,words,shorts,progress,root=root,video=video)
        finally:
            brain.close()
        guard.save(folder)
        if not shorts:
            notes.append(f'{path.name}: no moment strong enough for a short was found')
            continue
        locator = _locator(root, settings.look)
        items = []
        for n, short in enumerate(shorts, 1):
            item = {'index': n, **short.to_dict()}
            items.append(build_short(root, folder, video, words, item, settings, locator, progress,caption_words=caption_words,source_lineage=source_lineage))
        project = {'version': 1, 'video': {**asdict(video), 'fps': str(video.fps)}, 'name': path.stem,
                   'settings': asdict(settings), 'summary': summary, 'brain': brain.name,
                   'shorts': items, 'words': [[w.text, round(w.start, 3), round(w.end, 3)] for w in words]}
        # Only newly generated projects retain this immutable producer record.
        # Legacy projects are never searched/backfilled during a later rebuild.
        if source_lineage.get('state') == 'complete':
            project['gaming_source_lineage'] = source_lineage['record']
        from .title_review import VERSION as title_version
        project['title_review']={'version':title_version,'model':brain.name,'items':list(title_review.values())}
        from hinglish_captions.proofread import VERSION as caption_version
        project['caption_review']={'version':caption_version,'model':brain.name,'changes':caption_changes,'number_format':'digits'}
        project['caption_words']=[[w.text,round(w.start,3),round(w.end,3)] for w in caption_words]
        write_json(_project_file(folder), project)
        write_report(folder / 'report.html', project)
        results.append({'name': path.stem, 'folder': folder.name, 'shorts': len(items)})
        progress(f'Done: {len(items)} short(s) for {path.name}')
    (output / 'result.json').write_text(json.dumps({'results': results, 'notes': notes}, indent=2), encoding='utf-8')
    if not results:
        raise ValueError('; '.join(notes) or 'No shorts were made')
    if len(results) == 1:
        return output / results[0]['folder'] / 'report.html'
    index = output / 'index.html'
    index.write_text('<!doctype html><meta charset="utf-8"><title>Long to Shorts</title><body style="background:#0d0f12;'
                     'color:#fff;font:16px Segoe UI;max-width:800px;margin:40px auto">' + ''.join(
                         f'<p><a style="color:#ff6a2b" href="{r["folder"]}/report.html">{r["name"]}</a> · '
                         f'{r["shorts"]} shorts</p>' for r in results), encoding='utf-8')
    return index


def _load_video(data):
    from fractions import Fraction
    return LongVideo(**{**data, 'fps': Fraction(data['fps'])})


def snap_times(words, start, end):
    """A short you add by time: cut in the gaps between words (never inside a word)."""
    from hinglish_broll.phrases import Phrase
    inside = [w for w in words if w.start >= start - .25 and w.end <= end + .25]
    if not inside:
        return start, end
    return snap(words, Phrase(0, inside[0].start, inside[0].end, ''), Phrase(0, inside[-1].start, inside[-1].end, ''))


def _text_between(words, pieces):
    return ' … '.join(' '.join(w.text for w in words if s <= (w.start + w.end) / 2 < e) for s, e in pieces)


def rebuild_project(project_file, changes, progress=print):
    """Apply review-page changes: {shorts: [{index|None, keep, title, pieces: [[start, end]]}],
    look, captions, title, handle}. Only changed or new shorts are rendered again."""
    project_file = Path(project_file)
    folder = project_file.parent
    root = folder.parents[3]              # <root>/output/shorts/<run>/<video>
    project = json.loads(project_file.read_text(encoding='utf-8'))
    video = _load_video(project['video'])
    from hinglish_niche.gaming_lineage import load_highlights, unavailable
    source_lineage = (load_highlights(video.path, project['gaming_source_lineage'])
                      if 'gaming_source_lineage' in project else
                      unavailable('parent_lineage_unavailable','This saved project predates verified gaming lineage; no mapping was backfilled.'))
    words = [Word(t, s, e) for t, s, e in project['words']]
    caption_rows=changes.get('caption_words',project.get('caption_words',project['words']))
    caption_words=[Word(t,s,e) for t,s,e in caption_rows]
    settings_data = dict(project['settings'])
    for key in ('look', 'captions', 'title', 'handle', 'cta', 'caption_style'):
        if key in changes:
            settings_data[key] = changes[key]
    settings = ShortsSettings(**settings_data)
    global_change = bool(changes.get('refresh_captions')) or any(settings_data.get(k) != project['settings'].get(k)
                        for k in ('look', 'captions', 'title', 'handle', 'cta', 'caption_style'))
    old = {s['index']: s for s in project['shorts']}
    kept, rendered = [], 0
    next_index = max(old, default=0) + 1
    locator = _locator(root, settings.look)
    for change in changes.get('shorts', []):
        index = change.get('index')
        item = old.get(index) if index is not None else None
        pieces = []
        for s, e in change.get('pieces') or []:
            s, e = max(0.0, float(s)), min(video.duration, float(e))
            if e - s >= .5:
                pieces.append((s, e))
        pieces.sort()
        if item is None:
            if not pieces:
                continue
            pieces = [snap_times(words, s, e) for s, e in pieces]
            item = {'index': next_index, 'title': str(change.get('title') or '').strip() or 'My short',
                    'pieces': [list(p) for p in pieces], 'lines': [], 'why': 'Added by you', 'hook': '',
                    'score': 0, 'text': _text_between(words, pieces), 'part': 0, 'added': True}
            next_index += 1
            kept.append(build_short(root, folder, video, words, item, settings, locator, progress,caption_words=caption_words,source_lineage=source_lineage))
            rendered += 1
            continue
        if not change.get('keep', True) or not pieces:
            for key in ('mp4', 'xml'):
                if item.get(key) and (folder / item[key]).is_file():
                    (folder / item[key]).unlink()
            continue
        title = str(change.get('title') or item['title']).strip()
        moved = [list(map(lambda v: round(v, 3), p)) for p in pieces] != \
            [list(map(lambda v: round(v, 3), p)) for p in item['pieces']]
        item = {**item, 'title': title, 'pieces': [list(p) for p in pieces]}
        if moved:
            item['text'] = _text_between(words, pieces)
            item['duration'] = round(sum(e - s for s, e in pieces), 2)
        caption_change=global_change or index in changes.get('refresh_captions_indices',[])
        if moved or caption_change or title != old[index]['title']:
            kept.append(build_short(root, folder, video, words, item, settings, locator, progress,
                                    reuse_captions=not moved and not caption_change,caption_words=caption_words,source_lineage=source_lineage))
            rendered += 1
        else:
            kept.append(item)
    project['settings'] = asdict(settings)
    project['caption_words']=caption_rows
    project['shorts'] = sorted(kept, key=lambda s: s['pieces'][0][0])
    write_json(project_file, project)
    write_report(folder / 'report.html', project)
    return {'shorts': len(kept), 'rendered': rendered}
