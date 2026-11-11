"""Compile director-selected word IDs into a frame-accurate narration clock.

No creative fallback: unavailable anchors fail validation rather than receiving
invented evenly spaced times. Frame scheduling and semantic choices are separate.
"""
import math


def frame_at(seconds, fps=30):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Invalid acoustic onset')
    return math.ceil(seconds * fps - 1e-7)


def compile_plan(plan, words, effects, duration=60, fps=30):
    anchors = {w['id']: w for w in words}
    scenes = plan.get('scenes', [])
    if not scenes:
        raise ValueError('The local director returned no scenes')
    result = []
    starts = []
    for index, row in enumerate(scenes):
        word = anchors.get(row.get('start_word'))
        if word is None:
            raise ValueError(f'Unknown scene word: {row.get("start_word")}')
        starts.append(0 if index == 0 else frame_at(word['start'], fps))
    if starts != sorted(set(starts)) or starts[-1] >= duration * fps:
        raise ValueError('Scene starts must be increasing distinct word anchors')
    for index, row in enumerate(scenes):
        if row.get('effect') not in effects:
            raise ValueError('Unavailable effect selected by local director')
        start = starts[index]
        end = starts[index + 1] if index + 1 < len(scenes) else round(duration * fps)
        if end - start < fps * 1.5:
            raise ValueError(f'Scene {index + 1} is shorter than 1.5 seconds')
        copied = {**row, 'start_frame': start, 'end_frame': end,
                  'start': start / fps, 'seconds': (end - start) / fps}
        for field in ['photos', 'notes']:
            events = []
            for event in row.get(field, []):
                word = anchors.get(event.get('word'))
                if word is None:
                    raise ValueError(f'Unknown {field} word: {event.get("word")}')
                frame = frame_at(word['start'], fps)
                # The first source word can start shortly after zero. A scene
                # still begins at zero, while its event keeps the acoustic time.
                if not start <= frame < end:
                    raise ValueError(f'{field} cue {word["id"]} is outside scene {index + 1}')
                events.append({**event, 'frame': frame, 'global_at': frame / fps,
                               'at': (frame - start) / fps,
                               'acoustic_at': word['start'], 'spoken_text': word['text'],
                               'schedule_error_ms': round((frame / fps - word['start']) * 1000, 3)})
            if any(events[j]['frame'] > events[j+1]['frame'] for j in range(len(events)-1)):
                raise ValueError('Cues must follow narration order')
            copied[field] = events
        if row.get('sfx') != 'none':
            word = anchors.get(row.get('sfx_word'))
            if word is None:
                raise ValueError('Sound cue has no acoustic anchor')
            frame = frame_at(word['start'], fps)
            if not start <= frame < end:
                raise ValueError('Sound cue is outside its scene')
            copied['sfx_at'] = word['start']  # audio stays sample timed
        result.append(copied)
    return result


def retimed_phase(elapsed, cue_times, native_times, native_end, duration):
    """Piecewise map speech cue times to an existing template's reveal points."""
    if len(cue_times) != len(native_times):
        raise ValueError('Cue mapping lengths differ')
    knots = [(0., 0.), *zip(cue_times, native_times), (duration, native_end)]
    # Multiple cues on one spoken word are a single reveal boundary. Later
    # native phases win at that instant; no division by a zero time interval.
    merged = {}
    for actual, native in knots:
        if not (0 <= actual <= duration) or not math.isfinite(native):
            raise ValueError('Invalid retiming knot')
        merged[actual] = max(merged.get(actual, float('-inf')), native)
    points = sorted(merged.items())
    if any(points[i][1] > points[i+1][1] for i in range(len(points)-1)):
        raise ValueError('Existing template cannot visit cues in that order')
    if elapsed <= points[0][0]:
        return points[0][1]
    for (a, x), (b, y) in zip(points, points[1:]):
        if elapsed <= b:
            return x + (y-x) * (elapsed-a) / (b-a)
    return points[-1][1]
