"""Measure received bytes, including out-of-order ranges, without double counting."""
import json
import os
from pathlib import Path
import re
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]
STORE = Path(r'C:\Ai Models')


def length(path):
    try:
        with path.open('rb') as stream:
            return stream.seek(0, 2)
    except OSError:
        return 0


def received(folder):
    total = 0
    if not folder.is_dir():
        return total
    for directory, dirs, names in os.walk(folder):
        dirs[:] = [name for name in dirs if not name.endswith('.ranges')]
        for name in names:
            if not (name.endswith(('.gguf', '.safetensors', '.incomplete')) or name == 'model.bin'):
                continue
            file = Path(directory)/name
            if file.suffix in ('.gguf', '.safetensors') or name == 'model.bin':
                total += file.stat().st_size
                continue
            intervals = [(0, length(file))]
            parts = file.with_name(file.name + '.ranges')
            if parts.is_dir():
                for entry in os.scandir(parts):
                    part = Path(entry.path)
                    match = re.fullmatch(r'part-(\d+)-(\d+)\.(?:bin|tmp)', part.name)
                    if match:
                        start, end = map(int, match.groups())
                        size = length(part) if part.suffix == '.tmp' else entry.stat().st_size
                        intervals.append((start, min(end, start + size)))
            cursor = 0
            for start, end in sorted(intervals):
                total += max(0, end - max(start, cursor))
                cursor = max(cursor, end)
    return total


def main():
    state = json.loads((ROOT/'downloads/model-upgrade-c-drive.json').read_text(encoding='utf-8-sig'))
    known = {'asr':4703055333, 'independent_asr':3090835702, 'broll_vision':4271029553, 'cutout':1000000000}
    rows = []
    for role in ('planner','meaning','embedding','asr','independent_asr','broll_vision','cutout'):
        row = state['models'].get(role, {})
        folder = Path(row['path']) if row.get('path') else None
        if role=='cutout' and folder is None:
            folder=STORE/'rembg/models/birefnet-general/birefnet-general.onnx'
        got = received(folder) if folder and folder.is_dir() else length(folder) if folder else 0
        status=row.get('status','queued')
        if status=='downloaded' and folder and folder.is_dir():
            got=sum((folder/name).stat().st_size for name in row.get('files',[])
                    if (folder/name).is_file())
        if role=='cutout' and folder and not folder.is_file() and folder.parent.is_dir():
            got=received(folder.parent)
            if got: status='downloading'
        size = row.get('selected_bytes', known.get(role,0))
        rows.append(dict(role=role,status=status,received_bytes=got,expected_bytes=size,
                         percent=round(100*got/size,1) if size else None))
    report = dict(timestamp=time.time(),models=rows,received_bytes=sum(r['received_bytes'] for r in rows),
                  expected_bytes=sum(r['expected_bytes'] for r in rows),free_c_bytes=shutil.disk_usage(STORE).free)
    candidate_path=STORE/'logs/hinglish-asr-candidate.json'
    if candidate_path.is_file():
        candidate=json.loads(candidate_path.read_text(encoding='utf-8-sig'))
        if candidate.get('path')!=state['models'].get('asr',{}).get('path'):
            folder=Path(candidate['path']) if candidate.get('path') else None
            got=received(folder) if folder else 0
            if candidate.get('status') in ('downloaded','validating') and folder:
                got=sum((folder/name).stat().st_size for name in candidate.get('files',[]) if (folder/name).is_file())
            report['additional_downloads']=[dict(role='native_hinglish_asr',status=candidate.get('status'),
                received_bytes=got,expected_bytes=candidate.get('selected_bytes',0))]
    report['total_received_bytes']=report['received_bytes']+sum(r['received_bytes'] for r in report.get('additional_downloads',[]))
    report['total_expected_bytes']=report['expected_bytes']+sum(r['expected_bytes'] for r in report.get('additional_downloads',[]))
    path = ROOT/'downloads/current-upgrade-progress.json'
    if path.exists():
        previous = json.loads(path.read_text())
        elapsed = report['timestamp']-previous['timestamp']
        if elapsed > 5:
            report['recent_bytes_per_second'] = max(0,report['total_received_bytes']-previous.get('total_received_bytes',previous['received_bytes']))/elapsed
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
