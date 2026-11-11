"""StoryLens-only MuseTalk 1.5 renderer for the fixed Cortana hologram.

The audio conditioning and masked/reference VAE inputs follow MuseTalk (MIT).
Official model and runtime dependencies are stored beside this file.
"""
from pathlib import Path
import io
import json
import math
import os
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ["HF_HOME"] = str(HERE / "hf")
os.environ["HF_HUB_CACHE"] = str(HERE / "hf" / "hub")
os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, str(HERE / "packages"))
sys.path.insert(1, str(ROOT))

import cv2
import numpy as np
import torch
from diffusers import AutoencoderKL, UNet2DConditionModel
from safetensors.torch import load_file
from transformers import WhisperFeatureExtractor, WhisperModel

MODELS = HERE / "models"
FPS = 25
PORTRAIT = HERE / "cortana-hologram.png"
# Bounding box measured on this one portrait. The mask keeps its eyes, hair
# and suit intact, and blends the generated mouth into the blue projection.
FACE = (0.394, 0.129, 0.590, 0.353)


class Renderer:
    def __init__(self):
        if not torch.cuda.is_available():
            raise RuntimeError("MuseTalk requires the StoryLens NVIDIA CUDA runtime.")
        self.device = torch.device("cuda:0")
        self.dtype = torch.float16
        model_folder = MODELS / "musetalk" / "musetalkV15"
        state = load_file(str(model_folder / "unet_fp16.safetensors"), device="cpu")
        config = json.loads((model_folder / "musetalk.json").read_text(encoding="utf8"))
        with torch.device("meta"):
            model = UNet2DConditionModel.from_config(config)
        model.load_state_dict(state, strict=True, assign=True)
        self.unet = model.to(self.device, self.dtype).eval()
        del state
        self.vae = AutoencoderKL.from_pretrained(
            str(MODELS / "vae"), torch_dtype=self.dtype, local_files_only=True
        ).to(self.device).eval()
        whisper_path = str(MODELS / "whisper")
        self.features = WhisperFeatureExtractor.from_pretrained(whisper_path, local_files_only=True)
        self.encoder = WhisperModel.from_pretrained(
            whisper_path, torch_dtype=self.dtype, local_files_only=True
        ).encoder.to(self.device).eval()
        self.timestep = torch.zeros(1, dtype=torch.long, device=self.device)
        position = torch.arange(50, device=self.device).float().unsqueeze(1)
        angles = position * torch.exp(torch.arange(0, 384, 2, device=self.device) * (-math.log(10000) / 384))
        self.positions = torch.stack((angles.sin(), angles.cos()), dim=-1).flatten(1).to(self.dtype)
        portrait = cv2.imread(str(PORTRAIT))
        if portrait is None:
            raise RuntimeError("The StoryLens hologram portrait is missing.")
        self.portrait = cv2.resize(portrait, (512, 512), interpolation=cv2.INTER_AREA)
        self.box = tuple(round(n * 512) for n in FACE)
        x1, y1, x2, y2 = self.box
        face = self.portrait[y1:y2, x1:x2].copy()
        image = cv2.resize(cv2.cvtColor(face, cv2.COLOR_BGR2RGB), (256, 256), interpolation=cv2.INTER_LANCZOS4)
        reference = torch.from_numpy(image).permute(2, 0, 1).to(self.device, self.dtype).unsqueeze(0) / 127.5 - 1
        masked = reference.clone()
        masked[:, :, 128:] = -1
        with torch.inference_mode():
            latents = self.vae.encode(torch.cat((masked, reference))).latent_dist.mode()
            self.latent = (latents * self.vae.config.scaling_factor).reshape(1, 8, 32, 32)
        # Limit the generated patch to the nose, mouth and chin. Retain the
        # hologram's color and the original pixel structure near its edges.
        width, height = x2-x1, y2-y1
        mask = np.zeros((height, width), dtype=np.float32)
        cv2.ellipse(mask, (width//2, int(height*.73)), (int(width*.37), int(height*.24)), 0, 0, 360, 1, -1)
        self.mask = cv2.GaussianBlur(mask, (0, 0), 3.5)[..., None]

    @torch.inference_mode()
    def frames(self, samples, batch_size=4, step=1, reserve=None):
        if not 640 <= len(samples) <= 30 * 16000:
            raise ValueError("Avatar replies must contain 0.04 to 30 seconds of audio at 16 kHz.")
        from contextlib import nullcontext
        slot = reserve or nullcontext
        count = len(samples) // (16000 // FPS)
        with slot():
            features = self.features(samples, sampling_rate=16000, return_tensors="pt").input_features
            features = features.to(self.device, self.dtype)
            hidden = torch.stack(self.encoder(features, output_hidden_states=True).hidden_states, dim=2)[0]
            hidden = hidden[:count * 2]
            blank = hidden.new_zeros((6, *hidden.shape[1:]))
            hidden = torch.cat((blank[:4], hidden, blank))
        x1, y1, x2, y2 = self.box
        for begin in range(0, count, batch_size * step):
            end = min(count, begin + batch_size * step)
            with slot():
                indices = torch.arange(begin * 2, end * 2, 2 * step, device=self.device)[:, None]
                indices = indices + torch.arange(10, device=self.device)
                prompts = hidden[indices].flatten(1, 2) + self.positions
                predicted = self.unet(
                    self.latent.expand(len(indices), -1, -1, -1), self.timestep,
                    encoder_hidden_states=prompts
                ).sample
                decoded = self.vae.decode(predicted / self.vae.config.scaling_factor).sample
                patches = ((decoded / 2 + .5).clamp(0, 1) * 255).to(torch.uint8)
                patches = patches.permute(0, 2, 3, 1).cpu().numpy()
            for patch in patches:
                frame = self.portrait.copy()
                source = frame[y1:y2, x1:x2]
                generated = cv2.resize(patch[..., ::-1], (x2-x1, y2-y1), interpolation=cv2.INTER_AREA)
                source[:] = np.rint(source * (1 - self.mask) + generated * self.mask).astype(np.uint8)
                yield frame


def sample_audio(path):
    import soundfile
    from scipy.signal import resample_poly
    samples, rate = soundfile.read(path, dtype="float32", always_2d=True)
    mono = samples.mean(axis=1)
    gcd = math.gcd(rate, 16000)
    return resample_poly(mono, 16000 // gcd, rate // gcd)


def benchmark(audio, output):
    import subprocess
    import imageio_ffmpeg
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT, timeout=.2):
        start = time.perf_counter()
        renderer = Renderer()
        print("Loaded MuseTalk in", round(time.perf_counter()-start, 3), "seconds", flush=True)
        samples = sample_audio(audio)
        results = []
        for _ in range(2):
            start = time.perf_counter()
            frames = renderer.frames(samples)
            first = next(frames)
            first_frame_ms = (time.perf_counter() - start) * 1000
            remaining = list(frames)
            total = time.perf_counter() - start
            results.append({"first_frame_ms": round(first_frame_ms), "total_s": round(total, 3),
                            "frames": 1 + len(remaining), "fps": round((1 + len(remaining))/total, 1),
                            "gpu_peak_mib": round(torch.cuda.max_memory_allocated()/2**20)})
            print(json.dumps(results[-1]), flush=True)
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n",
                   "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "512x512", "-r", str(FPS), "-i", "pipe:0",
                   "-i", str(audio), "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(output)]
        with subprocess.Popen(command, stdin=subprocess.PIPE, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as encoder:
            with encoder.stdin as pipe:
                for frame in (first, *remaining):
                    pipe.write(frame.tobytes())
            if encoder.wait(timeout=20):
                raise RuntimeError("Could not encode the MuseTalk preview.")
        output.with_suffix(".json").write_text(json.dumps(results,indent=2), encoding="utf8")


def stream_replies():
    import base64
    import struct
    from hinglish_cut.gpu_lock import gpu_lock

    def reserve():
        return gpu_lock(ROOT, timeout=.12)

    with gpu_lock(ROOT, timeout=1):
        renderer = Renderer()
    # Prime CUDA kernels before accepting time-sensitive visual frames.
    for _ in renderer.frames(np.zeros(3_200, dtype=np.float32), batch_size=2, step=2, reserve=reserve):
        pass
    print("ready", flush=True)
    while length := sys.stdin.buffer.read(4):
        size, = struct.unpack("<I", length)
        if not 44 <= size <= 3_000_000:
            return
        wav = sys.stdin.buffer.read(size)
        if len(wav) != size:
            return
        try:
            step = 2
            x1, y1, x2, y2 = renderer.box
            for index, frame in enumerate(renderer.frames(sample_audio(io.BytesIO(wav)),
                                                         batch_size=2, step=step, reserve=reserve)):
                ok, patch = cv2.imencode(".jpg", frame[y1:y2, x1:x2], [cv2.IMWRITE_JPEG_QUALITY, 93])
                if ok:
                    row = [index * step / FPS, base64.b64encode(patch).decode("ascii")]
                    print(json.dumps(row, separators=(",", ":")), flush=True)
        except (OSError, ValueError, RuntimeError, TimeoutError):
            import traceback
            traceback.print_exc()
        print("end", flush=True)


if __name__ == "__main__" and sys.argv[1:] == ["--stream"]:
    stream_replies()
elif __name__ == "__main__":
    benchmark(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
