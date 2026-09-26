"""Sound design results page: the story and emotion map the model read, music sections and every
sound with the director's reasoning, plus the model's own thinking."""
from pathlib import Path
import html


def _clock(seconds):
    m, s = divmod(max(0.0, float(seconds)), 60)
    return f'{int(m)}:{s:04.1f}'


def write_report(path, name, plan, preview=None):
    e = html.escape
    feel = ''.join(
        f'<tr><td>{_clock(l["start"])}</td><td>{e(l["text"])}</td><td><b>{e(str(l.get("emotion", "")))}</b> '
        f'{"●" * int(l.get("intensity") or 0)}</td><td class="muted">{e(str(l.get("role", "")))}</td>'
        f'<td class="muted">{e(l.get("voice", ""))}</td></tr>' for l in plan['lines'])
    music = ''.join(
        f'<tr><td>{_clock(s["start"])}–{_clock(s["end"])}</td><td><b>{e(s["mood"])}</b></td>'
        f'<td>{e(Path(s["path"]).name)}</td><td class="muted">{e(s.get("why", ""))}<br>{e(s.get("pick_why", ""))}</td></tr>'
        for s in plan['music'])
    sounds = ''.join(
        f'<tr><td>{_clock(c["target"])}</td><td><b>{e(c["category"])}</b><br><small>{e(c["source"])}</small></td>'
        f'<td>{e(c.get("word") or "")}</td><td><small>{e(c.get("sound") or "")}</small><br>{e(Path(c["path"]).name)}</td>'
        f'<td class="muted">{e(c["reason"])}</td></tr>' for c in plan['cues'])
    video = f'<video src="{e(preview)}" controls playsinline></video>' if preview else ''
    Path(path).write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sound Design</title><style>
body{{margin:0;background:#0d0f12;color:#f3f4f6;font:14px/1.45 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1250px;margin:0 auto;padding:24px;display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);gap:24px}}
video{{width:100%;max-height:80vh;background:#000;border-radius:12px;position:sticky;top:16px}}
h1{{font-size:22px;margin:0 0 6px}}h2{{font-size:15px;margin:22px 0 6px;color:#ffb07a}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:6px;border-bottom:1px solid #2a2f38;text-align:left;vertical-align:top}}
th{{color:#9aa3af;font-size:12px}}td:first-child{{color:#ff6a2b;font-weight:700;white-space:nowrap}}.muted,small{{color:#9aa3af}}
details{{color:#9aa3af;white-space:pre-wrap;font-size:12px}}@media(max-width:860px){{main{{grid-template-columns:1fr}}}}
</style></head><body><main><section>{video}</section><section>
<h1>Sound design · {e(name)}</h1>
<p><b>Story:</b> {e(plan.get("story", ""))}<br><span class="muted">Palette: {e(plan.get("palette", ""))} · voice {plan["voice_db"]} dB</span></p>
<h2>How each line feels (words + your voice)</h2><table><tr><th>Time</th><th>Line</th><th>Emotion</th><th>Role</th><th>Voice</th></tr>{feel}</table>
<h2>Music</h2><table><tr><th>Time</th><th>Mood</th><th>Track</th><th>Why</th></tr>{music}</table>
<h2>Sounds</h2><table><tr><th>Time</th><th>Type</th><th>Word</th><th>Intent / file</th><th>Why</th></tr>{sounds}</table>
<details><summary>The model's own thinking</summary>{e(plan.get("thinking", ""))}</details>
<p class="muted">Import <b>SOUND_SEQUENCE.xml</b>: music and each effect are on their own audio tracks, levels already set.</p>
</section></main></body></html>''', encoding='utf-8')
