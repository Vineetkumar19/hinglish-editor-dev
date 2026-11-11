"""Build the comedy-first cold open from timed speech in one gaming replay."""
from bisect import bisect_right
from contextlib import nullcontext
from fractions import Fraction
from math import ceil, floor
from pathlib import Path
import re

from hinglish_shorts.source import open_video, quick_fingerprint

DURATION = 30
UNITS_PER_SECOND = 4
SYSTEM = """Select stand-alone funny moments for the first 30 seconds of this gaming replay.
Use only the supplied timed lines. Pick the strongest punchlines, playful sarcastic
roasts, funny banter and spontaneous comic reactions in Hindi, Hinglish or English.
An intact setup and payoff must fit in 3–5 seconds of contiguous source audio.
Playful profanity can be part of a joke; profanity alone, hostile abuse, raw gameplay,
ordinary narration, generic shouts, loading, promotion and dead air are not highlights.
Do not invent jokes, actions, laughter or context. Score honestly. Return fewer or
no candidates if the transcript does not support complete jokes. Do not repeat jokes."""
SCHEMA = {'type': 'object', 'properties': {'clips': {'type': 'array', 'maxItems': 8,
    'items': {'type': 'object', 'properties': {
        'first': {'type': 'integer'}, 'last': {'type': 'integer'},
        'score': {'type': 'integer', 'minimum': 1, 'maximum': 10},
        'reason': {'type': 'string', 'maxLength': 160}},
        'required': ['first', 'last', 'score', 'reason']}}}, 'required': ['clips']}


def request(value):
    raw = value.get('source')
    key = value.get('idempotency_key')
    if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9-]{36}', key):
        raise ValueError('Reopen Intro Create and submit the gaming replay again.')
    if not isinstance(raw, str) or not raw.strip() or '\x00' in raw:
        raise ValueError('Choose one downloaded gaming replay with commentary.')
    path = Path(raw.strip().strip('"'))
    if not path.is_absolute() or path.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm') or not path.is_file():
        raise ValueError('Choose an existing local MP4, MOV, MKV or WebM gaming replay.')
    path = path.resolve()
    return {'source': str(path), 'fingerprint': quick_fingerprint(path), 'idempotency_key': key}


