from dataclasses import asdict
from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
import shutil
import time
import wave
import xml.etree.ElementTree as ET
from urllib.parse import quote

from hinglish_cut.media import (EXTENSIONS, fingerprint, prepare_media, extract_audio,
                               assemble_audio, SAMPLE_RATE)
from hinglish_cut.xml_export import export_xml, OUTPUT_FORMATS
from .detection import detect_blocks, plan_cuts, removed_ranges, verify_plan, write_json
from .render import render_mp4


def select_inputs(root, supplied=None):
    if supplied:
        folder = Path(supplied).resolve()
        paths = ([folder] if folder.is_file() and folder.suffix.lower() in EXTENSIONS else
                 sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS))
        if not paths:
            raise ValueError(f'No video files found: {folder}')
        return paths, None
    base = Path(root) / 'input' / 'phase1'
    active = []
    for name, fmt in [('videos', None), ('instagram-vertical', 'instagram_vertical'),
                      ('youtube-horizontal', 'youtube_horizontal')]:
        folder = base / name
        folder.mkdir(parents=True, exist_ok=True)
        paths = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
        if paths:
            active.append((paths, fmt))
    if len(active) > 1:
        raise ValueError('Put this batch in just ONE Phase 1 input folder: videos, instagram-vertical or youtube-horizontal.')
    if not active:
        raise ValueError(f'Put your videos in {base / "videos"}, then run Phase 1 again. No script needed.')
    return active[0]


def _portable_copy(source, destination):
    """Hard links keep exported XML usable even after input/cache cleanup."""
    try:
        os.link(source, destination)
    except OSError:
        shutil.copyfile(source, destination)


def _clean_clip_names(path):
    tree = ET.parse(path)
    for clip in tree.findall('.//clipitem'):
        name = clip.find('name')
        name.text = name.text.split(' | script ')[0] + ' | kept speech'
    ET.indent(tree, space='  ')
    data = ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)
    Path(path).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))


STYLE = '''body{font:17px system-ui;background:#f6f5f0;color:#18312b;max-width:980px;margin:40px auto;padding:0 22px}
h1{font-size:36px} .card{background:white;padding:24px;border-radius:14px;margin:18px 0}
video{width:100%;max-height:520px;background:#121817;border-radius:8px}a{color:#12624a}
button{background:#194e40;color:white;border:0;border-radius:6px;padding:9px 13px;cursor:pointer}
td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}table{width:100%;border-collapse:collapse}
.muted{color:#52645e} .stats{font-size:24px;font-weight:650} audio{width:100%} summary{cursor:pointer}
'''


