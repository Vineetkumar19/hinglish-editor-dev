"""One bounded local speech batch; native failure cannot kill the HTTP server."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import re
import traceback

from .durable_json import write


def execute(root, key):
    root = Path(root).resolve()
    if not re.fullmatch('[a-f0-9]{32}', key):raise ValueError('Choose a saved speech preparation.')
    folder = root / 'cache/publisher/speech' / key
    request = json.loads((folder / 'request.json').read_text('utf-8'))
    from hinglish_publish.store import fingerprint
    from hinglish_cut.gpu_lock import gpu_lock
    rows = request['videos']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 40:raise ValueError('Choose between one and forty saved videos.')
    videos = [Path(row['path']).resolve() for row in rows]
    if any(fingerprint(v) != row['sha256'] for v, row in zip(videos, rows)):
        raise ValueError('The selected video changed before speech preparation.')
    def progress(stage):write(folder / 'status.json', {'status': 'running', 'stage': stage})
    with nullcontext() if request.get('gpu_locked_by_parent') else gpu_lock(root):
        from .assistant_publish import _transcripts_in_process
        _transcripts_in_process(root, videos, progress)
    write(folder / 'status.json', {'status': 'ready', 'stage': 'Spoken content saved.'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--id', required=True)
    args = parser.parse_args()
    try:execute(args.root, args.id)
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':raise SystemExit(main())
