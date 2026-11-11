"""Reference Reel's local, source-linked analysis and assembly."""
from fractions import Fraction
from pathlib import Path
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import math
import os
import re
import shutil
import threading
import uuid

import av
import cv2
import numpy as np

from hinglish_beats.detect import candidates, features, number
from hinglish_cinematic.render import run_ffmpeg
from hinglish_cut.xml_export import add, premiere_pathurl, rate, video_format_dimensions
from xml.etree import ElementTree as ET
from .reference_reel_media import (apply_look, color_lut, display_rgb, fit_look, flow_pair, interpolate,
                                  look_sample, periodic_cues, reference_still, rgb, separate_reference)
from .reference_reel_research import compare_candidates, inspect_reference_text, label_entries, research_effects


VIDEO_TYPES = {'.mp4', '.mov', '.mkv', '.webm', '.m4v'}
AUDIO_TYPES = {'.wav', '.mp3', '.m4a', '.flac', '.aiff', '.aac', '.ogg'}
AUDIO_ROLES = ('dialogue', 'music', 'effects', 'ambience')
SHOT_ROLES = {
    'automatic': (),
    'preparation': ('prep', 'lacing', 'strap', 'boot', 'equipment', 'setup'),
    'travel': ('travel', 'ride', 'road', 'trail', 'movement', 'drive', 'surf'),
    'reveal': ('reveal', 'emerge', 'unveil'),
    'reaction': ('reaction', 'expression', 'celebration'),
    'wide': ('wide', 'vista', 'establishing', 'panorama'),
    'detail': ('detail', 'macro', 'closeup'),
}
LOCK = threading.Lock()
MAX_UPLOAD = 2 * 1024**3
MAX_ASSETS = 12
MAX_FOLDER_ASSETS = 200
ANALYZER_VERSION = 2
EFFECT_DOCS = {
    'time remapping': 'https://helpx.adobe.com/after-effects/desktop/apply-effects-and-animation-presets/list-of-effects/time-effects.html',
    'transition': 'https://helpx.adobe.com/premiere/desktop/add-video-effects/effects-and-transitions-library/list-of-video-transitions.html',
}
FILES = {
    'plan.json': 'application/json',
    'reference-analysis.json': 'application/json',
    'recipe.json': 'application/json',
    'substitutions.json': 'application/json',
    'assets-and-rights.json': 'application/json',
    'fidelity-report.html': 'text/html; charset=utf-8',
    'reference-reel.jsx': 'application/octet-stream',
    'REFERENCE_REEL.xml': 'application/xml',
    'preview.mp4': 'video/mp4',
    'comparison.mp4': 'video/mp4',
    'comparison-frames.jpg': 'image/jpeg',
    'resolve-look.zip': 'application/zip',
}


def directory(root, identifier, kind):
    if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{32}', identifier):
        raise ValueError('Invalid Reference Reel ID.')
    parent = (Path(root) / 'output/reference-reel' / kind).resolve()
    folder = (parent / identifier).resolve()
    if folder.parent != parent:
        raise ValueError('Invalid Reference Reel location.')
    return folder


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False), 'utf-8')


def read_json(path):
    return json.loads(path.read_text('utf-8'))


def upload(root, name, stream, size):
    name = Path(name).name
    suffix = Path(name).suffix.lower()
    if suffix not in VIDEO_TYPES | AUDIO_TYPES or not 0 < size <= MAX_UPLOAD:
        raise ValueError('Choose a supported video or audio file up to 2 GiB.')
    asset_id = uuid.uuid4().hex
    folder = directory(root, asset_id, 'assets')
    folder.mkdir(parents=True)
    digest = hashlib.sha256()
    try:
        with (folder / ('source' + suffix)).open('xb') as target:
            while size:
                chunk = stream.read(min(1024**2, size))
                if not chunk:
                    raise ValueError('The upload stopped before the complete file arrived.')
                target.write(chunk)
                digest.update(chunk)
                size -= len(chunk)
        asset = {'id': asset_id, 'name': name, 'sha256': digest.hexdigest()}
        save_json(folder / 'asset.json', asset)
        return asset
    except BaseException:
        shutil.rmtree(folder)
        raise


def asset_record(root, asset_id):
    folder = directory(root, asset_id, 'assets')
    asset = read_json(folder / 'asset.json')
    if 'local_source' in asset:
        path = Path(asset['local_source'])
        try:
            stat = path.stat()
        except OSError as error:
            raise ValueError('A replacement video moved. Choose the footage folder again.') from error
        if not path.is_file() or [stat.st_size, stat.st_mtime_ns] != asset['stat']:
            raise ValueError('A replacement video changed. Choose the footage folder again.')
        return asset | {'path': str(path)}
    path = (folder / ('source' + Path(asset['name']).suffix.lower())).resolve()
    if path.parent != folder or not path.is_file():
        raise ValueError('An uploaded source is missing. Upload it again.')
    return asset | {'path': str(path)}


def motion_fit(before, after, difference):
    if before is None or not .006 < difference < .32:
        return None
    points = cv2.goodFeaturesToTrack(before, maxCorners=32, qualityLevel=.03, minDistance=6)
    if points is None or len(points) < 8:
        return None
    tracked, found, errors = cv2.calcOpticalFlowPyrLK(before, after, points, None,
                                                    winSize=(15, 15), maxLevel=2)
    mask = (found.ravel() == 1) & (errors.ravel() < 22)
    if np.count_nonzero(mask) < 8:
        return None
    old, new = points[mask, 0], tracked[mask, 0]
    matrix, inliers = cv2.estimateAffinePartial2D(old, new, ransacReprojThreshold=1.2, maxIters=160)
    if matrix is None or float(inliers.mean()) < .60:
        return None
    scale = float(np.hypot(matrix[0, 0], matrix[0, 1]))
    if not .78 < scale < 1.28:
        return None
    center = np.array([48., 48.])
    translation = matrix[:, :2] @ center + matrix[:, 2] - center
    residual = np.linalg.norm(new - (old @ matrix[:, :2].T + matrix[:, 2]), axis=1)
    return {'x': round(float(translation[0]) / 96, 5), 'y': round(float(translation[1]) / 96, 5),
            'scale': round(scale, 5), 'rotation': round(math.degrees(math.atan2(matrix[1, 0], matrix[0, 0])), 3),
            'local': round(float(np.median(residual)) / 96, 5), 'inliers': round(float(inliers.mean()), 4)}


def scan(asset, frame_limit, *, sample_fps=None):
    """Use all decoded presentation timestamps, including variable-rate sources."""
    rows = []
    previous = None
    previous_histogram = None
    with av.open(asset['path']) as media:
        if not media.streams.video:
            raise ValueError(f'{asset["name"]} has no video track.')
        video = media.streams.video[0]
        source_rate = video.average_rate or Fraction(30)
        time_base = str(video.time_base)
        next_sample = None
        for frame in media.decode(video):
            if sample_fps and frame.time is not None and next_sample is not None and frame.time < next_sample:
                continue
            if len(rows) >= frame_limit:
                raise ValueError(f'{asset["name"]} exceeds the {frame_limit:,}-frame analysis limit.')
            if frame.time is None:
                raise ValueError(f'{asset["name"]} has a video frame without a timestamp.')
            image = frame.reformat(width=96, height=96, format='rgb24').to_ndarray()
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            histogram = cv2.calcHist([image], [0, 1, 2], None, [6, 6, 6], [0, 256] * 3)
            histogram /= gray.size
            difference = float(cv2.absdiff(gray, previous).mean() / 255) if previous is not None else 0.
            distance = float(cv2.compareHist(histogram, previous_histogram, cv2.HISTCMP_BHATTACHARYYA)) if previous_histogram is not None else 0.
            if not rows:
                origin = frame.time
                rotation = getattr(frame, 'rotation', 0)
                width, height = (frame.height, frame.width) if abs(rotation) % 180 else (frame.width, frame.height)
                color = {key: int(getattr(frame, key)) for key in
                         ('colorspace', 'color_range', 'color_primaries', 'color_trc')}
            timestamp = frame.time - origin
            if rows and timestamp <= rows[-1]['t']:
                raise ValueError(f'{asset["name"]} has duplicate or unordered video timestamps.')
            rows.append({'t': timestamp, 'luma': round(float(gray.mean()), 4),
                         'contrast': round(float(gray.std()), 4),
                         'sharpness': round(float(cv2.Laplacian(gray, cv2.CV_32F).var()), 3),
                         'rgb': [round(float(v), 3) for v in image.mean(axis=(0, 1))],
                         'motion': round(difference, 5), 'histogram_change': round(distance, 5),
                         'global_motion': motion_fit(previous, gray, difference)})
            previous, previous_histogram = gray, histogram
            if sample_fps:
                next_sample = frame.time + 1 / sample_fps - 1e-7
            tail = float(frame.duration * frame.time_base) if frame.duration else 0.
        if sample_fps and video.duration:
            tail = max(tail, float(video.duration * video.time_base) - rows[-1]['t']) if rows else tail
        if not rows:
            raise ValueError(f'{asset["name"]} has no decodable video frames.')
        duration = rows[-1]['t'] + (tail or (rows[-1]['t'] - rows[-2]['t'] if len(rows) > 1 else 1 / float(source_rate)))
        if duration > (150 if frame_limit == 9000 else 600):
            raise ValueError(f'{asset["name"]} exceeds the maximum analysis duration.')
    with av.open(asset['path']) as media:
        audio_frame = next(media.decode(audio=0), None) if media.streams.audio else None
        audio_offset = None if audio_frame is None else (audio_frame.time or 0.) - origin
    return asset | {'frames': rows, 'rate': str(source_rate), 'width': width, 'height': height,
                    'duration': duration, 'audio_offset': audio_offset, 'origin': origin,
                    'time_base': time_base, 'color_metadata': color}


