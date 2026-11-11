"""Match Cut Finder workbench jobs, verified group publication and review."""

from bisect import bisect_left
from collections import Counter
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile

import av
import cv2

from hinglish_app.workbench_jobs import atomic_json
from hinglish_cut.compute_policy import heavy_device
from hinglish_cut.gpu_lock import gpu_lock
from .curation import Store, digest
from .match_cut_analysis import CALIBRATION, MIN_SCORE, WEIGHTS, analyze, check_stop, find_matches, near_duplicate, span
from .match_cut_media import FPS, _extract, _join, extract_marked, insert_group, supporting_frames
from .planner import VIDEO_EXTENSIONS, _content_fingerprint


RENDER_PROFILE = 'source-display-size-30fps-h264-aac-v2'
MAX_BATCH_BYTES = 20 * 1024 ** 3
FREE_BYTES_RESERVE = 2 * 1024 ** 3
COUNT_NAMES = ('', '', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
               'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen',
               'Eighteen', 'Nineteen', 'Twenty')


def settings(value):
    if value.get('operation') == 'create_manual_pair':
        marks = value.get('marks')
        if not isinstance(marks, list) or len(marks) != 2 or any(
            not isinstance(mark, dict)
            or not isinstance(mark.get('asset'), str)
            or not re.fullmatch(r'[a-f0-9]{24}', mark['asset'])
            or type(mark.get('frame')) is not int
            or mark['frame'] < 0
            for mark in marks
        ):
            raise ValueError('Mark one outgoing frame and one incoming frame in Best Clips.')
        return None
    if value.get('operation') == 'render_group':
        if not all(isinstance(value.get(key), str) and re.fullmatch(r'[a-f0-9]{24}', value[key])
                   for key in ('project', 'group')) or type(value.get('revision')) is not int:
            raise ValueError('Choose a saved match and reload its current revision.')
        if not isinstance(value.get('trims'), list):
            raise ValueError('Enter an in and out time for each clip.')
        return None
    paths, folders = value.get('paths', []), value.get('folders', [])
    if (not isinstance(paths, list) or not isinstance(folders, list)
            or any(not isinstance(p, str) or not p.strip() for p in paths + folders)
            or not (paths or folders)):
        raise ValueError('Choose at least one footage folder or video.')
    maximum, limit = value.get('max_clips', 4), value.get('groups_per_count', 5)
    if type(maximum) is not int or not 2 <= maximum <= 24:
        raise ValueError('Choose a maximum sequence length between 2 and 24 clips.')
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Choose between 1 and 20 sequences per clip count.')
    return paths, folders, maximum, limit


def _project(root, id):
    if not isinstance(id, str) or not re.fullmatch(r'[a-f0-9]{24}', id):
        raise ValueError('Choose a saved Match Cut Finder project.')
    base = (root / 'output/match-cut').resolve()
    project = (base / id).resolve()
    if project.parent != base:
        raise ValueError('The saved project folder is unavailable.')
    return project


def _read(path, default=None):
    try:
        return json.loads(path.read_text('utf-8'))
    except FileNotFoundError:
        if default is None:
            raise ValueError('The saved Match Cut Finder result is unavailable.') from None
        return default


def _index(project):
    return project / 'Match Cut Finder' / 'index.json'


@contextmanager
def _write_lock(project):
    project.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(project / '.write.sqlite3', timeout=0)
    try:
        try:
            db.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as error:
            raise ValueError('Wait for this match project to finish updating, then retry.') from error
        yield
    finally:
        db.close()


def snapshot(root, id):
    return _read(_index(_project(root, id)))


def _input_files(paths, folders, stop):
    collected = {Path(p).resolve() for p in paths}
    failures = []

    def inaccessible(error):
        failures.append({'source': str(error.filename), 'status': 'failed', 'details': str(error)})

    for folder in dict.fromkeys(Path(p).resolve() for p in folders):
        if not folder.is_dir():
            failures.append({'source': str(folder), 'status': 'failed', 'details': 'Folder unavailable'})
            continue
        for directory, children, names in os.walk(folder, onerror=inaccessible):
            check_stop(stop)
            if {'Best Clip', 'Match Cut Finder'} <= set(children):
                children[:] = [child for child in children if child not in {'Best Clip', 'Match Cut Finder'}]
            children[:] = [child for child in children if not child.startswith('.match-cut-')]
            collected.update((Path(directory) / name).resolve() for name in names
                             if Path(name).suffix.lower() in VIDEO_EXTENSIONS)
    return sorted(collected, key=lambda path: (str(path).casefold(), str(path))), failures


