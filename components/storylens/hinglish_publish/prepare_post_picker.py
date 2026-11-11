"""Read-only video picker for the browser; media remains at its original path."""
import os
import re
import subprocess
import threading
from pathlib import Path

from .prepare_post import VIDEO

_native_lock = threading.Lock()


def native_pick(root, initial='', *, kind='video'):
    """Searchable Windows Explorer dialog; selecting never copies/uploads media."""
    import sys
    from .prepare_post import IMAGE
    if os.name != 'nt':
        raise ValueError('The Windows file picker is unavailable here. Paste the original file path instead.')
    if kind not in ('video', 'thumbnail'):
        raise ValueError('Choose a video or thumbnail.')
    start = Path(str(initial).strip().strip('"')) if initial else Path(root)
    if not start.is_dir():start = start.parent
    if not start.is_dir():start = Path(root)
    if not _native_lock.acquire(blocking=False):
        raise ValueError('A file chooser is already open. Select a file or cancel that window first.')
    try:
        result = subprocess.run([sys.executable, '-E', '-X', 'utf8', '-m',
            'hinglish_publish.prepare_post_picker_native', kind, str(start.resolve())],
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise ValueError('The Windows file chooser stopped. Try Choose file again, or paste its full path.') from RuntimeError(result.stderr[-1500:])
        chosen = result.stdout.strip()
        if not chosen:return ''
        path = Path(chosen)
        if not path.is_file() or path.suffix.lower() not in (VIDEO if kind == 'video' else IMAGE):
            raise ValueError('Choose an existing supported '+('video' if kind == 'video' else 'image')+' file.')
        return str(path.resolve())
    finally:
        _native_lock.release()


def browse(value, query=''):
    if str(value) == '::drives::':
        if os.name == 'nt':
            import ctypes
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            paths = [Path(chr(65 + n) + ':\\') for n in range(26) if mask & (1 << n)]
        else:
            paths = [Path('/')]
        return {'path': '', 'parent': None, 'folders': [{'name': str(p), 'path': str(p)} for p in paths], 'videos': [], 'truncated': False}
    path = Path(str(value).strip().strip('"')).expanduser().resolve()
    if path.is_file():
        path = path.parent
    if not path.is_dir():
        raise ValueError('Check the folder path and try again.')
    try:
        entries = list(path.iterdir())
    except OSError as error:
        raise ValueError('Check that you can open this folder, or choose another folder.') from error
    def order(p):
        return [int(part) if part.isdigit() else part.casefold() for part in re.split(r'(\d+)', p.name)]
    folders, videos = [], []
    for entry in sorted(entries, key=order):
        try:
            if entry.is_dir():
                folders.append({'name': entry.name, 'path': str(entry.resolve())})
            elif entry.is_file() and entry.suffix.lower() in VIDEO and str(query).casefold() in entry.name.casefold():
                videos.append({'name': entry.name, 'path': str(entry.resolve()), 'bytes': entry.stat().st_size})
        except OSError:
            continue
    return {'path': str(path), 'parent': str(path.parent) if path.parent != path else None,
            'folders': folders[:400], 'videos': videos[:400], 'truncated': len(folders) > 400 or len(videos) > 400}
