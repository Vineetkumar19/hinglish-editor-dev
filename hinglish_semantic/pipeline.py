from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil

from hinglish_clean.detection import write_json
from hinglish_clean.pipeline import _portable_copy
from hinglish_clean.render import render_mp4
from hinglish_cut.backends import LocalSpeech
from hinglish_cut.cutting import make_cuts, selection_limits, constrain_cuts
from hinglish_cut.media import EXTENSIONS, assemble_audio, fingerprint
from hinglish_cut.model import Media, Word, Transcript, Selection, Cut
from hinglish_cut.xml_export import export_xml, OUTPUT_FORMATS

from .analysis import analyze_sources
from .assembly import retrieve, verify_candidates, select
from .cleanup import assess_cleanup, cleanup_cuts, verify_cleanup_audio
from .core import SemanticSettings, Span, script_ideas, fact_concerns, verified, spans_for
from .models import Verifier, Embedder
from .report import write_report


def inputs(root, mode, supplied=None):
    if supplied:
        p = Path(supplied).resolve()
        paths = ([p] if p.is_file() and p.suffix.lower() in EXTENSIONS else
                 sorted(x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in EXTENSIONS))
        if not paths: raise ValueError('No input video files found')
        return paths, None
    if mode == 'clean-plus':
        from hinglish_clean.pipeline import select_inputs
        return select_inputs(root)
    active = []
    for name, fmt in [('videos', None), ('instagram-vertical', 'instagram_vertical'), ('youtube-horizontal', 'youtube_horizontal')]:
        folder = Path(root) / 'input' / 'phase2' / name
        folder.mkdir(parents=True, exist_ok=True)
        paths = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
        if paths: active.append((paths, fmt))
    if len(active) != 1:
        raise ValueError('Put your Phase 2 videos in ONE folder: input/phase2/videos, instagram-vertical or youtube-horizontal')
    return active[0]


def portable_sources(output, transcripts, wavs):
    (output / 'media').mkdir(parents=True, exist_ok=True)
    local_wavs = {}
    for t in transcripts:
        destination = output / 'media' / (t.media.id + Path(t.media.path).suffix)
        _portable_copy(t.media.path, destination)
        t.media.path = str(destination.resolve())
        audio = output / 'media' / (t.media.id + '.wav')
        _portable_copy(wavs[t.media.id], audio)
        local_wavs[t.media.id] = audio
    return local_wavs


def new_output(root, mode):
    out = Path(root) / 'output' / mode / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True, exist_ok=False)
    return out


def save_project(output, settings, kind, transcripts, wavs, **details):
    project = {'schema': 'hinglish-semantic-1', 'kind': kind, 'settings': asdict(settings),
               'transcripts': [asdict(t) for t in transcripts],
               'audio_paths': {k: str(Path(v).resolve()) for k, v in wavs.items()}, **details}
    if settings.matching_backend == 'meaning':
        from .setup_meaning import JUDGE_REPO, JUDGE_REVISION, RUNTIME_TAG
        project['meaning_model'] = {'repo': JUDGE_REPO, 'revision': JUDGE_REVISION, 'runtime': RUNTIME_TAG}
    write_json(output / 'project.json', project)
    return project


def serialize_rows(rows):
    saved = []
    for row in rows:
        def convert(c):
            return {**c, 'span': asdict(c['span'])} if c else None
        saved.append({**row, 'selected': convert(row['selected']),
                      'selected_id': row['selected']['span'].id if row['selected'] else None,
                      'alternatives': [convert(c) for c in row['alternatives']]})
    return saved


