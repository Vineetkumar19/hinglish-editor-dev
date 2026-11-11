"""Small CPU-only face bounds for native AE framing. No LLM/GPU/network work."""
import argparse
import hashlib
import json
from pathlib import Path

VERSION = 1


def analyze(path, root):
    root, path = Path(root), Path(path).resolve(strict=True)
    stat = path.stat()
    key = hashlib.sha256(json.dumps([VERSION, str(path), stat.st_size, stat.st_mtime_ns]).encode()).hexdigest()
    cache = root / 'cache' / 'editor-panel' / 'subject-framing'
    saved = cache / (key + '.json')
    if saved.is_file():
        return json.loads(saved.read_text(encoding='utf-8'))
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    cv2.setNumThreads(1)
    model = root / 'models/opencv/face_detection_yunet_2023mar.onnx'
    if not model.is_file():
        raise ValueError('The existing local face detector is missing. Restore models/opencv/face_detection_yunet_2023mar.onnx.')
    detector = cv2.FaceDetectorYN.create(str(model), '', (320, 320), .72, .3, 200)
    still = path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif', '.webp', '.psd', '.exr', '.tga'}
    if still:
        with Image.open(path) as opened:
            if opened.width * opened.height > 60_000_000:
                raise ValueError('This image is too large for quick framing. Use a smaller source copy.')
            image = ImageOps.exif_transpose(opened)
            width, height = image.size
            image.thumbnail((1280, 1280))
            image = image.convert('RGB')
            frames = [(0, image)]
    else:
        from hinglish_broll.library import probe_video, read_frames
        duration, width, height = probe_video(path)
        times = [max(0, duration * v) for v in (.02, .25, .5, .75, .98)]
        frames = read_frames(path, times, size=960)
    hits = []
    for time, image in frames:
        bgr = np.ascontiguousarray(np.array(image.convert('RGB'))[:, :, ::-1])
        h, w = bgr.shape[:2]
        detector.setInputSize((w, h))
        _, found = detector.detect(bgr)
        for f in [] if found is None else found:
            x, y, fw, fh = map(float, f[:4])
            if fw <= 0 or fh <= 0:
                continue
            # Hair/forehead and chin get room; never identify a person.
            box = [max(0., (x - fw * .22) / w), max(0., (y - fh * .55) / h),
                   min(1., (x + fw * 1.22) / w), min(1., (y + fh * 1.25) / h)]
            if box[2] > box[0] and box[3] > box[1]:
                hits.append({'box': box, 'confidence': float(f[-1]), 'time': float(time)})
    value = {'version': VERSION, 'engine': 'OpenCV YuNet CPU', 'width': width, 'height': height,
             'faces': hits, 'sampled_frames': len(frames), 'video_sampled': not still,
             'fingerprint': key, 'source_bytes': stat.st_size, 'source_mtime_ns': stat.st_mtime_ns}
    cache.mkdir(parents=True, exist_ok=True)
    temp = saved.with_suffix('.tmp')
    temp.write_text(json.dumps(value), encoding='utf-8')
    temp.replace(saved)
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--path', required=True)
    args = p.parse_args()
    try:
        result = analyze(args.path, Path(__file__).resolve().parent.parent)
    except Exception as e:
        result = {'error': 'Automatic picture framing could not inspect this media. Copy it again or use a supported image/video.',
                  'code': 'copy_paste_media', 'details': str(e)}
    print(json.dumps(result))
