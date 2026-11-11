"""Portable GSAP/ThreeUI compositions rendered through the existing Hyperframes runtime."""
import json
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).with_name('web')


def build(scene, target, width, height, fps):
    folder = Path(target).with_suffix('.composition')
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('vendor', 'fonts'):
        shutil.copytree(WEB / name, folder / name, dirs_exist_ok=True)
    script = 'elements.js' if scene.get('template') == 'element_motion' else 'teacher-world.js' if scene.get('template') == 'teacher_editorial' else 'reference.js' if scene.get('template') == 'reference_layers' else 'creative.js'
    shutil.copyfile(WEB / script, folder / 'creative.js')
    payload = json.loads(json.dumps(scene))
    scale = min(width, height) / 1080
    dw, dh = round(width / scale), round(height / scale)
    payload.update(width=dw, height=dh)
    for i, asset in enumerate(payload.get('data', {}).get('assets', [])):
        from urllib.parse import urlparse, unquote
        src = asset.get('src', '')
        if src.startswith('file:'):
            original = Path(unquote(urlparse(src).path).lstrip('/') if os.name == 'nt' else unquote(urlparse(src).path))
            dest = f'asset-{i}{original.suffix}'
            shutil.copyfile(original, folder / dest); asset['src'] = dest
    text = (WEB / ('teacher-world.html' if scene.get('template')=='teacher_editorial' else 'creative.html')).read_text('utf-8')
    if scene.get('template')=='teacher_editorial':
        script_font=Path('C:/Windows/Fonts/segoesc.ttf')
        if script_font.is_file():
            shutil.copyfile(script_font,folder/'fonts/TeacherScript.ttf')
            text=text.replace('</head>','<style>@font-face{font-family:TeacherScript;src:url(fonts/TeacherScript.ttf)}</style></head>')
    if scene.get('data',{}).get('reference_scene',{}).get('text_groups'):
        from .native_text import bundle
        bundle(folder)
        text=text.replace('</head>','<link rel="stylesheet" href="native-hyperframes.css"></head>')
        text=text.replace('<script src="creative.js"></script>','<script src="native-hyperframes.js"></script><script src="creative.js"></script>')
    metadata = (f'id="composition" data-composition-id="main" data-no-timeline data-start="0" '
                f'data-duration="{float(scene["duration"])}" data-width="{width}" data-height="{height}" data-fps="{float(fps)}"')
    # Hyperframes sizes the composition root to the output resolution. Keep the
    # 1080-based design stage inside it so that normalization cannot shrink it twice.
    text = text.replace('<main id="stage"></main>', f'<div {metadata}><main id="stage"></main></div>')
    text = text.replace('</head>', f'<style>html,body{{width:{width}px;height:{height}px}}'
                        f'#composition{{position:relative;width:{width}px;height:{height}px;overflow:hidden}}'
                        f'#stage{{width:{dw}px;height:{dh}px;transform:scale({scale});transform-origin:top left}}</style></head>')
    encoded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')
    text = text.replace('</body>', '<script>window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};'
                        f'window.__creativeReady=window.mgLoad({encoded});'
                        'window.__hf.buildReady.creative=window.__creativeReady;</script></body>')
    (folder / 'index.html').write_text(text, 'utf-8')
    (folder / 'scene.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), 'utf-8')
    return folder


def render_hyperframes(scene, target, fps, width, height, progress=None, *, device='cpu'):
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.compute_policy import hyperframes_flags
    runtime = ROOT / 'tools/hyperframes-runtime/node_modules'
    node = Path('C:/Program Files/nodejs/node.exe')
    cli = runtime / 'hyperframes/bin/hyperframes.mjs'
    chrome = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
    ffprobe = runtime / '@ffprobe-installer/win32-x64/ffprobe.exe'
    if not all(p.is_file() for p in (node, cli, chrome, ffprobe)):
        raise RuntimeError('Creative motion tools missing: restore the local Hyperframes runtime and retry the saved project.')
    folder = build(scene, target, width, height, fps)
    if device == 'cuda':
        from hinglish_cut.browser_gpu import ready_guard
        html=folder/'index.html'
        html.write_text(ready_guard(html.read_text('utf8')),encoding='utf8')
    env = dict(os.environ, HYPERFRAMES_NO_TELEMETRY='1', HYPERFRAMES_BROWSER_PATH=str(chrome),
               HYPERFRAMES_FFMPEG_PATH=get_ffmpeg_exe(), HYPERFRAMES_FFPROBE_PATH=str(ffprobe))
    log_path = folder / 'render.log'
    confirmed = False
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(node), str(cli), 'render', str(folder), '--output', str(Path(target).resolve()),
            '--fps', str(Fraction(fps)), '--workers', '1', '--quality',
            'draft' if scene.get('quality') == 'preview' else 'high', *hyperframes_flags(device), '--json'],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 900
        try:
            while process.poll() is None:
                output = log_path.read_text('utf-8', errors='replace')
                confirmed = 'artifact validated' in output and 'Render complete' in output
                if confirmed:
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired: break
                if time.monotonic() > deadline:
                    raise RuntimeError('Creative motion render stopped: the render took too long. Retry Quick preview with fewer scenes.')
                time.sleep(.5)
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                else: process.terminate()
                process.wait(timeout=20)
    if process.returncode and not confirmed:
        raise RuntimeError('Creative motion render stopped: ' + log_path.read_text('utf-8', errors='replace')[-1800:])
    import av
    with av.open(str(target)) as container:
        stream = container.streams.video[0]
        actual = float(container.duration or 0) / 1e6
        if abs(actual - float(scene['duration'])) > max(.15, 2 / float(fps)) or (stream.width, stream.height) != (width, height):
            raise RuntimeError('Creative motion render stopped: the saved video is incomplete. Retry the saved project.')
    (folder / 'receipt.json').write_text(json.dumps({'engine': 'Hyperframes + GSAP',
        'depth': scene['template'] == 'orbital_title' or (scene['template'] == 'asset_hero' and bool(scene.get('data',{}).get('depth'))),
        'duration': actual, 'width': width, 'height': height,
        'clock': 'hf-seek', 'output': str(target)}, indent=2), 'utf-8')
    return Path(target)
