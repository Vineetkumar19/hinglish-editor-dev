"""Streamed analysis and bounded, evidence-based gaming highlight compilations."""
import html
import json
import subprocess
import uuid
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

import numpy as np

from imageio_ffmpeg import get_ffmpeg_exe as ffmpeg_path
from hinglish_cut.compute_policy import ffmpeg_h264, heavy_device
from hinglish_cut.gpu_lock import gpu_lock
from hinglish_shorts.find import make_lines, transcript, windows, snap
from hinglish_shorts.source import open_video, transcribe, quick_fingerprint
from hinglish_visuals.brain import open_brain

SCHEMA = {'type': 'object', 'properties': {'moments': {'type': 'array', 'maxItems': 8,
    'items': {'type': 'object', 'properties': {'first': {'type': 'integer'}, 'last': {'type': 'integer'},
        'score': {'type': 'integer', 'minimum': 1, 'maximum': 10}, 'title': {'type': 'string','maxLength':100},
        'kind': {'type': 'string', 'enum': ['funny', 'clutch', 'dramatic', 'surprise']},
        'reason': {'type': 'string','maxLength':240}}, 'required': ['first', 'last', 'score', 'title', 'kind', 'reason']}}},
    'required': ['moments']}
SYSTEM = '''Choose genuinely engaging gaming stream moments from this transcript section.
Return at most eight complete setup -> payoff moments, using supplied line IDs only. Each should be
10-100 seconds. Prefer funny reactions, clutch plays, failures, surprise or suspense. Skip waiting,
menus, loading, generic commentary, sponsors, repeated rounds and donation reads. Give fewer or none
when nothing is strong. Reason must cite what was actually said, not invent action you cannot see.
Audio peaks and visual changes are weak attention cues, not proof of a kill, laugh or win.
Write concise titles/reasons in English. Score 1-10 honestly. Preserve chronological context.'''


