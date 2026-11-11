# Storylens model setup on the RTX 5070 Ti laptop

**18 October storage update:** all model weights now physically reside under `C:\Ai Models`.
The previous model directories on A: are compatibility junctions. The higher model
replacements are still downloading; the installed models in the table below remain
active until replacement inference checks and index conversion finish. See
[the C-drive upgrade record](../output/validation/new-laptop/C_DRIVE_MODEL_UPGRADE.md).

**Local editor:** `http://127.0.0.1:8765/`. Start an editing-only local session with
`pwsh -NoProfile -File tools\host_local_editor.ps1`; this keeps scheduled publishing
off. Live model check receipts are written to
`output/validation/new-laptop/localhost-model-checks.json`.

Setup started 17 October 2026; resumed and rechecked 18 October. Hardware was queried directly: Ryzen 9 8940HX,
16 cores / 32 logical processors, 16 GB system RAM, RTX 5070 Ti Laptop GPU with
12,227 MiB VRAM, driver 617.42, driver CUDA support 13.4.

## Model selection

| Task | Selected model | Why |
| --- | --- | --- |
| Conversational planning, motion direction, entity research and sound planning | Ollama Qwen3.5 9B Q4_K_M | Installed. Thinking enabled for planning; tested multi-step planner controls pass after preserving literal caption-template choices. |
| Compatibility with existing fixed-tag scripts | Ollama Qwen3 8B | Preserves the project's original adapter and documentary-worker entry points. |
| Script Edit and B-roll's bundled semantic engine | Qwen3 4B Instruct 2507 Q4_K_M, existing pinned revision | Imported as `storylens-meaning:4b` into Ollama. Existing prompts, schemas and revision checks retained; real GPU inference passed. |
| Roman Hinglish transcription | Oriserve Whisper-Hindi2Hinglish-Swift | Existing specialized transcript format and editing pipeline. |
| Independent multilingual transcription | faster-whisper large-v3-turbo | Existing independent speech path, float16 CUDA / int8 CPU. |
| Word alignment | MMS 300M 1130 forced aligner | Existing Romanized alignment vocabulary and word timing contract. |
| Documentary and semantic retrieval | multilingual E5 small | Existing vectors must retain their original embedding encoder. |
| Sound-library semantic search | Ollama Qwen3 Embedding 0.6B | Separate existing sound index; does not replace E5. |
| B-roll ranking | CLIP ViT-B/32 | Existing image/text vector representation and cached footage index. |
| Sound recognition/ranking | LAION larger CLAP general | Existing mixed-audio and sound-library representation. |
| Background removal | rembg BiRefNet general lite / ISNet general use | Existing photo cutout engine; ONNX CPU provider avoids competing for GPU memory. |
| Face location | OpenCV YuNet | Existing lightweight face-aware zoom engine. |
| AI images and first frames | Z-Image Turbo, official BF16 variant at revision `367372dab44eb24c5908d1f6d867b66123cb390d` | 19.13 GiB selected weights/configuration; staged text encoding and CPU offload on this GPU. |
| AI video | Wan 2.2 TI2V 5B Diffusers | Existing video worker integration; staged text encoding and CPU offload. |
| Legacy Transformers semantic verifier | Qwen2.5 1.5B Instruct | Kept for compatibility with existing verifier settings. |

“Best” is task-dependent. This setup does not claim a universal quality winner or
that download completion proves successful inference. The 27B/35B planning
models do not fit comfortably on this laptop's current GPU/RAM combination.

## Changes and backups

- The copied Python 3.12 environment was preserved as `.venv-old-laptop-*`.
- The new `.venv` uses installed Python 3.13.16. Python 3.15 remains separate.
- `setup.ps1` now detects an unusable copied virtual environment before setup.
- Local model/runtime manifests are relocated only when their replacement files exist.
- The original llama.cpp CPU runtime remains under `tools/llama/b11011`.
- The existing Ollama GPU runtime now also runs the pinned 4B model; the redundant additional CUDA runtime download was stopped, retaining its partial archives. Its optional installer still checks published release digests.
- Central model preferences are optional, and explicit custom model selections retain priority.
- No embedding encoder or saved documentary database is replaced.
- Model choice/context tests cover explicit overrides and GPU-memory handoff.
- Core rembg installation now explicitly includes its required ONNX runtime.

