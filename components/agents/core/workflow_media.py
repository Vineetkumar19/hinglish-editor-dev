"""Read-only media validation of owner-selected release exports."""
from pathlib import Path
import json
import shutil
import subprocess
from . import config


def executable(name):
    configured = config.get('SUITE_' + name.upper())
    if configured:
        return str(configured)
    found = shutil.which(name)
    if found:
        return found
    path = config.profiles_dir() / 'workflow_runtime.json'
    if path.exists():
        candidate = json.loads(path.read_text(encoding='utf-8')).get(name)
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def inspect_video(path):
    source = Path(path)
    if source.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm', '.m4v'):
        raise ValueError('Publication requires an actual video export')
    probe = executable('ffprobe')
    if not probe:
        raise ValueError('ffprobe is required to verify release media')
    result = subprocess.run([probe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)],
        capture_output=True, text=True, timeout=15,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError('Release export failed media inspection')
    data = json.loads(result.stdout)
    video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    duration = float(data.get('format', {}).get('duration', 0))
    if not video or duration <= 0 or video.get('width', 0) <= 0 or video.get('height', 0) <= 0:
        raise ValueError('Export has no playable video stream or positive duration')
    return {'duration_seconds': duration, 'width': video['width'], 'height': video['height'],
            'codec': video.get('codec_name'), 'audio_streams': sum(s.get('codec_type') == 'audio' for s in data['streams']),
            'validation': 'container/stream inspection; artistic approval remains source-bound'}
