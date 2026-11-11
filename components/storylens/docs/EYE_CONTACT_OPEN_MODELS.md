# Free local Eye Contact

The free backend uses the neural gaze-flow weights from **Look at Me! Correcting Eye Gaze in Live Video Communication** (Hsu et al., 2019), with MediaPipe face/iris landmarks. It requires neither an NVIDIA account nor Maxine. All model assets and its isolated Python runtime are under `C:\Ai Models`.

The original model repository includes a BSD redistribution license:
https://github.com/chihfanhsu/gaze_correction/blob/master/LICENSES

The small ONNX exports were obtained from this pinned conversion repository. Its conversion script identifies the original checkpoints and the three model inputs. The macOS application code is not incorporated into this project:
https://github.com/KypMon/coreml-eye-contact/tree/e9d5ae505c62f87851756e966d3e8d1d39b1bcfe/neural

Keep the upstream license and provenance with the weights. The downloaded candidate receipt records source URLs and SHA-256 hashes. The two ONNX graphs total about 2.12 MB. MediaPipe's versioned face-landmarker model is separate:
https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker

The editor's own adapter estimates the correction from iris position, measures the neural model's local response to angle changes, resamples source pixels at their original resolution, and blends through an eye mask. It preserves blinks and large head turns. CPU inference is intentional for this small network; filling GPU memory is unnecessary. This is a practical free alternative, not a verified quality match for NVIDIA's proprietary model.

## Candidates investigated

| Candidate | Public availability | Decision |
|---|---|---|
| Hsu / Look at Me | BSD source and included pretrained weights; small ONNX exports available | Integrate and validate on local footage |
| GazeFlow | MIT source; official 1.56 GB ETH-XGaze checkpoint archive | Download for evaluation; old TensorFlow dependencies require separate compatibility work |
| RTGaze, AAAI 2026 | Official repository currently has only a README | No released implementation/weights to install |
| GazeGaussian, ICCV 2025 | Checkpoint and source available; old CUDA/PyTorch and native rasterizer dependencies; no top-level license in repository inventory | Not selected for this Windows integration |
| coreml-eye-contact application | macOS app; no top-level application license in repository inventory | Do not copy its application code; inspect model provenance only |
| eye-contact-cnn community fork | TensorFlow 1.x; README says research/educational use | Prefer original licensed model |
| STED-gaze | Released PyTorch redirector; GPL/MIT with NVIDIA-licensed exceptions; whole-face preprocessing | Investigated; not selected for the initial eye-only adapter |
| gaze estimators such as Gaze-LLE | Estimate where someone looks | Do not generate corrected eyes |

Sources:
https://github.com/CVI-SZU/GazeFlow
https://github.com/hengfei-wang/RTGaze
https://github.com/ucwxb/GazeGaussian
https://github.com/dtoyoda10/eye-contact-cnn
https://github.com/zhengyuf/STED-gaze

## Setup and checks

From the project directory:

```powershell
pwsh -NoProfile -File tools\eyecontact\setup_open_eyecontact.ps1
.\.venv\Scripts\python.exe -m hinglish_eyecontact --doctor
& 'C:\Ai Models\runtimes\eyecontact\Scripts\python.exe' -E -X utf8 tools\validate_open_eyecontact.py
```

The validation saves real model results under `output\validation\new-laptop\eyecontact-open`. Review the side-by-side video before trusting quality on a long export. Landmark failures, reflections in glasses, and large gaze shifts can limit results.

## Recorded checks on 18 October 2026

Both CPU and CUDA ran the actual two ONNX models successfully. On the same
115-frame camera sample, CPU validation took 12.78 seconds and CUDA validation
took 123.13 seconds, including measurement overhead. The setup retained CPU
because it was faster for this small network. The provider decision is recorded
in `C:\Ai Models\eyecontact\provider-benchmark.json`.

The independent landmark-centering proxy improved from 0.13348 to 0.09439 on
12 sampled frames. This is an implementation control, not a calibrated gaze
angle or subjective quality score. The real localhost job also passed: the
export preserved 115 video frames and its original audio track, and recorded
115 corrected frames. See `eyecontact-open/localhost-inference.json` within the
validation folder. Source footage was retained unchanged.
