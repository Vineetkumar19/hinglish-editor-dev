from html import escape
import json
from pathlib import Path
from hinglish_clean.pipeline import STYLE


def write_report(output, report, project):
    output = Path(output)
    def audio(name):
        return f'<audio controls preload="none" src="{escape(name, quote=True)}"></audio>' if name else ''
    content = []
    if report['kind'] == 'assemble':
        for row in report['rows']:
            choices = ['<label><input type="radio" name="idea-' + str(row['index']) + '" value="" '
                       + ('checked' if not row.get('selected_id') else '') + '>Leave this idea unmatched</label>']
            for c in row['alternatives']:
                span = c['span']
                selected = c['span']['id'] == row.get('selected_id')
                label = f'{span["start"]:.2f}s - {span["end"]:.2f}s | {c["source_name"]}'
                reason = c.get('verdict', {}).get('reason', 'Meaning not verified')
                concerns = ', '.join(c.get('issues', []))
                choices.append(f'<div class="option"><label><input type="radio" name="idea-{row["index"]}" '
                               f'value="{escape(span["id"], quote=True)}" {"checked" if selected else ""}>'
                               f'{escape(label)}</label><p>{escape(span["text"])}</p>'
                               f'<p class="muted">{escape(reason)} {escape(concerns)}</p>{audio(c.get("preview"))}</div>')
            content.append(f'<section class="card"><h2>{row["index"] + 1}. {escape(row["idea"])}</h2>'
                           f'<p>{escape(", ".join(row["issues"])) or "Candidate verified; listen before publishing."}</p>'
                           f'{audio(row.get("edited_audio"))}<details><summary>Compare / choose source takes</summary>'
                           + ''.join(choices) + '</details></section>')
    else:
        for p in report['proposals']:
            reason = p.get('review_reason') or p.get('verdict', {}).get('reason') or p['reason']
            disabled = 'disabled' if not p.get('bounds') else ''
            checked = 'checked' if p.get('approved') else ''
            content.append(f'<section class="card"><label><input type="checkbox" name="remove" '
                           f'value="{escape(p["id"], quote=True)}" {checked} {disabled}> Remove this {p["kind"]}</label>'
                           f'<p>{escape(p["text"])}</p><p>{escape(reason)}</p>'
                           + (f'<p>Later attempt: {escape(p["replacement"])}</p>' if 'replacement' in p else '')
                           + '<p>Before:</p>' + audio(p.get('before_preview'))
                           + ('<p>After proposed cut:</p>' + audio(p.get('preview')) if p.get('preview') else '') + '</section>')
    video = '<video controls preload="metadata" src="cleaned.mp4"></video>' if (output / 'cleaned.mp4').exists() else ''
    if report.get('source_video'):
        video += '<details><summary>Compare original video</summary><video controls preload="none" src="' + escape(report['source_video'], quote=True) + '"></video></details>'
    if report.get('unused_sections'):
        content.append('<section class="card"><details><summary>Source sections left out of this arrangement ('
                       + str(len(report['unused_sections'])) + ')</summary><p>Check whether these contain extra information you want to keep. Full sources remain in the media folder.</p>'
                       + ''.join(f'<p><a href="{escape(s["source"], quote=True)}#t={s["start"]:.2f},{s["end"]:.2f}">{s["start"]:.2f}s - {s["end"]:.2f}s</a> {escape(s["text"])}</p>' for s in report['unused_sections'])
                       + '</details></section>')
    links = ' &nbsp; '.join(f'<a href="{name}" download>{label}</a>' for name, label in
                          [('draft.xml', 'Premiere draft'), ('timeline.xml', 'Checked timeline'),
                           ('reviewed.xml', 'Your reviewed timeline')] if (output / name).exists())
    errors = ''.join(f'<li>{escape(str(e))}</li>' for e in report.get('errors', []))
    payload = json.dumps({'project': str((output / 'project.json').resolve()), 'kind': report['kind']}).replace('<', '\\u003c')
    title = 'Phase 2 - arrange by meaning' if report['kind'] == 'assemble' else 'Clean+ - fillers and retakes'
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{title}</title><style>{STYLE}.option{{border-top:1px solid #ddd;padding:14px 0}}label{{display:block}}input{{margin:8px}}</style>
    <body><h1>{title}</h1><p>{escape(report['status'])}</p><p>{links}</p>{video}
    <p>Listen before exporting. Scores and model checks are not a guarantee that meaning is intact.</p><ul>{errors}</ul>
    {''.join(content)}<div class="card"><h2>Save your choices</h2>
    <p>After reviewing, save choices below. Drag the downloaded file onto <b>Apply Reviewed Choices.bat</b> in the app folder.
    A new output is created, and your approved/rejected takes are saved locally to improve future similar edits.</p><button id="save">Save reviewed choices</button></div>
    <p class="muted">Keep this whole output folder for future Premiere edits. Fillers not transcribed by the speech model cannot be reliably removed.
    Retakes are intended for one talking-head speaker; conversations and meaningful repeated ideas need review.</p>
    <script>document.querySelector('#save').addEventListener('click',()=>{{let data={payload};
    data.choices={{}};document.querySelectorAll('input[type=radio]:checked').forEach(x=>{{data.choices[x.name.slice(5)]=x.value;}});
    data.remove=Array.from(document.querySelectorAll('input[name=remove]:checked')).map(x=>x.value);
    const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));
    const a=document.createElement('a');a.href=u;a.download='reviewed-choices.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}});</script></body></html>'''
    (output / 'report.html').write_text(html, encoding='utf-8')