def selection_cuts(rows, transcripts, settings):
    by_id = {t.media.id: t for t in transcripts}
    selections = []
    for row in rows:
        c = row.get('selected')
        span = c['span'] if c else None
        selections.append(Selection(row['index'], row['idea'], span.media_id if span else None,
                                    span.first if span else 0, span.last if span else 0))
    limits = selection_limits(selections, by_id)
    all_cuts = []
    per_line = {}
    for s in selections:
        if s.media_id is None:
            continue
        t = by_id[s.media_id]
        keep_pauses = bool(rows[s.line_index].get('preserve_pauses'))
        cuts = constrain_cuts(make_cuts(t, s.first_word, s.last_word, settings.speech_settings(), s.line_index,
                                       conservative=keep_pauses), limits[s.line_index])
        all_cuts.extend(cuts)
        per_line[s.line_index] = cuts
    # Source frame reuse is a hard export error, independent of semantic scores.
    for i, a in enumerate(all_cuts):
        if any(a.media_id == b.media_id and max(a.start_frame, b.start_frame) < min(a.end_frame, b.end_frame) for b in all_cuts[i + 1:]):
            raise ValueError('Selection reuses source frames. Choose non-overlapping takes.')
    return all_cuts, per_line


def emit_assembly(output, rows, transcripts, wavs, settings, fmt, errors, progress=print, replay=True, root=None, reviewed=False):
    media = {t.media.id: t.media for t in transcripts}
    cuts, per_line = selection_cuts(rows, transcripts, settings)
    preview = output / 'review-audio'
    preview.mkdir(exist_ok=True)
    engine = None
    replay_jobs = []
    try:
        for row in rows:
            if row['index'] not in per_line:
                continue
            name = f'idea-{row["index"] + 1:04d}.wav'
            assemble_audio(per_line[row['index']], media, wavs, preview / name)
            row['edited_audio'] = 'review-audio/' + name
            if replay:
                progress(f'Checking edited audio: idea {row["index"] + 1}/{len(rows)}')
                if engine is None: engine = LocalSpeech(settings.speech_settings(), Path(root) / 'models')
                try:
                    actual = engine.transcribe_cut(preview / name)
                    row['heard_after'] = actual
                    replay_jobs.append((row, actual))
                except Exception as error:
                    row['issues'].append('edited_audio_check_failed:' + str(error))
    finally:
        if engine: engine.close()
    verifier = Verifier(settings, root or output)
    try:
        for row, actual in replay_jobs:
            progress(f'Verifying edited meaning: idea {row["index"] + 1}/{len(rows)}')
            try:
                expected = row['selected']['span'].text
                result = verifier.check('preservation', expected=expected, spoken=actual)
                row['edited_verdict'] = result
                concerns = fact_concerns(expected, actual, settings.protected_terms)
                if not verified(result, settings) or concerns:
                    row['issues'].append('edited_meaning_needs_review')
                    row['issues'].extend(concerns)
            except Exception as error:
                row['issues'].append('edited_verifier_unavailable:' + str(error))
    finally:
        verifier.close()
    # If the cut's replay is uncertain, restore the whole selected utterance.
    # It remains a draft until reviewed; do not label the restored audio verified.
    restored = False
    for row in rows:
        if any(issue.startswith(('edited_meaning', 'edited_verifier', 'edited_audio_check')) for issue in row['issues']):
            row['preserve_pauses'] = True
            row['issues'].append('pauses_restored_review_required')
            restored = True
    if restored:
        cuts, per_line = selection_cuts(rows, transcripts, settings)
        for row in rows:
            if row.get('preserve_pauses') and row['index'] in per_line:
                assemble_audio(per_line[row['index']], media, wavs, output / row['edited_audio'])
                row['pre_restore_transcript'] = row.pop('heard_after', '')
                row['restored_audio_verified'] = False
    # All alternatives have a real source-time preview, even if not auto-selected.
    for row in rows:
        for c in row['alternatives']:
            span = c['span']
            m = media[span.media_id]
            c.setdefault('source_name', Path(m.path).name)
            key = hashlib.sha256(span.id.encode()).hexdigest()[:16]
            file = preview / f'option-{key}.wav'
            if not file.exists():
                a = max(0, math.floor((span.start - .08) * float(m.rate)))
                b = min(math.floor(m.duration * float(m.rate) + 1e-6), math.ceil((span.end + .12) * float(m.rate)))
                assemble_audio([Cut(m.id, a, b, row['index'])], media, wavs, file)
            c['preview'] = 'review-audio/' + file.name
    status = 'REVIEW_REQUIRED' if errors or any(r['issues'] for r in rows) else 'MEANING_CHECKS_PASSED_REVIEW_RECOMMENDED'
    used = [r['selected']['span'] for r in rows if r.get('selected')]
    unused = []
    for t in transcripts:
        for span in spans_for(t, combined=False):
            if not any(s.media_id == span.media_id and max(s.first, span.first) < min(s.last, span.last) for s in used):
                unused.append({'text': span.text, 'start': span.start, 'end': span.end,
                               'source': Path(t.media.path).relative_to(output).as_posix()})
    if cuts:
        export_xml(output / ('reviewed.xml' if reviewed else 'draft.xml'), cuts, media, fmt)
        if status == 'MEANING_CHECKS_PASSED_REVIEW_RECOMMENDED':
            export_xml(output / 'timeline.xml', cuts, media, fmt)
        assemble_audio(cuts, media, wavs, output / 'full-timeline.wav')
    report = {'kind': 'assemble', 'status': status, 'rows': serialize_rows(rows), 'errors': errors, 'unused_sections': unused,
              'duration_seconds': sum(c.duration / float(media[c.media_id].rate) for c in cuts), 'cut_count': len(cuts)}
    project = save_project(output, settings, 'assemble', transcripts, wavs,
                           rows=report['rows'], output_format=fmt, errors=errors)
    write_json(output / 'edit-decisions.json', {'cuts': [asdict(c) for c in cuts], 'media': {k: asdict(v) for k, v in media.items()}})
    write_json(output / 'report.json', report)
    write_report(output, report, project)
    return report