## Download and validation records

The running setup writes its latest result to
`output/validation/new-laptop/SETUP_STATUS.md`. Core inference runs after the
isolated environment is ready; RTX defaults are activated only if all core
controls pass. Image/video controls run after both downloads and their separate
environment are ready. See `downloads/verification-coordinator.log` for progress.
If a shutdown or connection failure interrupts setup, use
`Resume Laptop Model Setup.bat`. It reuses checked files and refuses to start a
second setup while the current workers are active. Keep the laptop plugged in
and awake while the large downloads run.

### Installed development software

Verified: Python 3.13.16, Git 2.56, Node.js 24.22 LTS/npm 11.19, Temurin
Java 25, VS Code, Git LFS, Visual Studio C++ Build Tools, NVIDIA driver and
Ollama 0.40.5. MySQL and PostgreSQL services are running. The editor itself
uses Python and a local HTML/JavaScript UI; Java, Maven, Node and additional
databases are not prerequisites for its core editing tools. Python 3.15 is
also installed, but this project's environment uses supported Python 3.13.
Visual Studio includes CMake 4.3.1; Eye Contact setup now discovers that bundled
copy without requiring another standalone CMake installation.

### Completed real model checks

- `storylens-meaning:4b`: the editor's structured B-roll client and semantic
  judge passed real inference. A numerical contradiction was rejected and a
  Roman Hinglish paraphrase accepted. Ollama reported all 3,877,571,133 loaded
  bytes in VRAM, with 8,192-token context. The first structured request took
  11.91 seconds including loading; this is a small control, not a video benchmark.
- Qwen3.5 9B: read text and shapes from actual generated test pixels. Its
  loaded 5,862,210,928 bytes were entirely in VRAM at the tested 8,192 context.
- Qwen3.5 9B planning: the five bounded assistant cases pass in reasoning mode
  with a deterministic guard preserving an explicitly requested caption-template
  number. This does not validate every creative editing request.
- Qwen3.5 9B without thinking failed a Hinglish paraphrase control and some
  planner cases. Those failure reports are retained; the pinned 4B model remains
  the semantic judge. Planning uses thinking mode and normal validation/review.
- Caption rendering now has bundled, licensed fonts; it no longer depends on
  the old laptop's separately installed fonts.
- Qwen3 Embedding 0.6B: downloaded and passed real inference, producing two
  finite 1,024-dimensional sound-search vectors. The fixed E5 documentary
  encoder and its existing vector database remain separate.
- The full regression suite passed: 614 tests run, 25 environment-dependent
  tests skipped. This run used preserved compatible Python 3.12 packages while
  the new Python 3.13 CUDA environment was downloading. A subsequent 54-test
  dashboard/chat/preferences run also passed after adding optional device defaults.
- Qwen3 8B is installed for compatibility. Its real reasoning-mode planning
  check passed four of five cases; the negated-caption request produced no
  editing steps. It is not the default planner on this laptop.

The new Python 3.13 environment passed the complete regression suite on 18 October:
615 tests ran in 278 seconds, with 25 skipped. Both core and generation environments
passed `pip check`. The built-in editor doctor passed all imports and its CUDA
matrix calculation. See `downloads/project-test-suite-python313.log` and
`downloads/core-doctor.log`.

