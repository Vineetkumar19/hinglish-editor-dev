"""Deterministic source-clock and cut-boundary evidence for Match Cut Finder."""

from bisect import bisect_left
from fractions import Fraction
import gzip
import json
import math
import os
from pathlib import Path
from uuid import uuid4

import av
import cv2
import numpy as np

from hinglish_cut.media import video_rotation
from .curation import digest
from .footage import inspect


ANALYZER = 'match-boundaries-v4'
CALIBRATION = 'scene-handoff-v1'
WEIGHTS = dict(motion=.72, composition=.16, shape=.07, cleanliness=.05)
MIN_SCORE = .59
NEIGHBORS = 16
CELL = (np.arange(64)[:, None] // 16 * 4 + np.arange(96)[None, :] // 24) * 8
TILE_INDEX = (CELL // 8).ravel()
YY, XX = np.mgrid[:64, :96].astype(np.float32)


def check_stop(stop):
    if stop.is_set():
        raise InterruptedError('Match Cut Finder stopped. Verified exports are kept.')


def unit(values):
    values = np.asarray(values, dtype=np.float32)
    return values / max(1e-6, np.linalg.norm(values))


def probe(path):
    with av.open(str(path)) as media:
        if not media.streams.video:
            raise ValueError('No readable video track.')
        stream = media.streams.video[0]
        codec = stream.codec_context
        time_base = str(stream.time_base)
        origin = float(Fraction(media.start_time or 0, av.time_base))
        sar = Fraction(stream.sample_aspect_ratio or 1)
        aspect = float(stream.width * sar / stream.height)
        rotation = video_rotation(path)
        if rotation % 180:
            aspect = 1 / aspect
        return {'time_base': time_base, 'container_origin': origin, 'rotation': rotation,
                'width': stream.width, 'height': stream.height, 'sar': str(sar), 'aspect': aspect,
                'color': {key: str(getattr(codec, key)) for key in
                          ('color_range', 'colorspace', 'color_primaries', 'color_trc')},
                'audio_channels': media.streams.audio[0].codec_context.channels if media.streams.audio else 0}


class Samples:
    def __init__(self):
        self.ticks = []
        self.times = []
        self.rows = []
        self.previous = None
        self.last_duration = 0

    def clock(self, frame):
        if frame.pts is None or (self.ticks and frame.pts <= self.ticks[-1]):
            raise ValueError('Source has missing or non-increasing presentation timestamps.')
        self.ticks.append(frame.pts)
        self.last_duration = frame.duration or 0

    def sample(self, seconds, pixels):
        pixels = cv2.resize(pixels, (96, 64), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
        x = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
        y = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        magnitude, angles = cv2.cartToPolar(x, y, angleInDegrees=True)
        strength = np.clip(magnitude, 0, 255)
        edge = cv2.resize(np.sqrt(strength), (8, 6), interpolation=cv2.INTER_AREA)
        luma = cv2.resize(gray, (8, 6), interpolation=cv2.INTER_AREA).astype(np.float32)
        composition = np.concatenate((unit((edge - edge.mean()).ravel()),
                                      unit((luma - luma.mean()).ravel()))) / math.sqrt(2)
        hog = np.bincount((CELL + (angles % 180 / 22.5).astype(np.int32)).ravel(),
                          weights=strength.ravel(), minlength=128).reshape(16, 8)
        hog = np.sqrt(hog)
        shape = unit((hog - hog.mean(axis=0)).ravel())
        # Keep local structure before whole-frame normalization. The
        # camera-compensated motion window determines which tiles matter.
        local_luma = cv2.resize(gray, (12, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
        local_luma = local_luma.reshape(4, 3, 4, 3).transpose(0, 2, 1, 3).reshape(16, 9)
        local_luma -= local_luma.mean(axis=1, keepdims=True)
        local_pose = np.concatenate((local_luma / np.maximum(1, np.linalg.norm(local_luma, axis=1, keepdims=True)),
                                     hog / np.maximum(1, np.linalg.norm(hog, axis=1, keepdims=True))), axis=1)
        hsv = cv2.cvtColor(pixels, cv2.COLOR_RGB2HSV)
        appearance = unit(np.sqrt(cv2.calcHist([hsv], [0, 1, 2], None, [8, 3, 3],
                                               [0, 180, 0, 256, 0, 256]).ravel()))

        motion = np.zeros(10, dtype=np.float32)
        speed = confidence = shake = camera_support = 0.
        camera = np.zeros(2, dtype=np.float32)
        movement = np.zeros(2, dtype=np.float32)
        focus = strength * strength
        motion_tiles = np.zeros(16, dtype=np.float32)
        if self.previous is not None:
            flow = cv2.calcOpticalFlowFarneback(self.previous, gray, None, .5, 3, 13, 2, 5, 1.1, 0)
            camera = np.median(flow.reshape(-1, 2), axis=0)
            residual = flow - camera
            textured = strength > 35
            if textured.any():
                stable = np.linalg.norm(residual[textured], axis=1) <= max(.45, .5 * np.linalg.norm(camera))
                camera_support = float(stable.mean()) * min(1., float(textured.mean()) * 6)
            lengths, directions = cv2.cartToPolar(residual[..., 0], residual[..., 1], angleInDegrees=True)
            lengths = np.clip(np.nan_to_num(lengths, posinf=0), 0, 20)
            reliable = (strength > 35) & (lengths > .3)
            weights = lengths * reliable
            motion_tiles = np.bincount(TILE_INDEX, weights=weights.ravel(), minlength=16)
            speed = float(weights.sum() / max(1, np.count_nonzero(strength > 35)))
            confidence = min(1., float(reliable.mean()) * 12) * min(1., speed / .8)
            flow_bins = (np.nan_to_num(directions) % 360 / 45).astype(np.int32)
            motion[:8] = unit(np.bincount(flow_bins.ravel(), weights=weights.ravel(), minlength=8))
            if weights.sum() > 0:
                movement = np.sum(residual * weights[..., None], axis=(0, 1)) / weights.sum()
                cx = float((XX * weights).sum() / weights.sum())
                cy = float((YY * weights).sum() / weights.sum())
                radius = np.hypot(XX - cx, YY - cy)
                angular = ((XX - cx) * residual[..., 1] - (YY - cy) * residual[..., 0]) / np.maximum(1, radius * lengths)
                spin = float(np.clip((angular * weights).sum() / weights.sum(), -1, 1))
                motion[8:] = max(0., spin) * 2, max(0., -spin) * 2
                focus = focus * (1 + reliable.astype(np.float32))
            shake = min(1., float(np.linalg.norm(camera)) / 20)
        self.previous = gray

        weight = max(1., float(focus.sum()))
        cx, cy = float((XX * focus).sum() / weight), float((YY * focus).sum() / weight)
        sx = math.sqrt(float(((XX - cx) ** 2 * focus).sum() / weight))
        sy = math.sqrt(float(((YY - cy) ** 2 * focus).sum() / weight))
        clean = min(1., float(((gray > 8) & (gray < 248)).mean()) * 1.3) * (1 - .6 * shake)
        # Normalized whole-frame evidence is for detecting repeated scenes,
        # never for awarding a transition a high score.
        identity = cv2.resize(gray, (20, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
        identity = unit((identity - identity.mean()).ravel())
        self.times.append(seconds)
        self.rows.append({'identity': identity, 'camera': camera, 'camera_support': camera_support,
                          'movement': movement, 'composition': composition, 'shape': shape, 'appearance': appearance,
                          'motion': unit(motion), 'speed': speed, 'confidence': confidence,
                          'local_pose': local_pose, 'motion_tiles': motion_tiles,
                          'subject_box': [cx / 96, cy / 64, sx * 2 / 96, sy * 2 / 64],
                          'cleanliness': clean})

    def anchors(self, start, end, role, tick, time_base):
        first, after = bisect_left(self.times, start - 1e-6), bisect_left(self.times, end - 1e-6)
        if after - first < 2:
            return []
        edge = first if role == 'entry' else after - 1
        step = 1 if role == 'entry' else -1
        anchors = []
        for offset in range(min(3, max(1, (after - first) // 4))):
            i = edge + step * offset
            ref = self.rows[i]
            a, b = (i + 1, min(after, i + 9)) if role == 'entry' else (max(first + 1, i - 7), i + 1)
            window = self.rows[a:b]
            if not window or ref['cleanliness'] < .45:
                continue
            evidence = {k: ref[k].tolist() for k in ('composition', 'shape', 'appearance')}
            confidence = float(np.mean([frame['confidence'] for frame in window]))
            flow = unit(np.mean([frame['motion'] * frame['confidence'] for frame in window], axis=0))
            motion_tiles = np.sum([frame['motion_tiles'] for frame in window], axis=0)
            motion_tiles /= max(1., float(motion_tiles.sum()))
            when = tick if not offset else self.ticks[min(len(self.ticks) - 1, max(0,
                bisect_left(self.ticks, self.ticks[0] + round(self.times[i] / time_base) + (role == 'exit'))))]
            camera_support = float(np.mean([row['camera_support'] for row in window]))
            camera = np.mean([row['camera'] * row['camera_support'] for row in window], axis=0)
            movement = np.mean([row['movement'] * row['confidence'] for row in window], axis=0)
            anchors.append({**evidence, 'motion': flow.tolist(), 'speed': float(np.mean([r['speed'] for r in window])),
                            'camera': camera.tolist(), 'camera_support': camera_support,
                            'movement': movement.tolist(),
                            'confidence': confidence, 'subject_box': ref['subject_box'], 'cleanliness': ref['cleanliness'],
                            'local_pose': ref['local_pose'].tolist(), 'motion_tiles': motion_tiles.tolist(),
                            'tick': when, 'anchor_seconds': self.times[i], 'offset': offset})
        return anchors


def span(row, source, start_tick, end_tick):
    clock = Fraction(source['time_base'])
    return {**row, 'in_tick': start_tick, 'out_tick': end_tick, 'time_base': source['time_base'],
            'start': float((start_tick - source['first_tick']) * clock),
            'duration': float((end_tick - start_tick) * clock),
            'seek': max(0., float(start_tick * clock) - source['container_origin'])}


def analyze(path, fingerprint, cache, db, stop):
    probe_key = digest([fingerprint, ANALYZER, 'probe'])
    source = db.cached(probe_key)
    if source is None:
        source = probe(path)
        db.cached(probe_key, source)
    key = digest([fingerprint, ANALYZER, 'descriptors'])
    cache_file = cache / (key + '.json.gz')
    if db.cached(key) is not None and cache_file.is_file():
        try:
            with gzip.open(cache_file, 'rt', encoding='utf-8') as handle:
                result = json.load(handle)
            return result, True
        except (OSError, ValueError):
            pass

    samples = Samples()
    rows = inspect(path, stop, lambda _: None, sample_seconds=.125,
                   sample_frame=samples.sample, frame_timing=samples.clock)
    first = samples.ticks[0]
    tail = samples.ticks[-1] - samples.ticks[-2] if len(samples.ticks) > 1 else 1
    end = samples.ticks[-1] + (samples.last_duration or max(1, tail))
    source.update(first_tick=first, end_tick=end, frame_pts=samples.ticks,
                  proxy_mapping='source-relative presentation timestamps; sampled at up to 8 Hz')
    clock = Fraction(source['time_base'])
    for row in rows:
        a = bisect_left(samples.ticks, first + round(row['start'] / clock))
        b = bisect_left(samples.ticks, first + round((row['start'] + row['duration']) / clock))
        tick_in = samples.ticks[a]
        tick_out = samples.ticks[b] if b < len(samples.ticks) else end
        row.update(span(row, source, tick_in, tick_out))
        row['source_id'] = fingerprint[:16]
        row['source_sha256'] = fingerprint
        row['id'] = digest([fingerprint, tick_in, tick_out, source['time_base']])[:24]
        row['aspect'] = source['aspect']
        lo = bisect_left(samples.times, row['start'] - 1e-6)
        hi = bisect_left(samples.times, row['start'] + row['duration'] - 1e-6)
        sample_indices = np.unique(np.linspace(lo, hi - 1, 9).round().astype(int)) if hi > lo else []
        row['scene_signature'] = [samples.rows[i]['identity'].round(5).tolist() for i in sample_indices]
        row['entries'] = samples.anchors(row['start'], row['start'] + row['duration'], 'entry', tick_in, clock)
        row['exits'] = samples.anchors(row['start'], row['start'] + row['duration'], 'exit', tick_out, clock)
        row.pop('source')
    result = {'source': source, 'rows': rows, 'sample_count': len(samples.times)}
    cache.mkdir(parents=True, exist_ok=True)
    temp = cache_file.with_name(key + '.' + uuid4().hex + '.tmp')
    try:
        with gzip.open(temp, 'wt', encoding='utf-8') as handle:
            json.dump(result, handle, allow_nan=False, separators=(',', ':'))
        os.replace(temp, cache_file)
        db.cached(key, {'file': cache_file.name, 'samples': len(samples.times), 'spans': len(rows)})
    finally:
        temp.unlink(missing_ok=True)
    return result, False


def near_duplicate(a, b):
    """Suppress whole-shot repeats, even after recoloring, trimming or re-encoding."""
    old = list(zip(a['signature'], b['signature']))
    if old and all((x['hash'] ^ y['hash']).bit_count() <= 5 and
                   sum(min(i, j) for i, j in zip(x['hist'], y['hist'])) >= .94 for x, y in old):
        return True
    first, second = a.get('scene_signature'), b.get('scene_signature')
    if not first or not second:
        return False
    similar = np.asarray(first, np.float32) @ np.asarray(second, np.float32).T >= .974
    # Cross-check coverage in both clips. A single matching cut frame or prop
    # is not enough to classify otherwise different footage as a repeat.
    return bool(similar.any(axis=0).mean() >= .67 and similar.any(axis=1).mean() >= .67)


def dot(a, b):
    return float(np.clip(np.dot(a, b), 0, 1))


def vector_match(a, b, minimum):
    first, second = np.linalg.norm(a), np.linalg.norm(b)
    if min(first, second) < minimum:
        return None
    direction = float(np.dot(a, b) / (first * second))
    pace = min(first, second) / max(first, second)
    return direction, float(pace)


def edge_score(exit, entry):
    """Score a directed handoff from outgoing to incoming movement."""
    shape = dot(exit['shape'], entry['shape'])
    layout = dot(exit['composition'], entry['composition'])
    box = math.exp(-3 * sum(abs(x - y) for x, y in zip(exit['subject_box'], entry['subject_box'])))
    composition = .55 * box + .45 * layout
    confidence = min(exit['confidence'], entry['confidence'])
    movement = vector_match(exit['movement'], entry['movement'], .12)
    if movement and confidence >= .25 and movement[0] < .1:
        return None
    motion, handoff = 0., None
    if confidence >= .21:
        directions = dot(exit['motion'], entry['motion'])
        speed = min(exit['speed'], entry['speed']) / max(.01, exit['speed'], entry['speed'])
        outgoing, incoming = np.asarray(exit['motion_tiles']), np.asarray(entry['motion_tiles'])
        localized = min(np.sort(outgoing)[-4:].sum(), np.sort(incoming)[-4:].sum())
        if movement and movement[0] >= .72 and movement[1] >= .32 and localized >= .45:
            motion = .74 * movement[0] + .26 * min(speed, movement[1])
            handoff = 'subject movement'
        elif directions >= .76 and speed >= .42 and box >= .42 and shape >= .42:
            overlap = np.minimum(outgoing, incoming).sum()
            stable = min(exit['camera_support'], entry['camera_support'])
            # Diffuse motion (water, landscape drift) can mimic a gesture's
            # direction histogram. Require a stable, shared moving region.
            if localized >= .40 and overlap >= .58 and stable >= .48:
                motion = .75 * directions + .25 * speed
                handoff = 'gesture or rotation'
    camera = vector_match(exit['camera'], entry['camera'], .35)
    if (camera and min(exit['camera_support'], entry['camera_support']) >= .32
            and camera[0] >= .83 and camera[1] >= .40 and box >= .44
            and layout >= .46 and shape >= .45):
        sweep = .72 * camera[0] + .28 * camera[1]
        if sweep > motion:
            motion, handoff = sweep, 'camera movement'
    if motion < .68:
        return None
    signals = {'composition': composition, 'shape': shape, 'motion': motion,
               'cleanliness': min(exit['cleanliness'], entry['cleanliness'])}
    score = sum(WEIGHTS[key] * value for key, value in signals.items())
    score -= .008 * (exit['offset'] + entry['offset'])
    if score < MIN_SCORE:
        return None
    return {**{key: round(value, 4) for key, value in signals.items()},
            'appearance': round(dot(exit['appearance'], entry['appearance']), 4),
            'score': round(score, 4), 'motion_confidence': round(confidence, 4),
            'out_tick': exit['tick'], 'in_tick': entry['tick'],
            'anchor_seconds': [exit['anchor_seconds'], entry['anchor_seconds']],
            'subject_boxes': [exit['subject_box'], entry['subject_box']],
            'transition': 'hard cut', 'handoff': handoff}


def _boundary_vectors(clips, side, key):
    return np.asarray([unit(np.mean([anchor[key] for anchor in clip[side]], axis=0)) for clip in clips])


def find_matches(clips, stop, progress):
    if not clips:
        return []
    graph = [[] for _ in clips]
    signals = [(_boundary_vectors(clips, 'exits', key), _boundary_vectors(clips, 'entries', key))
               for key in ('movement', 'camera', 'motion')]
    aspects = np.log([row['aspect'] for row in clips])
    for lo in range(0, len(clips), 96):
        check_stop(stop)
        rough = np.maximum.reduce([ends[lo:lo + 96] @ starts.T for ends, starts in signals])
        rough[np.abs(aspects[lo:lo + 96, None] - aspects[None, :]) > .24] = -1
        for i, scores in enumerate(rough, lo):
            left = clips[i]
            source_counts = {}
            retrieved = 0
            for j in np.argsort(-scores, kind='stable'):
                if scores[j] < .52 or retrieved >= 36:
                    break
                right = clips[j]
                if left['source_id'] == right['source_id']:
                    if left['shot_start'] == right['shot_start']:
                        continue
                    if left['start'] <= right['start'] + right['duration'] + .25 and right['start'] <= left['start'] + left['duration'] + .25:
                        continue
                if source_counts.get(right['source_id'], 0) >= 3:
                    continue
                if near_duplicate(left, right):
                    continue
                retrieved += 1
                source_counts[right['source_id']] = source_counts.get(right['source_id'], 0) + 1
                scored = [cut for a in left['exits'] for b in right['entries']
                          if (cut := edge_score(a, b)) is not None]
                if not scored:
                    continue
                graph[i].append((int(j), max(scored, key=lambda cut: cut['score'])))
            graph[i] = sorted(graph[i], key=lambda item: (-item[1]['score'], item[0]))[:NEIGHBORS]
        progress('Finding movement that carries across cuts', 46 + round(14 * min(len(clips), lo + 96) / len(clips)))
    return graph
