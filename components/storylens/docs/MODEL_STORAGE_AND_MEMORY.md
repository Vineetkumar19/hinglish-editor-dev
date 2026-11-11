# Storylens model storage and inference memory

This table preserves the comparison made before the user's seven-model upgrade
selection. For the selected replacements and their current activation status,
see `output/validation/new-laptop/C_DRIVE_MODEL_UPGRADE.md` and
`C:\Ai Models\logs\model-upgrade-completion.json`. All model weights now reside
physically under `C:\Ai Models`; former A: model directories are junctions.

Checked 18 October 2026. Laptop: RTX 5070 Ti Laptop GPU, approximately 12 GiB
VRAM, 16 GB RAM; planned RAM upgrade to 48 GB.

Storage is shown in GiB (the units Windows labels GB), except tiny files marked
MiB. Current sizes come from the downloaded-file manifest, local Ollama
manifests, and actual small model files. Upgrade sizes come from official
repository/registry metadata, selecting one weight format and all required
pipeline components. They exclude Python environments, conversion workspace,
rendered media, caches, and duplicate copies in other runtimes.

M = recorded measurement from an earlier successful inference. E = a broad
planning estimate, not a measured requirement or guaranteed fit. P = publisher's
reference figure, retaining its stated GB units. LLM estimates assume roughly
8K context, a single request, and the named quantization. Longer contexts,
larger batches, image sizes and video lengths increase memory use. A model's
on-disk precision can differ from the precision used during inference.

Ollama M values below are its reported loaded GPU residency, not complete
process/driver peak VRAM. These are historical loaded-inference figures, not
live idle GPU use. The local Ollama service was initially stopped and the custom
`storylens-meaning:4b` registration was absent. The installed runtime was started
and that registration restored from the existing GGUF without a model download.
All four expected Ollama tags are now listed. The semantic model occupies about
2.33 GiB in the original A: GGUF plus another 2.33 GiB in Ollama on C:; its disk
cell includes both copies. Upgrade disk cells describe one installation.

Upgrade candidates require accuracy/integration comparisons. They are not
guaranteed quality improvements or necessarily direct replacements.

