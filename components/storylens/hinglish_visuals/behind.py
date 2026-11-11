"""Occlude an animated real visual with the talking-head foreground, frame by frame.

The output contains only the visual's visible pixels. The original video/audio stays on
its existing track, so an editor can move or remove the visual independently.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter


def occlude(visual, mask):
    result = visual.convert('RGBA').copy()
    a = np.asarray(result.getchannel('A'), dtype=np.float32)
    foreground = np.asarray(mask.resize(result.size, Image.Resampling.BILINEAR), dtype=np.float32) / 255
    result.putalpha(Image.fromarray(np.round(a * (1 - foreground)).astype(np.uint8)))
    return result


def render_behind(root, timeline, overlay, start, end, target, progress=print):
    from hinglish_cut.compute_policy import require_gpu_implementation
    require_gpu_implementation(root,'Transparent foreground MOV export',False)
    from hinglish_cut.model_preferences import preferences
    settings = preferences(root)
    runtime = Path(settings.get('cuda_runtime_python', sys.executable)) if settings.get('require_cuda_inference') else Path(sys.executable)
    if not runtime.is_file():
        raise RuntimeError('Smart Visuals foreground unavailable: the configured cutout runtime is missing')
    # An isolated process releases the segmentation model after this one short shot.
    command = [str(runtime), '-E', '-X', 'utf8', '-m', 'hinglish_visuals.behind', '--root', str(root),
               '--xml', str(timeline.xml_path), '--overlay', str(overlay), '--start', str(start),
               '--end', str(end), '--output', str(target)]
    progress('Separating the speaker from the background for this visual')
    result = subprocess.run(command, cwd=str(root), capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=max(180, (end - start) * 90),
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode or not Path(target).is_file():
        raise RuntimeError('Smart Visuals foreground unavailable: ' + (result.stderr or result.stdout)[-1200:])
    return Path(target)


def local_masker(root):
    from hinglish_cut.model_storage import configure, role
    from hinglish_cut.model_preferences import preferences
    configure(root)
    settings = preferences(root)
    import onnxruntime as ort
    providers = ['CPUExecutionProvider']
    dll = None
    if settings.get('require_cuda_inference'):
        if 'CUDAExecutionProvider' not in ort.get_available_providers():
            raise RuntimeError('The configured foreground runtime has no CUDA provider')
        import importlib.util
        torch_lib = Path(importlib.util.find_spec('torch').origin).parent / 'lib'
        dll = os.add_dll_directory(str(torch_lib)) if hasattr(os, 'add_dll_directory') else None
        ort.preload_dlls(directory=str(torch_lib))
        providers = [('CUDAExecutionProvider', {'cudnn_conv_algo_search': 'HEURISTIC',
                     'cudnn_conv_use_max_workspace': '0'}), 'CPUExecutionProvider']
    selected = role(root, 'cutout')
    from rembg import new_session, remove
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = new_session('birefnet-general' if selected else 'birefnet-general-lite',
                          sess_opts=options, providers=providers)
    if settings.get('require_cuda_inference') and 'CUDAExecutionProvider' not in session.inner_session.get_providers():
        raise RuntimeError('The requested CUDA foreground model could not initialize')

    def mask(image):
        # Retain the DLL handle and session throughout the shot.
        _ = dll
        sample = image.convert('RGB').copy()
        sample.thumbnail((768, 768), Image.Resampling.LANCZOS)
        result = remove(sample, session=session, only_mask=True).convert('L')
        coverage = float((np.asarray(result) > 128).mean())
        if not .025 < coverage < .95:
            raise ValueError('No usable speaker foreground was found in this frame')
        return result.resize(image.size, Image.Resampling.BILINEAR).filter(
            ImageFilter.GaussianBlur(max(.4, min(image.size) / 1000)))
    return mask, session.inner_session.get_providers()


def process(xml, overlay, start, end, target, masker):
    from hinglish_zoom.xml_apply import Sequence
    from hinglish_zoom.preview import Reader, _frame
    from .render import _Writer, _frames
    seq = Sequence(xml)
    writer = _Writer(target, seq.width, seq.height, seq.fps, alpha=True)
    count = _frames(end - start, seq.fps)
    readers = {}
    visual = Reader(overlay)
    try:
        for index in range(count):
            t = start + index / float(seq.fps)
            frame_index = round(t * float(seq.fps))
            clip = next((c for c in seq.clips if c.start <= frame_index < c.end), None)
            if clip is None:
                raise ValueError('No talking-head video is present under this visual')
            source_in = float(clip.source_in / clip.rate)
            if clip.id not in readers:
                for reader in readers.values():
                    reader.close()
                readers = {clip.id: Reader(clip.path, source_in)}
            image = readers[clip.id].frame_at(source_in + (frame_index - clip.start) / float(seq.fps))
            if image is None:
                raise ValueError('The talking-head frame could not be read')
            canvas = _frame(image.convert('RGB'), clip, 1, (0, 0), seq, seq.width, seq.height, 1)
            mask = masker(canvas)
            art = visual.frame_at(index / float(seq.fps))
            if art is None:
                raise ValueError('The animated visual could not be read')
            writer.write(np.asarray(occlude(art, mask)))
        return writer.finish()
    except BaseException:
        writer.abort()
        raise
    finally:
        visual.close()
        for reader in readers.values():
            reader.close()


def main():
    parser = argparse.ArgumentParser()
    for name in ('root', 'xml', 'overlay', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--start', type=float, required=True)
    parser.add_argument('--end', type=float, required=True)
    args = parser.parse_args()
    masker, providers = local_masker(args.root)
    process(args.xml, args.overlay, args.start, args.end, args.output, masker)
    args.output.with_suffix('.json').write_text(json.dumps({'providers': providers, 'start': args.start,
        'end': args.end, 'foreground_frames_checked': True}), encoding='utf-8')


if __name__ == '__main__':
    main()
