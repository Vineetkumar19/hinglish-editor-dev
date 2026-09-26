"""Eye Contact: timeline XML / video / folder -> eye-contact copies of your camera files + relinked XML."""
from datetime import datetime
from pathlib import Path
import hashlib
import json
import os
import shutil
import time
import uuid

from hinglish_broll.pipeline import _videos
from hinglish_broll.timeline import path_key

from .maxine import doctor, run_gaze
from .media import (MJPEG_BYTES_PER_PIXEL, ChunkInput, FinalVideo, add_original_audio, chunk_frames, free_bytes,
                    plan_boundary, probe, side_by_side, simulate_engine, source_frames)
from .report import write_report
from .settings import EyeSettings
from .timeline import relink, used_sources

VERSION = 1                 # bump when the output of the same source + settings would change
PREVIEW_SECONDS = 12.0


def media_key(path, settings):
    stat = Path(path).stat()
    data = [path_key(path), stat.st_size, int(stat.st_mtime), settings.key(), VERSION]
    return hashlib.sha1(json.dumps(data).encode()).hexdigest()[:10]


def disk_needed(info):
    """Bytes of scratch space: one chunk in and out of NVIDIA + the new video twice (temp + final)."""
    pixels = info.width * info.height
    chunk = min(info.frames, chunk_frames(info))
    return int(chunk * pixels * (MJPEG_BYTES_PER_PIXEL + .12) + 2 * info.frames * pixels * .012)


def correct(source, media_dir, engine, settings, used, progress):
    """One camera file -> its eye-contact copy (same length, frame timing, audio and timecode)."""
    info = probe(source)
    key = media_key(source, settings)
    target = media_dir / f'{Path(source).stem[:60]}_EYECONTACT_{key}{info.container_suffix}'
    stats = {'source': str(source), 'target': str(target), 'duration': info.duration, 'frames': info.frames,
             'fixed': info.frames, 'seconds': 0.0, 'parts': 0}
    if target.is_file():
        progress(f'  Already done earlier: reusing {target.name}')
        return target, info, {**stats, 'reused': True}
    media_dir.mkdir(parents=True, exist_ok=True)
    need = disk_needed(info)
    if free_bytes(media_dir) < need * 1.1:
        raise RuntimeError(f'Not enough free space for {Path(source).name}: needs about {need / 1e9:.1f} GB free '
                           f'on {media_dir.anchor}')
    work = media_dir / f'.work-{key}'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    started, per = time.time(), chunk_frames(info)
    final = FinalVideo(work / 'video.mp4', info, settings.quality)
    chunk, parts = None, 0

    def finish(chunk, part):
        chunk.close()
        corrected = work / f'part-{part:03d}.avi'
        engine(chunk.path, corrected, len(chunk.pts), progress, label=f'part {part} · ')
        final.append(corrected, chunk)
        corrected.unlink(missing_ok=True)
        chunk.path.unlink(missing_ok=True)

    try:
        for frame, pts, seconds in source_frames(info):
            if chunk is None:
                parts += 1
                chunk = ChunkInput(work / f'part-{parts:03d}.mp4', info)
            chunk.add(frame, pts, seconds)
            if plan_boundary(chunk, per, seconds, used):
                finish(chunk, parts)
                chunk = None
        if chunk is not None and chunk.pts:
            finish(chunk, parts)
        final.close()
        progress('  Putting your original audio back')
        done = add_original_audio(final.path, source, work / f'final{target.suffix}', info.timecode)
        os.replace(done, target)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    stats.update(frames=final.frames, fixed=final.fixed, seconds=time.time() - started, parts=parts)
    return target, info, stats


def check(info, target):
    """The copy must line up with the original frame for frame."""
    got = probe(target)
    notes = []
    if abs(got.duration - info.duration) > 1.5 / float(info.rate):
        notes.append(f'{Path(target).name}: length {got.duration:.3f}s vs original {info.duration:.3f}s')
    if len(got.audio) != len(info.audio):
        notes.append(f'{Path(target).name}: {len(got.audio)} audio tracks vs {len(info.audio)} in the original')
    return notes


def run(root, input_path, settings=None, progress=print, simulate=False):
    root = Path(root).resolve()
    settings = settings or EyeSettings()
    health = doctor(root)
    if simulate:
        progress('SIMULATION (developer test): the pipeline runs, but the eyes are NOT changed')
        engine = simulate_engine
    elif not health.ready:
        raise RuntimeError(health.text())
    else:
        progress(f'NVIDIA Eye Contact on {health.gpu.name}')

        def engine(source, target, frames, progress, label=''):
            return run_gaze(health.install, source, target, settings, frames, progress, label)

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'eyecontact' / stamp
    output.mkdir(parents=True)
    media_dir = root / 'output' / 'eyecontact' / ('media-simulated' if simulate else 'media')
    input_path = Path(input_path)
    is_xml = input_path.suffix.lower() == '.xml'
    progress('Reading the timeline' if is_xml else 'Finding your videos')
    if is_xml:
        # stock B-roll downloads and the sound library never hold your talking head
        sources = used_sources(input_path, skip=[root / 'cache' / 'broll', root / 'output' / 'broll',
                                                 root / 'library', root / 'output' / 'eyecontact'])
    else:
        sources = [{'path': str(p), 'ranges': []} for p in _videos(input_path)]
    if not sources:
        raise ValueError('No camera clips were found' + (' on the video tracks of this timeline' if is_xml else ''))

    results, fixed, notes = [], {}, []
    for n, source in enumerate(sources, 1):
        path = Path(source['path'])
        if not path.is_file():
            notes.append(f'Media offline, skipped: {path}')
            continue
        progress(f'Eye contact {n}/{len(sources)}: {path.name}')
        target, info, stats = correct(path, media_dir, engine, settings, source['ranges'], progress)
        if info.hdr:
            notes.append(f'{path.name} is HDR: it was converted to standard 8-bit video for NVIDIA')
        notes += check(info, target)
        if stats['fixed'] < stats['frames'] - 2:
            notes.append(f'{path.name}: NVIDIA returned {stats["fixed"]} of {stats["frames"]} frames; '
                         'the rest keep the original eyes')
        fixed[str(path)] = target
        results.append({**stats, 'info': info, 'ranges': source['ranges']})
    if not results:
        raise ValueError('None of the camera files could be found')

    xml_name = None
    if is_xml:
        xml_name = 'EYE_CONTACT_SEQUENCE.xml'
        swapped = relink(input_path, output / xml_name, fixed)
        progress(f'  Relinked {swapped} clip file(s) in the timeline')
    progress('Making a before / after preview')
    first = results[0]
    ranges = first['ranges'] or [(0.0, first['info'].duration)]
    a, b = max(ranges, key=lambda r: r[1] - r[0])
    start = max(a, (a + b) / 2 - PREVIEW_SECONDS / 2)
    preview = side_by_side(first['info'], first['target'], start, min(PREVIEW_SECONDS, b - start),
                           output / 'preview.mp4')
    page = write_report(output / 'report.html', input_path.stem, [{k: v for k, v in r.items() if k != 'info'}
                                                                   for r in results],
                        settings, preview.name, xml_name, notes, simulated=simulate)
    (output / 'eyecontact-plan.json').write_text(json.dumps({
        'settings': settings.__dict__, 'simulated': simulate, 'notes': notes,
        'files': [{k: v for k, v in r.items() if k != 'info'} for r in results]}, indent=2), encoding='utf-8')
    return page
