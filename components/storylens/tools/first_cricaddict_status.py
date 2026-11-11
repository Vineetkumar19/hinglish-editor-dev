"""A lightweight, honest local progress page for the first reference."""
import html,json,time
from pathlib import Path
from study_one_cricaddict_review import complete_observations
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01'
def get(name):
 try:return json.loads((OUT/name).read_text(encoding='utf8'))
 except (OSError,ValueError):return {}
def main():
 while True:
  source=get('source.json');native=get('native-vision-coverage.json');speech=get('speech-receipt.json');completion=get('completion.json')
  rows=[]
  for p in (OUT/'review-panels').glob('*.json'):
   if not p.stem.isdigit():continue
   try:
    r=json.loads(p.read_text(encoding='utf8'))
    if r.get('review_schema_revision')==3 and complete_observations(r.get('observations')):rows.append(r)
   except (OSError,ValueError):pass
  seconds=sum(len(r['sampled_seconds']) for r in rows);stage='Detailed local vision review'
  if get('learned-lessons.json'):stage='Local sample direction and asset preparation'
  if get('sample-render-receipt.json'):stage=get('sample-render-receipt.json').get('stage',stage)
  if completion.get('status')=='complete':stage='Complete — first reference only'
  lessons=''.join(f'<li>{html.escape(l["title"])} — source {l["start"]:.2f}–{l["end"]:.2f}s</li>' for l in get('learned-lessons.json').get('lessons',[]))
  link='<p><a href="report.html">Open the completed report and one-minute sample</a></p>' if completion.get('status')=='complete' else '<p>The sample is pending. This page is progress evidence, not a completed video.</p>'
  page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="15"><title>cricAddict · First-video study progress</title><style>body{{background:#10171b;color:#eee5d6;font:18px/1.6 system-ui;max-width:1100px;margin:auto;padding:36px}}h1{{font:42px Georgia}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}article{{padding:22px;background:#1c2830;border:1px solid #43525c;border-radius:14px}}b{{display:block;font-size:28px}}img{{width:100%;border-radius:12px}}a{{color:#edbb76}}</style><h1>One video at a time: cricAddict</h1><p>{html.escape(source.get('name','First reference'))}</p><h2>{html.escape(stage)}</h2><div class="cards"><article><b>{native.get('native_frames',0):,}</b>recorded frames interpreted locally</article><article><b>{speech.get('words',0):,}</b>fresh local speech words</article><article><b>{seconds} / 753</b>seconds in validated local vision panels</article></div><p>Every native frame has CLIP vectors and candidate labels. The slower Qwen2.5-VL review sees one original frame for every source second in timestamped panels. The local director will choose a passage and the sample's creative decisions after that review finishes. Failed, repeated or truncated observations are excluded.</p>{link}<ul>{lessons}</ul><p>No second reference has started. No cloud creative plan is used. Saved reference memory stays independent of the Ollama language model.</p><h2>Example timestamped source panel</h2><img src="review-panels/0000.jpg"><p>Original source frames; this panel is analysis evidence, not generated output.</p></html>'''
  p=OUT/'progress.html';tmp=p.with_suffix('.tmp');tmp.write_text(page,encoding='utf8');tmp.replace(p)
  if completion.get('status')=='complete':break
  time.sleep(15)
if __name__=='__main__':main()
