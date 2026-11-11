"""Export complete paragraph assemblies without treating a model score as proof."""
from dataclasses import asdict, replace
from fractions import Fraction
from html import escape
import hashlib
import json
import math
from pathlib import Path

from hinglish_cut.model import Cut, Selection
from hinglish_cut.cutting import selection_limits, constrain_cuts, merge_ranges
from hinglish_cut.media import assemble_audio
from hinglish_cut.xml_export import export_xml, OUTPUT_FORMATS
from hinglish_clean.detection import write_json
from hinglish_clean.pipeline import STYLE
from .core import cleanup_proposals, subtract_ranges, safe_filler_word
from .preview import render_preview
from .pacing import paced_spans, handles


def cuts_for_rows(rows, transcripts, settings):
    by_id = {t.media.id: t for t in transcripts}
    effective = paced_spans(rows, transcripts, settings.pacing)
    selected_rows = [r for r in rows if r.get('selected')]
    selections = []
    for row in rows:
        if row['selected']:
            s = effective[row['index']]
            selections.append(Selection(row['index'], row['idea'], s.media_id, s.first, s.last))
    limits = selection_limits(selections, by_id)
    # Word timestamps are continuous; the XML can cut only on whole frames.
    # Two touching words (e.g. 4.38s at 30 fps) otherwise round outwards to
    # overlapping frames. Share one nearest-frame boundary for sub-frame gaps.
    for media_id, t in by_id.items():
        ordered = sorted((s for s in selections if s.media_id == media_id), key=lambda s: s.first_word)
        fps = float(t.media.rate)
        for left, right in zip(ordered, ordered[1:]):
            a, b = t.words[left.last_word - 1].end, t.words[right.first_word].start
            if left.last_word <= right.first_word and -1 / fps <= b - a < 1 / fps:
                boundary = round((a + b) * fps / 2)
                limits[left.line_index][1] = min(limits[left.line_index][1], boundary)
                limits[right.line_index][0] = max(limits[right.line_index][0], boundary)
    all_cuts, per_row = [], {}
    for row in rows:
        if not row['selected']: continue
        s = effective[row['index']]
        t = by_id[s.media_id]
        fps = float(t.media.rate)
        lead, tail, min_silence = handles(row, selected_rows, settings.pacing)
        low, high = max(0, s.start - lead), min(t.media.duration, s.end + tail)
        # Longer handles must not bring back discarded takes or neighboring
        # words. Keep room tone/breaths only within the unused source gap.
        if s.first:
            low = max(low, min(s.start, t.words[s.first - 1].end + .025))
        if s.last < len(t.words):
            high = min(high, max(s.end, t.words[s.last].start - .025))
        regions = [(w.start, w.end) for w in t.words[s.first:s.last]]
        regions += [(max(low, a), min(high, b)) for a, b in t.speech if a < high and b > low]
        groups = merge_ranges(regions, min_silence)
        ranges = merge_ranges([(max(low, a - lead), min(high, b + tail)) for a, b in groups])
        cuts = [Cut(s.media_id, max(0, math.floor(a * fps)), min(math.floor(t.media.duration * fps + 1e-6), math.ceil(b * fps)), row['index'])
                for a, b in ranges]
        cuts = constrain_cuts(cuts, limits[row['index']])
        # Only timed, isolated hesitation tokens qualify. "Oh"/"shh" are kept.
        fillers = [p for p in cleanup_proposals(t, settings) if p['kind'] == 'filler'
                   and p['eligible'] and s.first <= p['first'] and p['last'] <= s.last and safe_filler_word(p['text'])]
        cuts = subtract_ranges(cuts, [p['bounds'] for p in fillers])
        row['filler_removals'] = fillers
        per_row[row['index']] = cuts
        all_cuts.extend(cuts)
    used = {}
    for c in all_cuts:
        previous = used.setdefault(c.media_id, [])
        if any(max(c.start_frame, a) < min(c.end_frame, b) for a, b in previous):
            raise ValueError(f'Conflicting source timing in sentence {c.line_index + 1} '
                             f'({Path(by_id[c.media_id].media.path).name}). '
                             'Choose a different take in the review; model downloads cannot fix this.')
        previous.append((c.start_frame, c.end_frame))
    return all_cuts, per_row


