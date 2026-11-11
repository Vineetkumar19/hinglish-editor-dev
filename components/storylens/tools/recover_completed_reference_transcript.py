"""Recover the completed Delhi segment transcript after a numpy-bool JSON error."""
import json
from pathlib import Path
folder=Path(__file__).resolve().parent.parent/'output/reference-analysis/cricket-documentaries/dc'
lines=[json.loads(line) for line in (folder/'transcript.partial.jsonl').read_text(encoding='utf-8').splitlines()]
seconds=json.loads((folder/'scan.json').read_text(encoding='utf-8'))['source']['seconds']
if not lines or lines[-1]['end']<seconds-1:raise RuntimeError('Partial transcript does not reach the end of this source.')
(folder/'transcript.json').write_text(json.dumps(lines,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'transcript.txt').write_text('\n'.join(f'[{p["start"]:.2f}–{p["end"]:.2f}] {p["text"]}' for p in lines),encoding='utf-8')
(folder/'speech-coverage.json').write_text(json.dumps({'backend':'local faster-whisper large-v3-turbo CPU int8, beam1, VAD','source_seconds':seconds,'segments':len(lines),'words':None,'warning':'Full segment transcript recovered after final word-JSON serialization failed. Word-level receipt was not saved. Names/numbers remain fallible ASR, not verified cricket facts.'},indent=2),encoding='utf-8')
print('Recovered full Delhi segment transcript; word-level receipt unavailable.')
