"""Find and run NVIDIA Maxine's Eye Contact engine (GazeRedirectionApp, offline mode). RTX GPUs only."""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import subprocess
import threading
import time

from .settings import FEATURES, load_install

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
APP_NAME = 'GazeRedirectionApp.exe'
RUN_BAT = 'run_gazeredirectionapp_offline.bat'
# Tensor-core GPUs (GeForce/Quadro RTX, TITAN RTX, data-centre A/L/H/B parts). GTX 16xx has none.
TENSOR_GPU = re.compile(r'\bRTX\b|TITAN RTX|\bA\d{1,4}\b|\bL\d{1,2}S?\b|\bH\d{3}\b|\bB\d{3}\b', re.I)


@dataclass
class Gpu:
    name: str
    compute: str = ''
    driver: str = ''
    memory: str = ''

    @property
    def has_tensor_cores(self):
        return bool(TENSOR_GPU.search(self.name))

    @property
    def arch(self):
        """install_feature.ps1 -gpu value: 7.5 -> 75, 8.6 -> 86, 8.9 -> 89, 12.0 -> 120."""
        try:
            major, minor = self.compute.split('.')
            return f'{int(major)}{int(minor)}'
        except ValueError:
            return ''


def gpus():
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=name,compute_cap,driver_version,memory.total',
                              '--format=csv,noheader'], capture_output=True, text=True, timeout=20,
                             creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.stdout.splitlines():
        parts = [p.strip() for p in line.split(',')]
        if parts and parts[0]:
            found.append(Gpu(*(parts + [''] * 4)[:4]))
    return found


@dataclass
class Install:
    app: Path | None = None
    model_dir: Path | None = None
    sdk_root: Path | None = None
    path_dirs: list = field(default_factory=list)
    features: dict = field(default_factory=dict)

    @property
    def missing_features(self):
        return [f for f, ok in self.features.items() if not ok]


def _from_run_bat(bat):
    """The sample build writes the exact DLL folders and model path into its run .bat; reuse them."""
    text = bat.read_text(encoding='utf-8', errors='replace')
    dirs, model = [], None
    path = re.search(r'SET\s+"?PATH=([^"\r\n]*)', text, re.I)
    if path:
        dirs = [d.strip() for d in path.group(1).split(';') if d.strip() and '%PATH%' not in d.upper()]
    found = re.search(r'--model_path="?([^"\r\n]+?)"?(?:\s|$)', text)
    if found:
        model = found.group(1)
    return dirs, model


def _sdk_root_from(dirs):
    for d in dirs:
        if (Path(d) / 'nvARPose.dll').is_file():
            return Path(d).parent
    return None


def find_install(root):
    root = Path(root)
    config = load_install(root)
    app = config.get('app_exe') or os.environ.get('HINGLISH_GAZE_APP')
    app = Path(app) if app else None
    if app is None or not app.is_file():
        tools = root / 'tools' / 'maxine'
        app = next((p for p in sorted(tools.rglob(APP_NAME)) if 'Release' in p.parts), None) if tools.is_dir() else None
    install = Install(app=app)
    bat_dirs, bat_model = [], None
    if app is not None and (app.parent / RUN_BAT).is_file():
        bat_dirs, bat_model = _from_run_bat(app.parent / RUN_BAT)
    sdk = config.get('sdk_root') or _sdk_root_from(bat_dirs)
    install.sdk_root = Path(sdk) if sdk else None
    model = config.get('model_dir') or bat_model or (install.sdk_root / 'bin' / 'models' if install.sdk_root else None)
    install.model_dir = Path(model) if model else None
    dirs = list(config.get('path_dirs') or bat_dirs)
    if install.sdk_root is not None:
        dirs.append(str(install.sdk_root / 'bin'))
        dirs += [str(p) for p in sorted((install.sdk_root / 'features').glob('*/bin'))]
    install.path_dirs = list(dict.fromkeys(d for d in dirs if Path(d).is_dir()))
    features = install.sdk_root / 'features' if install.sdk_root else None
    install.features = {f: bool(features and (features / f.lower()).is_dir()) for f in FEATURES}
    return install


