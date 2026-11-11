"""Real free-model controls: meaningful edits, no-face passthrough, timing, and a preview."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    import cv2
    import numpy as np
    from hinglish_eyecontact.open_gaze import Corrector, configuration, doctor
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'output/validation/new-laptop/eyecontact-open/frontal-input.mp4')
    parser.add_argument('--provider',choices=['CPUExecutionProvider','CUDAExecutionProvider'])
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    output = args.output or ROOT/'output/validation/new-laptop/eyecontact-open'
    output.mkdir(parents=True,exist_ok=True)
    health = doctor(ROOT)
    assert health.ready, health.text()
    config = configuration(ROOT)
    if args.provider:config['provider']=args.provider
    engine = Corrector(config, look_away=False)
    started = time.monotonic()
    blank = np.full((480,640,3),70,np.uint8)
    assert np.array_equal(engine.correct(blank,0), blank), 'No-face control changed pixels'
    capture = cv2.VideoCapture(str(args.input))
    width,height = int(capture.get(3)),int(capture.get(4))
    fps = capture.get(5) or 30
    movie = cv2.VideoWriter(str(output/'comparison.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width*2,height))
    frame_count = 0
    differences = []
    offsets_before, offsets_after = [], []
    mp = engine.mp
    measure_options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=config['landmark_model']),num_faces=1)
    measurer = mp.tasks.vision.FaceLandmarker.create_from_options(measure_options)
    def offset(image):
        from hinglish_eyecontact.open_gaze import EYES
        result = measurer.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)))
        if not result.face_landmarks:
            return None
        p = np.array([[x.x*width,x.y*height] for x in result.face_landmarks[0]],np.float32)
        distances = []
        for side, indices in EYES.items():
            eye = p[list(indices)]
            center = np.array([(eye[0,0]+eye[3,0])*.5,(eye[1,1]+eye[2,1]+eye[4,1]+eye[5,1])*.25])
            iris = p[468 if side=='R' else 473]
            distances.append(float(np.linalg.norm(iris-center)/np.linalg.norm(eye[3]-eye[0])))
        return float(np.mean(distances))
    best = (0,None,None)
    try:
        while True:
            ok, original = capture.read()
            if not ok:
                break
            corrected = engine.correct(original,(frame_count+1)*1000/fps)
            difference = float(np.mean(np.abs(corrected.astype(np.float32)-original.astype(np.float32))))
            differences.append(difference)
            if frame_count % 10 == 0:
                before, after = offset(original), offset(corrected)
                if before is not None and after is not None:
                    offsets_before.append(before); offsets_after.append(after)
            if difference > best[0]:
                best = (difference,original.copy(),corrected.copy())
            movie.write(np.concatenate([original,corrected],axis=1))
            frame_count += 1
    finally:
        movie.release(); capture.release(); engine.close(); measurer.close()
    assert frame_count > 0
    if best[1] is not None:
        cv2.imwrite(str(output/'before.png'),best[1])
        cv2.imwrite(str(output/'after.png'),best[2])
        cv2.imwrite(str(output/'comparison.png'),np.concatenate([best[1],best[2]],axis=1))
    checks = dict(model_checksums=health.ready,no_face_passthrough=True,
                  face_detected=engine.stats['detected_frames'] > 0,
                  neural_edits=engine.stats['corrected_frames'] > 0 and max(differences) > .001)
    centering = dict(samples=len(offsets_before),before=float(np.mean(offsets_before)) if offsets_before else None,
                     after=float(np.mean(offsets_after)) if offsets_after else None)
    checks['iris_centering_improved'] = bool(offsets_before and centering['after'] < centering['before'])
    receipt = dict(passed=all(checks.values()),checks=checks,stats=engine.stats,frames=frame_count,
                   seconds=time.monotonic()-started,mean_frame_pixel_difference=float(np.mean(differences)),
                   maximum_frame_pixel_difference=max(differences),backend='hsu_onnx',
                   provider=engine.provider,
                   iris_centering_proxy=centering,
                   preview=str(output/'comparison.mp4'),quality_review='Visual and gaze-direction assessment still required')
    (output/'real-inference.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt),flush=True)
    if not receipt['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    sys.path.insert(0,str(ROOT))
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):main()