def _stat(path):
    value = Path(path).stat()
    return value.st_size, value.st_mtime_ns, value.st_ino


def scan_collection(root, paths, folders, stop, progress):
    files, outcomes = _input_files(paths, folders, stop)
    cache = root / 'cache/match-cut'
    db = Store(cache / 'ledger.sqlite3')
    sources, checked, candidates, best = {}, {}, [], []
    for n, path in enumerate(files, 1):
        check_stop(stop)
        progress(f'Scanning video {n} of {len(files)}', 2 + round(43 * (n - 1) / len(files)))
        outcome = {'source': str(path)}
        outcomes.append(outcome)
        try:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                raise ValueError('Missing or unsupported video.')
            identity = _stat(path)
            fingerprint = _content_fingerprint(path, stop)
            outcome['sha256'] = fingerprint
            if fingerprint in sources:
                outcome.update(status='duplicate', same_as=sources[fingerprint]['path'])
                continue
            record, reused = analyze(path, fingerprint, cache, db, stop)
            if _stat(path) != identity:
                raise ValueError('Source changed while scanning. Select it again when editing is finished.')
            checked[str(path)] = identity
            sources[fingerprint] = {**record['source'], 'path': str(path), 'sha256': fingerprint}
            rows = [{**row, 'source': str(path), 'source_id': fingerprint,
                     'best_clip_candidate_id': hashlib.sha256((fingerprint + ':' + str(row['start'])).encode()).hexdigest()[:20]}
                    for row in record['rows']]
            eligible = [row for row in rows if row['entries'] and row['exits']]
            if rows:
                best.append(max(rows, key=lambda row: row['score']))
            candidates.extend(eligible)
            outcome.update(status='scanned' if rows else 'no_usable_clip', usable_clips=len(rows),
                           match_candidates=len(eligible), sampled_frames=record['sample_count'], cache_hit=reused)
        except (OSError, ValueError, av.error.FFmpegError, cv2.error) as error:
            check_stop(stop)
            outcome.update(status='failed', details=str(error))
    return candidates, best, sources, outcomes, checked


def _chains(graph, clips, maximum, limit, stop):
    def rank(item):
        ids, cuts = item
        scores = [cut['score'] for cut in cuts]
        return -(.7 * sum(scores) / len(scores) + .3 * min(scores)), ids

    repeated = {}
    def repeats(i, j):
        key = min(i, j), max(i, j)
        if key not in repeated:
            repeated[key] = near_duplicate(clips[i], clips[j])
        return repeated[key]

    frontier = [((i, j), (cut,)) for i, edges in enumerate(graph) for j, cut in edges]
    for count in range(2, maximum + 1):
        check_stop(stop)
        if not frontier:
            break
        frontier.sort(key=rank)
        selected, seen, appearances = [], set(), Counter()
        for item in frontier:
            identity = frozenset(item[0])
            sources = {clips[index]['source_id'] for index in item[0]}
            if identity in seen or any(appearances[source] >= max(2, math.ceil(limit / 2)) for source in sources):
                continue
            if any(all(any(i == j or repeats(i, j) for j in previous) for i in item[0])
                   for _, previous, _ in selected):
                continue
            selected.append((-rank(item)[0], *item))
            seen.add(identity)
            appearances.update(sources)
            if len(selected) == limit:
                break
        yield count, selected
        endings, next_frontier = Counter(), []
        for ids, cuts in frontier:
            last = ids[-1]
            if endings[last] >= 8:
                continue
            endings[last] += 1
            used_sources = {clips[index]['source_id'] for index in ids}
            next_frontier.extend((ids + (j,), cuts + (cut,)) for j, cut in graph[last]
                                 if clips[j]['source_id'] not in used_sources and not any(repeats(i, j) for i in ids[:-1]))
        frontier = next_frontier


def _clip_label(row):
    name = re.sub(r'[^A-Za-z0-9_-]+', '-', Path(row['source']).stem).strip('-')[:45] or 'clip'
    return name, 'src' + row['source_id'][:8]