def proposals(root, video, device, stop, progress):
    from hinglish_broll.phrases import build_phrases
    from hinglish_shorts.find import windows
    from hinglish_shorts.source import transcribe
    from hinglish_visuals.brain import open_brain

    def update(message):
        if stop.is_set():
            raise InterruptedError('Gaming intro stopped.')
        progress(message, 12)

    words = transcribe(root, video, device, update, retry_unreadable=True)
    lines = build_phrases(words, pause=.33, max_words=14, max_seconds=4.5, merge=False)
    sections = list(windows(lines, size=100, overlap=6))
    if not sections:
        return []
    brain = open_brain(root, progress=update)
    brain.context_feature = 'gaming'
    selected = {}
    try:
        for number, section in enumerate(sections, 1):
            if stop.is_set():
                raise InterruptedError('Gaming intro stopped.')
            progress(f'Finding complete jokes in section {number}/{len(sections)}', 15 + 45 * number // len(sections))
            answer = brain.json(SYSTEM, {'lines': [vars(line) for line in section]}, SCHEMA, max_tokens=1200)
            if not isinstance(answer.get('clips'), list):
                raise ValueError('The gaming planner returned an unreadable result. Retry this intro.')
            for clip in answer['clips'][:8]:
                if not isinstance(clip, dict):
                    continue
                first, last, score = (clip.get(key) for key in ('first', 'last', 'score'))
                if any(type(n) is not int for n in (first, last, score)):
                    continue
                if not section[0].id <= first <= last <= section[-1].id or not 7 <= score <= 10:
                    continue
                reason = clip.get('reason')
                if not isinstance(reason, str) or not reason.strip():
                    continue
                start, end = lines[first].start, lines[last].end
                if not 0 <= start < end <= video.duration or end - start > 5:
                    continue
                left = min(start, lines[first - 1].end) if first else 0
                right = max(end, lines[last + 1].start) if last + 1 < len(lines) else video.duration
                item = {'first': first, 'last': last, 'start': start, 'end': end,
                        'left': left, 'right': right, 'score': score, 'reason': reason[:160],
                        'text': ' '.join(line.text for line in lines[first:last + 1])}
                previous = selected.get((first, last))
                if previous is None or previous['score'] < score:
                    selected[first, last] = item
    finally:
        brain.close()
    return list(selected.values())


def plan_clips(items, fps):
    """Pick non-overlapping complete jokes under one exact 30-second budget."""
    options = []
    for item in items:
        earliest, latest = ceil(item['left'] * fps), floor(item['right'] * fps)
        speech_in, speech_out = floor(item['start'] * fps), ceil(item['end'] * fps)
        for units in range(3 * UNITS_PER_SECOND, 5 * UNITS_PER_SECOND + 1):
            length = Fraction(units, UNITS_PER_SECOND) * fps
            min_start = max(earliest, speech_out - floor(length))
            max_start = min(speech_in, latest - ceil(length))
            if min_start <= max_start:
                start = min(max_start, max(min_start, speech_in - round(fps / 8)))
                options.append((start + ceil(length), start, units, item))
    options.sort(key=lambda row: row[:3])
    ends = [option[0] for option in options]
    target = DURATION * UNITS_PER_SECOND
    # Values carry a score and a linked list of the chosen cut options.
    rows = [[(0, None)] + [None] * target]
    for i, option in enumerate(options):
        _, start, units, item = option
        before = rows[bisect_right(ends, start, hi=i)]
        current = rows[-1].copy()
        value = units * item['score'] * 16 - abs(units - 4 * UNITS_PER_SECOND)
        for total in range(units, target + 1):
            earlier = before[total - units]
            if earlier is not None and (current[total] is None or earlier[0] + value > current[total][0]):
                current[total] = (earlier[0] + value, (option, earlier[1]))
        rows.append(current)
    result = rows[-1][target]
    if result is None:
        raise ValueError('Too few complete funny moments to fill 30 seconds. Choose a replay with more usable commentary.')
    chosen = []
    chain = result[1]
    while chain:
        option, chain = chain
        chosen.append(option)
    # Lead with the strongest line and finish with another strong payoff.
    chosen.sort(key=lambda row: (-row[3]['score'], row[1]))
    chosen.append(chosen.pop(1))
    cursor = 0
    cuts = []
    for _, start, units, item in chosen:
        finish = cursor + units
        frames = round(Fraction(finish, UNITS_PER_SECOND) * fps) - round(Fraction(cursor, UNITS_PER_SECOND) * fps)
        cuts.append({'source_start': start, 'frames': frames, 'text': item['text'], 'reason': item['reason']})
        cursor = finish
    return cuts


def run(root, engine_root, value, folder, stop, progress, *, reviewed_moments=None, include_replay=True):
    import av
    from hinglish_app.workbench_jobs import atomic_json
    from hinglish_cinematic.render import run_ffmpeg
    from hinglish_cut.compute_policy import ffmpeg_h264, heavy_device
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml

    source = Path(value['source'])
    if quick_fingerprint(source) != value['fingerprint']:
        raise ValueError('The replay changed. Choose the current file and start a new intro.')
    video = open_video(source)
    if video.duration < DURATION or video.width < video.height or video.width % 2 or video.height % 2:
        raise ValueError('Choose a landscape gaming replay of at least 30 seconds with even video dimensions.')
    with av.open(video.path) as media:
        seek_offset = video.video_start - (media.start_time or 0) / av.time_base
    device = heavy_device(engine_root)
    progress('Reading the replay commentary', 8)
    items = proposals(engine_root, video, device, stop, progress) if reviewed_moments is None else reviewed_moments
    if any(not 0 <= item['left'] <= item['start'] < item['end'] <= item['right'] <= video.duration for item in items):
        raise ValueError('A reviewed moment is outside the gaming replay.')
    cuts = plan_clips(items, video.fps)
    if quick_fingerprint(source) != value['fingerprint']:
        raise ValueError('The replay changed during planning. Choose the current file and start a new intro.')
    folder.mkdir(parents=True, exist_ok=True)
    parts, sounds = [], []
    for index, cut in enumerate(cuts, 1):
        progress(f'Rendering comedy cut {index} of {len(cuts)}', 62 + 28 * index // len(cuts))
        part = folder / f'cut-{index:02}.mp4'
        audio = folder / f'cut-{index:02}.wav'
        start = max(0, float(cut['source_start'] / video.fps) + seek_offset)
        seconds = cut['frames'] / video.fps
        with gpu_lock(engine_root) if device == 'cuda' else nullcontext():
            run_ffmpeg(['-ss', str(float(start)), '-i', source, '-map', '0:v:0', '-an',
                        '-vf', f'fps={video.fps}', '-frames:v', str(cut['frames']),
                        *ffmpeg_h264(device, 18), '-pix_fmt', 'yuv420p', part,
                        '-map', '0:a:0', '-vn', '-af', 'apad', '-t', str(float(seconds)),
                        '-ac', '2', '-ar', '48000', '-c:a', 'pcm_s16le', audio], folder, stop)
        parts.append(f"file '{part.name}'\nduration {float(seconds):.9f}")
        sounds.append(f"file '{audio.name}'")
    listing = folder / 'cuts.txt'
    listing.write_text('\n'.join(parts) + '\n', encoding='utf-8')
    soundtrack = folder / 'soundtrack.txt'
    soundtrack.write_text('\n'.join(sounds) + '\n', encoding='utf-8')
    partial = folder / 'gaming-intro.partial.mp4'
    target = folder / 'Gaming Intro.mp4'
    frames = round(DURATION * video.fps)
    seconds = float(frames / video.fps)
    run_ffmpeg(['-f', 'concat', '-safe', '1', '-i', listing, '-f', 'concat', '-safe', '1', '-i', soundtrack,
                '-map', '0:v:0', '-map', '1:a:0',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-t', str(seconds),
                '-movflags', '+faststart', partial], folder, stop)
    progress('Verifying the cold open and the replay handoff', 94)
    with av.open(str(partial)) as media:
        track = media.streams.video[0]
        if (track.width, track.height) != (video.width, video.height) or len(media.streams.audio) != 1:
            raise ValueError('The gaming intro failed picture or original-audio verification.')
        index = 0
        for index, frame in enumerate(media.decode(video=0), 1):
            expected = (index - 1) / video.fps
            if frame.pts is None or abs(frame.pts * frame.time_base - expected) > 1 / video.fps / 2:
                raise ValueError('The gaming intro failed frame timing verification.')
        if index != frames:
            raise ValueError('The gaming intro failed the 30-second frame count.')
    if quick_fingerprint(source) != value['fingerprint']:
        raise ValueError('The replay changed during rendering. Choose the current file and start a new intro.')
    result = {'video': str(target), 'source_name': source.name,
              'fps': str(video.fps), 'seconds': seconds, 'frames': frames, 'cuts': cuts}
    if include_replay:
        original = video.media()
        timeline = folder / 'Gaming Intro and Replay.xml'
        edit = [Cut(original.id, cut['source_start'], cut['source_start'] + cut['frames'], i)
                for i, cut in enumerate(cuts)]
        edit.append(Cut(original.id, 0, floor(video.duration * video.fps), len(edit)))
        export_xml(timeline, edit, {original.id: original})
        result['timeline'] = str(timeline)
    partial.replace(target)
    atomic_json(folder / 'intro-plan.json', result)
    return result