def run_assembly(root, settings, supplied=None, script=None, output_format=None, progress=print):
    root = Path(root).resolve()
    paths, fmt = inputs(root, 'assemble', supplied)
    script = Path(script) if script else root / 'input' / 'phase2' / 'script.txt'
    if not script.exists(): raise ValueError(f'Add your script or outline: {script}')
    script_text = script.read_text(encoding='utf-8-sig')
    lines = script_ideas(script_text)
    if not lines: raise ValueError('The Phase 2 script is empty')
    if any(len(line.split()) > 100 for line in lines):
        raise ValueError('Put one idea per line (up to 100 words). Split long paragraphs into several ideas.')
    transcripts, wavs, errors = analyze_sources(paths, root, settings, progress)
    if not transcripts:
        raise ValueError('No usable source videos. ' + str(errors))
    from .coverage import arrange_paragraphs
    from .paragraph_export import emit_paragraphs
    encoder = Embedder(settings, root)
    try:
        if settings.matching_backend == 'meaning':
            from .local_judge import MeaningJudge
            from .meaning import arrange_meaning
            judge = MeaningJudge(settings, root)
            try:
                rows = arrange_meaning(script_text, transcripts, settings, encoder, judge, progress)
            finally:
                judge.close()
        else:
            rows = arrange_paragraphs(script_text, transcripts, settings, encoder, progress)
    finally:
        encoder.close()
    output = new_output(root, 'phase2')
    wavs = portable_sources(output, transcripts, wavs)
    if output_format: fmt = None if output_format == 'source' else output_format
    # Source-sized assembly uses the first source's canvas, with fit transforms on
    # every source to prevent native-size zoom when cameras have different sizes.
    if fmt is None and transcripts:
        m = transcripts[0].media
        fmt = 'instagram_vertical' if m.height > m.width else 'youtube_horizontal'
    # Keep the selected source timings even if later rendering fails, so review
    # recovery does not require another model run.
    save_project(output, settings, 'assemble', transcripts, wavs, rows=serialize_rows(rows),
                 output_format=fmt, errors=errors, assembly_version='paragraph-coverage-2')
    report = emit_paragraphs(output, rows, transcripts, wavs, settings, fmt, errors, root, progress)
    missing = [r['idea'] for r in rows if not r.get('selected')]
    if missing:
        progress(f'INCOMPLETE DRAFT: {len(missing)} script sections need a source take in the review page:')
        for idea in missing: progress('  ' + idea)
    uncertain = [r['idea'] for r in rows if r.get('selection_status') == 'unverified_context_passage']
    if uncertain:
        progress(f'LISTENING REVIEW: {len(uncertain)} nearby source passages were included with uncertain transcripts:')
        for idea in uncertain: progress('  ' + idea)
    progress(f'{report["status"]}: {output / "report.html"}')
    return output, report