Real core inference passed for CUDA arithmetic, Roman Hinglish speech, silence
detection, MMS word alignment, independent Turbo speech, E5 retrieval, CLIP image
ranking, CLAP audio ranking, the pinned Qwen structured-output client, and YuNet.
Background-removal inference initially hit a network timeout; both official ONNX
files are now complete, match rembg's specified MD5 checksums, and passed actual
RGBA output checks. SHA-256 fingerprints are also recorded in `cutout-downloads.json`.
Real image generation passed at 512 x 512, using the official BF16 Z-Image weights
with staged encoding and FP8 transformer storage. The mug/plant control took
15.6 seconds to generate; the full fresh worker invocation took 87.98 seconds,
including model loading. The PNG was decoded and visually checked. This is a
small runtime control, not a production-resolution benchmark. See
`image-generation-inference.json` and its recorded output path.

The editor's default landscape image size also passed: **1344 x 768**, nine
steps, 24.1 seconds for image generation and 72.73 seconds for the full separate
worker invocation including loading and prompt encoding. The PNG was decoded
and visually checked. This single run used cached files and is not a guarantee
for other prompts, batch sizes or cold starts. See
`image-generation-normal-resolution.json` and its per-run worker log. Model
downloads continued independently during this check.

The NVIDIA H.264 encoder also passed a real 30-frame encode/decode control;
the editor selected `h264_nvenc`. See `video-encoding-inference.json`.

A six-second speech-to-timeline control exposed a recognition problem: nearby
short speech regions were processed separately, losing sentence context and
missing the second script line. The speech backend now joins nearby regions
for recognition while retaining the original silence-cut intervals. Transcript
cache keys include the analysis version so stale results are not reused.
The comparison is in `speech-context-comparison.json`; the original failure is
retained in `edit-pipeline-before-context-v2.json` and its fixture folder.

The actual edited-video check now matches both script lines, exports two cuts,
and renders 97 frames with audio in 21.18 seconds. An uncertain word/alignment
and text mismatch still require review, and semantic approval was not run;
`REVIEW_REQUIRED` remains correct. See `edit-pipeline-inference.json`. This
bounded example does not certify transcript accuracy for other footage.

After these changes, 45 focused pipeline, model-file, semantic-editing and AI
generation tests passed. The model doctor now checks every indexed weight shard,
its declared safetensors extent, and required component/tokenizer files. Missing
shards, truncated weights and incomplete transfers cannot report ready. This
quick structural check complements the setup downloader's full SHA-256 checks;
it does not rehash multi-gigabyte files whenever the settings page opens.
The actual installed image model passes; Wan correctly remains unavailable
while its download is unfinished.

Video weights are now complete and all eleven LFS weight files passed SHA-256
verification. Actual image, text-to-video and image-to-video controls passed
together in 210.41 seconds including worker/model loading. The video controls
are 256x256 with 17 frames each, not production 720p tests. See
`output/validation/new-laptop/generation-inference.json`. Storage and memory
comparisons are recorded in `docs/MODEL_STORAGE_AND_MEMORY.md`.

Wan's tokenizer JSON repeatedly timed out on the normal transfer. It was
recovered separately without cancelling the weight download and verified against
the pinned repository's LFS SHA-256:
`20a46ac256746594ed7e1e3ef733b83fbc5a6f0922aa7480eda961743de080ef`.
Future setup runs also use resumable ranges for LFS tokenizer files. Four
download-recovery tests passed, including prefixed LFS hash handling and retaining
the normal path for small Git metadata.

The actual Z-Image BF16 text encoder passed CUDA prompt encoding and used
8,316,807,168 peak allocated VRAM bytes. The BF16 snapshot omitted the chat
template expected by current Diffusers; setup now supplies the official template
from pinned revision `f332072aa78be7aecdf3ee76d5c247082da564a6`, after checking
that its tokenizer settings match. The pinned BF16 weights and vocabulary remain
unchanged. Provenance is recorded in `image-tokenizer-template.json`.

A separate check with tiny random weights passed image generation, text-to-video
and image-to-video with staged prompt encoding and GPU offload. It exposed and
fixed a real Wan device mismatch: staged CPU embeddings must move to CUDA before
denoising. This check validates the library integration, not full-model memory
requirements or output quality. See `generation-api-control.json`.

