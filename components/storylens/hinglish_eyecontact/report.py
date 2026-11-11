"""Eye Contact results page: before/after preview + every corrected file."""
from pathlib import Path
import html


def _clock(seconds):
    m, s = divmod(max(0.0, seconds), 60)
    return f'{int(m)}:{s:04.1f}'


def write_report(path, name, results, settings, preview=None, xml_name=None, notes=(), simulated=False):
    rows = ''.join(
        f'<tr><td>{html.escape(Path(r["source"]).name)}</td><td>{_clock(r["duration"])}</td>'
        f'<td>{r["fixed"]}/{r["frames"]}</td><td>{"reused" if r.get("reused") else _clock(r["seconds"])}</td>'
        f'<td class="said">{html.escape(r["target"])}</td></tr>' for r in results)
    video = (f'<video src="{html.escape(preview)}" controls playsinline></video>'
             '<p class="muted">Left: original · Right: eye contact</p>' if preview else '')
    note_html = ''.join(f'<li>{html.escape(n)}</li>' for n in notes)
    how = (f'Import <b>{html.escape(xml_name)}</b> in Premiere Pro or DaVinci Resolve: the same edit, linked to the '
           'eye-contact copies. Your original sequence and files are unchanged.' if xml_name else
           'Use the eye-contact copies in place of your original files. Your originals are unchanged.')
    warning = ('<p class="warn">SIMULATED run (no RTX GPU): the eyes were NOT changed. This only tested the '
               'pipeline.</p>' if simulated else '')
    Path(path).write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Eye Contact</title><style>
:root{{--bg:#0d0f12;--card:#171a20;--line:#2a2f38;--text:#f3f4f6;--muted:#9aa3af;--accent:#ff6a2b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px;display:grid;grid-template-columns:minmax(0,460px) minmax(0,1fr);gap:24px}}
h1{{font-size:22px;margin:0 0 4px}}.muted{{color:var(--muted)}}.warn{{color:#ffb020;font-weight:600}}
video{{width:100%;max-height:80vh;background:#000;border-radius:12px;display:block}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--muted);font-weight:600;font-size:12px}}td:first-child{{color:var(--accent);font-weight:700}}
.said{{color:var(--muted);word-break:break-all}}ul{{color:var(--muted);font-size:13px}}
@media(max-width:800px){{main{{grid-template-columns:1fr}}}}</style></head><body><main>
<section>{video}</section><section><h1>Eye Contact · {html.escape(name)}</h1>{warning}
<p class="muted">{('Open Eye Contact · Hsu neural flow' if settings.backend == 'hsu_onnx' else 'NVIDIA Maxine eye contact')} · script position {html.escape(settings.reach)} ·
natural glances {"on" if settings.look_away else "off"} · eye size {settings.eye_size}</p>
<table><tr><th>File</th><th>Length</th><th>Frames processed</th><th>Time</th><th>Eye-contact copy</th></tr>{rows}</table>
<p class="muted">{how}</p>{f"<ul>{note_html}</ul>" if note_html else ""}</section></main></body></html>''',
                          encoding='utf-8')
    return Path(path)