def emit_cleanup(output, transcript, wavs, settings, fmt, proposals, errors, progress=print, reviewed=False):
    base, cuts = cleanup_cuts(transcript, settings, proposals)
    media = {transcript.media.id: transcript.media}
    for p in proposals:
        first = max(0, p['first'] - 5)
        last = min(len(transcript.words), p['last'] + 5)
        before = make_cuts(transcript, first, last, settings.speech_settings(), conservative=True)
        name = 'before-' + p['id'].replace(':', '-') + '.wav'
        assemble_audio(before, media, wavs, output / name)
        p['before_preview'] = name
    if cuts:
        export_xml(output / ('reviewed.xml' if reviewed else 'draft.xml'), cuts, media, fmt)
        render_mp4(transcript.media, cuts, output / 'cleaned.mp4', OUTPUT_FORMATS.get(fmt), progress)
        assemble_audio(cuts, media, wavs, output / 'full-timeline.wav')
    report = {'kind': 'clean-plus', 'status': 'REVIEW_REQUIRED', 'proposals': proposals,
              'source_video': Path(transcript.media.path).relative_to(output).as_posix(),
              'errors': errors + transcript.issues, 'cut_count': len(cuts),
              'original_seconds': transcript.media.duration,
              'edited_seconds': sum(c.duration for c in cuts) / float(transcript.media.rate),
              'removed_fillers': sum(p['kind'] == 'filler' and p.get('approved', False) for p in proposals),
              'removed_retakes': sum(p['kind'] == 'retake' and p.get('approved', False) for p in proposals)}
    project = save_project(output, settings, 'clean-plus', [transcript], wavs, proposals=proposals, output_format=fmt, errors=errors)
    write_json(output / 'edit-decisions.json', {'cuts': [asdict(c) for c in cuts], 'base_cuts': [asdict(c) for c in base], 'media': asdict(transcript.media)})
    write_json(output / 'report.json', report)
    write_report(output, report, project)
    return report


def run_cleanup(root, settings, supplied=None, output_format=None, progress=print):
    root = Path(root).resolve()
    paths, fmt = inputs(root, 'clean-plus', supplied)
    if output_format: fmt = None if output_format == 'source' else output_format
    transcripts, wavs, errors = analyze_sources(paths, root, settings, progress)
    batch = new_output(root, 'clean-plus')
    entries = []
    semantic_scores = {}
    encoder = None
    try:
        for t in transcripts:
            spans = spans_for(t, combined=False)
            if len(spans) < 2:
                continue
            if encoder is None: encoder = Embedder(settings, root)
            vectors = encoder.encode([s.text for s in spans], progress)
            for i, a in enumerate(spans):
                for j in range(i + 1, min(len(spans), i + 4)):
                    b = spans[j]
                    if b.start - a.end <= settings.retake_window:
                        semantic_scores[a.id, b.id] = float(vectors[i] @ vectors[j])
    finally:
        if encoder: encoder.close()
    verifier = Verifier(settings, root)
    engine = None
    try:
        for n, transcript in enumerate(transcripts, 1):
            output = batch / f'{n:03d}'
            output.mkdir()
            local_wavs = portable_sources(output, [transcript], wavs)
            proposals = assess_cleanup(transcript, settings, verifier, progress, semantic_scores)
            if any(p.get('approved') for p in proposals):
                engine = LocalSpeech(settings.speech_settings(), root / 'models')
                verify_cleanup_audio(transcript, proposals, local_wavs[transcript.media.id], output,
                                     settings, engine.transcribe_cut, verifier, progress)
                engine.close()
                engine = None
            report = emit_cleanup(output, transcript, local_wavs, settings, fmt, proposals, errors, progress)
            entries.append({'output': str(output), 'report': report})
            progress(f'Clean+ review: {output / "report.html"}')
    finally:
        verifier.close()
        if engine: engine.close()
    write_json(batch / 'batch.json', {'entries': entries, 'errors': errors})
    from html import escape
    (batch / 'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>Clean+ results</h1>'
            + ''.join(f'<p><a href="{Path(e["output"]).name}/report.html">Video {i + 1}</a></p>' for i, e in enumerate(entries))
            + '<pre>' + escape(json.dumps(errors, indent=2)) + '</pre>', encoding='utf-8')
    return batch, {'status': 'REVIEW_REQUIRED', 'entries': entries, 'errors': errors}


