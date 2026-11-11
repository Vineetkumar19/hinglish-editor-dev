"""Readable local evidence index; does not imply unrecorded visual review."""
import html,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'output/reference-analysis/cricket-documentaries'

def main():
    inventory=json.loads((BASE/'inventory.json').read_text(encoding='utf-8'))
    cards=[];measured=0;reviewed=0
    for item in inventory:
        slug=Path(item['name']).stem.split()[0];folder=BASE/slug
        scan=json.loads((folder/'scan.json').read_text(encoding='utf-8')) if (folder/'scan.json').exists() else {}
        notes=json.loads((folder/'review-notes.json').read_text(encoding='utf-8')) if (folder/'review-notes.json').exists() else {}
        measured+=scan.get('decoded_frames',0);reviewed+=bool(notes)
        escape=html.escape
        pages=notes.get('visual_review',{}).get('every_second_pages',[])
        status=f"{scan['decoded_frames']:,} native frames measured" if scan else 'Native scan pending'
        status+=f" · {len(pages)} second-by-second pages visually reviewed"
        speech='Automatic transcript complete' if (folder/'transcript.json').exists() else 'Speech pass pending/in progress'
        if (folder/'speech-coverage.json').exists():
            coverage=json.loads((folder/'speech-coverage.json').read_text(encoding='utf-8'))
            speech+=' · '+('Segment timings only; word timings unavailable' if coverage.get('words') is None else 'ASR word timings; names and numbers need review')
        links=[]
        for pattern,label in [('overview/*.jpg','Overview'),('every-second/*.jpg','Every second'),('details/*/contact-*.jpg','Animation detail')]:
            for path in sorted(folder.glob(pattern)):
                links.append(f'<a href="{escape(path.relative_to(BASE).as_posix(),quote=True)}">{label} {escape(path.parent.name if label=="Animation detail" else path.stem)}</a>')
        for name in ('scan.json','frame-metrics.csv','words.json','transcript.txt','speech-coverage.json','review-notes.json'):
            if (folder/name).exists():links.append(f'<a href="{slug}/{name}">{name}</a>')
        chapter_rows=''.join(f'<tr><td>{c["start"]:.1f}–{c["end"]:.1f}s</td><td>{escape(c["look"])}</td><td>{escape(c["observations"])}</td></tr>' for c in notes.get('chapters',[]))
        poster=(folder/'frames/00020.jpg')
        preview=f'<img loading="lazy" src="{slug}/frames/00020.jpg" alt="Reference frame at 20 seconds">' if poster.exists() else ''
        cards.append(f'<section><h2>{escape(item["name"])}</h2><p>{item["duration"]/60:.2f} minutes · {item["bytes"]/1e9:.2f} GB · {item["width"]}×{item["height"]} · {item["fps"]} fps</p><p class="status">{status}<br>{speech}</p>{preview}<p>{escape(notes.get("coverage_limit","Visual review is pending."))}</p><details><summary>Timeline images, measurements and transcript</summary><nav>{"".join(links)}</nav></details><table><tr><th>Time</th><th>Look</th><th>Observed editing</th></tr>{chapter_rows}</table></section>')
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Your Cricket Documentary References</title><style>body{{font:16px/1.6 system-ui;background:#10151a;color:#e5e9eb;max-width:1120px;margin:auto;padding:35px}}h1,h2{{line-height:1.2}}h1{{font-size:38px}}a{{color:#8ed8ed}}section{{background:#192127;border:1px solid #39454b;border-radius:16px;padding:24px;margin:28px 0}}section>img{{width:460px;max-width:100%;border-radius:8px}}nav{{display:flex;gap:12px;flex-wrap:wrap;padding:20px 0}}table{{border-collapse:collapse;width:100%;margin-top:20px}}td,th{{text-align:left;vertical-align:top;border-bottom:1px solid #3c484f;padding:12px}}td:first-child{{white-space:nowrap}}.status{{color:#d9c292}}.note{{background:#2a302b;padding:20px;border-radius:12px}}</style><h1>Your Cricket Documentary References</h1><p>Seven local videos · {sum(i['duration'] for i in inventory)/60:.2f} minutes · {sum(i['bytes'] for i in inventory)/1e9:.2f} GB of originals.</p><p class="status">{measured:,} native frames measured · {reviewed}/7 videos with saved visual-review notes.</p><p class="note">At 60fps, native frames are 16.67ms apart. Every decoded frame is measured at 256×144; this detects changes but does not recognise players, fonts or match dates. Visual review covers the saved second-by-second images and explicitly recorded detail windows. These are editing observations, not independently verified cricket facts or a claim of individually watching every native frame. Originals stay on A:; only small analysis derivatives are saved here.</p><p>The Cricket profile uses a persistent editing memory and the <strong>Your Cricket Documentary</strong> motion style. It does not change General or Gaming defaults. Historical player imagery must have a reviewed year/team/match record; a generic portrait cannot pass that check.</p><p><a href="../../../docs/CRICKET_DOCUMENTARY_STYLE_GUIDE.md">Editing guide</a> · <a href="inventory.json">Source inventory</a> · <a href="demo/report.html">Rendered style study</a></p>{''.join(cards)}</html>'''
    body=body.replace('<a href="demo/report.html">Rendered style study</a>',
        '<a href="motion-stories/report.html">Motion comparison — road, reel, focus, hinges and pages</a> · <a href="demo-motion-v3/report.html">Earlier background study</a> · <a href="demo-motion-v2/report.html">Previous motion preview</a> · <a href="demo/report.html">First layout study</a>')
    (BASE/'report.html').write_text(body,encoding='utf-8')
    print(json.dumps({'frames_measured':measured,'videos_with_notes':reviewed,'report':str(BASE/'report.html')}))

if __name__=='__main__':main()