@dataclass
class Report:
    ready: bool
    checks: list          # (ok, text)
    gpu: Gpu | None
    install: Install

    def text(self):
        lines = [('OK   ' if ok else 'NO   ') + t for ok, t in self.checks]
        lines.append('Eye Contact is ready.' if self.ready else
                     'Eye Contact is not ready yet. Run "Setup Eye Contact (RTX).bat" on the RTX laptop.')
        return '\n'.join(lines)


def doctor(root):
    checks = []
    found = gpus()
    gpu = next((g for g in found if g.has_tensor_cores), None)
    if not found:
        checks.append((False, 'No NVIDIA GPU found (nvidia-smi did not answer). Eye Contact needs an NVIDIA RTX GPU.'))
    elif gpu is None:
        checks.append((False, f'{found[0].name} has no Tensor Cores. NVIDIA Eye Contact runs only on RTX GPUs '
                              '(RTX 20/30/40/50 series). It will run on your RTX 5070 Ti laptop.'))
    else:
        checks.append((True, f'GPU {gpu.name} (compute {gpu.compute}, driver {gpu.driver}, {gpu.memory})'))
    install = find_install(root)
    if install.app is None:
        checks.append((False, f'{APP_NAME} not found (not built yet).'))
    else:
        checks.append((True, f'Eye Contact engine: {install.app}'))
    if install.sdk_root is None:
        checks.append((False, 'NVIDIA AR SDK not found.'))
    else:
        checks.append((True, f'NVIDIA AR SDK: {install.sdk_root}'))
        if install.missing_features:
            checks.append((False, 'Missing SDK features: ' + ', '.join(install.missing_features)))
        else:
            checks.append((True, 'SDK features: ' + ', '.join(FEATURES)))
    if install.model_dir is None or not install.model_dir.is_dir():
        checks.append((False, 'Model folder not found.'))
    else:
        checks.append((True, f'Models: {install.model_dir}'))
    return Report(all(ok for ok, _ in checks), checks, gpu, install)


class AviFrameCounter:
    """Counts frames written so far into a growing AVI (each video frame is a '00dc' chunk)."""
    MARK = b'00dc'

    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.frames = 0
        self.tail = b''

    def update(self):
        try:
            with open(self.path, 'rb') as f:
                f.seek(self.offset)
                data = f.read()
        except OSError:
            return self.frames
        self.offset += len(data)
        chunk = self.tail + data             # a mark split across two reads is still counted once
        self.frames += chunk.count(self.MARK)
        self.tail = chunk[-3:]
        return self.frames


def run_gaze(install, source, target, settings, frames, progress=print, label=''):
    """GazeRedirectionApp --offline_mode: `source` video -> `target` .avi (MJPG, no audio)."""
    target = Path(target)
    target.unlink(missing_ok=True)
    command = [str(install.app), *settings.gaze_flags(), f'--model_path={install.model_dir}',
               f'--in={source}', f'--out={target}', '--codec=MJPG']
    env = {**os.environ, 'PATH': ';'.join(install.path_dirs + [os.environ.get('PATH', '')])}
    process = subprocess.Popen(command, cwd=str(install.app.parent), env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, errors='replace', creationflags=NO_WINDOW)
    said = []
    reader = threading.Thread(target=lambda: said.extend(process.stdout), daemon=True)
    reader.start()
    counter, started, last = AviFrameCounter(target), time.time(), 0.0
    while process.poll() is None:
        time.sleep(1.0)
        if time.time() - last >= 5:
            done = min(frames, counter.update())
            speed = done / max(1e-6, time.time() - started)
            eta = (frames - done) / speed if speed > 0 else 0
            progress(f'  Eye contact {label}{done}/{frames} frames ({speed:.0f} fps, ~{eta / 60:.1f} min left)')
            last = time.time()
    reader.join(timeout=5)
    tail = ' '.join(line.strip() for line in said[-6:] if line.strip())
    if process.returncode != 0 or not target.is_file() or target.stat().st_size < 1024:
        raise RuntimeError(f'NVIDIA Eye Contact stopped (code {process.returncode}). {tail}'.strip())
    return target