def _public_span(row):
    result = {k: row[k] for k in ('source', 'source_id', 'source_sha256', 'in_tick', 'out_tick',
                                 'time_base', 'start', 'duration', 'seek', 'score')}
    result['id'] = digest([row['source_sha256'], row['in_tick'], row['out_tick'], row['time_base']])[:24]
    if row.get('best_clip_candidate_id'):
        result['best_clip_candidate_id'] = row['best_clip_candidate_id']
    if 'shot_start' in row:
        result['shot_id'] = digest([row['source_sha256'], row['shot_start'], row['shot_end']])[:24]
    elif row.get('shot_id'):
        result['shot_id'] = row['shot_id']
    return result


def _artifact(project, path, actual, stop, **details):
    relative = path.relative_to(project).as_posix()
    return digest(relative)[:24], {'path': relative, 'sha256': _content_fingerprint(actual, stop), **details}


def _artifacts_ok(project, rows, stop):
    try:
        return all(_content_fingerprint(project / row['path'], stop) == row['sha256'] for row in rows.values())
    except OSError:
        return False


class Renderer:
    def __init__(self, project, work, device, checked, stop):
        self.project, self.work, self.device, self.checked, self.stop = project, work, device, checked, stop
        self.cache = {}
        self.bytes = 0

    def room(self, incoming=0):
        if self.bytes + incoming > MAX_BATCH_BYTES or shutil.disk_usage(self.project).free < FREE_BYTES_RESERVE + incoming:
            raise OSError('Export limit reached. Free disk space or lower the number of match groups, then retry.')
        self.bytes += incoming

    def extract(self, row, path):
        check_stop(self.stop)
        source = row['source']
        if source not in self.checked or _stat(source) != self.checked[source]:
            raise ValueError('A source changed after scanning. Start a new scan.')
        manual = row.get('marked_extract')
        key = (manual['sha256'], manual['first'], manual['after']) if manual else (
            row['source_sha256'], row['in_tick'], row['out_tick'])
        if key not in self.cache:
            self.room()
            saved = self.work / (digest(key)[:24] + '.mp4')
            if manual:
                clip = self.project / manual['path']
                identity = _stat(clip)
                if _content_fingerprint(clip, self.stop) != manual['sha256']:
                    raise ValueError('The marked Best Clip changed. Rescan before marking the frame again.')
                info = extract_marked(clip, manual['first'], manual['after'], saved, self.device, self.stop)
                if _stat(clip) != identity:
                    raise ValueError('The marked Best Clip changed while rendering.')
            else:
                info = _extract(row, saved, self.device, self.stop)
            if _stat(source) != self.checked[source]:
                raise ValueError('A source changed while extracting. Start a new scan.')
            self.cache[key] = saved, info
        saved, info = self.cache[key]
        self.room(saved.stat().st_size)
        shutil.copyfile(saved, path)
        return info

    def group(self, rows, stage, final):
        clips, parts, assets = [], [], {}
        for i, row in enumerate(rows, 1):
            slug, source = _clip_label(row)
            name = f'{i:02d}__{source}__{slug}.mp4'
            part = stage / name
            info = self.extract(row, part)
            key, details = _artifact(self.project, final / name, part, self.stop, **info)
            assets[key] = details
            clips.append({**_public_span(row), 'asset': key})
            parts.append((part, info))
        joined = stage / 'preview.mp4'
        self.room(sum(path.stat().st_size for path, _ in parts))
        info = _join(parts, joined, self.work, self.device, self.stop)
        key, details = _artifact(self.project, final / joined.name, joined, self.stop, **info)
        assets[key] = details
        evidence = []
        for pair in supporting_frames(parts, stage, self.stop):
            keys = []
            for path in pair:
                frame, info = _artifact(self.project, final / path.name, path, self.stop)
                assets[frame] = info
                keys.append(frame)
            evidence.append(keys)
        return {'clips': clips, 'preview': key, 'supporting_frames': evidence, 'artifacts': assets}