def summarize(rows):
    return {key: round(float(np.median([row[key] for row in rows])), 5)
            for key in ('luma', 'contrast', 'motion')}


def editorial_signature(sample):
    fits = [row['global_motion'] for row in sample if row.get('global_motion')]
    if len(fits) < max(3, len(sample) // 5):
        return {'motion_role': 'steady/detail' if np.median([row['motion'] for row in sample]) < .035 else 'unclassified',
                'fit_coverage': round(len(fits) / len(sample), 3), 'direction': [0, 0]}
    dx, dy, local = np.median([[fit['x'], fit['y'], fit['local']] for fit in fits], axis=0)
    role = 'directional travel' if math.hypot(dx, dy) > .008 else 'subject motion' if local > .010 else 'steady/detail'
    return {'motion_role': role, 'fit_coverage': round(len(fits) / len(sample), 3),
            'direction': [round(float(dx), 5), round(float(dy), 5)]}


def retime_hint(sample):
    if len(sample) < 24:
        return None
    groups = np.array_split(np.arange(1, len(sample)), 3)
    levels = []
    for group in groups:
        fits = [sample[i]['global_motion'] for i in group if sample[i].get('global_motion')]
        if len(fits) < len(group) * .65:
            return None
        directions = np.array([[fit['x'], fit['y']] for fit in fits])
        magnitude = np.linalg.norm(directions, axis=1)
        speed = float(np.median(magnitude))
        if speed < .003 or np.linalg.norm(np.median(directions, axis=0)) < speed * .72:
            return None
        levels.append(speed)
    if max(levels) / min(levels) < 1.65:
        return None
    baseline = float(np.median(levels))
    return {'speed': [round(max(.55, min(1.6, level / baseline)), 2) for level in levels],
            'normalized_motion': [round(level, 5) for level in levels],
            'status': 'inferred pacing suggestion; original speed is unknown',
            'reference_seconds': [sample[0]['t'], sample[-1]['t']],
            'documentation': EFFECT_DOCS['time remapping']}


def evidence_cues(sample, fps):
    cues = []
    for i in range(1, len(sample) - 1):
        before, now, after = sample[i - 1:i + 2]
        if now['luma'] > max(before['luma'], after['luma']) + 34 and abs(before['luma'] - after['luma']) < 10:
            delta = now['luma'] - (before['luma'] + after['luma']) / 2
            options = sorted(set(max(5, min(90, round(100 * delta / max(1, 255 - before['luma']) + n)))
                                 for n in (-10, 0, 10)))
            ranked = sorted((round(abs((255 - before['luma']) * opacity / 100 - delta), 3), opacity)
                            for opacity in options)
            cues.append({'kind': 'brief luma spike', 'seconds': now['t'], 'frame': round(now['t'] * fps),
                         'luma_delta': round(delta, 2), 'provenance': 'measured pixels',
                         'resolution': 'built-in white pulse approximation',
                         'candidate_luma_errors': ranked, 'recommended_opacity': ranked[0][1]})
    for i, now in enumerate(sample):
        fit = now.get('global_motion')
        if fit and abs(fit['x']) > .065 and now['sharpness'] < .6 * max(
            row['sharpness'] for row in sample[max(0, i - 4):i + 1]
        ):
            cues.append({'kind': 'possible directional blur', 'frame': round(now['t'] * fps), 'seconds': now['t'],
                         'previous_seconds': sample[i - 1]['t'],
                         'translation_x': fit['x'], 'inlier_fraction': fit['inliers'],
                         'provenance': 'inferred from motion and loss of edge detail',
                         'resolution': 'clean fallback', 'documentation': EFFECT_DOCS['transition']})
            break
    for i in range(6, len(sample)):
        region = sample[i - 6:i + 1]
        changes = [row['histogram_change'] for row in region[1:]]
        if sum(.065 <= value <= .27 for value in changes) >= 5 and max(changes) < .32 and (
            abs(region[-1]['luma'] - region[0]['luma']) > 20
        ):
            cues.append({'kind': 'possible gradual blend', 'frame': round(region[3]['t'] * fps),
                         'seconds': region[3]['t'], 'range_seconds': [region[0]['t'], region[-1]['t']],
                         'provenance': 'sustained histogram movement and a luma shift',
                         'resolution': 'clean fallback', 'documentation': EFFECT_DOCS['transition']})
            break
    return cues


def boundaries(reference, sensitivity):
    rows = reference['frames']
    cuts = [0]
    for index, row in enumerate(rows[1:], 1):
        if row['t'] - rows[cuts[-1]]['t'] < .10:
            continue
        if row['histogram_change'] >= sensitivity and row['motion'] >= .09:
            # A single bright frame that immediately returns is a flash cue.
            if index < len(rows) - 1 and abs(rows[index + 1]['luma'] - rows[index - 1]['luma']) < 10 and (
                row['luma'] - max(rows[index - 1]['luma'], rows[index + 1]['luma']) > 34
            ):
                continue
            if index > 1 and rows[index - 1]['luma'] - max(row['luma'], rows[index - 2]['luma']) > 34 and (
                abs(row['luma'] - rows[index - 2]['luma']) < 10
            ):
                continue
            cuts.append(index)
    return cuts


def suggest(shots, sources, fps, pattern=None):
    """Propose non-overlapping ranges from within each source shot."""
    indexes = []
    for source in sources:
        rows = source['frames']
        starts = boundaries(source, .38)
        times = np.array([row['t'] for row in rows])
        totals = np.vstack([np.zeros(5), np.cumsum(
            [[row['motion'], row['contrast'], row['luma'],
              (row.get('global_motion') or {}).get('x', 0), (row.get('global_motion') or {}).get('y', 0)]
             for row in rows], axis=0)])
        step = max(1, round((source.get('sample_fps') or float(Fraction(source['rate']))) * .25))
        indexes.append((source, times, totals, step, list(zip(starts, starts[1:] + [len(rows)]))))
    options = []
    for slot, shot in enumerate(shots):
        duration = (shot['end'] - shot['start']) / fps
        controls = pattern[slot]['controls'] if pattern else {}
        role = controls.get('role', shot.get('role', 'automatic'))
        if role == 'automatic' and (shot.get('semantic') or {}).get('confidence') in ('medium', 'high'):
            role = shot['semantic']['role']
        source_length = duration * average_speed(controls)
        ranked = []
        for source, times, totals, step, spans in indexes:
            asset_id = source['id']
            for first, last in spans:
                end = times[last] if last < len(times) else source['duration']
                indices = np.arange(first, last, step)
                starts = times[indices]
                eligible = starts + source_length <= end + 1e-7
                indices, starts = indices[eligible], starts[eligible]
                if not len(indices):
                    continue
                ends = np.maximum(indices + 1, np.searchsorted(times, starts + source_length))
                motion, contrast, luma, x, y = ((totals[ends] - totals[indices]) / (ends - indices)[:, None]).T
                scores = abs(motion - shot['motion']) * 4
                scores += abs(contrast - shot['contrast']) / 160
                scores += abs(luma - shot['luma']) / 400
                direction = shot['signature']['direction']
                scores += 4 * np.hypot(x - direction[0], y - direction[1])
                words = set(re.findall('[a-z]+', source['name'].casefold()))
                if words.intersection(SHOT_ROLES[role]):
                    scores -= .18
                if role != 'automatic':
                    centers = starts + source_length / 2
                    for label in source.get('semantic_windows', []):
                        if label['confidence'] == 'low' or label['role'] == 'automatic':
                            continue
                        inside = (centers >= label['start']) & (centers < label['end'])
                        scores[inside] += -.65 if label['role'] == role else .26
                # Retain several feasible offsets so a neighboring slot can use a
                # different part of the same file without crossing its source cut.
                for best in np.argsort(scores, kind='stable')[:4]:
                    ranked.append((float(scores[best]), asset_id, float(starts[best]), float(luma[best])))
        ranked.sort()
        per_source = {}
        for candidate in ranked:
            shortlist = per_source.setdefault(candidate[1], [])
            if len(shortlist) < 4:
                shortlist.append(candidate)
        options.append((source_length, sorted(candidate for group in per_source.values() for candidate in group)))

    beam = [(0., [], {})]
    for length, candidates_for_slot in options:
        proposals = []
        for score, chosen, occupied in beam:
            for candidate in candidates_for_slot:
                cost, asset_id, start, _ = candidate
                spans = occupied.get(asset_id, [])
                if any(start < b - 1e-7 and start + length > a + 1e-7 for a, b in spans):
                    continue
                previous = chosen[-1] if chosen else None
                reuse_penalty = .1 if previous and previous[1] == asset_id else 0
                proposals.append((score + cost + reuse_penalty, [*chosen, candidate],
                                  occupied | {asset_id: [*spans, (start, start + length)]}))
            proposals.append((score + 5., [*chosen, None], occupied))
        beam = sorted(proposals, key=lambda item: item[0])[:8]

    result = []
    for slot, (shot, chosen) in enumerate(zip(shots, beam[0][1])):
        controls = pattern[slot]['controls'] if pattern else {}
        choices = []
        for score, asset_id, start, _ in options[slot][1]:
            if all(item['asset'] != asset_id for item in choices):
                choices.append({'asset': asset_id, 'source_in': round(start, 8), 'distance': round(score, 4)})
        if chosen:
            score, asset_id, start, luma = chosen
            exposure = math.log2((shot['luma'] + 8) / (luma + 8))
            result.append({'asset': asset_id, 'source_in': round(start, 8), 'speed_in': 1, 'speed_out': 1,
                           'exposure': round(max(-1.5, min(1.5, exposure)), 2), 'zoom_in': 100, 'zoom_out': 100,
                           'evidence': '', 'distance': round(score, 4), 'alternatives': choices[:5]})
        else:
            result.append({'asset': '', 'source_in': 0, 'speed_in': 1, 'speed_out': 1,
                           'exposure': 0, 'zoom_in': 100, 'zoom_out': 100, 'evidence': '', 'distance': None,
                           'alternatives': []})
        flashes = [cue for cue in shot['cues'] if cue['kind'] == 'brief luma spike']
        if len(flashes) == 1:
            result[-1].update(flash_frame=flashes[0]['frame'], flash_opacity=flashes[0]['recommended_opacity'])
        label = shot.get('semantic', {})
        result[-1]['role'] = label['role'] if label.get('confidence') in ('medium', 'high') else 'automatic'
        result[-1].update(controls)
        if slot and controls.get('transition') not in (None, 'cut'):
            previous = beam[0][1][slot - 1]
            has_tail = False
            if previous:
                source = next(item for item in sources if item['id'] == previous[1])
                tail = controls['transition_frames'] / fps * result[-2]['speed_out']
                has_tail = previous[2] + options[slot - 1][0] + tail <= source['duration'] + 1e-7
            if not chosen or (controls['transition'] == 'dissolve' and not has_tail):
                result[-1].update(transition='cut', transition_frames=0,
                                  fallback='Reused recipe transition omitted because a replacement or source handle was unavailable.')
    return result


def average_speed(mapping):
    first, last = mapping.get('speed_in', 1), mapping.get('speed_out', 1)
    middle = mapping.get('speed_mid')
    return (first + last) / 2 if middle is None else (first + 2 * middle + last) / 4


def footage_sources(root, payload, reference):
    ids = payload.get('footage')
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_ASSETS or any(not isinstance(i, str) for i in ids):
        raise ValueError(f'Choose 1–{MAX_ASSETS} replacement videos.')
    if len(set(ids)) != len(ids) or reference['id'] in ids:
        raise ValueError('Choose distinct reference and replacement inputs.')
    sources = [scan(asset_record(root, asset_id), 18000) for asset_id in ids]
    for source in sources:
        source['scene_times'] = [source['frames'][index]['t'] for index in boundaries(source, .38)[1:]]
    if len({source['sha256'] for source in [reference, *sources]}) != len(sources) + 1:
        raise ValueError('The reference and replacement files must contain distinct media.')
    return sources


def scan_folder(root, folder_path, reference):
    if not isinstance(folder_path, str) or not Path(folder_path).is_absolute():
        raise ValueError('Choose a local footage folder.')
    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        raise ValueError('The footage folder was not found.')
    files = sorted({path.resolve() for path in folder.rglob('*')
                    if path.suffix.lower() in VIDEO_TYPES and not path.name.startswith('._')
                    and path.is_file() and path.resolve().is_relative_to(folder)})
    if not 1 <= len(files) <= MAX_FOLDER_ASSETS:
        raise ValueError(f'Choose a folder containing 1–{MAX_FOLDER_ASSETS} supported videos.')
    sources, skipped = [], []
    seen = {reference['sha256']}
    for path in files:
        stat = path.stat()
        with path.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        if sha in seen:
            skipped.append(path.name)
            continue
        asset_id = uuid.uuid4().hex
        asset = {'id': asset_id, 'name': path.name, 'sha256': sha,
                 'local_source': str(path), 'stat': [stat.st_size, stat.st_mtime_ns]}
        try:
            source = scan(asset | {'path': str(path)}, 18000, sample_fps=8)
        except (av.FFmpegError, ValueError, OSError):
            skipped.append(path.name)
            continue
        source['sample_fps'] = 8
        source['scene_times'] = [source['frames'][index]['t'] for index in boundaries(source, .38)[1:]]
        record = directory(root, asset_id, 'assets')
        record.mkdir(parents=True)
        save_json(record / 'asset.json', asset)
        seen.add(sha)
        sources.append(source)
    if not sources:
        raise ValueError('No distinct, readable replacement footage was found.')
    return sources, skipped


def analyze(root, payload):
    reference = scan(asset_record(root, payload.get('reference')), 9000)
    folder_mode = 'folder' in payload
    sources, skipped = (scan_folder(root, payload['folder'], reference) if folder_mode
                        else (footage_sources(root, payload, reference), []))
    result = measure_clock(reference, .38 if folder_mode else payload.get('sensitivity', .38))
    if folder_mode:
        result['skipped_footage'] = skipped
    return save_analysis(root, reference, sources, result, semantic=payload.get('semantic', False),
                         review_text=payload.get('review_text', False))


def measure_clock(reference, sensitivity=.38, cuts=None):
    exact_rate = Fraction(reference['rate'])
    nominal = max(12, min(60, round(float(exact_rate))))
    fps = exact_rate if exact_rate in (nominal, Fraction(nominal * 1000, 1001)) else Fraction(nominal)
    rows = reference['frames']
    count = max(1, round(reference['duration'] * fps))
    if cuts is None:
        starts = boundaries(reference, number(sensitivity, 'Cut threshold', .18, .85))
        cuts = [frame for i in starts if (frame := round(rows[i]['t'] * fps)) < count]
    check_cuts(cuts, count)
    shots = make_shots(reference, fps, count, cuts)
    onsets = []
    audio_note = 'Reference has no audio stream.'
    if reference['audio_offset'] is not None:
        try:
            flux, energy, attacks, _ = features(reference['path'])
            for event in candidates(flux, energy, attacks):
                seconds = event['seconds'] + reference['audio_offset']
                frame = round(seconds * fps)
                if 0 <= frame < count:
                    onsets.append(event | {'seconds': round(seconds, 6), 'frame': frame})
            audio_note = 'Audio transients are candidates. Review them against the music before treating them as beats.'
        except (ValueError, av.FFmpegError) as error:
            audio_note = f'Onset analysis unavailable: {error}'
    return {'fps': str(fps), 'frame_count': count, 'decoded_frames': len(rows),
              'width': reference['width'], 'height': reference['height'], 'reference': reference['name'],
              'reference_id': reference['id'], 'reference_sha256': reference['sha256'], 'shots': shots,
              'onsets': onsets, 'audio_note': audio_note, 'has_audio': reference['audio_offset'] is not None,
              'periodic_cues': periodic_cues(onsets, float(fps)),
              'analyzer_version': ANALYZER_VERSION}


def save_analysis(root, reference, sources, result, pattern=None, *, semantic=False, review_text=False):
    if type(semantic) is not bool:
        raise ValueError('Choose whether to use ChatGPT editorial labels.')
    if type(review_text) is not bool:
        raise ValueError('Choose whether to use ChatGPT for sampled text review.')
    analysis_id = uuid.uuid4().hex
    folder = directory(root, analysis_id, 'analyses')
    folder.mkdir(parents=True)
    fps = float(Fraction(result['fps']))
    compare_candidates(reference, result['shots'])
    research_effects(result['shots'])
    result['semantic_review'] = {'status': 'off', 'detail': 'Local motion matching used.'}
    if semantic:
        try:
            semantic_pass(reference, sources, result['shots'], fps, folder)
            result['semantic_review'] = {'status': 'complete', 'detail': 'ChatGPT editorial roles scored with the measured source ranges.'}
        except (ValueError, OSError, RuntimeError) as error:
            result['semantic_review'] = {'status': 'fallback', 'detail': f'{error} Local motion matching used.'}
    if review_text:
        try:
            result['text_review'] = inspect_reference_text(reference, fps, result['frame_count'], folder)
        except (ValueError, OSError, RuntimeError) as error:
            result['text_review'] = {'status': 'unavailable', 'detail': str(error), 'observations': []}
    asset_summary = [{key: value for key, value in source.items() if key not in ('frames', 'path')} for source in sources]
    result = result | {'id': analysis_id, 'footage': asset_summary,
                       'mappings': suggest(result['shots'], sources, fps, pattern)}
    save_json(folder / 'frames.json', reference)
    save_json(folder / 'footage-frames.json', sources)
    save_json(folder / 'analysis.json', result)
    return result


def semantic_pass(reference, sources, shots, fps, folder):
    targets = {f'R{index+1}': shot for index, shot in enumerate(shots[:24]) if not shot.get('semantic')}
    entries = [(key, reference, shot['start'] / fps, shot['end'] / fps) for key, shot in targets.items()]
    windows = {}
    for index, source in enumerate(sources, 1):
        starts = [source['frames'][n]['t'] for n in boundaries(source, .38)]
        edges = starts + [source['duration']]
        spans = list(zip(edges, edges[1:]))
        if len(spans) == 1 and source['duration'] > 6:
            edges = np.linspace(0, source['duration'], 4).tolist()
            spans = list(zip(edges, edges[1:]))
        spans = sorted(sorted(spans, key=lambda span: span[1] - span[0], reverse=True)[:3])
        for number, (start, end) in enumerate(spans, 1):
            key = f'S{index}.{number}'
            windows[key] = (source, start, end)
            entries.append((key, source, start, end))
    labels = label_entries(entries, folder)
    for key, shot in targets.items():
        shot['semantic'] = labels[key]
    for key, (source, start, end) in windows.items():
        source.setdefault('semantic_windows', []).append(labels[key] | {'start': start, 'end': end})


def reuse(root, payload):
    if 'portable_recipe' in payload:
        return reuse_portable(root, payload)
    recipe_path = directory(root, payload.get('recipe'), 'recipes') / 'recipe.json'
    recipe = read_json(recipe_path)
    result = recipe['reference_clock']
    if result['analyzer_version'] != ANALYZER_VERSION:
        raise ValueError('The reference analyzer changed. Analyze the original reference again before reusing it.')
    folder = directory(root, recipe['source_analysis'], 'analyses')
    reference = read_json(folder / 'frames.json')
    stored = asset_record(root, reference['id'])
    if stored['sha256'] != result['reference_sha256']:
        raise ValueError('The saved recipe no longer matches the reference asset.')
    sources = footage_sources(root, payload, reference)
    return save_analysis(root, reference, sources, result | {'recipe_parent': recipe['id'],
                         'render_preferences': recipe.get('render_preferences', {})}, recipe['slots'],
                         semantic=payload.get('semantic', False), review_text=payload.get('review_text', False))


def reuse_portable(root, payload):
    recipe = payload['portable_recipe']
    if not isinstance(recipe, dict) or type(recipe.get('version')) is not int or recipe['version'] != 1:
        raise ValueError('Choose a version 1 Reference Reel recipe.')
    recipe_id = recipe.get('id')
    clock, slots = recipe.get('reference_clock'), recipe.get('slots')
    if (not isinstance(recipe_id, str) or not re.fullmatch('[0-9a-f]{32}', recipe_id)
            or not isinstance(clock, dict) or not isinstance(slots, list) or not 1 <= len(slots) <= 250
            or any(not isinstance(slot, dict) or not isinstance(slot.get('controls'), dict) for slot in slots)):
        raise ValueError('The recipe is missing its saved timeline or controls.')
    stored = asset_record(root, payload.get('reference'))
    if clock.get('reference_sha256') != stored['sha256']:
        raise ValueError('Upload the exact reference video used to create this recipe.')
    reference = scan(stored, 9000)
    result = measure_clock(reference, cuts=[slot.get('start') for slot in slots])
    if clock.get('fps') != result['fps'] or clock.get('frame_count') != result['frame_count']:
        raise ValueError('The recipe frame grid differs from the uploaded reference.')
    pattern = []
    for index, (slot, shot) in enumerate(zip(slots, result['shots'])):
        if slot.get('end') != shot['end']:
            raise ValueError('The recipe has an invalid shot span.')
        raw = slot['controls']
        controls = {key: number(raw.get(key, default), key, low, high) for key, default, low, high in (
            ('speed_in', 1, .25, 4), ('speed_out', 1, .25, 4), ('zoom_in', 100, 100, 200),
            ('zoom_out', 100, 100, 200), ('flash_opacity', 30, 0, 100))}
        mid, role, note = raw.get('speed_mid'), raw.get('role', 'automatic'), raw.get('evidence', '')
        transition, duration = raw.get('transition', 'cut'), raw.get('transition_frames', 0)
        flash = raw.get('flash_frame')
        if not isinstance(role, str) or role not in SHOT_ROLES or not isinstance(note, str) or len(note) > 600:
            raise ValueError('The recipe has an invalid shot role or observation.')
        if transition not in ('cut', 'dissolve', 'whip-left', 'whip-right') or (transition != 'cut' and (
            not index or type(duration) is not int or not 2 <= duration <= 12 or duration >= shot['end'] - shot['start']
        )):
            raise ValueError('The recipe has an invalid transition.')
        if flash is not None and (type(flash) is not int or flash not in {
            cue['frame'] for cue in shot['cues'] if cue['kind'] == 'brief luma spike'
        }):
            raise ValueError('The recipe flash no longer matches the measured reference frames.')
        controls.update(speed_mid=None if mid is None else number(mid, 'Midpoint speed', .25, 4),
                        role=role, evidence=note, transition=transition,
                        transition_frames=duration if transition != 'cut' else 0, flash_frame=flash)
        pattern.append({'controls': controls})
    preferences = recipe.get('render_preferences', {})
    if not isinstance(preferences, dict) or preferences.get('interpolation', 'sample') not in ('sample', 'optical'):
        raise ValueError('The recipe has an invalid interpolation setting.')
    verified_preferences = {'interpolation': preferences.get('interpolation', 'sample'),
                            'look_strength': number(preferences.get('look_strength', 0), 'Look strength', 0, 1)}
    sources = footage_sources(root, payload, reference)
    return save_analysis(root, reference, sources, result | {'recipe_parent': recipe_id,
                         'render_preferences': verified_preferences}, pattern, semantic=payload.get('semantic', False),
                         review_text=payload.get('review_text', False))


def make_shots(reference, fps, count, cuts):
    from bisect import bisect_left
    rows = reference['frames']
    times = [row['t'] for row in rows]
    shots = []
    for a, b in zip(cuts, cuts[1:] + [count]):
        if b <= a:
            continue
        # A cut rounded to a sequence frame can lie just before or after its PTS.
        left, right = (bisect_left(times, (edge - .5) / float(fps)) for edge in (a, b))
        sample = rows[left:right] or [rows[min(left, len(rows) - 1)]]
        flags = [cue for cue in evidence_cues(sample, fps) if a <= cue['frame'] < b]
        shots.append({'start': a, 'end': b, 'source_frame': left, 'cues': flags, 'signature': editorial_signature(sample),
                      'retime_hint': retime_hint(sample),
                      **summarize([item | {'motion': 0.} if index == 0 else item for index, item in enumerate(sample)])})
    if len(shots) > 250:
        raise ValueError('More than 250 cut candidates. Increase the cut threshold and analyze again.')
    return shots


def recut(root, analysis, cuts):
    fps = Fraction(analysis['fps'])
    folder = directory(root, analysis['id'], 'analyses')
    reference = read_json(folder / 'frames.json')
    check_cuts(cuts, analysis['frame_count'])
    shots = make_shots(reference, fps, analysis['frame_count'], cuts)
    previous = {(shot['start'], shot['end']): shot for shot in analysis['shots']}
    for shot in shots:
        old = previous.get((shot['start'], shot['end']))
        if old:
            for key in ('semantic', 'cues'):
                if key in old:
                    shot[key] = old[key]
    return shots, reference


def check_cuts(cuts, frame_count):
    if (not isinstance(cuts, list) or not cuts or cuts[0] != 0 or len(cuts) > 250
            or any(type(cut) is not int or not 0 <= cut < frame_count for cut in cuts)
            or cuts != sorted(set(cuts))):
        raise ValueError('Enter increasing whole cut frames, starting at 0, within the reel (250 shots max).')


def build_plan(root, analysis, payload):
    fps = Fraction(analysis['fps'])
    shots, reference = recut(root, analysis, payload.get('cuts'))
    mappings = payload.get('mappings')
    if not isinstance(mappings, list) or len(mappings) != len(shots):
        raise ValueError('Map one replacement range to each shot.')
    sources = {item['id']: asset_record(root, item['id']) | item for item in analysis['footage']}
    allow_missing = payload.get('allow_missing', False)
    if type(allow_missing) is not bool:
        raise ValueError('Choose whether unmatched shots may appear as review placeholders.')
    interpolation = payload.get('interpolation', 'sample')
    if interpolation not in ('sample', 'optical'):
        raise ValueError('Choose frame sampling or optical flow.')
    look_strength = number(payload.get('look_strength', 0), 'Rec.709 look strength', 0, 1)
    edits = []
    notes = [
        'Hard cut candidates and audio transients require review.',
        'Exposure suggestions compare measured luminance. Shot content, input color management and the reference grade are unresolved.',
        'Cross-subject suggestions rank motion direction, energy, contrast and luminance. Check action and shot role by eye.',
        'Unrecognized transitions and compositing use a clean edit. Original effect parameters and isolated reference sounds are unresolved.',
        'Reference video timestamps are mapped to a constant-rate composition. Source video is sampled at its presentation timestamps.',
    ]
    if analysis.get('semantic_review'):
        notes.append(analysis['semantic_review']['detail'])
    for index, (shot, mapping) in enumerate(zip(shots, mappings), 1):
        if not isinstance(mapping, dict) or not isinstance(mapping.get('asset'), str):
            raise ValueError(f'Choose replacement footage for shot {index}.')
        source = sources.get(mapping['asset'])
        if source is None and (mapping['asset'] or not allow_missing):
            raise ValueError(f'Choose replacement footage for shot {index} or allow review placeholders.')
        start = number(mapping.get('source_in'), f'Shot {index} source in', 0, source['duration'] if source else 600)
        first = number(mapping.get('speed_in'), f'Shot {index} starting speed', .25, 4)
        last = number(mapping.get('speed_out'), f'Shot {index} ending speed', .25, 4)
        middle = mapping.get('speed_mid')
        if middle is not None:
            middle = number(middle, f'Shot {index} midpoint speed', .25, 4)
        zoom_first = number(mapping.get('zoom_in'), f'Shot {index} starting scale', 100, 200)
        zoom_last = number(mapping.get('zoom_out'), f'Shot {index} ending scale', 100, 200)
        exposure = number(mapping.get('exposure'), f'Shot {index} exposure', -3, 3)
        contrast = number(mapping.get('contrast', 0), f'Shot {index} contrast', -25, 25)
        transition = mapping.get('transition', 'cut')
        if transition not in ('cut', 'dissolve', 'whip-left', 'whip-right'):
            raise ValueError(f'Choose a supported entrance transition for shot {index}.')
        transition_frames = mapping.get('transition_frames', 5) if transition != 'cut' else 0
        if transition != 'cut' and (
            type(transition_frames) is not int or not 2 <= transition_frames <= 12
            or transition_frames >= shot['end'] - shot['start'] or index == 1 or not source
        ):
            raise ValueError(f'Shot {index} needs a mapped entrance with 2–12 frames of transition time.')
        evidence = mapping.get('evidence', '')
        role = mapping.get('role', 'automatic')
        if not isinstance(role, str) or role not in SHOT_ROLES:
            raise ValueError(f'Choose a supported editorial role for shot {index}.')
        for suggested_shot, suggestion in zip(analysis['shots'], analysis['mappings']):
            if (suggested_shot['start'], suggested_shot['end']) == (shot['start'], shot['end']) and (
                suggestion.get('fallback') and transition == 'cut'
            ):
                notes.append(f'Shot {index}: {suggestion["fallback"]}')
                break
        if not isinstance(evidence, str) or len(evidence) > 600:
            raise ValueError(f'Shot {index} evidence must be at most 600 characters.')
        if (first != 1 or last != 1 or middle not in (None, 1) or zoom_first != 100
                or zoom_last != 100 or transition != 'cut') and not evidence.strip():
            raise ValueError(f'Enter a reference observation and timestamp for shot {index} retiming, scale or transition.')
        flash_frame = mapping.get('flash_frame')
        flash_opacity = number(mapping.get('flash_opacity', 30), f'Shot {index} flash opacity', 0, 100)
        if flash_frame is not None and (
            type(flash_frame) is not int or flash_frame not in {cue['frame'] for cue in shot['cues'] if cue['kind'] == 'brief luma spike'}
            or not shot['start'] <= flash_frame < shot['end']
        ):
            raise ValueError(f'Choose a measured luma spike inside shot {index} for a flash.')
        duration = (shot['end'] - shot['start']) / float(fps)
        end = start + duration * average_speed({'speed_in': first, 'speed_mid': middle, 'speed_out': last})
        if source and end > source['duration'] + 1e-7:
            raise ValueError(f'Shot {index} needs footage through {end:.3f} s. {source["name"]} ends at {source["duration"]:.3f} s.')
        if source and interpolation == 'sample' and min(first, last, middle if middle is not None else 4) * float(Fraction(source['rate'])) < float(fps):
            notes.append(f'Shot {index} uses frame sampling and may repeat frames in slowed regions.')
        if transition == 'dissolve':
            previous = edits[-1]
            end_handle = previous['source_out'] + transition_frames / float(fps) * previous['speed_out']
            if not previous['source'] or end_handle > previous['source']['duration'] + 1e-7:
                raise ValueError(f'Shot {index} dissolve needs {transition_frames} frames of extra footage after the previous trim. '
                                 'Choose another range or use a clean cut.')
        edits.append(shot | {'source': source, 'source_in': start, 'source_out': end, 'speed_in': first,
                            'speed_out': last, 'speed_mid': middle, 'zoom_in': zoom_first, 'zoom_out': zoom_last,
                            'exposure': exposure, 'contrast_adjustment': contrast, 'evidence': evidence, 'role': role,
                            'transition': transition, 'transition_frames': transition_frames,
                            'flash_frame': flash_frame, 'flash_opacity': flash_opacity})
        edit = edits[-1]
        edit['interpolation'] = interpolation
        if look_strength and source:
            ref_look = look_sample(reference, shot['start'] / float(fps), shot['end'] / float(fps))
            src_look = look_sample(source, start, end, tone_lut(edit))
            edit['managed_look'] = fit_look(ref_look, src_look, look_strength)
        count = shot['end'] - shot['start']
        step = count if first == last and middle in (None, first) else 1
        edit['time_map'] = [[frame, source_time(edit, frame / float(fps), duration)]
                            for frame in range(0, count + 1, step)]
    use_audio = payload.get('use_audio', False)
    if type(use_audio) is not bool or (use_audio and not analysis['has_audio']):
        raise ValueError('The requested reference soundtrack is unavailable.')
    recover_audio = payload.get('recover_audio', False)
    if type(recover_audio) is not bool or (recover_audio and not use_audio):
        raise ValueError('Choose and clear reference audio reuse before recovering estimated tracks.')
    audio_rights = payload.get('audio_rights', '')
    supplied = payload.get('audio_layers', [])
    if not isinstance(supplied, list) or len(supplied) > len(AUDIO_ROLES) or (use_audio and supplied):
        raise ValueError('Use either the reference mix or separately supplied audio layers.')
    if (use_audio or supplied) and (not isinstance(audio_rights, str) or not 4 <= len(audio_rights.strip()) <= 600):
        raise ValueError('Record the source and scope of your permission to reuse the audio.')
    layers = []
    for row in supplied:
        if not isinstance(row, dict) or row.get('role') not in AUDIO_ROLES:
            raise ValueError('Choose dialogue, music, effects or ambience for each audio source.')
        start = row.get('frame')
        if type(start) is not int or not 0 <= start < analysis['frame_count']:
            raise ValueError(f'Choose a start frame within the reel for {row["role"]}.')
        asset = asset_record(root, row.get('asset'))
        if Path(asset['path']).suffix not in AUDIO_TYPES:
            raise ValueError(f'Choose an audio file for {row["role"]}.')
        layers.append({'role': row['role'], 'frame': start, 'asset': asset})
    if len({row['role'] for row in layers}) != len(layers) or len({row['asset']['sha256'] for row in layers}) != len(layers):
        raise ValueError('Choose one distinct audio file for each role.')
    if look_strength:
        notes.append('Managed SDR look uses supported Rec.709, sRGB and SD tags. Unspecified tags assume Rec.709. '
                     'After Effects keeps editable source balance; the Resolve package holds the fitted look separately.')
    notes.append('Vocal estimate and backing residual are editable. Clean independent original stems cannot be recovered from this mix.' if recover_audio else
                 'The opt-in reference mix stays together on its own audio layer.' if use_audio else
                 'Supplied audio stays on separate editable tracks.' if supplied else
                 'The timeline is silent. Reference soundtrack reuse is opt-in and replacement camera audio is muted.')
    return {'version': 1, 'analysis': analysis['id'], 'fps': str(fps), 'fps_number': float(fps),
            'frame_count': analysis['frame_count'], 'width': analysis['width'], 'height': analysis['height'],
            'reference': {key: reference[key] for key in ('name', 'sha256', 'origin', 'audio_offset', 'time_base', 'color_metadata')},
            'shots': edits, 'onsets': analysis['onsets'], 'periodic_cues': analysis.get('periodic_cues'),
            'text_review': analysis.get('text_review'),
            'unresolved': notes, 'use_audio': use_audio,
            'anchors': [{'type': 'cut', 'frame': shot['start']} for shot in edits] +
                       [{'type': 'audio onset candidate', 'frame': onset['frame']} for onset in analysis['onsets']],
            'audio_rights': audio_rights if use_audio or supplied else '', 'supplied_audio': layers,
            'recover_audio': recover_audio, 'look_strength': look_strength, 'interpolation': interpolation,
            'preview_only': any(not edit['source'] for edit in edits)}


def source_time(shot, time, duration):
    middle = shot['speed_mid']
    if middle is not None:
        half = duration / 2
        if time > half:
            rest = time - half
            return shot['source_in'] + half * (shot['speed_in'] + middle) / 2 + rest * (
                middle + .5 * (shot['speed_out'] - middle) * rest / half)
        return shot['source_in'] + time * (shot['speed_in'] + .5 * (middle - shot['speed_in']) * time / half)
    return shot['source_in'] + time * (shot['speed_in'] + .5 * (shot['speed_out'] - shot['speed_in']) * time / duration)


def picture_frames(shot, fps, stats=None):
    source = shot['source']
    with av.open(source['path']) as media:
        stream = media.streams.video[0]
        if shot['source_in'] > 1:
            seek = max(0., source['origin'] + shot['source_in'] - 1)
            media.seek(int(seek / float(stream.time_base)), stream=stream)
        decoded = iter(media.decode(stream))
        current = next(decoded, None)
        if current is None:
            raise ValueError(f'No video decoded from {source["name"]}.')
        following = next(decoded, None)
        count = shot['end'] - shot['start']
        image = pair = following_image = grid = None
        optical = shot.get('interpolation') == 'optical'
        source_cuts = set(source.get('scene_times', ()))
        def picture(frame):
            scale = min(1., 1280 / max(frame.width, frame.height)) if optical else 1.
            pixels = rgb(frame, max(2, round(frame.width * scale)), max(2, round(frame.height * scale)))
            rotation = getattr(frame, 'rotation', 0)
            return np.ascontiguousarray(np.rot90(pixels, round(rotation / 90))) if rotation else pixels
        for index in range(count):
            time = source['origin'] + source_time(shot, index / fps, count / fps)
            while following is not None and following.time <= time + 1e-7:
                current, following = following, next(decoded, None)
                image, following_image, pair = following_image, None, None
            if current.time > time + 1e-6:
                raise ValueError(f'The selected start is unavailable in {source["name"]}.')
            if image is None:
                image = picture(current)
            if optical and following is not None and time > current.time + 1e-6 and (
                following.time - source['origin'] < shot['source_out'] + 1e-7
                and 0 < following.time - current.time <= .125
            ):
                if following_image is None:
                    following_image = picture(following)
                    at_cut = following.time - source['origin'] in source_cuts
                    pair = flow_pair(image, following_image) if image.shape == following_image.shape and not at_cut else None
                    if grid is None or grid[0].shape != image.shape[:2]:
                        grid = np.meshgrid(np.arange(image.shape[1], dtype=np.float32),
                                           np.arange(image.shape[0], dtype=np.float32))
                if pair is not None:
                    if stats is not None:
                        stats['generated'] += 1
                    yield interpolate(image, following_image, pair, (time-current.time)/(following.time-current.time), grid)
                    continue
                if stats is not None:
                    stats['rejected_pairs'] += 1
            yield image


def render_shot(shot, rate_value, width, height, target, previous, managed=False, *, device="cpu"):
    from hinglish_cut.compute_policy import h264_profile
    fps = float(rate_value)
    stats = {'generated': 0, 'rejected_pairs': 0}
    with av.open(str(target), 'w', options={'movflags': '+faststart'}) as output:
        codec, options = h264_profile(device, 19) if device == 'cuda' else (
            'libx264', {'preset': 'veryfast', 'crf': '19', 'threads': '2'})
        stream = output.add_stream(codec, rate=rate_value, options=options)
        stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
        if managed:
            stream.codec_context.colorspace = 1
            stream.codec_context.color_primaries = 1
            stream.codec_context.color_trc = 1
            stream.codec_context.color_range = 1
        duration_frames = shot['end'] - shot['start']
        lut = tone_lut(shot)
        tail = None
        if shot['transition'] == 'dissolve':
            tail_shot = previous | {'start': 0, 'end': shot['transition_frames'], 'source_in': previous['source_out'],
                                    'speed_in': previous['speed_out'], 'speed_mid': None,
                                    'zoom_in': previous['zoom_out'], 'flash_frame': None,
                                    'source_out': previous['source_out'] + shot['transition_frames'] / fps * previous['speed_out']}
            tail = picture_frames(tail_shot, fps, stats)
        pictures = picture_frames(shot, fps, stats) if shot['source'] else [None] * duration_frames
        for index, image in enumerate(pictures):
            canvas = np.zeros((height, width, 3), dtype=np.uint8)
            if image is None:
                canvas[:] = (65, 24, 24)
                cv2.putText(canvas, 'Unmapped shot', (12, height // 2), cv2.FONT_HERSHEY_SIMPLEX,
                            min(width / 360, 1), (255, 255, 255), 2, cv2.LINE_AA)
            else:
                delta = 0.
                if shot['transition'].startswith('whip') and index < shot['transition_frames']:
                    delta = .08 * (1 - index / shot['transition_frames'])
                    if shot['transition'] == 'whip-left':
                        delta = -delta
                paint_shot(canvas, image, lut, shot, index, duration_frames, delta)
                if delta:
                    blur = max(3, (round(abs(delta) * width / 6) // 2) * 2 + 1)
                    canvas[:] = cv2.blur(canvas, (blur, 1))
                if tail is not None and index < shot['transition_frames']:
                    outgoing = np.zeros_like(canvas)
                    paint_shot(outgoing, next(tail), tone_lut(previous), tail_shot, index, shot['transition_frames'])
                    opacity = index / shot['transition_frames']
                    canvas[:] = cv2.addWeighted(outgoing, 1 - opacity, canvas, opacity, 0)
            frame = av.VideoFrame.from_ndarray(canvas, format='rgb24')
            if managed:
                frame = frame.reformat(format='yuv420p', dst_colorspace='ITU709',
                                       dst_color_range='MPEG', dst_color_primaries=1, dst_color_trc=1)
            frame.pts = index
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return stats


def tone_lut(shot):
    expanded = np.arange(256) * 2**shot['exposure']
    contrast = 1 + shot['contrast_adjustment'] / 100
    return np.clip((expanded - 127.5) * contrast + 127.5, 0, 255).astype('uint8')


def render_preview(plan, folder, audio, *, device="cpu"):
    frame_rate = Fraction(plan['fps'])
    scale = min(1., 960 / max(plan['width'], plan['height']))
    width, height = (max(2, round(plan[axis] * scale / 2) * 2) for axis in ('width', 'height'))
    cache = folder.parent.parent / 'picture-cache'
    cache.mkdir(exist_ok=True)
    parts = []
    reused = 0
    for index, shot in enumerate(plan['shots'], 1):
        source = shot['source']
        previous = plan['shots'][index - 2] if index > 1 else None
        identity = {
            'renderer': 6 if plan['look_strength'] else 5, 'device': device,
            'fps': plan['fps'], 'size': [width, height], 'time_map': shot['time_map'],
            'sha256': source['sha256'] if source else None, 'exposure': shot['exposure'],
            'contrast': shot['contrast_adjustment'], 'transition': [shot['transition'], shot['transition_frames']],
            'scale': [shot['zoom_in'], shot['zoom_out']],
            'interpolation': shot['interpolation'], 'look': shot.get('managed_look'), 'managed': bool(plan['look_strength']),
            'flash': [shot['flash_frame'] - shot['start'], shot['flash_opacity']] if shot['flash_frame'] is not None else None,
        }
        if shot['transition'] == 'dissolve':
            identity['dissolve_from'] = [previous['source']['sha256'], previous['source_out'], previous['speed_out'],
                                         previous['zoom_out'], previous['exposure'], previous['contrast_adjustment'],
                                         previous.get('managed_look'), previous['interpolation']]
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        cached = cache / (key + '.mp4')
        metrics = cache / (key + '.json')
        if cached.is_file() and metrics.is_file():
            reused += 1
        else:
            partial = cache / (key + '.partial.mp4')
            try:
                stats = render_shot(shot, frame_rate, width, height, partial, previous,
                                    bool(plan['look_strength']), device=device)
                with av.open(str(partial)) as check:
                    if sum(1 for _ in check.decode(video=0)) != shot['end'] - shot['start']:
                        raise RuntimeError(f'Shot {index} preview has the wrong frame count.')
                partial.replace(cached)
                save_json(metrics, stats)
            finally:
                partial.unlink(missing_ok=True)
        shot['optical_flow'] = read_json(metrics)
        target = folder / f'shot-{index:03}.mp4'
        try:
            os.link(cached, target)
        except OSError:
            shutil.copyfile(cached, target)
        parts.append(target)
    picture = folder / 'picture.mp4'
    with av.open(str(picture), 'w', options={'movflags': '+faststart'}) as output:
        target = None
        for shot, path in zip(plan['shots'], parts):
            with av.open(str(path)) as media:
                stream = media.streams.video[0]
                if target is None:
                    target = output.add_stream_from_template(stream)
                    target.time_base = stream.time_base
                offset = round(Fraction(shot['start']) / frame_rate / stream.time_base)
                for packet in media.demux(stream):
                    if packet.dts is None:
                        continue
                    packet.pts += offset
                    packet.dts += offset
                    packet.stream = target
                    output.mux(packet)
    preview = folder / 'preview.mp4'
    if audio:
        run_ffmpeg(['-i', picture, '-i', audio, '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k',
                    '-c:v', 'copy', '-movflags', '+faststart', preview], folder, threading.Event())
        picture.unlink()
    else:
        picture.rename(preview)
    with av.open(str(preview)) as check:
        timestamps = [frame.time for frame in check.decode(video=0)]
        if len(timestamps) != plan['frame_count'] or any(
            abs(timestamp - index / float(frame_rate)) > .0001 for index, timestamp in enumerate(timestamps)
        ):
            raise RuntimeError('The preview frame count did not match the timeline.')
    with preview.open('rb') as stream:
        fingerprint = hashlib.file_digest(stream, 'sha256').hexdigest()
    plan['render'] = {'width': width, 'height': height, 'reused_shots': reused,
                      'renderer': 'PyAV + FFmpeg', 'device': device, 'preview_sha256': fingerprint}
    return parts


def paint_shot(canvas, image, lut, shot, index, duration_frames, shift=0.):
    height, width = canvas.shape[:2]
    zoom = (shot['zoom_in'] + (shot['zoom_out'] - shot['zoom_in']) * index / duration_frames) / 100
    factor = min(width / image.shape[1], height / image.shape[0]) * zoom * (1 + 2 * abs(shift))
    w, h = max(1, round(image.shape[1] * factor)), max(1, round(image.shape[0] * factor))
    pixels = cv2.resize(image, (w, h), interpolation=cv2.INTER_LINEAR)
    if shot.get('managed_look'):
        normalized = display_rgb(pixels, shot['source']['color_metadata'])
        balanced = lut[np.rint(normalized * 255).astype(np.uint8)].astype(np.float32) / 255
        pixels = np.rint(apply_look(balanced, shot['managed_look']) * 255).astype('uint8')
    else:
        pixels = cv2.LUT(pixels, lut)
    x, y = (width - w) // 2 + round(width * shift), (height - h) // 2
    a, b = max(0, x), max(0, y)
    c, d = min(width, x + w), min(height, y + h)
    canvas[b:d, a:c] = pixels[b-y:d-y, a-x:c-x]
    if shot['start'] + index == shot['flash_frame']:
        alpha = shot['flash_opacity'] / 100
        canvas[:] = np.rint(canvas * (1 - alpha) + 255 * alpha).astype(np.uint8)


def comparison(plan, reference, folder, *, device="cpu"):
    from hinglish_cut.compute_policy import ffmpeg_h264
    height = 480
    width = max(2, min(854, round(height * plan['width'] / plan['height'] / 2) * 2))
    fit = f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    frames, fps = plan['frame_count'], plan['fps']
    align = f'setpts=PTS-STARTPTS,fps={fps},{fit},tpad=stop_mode=clone:stop_duration=1,trim=end_frame={frames}'
    filters = f'[0:v]{align}[ref];[1:v]{align}[draft];[ref][draft]hstack=shortest=1'
    encoder = ffmpeg_h264(device, 20) if device == 'cuda' else [
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20']
    run_ffmpeg(['-i', reference, '-i', folder / 'preview.mp4', '-filter_complex_threads', 1,
                '-filter_complex', filters, '-map', '1:a:0?', *encoder,
                '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart',
                folder / 'comparison.mp4'], folder, threading.Event())
    sample_indices = sorted({max(0, shot['start'] + offset) for shot in plan['shots'][:12] for offset in (-1, 0)})
    stills = []
    with av.open(str(folder / 'comparison.mp4')) as check:
        count = 0
        for index, frame in enumerate(check.decode(video=0)):
            count = index + 1
            if index in sample_indices:
                still = frame.to_ndarray(format='bgr24')
                resized = cv2.resize(still, (350, max(96, round(350 * height / (2 * width)))))
                label = np.zeros((28, 350, 3), dtype=np.uint8)
                cv2.putText(label, f'Frame {index} | reference / draft', (8, 18), cv2.FONT_HERSHEY_SIMPLEX,
                            .45, (240, 240, 240), 1, cv2.LINE_AA)
                stills.append(np.vstack([label, resized]))
        if count != frames:
            raise RuntimeError('The comparison frame count did not match the timeline.')
    columns = min(3, len(stills))
    rows = math.ceil(len(stills) / columns)
    tile_height = stills[0].shape[0]
    sheet = np.zeros((rows * tile_height, columns * 350, 3), dtype=np.uint8)
    for index, still in enumerate(stills):
        row, column = divmod(index, columns)
        sheet[row*tile_height:(row+1)*tile_height, column*350:(column+1)*350] = still
    ok, jpeg = cv2.imencode('.jpg', sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError('The cut contact sheet could not be encoded.')
    (folder / 'comparison-frames.jpg').write_bytes(jpeg.tobytes())


def premiere_xml(plan, folder, parts):
    root = ET.Element('xmeml', version='5')
    sequence = add(root, 'sequence', id='reference-reel')
    add(sequence, 'name', 'Storylens Reference Reel' + (' - Review' if plan['preview_only'] else ''))
    add(sequence, 'duration', plan['frame_count'])
    rate(sequence, plan['fps'])
    media = add(sequence, 'media')
    video = add(media, 'video')
    dims = (plan['render']['width'], plan['render']['height'], plan['fps'])
    video_format_dimensions(add(add(video, 'format'), 'samplecharacteristics'), *dims)
    track = add(video, 'track')
    for index, (shot, path) in enumerate(zip(plan['shots'], parts), 1):
        item = add(track, 'clipitem', id=f'video-{index}')
        source = shot['source']
        name = source['name'] + ' | ' + source['sha256'][:12] if source else 'Unmapped'
        add(item, 'name', f'Shot {index} | {name}')
        add(item, 'enabled', 'TRUE')
        rate(item, plan['fps'])
        length = shot['end'] - shot['start']
        for field, value in [('start', shot['start']), ('end', shot['end']), ('in', 0), ('out', length)]:
            add(item, field, value)
        file = add(item, 'file', id=f'shot-{index}')
        add(file, 'name', path.name)
        add(file, 'pathurl', premiere_pathurl(path))
        rate(file, plan['fps'])
        add(file, 'duration', length)
        attributes = add(add(add(file, 'media'), 'video'), 'samplecharacteristics')
        video_format_dimensions(attributes, *dims)
    if plan['audio_tracks']:
        sound = add(media, 'audio')
        add(sound, 'numOutputChannels', 2)
        format_attributes = add(add(sound, 'format'), 'samplecharacteristics')
        add(format_attributes, 'depth', 24)
        add(format_attributes, 'samplerate', 48000)
        outputs = add(sound, 'outputs')
        for channel in (1, 2):
            group = add(outputs, 'group')
            add(group, 'index', channel)
            add(group, 'numchannels', 1)
            add(group, 'downmix', 0)
            add(add(group, 'channel'), 'index', channel)
        frames = plan['frame_count']
        ticks = round(frames * 254016000000 / Fraction(plan['fps']))
        for index, layer in enumerate(plan['audio_tracks'], 1):
            # Premiere's own XML writes each stereo track as a linked L/R pair.
            for channel in (1, 2):
                track = add(sound, 'track', premiereTrackType='Stereo',
                            currentExplodedTrackIndex=str(channel - 1), totalExplodedTrackCount='2')
                clip = add(track, 'clipitem', id=f'audio-{index}-{channel}', premiereChannelType='stereo')
                add(clip, 'masterclipid', f'master-audio-{index}')
                add(clip, 'name', layer['name'])
                add(clip, 'enabled', 'TRUE')
                rate(clip, plan['fps'])
                add(clip, 'duration', frames)
                for field, value in [('start', 0), ('end', frames), ('in', 0), ('out', frames)]:
                    add(clip, field, value)
                add(clip, 'pproTicksIn', 0)
                add(clip, 'pproTicksOut', ticks)
                file = add(clip, 'file', id=f'audio-file-{index}')
                if channel == 1:
                    add(file, 'name', Path(layer['path']).name)
                    add(file, 'pathurl', premiere_pathurl(layer['path']))
                    rate(file, plan['fps'])
                    add(file, 'duration', frames)
                    audio = add(add(file, 'media'), 'audio')
                    attributes = add(audio, 'samplecharacteristics')
                    add(attributes, 'depth', 32 if plan['recover_audio'] else 16)
                    add(attributes, 'samplerate', 48000)
                    add(audio, 'channelcount', 2)
                source = add(clip, 'sourcetrack')
                add(source, 'mediatype', 'audio')
                add(source, 'trackindex', channel)
                for linked in (1, 2):
                    link = add(clip, 'link')
                    add(link, 'linkclipref', f'audio-{index}-{linked}')
                    add(link, 'mediatype', 'audio')
                    add(link, 'trackindex', 2 * (index - 1) + linked)
                    add(link, 'clipindex', 1)
                    add(link, 'groupindex', 1)
                add(track, 'enabled', 'TRUE')
                add(track, 'locked', 'FALSE')
                add(track, 'outputchannelindex', channel)
    for event in plan['onsets']:
        marker = add(sequence, 'marker')
        add(marker, 'name', 'Reference audio onset')
        add(marker, 'in', event['frame'])
        add(marker, 'out', -1)
    ET.indent(root, space='  ')
    (folder / 'REFERENCE_REEL.xml').write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))


def reports(folder, plan, analysis, job_id):
    edits = plan['shots']
    substitutions = []
    for index, shot in enumerate(edits, 1):
        source = shot['source']
        substitutions.append({'slot': index, 'reference_frames': [shot['start'], shot['end']],
                              'status': 'substitute' if source else 'unresolved', 'editorial_role': shot['role'],
                              'source': source['name'] if source else None,
                              'sha256': source['sha256'] if source else None,
                              'source_seconds': [shot['source_in'], shot['source_out']] if source else None,
                              'alternatives': next((mapping['alternatives'] for anchor, mapping in
                                                   zip(analysis['shots'], analysis['mappings'])
                                                   if (anchor['start'], anchor['end']) == (shot['start'], shot['end'])), [])})
    save_json(folder / 'substitutions.json', substitutions)
    save_json(folder / 'assets-and-rights.json', {
        'reference': plan['reference'],
        'source_assets': analysis['footage'],
        'distribution': 'Local reconstruction review',
        'audio': {'policy': 'user supplied reuse statement' if plan['audio_tracks'] else 'excluded',
                  'permission_statement': plan['audio_rights'],
                  'type': ('Vocal estimate plus backing residual' if plan['recover_audio'] else
                           'Reference mix' if plan['use_audio'] else 'User-supplied audio layers'),
                  'recovery': plan.get('audio_recovery'),
                  'supplied_sources': plan['supplied_audio']},
    })
    report_rows = [
        ('Cut timing', 'Exact to reviewed grid', f'{len(edits)} slots, {plan["frame_count"]} frames; source PTS quantized to {plan["fps"]} fps.'),
        ('Speed', 'Approximate', 'Editable speed curve. '
         f'{sum(shot["optical_flow"]["generated"] for shot in edits)} motion-interpolated samples, '
         f'{sum(shot["optical_flow"]["rejected_pairs"] for shot in edits)} rejected samples used frame sampling.'),
        ('Framing and transitions', 'Approximate', 'Editable zoom, flashes, dissolves and directional whips where selected.'),
        ('Grade', 'Approximate', 'Normalized SDR look exported for Resolve; native source balance remains separate.'
         if plan['look_strength'] else 'Shot exposure and contrast compensation.'),
        ('Text and unsupported effects', 'Unresolved', 'No inferred text or unverified transitions are added.'),
        ('Audio', 'Estimated tracks' if plan['recover_audio'] else 'Reference mix' if plan['use_audio']
         else 'Supplied layers' if plan['audio_tracks'] else 'Excluded',
         'Onset markers are candidates. Roles in the reference mix remain unresolved.'),
        ('Replacement media', 'Substitute', f'{sum(edit["source"] is not None for edit in edits)} assigned; '
         f'{sum(edit["source"] is None for edit in edits)} review placeholders.'),
    ]
    rows = ''.join('<tr>' + ''.join(f'<td>{escape(cell)}</td>' for cell in row) + '</tr>' for row in report_rows)
    (folder / 'fidelity-report.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Reference Reel fidelity</title>'
        '<style>body{font:16px system-ui;margin:2em;max-width:70em}td,th{padding:.65em;text-align:left;'
        'border-bottom:1px solid #ccc}table{border-collapse:collapse}</style>'
        f'<h1>Reference Reel fidelity</h1><p>{escape(plan["reference"]["name"])} · {job_id}</p>'
        '<p>Comparison video shows reference on the left and reconstruction on the right.</p>'
        '<table><thead><tr><th>Element</th><th>Result</th><th>Evidence</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></html>', 'utf-8')


def saved_recipe(plan, analysis, job_id):
    omitted = {'id', 'footage', 'mappings', 'shots'}
    clock = {key: value for key, value in analysis.items() if key not in omitted}
    measured = ('start', 'end', 'source_frame', 'cues', 'signature', 'retime_hint', 'luma', 'contrast', 'motion')
    clock['shots'] = [{key: shot[key] for key in measured} for shot in plan['shots']]
    for target, shot in zip(clock['shots'], plan['shots']):
        if 'semantic' in shot:
            target['semantic'] = shot['semantic']
    controls = ('speed_in', 'speed_mid', 'speed_out', 'zoom_in', 'zoom_out', 'evidence', 'role',
                'flash_frame', 'flash_opacity', 'transition', 'transition_frames')
    return {'id': job_id, 'version': 1, 'parent': analysis.get('recipe_parent'),
            'created_utc': datetime.now(timezone.utc).isoformat(), 'source_analysis': analysis['id'],
            'reference_clock': clock, 'audio_policy': 'Fresh permission required for every reconstruction',
            'render_preferences': {'interpolation': plan['interpolation'], 'look_strength': plan['look_strength']},
            'slots': [{'start': shot['start'], 'end': shot['end'], 'controls': {key: shot[key] for key in controls}}
                      for shot in plan['shots']]}


def prepare_audio(plan, reference, folder, engine_root):
    length = plan['frame_count'] / plan['fps_number']
    tracks = []
    inputs = [(item['role'], item['asset']['path'], item['frame'] / plan['fps_number']) for item in plan['supplied_audio']]
    if plan['use_audio']:
        inputs = [('Reference soundtrack', reference['path'], plan['reference']['audio_offset'])]
    for role, path, offset in inputs:
        target = folder / f'audio-{len(tracks) + 1:02}.wav'
        filters = (f'asetpts=PTS-STARTPTS+({offset:.9f})/TB,aresample=48000:async=1:first_pts=0,'
                   f'apad,volume={1 / len(inputs):.8f}')
        run_ffmpeg(['-i', path, '-map', '0:a:0', '-vn', '-af', filters, '-t', f'{length:.9f}',
                    '-ac', '2', '-c:a', 'pcm_s16le', target], folder, threading.Event())
        with av.open(str(target)) as check:
            if abs(sum(f.samples for f in check.decode(audio=0)) / 48000 - length) > .002:
                raise RuntimeError(f'The {role} track duration did not match the timeline.')
        tracks.append({'name': role.title(), 'path': str(target)})
    plan['audio_tracks'] = tracks
    if plan['recover_audio']:
        mix = Path(tracks[0]['path'])
        plan['audio_tracks'], plan['audio_recovery'] = separate_reference(engine_root, mix, folder)
        return mix
    if len(tracks) < 2:
        return Path(tracks[0]['path']) if tracks else None
    args = [item for track in tracks for item in ('-i', track['path'])]
    mix = folder / 'soundtrack-mix.wav'
    run_ffmpeg([*args, '-filter_complex', f'amix=inputs={len(tracks)}:duration=first:normalize=0',
                '-c:a', 'pcm_s16le', mix], folder, threading.Event())
    return mix


def export(root, analysis, payload, engine_root=None):
    from contextlib import nullcontext
    from hinglish_cut.compute_policy import heavy_device
    from hinglish_cut.gpu_lock import gpu_lock

    device = heavy_device(engine_root or root)
    plan = build_plan(root, analysis, payload)
    job_id = uuid.uuid4().hex
    folder = directory(root, job_id, 'jobs')
    folder.mkdir(parents=True)
    try:
        reference = read_json(directory(root, analysis['id'], 'analyses') / 'frames.json')
        reference.update(asset_record(root, analysis['reference_id']))
        audio = prepare_audio(plan, reference, folder, engine_root or root)
        plan['recipe'] = job_id
        with gpu_lock(engine_root or root) if device == 'cuda' else nullcontext():
            parts = render_preview(plan, folder, audio, device=device)
            comparison(plan, reference['path'], folder, device=device)
        premiere_xml(plan, folder, parts)
        reports(folder, plan, analysis, job_id)
        if plan['look_strength']:
            from zipfile import ZipFile, ZIP_DEFLATED
            with ZipFile(folder / 'resolve-look.zip', 'w', compression=ZIP_DEFLATED) as package:
                package.writestr('README.txt', 'Rec.709 SDR look approximations by shot. Normalize to Rec.709 SDR '
                                 'and apply the shot exposure and contrast from plan.json before the matching LUT. '
                                 'Compare at matching reference frames and keep the native grade structure.\n')
                for index, shot in enumerate(plan['shots'], 1):
                    if shot.get('managed_look'):
                        lut_path = folder / f'shot-{index:03}.cube'
                        color_lut(shot, lut_path)
                        package.write(lut_path, lut_path.name)
                        if index <= 24:
                            seconds = (shot['start'] + shot['end']) / (2 * plan['fps_number'])
                            package.writestr(f'reference-shot-{index:03}.jpg', reference_still(reference, seconds))
        manifest = json.dumps(plan, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
        template = Path(__file__).with_name('reference_reel_ae.jsx').read_text('utf-8')
        (folder / 'reference-reel.jsx').write_text(template.replace('__REFERENCE_REEL_PLAN__', manifest, 1), 'utf-8')
        recipe = saved_recipe(plan, analysis, job_id)
        recipe_dir = directory(root, job_id, 'recipes')
        recipe_dir.mkdir(parents=True)
        save_json(recipe_dir / 'recipe.json', recipe)
        save_json(folder / 'recipe.json', recipe)
        reference['path'] = ''
        save_json(folder / 'reference-analysis.json', {'review': analysis, 'decoded_reference': reference})
        save_json(folder / 'plan.json', plan)
        return {'id': job_id, 'recipe': job_id, 'files': [name for name in FILES if (folder / name).is_file()],
                'preview_only': plan['preview_only'], 'unresolved': plan['unresolved']}
    except BaseException:
        shutil.rmtree(folder)
        raise


def post(handler, state, parsed):
    from urllib.parse import parse_qs
    if parsed.path == '/api/reference-reel/upload':
        name = parse_qs(parsed.query).get('name', [''])[0]
        length = int(handler.headers.get('Content-Length', '0'))
        return handler._json(201, upload(state.root, name, handler.rfile, length))
    if parsed.path not in ('/api/reference-reel/analyze', '/api/reference-reel/reuse',
                           '/api/reference-reel/recut', '/api/reference-reel/export'):
        return handler._json(404, {'error': 'Unknown Reference Reel operation.'})
    size = int(handler.headers.get('Content-Length', '0'))
    if not 0 < size <= 1024**2:
        raise ValueError('Invalid Reference Reel request size.')
    payload = json.loads(handler.rfile.read(size))
    if not isinstance(payload, dict):
        raise ValueError('Send a Reference Reel request object.')
    if not LOCK.acquire(blocking=False):
        return handler._json(409, {'error': 'Reference Reel is busy. Wait for the active analysis or export to finish.'})
    try:
        if parsed.path.endswith('/analyze'):
            return handler._json(201, analyze(state.root, payload))
        if parsed.path.endswith('/reuse'):
            return handler._json(201, reuse(state.root, payload))
        folder = directory(state.root, payload.get('analysis'), 'analyses')
        analysis = read_json(folder / 'analysis.json')
        if parsed.path.endswith('/recut'):
            shots, _ = recut(state.root, analysis, payload.get('cuts'))
            mappings = suggest(shots, read_json(folder / 'footage-frames.json'), float(Fraction(analysis['fps'])))
            return handler._json(200, {'shots': shots, 'mappings': mappings})
        return handler._json(201, export(state.root, analysis, payload, getattr(state, 'engine_root', None)))
    except av.FFmpegError as error:
        raise ValueError(f'A video could not be decoded or encoded: {error}') from error
    finally:
        LOCK.release()


def get(handler, state, parsed):
    parts = parsed.path.split('/')
    if len(parts) == 6 and parts[3] == 'assets' and parts[5] == 'video':
        path = Path(asset_record(state.root, parts[4])['path'])
        types = {'.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm'}
        if path.suffix not in VIDEO_TYPES:
            return handler._json(404, {'error': 'This asset is not a video.'})
        return send_file(handler, path, types.get(path.suffix, 'application/octet-stream'))
    if len(parts) != 6 or parts[3] != 'jobs' or parts[5] not in FILES:
        return handler._json(404, {'error': 'Unknown Reference Reel output.'})
    folder = directory(state.root, parts[4], 'jobs')
    path = (folder / parts[5]).resolve()
    if path.parent != folder or not path.is_file() or not (folder / 'plan.json').is_file():
        return handler._json(404, {'error': 'The requested Reference Reel export is unavailable.'})
    return send_file(handler, path, FILES[path.name])


def send_file(handler, path, content_type):
    handler.send_response(200)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(path.stat().st_size))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    with path.open('rb') as content:
        shutil.copyfileobj(content, handler.wfile)