def signals(root, video, progress=print):
    """FFmpeg streams tiny audio bins and low-rate thumbnails; no 5-hour frame/audio array."""
    target = Path(root) / 'cache' / 'niche' / ('signals-' + quick_fingerprint(video.path) + '.json')
    if target.exists():
        return json.loads(target.read_text(encoding='utf-8'))
    progress('Scanning audio energy and gameplay changes without loading the whole stream into RAM')
    exe = str(ffmpeg_path())
    flags = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    peaks = []
    process = subprocess.Popen([exe, '-v', 'error', '-threads', '2', '-i', video.path, '-vn',
        '-ac', '1', '-ar', '8000', '-f', 'f32le', 'pipe:1'], stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, **flags)
    try:
        n = 0
        while True:
            block = process.stdout.read(8000 * 4 * 5)
            if not block:
                break
            samples = np.frombuffer(block[:len(block) // 4 * 4], dtype='<f4')
            peaks.append({'time': n * 5, 'energy': float(np.sqrt(np.mean(samples * samples)))})
            n += 1
        if process.wait():
            raise ValueError('Could not scan the stream audio.')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
    changes = []
    process = subprocess.Popen([exe, '-v', 'error', '-threads', '2', '-i', video.path, '-an',
        '-vf', 'fps=1/5,scale=64:36', '-pix_fmt', 'gray', '-f', 'rawvideo', 'pipe:1'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **flags)
    try:
        previous, n = None, 0
        while True:
            block = process.stdout.read(64 * 36)
            if len(block) != 64 * 36:
                break
            pixels = np.frombuffer(block, dtype='uint8').astype('float32')
            if previous is not None:
                changes.append({'time': n * 5, 'change': float(np.mean(np.abs(pixels - previous)))})
            previous, n = pixels, n + 1
        if process.wait():
            raise ValueError('Could not scan gameplay changes.')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
    data = {'audio': peaks, 'visual': changes, 'note': 'Attention cues only, no event classifier.'}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(data), encoding='utf-8')
    temporary.replace(target)
    return data


def candidates(brain, words, duration, cues, progress=print):
    lines = make_lines(words)
    found = []
    parts = list(windows(lines));done=0
    while parts:
        progress(f'Finding gaming moments in section {done+1}/{done+len(parts)}')
        part=parts.pop(0)
        start, end = part[0].start, part[-1].end
        evidence = {key: sorted((p for p in cues.get(key, []) if start <= p['time'] <= end),
                    key=lambda p: p.get('energy', p.get('change', 0)), reverse=True)[:8] for key in ('audio', 'visual')}
        try:
            answer = brain.json(SYSTEM, {'transcript': transcript(part), 'attention_cues': evidence},
                                SCHEMA, max_tokens=1800,think=False)
        except Exception as error:
            # Dense Hinglish speech can exceed a tokenizer's context estimate.
            # Preserve every line, with overlap, and retry only smaller parts.
            response=getattr(error,'response',None)
            context_error=response is not None and response.status_code==400 and any(
                word in response.text.casefold() for word in ('context','tokens','too long'))
            if not (context_error or isinstance(error,json.JSONDecodeError)) or len(part)<2:raise
            middle=len(part)//2;overlap=min(3,(len(part)-1)//4)
            parts[:0]=[part[:middle+overlap],part[middle-overlap:]]
            progress('This gaming section exceeded the local response/context budget; retrying smaller overlapping sections without dropping source lines')
            continue
        found += validate_moments(answer.get('moments', []), part, words, duration)
        done+=1
    return found


def validate_moments(raw, lines, words, duration):
    ids = {line.id: line for line in lines}
    kept = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        a, b, score = item.get('first'), item.get('last'), item.get('score')
        if type(a) is not int or type(b) is not int or a not in ids or b not in ids or b < a:
            continue
        if type(score) is not int or not 1 <= score <= 10 or item.get('kind') not in ('funny', 'clutch', 'dramatic', 'surprise'):
            continue
        start, end = snap(words, ids[a], ids[b])
        start, end = max(0, start), min(duration, end)
        text = ' '.join(l.text for l in lines if a <= l.id <= b)
        if not 10 <= end - start <= 100 or any(p in text.casefold() for p in ('sponsor', 'subscribe', 'donation', 'loading screen')):
            continue
        kept.append({'start': round(start, 3), 'end': round(end, 3), 'score': score,
                     'kind': item['kind'], 'title': str(item.get('title', ''))[:100],
                     'reason': str(item.get('reason', ''))[:500], 'transcript': text})
    return kept


def select(found, target_seconds):
    chosen, total = [], 0
    for item in sorted(found, key=lambda m: (-m['score'], m['start'])):
        if item['score'] < 6:
            continue
        if any(min(item['end'], c['end']) > max(item['start'], c['start']) for c in chosen):
            continue
        seconds = item['end'] - item['start']
        if total + seconds > target_seconds:
            continue
        chosen.append(item)
        total += seconds
    return sorted(chosen, key=lambda m: m['start'])


def approved_memes(root):
    base = Path(root) / 'library' / 'creator-memes'
    file = base / 'manifest.json'
    if not file.exists():
        return []
    kept = []
    for entry in json.loads(file.read_text(encoding='utf-8')).get('assets', [])[:50]:
        p = (base / str(entry.get('file', ''))).resolve()
        if entry.get('approved') is True and entry.get('rights') in ('owned', 'licensed') and \
                p.is_relative_to(base.resolve()) and p.is_file() and p.suffix.lower() == '.mp4':
            kept.append({**entry, 'path': str(p)})
    return kept


def render(root, video, moments, folder, memes=True, progress=print, *, lineage_parts=None, device=None):
    """Decode selected intervals, preserving full frame, output timing and stereo audio."""
    device = heavy_device(root, device)
    exe = str(ffmpeg_path())
    width, height = video.width + video.width % 2, video.height + video.height % 2
    fps = str(video.fps)
    pad = f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    main_filter = 'format=yuv420p,' + pad
    if device == 'cuda':
        insert_filter = (f'format=nv12,hwupload_cuda,scale_cuda=w={width}:h={height}:'
                         'force_original_aspect_ratio=decrease:force_divisible_by=2:interp_algo=bicubic,'
                         'hwdownload,format=nv12,' + pad + ',format=yuv420p')
        encoder = ffmpeg_h264(device, 20)
        progress(f'Encoding gaming highlights on NVIDIA at {width} × {height}, {fps} fps')
    else:
        insert_filter = f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,' + pad + ',format=yuv420p'
        encoder = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-threads', '2']
    parts = folder / 'parts'
    parts.mkdir()
    cuts, media, entries, receipts = [], {}, [], []
    from hinglish_cut.model import Cut
    from hinglish_cut.media import probe
    from hinglish_cut.xml_export import export_xml
    assets = approved_memes(root) if memes else []
    meme_count = 0
    for i, moment in enumerate(moments):
        clips = [(video.path, moment['start'], moment['end'] - moment['start'], False)]
        matching = [a for a in assets if moment['kind'] in a.get('tags', [])]
        if matching and meme_count < 6 and (i + 1) % 3 == 0:
            asset = matching[meme_count % len(matching)]
            facts = open_video(asset['path'])
            clips.append((asset['path'], 0, min(1.5, facts.duration), True))
            meme_count += 1
        for path, start, length, is_meme in clips:
            source_stamp = None
            if lineage_parts is not None:
                from .gaming_lineage import media_stamp
                source_stamp = media_stamp(path)
            out = parts / f'part-{len(entries):03d}.mp4'
            progress(f'Rendering selected moment {i + 1}/{len(moments)}')
            command = [exe, '-y', '-v', 'error', '-threads', '2', '-ss', str(start), '-i', path,
                '-t', str(length), '-map', '0:v:0', '-map', '0:a:0',
                '-vf', insert_filter if is_meme else main_filter, '-r', fps, *encoder,
                '-c:a', 'aac', '-ac', '2', '-ar', '48000', '-af', 'asetpts=PTS-STARTPTS',
                '-movflags', '+faststart', str(out)]
            with gpu_lock(root) if device == 'cuda' else nullcontext():
                try:
                    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                except subprocess.CalledProcessError as error:
                    if device == 'cuda':
                        detail = (error.stderr or b'').decode('utf-8', errors='replace').strip()
                        raise RuntimeError(f'NVIDIA gaming render failed: {detail}') from error
                    raise
            m = probe(out)
            media[m.id] = m
            cuts.append(Cut(m.id, 0, round(m.duration * float(m.rate)), len(cuts)))
            entries.append(out)
            if lineage_parts is not None:
                lineage_parts.append({'kind':'insert' if is_meme else 'root',
                    'source_path':str(path),'source_in':start,'requested_duration':length,
                    'rendered_path':str(out),'source_stamp':source_stamp})
            if is_meme:
                receipts.append({'file': path, 'after_moment': i + 1, 'seconds': length})
    playlist = parts / 'concat.txt'
    playlist.write_text('\n'.join("file '" + p.name + "'" for p in entries), encoding='utf-8')
    target = folder / 'GAMING_HIGHLIGHTS.mp4'
    subprocess.run([exe, '-y', '-v', 'error', '-f', 'concat', '-safe', '1', '-i', str(playlist),
                    '-c', 'copy', '-movflags', '+faststart', str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    finished = open_video(target)
    if (finished.width, finished.height, finished.fps, finished.channels) != (width, height, video.fps, 2):
        raise ValueError('The completed highlight did not preserve source resolution, frame rate and stereo audio.')
    export_xml(folder / 'GAMING_SEQUENCE.xml', cuts, media)
    return target, receipts


def run(root, input_path, minutes=15, memes=True, device='cpu', progress=print):
    root = Path(root)
    device = heavy_device(root, device)
    minutes = int(minutes)
    if not 1 <= minutes <= 30:
        raise ValueError('Choose 1-30 target minutes for gaming highlights.')
    paths = [Path(input_path)] if Path(input_path).is_file() else sorted(
        p for p in Path(input_path).glob('*') if p.suffix.lower() in ('.mp4', '.mkv', '.mov', '.webm'))
    if not paths:
        raise ValueError('Attach your downloaded gaming stream.')
    output = root / 'output' / 'gaming' / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6])
    output.mkdir(parents=True)
    reports = []
    for index, path in enumerate(paths, 1):
        folder = output / f'{index:03d}-stream'
        folder.mkdir()
        video = open_video(path)
        cues = signals(root, video, progress)
        words = transcribe(root, video, device, progress,skip_invalid_recognition=True)
        brain = open_brain(root, progress=progress)
        brain.context_feature = 'gaming'
        try:
            picked = select(candidates(brain, words, video.duration, cues, progress), minutes * 60)
        finally:
            brain.close()
        if not picked:
            raise ValueError('No strong, complete gaming moments were found. Provide a speech-rich stream or timestamp notes.')
        from .gaming_lineage import capture_source, capture_highlights, write_new_record
        source_lineage = capture_source(path)
        lineage_parts = []
        target, assets = render(root, video, picked, folder, memes, progress, lineage_parts=lineage_parts, device=device)
        facts = open_video(target)
        lineage = capture_highlights(source_lineage, lineage_parts, target)
        write_new_record(folder / 'gaming-lineage.json', lineage)
        project = {'source': str(path.resolve()), 'source_seconds': video.duration, 'target_minutes': minutes,
                   'output_seconds': facts.duration, 'moments': picked, 'memes': assets,
                   'note': 'May be shorter than the target when few strong moments exist. Audio/visual cues are not event recognition.',
                   'video': str(target.resolve()), 'lineage':lineage,
                   'quality': {'passed': facts.duration > 0 and facts.channels == 2,
                    'checks': ['Source-bounded timestamps', 'No overlapping selected moments', 'Minimum score 6', 'Stereo audio']}}
        (folder / 'gaming-project.json').write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding='utf-8')
        rows = ''.join(f'<tr><td>{m["start"]:.1f}–{m["end"]:.1f}s</td><td>{html.escape(m["title"])}</td>'
                       f'<td>{m["score"]}/10</td><td>{html.escape(m["reason"])}</td></tr>' for m in picked)
        report = folder / 'report.html'
        report.write_text('<!doctype html><meta charset="utf-8"><title>Gaming highlights review</title>'
            '<style>body{background:#12161e;color:#eef1f8;font:16px system-ui;padding:32px}video{width:min(900px,100%)}'
            'td{padding:14px;border-bottom:1px solid #345}a{color:#72d3ff}</style><h1>Gaming highlights</h1>'
            f'<p>{video.duration/60:.1f} minutes → {facts.duration/60:.1f} minutes. Target: {minutes} minutes.</p>'
            '<video controls src="GAMING_HIGHLIGHTS.mp4"></video><p><a href="GAMING_SEQUENCE.xml">Editable timeline</a></p>'
            f'<p>{html.escape(project["note"])}</p><table>{rows}</table>', encoding='utf-8')
        reports.append(report)
    main = output / 'report.html'
    main.write_text('<!doctype html><meta charset="utf-8"><h1>Gaming stream results</h1>' + ''.join(
        '<p><a href="' + r.relative_to(output).as_posix() + '">Review stream ' + str(i + 1) + '</a></p>'
        for i, r in enumerate(reports)), encoding='utf-8')
    return main