def _best(renderer, rows, failures, progress):
    project, stop = renderer.project, renderer.stop
    folder = project / 'Best Clip'
    folder.mkdir(exist_ok=True)
    ledger = folder / 'index.json'
    previous = _read(ledger, {})
    result, artifacts = [], {}
    rows.sort(key=lambda row: (-row['score'], row['source'], row['start']))
    for i, row in enumerate(rows, 1):
        progress(f'Exporting Best Clip {i} of {len(rows)}', 61 + round(23 * i / len(rows)))
        old = previous.get(row['id'])
        if old and _artifacts_ok(project, {old['item']['asset']: old['artifact']}, stop):
            item, info = old['item'], old['artifact']
        else:
            slug, source = _clip_label(row)
            number = old['number'] if old else 1 + max((r['number'] for r in previous.values()), default=0)
            filename = f'BC_{number:04d}__{slug}__{source}.mp4'
            final = folder / filename
            try:
                with tempfile.TemporaryDirectory(prefix='.match-cut-', dir=folder) as temp:
                    staged = Path(temp) / filename
                    measured = renderer.extract(row, staged)
                    key, info = _artifact(project, final, staged, stop, **measured)
                    staged.replace(final)
                item = {**_public_span(row), 'asset': key}
                previous[row['id']] = {'item': item, 'artifact': info, 'number': number}
                atomic_json(ledger, previous)
            except (OSError, ValueError, RuntimeError) as error:
                check_stop(stop)
                failures.append({'source': row['source'], 'details': str(error)})
                continue
        result.append(item)
        artifacts[item['asset']] = info
    return result, artifacts


def _group_records(project):
    return {row['id']: (path.parent, row) for path in (project / 'Match Cut Finder').glob('*/*/match.json')
            if re.fullmatch(r'\d+\.\d+', path.parent.name) and (row := _read(path))}


def _group_folder(project, count):
    name = COUNT_NAMES[count] if count < len(COUNT_NAMES) else str(count)
    return project / 'Match Cut Finder' / (name + ' Frame Match Cut')


def _clock_cut(left, right, source_left, source_right, cut):
    out_clock, in_clock = map(Fraction, (source_left['time_base'], source_right['time_base']))
    out_time, in_time = cut['anchor_seconds']
    out_sample = source_left['first_tick'] + round(out_time / out_clock)
    in_sample = source_right['first_tick'] + round(in_time / in_clock)
    outgoing, incoming = source_left['frame_pts'], source_right['frame_pts']
    after = bisect_left(outgoing, out_sample + 1)
    first = bisect_left(incoming, in_sample)
    out_tick = min(left['out_tick'], outgoing[after] if after < len(outgoing) else source_left['end_tick'])
    in_tick = max(right['in_tick'], incoming[first] if first < len(incoming) else right['in_tick'])
    return {**cut, 'out_tick': out_tick, 'in_tick': in_tick}


def _publish_group(renderer, rows, cuts, count, score, records, *, marks=None):
    project, stop = renderer.project, renderer.stop
    identity = [RENDER_PROFILE, [[row['source_sha256'], row['in_tick'], row['out_tick']] for row in rows]]
    if marks is not None:
        identity.append(['manual', marks])
    else:
        identity.append(['calibration', CALIBRATION])
    key = digest(identity)[:24]
    if key in records:
        folder, group = records[key]
        original = group['original']
        if not _artifacts_ok(project, original['artifacts'], stop):
            raise ValueError('An existing group export was changed or removed. Restore its files before rescanning.')
        if marks is None and not group['locked']:
            group.update(score=score, cuts=cuts, calibration=CALIBRATION, weights=WEIGHTS)
            atomic_json(folder / 'match.json', group)
        return group

    bucket = _group_folder(project, count)
    number = 1 + max((int(group['name'].split('.')[1]) for _, group in records.values()
                      if group['count'] == count), default=0)
    name = f'{count}.{number}'
    folder = bucket / name
    with tempfile.TemporaryDirectory(prefix='.match-cut-', dir=bucket.parent) as temp:
        stage = Path(temp) / name
        stage.mkdir()
        rendered = renderer.group(rows, stage, folder)
        tags = ['Framing', 'Shape']
        if any(cut['motion'] is not None for cut in cuts):
            tags.append('Motion')
        group = {'id': key, 'name': name, 'count': count, 'score': score, 'rating': None, 'tags': tags,
                 'status': 'verified', 'locked': False, 'revision': 1, 'render_profile': RENDER_PROFILE,
                 'calibration': CALIBRATION, 'weights': WEIGHTS, 'cuts': cuts,
                 'folder': folder.relative_to(project).as_posix(), 'original': rendered, 'renditions': []}
        if marks is not None:
            group.update(tags=['Manual'], manual_anchors=marks, calibration=None, weights=None,
                         render_profile=RENDER_PROFILE + '+marked-frames')
        atomic_json(stage / 'match.json', group)
        bucket.mkdir(exist_ok=True)
        stage.replace(folder)
    records[key] = folder, group
    return group


