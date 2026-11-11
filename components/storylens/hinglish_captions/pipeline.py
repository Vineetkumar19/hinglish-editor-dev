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


def run(root, input_path, style='caption_1', device='cpu', output_format=None, progress=print,
        reference_script='',caption_content='speech',preview=False,editable_only=False,
        analysis_audio=None):
    from hinglish_cut.compute_policy import heavy_device
    device=heavy_device(root,device)
    root, input_path = Path(root), Path(input_path)
    template(style)
    paths = _videos(input_path)
    if not paths: raise ValueError('No supported videos were found')
    if caption_content not in ('speech','lyrics'):raise ValueError('Choose speech captions or song lyrics')
    if analysis_audio is not None and len(paths)!=1:
        raise ValueError('Use one prepared reel with its saved analysis audio.')
    if editable_only and preview:raise ValueError('Editable-only captions do not include a rendered preview.')
    data = json.loads((root / 'config.phase2.json').read_text(encoding='utf-8-sig'))
    data.update(device=device, speech_backend='swift', matching_backend='word_coverage')
    settings = SemanticSettings(**data)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
    output = root / 'output' / 'captions' / stamp
    output.mkdir(parents=True)
    if caption_content=='lyrics':
        from hinglish_cut.media import prepare_media
        sources=[(prepare_media(path,root/'cache/conformed',progress)[0],None) for path in paths]
        errors=[]
    else:
        transcripts, _, errors = analyze_sources(paths, root, settings, progress,
                                                 predecoded_audio=analysis_audio)
        sources=[(transcript.media,transcript) for transcript in transcripts]
        # Speech VAD and the conversational recognizer can fail on singing.
        # Retry only rejected recognition, using the independent full-context
        # CUDA path. Its transcript and alignment checks remain mandatory.
        from hinglish_cut.media import prepare_media
        remaining_errors = []
        for error in errors:
            if error.get('reason') != 'invalid_recognition':
                remaining_errors.append(error)
                continue
            progress('  Speech recognizer returned invalid text; retrying the complete audio on NVIDIA RTX')
            retry_media = prepare_media(Path(error['source']), root/'cache/conformed', progress)[0]
            sources.append((retry_media, None))
        errors = remaining_errors
    results = []
    for index, (media,transcript) in enumerate(sources, 1):
        content_mode = 'lyrics' if transcript is None else caption_content
        folder = output / f'{index:03d}-{Path(media.path).stem}'
        media_folder = folder / 'media'; media_folder.mkdir(parents=True)
        source_copy = media_folder / ('source' + Path(media.path).suffix.lower())
        _link(media.path, source_copy)
        media = replace(media, path=str(source_copy.resolve()))
        width, height = canvas_for(output_format, media)
        if content_mode=='lyrics':
            from .lyrics import transcribe_song
            cues,transcription=transcribe_song(root,media,reference_script,device,progress,
                                               analysis_audio=analysis_audio)
            if caption_content != content_mode:
                transcription['fallback_from'] = 'speech'
                transcription['fallback_reason'] = 'invalid_recognition'
            words=[word for cue in cues for word in cue.words]
            spelling_changes=[]
        else:
            words = timed_words(transcript.words, media.duration)
            from hinglish_cut.recognition_quality import checked_transcript
            checked_transcript(' '.join(word.text for word in words))
            from hinglish_publish.memory import correct_words
            words, spelling_changes = correct_with_reference(words, reference_script)
            words, learned_changes = correct_words(root, words, reference_script)
            spelling_changes = learned_changes + spelling_changes
            from hinglish_visuals.brain import open_brain
            from .proofread import review as review_spelling
            from .audio_evidence import collect
            evidence=collect(root,media,words,[(0,media.duration)],progress,
                             device_override=device if editable_only else None)
            caption_brain=open_brain(root,'ollama' if editable_only and device=='cuda' else 'auto',progress=progress)
            try:words,local_changes=review_spelling(caption_brain,words,progress,evidence=evidence)
            finally:caption_brain.close()
            spelling_changes+=local_changes
            transcription={'mode':'speech','device':device,'warnings':transcript.issues,
                           'accuracy_scope':'Layout and transcript coverage checks do not certify recognition accuracy.'}
        # A caption is a visual beat, not a transcript paragraph. Portrait layouts
        # stay tighter; every other layout is still strictly capped at five words.
        if content_mode!='lyrics':
            from .numbers import digits
            words=digits(words)
            cues = build_cues(words, max_words=template(style).get('max_words', 4 if height > width else 5),
                               max_chars=52 if style=='caption_1' else (28 if height > width else 34))
        from .template_patterns import bind_patterns
        cues=bind_patterns(cues)
        if style=='caption_1':
            from .caption_one import paginate_cues
            cues=paginate_cues(cues)
        elif style in ('caption_3','caption_4','caption_5'):
            if style=='caption_5':
                from .caption_five import paginate_cues
            elif style=='caption_4':
                from .caption_four import paginate_cues
            else:
                from .caption_three import paginate_cues
            cues=paginate_cues(cues)
        if not cues:
            errors.append({'source': media.path, 'error': 'No speech could be transcribed'})
            continue
        folder.mkdir(parents=True, exist_ok=True)
        srt, ass = folder / 'captions.srt', folder / 'captions.ass'
        overlay, xml = media_folder / 'premium-captions.mov', folder / 'CAPTIONED_SEQUENCE.xml'
        selected_style=template(style)
        visibility=selected_style.get('word_visibility') or ('styled_spoken' if selected_style.get('layout') else ('spoken' if content_mode=='lyrics' else 'phrase'))
        position=selected_style.get('default_position',.70)
        write_srt(srt,cues,visibility);write_ass(ass,cues,style,width,height,position=position,word_visibility=visibility)
        # Save editable captions before a GPU-only format restriction can stop export.
        project_file=folder/'caption-project.json'
        write_project(project_file,media,cues,style,output_format or 'source',source_copy.relative_to(folder).as_posix(),
                      spelling_changes,reference_script,position=position)
        if not editable_only:
            render_overlay(overlay,cues,width,height,media.duration,media.rate,style,progress,position=position,word_visibility=visibility,device=device)
            export_caption_xml(xml, media, overlay, output_format, width, height)
        else:
            progress('  Editable captions ready; no caption video render is needed for After Effects')
        transcript_file = folder / 'transcript.txt'
        transcript_file.write_text(' '.join(w.text for w in words), encoding='utf-8')
        files = ([] if editable_only else [('Open Premiere / Resolve XML', xml.name)]) + [
            ('Editable SRT', srt.name), ('Styled ASS', ass.name),
            ('Roman Hinglish transcript', transcript_file.name)]
        project_file = folder / 'caption-project.json'
        source_relative = source_copy.relative_to(folder).as_posix()
        project = write_project(project_file, media, cues, style, output_format or 'source', source_relative,
                                spelling_changes, reference_script,position=position)
        project.update(caption_content=content_mode,transcription=transcription,word_visibility=visibility)
        if preview:
            from .export_video import render_captioned_video
            progress('  Encoding the captioned video with NVIDIA RTX' if device=='cuda' else '  Encoding the captioned video')
            project['video_encoder']=render_captioned_video(source_copy,overlay,folder/'captioned-preview.mp4',device)
            files.append(('Captioned MP4','captioned-preview.mp4'))
        project_file.write_text(json.dumps(project,indent=2,ensure_ascii=False),encoding='utf-8')
        write_report(folder / 'report.html', Path(media.path).name, source_relative, cues, style, files, project)
        results.append({'name': Path(media.path).name, 'folder': folder.name, 'cues': len(cues),
                        'style': template(style)['name'], 'xml': None if editable_only else str(xml),
                        'caption_content':content_mode,'transcription':transcription,
                        'preview':str(folder/'captioned-preview.mp4') if preview else None})
    if not results:
        raise ValueError('Captions could not be created. '+('; '.join(error['error'] for error in errors) or 'No usable transcription.'))
    write_index(output / 'index.html', results, errors)
    (output / 'result.json').write_text(json.dumps({'results': results, 'errors': errors}, indent=2), encoding='utf-8')
    return output