The currently resumed downloads and coordinator run in independent hidden
processes. Current logs are `downloads/huggingface-resumed.log`,
`downloads/huggingface-resumed-errors.log`, `downloads/verification-resumed.log`,
and `downloads/verification-resumed-errors.log`. A separate image check runs as
soon as its weights are verified, before the larger Wan download finishes.

At 09:17 IST on 18 October, the earlier downloader and coordinator were no
longer running; the download log had stopped advancing at 07:44. Both were
relaunched at 09:18, reusing the existing files and range parts. Their new logs
are `downloads/huggingface-resumed-20261018-091812{,-errors}.log` and
`downloads/verification-resumed-20261018-091812{,-errors}.log`. The coordinator's
`-GenerationOnly` option checks the nine saved passing core receipts and waits
for the unfinished generation weights, avoiding another core inference run.

The setup scripts clear inherited `PYTHONPATH` so bootstrap Python 3.12 packages
cannot contaminate the new Python 3.13 environment. The preserved backup's CPU
Torch/torchaudio were restored to their original 2.9.1+cpu versions using verified
official wheels after an initial installation inherited that bootstrap path.

- `downloads/laptop-model-downloads.json`: per-model revision, selected files, destination and download status.
- `downloads/package-prefetch.log`: verified package cache; exact resolved
  package versions and upstream hashes are in `laptop-dependency-report.json`.
- `downloads/huggingface-model-setup.log`: resumable Hugging Face download log.
- `downloads/finish-environments-isolated.log`: current isolated Python/CUDA
  dependency installation; earlier attempt logs are retained for diagnosis.
- `downloads/llama-cuda-setup.log`: optional additional CUDA runtime download,
  superseded by the working Ollama GPU backend.
- `downloads/meaning-ollama-import.log`: successful import of the pinned GGUF.
- `output/validation/new-laptop/meaning-ollama-inference.json`: structured-output,
  meaning controls and measured GPU residency.
- `output/validation/new-laptop/ollama-inference.json`: initial vision pass and
  semantic-control failure, retained without hiding the failure.
- `output/validation/new-laptop/cuda-kernel.json`: isolated real CUDA arithmetic.
- `output/validation/new-laptop/embeddings-inference.json`: real sound embeddings.
- `downloads/project-test-suite-offline.log`: completed passing regression suite
  using preserved compatible packages while the new environment installed.

The setup remains in progress until GPU arithmetic, model inference and the
relevant feature checks have completed. Large image/video pipelines need
additional validation on the current 16 GB system RAM; their offload mode does
not imply they fit entirely in 12 GB VRAM.

## Eye Contact

The free Hsu neural gaze-flow backend is installed and selected. No NVIDIA
account, subscription, SDK or API key is required for this backend. Its model
files and isolated runtime are under `C:\Ai Models`; see
[the model provenance and setup](EYE_CONTACT_OPEN_MODELS.md).

Real CPU and CUDA controls both passed. The CPU control took 12.78 seconds
versus 123.13 seconds with CUDA on the same 115-frame sample, including
validation overhead, so CPU was selected. These are short control timings,
not sustained export benchmarks. The localhost export retained all 115 frames
and its audio track, and recorded actual neural corrections on 115 frames.

Results: `output/validation/new-laptop/eyecontact-open/localhost-inference.json`
and `C:\Ai Models\eyecontact\provider-benchmark.json`. This does not establish
quality parity with Maxine or guarantee results for glasses, large head turns,
or every lighting condition. The original Maxine integration remains optional.

## Sources

- https://ollama.com/library/qwen3.5:9b
- https://huggingface.co/Qwen/Qwen3.5-9B
- https://huggingface.co/Tongyi-MAI/Z-Image-Turbo
- https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/tree/367372dab44eb24c5908d1f6d867b66123cb390d
- https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers
- https://github.com/ggml-org/llama.cpp/releases/tag/b11011
