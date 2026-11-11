"""Find where the speaker's face is, so zooms go into the face (OpenCV YuNet, local)."""
import hashlib
import json
from pathlib import Path

import numpy as np

from hinglish_broll.library import probe_video, read_frames

YUNET = 'models/opencv/face_detection_yunet_2023mar.onnx'
YUNET_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
DEFAULT_FACE = (.5, .4)     # typical talking-head framing when no face is found


class FaceLocator:
    def __init__(self, root):
        import cv2
        self.cv2, self.root = cv2, Path(root)
        self.cache = self.root / 'cache' / 'zoom' / 'faces'
        self.cache.mkdir(parents=True, exist_ok=True)
        model = self.root / YUNET
        if not model.is_file():
            try:
                import requests
                model.parent.mkdir(parents=True, exist_ok=True)
                data = requests.get(YUNET_URL, timeout=60).content
                if len(data) > 100_000: model.write_bytes(data)
            except Exception:
                pass
        self.yunet = cv2.FaceDetectorYN.create(str(model), '', (320, 320), .7, .3, 50) if model.is_file() else None
        self.haar = None if self.yunet else cv2.CascadeClassifier(
            str(Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'))

    def _detect(self, image):
        """Largest face in a PIL image -> (fx, fy) normalized, aimed slightly above the box centre (eyes)."""
        bgr = np.ascontiguousarray(np.array(image.convert('RGB'))[:, :, ::-1])
        h, w = bgr.shape[:2]
        if self.yunet is not None:
            self.yunet.setInputSize((w, h))
            _, faces = self.yunet.detect(bgr)
            boxes = [] if faces is None else [f[:4] for f in faces]
        else:
            gray = self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2GRAY)
            boxes = list(self.haar.detectMultiScale(gray, 1.1, 5, minSize=(w // 12, w // 12)))
        if not len(boxes):
            return None
        x, y, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
        return float((x + bw / 2) / w), float((y + bh * .42) / h)

    def locate(self, path, source_in, source_out, samples=3):
        """Median face position over a clip's used range, as fractions of the upright frame."""
        path = Path(path)
        try:
            stat = path.stat()
        except OSError:
            return DEFAULT_FACE, False
        span = max(0.0, source_out - source_in)
        times = [round(source_in + span * (k + .5) / samples, 2) for k in range(samples)]
        key = hashlib.sha1(json.dumps([str(path.resolve()), stat.st_size, int(stat.st_mtime), times]).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        if file.exists():
            data = json.loads(file.read_text(encoding='utf-8'))
            return tuple(data['face']), data['found']
        found = []
        try:
            for _, image in read_frames(path, times, size=640):
                hit = self._detect(image)
                if hit: found.append(hit)
        except Exception:
            found = []
        face = (float(np.median([f[0] for f in found])), float(np.median([f[1] for f in found]))) if found else DEFAULT_FACE
        file.write_text(json.dumps({'face': face, 'found': bool(found)}), encoding='utf-8')
        return face, bool(found)


    def face_during(self, path, t0, t1, samples=5, min_share=.6, max_spread=.15):
        """Face position while one zoom runs (source seconds t0..t1), or None when there is no clear,
        steady face (nobody on screen, several people, or the speaker moving a lot)."""
        path = Path(path)
        try:
            stat = path.stat()
        except OSError:
            return None
        times = [round(t0 + (t1 - t0) * (k + .5) / samples, 2) for k in range(samples)]
        key = hashlib.sha1(json.dumps(['during', str(path.resolve()), stat.st_size, int(stat.st_mtime),
                                       times]).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        if file.exists():
            hits = json.loads(file.read_text(encoding='utf-8'))
        else:
            hits = []
            try:
                for _, image in read_frames(path, times, size=640):
                    hit = self._detect(image)
                    if hit: hits.append(hit)
            except Exception:
                hits = []
            file.write_text(json.dumps(hits), encoding='utf-8')
        if len(hits) < max(2, round(min_share * samples)):
            return None
        xs, ys = [h[0] for h in hits], [h[1] for h in hits]
        if max(xs) - min(xs) > max_spread or max(ys) - min(ys) > max_spread:
            return None
        return float(np.median(xs)), float(np.median(ys))


def source_size(path):
    info = probe_video(path)
    if not info:
        raise ValueError(f'No video stream in {Path(path).name}')
    return info[1], info[2]
