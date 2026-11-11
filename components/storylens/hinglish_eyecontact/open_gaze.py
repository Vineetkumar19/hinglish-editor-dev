"""Local BSD-licensed Hsu gaze weights with a separate MediaPipe runtime.

The model predicts eye flow; full-resolution source pixels are resampled instead
of enlarging the model's 64x48 reconstruction. No NVIDIA SDK or network calls.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

CONFIG = 'config.eyecontact.open.local.json'
HASHES = {'gaze_L.onnx': 'f39ee44e76c4efbd0bace9295baab7a8c823ac18a4ff7f5b725ddbfbf2bd50e1',
          'gaze_R.onnx': 'f64f721e805c8bcbf2d0b96b889fe957f480e5e328014a9ee6e93d68f0aa2d47'}
EYES = {'R': (33, 160, 158, 133, 153, 144),
        'L': (263, 387, 385, 362, 380, 373)}


def configuration(root):
    file = Path(root) / CONFIG
    return json.loads(file.read_text(encoding='utf-8-sig')) if file.is_file() else {}


@dataclass
class Health:
    ready: bool
    checks: list
    install: dict
    gpu: object = None
    backend: str = 'hsu_onnx'
    label: str = 'Open Eye Contact (Hsu neural flow, CPU)'

    def text(self):
        return '\n'.join(('OK   ' if ok else 'NO   ') + message for ok, message in self.checks)


def doctor(root):
    config = configuration(root)
    checks = [(config.get('backend') == 'hsu_onnx', 'Free local Hsu neural eye-contact backend')]
    for key in ('runtime_python', 'landmark_model'):
        checks.append((bool(config.get(key) and Path(config[key]).is_file()), key.replace('_', ' ')))
    folder = Path(config.get('model_dir', '__missing_eyecontact_models__'))
    for name, digest in HASHES.items():
        file = folder / name
        valid = file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == digest
        checks.append((valid, name + ' checksum'))
    checks.append((Path(root, 'hinglish_eyecontact', 'open_gaze.py').is_file(), 'Open eye-contact worker'))
    label = 'Open Eye Contact (Hsu neural flow, '+('CUDA' if config.get('provider')=='CUDAExecutionProvider' else 'CPU')+')'
    gpu=None
    if config.get('provider')=='CUDAExecutionProvider':
        from .maxine import gpus
        available=gpus();gpu=available[0] if available else None
        checks.append((gpu is not None,'NVIDIA GPU available for the selected CUDA eye network'))
    return Health(all(ok for ok, _ in checks), checks, config, gpu=gpu, label=label)


def run_gaze(root, install, source, target, settings, frames, progress=print, label=''):
    command = [install['runtime_python'], '-E', '-X', 'utf8', '-u', '-m', 'hinglish_eyecontact.open_gaze',
               '--root', str(root), '--input', str(source), '--output', str(target),
               '--reach', settings.reach, '--eye-size', str(settings.eye_size)]
    if not settings.look_away:
        command.append('--no-look-away')
    progress('  ' + label + 'Open Eye Contact: local neural eye correction')
    environment = dict(os.environ)
    environment['MPLCONFIGDIR'] = str(Path(install['runtime_python']).parents[1]/'matplotlib-cache')
    process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    tail = []
    for line in process.stdout:
        tail.append(line.strip())
        if len(tail) > 12:
            tail.pop(0)
        progress('  ' + line.strip())
    if process.wait() or not Path(target).is_file():
        raise RuntimeError('Open Eye Contact failed: ' + ' '.join(tail))
    return Path(target)


def anchor_maps(points, origin, size):
    import numpy as np
    height, width = size
    anchors = np.asarray(points, dtype=np.float32) - np.asarray(origin, dtype=np.float32)
    anchors *= np.array([64 / width, 48 / height], np.float32)
    # The published network was trained with integer pixel anchors.
    anchors = np.trunc(anchors)
    yy, xx = np.mgrid[:48, :64].astype(np.float32)
    return np.stack([component for x, y in anchors for component in (xx - x, yy - y)], axis=-1)[None]


def eye_openness(points):
    import numpy as np
    p = np.asarray(points)
    width = float(np.linalg.norm(p[3] - p[0]))
    return float((np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])) / max(2 * width, 1e-6))


def solve_angles(jacobian, displacement, limit):
    import numpy as np
    if not np.isfinite(jacobian).all() or np.linalg.cond(jacobian) > 100:
        return None
    return np.clip(np.linalg.solve(jacobian, displacement), -limit, limit).astype(np.float32)


class Corrector:
    def __init__(self, config, reach='near', look_away=True, eye_size=3):
        import mediapipe as mp
        import numpy as np
        import onnxruntime as ort
        self.mp, self.np = mp, np
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=config['landmark_model']),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1,
            min_face_detection_confidence=.6, min_face_presence_confidence=.6,
            min_tracking_confidence=.6, output_facial_transformation_matrixes=True)
        self.detector = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 4
        session_options.inter_op_num_threads = 1
        provider = config.get('provider','CPUExecutionProvider')
        providers = ['CPUExecutionProvider']
        if provider == 'CUDAExecutionProvider':
            import importlib.util
            torch_lib = Path(importlib.util.find_spec('torch').origin).parent/'lib'
            self.dll_directory = os.add_dll_directory(str(torch_lib)) if hasattr(os,'add_dll_directory') else None
            ort.preload_dlls(directory=str(torch_lib))
            providers = [('CUDAExecutionProvider',{'cudnn_conv_algo_search':'HEURISTIC',
                          'cudnn_conv_use_max_workspace':'0','gpu_mem_limit':512*1024**2}), 'CPUExecutionProvider']
        self.sessions = {side: ort.InferenceSession(str(Path(config['model_dir']) / ('gaze_' + side + '.onnx')),
                         sess_options=session_options, providers=providers) for side in EYES}
        if provider == 'CUDAExecutionProvider' and not all('CUDAExecutionProvider' in s.get_providers() for s in self.sessions.values()):
            raise RuntimeError('The requested CUDA provider did not initialize; CPU configuration is unchanged')
        self.provider = provider
        self.limit = 20 if reach == 'near' else 28
        self.look_away = look_away
        self.smooth = {}
        self.eye_size = eye_size
        self.blink_threshold = .14 + (eye_size-3)*.0125
        self.last_ms = -1
        self.stats = dict(frames=0, detected_frames=0, corrected_frames=0, corrected_eyes=0,
                          blink_skips=0, pose_skips=0, small_eye_skips=0)

    def close(self):
        self.detector.close()

    def correct(self, frame, timestamp_ms):
        import cv2
        np = self.np
        self.stats['frames'] += 1
        timestamp_ms = max(self.last_ms + 1, int(timestamp_ms))
        self.last_ms = timestamp_ms
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.detector.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
        if not result.face_landmarks:
            self.smooth.clear()
            return frame
        self.stats['detected_frames'] += 1
        h, w = frame.shape[:2]
        points = np.array([[p.x * w, p.y * h] for p in result.face_landmarks[0]], np.float32)
        # Full frontal correction is unsafe during large head turns.
        left, right, nose = points[33], points[263], points[1]
        interocular = float(np.linalg.norm(right - left))
        if interocular < 30:
            self.stats['small_eye_skips'] += 1
            return frame
        asymmetry = abs(float(np.linalg.norm(nose-left) - np.linalg.norm(nose-right))) / interocular
        roll = abs(float(np.degrees(np.arctan2(right[1]-left[1], right[0]-left[0]))))
        if asymmetry > .4 or roll > 25:
            self.stats['pose_skips'] += 1
            self.smooth.clear()
            return frame
        output = frame.copy()
        corrected = 0
        for side, indices in EYES.items():
            eye = points[list(indices)]
            openness = eye_openness(eye)
            if openness < self.blink_threshold:
                self.stats['blink_skips'] += 1
                self.smooth.pop(side, None)
                continue
            eye_width = float(np.linalg.norm(eye[3]-eye[0]))
            if eye_width < 16:
                self.stats['small_eye_skips'] += 1
                continue
            center = (eye[0]+eye[3])*.5
            crop_width = eye_width * 1.5
            crop_height = crop_width * .75
            x0, x1 = int(center[0]-crop_width*.5), int(center[0]+crop_width*.5)
            y0, y1 = int(center[1]-crop_height*7/12), int(center[1]+crop_height*5/12)
            if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
                continue
            crop = frame[y0:y1, x0:x1]
            ch, cw = crop.shape[:2]
            iris = points[468 if side == 'R' else 473]
            target = np.array([center[0], (eye[1,1]+eye[2,1]+eye[4,1]+eye[5,1])*.25], np.float32)
            desired = np.clip((iris-target) * [64/cw, 48/ch], -7, 7).astype(np.float32)
            previous = self.smooth.get(side)
            desired = desired if previous is None else previous*.65 + desired*.35
            self.smooth[side] = desired
            if float(np.linalg.norm(desired)) < .2:
                continue
            inputs = {'input_img:0': (cv2.resize(crop, (64,48)).astype(np.float32)/255)[None],
                      'input_fp:0': anchor_maps(eye, (x0,y0), (ch,cw)),
                      'input_ang:0': np.zeros((1,2), np.float32)}
            session = self.sessions[side]
            # Names are taken from the graph, so equivalent exports stay usable.
            feeds = {item.name: inputs[item.name if item.name in inputs else item.name+':0'] for item in session.get_inputs()}
            angle_name = next(item.name for item in session.get_inputs() if 'ang' in item.name)
            flow_name = next(item.name for item in session.get_outputs() if 'flow_raw' in item.name)
            light_name = next(item.name for item in session.get_outputs() if 'lcm_map' in item.name)
            base, base_light = session.run([flow_name, light_name], feeds)
            base = np.tanh(base[0])
            sample = np.rint((target-[x0,y0])*[64/cw,48/ch]).astype(int)
            sx, sy = np.clip(sample,[0,0],[63,47])
            columns = []
            for axis in range(2):
                angle = np.zeros((1,2), np.float32); angle[0,axis] = 6
                feeds[angle_name] = angle
                test = session.run([flow_name], feeds)[0][0]
                columns.append((np.tanh(test)[sy,sx]-base[sy,sx])*[32,24]/6)
            angles = solve_angles(np.stack(columns, axis=1), desired, self.limit)
            if angles is None:
                continue
            feeds[angle_name] = angles[None]
            flow, light = session.run([flow_name, light_name], feeds)
            flow = cv2.resize(np.tanh(flow[0])-base, (cw,ch))
            strength = min(1., max(0., (openness-self.blink_threshold)/.10)) * .8
            if self.look_away:
                # Preserve brief glances; this is deterministic for an offline clip.
                phase = (timestamp_ms/1000) % 9
                if phase > 8:
                    strength *= abs(phase-8.5)*2
            yy, xx = np.mgrid[:ch,:cw].astype(np.float32)
            mapx = xx + np.clip(flow[...,0]*cw*.5, -cw*.18, cw*.18)*strength
            mapy = yy + np.clip(flow[...,1]*ch*.5, -ch*.18, ch*.18)*strength
            redirected = cv2.remap(crop, mapx.astype(np.float32), mapy.astype(np.float32), cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)
            delta_light = cv2.resize(light[0,...,1]-base_light[0,...,1], (cw,ch))
            delta_light = np.clip(delta_light,-.06,.06)[...,None]*strength
            redirected += (255-redirected)*delta_light
            mask = np.zeros((ch,cw), np.float32)
            cv2.fillConvexPoly(mask, np.rint(eye-[x0,y0]).astype(np.int32), 1)
            radius = max(1, round(eye_width*.025))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,2*radius+1))
            mask = cv2.dilate(mask,kernel)
            mask = cv2.GaussianBlur(mask,(0,0),max(.7,eye_width*.025))[...,None]
            output[y0:y1,x0:x1] = np.clip(crop*(1-mask)+redirected*mask,0,255).astype(np.uint8)
            corrected += 1
        self.stats['corrected_eyes'] += corrected
        self.stats['corrected_frames'] += bool(corrected)
        return output


def main():
    import cv2
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--reach', default='near')
    parser.add_argument('--no-look-away', action='store_true')
    parser.add_argument('--eye-size', type=int, default=3)
    args = parser.parse_args()
    health = doctor(args.root)
    if not health.ready:
        raise RuntimeError(health.text())
    corrector = Corrector(health.install, args.reach, not args.no_look_away, args.eye_size)
    capture = cv2.VideoCapture(args.input)
    if not capture.isOpened():
        raise RuntimeError('Cannot open eye-contact input')
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    size = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    writer = cv2.VideoWriter(args.output,cv2.VideoWriter_fourcc(*'MJPG'),fps,size)
    if not writer.isOpened():
        raise RuntimeError('Cannot create eye-contact video')
    started = time.monotonic()
    count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result = corrector.correct(frame,count*1000/fps)
            writer.write(result)
            count += 1
            if count % 120 == 0:
                print(f'{count} frames processed; {corrector.stats["corrected_frames"]} corrected',flush=True)
    finally:
        capture.release(); writer.release(); corrector.close()
    if not count:
        raise RuntimeError('No video frames decoded')
    stats = {**corrector.stats, 'seconds':time.monotonic()-started,'backend':'hsu_onnx','provider':corrector.provider}
    Path(args.output).with_suffix('.stats.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    print(json.dumps(stats),flush=True)


if __name__ == '__main__':
    main()