def write_paragraph_page(output, report):
    issue_labels = {
        'quantity_unclear_in_transcript_listen_before_export': 'The spoken amount is unclear in the transcript. Listen to confirm it.',
        'timing_needs_listening_check': 'Check that the beginning and ending of this phrase sound complete.',
        'alternative_occurrence_available': 'Another take may fit; compare the alternatives.',
        'sentence_not_matched': 'This script idea has no confirmed spoken match.'}
    cards = []
    for paragraph in report['paragraphs']:
        details = []
        for row in paragraph['rows']:
            selected = row.get('selected')
            parts = [f'<h3>{escape(row["idea"])}</h3>']
            if selected:
                s = selected['span']
                parts.append(f'<p>{escape(selected["source_name"])} · {s["start"]:.2f}–{s["end"]:.2f}s</p>'
                             f'<p>Transcribed from video: {escape(row.get("cut_text", s["text"]))}</p>')
            else:
                parts.append('<p class="concern">No complete source match for this sentence.</p>')
            if row['issues']:
                parts.append('<p class="concern">' + escape(' '.join(issue_labels.get(x, x) for x in row['issues'])) + '</p>')
            if row.get('edited_audio'):
                parts.append(f'<audio controls preload="none" src="{row["edited_audio"]}"></audio>')
            choices = [f'<label><input type="radio" name="idea-{row["index"]}" value="" {"checked" if not selected else ""}> Leave unmatched</label>']
            for c in row['alternatives']:
                s = c['span']
                checked = 'checked' if selected and s['id'] == selected['span']['id'] else ''
                choices.append(f'<label><input type="radio" name="idea-{row["index"]}" value="{escape(s["id"], quote=True)}" {checked}>'
                               f'{escape(c["source_name"])} {s["start"]:.2f}–{s["end"]:.2f}s</label><p>{escape(s["text"])}</p>'
                               f'<audio controls preload="none" src="{c["preview"]}"></audio>')
            parts.append('<details><summary>Other takes</summary>' + ''.join(choices) + '</details>')
            details.append('<div class="part">' + ''.join(parts) + '</div>')
        replay_note = (f'<p class="concern">{escape(paragraph["review"])}</p>' if paragraph.get('review') else '')
        replay_text = (f'<p>Heard after cutting (automatic transcript): {escape(paragraph["heard_after"])}</p>'
                       if paragraph.get('heard_after') else '')
        cards.append(f'<section class="card"><h2>Paragraph {paragraph["index"] + 1}</h2><p>{escape(paragraph["text"])}</p>'
                     f'<p>{paragraph["placed"]}/{len(paragraph["rows"])} sentences placed</p>'
                     + replay_note + replay_text +
                     f'<audio controls preload="none" src="{paragraph["audio"]}"></audio>'
                     '<details><summary>Sentences, source timings and alternative takes</summary>' + ''.join(details) + '</details></section>')
    payload = json.dumps({'project': str((output / 'project.json').resolve()), 'kind': 'assemble'}).replace('<', '\\u003c')
    preview = '<video controls preload="metadata" src="preview.mp4"></video>' if (output / 'preview.mp4').exists() else ''
    links = []
    if (output / 'EDITED_SEQUENCE.xml').exists(): links.append('<a href="EDITED_SEQUENCE.xml" download>Download Premiere XML</a>')
    if preview: links.append('<a href="preview.mp4" download>Download video preview</a>')
    errors = ''.join(f'<p class="concern">{escape(str(e))}</p>' for e in report['errors'])
    missing = [r for r in report['rows'] if not r.get('selected')]
    if missing:
        errors += ('<section class="card concern"><h2>Incomplete draft: '
                   + str(len(missing)) + ' script sections need a take</h2><p>'
                   + escape(' / '.join(r['idea'] for r in missing))
                   + '</p><p>These sections are absent from the XML and video. '
                     'Choose their source takes below before exporting the finished video.</p></section>')
    uncertain = [r for r in report['rows'] if r.get('selection_status') == 'unverified_context_passage']
    if uncertain:
        errors += ('<section class="card concern"><h2>' + str(len(uncertain))
                   + ' included passages need listening review</h2><p>'
                   + escape(' / '.join(r['idea'] for r in uncertain))
                   + '</p><p>Speech recognition was uncertain. Nearby source passages were kept in the draft; '
                     'their meaning has NOT been verified. Listen and keep or change these takes below.</p></section>')
    (output / 'report.html').write_text(f'''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Edited sequence</title><style>{STYLE}.part{{border-top:1px solid #ddd;padding:12px 0}}.concern{{color:#8c4f00}}label{{display:block}}video{{max-height:600px}}</style>
    <body><h1>Your script — assembled by sentence</h1>
    <p>{report['placed_sentences']}/{report['sentence_count']} sentences placed · {report['duration_seconds']:.1f}s · {report['cut_count']} timeline clips</p>
    <p>Pacing: {escape(report.get('pacing', 'tight'))}. Original speaking speed; natural source pauses retained where available.</p>
    <p>{' · '.join(links)}</p>{errors}
    <p>Import EDITED_SEQUENCE.xml into Premiere, then double-click the sequence named EDITED_SEQUENCE.</p>
    <p>Listen to the result. Transcript spelling can be wrong; a placed sentence is not a guarantee of correct meaning.</p>
    <p>Only recognized, timed hesitation sounds can be removed. Sounds missed by transcription still need listening review.</p>{preview}
    {''.join(cards)}<section class="card"><h2>Save changed takes</h2><p>Choose alternatives above, save this file, then drag it onto Apply Reviewed Choices.bat.</p>
    <p>When you apply this review file, your approved and rejected takes are saved locally and help future similar edits.</p>
    <button id="save">Save reviewed choices</button></section>
    <script>document.querySelector('#save').onclick=()=>{{const data={payload};data.choices={{}};
    document.querySelectorAll('input[type=radio]:checked').forEach(x=>data.choices[x.name.slice(5)]=x.value);
    const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));
    const a=document.createElement('a');a.href=u;a.download='reviewed-choices.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}};</script></body></html>''', encoding='utf-8')


