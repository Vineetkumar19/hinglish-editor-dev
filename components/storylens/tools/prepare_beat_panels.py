"""Idempotently attach Beat Studio controls to the two Premiere panels."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = '''<!-- STORYLENS_BEATS_BEGIN -->
<section style="border:1px solid #42484b;border-radius:8px;padding:14px;margin:18px 0">
<h3>Cinematic Reels</h3><p>Music + your performance shots. Assemble first, choose effects afterwards.</p>
<button id="cinematicOpen">Open Cinematic Reels</button><button id="cinematicImport">Import latest cinematic reel</button><p id="cinematicStatus" role="status"></p>
</section>
<section id="beatStudio" style="border:1px solid #42484b;border-radius:8px;padding:14px;margin:18px 0">
<h3>Beat Studio</h3><p>Select exactly one music clip on an audio track.</p>
<label><input id="beatAuto" type="checkbox"> Auto-detect when the selected music changes</label>
<label>Beat density<select id="beatDensity"><option value="light">Light · fewer prominent beats</option><option value="medium" selected>Medium · balanced</option><option value="strong">Strong · more detected beats</option></select></label>
<label>Maximum markers (optional)<input id="beatCount" type="number" min="1" max="10000" placeholder="e.g. 25 clips → up to 25 markers"></label>
<button id="beatDetect">1. Detect &amp; mark beats</button>
<label>Effect<select id="beatStyle"><option value="punch">Punch zoom</option><option value="smooth">Smooth zoom</option></select></label>
<label>Zoom amount · %<input id="beatAmount" type="number" min="1" max="20" value="8"></label>
<label>Effects target video track<input id="beatVideoTrack" type="number" min="1" max="99" value="1"></label>
<button id="beatApply" disabled>2. Apply effects to beats</button>
<p id="beatStatus" role="status">Markers first. Effects run separately on a duplicate sequence. Normal-speed music only.</p>
</section><!-- STORYLENS_BEATS_END -->'''


def prepare(root=ROOT):
    for name, script in (('premiere-cep', 'js/beats.js'), ('premiere-uxp', 'beats.js')):
        file = Path(root) / 'editor_plugins' / name / 'index.html'
        text = file.read_text(encoding='utf-8')
        if '<!-- STORYLENS_BEATS_BEGIN -->' in text:
            start=text.index('<!-- STORYLENS_BEATS_BEGIN -->');end=text.index('<!-- STORYLENS_BEATS_END -->')+len('<!-- STORYLENS_BEATS_END -->')
            text=text[:start]+CONTROLS+text[end:]
        else:
            text = text.replace('<main>', '<main>' + CONTROLS, 1)
        if f'src="{script}"' not in text:
            text = text.replace('</body>', f'<script src="{script}"></script></body>')
        file.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    prepare()
