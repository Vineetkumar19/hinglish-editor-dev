# Song lyrics and NVIDIA RTX correction

The actual uploaded `Rog Music.mp4` was 15.4 seconds. Its old speech-only output
contained `nan nan nan`, and the quality checker incorrectly called it 100%.
The invalid result is preserved for diagnosis, with its quality now failed at
0/100. Both recognizer output and cached transcripts reject these placeholders.

Song mode uses the installed C-drive faster-whisper-large-v3 on CUDA FP16,
explicit Hindi transcription and the full audio excerpt without speech VAD
cuts. Automatic language detection incorrectly selected English in the control;
the Prime speech specialist also failed this sung example.

Supplied lyrics are authoritative for spelling and phrase boundaries. Independent
recognized words must agree in count and at least 75% phonetic correspondence
before their ordered word attention can be transferred to the reference. This
example corrected three recognition mismatches (`Haan`, `Ho`, `yakeen`). Those
corrections remain visible in metadata. Other references use checked forced
alignment or fail for review. No general speech matching or factual thresholds
were weakened. Neither coverage nor layout quality certifies lyric accuracy.

The corrected four-line project preserves `Kissi` exactly. Its final readable
karaoke version has all 462 video frames and the original audio stream. The
source SHA-256 remained unchanged. Caption editing preserves lyric phrases and
rebuilds the burned-in MP4 so changing text/style cannot leave a stale video.
Timing remains model-aligned and reviewable; auditory review was not available.

## RTX behavior

This machine is an NVIDIA GeForce RTX 5070 Ti Laptop GPU with 12 GB dedicated
memory. Localhost jobs enforce the selected CUDA preference. The song model
reported CUDA; the job reached 97% sampled GPU utilization and 8,000 MiB total
device memory. The latter includes other allocations and is not isolated model
VRAM. The MP4 encoder was `h264_nvenc`, with no silent CPU encoder fallback.

Silero VAD and CLAP passed actual CUDA inference. Full BiRefNet used the already
installed GPU ONNX runtime: its actual operator profile contained 4,821 CUDA
operations, including 396 convolution/matrix operations, and its alpha mask
passed foreground/background checks. Requested CUDA vision and sound inference
cannot silently downgrade to CPU. Hsu Eye Contact is configured for CUDA and
has an existing passing real CUDA receipt. All weights and model caches remain
under `C:\Ai Models`; no new model download was needed for this repair.

CPU still handles text rasterization, transparent qtrle overlays, file I/O,
audio preprocessing, current MediaPipe/YuNet execution and some other video
renderers. Large image/video generation retains CPU offload to fit VRAM.
GPU utilization will fall between neural inference and NVENC stages. Requiring
RTX for supported AI does not make every application operation GPU-compatible.

The cold BiRefNet control took 223.82 seconds, then a subsequent process took
32.51 seconds on the same input after warming the CUDA caches. Earlier Hsu GPU inference took
123.13 seconds versus 12.78 seconds on CPU. Their successful CUDA execution
does not establish a speed advantage. Scheduled work remains paused, publishing
is disabled in the local server, and critical-battery protection is unchanged.

## Validation

- 128 focused caption, server, model preference, cleaning, motion, sound, B-roll
  and semantic tests passed.
- 66 focused tests passed after the final lyric routing, rebuild and GPU-policy
  changes.
- 31 final Eye Contact, song and server tests passed after correcting the CUDA
  status label. Restarted localhost reports the actual NVIDIA device, requires
  CUDA in the UI, and passes the original-audio bitstream comparison.
- `output/validation/song-captions/corrected-localhost-result.json`: actual
  localhost song job, exact four phrases, CUDA, NVENC, audio/video, original hash.
- `output/validation/song-captions/rtx-policy-check.json`: real Silero, full
  BiRefNet and CLAP device checks.
- `output/validation/song-captions/localhost-final-check.json`: restarted editor
  status, required RTX mode and preserved source audio.
- `output/validation/new-laptop/eyecontact-cuda/real-inference.json`: existing
  real Hsu CUDA neural-edit control.

These results do not certify every task, input, visual effect or transcription
as perfect. Inspect the final MP4 for subjective styling and sung-word timing.