def emit_paragraphs(output, rows, transcripts, wavs, settings, fmt, errors, root, progress=print, replay=True):
    from .pipeline import serialize_rows, save_project
    from .coverage import text_evidence
    from .speech import speech_engine
    media = {t.media.id: t.media for t in transcripts}
    cuts, per_row = cuts_for_rows(rows, transcripts, settings)
    audio_folder = output / 'review-audio'
    audio_folder.mkdir(exist_ok=True)
    for row in rows:
        if row['index'] in per_row:
            row['edited_audio'] = f'review-audio/sentence-{row["index"] + 1:03d}.wav'
            assemble_audio(per_row[row['index']], media, wavs, output / row['edited_audio'])
        for c in row['alternatives']:
            s = c['span']; m = media[s.media_id]
            name = hashlib.sha256(s.id.encode()).hexdigest()[:16]
            c['preview'] = f'review-audio/option-{name}.wav'
            if not (output / c['preview']).exists():
                a, b = max(0, math.floor((s.start - .08) * float(m.rate))), min(math.floor(m.duration * float(m.rate)), math.ceil((s.end + .12) * float(m.rate)))
                assemble_audio([Cut(s.media_id, a, b, row['index'])], media, wavs, output / c['preview'])
    paragraphs = []
    engine = None
    try:
        for index in sorted({r['paragraph_index'] for r in rows}):
            group = [r for r in rows if r['paragraph_index'] == index]
            p_cuts = [c for r in group for c in per_row.get(r['index'], [])]
            name = f'review-audio/paragraph-{index + 1:02d}.wav'
            assemble_audio(p_cuts, media, wavs, output / name)
            paragraph = {'index': index, 'text': group[0]['paragraph_text'], 'rows': group,
                         'placed': sum(r['selected'] is not None for r in group), 'audio': name}
            if replay and p_cuts:
                progress(f'Checking actual edited paragraph {index + 1}')
                # Verify the edited audio independently. Reloading the primary
                # sharded ASR after meaning inference crashed the live worker.
                if engine is None:
                    engine = speech_engine(replace(settings, speech_backend='turbo'), root)
                try:
                    paragraph['heard_after'] = engine.transcribe_cut(output / name)
                    expected = ' '.join(r.get('cut_text', r['selected']['span'].text) for r in group if r['selected'])
                    paragraph['replay_evidence'] = text_evidence(expected, paragraph['heard_after'])
                    if paragraph['replay_evidence']['recall'] < .65:
                        paragraph['review'] = 'Replay transcription differs; listen to this paragraph.'
                except Exception as error:
                    paragraph['review'] = 'Replay check unavailable: ' + str(error)
            paragraphs.append(paragraph)
    finally:
        if engine: engine.close()
    if cuts:
        export_xml(output / 'EDITED_SEQUENCE.xml', cuts, media, fmt)
        assemble_audio(cuts, media, wavs, output / 'full-timeline.wav')
        canvas = OUTPUT_FORMATS.get(fmt) or (transcripts[0].media.width, transcripts[0].media.height)
        try:
            render_preview(cuts, media, output / 'full-timeline.wav', output / 'preview.mp4', canvas, progress,device=settings.device)
        except Exception as error:
            errors = [*errors, 'Video preview unavailable; XML and audio retained: ' + str(error)]
    saved_rows = serialize_rows(rows)
    for p in paragraphs: p['rows'] = [r for r in saved_rows if r['paragraph_index'] == p['index']]
    report = {'kind': 'assemble', 'version': 'paragraph-coverage-2', 'status': 'REVIEW_REQUIRED',
              'pacing': settings.pacing,
              'rows': saved_rows, 'paragraphs': paragraphs, 'errors': errors,
              'sentence_count': len(rows), 'placed_sentences': sum(r['selected'] is not None for r in rows),
              'cut_count': len(cuts), 'duration_seconds': sum(c.duration / float(media[c.media_id].rate) for c in cuts)}
    save_project(output, settings, 'assemble', transcripts, wavs, rows=saved_rows,
                 output_format=fmt, errors=errors, assembly_version='paragraph-coverage-2')
    write_json(output / 'report.json', report)
    write_json(output / 'edit-decisions.json', {'cuts': [asdict(c) for c in cuts], 'media': {k: asdict(v) for k, v in media.items()}})
    write_paragraph_page(output, report)
    return report
