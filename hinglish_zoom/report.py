"""Smart Zoom results page: preview video + every zoom moment."""
from pathlib import Path
import html

KIND_LABEL = {'smooth': 'Smooth zoom-in', 'punch': 'Punch-in', 'impact': 'Impact punch',
              'reveal': 'Zoom-out reveal', 'push': 'Slow push-in'}


def _clock(seconds):
    m, s = divmod(max(0.0, seconds), 60)
    return f'{int(m)}:{s:04.1f}'


def write_report(path, name, events, settings, width, height, preview=None, notes=()):
    rows = ''.join(
        f'<tr><td>{_clock(e.word)}</td><td><b>{html.escape(e.word_text)}</b></td>'
        f'<td>{html.escape(KIND_LABEL.get(e.kind, e.kind))}</td><td>{e.level * 100:.0f}%</td>'
        f'<td class="said">{html.escape(e.text)}</td></tr>' for e in events)
    video = (f'<video src="{html.escape(preview)}" controls playsinline style="aspect-ratio:{width}/{height}"></video>'
             if preview else '<p class="muted">Preview is skipped for long timelines — import the XML to watch.</p>')
    note_html = ''.join(f'<li>{html.escape(n)}</li>' for n in notes)
    Path(path).write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Smart Zoom</title><style>
:root{{--bg:#0d0f12;--card:#171a20;--line:#2a2f38;--text:#f3f4f6;--muted:#9aa3af;--accent:#ff6a2b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px;display:grid;grid-template-columns:minmax(0,380px) minmax(0,1fr);gap:24px}}
h1{{font-size:22px;margin:0 0 4px}}.muted{{color:var(--muted)}}
video{{width:100%;max-height:80vh;background:#000;border-radius:12px;display:block}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--muted);font-weight:600;font-size:12px}}td:first-child{{color:var(--accent);font-weight:700;white-space:nowrap}}
.said{{color:var(--muted)}}ul{{color:var(--muted);font-size:13px}}
@media(max-width:800px){{main{{grid-template-columns:1fr}}}}</style></head><body><main>
<section>{video}</section><section><h1>Smart Zoom · {html.escape(name)}</h1>
<p class="muted">{len(events)} zooms · style {html.escape(settings.style)} · strength {html.escape(settings.strength)} ·
frequency {html.escape(settings.frequency)} · face {"on" if settings.face else "off"} · jump-cut framing {"on" if settings.jump_cuts else "off"}</p>
<table><tr><th>Time</th><th>Word</th><th>Zoom</th><th>Level</th><th>Said</th></tr>{rows}</table>
<p class="muted">Import <b>ZOOMED_SEQUENCE.xml</b> in Premiere Pro or DaVinci Resolve. Your original sequence is unchanged;
audio is not cut.</p>{f"<ul>{note_html}</ul>" if note_html else ""}</section></main></body></html>''', encoding='utf-8')