def _result(project, best, assets, records, ranked, outcomes, failures, candidates):
    ranked = [id for id in ranked if id in records]
    matches, used = [], set()
    for id in [*ranked, *records]:
        if id in used:
            continue
        used.add(id)
        _, group = records[id]
        active = group['renditions'][-1] if group['renditions'] else group['original']
        for rendition in [group['original'], *group['renditions']]:
            assets.update(rendition['artifacts'])
        match = {key: value for key, value in group.items() if key not in ('original', 'renditions')}
        if id not in ranked and match['status'] == 'verified' and not match['locked'] and not match.get('manual_anchors'):
            match['status'] = 'archived'
        match.update({k: v for k, v in active.items() if k not in ('artifacts', 'revision')},
                     rank=ranked.index(id) + 1 if id in ranked else None,
                     rendition_revision=active.get('revision', 1),
                     preview_path=active['artifacts'][active['preview']]['path'],
                     original_preview=group['original']['preview'])
        matches.append(match)
    result = {'version': 2, 'project': project.name, 'folder': str(project), 'best': best, 'groups': matches,
              'ranked': ranked, 'sources': outcomes, 'failures': failures, 'candidates': candidates,
              'threshold': MIN_SCORE, 'weights': WEIGHTS, 'calibration': CALIBRATION, 'artifacts': assets,
              'selection': 'Scores rank the evidence for review. They are not probabilities.'}
    atomic_json(_index(project), result)
    return result


def _refresh(project):
    current = _read(_index(project))
    assets = {row['asset']: current['artifacts'][row['asset']] for row in current['best']}
    return _result(project, current['best'], assets, _group_records(project), current['ranked'],
                   current['sources'], current['failures'], current['candidates'])


def _review_group(project, value):
    records = _group_records(project)
    if not isinstance(value.get('group'), str) or value['group'] not in records:
        raise ValueError('Choose a verified match group.')
    folder, group = records[value['group']]
    if type(value.get('revision')) is not int or value['revision'] != group['revision']:
        raise ValueError('This match changed. Reload its latest revision before editing.')
    return folder, group


def review(root, value):
    project = _project(root, value.get('project'))
    if not _index(project).is_file():
        raise ValueError('Choose a completed match project.')
    with _write_lock(project):
        return _review(project, value)


def _review(project, value):
    folder, group = _review_group(project, value)
    action = value.get('action')
    if action == 'insert_group':
        if group['status'] == 'rejected':
            raise ValueError('Restore the rejected match before inserting it.')
        active = group['renditions'][-1] if group['renditions'] else group['original']
        from threading import Event
        if not _artifacts_ok(project, active['artifacts'], Event()):
            raise ValueError('The verified media changed. Restore the original export before inserting.')
        timeline = insert_group(project, active['clips'], active['artifacts'], active['preview'])
        return {'timeline': str(timeline)}
    if action == 'lock':
        group['locked'] = not group['locked']
    elif group['locked']:
        raise ValueError('Unlock this match before changing it.')
    elif action == 'reject':
        group['status'] = 'verified' if group['status'] == 'rejected' else 'rejected'
    elif action == 'rate' and type(value.get('rating')) is int and 1 <= value['rating'] <= 5:
        group['rating'] = value['rating']
    else:
        raise ValueError('Choose a supported match review action.')
    group['revision'] += 1
    atomic_json(folder / 'match.json', group)
    return _refresh(project)


