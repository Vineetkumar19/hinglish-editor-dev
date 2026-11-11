# Storylens project onboarding

This is the initial architecture audit. Subsequent setup and validation are
recorded in [LOCAL_MODELS_LAPTOP.md](LOCAL_MODELS_LAPTOP.md).

Read-through on 17 October 2026 after moving to `A:\Full Drive\remove silence`.
This is an architecture and migration orientation, not a claim that every source line, media file or model weight has been audited.

## Product and runtime

Storylens began as a local Roman Hinglish script-based cutter and has expanded into a modular AI editing application. The Python package name remains `hinglish-auto-cutter`. The main standalone UI is HTML/CSS/JavaScript served by a Python localhost HTTP server. It is not a Node/Electron application.

`Run Hinglish Editor.bat` launches `python -m hinglish_app`. `hinglish_app/server.py` validates jobs, dispatches feature pipelines and exposes review/rebuild operations. The conversational assistant chooses supported editing tools, persists sessions and chains outputs. A shared editing lock limits overlap within the application; separate external workers remain independent.

## Module map

| Modules | Responsibility |
| --- | --- |
| `hinglish_cut` | Original script matching, local speech recognition/alignment, conservative cuts, evaluation and FCP7 XML export |
| `hinglish_clean`, `hinglish_semantic` | Silence removal, retake/filler proposals, meaning-based assembly, review choices and local correction examples |
| `hinglish_captions` | Roman Hinglish timed captions, templates, editable review outputs and caption layers |
| `hinglish_broll`, `hinglish_visuals`, `hinglish_zoom` | Stock/local cutaways, entity-specific visual research and evaluation, face-aware planned zooms |
| `hinglish_sound`, `hinglish_eyecontact` | Sound-library planning/mixing and optional NVIDIA Maxine gaze correction |
| `hinglish_shorts` | Long-form selection and short-format output |
| `hinglish_aigen`, `hinglish_aiimage`, `hinglish_aivideo` | Shared separate diffusion worker, image generation and video generation |
| `hinglish_motion` | Local-model plans bound to browser-rendered animation templates |
| `hinglish_beats`, `hinglish_cinematic` | Music beat analysis, editor beat effects and music-led reel assembly |
| `hinglish_niche` | General/Cricket/Gaming preferences, research, documentary evidence, style memory and retrieval |
| `hinglish_eval` | Feature-specific quality checks and bounded correction/retry orchestration |
| `hinglish_publish` | Publishing drafts, providers, scheduling and worker state |
| `hinglish_license`, `hinglish_saas` | Licensing, accounts, billing, support and service-side persistence |
| `editor_plugins` | Premiere CEP/UXP, After Effects CEP and Resolve integration |

## Main model paths

- Speech: Oriserve Whisper Hindi-to-Hinglish Swift; optional faster-whisper large-v3-turbo for semantic workflows; Silero speech activity detection; romanized MMS forced alignment.
- Planning: Ollama Qwen3 8B where supported, with a bundled Qwen3 4B GGUF/llama.cpp fallback. The bundled server launcher currently requests zero GPU layers.
- Visual assessment: optional Ollama Qwen2.5-VL, alongside CLIP-based search/ranking and project-specific checks.
- Documentary retrieval: fixed multilingual E5 small text embeddings and `library/creator-profiles/editing-dna.sqlite3`.
- Generation: separate diffusers environment using Z-Image Turbo and Wan 2.2 TI2V 5B, with VRAM-based offload settings.

## Persistent state to preserve

`models` contains local model caches/manifests. `library` contains creator profiles, style evidence, reusable assets and sound packs. `cache` contains intermediate analyses, correction examples and assistant sessions. `output` and `validation` contain generated timelines, videos, reviews and previous validation receipts. `input` contains user source material. Keep originals and reference drives when relocating absolute-path references.

The two documentary libraries, **vineet documentry edit** and **cricAddict**, remain separate. Their saved knowledge is retrieval memory and measured reference evidence, not fine-tuned model weights. More stored evidence does not automatically create new animation rigs. The single-reference study documentation also records a user-review boundary before advancing to the next reference; onboarding does not resume that workflow.

## Validation boundary

The folder has a substantial `tests` suite and historical real-media validation reports. Those reports describe prior environments and are not proof that this new machine is ready. No new inference benchmark, complete automated suite, editor import check or diffusion-generation run has been completed during this read-through.

The initial blockers are a broken relocated virtual environment, CPU-only PyTorch, old absolute model paths and a stale AI generation install configuration. See `../NEW LAPTOP - SETUP.md` for software, download status and the setup sequence. No application source was changed during onboarding.
