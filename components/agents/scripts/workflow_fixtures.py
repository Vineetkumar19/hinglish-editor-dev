"""Tiny synthetic video for isolated transport/inspection tests, never production."""
from pathlib import Path
import subprocess
from core.workflow_media import executable


def video(path, color='blue'):
    ffmpeg = executable('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('Existing ffmpeg is needed to create the test video')
    path = Path(path)
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={color}:s=64x64:r=10:d=0.3',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, capture_output=True, timeout=15,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return path