def render_group(project, value, stop, progress, gpu_root):
    progress('Checking the original source clocks', 10)
    with gpu_lock(gpu_root), _write_lock(project):
        folder, group = _review_group(project, value)
        if group['locked'] or group['status'] == 'rejected':
            raise ValueError('Unlock and restore this match before adjusting its trims.')
        original = group['original']['clips']
        if len(original) != len(value['trims']):
            raise ValueError('Enter an in and out time for each clip.')
        checked, rows = {}, []
        for old, trim in zip(original, value['trims']):
            if (not isinstance(trim, list) or len(trim) != 2 or
                    any(type(x) not in (int, float) or not math.isfinite(x) for x in trim)):
                raise ValueError('Enter finite source times in seconds.')
            metadata = _read(project / '.sources' / (old['source_sha256'] + '.json'))
            if old['source'] not in checked:
                identity = _stat(old['source'])
                if _content_fingerprint(old['source'], stop) != old['source_sha256']:
                    raise ValueError('A source changed. Scan the collection again before revising.')
                checked[old['source']] = identity
            clock = Fraction(old['time_base'])
            ticks = metadata['frame_pts'] + [metadata['end_tick']]
            requested = [metadata['first_tick'] + round(seconds / clock) for seconds in trim]
            if requested[0] < old['in_tick'] or requested[1] > old['out_tick'] or trim[1] - trim[0] < .5:
                raise ValueError('Keep each revised trim within its original extract and at least half a second long.')
            start, end = (ticks[bisect_left(ticks, tick)] for tick in requested)
            rows.append(span(old, metadata, start, end))
        group['revision'] += 1
        final = folder / f'Revision {group["revision"]}'
        while final.exists():
            group['revision'] += 1
            final = folder / f'Revision {group["revision"]}'
        progress('Rendering the revised trims', 45)
        with tempfile.TemporaryDirectory(prefix='.match-cut-', dir=folder) as temp:
            work = Path(temp)
            stage = work / 'rendition'
            stage.mkdir()
            renderer = Renderer(project, work, heavy_device(gpu_root), checked, stop)
            result = renderer.group(rows, stage, final)
            result.update(revision=group['revision'], kind='manual trim', scores_apply_to='original')
            atomic_json(stage / 'rendition.json', result)
            check_stop(stop)
            stage.replace(final)
        group['renditions'].append(result)
        atomic_json(folder / 'match.json', group)
        return _refresh(project)


def create_manual_pair(project, marks, stop, progress, gpu_root):
    progress('Checking the marked frames', 10)
    with gpu_lock(gpu_root), _write_lock(project):
        current = _read(_index(project))
        best = {item['asset']: item for item in current['best']}
        if marks[0]['asset'] == marks[1]['asset']:
            raise ValueError('Choose two different Best Clips.')
        checked, rows, anchors = {}, [], []
        for outgoing, mark in zip((True, False), marks):
            asset, frame = mark['asset'], mark['frame']
            if asset not in best:
                raise ValueError('A marked clip is no longer in this collection. Mark its frame again.')
            clip, media = best[asset], current['artifacts'][asset]
            if frame >= media['frames']:
                raise ValueError('A marked frame is outside its Best Clip.')
            first, after = (0, frame + 1) if outgoing else (frame, media['frames'])
            if after - first < FPS // 2:
                raise ValueError('Leave at least half a second on each side of the cut.')
            metadata = _read(project / '.sources' / (clip['source_sha256'] + '.json'))
            path = clip['source']
            identity = _stat(path)
            if _content_fingerprint(path, stop) != clip['source_sha256'] or _stat(path) != identity:
                raise ValueError('A source changed. Scan the collection again before creating a pair.')
            checked[path] = identity
            clock = Fraction(clip['time_base'])
            ticks = metadata['frame_pts'] + [metadata['end_tick']]

            def source_tick(excerpt_frame):
                target = clip['in_tick'] + round(Fraction(excerpt_frame, FPS) / clock)
                return min(clip['out_tick'], ticks[min(bisect_left(ticks, target), len(ticks) - 1)])

            row = span(clip, metadata, source_tick(first), source_tick(after))
            row['marked_extract'] = {'path': media['path'], 'sha256': media['sha256'], 'first': first, 'after': after}
            rows.append(row)
            anchors.append({'role': 'outgoing' if outgoing else 'incoming', 'asset': asset, 'frame': frame,
                            'asset_sha256': media['sha256'], 'source_tick': source_tick(frame)})
        progress('Rendering the manual pair', 45)
        with tempfile.TemporaryDirectory(prefix='.match-cut-', dir=project) as temp:
            renderer = Renderer(project, Path(temp), heavy_device(gpu_root), checked, stop)
            cut = {'out_tick': rows[0]['out_tick'], 'in_tick': rows[1]['in_tick'],
                   'transition': 'hard cut', 'motion': None, 'manual': True}
            group = _publish_group(renderer, rows, [cut], 2, None, _group_records(project), marks=anchors)
        return {**_refresh(project), 'manual_group': group['id']}