def write_report(output, report):
    def stamp(seconds):
        return f'{int(seconds // 60):02d}:{seconds % 60:05.2f}'
    rows = ''.join(
        f'<tr><td>{stamp(d["start_seconds"])} - {stamp(d["end_seconds"])}</td>'
        f'<td>{d["end_seconds"] - d["start_seconds"]:.2f}s</td>'
        f'<td><button data-start="{max(0, d["start_seconds"] - .5)}" '
        f'data-end="{min(report["original_seconds"], d["end_seconds"] + .5)}">Listen around cut</button></td></tr>'
        for d in report['removed'])
    if report['cut_count']:
        video = ('<video controls preload="metadata" src="cleaned.mp4"></video>'
                 if report['mp4_created'] else '<p>MP4 export was skipped. Import timeline.xml into Premiere.</p>')
        result = f'''<div class="card"><h2>Your cleaned video</h2>{video}
        <p><a href="timeline.xml" download>Premiere XML</a> &nbsp; <a href="edit-decisions.json">Edit details</a></p>
        <p class="muted">Listen to the joins before publishing. Detection checks passed; this is not a human speech-accuracy guarantee.</p></div>'''
    else:
        result = '<div class="card"><h2>No speech detected</h2><p>No cleaned video or empty timeline was created. Check the original recording below. Quiet speech or music may need a different detection threshold.</p></div>'
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Phase 1 - {escape(report['source_name'])}</title><style>{STYLE}</style>
    <body><p>PHASE 1 / SILENCE REMOVAL</p><h1>{escape(report['source_name'])}</h1>
    <div class="stats">{stamp(report['original_seconds'])} original &nbsp; / &nbsp;
    {stamp(report['edited_seconds'])} edited &nbsp; / &nbsp; {report['removed_seconds']:.1f}s removed</div>
    {result}<div class="card"><h2>Original video</h2>
    <video id="original" controls preload="metadata" src="{escape(report['media_file'], quote=True)}"></video>
    <p>Use this to check a removed pause. Reopen the XML in Premiere to adjust any cut.</p></div>
    <div class="card"><details><summary>{len(report['removed'])} removed pauses - source timestamps</summary>
    <p>Reason: no speech detected in these intervals. Very short pauses and word-edge margins remain.</p>
    <table><thead><tr><th>Original time</th><th>Removed</th><th>Check</th></tr></thead><tbody>{rows}</tbody></table></details></div>
    <p class="muted">This build removes silence. Filler-word classification and retake selection are not enabled.
    Keep this entire output folder for future Premiere edits. The media subfolder contains the linked source.</p>
    <script>const p=document.querySelector('#original');let stopAt=null;
    document.querySelectorAll('button[data-start]').forEach(b=>b.addEventListener('click',()=>{{
    p.currentTime=Number(b.dataset.start);stopAt=Number(b.dataset.end);p.play().catch(()=>{{}});p.scrollIntoView({{behavior:'smooth',block:'center'}});}}));
    p.addEventListener('timeupdate',()=>{{if(stopAt!==null&&p.currentTime>=stopAt){{p.pause();stopAt=null;}}}});
    </script></body></html>'''
    (output / 'report.html').write_text(html, encoding='utf-8')


def clean_one(source, root, output, settings, output_format=None, mp4=True, progress=print, detector=None):
    started = time.monotonic()
    progress(f'Preparing {source.name}')
    digest = fingerprint(source)
    cache = root / 'cache' / 'phase1' / digest
    cache.mkdir(parents=True, exist_ok=True)
    prepared, note = prepare_media(source, root / 'cache' / 'conformed', progress)
    if prepared.channels > 2:
        raise ValueError('Phase 1 currently accepts mono or stereo recordings')
    # Include the prepared media version so a future orientation fix invalidates analysis.
    cache = cache / Path(prepared.path).stem
    cache.mkdir(parents=True, exist_ok=True)
    wav = cache / 'analysis.wav'
    valid_wav = False
    if wav.exists():
        with wave.open(str(wav), 'rb') as check:
            valid_wav = (check.getnframes() == round(prepared.duration * SAMPLE_RATE)
                         and check.getframerate() == SAMPLE_RATE and check.getnchannels() == 1)
    if not valid_wav:
        progress('  Reading audio')
        partial = cache / 'analysis.partial.wav'
        extract_audio(prepared, partial)
        partial.replace(wav)
    speech = detect_blocks(wav, prepared.duration, cache / 'speech', settings, detector, progress)
    cuts = plan_cuts(prepared, speech, settings)
    verify_plan(prepared, cuts, speech)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'media').mkdir()
    media_file = 'media/source' + Path(prepared.path).suffix.lower()
    _portable_copy(prepared.path, output / media_file)
    prepared.path = str((output / media_file).resolve())
    fps = float(prepared.rate)
    removed = removed_ranges(prepared, cuts) if cuts else []
    edited = sum(c.duration for c in cuts) / fps
    report = {
        'status': 'READY_FOR_REVIEW' if cuts else 'NO_SPEECH_DETECTED',
        'source_name': source.name, 'source_path': str(source.resolve()), 'source_sha256': digest,
        'media_file': media_file,
        'original_seconds': prepared.duration, 'edited_seconds': edited,
        'removed_seconds': sum(b - a for a, b in removed) / fps,
        'cut_count': len(cuts), 'mp4_created': False, 'output_format': output_format or 'source',
        'settings': asdict(settings), 'conform_note': note,
        'removed': [{'start_frame': a, 'end_frame': b, 'start_seconds': a / fps,
                     'end_seconds': b / fps, 'reason': 'no_speech_detected'} for a, b in removed],
        'checks': {'detected_speech_preserved': True, 'source_order_preserved': True,
                   'frame_bounds_valid': True, 'human_review_required': True},
    }
    write_json(output / 'edit-decisions.json', {'media': asdict(prepared), 'cuts': [asdict(c) for c in cuts],
               'speech': speech, 'removed': report['removed'], 'settings': asdict(settings),
               'source_sha256': digest, 'output_format': output_format})
    if cuts:
        export_xml(output / 'timeline.xml', cuts, {prepared.id: prepared}, output_format)
        _clean_clip_names(output / 'timeline.xml')
        assemble_audio(cuts, {prepared.id: prepared}, {prepared.id: wav}, output / 'review-audio.wav')
        if mp4:
            progress(f'  Keeping {edited:.1f}s, removing {report["removed_seconds"]:.1f}s. Saving MP4...')
            try:
                report['render'] = render_mp4(prepared, cuts, output / 'cleaned.mp4',
                                             OUTPUT_FORMATS.get(output_format), progress)
                report['mp4_created'] = True
            except Exception as error:
                report['status'] = 'MP4_FAILED_XML_READY'
                report['render_error'] = str(error)
                progress(f'  MP4 export failed: {error}. Premiere XML is available.')
    report['elapsed_seconds'] = round(time.monotonic() - started, 2)
    write_json(output / 'report.json', report)
    write_report(output, report)
    progress(f'  {report["status"]}: {output / "report.html"}')
    return report


def run(root, settings, supplied=None, output_format=None, mp4=True, progress=print):
    root = Path(root).resolve()
    paths, folder_format = select_inputs(root, supplied)
    fmt = folder_format if output_format is None else (None if output_format == 'source' else output_format)
    batch = root / 'output' / 'phase1' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    batch.mkdir(parents=True)
    entries = []
    for index, source in enumerate(paths, 1):
        progress(f'Video {index}/{len(paths)}')
        output = batch / f'{index:03d}-{source.stem}'
        try:
            report = clean_one(source, root, output, settings, fmt, mp4, progress)
            entries.append({'source': source.name, 'status': report['status'], 'folder': output.name})
        except Exception as error:
            progress(f'Could not process {source.name}: {error}')
            entries.append({'source': source.name, 'status': 'FAILED', 'error': str(error)})
        write_json(batch / 'batch.json', entries)
    links = ''.join(f'<li>{escape(e["source"])}: ' +
                    (f'<a href="{quote(e["folder"], safe="")}/report.html">{e["status"]}</a>' if 'folder' in e
                     else escape(e['error'])) + '</li>' for e in entries)
    (batch / 'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>Phase 1 results</title><style>{STYLE}</style>'
                                    f'<h1>Phase 1 results</h1><p>Each source video has its own cleaned edit.</p><ul>{links}</ul>', encoding='utf-8')
    return batch, entries