| Task | Current model | Current disk | Current inference VRAM | Upgrade / alternative | Upgrade disk | Upgrade inference VRAM |
| --- | --- | ---: | --- | --- | ---: | --- |
| Planning and vision | Qwen3.5 9B Q4_K_M | 6.10 GiB | **5.46 GiB M** resident, 8K context | [Qwen3.5 27B Q4_K_M](https://ollama.com/library/qwen3.5:27b) | 16.28 GiB | **18–22 GiB E** fully on GPU; split CPU/GPU possible |
| Semantic judge / script meaning | Qwen3 4B Instruct 2507 Q4_K_M | **4.65 GiB total**, two 2.33-GiB copies | **3.61 GiB M** resident, 8K context | [Qwen3 8B Q4_K_M](https://ollama.com/library/qwen3:8b), already installed as compatibility model | 4.87 GiB | **6–8 GiB E**; semantic tests needed before switching |
| Roman Hinglish speech | Whisper-Hindi2Hinglish-Swift | 0.28 GiB | **0.5–1.5 GiB E**, FP16 | [Full Whisper large-v3, CTranslate2](https://huggingface.co/Systran/faster-whisper-large-v3) | about 2.88 GiB | **4–6 GiB E**, FP16, unbatched; Roman Hinglish behavior must be compared |
| Independent speech | faster-whisper large-v3-turbo | 1.51 GiB | **2–3 GiB E**, FP16, unbatched | [Full faster-whisper large-v3](https://huggingface.co/Systran/faster-whisper-large-v3) | about 2.88 GiB | **4–6 GiB E**, FP16, unbatched |
| Word timestamps | MMS 300M forced aligner | 1.18 GiB | **0.8–2 GiB E**, FP16 | Keep current specialist | — | — |
| Speech/silence detection | Silero VAD | about 0.011 GiB, bundled variants | **0**, runs on CPU | Keep current specialist | — | — |
| Documentary/text retrieval | multilingual-E5-small | 0.46 GiB | **0**, configured on CPU | [multilingual-E5-base](https://huggingface.co/intfloat/multilingual-e5-base) | about 1.04 GiB | **0 on CPU**; roughly **1.5–3 GiB E** if FP32 on GPU |
| Footage/image-text matching | CLIP ViT-B/32 | 0.57 GiB | **0.5–1.5 GiB E**, FP16 | [CLIP ViT-L/14](https://huggingface.co/openai/clip-vit-large-patch14) | about 1.59 GiB | **1–3 GiB E**, FP16, modest batches |
| Audio-text matching | LAION larger CLAP general | 0.73 GiB | **1–2 GiB E**, FP32 | Keep current; domain-specific CLAP is an alternative, not a clear size upgrade | — | — |
| Sound-library text search | Qwen3 Embedding 0.6B | 0.60 GiB | **1–2 GiB E**, short inputs | [Qwen3 Embedding 4B Q4_K_M](https://ollama.com/library/qwen3-embedding:4b) | 2.33 GiB | **3–5 GiB E**, short inputs; long documents/batches need more |
| Background removal | BiRefNet general lite, ONNX | 0.209 GiB | **0**, CPU provider | [Full BiRefNet general, ONNX](https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx) | 0.906 GiB | **0 on CPU**; GPU-provider peak not measured |
| Background removal fallback | ISNet general use, ONNX | 0.166 GiB | **0**, CPU provider | Same full BiRefNet option above | 0.906 GiB | **0 on CPU**; GPU-provider peak not measured |
| Face location / framing | YuNet | 0.22 MiB | **0**, configured on CPU | Keep current; a different detector would need integration | — | — |
| Images / first frames | Z-Image Turbo, official BF16 files; FP8 transformer storage during offloaded inference | 19.13 GiB | **7.75 GiB M for text encoding only**; complete pipeline peak not recorded; 1344x768 generation passed on this GPU | [FLUX.2 Klein 4B, complete BF16 pipeline](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), an alternative supporting image editing | about 14.87 GiB | **about 13 GB P**; supports CPU offload, but not measured/integrated here |
| Text-to-video / image-to-video | Wan2.2 TI2V 5B; FP8 transformer storage and staged CPU encoding | 31.85 GiB | **Full peak not recorded**; both 256x256, 17-frame controls passed on this 12-GB GPU with offload | [Wan2.2 A14B T2V](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B-Diffusers) or [A14B I2V](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B-Diffusers) | about **117.5 GiB each**, official published Diffusers weights | **80 GB P** for the official native reference command with dtype conversion; lower-memory quantized/offloaded paths need separate validation |
| Older fixed-tag compatibility | Qwen3 8B Q4_K_M | 4.87 GiB | **6–8 GiB E** | [Qwen3 14B Q4_K_M](https://ollama.com/library/qwen3:14b) | 8.64 GiB | **10–12 GiB E**, tight at 8K context; partial offload may be needed |
| Legacy semantic verifier | Qwen2.5 1.5B Instruct, FP16 | 2.89 GiB | **3–5 GiB E**; not separately profiled | Use the already downloaded Qwen3 4B semantic engine | 2.33 GiB per model copy, already present | **3.61 GiB M** resident in previous test |

Free Eye Contact is now installed and tested. The selected Hsu ONNX graphs total
2.12 MB and the separate MediaPipe face-landmarker file is 3.76 MB; runtime
packages take additional space. The chosen CPU provider uses no model VRAM.
CPU and CUDA both passed, and CPU was faster on the bounded sample. This is a
practical alternative whose quality has not been shown equivalent to Maxine.
See `docs/EYE_CONTACT_OPEN_MODELS.md`. Ollama itself is the runtime; it is not
an additional language model.

## RAM and VRAM offloading

- **16 GB RAM + 12-GB GPU:** the current small controls passed for the selected
  models. Large image/video models already rely on staged loading, offloading,
  and Windows virtual memory. Their full-resolution video performance is not
  certified. The specialist speech/CLIP/CLAP models do not need a larger GPU
  merely to fit individually at the tested small batch sizes.
- **48 GB RAM + 12-GB GPU:** a reasonable platform to experiment with Qwen3.5
  27B Q4 CPU/GPU splitting, and it gives image/video offloading more headroom.
  This is a fit/performance inference, not a benchmark on this laptop. CPU-held
  language-model layers compute on the CPU and can slow token generation.
- **A14B:** 48 GB system RAM does not guarantee a fit with the existing worker.
  A different quantized pipeline and finer-grained offload would need to be
  integrated and tested. The currently available two-expert FP32 transformer
  files account for about 106.46 GiB of the 117.5-GiB pipeline. Converting just
  those experts to BF16 would give approximately 64.3 GiB of pipeline weights;
  FP8 storage would give approximately 37.7 GiB. These are arithmetic
  weight-storage estimates, not official downloaded variants, RAM requirements,
  or VRAM measurements. They exclude conversion workspace and runtime buffers.

RAM and VRAM are separate pools, not one interchangeable 60-GB allocation.
The runtime must support splitting; activations and the current layer still
need space on the GPU. Keep several GB of RAM for Windows, the editor and media
buffers. Context length, resolution, frames and concurrent jobs affect fit.
All models are not intended to remain loaded simultaneously.

Changing E5, CLIP or Qwen embedding models requires rebuilding the corresponding
search index, even if an output dimension is kept the same.

Before restoring the semantic runtime copy, A: had **20.27 GiB free** and C:
**275.46 GiB free**. A new 27B
copy on A: would leave only about 4 GiB before extra caches, so expand the
volume or choose C: before installing upgrades. Both official A14B pipelines
together are about 235 GiB before shared-file deduplication.

Machine-readable size/revision evidence:
`output/validation/new-laptop/model-resource-metadata.json`.
Measured memory evidence: `ollama-inference.json`,
`meaning-ollama-inference.json`, and `image-text-encoder.json` in the same folder.
Generation success is recorded in `generation-inference.json`; these are bounded
controls, not a production video benchmark.

Publisher memory references: [FLUX.2 Klein model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B),
[Wan A14B native reference](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B),
and [faster-whisper runtime/precision benchmarks](https://github.com/SYSTRAN/faster-whisper).