def apply_choices(root, path, progress=print):
    choices = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    project_path = Path(choices['project']).resolve()
    # Only this app's generated project manifests are accepted. No commands from
    # downloaded choice files are executed and outputs are always fresh folders.
    root = Path(root).resolve()
    if not project_path.is_relative_to(root / 'output'):
        raise ValueError('Choose a review project inside this app output folder')
    project = json.loads(project_path.read_text(encoding='utf-8'))
    if project.get('schema') != 'hinglish-semantic-1' or choices.get('kind') != project['kind']:
        raise ValueError('This is not a compatible review file')
    settings = SemanticSettings(**project['settings'])
    transcripts = [Transcript(Media(**t['media']), [Word(**w) for w in t['words']], t['speech'], t['issues']) for t in project['transcripts']]
    wavs = {k: Path(v) for k, v in project['audio_paths'].items()}
    output = new_output(root, 'phase2-reviewed' if project['kind'] == 'assemble' else 'clean-plus-reviewed')
    wavs = portable_sources(output, transcripts, wavs)
    if project['kind'] == 'assemble':
        rows = project['rows']
        for row in rows:
            for c in row['alternatives']: c['span'] = Span(**c['span'])
            selected_id = choices.get('choices', {}).get(str(row['index']), row.get('selected_id'))
            candidate = next((c for c in row['alternatives'] if c['span'].id == selected_id), None)
            if selected_id and candidate is None: raise ValueError('Unknown source choice')
            row['selected'] = candidate
            row['issues'] = ['manually_selected_review_required'] if candidate else ['no_match_selected']
        from .learning import LearningMemory
        learned = LearningMemory(root).record_review(rows, choices.get('choices', {}), project_path)
        progress(f'Learning memory updated from {learned} reviewed decisions')
        if project.get('assembly_version') == 'paragraph-coverage-2':
            from .paragraph_export import emit_paragraphs
            report = emit_paragraphs(output, rows, transcripts, wavs, settings, project['output_format'],
                                     project['errors'], root, progress, replay=False)
        else:
            report = emit_assembly(output, rows, transcripts, wavs, settings, project['output_format'], project['errors'],
                                   progress, replay=False, root=root, reviewed=True)
    else:
        proposals = project['proposals']
        wanted = set(choices.get('remove', []))
        if wanted - {p['id'] for p in proposals}: raise ValueError('Unknown removal choice')
        for p in proposals:
            p['approved'] = p['id'] in wanted
            if p['approved'] and not p.get('bounds'): raise ValueError('Cannot cut an unaligned word safely')
            p['review_reason'] = 'Manually reviewed'
            p.pop('preview', None)
        report = emit_cleanup(output, transcripts[0], wavs, settings, project['output_format'], proposals, project['errors'], progress, reviewed=True)
    progress(f'Reviewed output: {output / "report.html"}')
    return output, report
