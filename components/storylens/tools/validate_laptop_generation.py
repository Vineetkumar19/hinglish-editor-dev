"""Bounded real generation controls, run only after both model downloads finish."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-only', action='store_true')
    parser.add_argument('--normal-image-size', action='store_true',
                        help='Check the editor default 1344x768 image size (requires --image-only).')
    parser.add_argument('--reuse-image',type=Path,
                        help='Use an already-generated control image while checking video workers')
    args = parser.parse_args()
    if args.normal_image_size and not args.image_only:
        parser.error('--normal-image-size requires --image-only')
    folder = ROOT / 'output/validation/new-laptop'
    folder.mkdir(parents=True, exist_ok=True)
    run = folder / ('generation-control-' + uuid.uuid4().hex[:12])
    run.mkdir()
    install = ROOT / 'tools/aigen/install'
    python = install / 'venv/Scripts/python.exe'
    items = [
        {'id': 'laptop-image', 'kind': 'image', 'prompt': 'A red ceramic mug on a wooden table beside a small green plant, soft daylight, realistic photograph.',
         'width': 512, 'height': 512, 'seed': 7, 'out': str(run / 'generated-image-control.png')},
        {'id': 'laptop-video', 'kind': 'video', 'prompt': 'A red ball rolls slowly across a plain wooden floor, fixed camera, soft daylight.',
         'negative': 'blurry, distorted', 'width': 256, 'height': 256, 'frames': 17,
         'fps': 8, 'seed': 7, 'out': str(run / 'generated-video-control.mp4')},
    ]
    items.append(dict(items[1], id='laptop-image-to-video', image=items[0]['out'],
                      out=str(run / 'generated-image-to-video-control.mp4')))
    if args.image_only:
        items = items[:1]
    if args.normal_image_size:
        items[0].update(width=1344, height=768)
    if args.reuse_image:
        source=args.reuse_image.resolve()
        if not source.is_relative_to((ROOT/'output').resolve()) or not source.is_file():
            parser.error('--reuse-image must name an existing generated output')
        items[0]['out']=str(source)
        if len(items)>2: items[2]['image']=str(source)
    jobs = run / 'jobs.json'
    jobs.write_text(json.dumps({'items': items}, indent=2), encoding='utf-8')
    env = dict(os.environ, HF_HUB_OFFLINE='1', HF_HUB_DISABLE_XET='1', PYTHONIOENCODING='utf-8',
               PYTHONFAULTHANDLER='1')
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'): env.pop(key,None)
    receipt = {'passed': False, 'scope': 'Small runtime controls; does not certify production resolution or creative quality.'}
    if args.normal_image_size:
        receipt['scope'] = 'One 1344x768 image at the editor default size; does not certify video resolution or creative quality.'
    receipt['width'], receipt['height'] = items[0]['width'], items[0]['height']
    log_path = run / 'generation-worker.log'
    receipt['worker_log'] = str(log_path)
    receipt['reused_image']=bool(args.reuse_image)
    started = time.monotonic()
    try:
        with log_path.open('w', encoding='utf-8') as log:
            # Match the actual editor: image and video batches run in separate
            # processes so their CPU allocators/offload hooks cannot overlap.
            for kind in ('image','video'):
                batch=[item for item in items if item['kind']==kind]
                if not batch or (kind=='image' and args.reuse_image): continue
                batch_file=run/('jobs-'+kind+'.json')
                batch_file.write_text(json.dumps({'items':batch},indent=2),encoding='utf-8')
                log.write('\nStarting isolated '+kind+' worker\n');log.flush()
                result = subprocess.run([str(python), '-E', '-X', 'utf8','-X','faulthandler',str(ROOT / 'tools/aigen/worker.py'),
                    '--install', str(install), '--jobs', str(batch_file), '--mode', 'offload'],
                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
                receipt.setdefault('worker_return_codes',{})[kind]=result.returncode
                if result.returncode:
                    raise RuntimeError(f'{kind} worker exited {result.returncode}; see {log_path}')
        from PIL import Image
        import av
        with Image.open(items[0]['out']) as image:
            assert image.size == (items[0]['width'], items[0]['height'])
            image.verify()
        for control in items[1:]:
            with av.open(control['out']) as video:
                stream = video.streams.video[0]
                assert (stream.width, stream.height) == (256, 256)
                frames = sum(1 for _ in video.decode(video=0))
                assert frames == 17
        receipt.update(passed=True, image=items[0]['out'])
        if not args.image_only:
            receipt.update(video=items[1]['out'], image_to_video=items[2]['out'], frames=frames)
    except Exception as error:
        receipt['error'] = f'{type(error).__name__}: {error}'
    receipt['seconds'] = round(time.monotonic() - started, 2)
    name = 'image-generation-inference.json' if args.image_only else 'generation-inference.json'
    if args.normal_image_size:
        name = 'image-generation-normal-resolution.json'
    (folder / name).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2), flush=True)
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
