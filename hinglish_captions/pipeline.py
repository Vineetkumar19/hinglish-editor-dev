from dataclasses import replace
from datetime import datetime
from pathlib import Path
import json
import os
import shutil
import uuid

from hinglish_cut.media import EXTENSIONS
from hinglish_cut.xml_export import canvas_for
from hinglish_semantic.analysis import analyze_sources
from hinglish_semantic.core import SemanticSettings

from .core import build_cues, correct_with_reference, timed_words
from .project import write_project
from .renderer import render_overlay
from .report import write_index, write_report
from .styles import template
from .subtitles import write_ass, write_srt
from .xml_export import export_caption_xml


def _videos(folder):
    folder = Path(folder)
    if folder.is_file(): return [folder]
    return sorted((p for p in folder.rglob('*') if p.suffix.lower() in EXTENSIONS), key=lambda p: str(p).casefold())


def _link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try: os.link(source, target)
    except OSError: shutil.copyfile(source, target)


def run(root, input_path, style='flash_cut', device='cpu', output_format=None, progress=print,
        reference_script=''):
    root, input_path = Path(root), Path(input_path)
    template(style)
    paths = _videos(input_path)
    if not paths: raise ValueError('No supported videos were found')
    data = json.loads((root / 'config.phase2.json').read_text(encoding='utf-8-sig'))
    data.update(device=device, speech_backend='swift', matching_backend='word_coverage')
    settings = SemanticSettings(**data)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'captions' / stamp
    output.mkdir(parents=True)
    transcripts, _, errors = analyze_sources(paths, root, settings, progress)
    results = []
    for index, transcript in enumerate(transcripts, 1):
        media = transcript.media
        folder = output / f'{index:03d}-{Path(media.path).stem}'
        media_folder = folder / 'media'; media_folder.mkdir(parents=True)
        source_copy = media_folder / ('source' + Path(media.path).suffix.lower())
        _link(media.path, source_copy)
        media = replace(media, path=str(source_copy.resolve()))
        width, height = canvas_for(output_format, media)
        words = timed_words(transcript.words, media.duration)
        words, spelling_changes = correct_with_reference(words, reference_script)
        cues = build_cues(words, max_words=4 if height > width else 6, max_chars=28 if height > width else 46)
        if not cues:
            errors.append({'source': media.path, 'error': 'No speech could be transcribed'})
            continue
        folder.mkdir(parents=True, exist_ok=True)
        srt, ass = folder / 'captions.srt', folder / 'captions.ass'
        overlay, xml = media_folder / 'premium-captions.mov', folder / 'CAPTIONED_SEQUENCE.xml'
        write_srt(srt, cues); write_ass(ass, cues, style, width, height)
        render_overlay(overlay, cues, width, height, media.duration, media.rate, style, progress)
        export_caption_xml(xml, media, overlay, output_format, width, height)
        transcript_file = folder / 'transcript.txt'
        transcript_file.write_text(' '.join(w.text for w in words), encoding='utf-8')
        files = [('Open Premiere / Resolve XML', xml.name), ('Editable SRT', srt.name),
                 ('Styled ASS', ass.name), ('Roman Hinglish transcript', transcript_file.name)]
        project_file = folder / 'caption-project.json'
        source_relative = source_copy.relative_to(folder).as_posix()
        project = write_project(project_file, media, cues, style, output_format or 'source', source_relative,
                                spelling_changes, reference_script)
        write_report(folder / 'report.html', Path(media.path).name, source_relative, cues, style, files, project)
        results.append({'name': Path(media.path).name, 'folder': folder.name, 'cues': len(cues),
                        'style': template(style)['name'], 'xml': str(xml)})
    if not results:
        raise ValueError('Captions could not be created for any supplied video')
    write_index(output / 'index.html', results, errors)
    (output / 'result.json').write_text(json.dumps({'results': results, 'errors': errors}, indent=2), encoding='utf-8')
    return output
