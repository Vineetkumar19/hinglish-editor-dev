"""Choose the configured free local backend, retaining optional Maxine support."""
from pathlib import Path
from . import maxine, open_gaze


def doctor(root):
    if Path(root, open_gaze.CONFIG).is_file():
        return open_gaze.doctor(root)
    return maxine.doctor(root)


def run_gaze(root, health, source, target, settings, frames, progress=print, label=''):
    if getattr(health, 'backend', '') == 'hsu_onnx':
        return open_gaze.run_gaze(root, health.install, source, target, settings, frames, progress, label)
    return maxine.run_gaze(health.install, source, target, settings, frames, progress, label)