def run(root, value, job_folder, stop, progress, gpu_root=None):
    db = Store(root / 'cache/match-cut/ledger.sqlite3')
    key = 'job:' + job_folder.name
    record = {'request_sha256': digest(value), 'operation': value.get('operation', 'scan_collection')}
    db.cached(key, {**record, 'status': 'running'})
    try:
        result = _run(root, value, job_folder, stop, progress, gpu_root)
    except Exception:
        db.cached(key, {**record, 'status': 'cancelled' if stop.is_set() else 'failed'})
        raise
    db.cached(key, {**record, 'status': 'complete', 'project': result['project'],
                    'published_groups': len(result['groups']), 'best_clips': len(result['best'])})
    return result


def _run(root, value, job_folder, stop, progress, gpu_root):
    gpu_root = gpu_root or root
    parsed = settings(value)
    if parsed is None:
        project = _project(root, value.get('project'))
        if value.get('operation') == 'create_manual_pair':
            return create_manual_pair(project, value['marks'], stop, progress, gpu_root)
        return render_group(project, value, stop, progress, gpu_root)
    paths, folders, maximum, limit = parsed
    scope = [sorted({os.path.normcase(str(Path(item).resolve())) for item in selection}) for selection in (paths, folders)]
    project = _project(root, digest(scope)[:24])
    progress('Finding videos in all selected folders', 1)
    candidates, rows, sources, outcomes, checked = scan_collection(root, paths, folders, stop, progress)
    atomic_json(job_folder / 'source-outcomes.json', outcomes)
    if not rows:
        raise ValueError('No usable clips were found. Choose readable, sufficiently exposed video footage.')
    progress('Finding movement that carries across cuts', 46)
    graph = find_matches(candidates, stop, progress)
    groups = list(_chains(graph, candidates, min(maximum, len(candidates)), limit, stop))
    progress('Waiting for the Storylens encoder', 60)
    with gpu_lock(gpu_root), _write_lock(project):
        check_stop(stop)
        (project / 'Match Cut Finder').mkdir(parents=True, exist_ok=True)
        metadata = project / '.sources'
        metadata.mkdir(exist_ok=True)
        for fingerprint, source in sources.items():
            atomic_json(metadata / (fingerprint + '.json'), source)
        records, ranked, failures = _group_records(project), [], []
        with tempfile.TemporaryDirectory(prefix='.match-cut-', dir=project) as temp:
            renderer = Renderer(project, Path(temp), heavy_device(gpu_root), checked, stop)
            previews_only = value.get('transition_previews_only') is True
            best, assets = ([], {}) if previews_only else _best(renderer, rows, failures, progress)
            total = sum(len(items) for _, items in groups)
            finished = 0
            for count, items in groups:
                for score, indices, cuts in items:
                    selected = [candidates[i] for i in indices]
                    cuts = [_clock_cut(left, right, sources[left['source_sha256']], sources[right['source_sha256']], cut)
                            for left, right, cut in zip(selected, selected[1:], cuts)]
                    trims = [span(row, sources[row['source_sha256']],
                                  cuts[i - 1]['in_tick'] if i else row['in_tick'],
                                  cuts[i]['out_tick'] if i + 1 < count else row['out_tick'])
                             for i, row in enumerate(selected)]
                    if min(row['duration'] for row in trims) < .45:
                        continue
                    check_stop(stop)
                    finished += 1
                    progress(f'Building preview {finished} of {total}', 84 + round(15 * finished / total))
                    try:
                        group = _publish_group(renderer, trims, cuts, count, round(score, 4), records)
                        ranked.append(group['id'])
                    except (OSError, ValueError, RuntimeError) as error:
                        check_stop(stop)
                        failures.append({'source': ' → '.join(Path(row['source']).name for row in trims),
                                         'details': str(error)})
        if not best and not previews_only:
            atomic_json(job_folder / 'render-failures.json', failures)
            raise ValueError('No Best Clips could be exported. Check the encoder and source files, then retry.')
        return _result(project, best, assets, records, ranked, outcomes, failures, len(candidates))
